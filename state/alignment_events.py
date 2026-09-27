#!/usr/bin/env python3
"""Append-only alignment bus: conductor/state/events.jsonl (Bob ↔ Web Bob ↔ builders)."""
from __future__ import annotations

import fcntl
import json
import os
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

CT = ZoneInfo("America/Chicago")
STATE_DIR = Path("conductor/state")
EVENTS_FILE = "events.jsonl"
LOCK_FILE = ".events.lock"
MAX_LINES = 2000


def _folder(root: Path) -> Path:
    path = root / STATE_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def _now_ct() -> str:
    return datetime.now(CT).strftime("%Y-%m-%d %H:%M:%S CT")


def _lock(root: Path):
    handle = (_folder(root) / LOCK_FILE).open("a")
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
    return handle


def _line_count(path: Path) -> int:
    if not path.is_file():
        return 0
    count = 0
    with path.open("r", errors="replace") as handle:
        for _ in handle:
            count += 1
    return count


def append_event(root: Path, *, actor: str, kind: str, summary: str, **fields) -> int:
    """Append one event; returns monotonic seq."""
    folder = _folder(root)
    path = folder / EVENTS_FILE
    handle = _lock(root)
    try:
        seq = _line_count(path) + 1
        row = {
            "seq": seq,
            "at": _now_ct(),
            "ts": time.time(),
            "actor": (actor or "unknown")[:40],
            "kind": (kind or "note")[:40],
            "summary": (summary or "")[:500],
        }
        for key, value in fields.items():
            if key in row:
                continue
            if isinstance(value, (str, int, float, bool)) or value is None:
                row[key] = value
            elif isinstance(value, (list, dict)):
                row[key] = value
        with path.open("a", encoding="utf-8") as out:
            out.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            out.flush()
            os.fsync(out.fileno())
        if seq > MAX_LINES:
            _rotate(path)
        return seq
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def _rotate(path: Path) -> None:
    try:
        lines = path.read_text(errors="replace").splitlines()
    except OSError:
        return
    keep = lines[-MAX_LINES:]
    path.write_text("\n".join(keep) + ("\n" if keep else ""))


def read_events(root: Path, *, since_seq: int = 0, limit: int = 80) -> list[dict]:
    path = _folder(root) / EVENTS_FILE
    if not path.is_file():
        return []
    rows: list[dict] = []
    with path.open("r", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if int(row.get("seq") or 0) <= since_seq:
                continue
            rows.append(row)
    return rows[-limit:]


def read_events_since_paginated(
    root: Path,
    *,
    since_seq: int = 0,
    page_size: int = 80,
    max_pages: int = 8,
) -> list[dict]:
    """Read events after since_seq oldest-first, up to page_size * max_pages."""
    path = _folder(root) / EVENTS_FILE
    if not path.is_file():
        return []
    cap = max(1, page_size) * max(1, max_pages)
    rows: list[dict] = []
    with path.open("r", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if int(row.get("seq") or 0) <= since_seq:
                continue
            rows.append(row)
            if len(rows) >= cap:
                break
    return rows


def latest_seq(root: Path) -> int:
    path = _folder(root) / EVENTS_FILE
    if not path.is_file():
        return 0
    last = 0
    with path.open("r", errors="replace") as handle:
        for line in handle:
            try:
                last = max(last, int(json.loads(line).get("seq") or 0))
            except json.JSONDecodeError:
                continue
    return last
