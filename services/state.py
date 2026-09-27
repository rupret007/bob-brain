#!/usr/bin/env python3
"""Small, fsynced state primitives shared by the services and queue hooks."""
from __future__ import annotations

import contextlib
import fcntl
import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(os.environ.get("BOB_ROOT", Path(__file__).resolve().parents[2])).resolve()
CONDUCTOR = ROOT / "conductor"


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextlib.contextmanager
def lock(name, blocking=True):
    folder = CONDUCTOR / "locks"
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / (name + ".lock")).open("a+") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        yield handle


def atomic_write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="." + path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            out.write(text)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, path)
        # Persist the rename as well as the contents (macOS supports directory fsync).
        fd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def read_json(path, default=None):
    path = Path(path)
    return json.loads(path.read_text()) if path.exists() else default


def write_json(path, value):
    atomic_write(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def _rows(path):
    """Repair only an interrupted final append; refuse corruption in the middle."""
    path = Path(path)
    if not path.exists():
        return []
    data = path.read_bytes()
    lines = data.splitlines(keepends=True)
    rows, offset = [], 0
    for i, line in enumerate(lines):
        try:
            row = json.loads(line)
        except (ValueError, UnicodeDecodeError):
            if i != len(lines) - 1:
                raise ValueError("journal corruption before final line: " + str(path))
            atomic_write(path.with_name(path.name + ".interrupted-tail"), line.decode("utf-8", "replace"))
            atomic_write(path, data[:offset].decode("utf-8"))
            break
        rows.append(row)
        offset += len(line)
    if rows and path.read_bytes() and not path.read_bytes().endswith(b"\n"):
        with path.open("ab") as out:
            out.write(b"\n")
            out.flush()
            os.fsync(out.fileno())
    return rows


def journal_rows(name):
    with lock(name):
        return _rows(CONDUCTOR / (name + ".jsonl"))


def _append(path, value):
    with path.open("a", encoding="utf-8") as out:
        out.write(json.dumps(value, sort_keys=True) + "\n")
        out.flush()
        os.fsync(out.fileno())


def append_event(name, value):
    with lock(name):
        path = CONDUCTOR / (name + ".jsonl")
        _rows(path)
        _append(path, dict(value, at=stamp(), timestamp=time.time()))


def jobs():
    return {r["job_id"]: r for r in journal_rows("jobs")}


def job_event(job_id, state=None, **fields):
    if state and state not in ("queued", "launched", "running", "blocked", "harvested"):
        raise ValueError("invalid job state")
    with lock("jobs"):
        path = CONDUCTOR / "jobs.jsonl"
        previous = next((r for r in reversed(_rows(path)) if r["job_id"] == job_id), {})
        expected = fields.pop("expected_token", None)
        if expected is not None and previous.get("attempt_token") != expected:
            return previous
        expected_states = fields.pop("expected_states", None)
        if expected_states is not None and previous.get("state") not in expected_states:
            return previous
        row = dict(previous, **fields)
        row.update(job_id=job_id, state=state or previous.get("state", "launched"))
        # Reconciliation may discover a closeout after the launch but before running.
        if previous.get("state") == "harvested" and previous.get("outcome") != "blocked" and row["state"] != "harvested" and not fields.get("invalidate_result"):
            raise ValueError("cannot relaunch a harvested job: " + job_id)
        if all(previous.get(k) == v for k, v in row.items()):
            return previous
        row.update(at=stamp(), timestamp=time.time())
        row.setdefault("launched_at", time.time())
        _append(path, row)
        return row


def alert(key, message=None):
    """Persist alerts only. runtime.py is the sole STATUS.md writer."""
    with lock("status"):
        path = CONDUCTOR / "alerts.json"
        entries = read_json(path, {})
        if message:
            entries[key] = " ".join(message.split())
        else:
            entries.pop(key, None)
        write_json(path, entries)


def log(message):
    print(stamp() + " " + message, flush=True)
