"""Durable Web Bob tasks. Every transition is locked, fsynced and claim fenced."""
from __future__ import annotations

import contextlib
import fcntl
import json
import os
import re
import time
import uuid
from pathlib import Path

MODEL_WORKERS = ("codex", "claude", "cursor", "gemini", "minimax")
WORKERS = (*MODEL_WORKERS, "mini")
CONCURRENCY = {"gemini": 3, "minimax": 3}
ACTIVE = ("claimed", "running")
TERMINAL = ("succeeded", "failed")
LEASE_SECONDS = 90
MAX_ATTEMPTS = 3


def file_request(prompt):
    """A small explicit temporary-file task may use any tool-capable CLI."""
    match = re.fullmatch(r"(?:please\s+)?write\s+([^\n]{1,1000}?)\s+to\s+(/tmp/[A-Za-z0-9_-]+\.(?:txt|md|json))\s*", prompt, re.I)
    return (match[1].strip("\"'"), match[2]) if match else None


def worker_name(value):
    value = {"cursor-agent": "cursor", "mini CPU": "mini"}.get(value, value)
    if value not in (*WORKERS, "auto"):
        raise ValueError("Choose codex, claude, cursor-agent, gemini, minimax, or mini; never Grok.")
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


def worker_order(kind):
    return {"coding": ("codex", "cursor"), "artifact": ("codex", "cursor", "claude"), "local": ("mini",),
            "analysis": ("claude", "gemini", "minimax", "codex", "cursor")}[kind]


def capacity(worker):
    return CONCURRENCY.get(worker, 1)


def group_complete(members):
    if not members:
        return False
    first = members[0]
    size = first.get("group_size")
    return (type(size) is int and 2 <= size <= 24 and len(members) == size
            and {r.get("group_index") for r in members} == set(range(size))
            and all((r.get("group_size"), r.get("conversation_id"), r.get("group_goal")) ==
                    (size, first.get("conversation_id"), first.get("group_goal")) for r in members))


def enqueue(root, conversation_id, request_id, prompt, *, worker="auto", kind="analysis", source_file=None,
            group_id=None, group_size=None, group_index=None, group_goal=None, title=None, local_suite=None):
    worker = worker_name(worker)
    if worker == "mini":
        kind = "local"
    if kind not in ("analysis", "coding", "artifact", "local") or not prompt.strip():
        raise ValueError("Task needs a description and a supported kind")
    if kind == "artifact" and not file_request(prompt):
        raise ValueError("Small file tasks require an explicit text and /tmp file destination")
    if worker != "auto" and worker not in worker_order(kind):
        raise ValueError("Code changes require codex or cursor-agent. API workers can analyze supplied evidence.")
    if group_id and (type(group_size) is not int or not 2 <= group_size <= 24 or
                     type(group_index) is not int or not 0 <= group_index < group_size):
        raise ValueError("A task group requires a valid size and unique subtask index")
    key = "webbob:" + str(conversation_id) + ":" + str(request_id)
    identifier = "webchat-" + uuid.uuid5(uuid.NAMESPACE_URL, key).hex
    with locked(root) as path:
        rows = _read(path)
        if identifier in rows:
            row = rows[identifier]
            if (row["prompt"], row["requested_worker"], row["kind"], row.get("group_id"), row.get("group_size"),
                row.get("group_index"), row.get("group_goal"), row.get("title"), row.get("local_suite")) != (
                    prompt, worker, kind, group_id, group_size, group_index, group_goal, title, local_suite):
                raise ValueError("This request ID already belongs to a different task")
            return row
        for member in (r for r in rows.values() if group_id and r.get("group_id") == group_id):
            if (member.get("group_index") == group_index or
                (member.get("group_size"), member.get("conversation_id"), member.get("group_goal")) !=
                    (group_size, conversation_id, group_goal)):
                raise ValueError("Conflicting task group membership")
        return _append(path, dict(id=identifier, conversation_id=conversation_id, request_id=request_id,
                                 prompt=prompt, requested_worker=worker, kind=kind, source_file=source_file,
                                 status="queued", attempts=0, created_at=time.time(), delivered_at=None,
                                 group_id=group_id, group_size=group_size, group_index=group_index,
                                 group_goal=group_goal, title=title, local_suite=local_suite,
                                 tried_workers=[], max_attempts=max(MAX_ATTEMPTS, len(worker_order(kind))),
                                 worker=None, claim_token=None, lease_until=0, retry_at=0), "enqueued")


def claim(root, worker, now=None, *, identifier=None, allow_fallback=False, limit=None):
    worker = worker_name(worker)
    if worker == "auto":
        raise ValueError("Claims require an actual worker")
    now = time.time() if now is None else now
    with locked(root) as path:
        rows = _read(path)
        ceiling = capacity(worker) if limit is None else max(0, min(capacity(worker), int(limit)))
        if sum(r["status"] in ACTIVE and r["worker"] == worker for r in rows.values()) >= ceiling:
            return None
        for row in sorted(rows.values(), key=lambda r: r["created_at"]):
            if identifier and row["id"] != identifier:
                continue
            if row["status"] != "queued" or row.get("retry_at", 0) > now:
                continue
            if row["requested_worker"] not in ("auto", worker) and not allow_fallback:
                continue
            if worker not in worker_order(row["kind"]):
                continue
            if row.get("group_id") and not group_complete([r for r in rows.values() if r.get("group_id") == row["group_id"]]):
                continue  # Saved intent repairs an interrupted multi-row append before dispatch.
            row.update(status="claimed", worker=worker, claim_token=uuid.uuid4().hex,
                       claimed_at=now, lease_until=now + LEASE_SECONDS, attempts=row["attempts"] + 1,
                       pid=None, started_at=None, execution_started_at=None, error=None)
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
        elif event == "executing":
            row.update(execution_started_at=now)
        elif event == "heartbeat":
            pass
        elif event == "succeeded":
            if not fields.get("result", "").strip():
                raise ValueError("An empty result cannot finish a task")
            row.update(status="succeeded", finished_at=now)
        elif event in ("retry", "busy"):
            if event == "busy":
                row["attempts"] -= 1  # A lane race is not a failed execution.
            if event == "retry":
                row["tried_workers"] = list(dict.fromkeys([*row.get("tried_workers", []), row["worker"]]))
            row.update(status="failed" if row["attempts"] >= row.get("max_attempts", MAX_ATTEMPTS) else "queued",
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
            row["tried_workers"] = list(dict.fromkeys([*row.get("tried_workers", []), row["worker"]]))
            row.update(status="failed" if row["attempts"] >= row.get("max_attempts", MAX_ATTEMPTS) else "queued",
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
