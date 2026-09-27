#!/usr/bin/env python3
"""Durable ask queue. Producers append through enqueue(); only the scheduler assigns.

Each journal line is a complete version of one request. Readers fold by id.
The queue-store lock is deliberately distinct from the scheduler's queue lock.
"""
from __future__ import annotations

import argparse
import json
import re
import time
import uuid
from pathlib import Path, PurePosixPath

import state

ROLES = ("build", "review", "research", "critique", "test", "council")
STATUSES = ("queued", "running", "retry", "blocked", "split", "waiting-siblings",
            "review", "council", "completed", "jeff-draft", "cancelled")


def scopes(value=None):
    """Literal repository-relative files/directories, with '.' meaning whole repo."""
    value = ["."] if value is None else value
    if not isinstance(value, list) or not value:
        raise ValueError("scope must be a nonempty list of relative files/directories")
    result = []
    for name in value:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("scope entries must be paths")
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or ".git" in path.parts or any(c in name for c in "*?[]\\"):
            raise ValueError("scope must use literal relative paths, without traversal or globs")
        result.append(str(path))
    return sorted(set(result))


def overlaps(left, right):
    return any(a == "." or b == "." or a == b or a.startswith(b + "/") or b.startswith(a + "/")
               for a in scopes(left) for b in scopes(right))


def contains(scope, path):
    return any(s == "." or path == s or path.startswith(s + "/") for s in scopes(scope))


def normalize(spec):
    row = dict(spec)
    row["id"] = row.get("id") or "ask-" + uuid.uuid4().hex[:16]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,119}", row["id"]):
        raise ValueError("invalid queue id")
    row["goal"] = row.get("goal", row.get("prompt", "")).strip()
    if not row["goal"] or not row.get("repo"):
        raise ValueError("queue requests require goal and repo")
    row["repo"] = str(Path(row["repo"]).expanduser().resolve())
    row["role"] = row.get("role") or ("build" if row.get("kind") == "coding" else "research")
    if row["role"] not in ROLES:
        raise ValueError("unknown queue role")
    row["scope"] = scopes(row.get("scope"))
    row["priority"] = int(row.get("priority", 99))
    row["kind"] = "coding" if row["role"] == "build" else "non-coding"
    row["prompt"] = row["goal"]
    commands = row.get("test_commands", [])
    if not isinstance(commands, list) or any(not isinstance(c, list) or not c or
            any(not isinstance(a, str) or not a for a in c) for c in commands):
        raise ValueError("test_commands must be a list of nonempty argv lists")
    if row.get("parts"):
        if not isinstance(row["parts"], list):
            raise ValueError("parts must be a list")
        for index, part in enumerate(row["parts"]):
            if not isinstance(part, dict) or part.get("parts"):
                raise ValueError("parts must be flat job specifications")
            normalize(_child_spec(row, part, index + 1))
    return row


def child_id(parent, suffix):
    # Retain uniqueness even for long producer-assigned ids.
    import hashlib
    return parent[:65] + "-" + hashlib.sha256(parent.encode()).hexdigest()[:8] + "-" + suffix


def _child_spec(parent, part, index):
    inherited = {k: parent[k] for k in ("repo", "role", "priority", "scope", "project",
                                       "test_commands", "base_ref") if k in parent}
    inherited.update(part)
    inherited.update(id=child_id(parent["id"], "part-" + str(index)), parent_id=parent["id"])
    return inherited


def _path(conductor=None):
    path = (conductor if conductor is not None else state.CONDUCTOR) / "state/queue.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _records(conductor=None):
    rows = state._rows(_path(conductor))
    if any(not isinstance(r, dict) or not r.get("id") for r in rows):
        raise ValueError("invalid queue journal row")
    return {r["id"]: r for r in rows}


def snapshot(*, conductor=None):
    with state.lock("queue-store", conductor=conductor):
        return _records(conductor)


def _write(previous, fields, conductor=None):
    row = dict(previous, **fields)
    if row.get("status") not in STATUSES:
        raise ValueError("invalid queue status")
    if row == previous:
        return previous
    row["updated_at"] = time.time()
    state._append(_path(conductor), row)
    return row


def enqueue(spec, *, conductor=None):
    row = normalize(spec)
    with state.lock("queue-store", conductor=conductor):
        previous = _records(conductor).get(row["id"])
        if previous:
            # Replaying a durable producer id never launches another copy.
            if any(previous.get(k) != row.get(k) for k in ("goal", "repo", "role", "scope", "parts", "test_commands", "depends_on")):
                raise ValueError("queue id already belongs to a different request")
            return previous
        return _write({}, dict(row, status="queued", owner=None, heartbeat=None,
                               created_at=time.time(), stage=row.get("stage", "work")), conductor)


def edit_pending(identifier, *, priority=None, status=None, conductor=None):
    """Producer edits are allowed only before the scheduler creates an execution."""
    with state.lock("queue-store", conductor=conductor):
        previous = _records(conductor)[identifier]
        if previous.get("execution_id") or previous["status"] not in ("queued", "blocked", "cancelled"):
            raise ValueError("Job already assigned; pending-queue edits cannot stop a worker.")
        fields = {}
        if priority is not None:
            fields["priority"] = int(priority)
        if status is not None:
            if status not in ("queued", "blocked", "cancelled"):
                raise ValueError("invalid pending queue status")
            fields.update(status=status, reason="paused by producer" if status == "blocked" else "")
        return _write(previous, fields, conductor)


def update(identifier, **fields):
    """Compare execution tokens so an old worker cannot overwrite a newer attempt."""
    expected = fields.pop("expected_token", None)
    with state.lock("queue-store"):
        previous = _records()[identifier]
        if expected is not None and previous.get("attempt_token") != expected:
            return previous
        if previous["status"] in ("cancelled", "jeff-draft", "completed"):
            return previous
        return _write(previous, fields)


def split(identifier):
    """Idempotent expansion, including recovery after a crash between child appends."""
    parent = snapshot()[identifier]
    children = []
    for index, part in enumerate(parent.get("parts", []), 1):
        children.append(enqueue(_child_spec(parent, part, index))["id"])
    if children:
        update(identifier, status="split", children=children)
    return children


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("enqueue", "list"))
    parser.add_argument("spec", nargs="?", type=Path, help="JSON request file")
    args = parser.parse_args()
    if args.action == "enqueue" and args.spec is None:
        parser.error("enqueue requires a JSON request file")
    print(json.dumps(enqueue(json.loads(args.spec.read_text())) if args.action == "enqueue"
                     else list(snapshot().values()), indent=2))


if __name__ == "__main__":
    main()
