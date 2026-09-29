"""Durable Web Bob tasks. Every transition is locked, fsynced and claim fenced."""
from __future__ import annotations

import contextlib
import fcntl
import json
import os
import time
import uuid
from pathlib import Path

WORKERS = ("codex", "claude", "cursor", "gemini", "minimax")
ACTIVE = ("claimed", "running")
TERMINAL = ("succeeded", "failed")
LEASE_SECONDS = 90
MAX_ATTEMPTS = 3


def worker_name(value):
    value = "cursor" if value == "cursor-agent" else value
    if value not in (*WORKERS, "auto"):
        raise ValueError("Choose codex, claude, cursor-agent, gemini, or minimax; never Grok.")
    return value


@contextlib.contextmanager
def locked(root):
    folder = Path(root) / "conductor/state"
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / ".queue.lock").open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield folder / "queue.jsonl"


def _read(path):
    if not path.exists():
        return {}
    data = path.read_bytes()
    rows, offset = {}, 0
    for line in data.splitlines(keepends=True):
        try:
            row = json.loads(line)
            rows[row["id"]] = row
        except (ValueError, KeyError, TypeError):
            if offset + len(line) != len(data) or line.endswith(b"\n"):
                raise ValueError("Task queue corruption; refusing to discard committed records") from None
            # Only a torn final append can be discarded, under the writer lock.
            with path.open("r+b") as handle:
                handle.truncate(offset)
                handle.flush()
                os.fsync(handle.fileno())
            break
        offset += len(line)
    if data and not data.endswith(b"\n") and offset == len(data):
        with path.open("ab") as handle:
            handle.write(b"\n")
            handle.flush()
            os.fsync(handle.fileno())
    return rows


def _append(path, row, event, now=None):
    row = dict(row, event=event, updated_at=time.time() if now is None else now)
    with open(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600), "a") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return row


def tasks(root):
    with locked(root) as path:
        return _read(path)


def enqueue(root, conversation_id, request_id, prompt, *, worker="auto", kind="analysis", source_file=None):
    worker = worker_name(worker)
    if kind not in ("analysis", "coding") or not prompt.strip():
        raise ValueError("Task needs a description and a supported kind")
    if kind == "coding" and worker in ("gemini", "minimax", "claude"):
        raise ValueError("Code changes require codex or cursor-agent. API workers can analyze supplied evidence.")
    key = "webbob:" + str(conversation_id) + ":" + str(request_id)
    identifier = "webchat-" + uuid.uuid5(uuid.NAMESPACE_URL, key).hex
    with locked(root) as path:
        rows = _read(path)
        if identifier in rows:
            row = rows[identifier]
            if (row["prompt"], row["requested_worker"], row["kind"]) != (prompt, worker, kind):
                raise ValueError("This request ID already belongs to a different task")
            return row
        return _append(path, dict(id=identifier, conversation_id=conversation_id, request_id=request_id,
                                 prompt=prompt, requested_worker=worker, kind=kind, source_file=source_file,
                                 status="queued", attempts=0, created_at=time.time(), delivered_at=None,
                                 worker=None, claim_token=None, lease_until=0, retry_at=0), "enqueued")


def claim(root, worker, now=None):
    worker = worker_name(worker)
    if worker == "auto":
        raise ValueError("Claims require an actual worker")
    now = time.time() if now is None else now
    with locked(root) as path:
        rows = _read(path)
        if any(r["status"] in ACTIVE and r["worker"] == worker for r in rows.values()):
            return None
        for row in sorted(rows.values(), key=lambda r: r["created_at"]):
            if row["status"] != "queued" or row.get("retry_at", 0) > now:
                continue
            if row["requested_worker"] not in ("auto", worker):
                continue
            if row["kind"] == "coding" and worker not in ("codex", "cursor"):
                continue
            row.update(status="claimed", worker=worker, claim_token=uuid.uuid4().hex,
                       claimed_at=now, lease_until=now + LEASE_SECONDS, attempts=row["attempts"] + 1,
                       pid=None, started_at=None, error=None)
            return _append(path, row, "claimed", now)
    return None


def transition(root, identifier, token, event, *, now=None, **fields):
    now = time.time() if now is None else now
    with locked(root) as path:
        row = _read(path).get(identifier)
        if not row or row["status"] not in ACTIVE or row["claim_token"] != token or row["lease_until"] <= now:
            return None
        if event == "running":
            row.update(status="running", started_at=now, pid=os.getpid())
        elif event == "heartbeat":
            pass
        elif event == "succeeded":
            if not fields.get("result", "").strip():
                raise ValueError("An empty result cannot finish a task")
            row.update(status="succeeded", finished_at=now)
        elif event in ("retry", "busy"):
            if event == "busy":
                row["attempts"] -= 1  # A lane race is not a failed execution.
            row.update(status="failed" if row["attempts"] >= MAX_ATTEMPTS else "queued",
                       retry_at=now + (5 if event == "busy" else min(60, 5 * 2 ** row["attempts"])),
                       claim_token=None)
            if row["status"] == "failed":
                row["finished_at"] = now
        else:
            raise ValueError("Unknown task transition")
        row.update(fields, heartbeat_at=now, lease_until=now + LEASE_SECONDS if row["status"] in ACTIVE else 0)
        return _append(path, row, event, now)


def recover(root, worker_alive, now=None):
    """Requeue lost claims; a live expired execution must exit before replacement."""
    now = time.time() if now is None else now
    changed = []
    with locked(root) as path:
        for row in _read(path).values():
            if row["status"] not in ACTIVE:
                continue
            alive = worker_alive(row)
            # A freshly launched worker has time to acquire its execution lock.
            if alive or (row["status"] == "claimed" and row["lease_until"] > now):
                continue
            row.update(status="failed" if row["attempts"] >= MAX_ATTEMPTS else "queued",
                       claim_token=None, lease_until=0, retry_at=now,
                       error="Worker exited before returning a result; claim recovered")
            if row["status"] == "failed":
                row["finished_at"] = now
            changed.append(_append(path, row, "recovered", now))
    return changed


def delivered(root, identifier, message_id):
    with locked(root) as path:
        row = _read(path)[identifier]
        if row["status"] not in TERMINAL:
            raise ValueError("Cannot acknowledge an unfinished result")
        if not row.get("delivered_at"):
            row.update(delivered_at=time.time(), result_message_id=message_id)
            return _append(path, row, "delivered")
        return row
