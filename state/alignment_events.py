#!/usr/bin/env python3
"""Append-only alignment bus: versioned shared journal (Bob ↔ Web Bob ↔ builders)."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import secrets
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

CT = ZoneInfo("America/Chicago")
STATE_DIR = Path("conductor/state")
EVENTS_FILE = "coordination-events.jsonl"
LEGACY_EVENTS_FILE = "events.jsonl"
LOCK_FILE = ".events.lock"


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


def _read_path(root: Path) -> Path:
    folder = root / STATE_DIR
    current = folder / EVENTS_FILE
    return current if current.exists() else folder / LEGACY_EVENTS_FILE


def _inherit_legacy(folder: Path) -> None:
    """Copy retained bytes once, under the shared writer lock; never edit v1.

    Legacy publishers can keep their own journal without trimming this one.
    Events written only to v1 after migration are not claimed to be synchronized.
    """
    target = folder / EVENTS_FILE
    legacy = folder / LEGACY_EVENTS_FILE
    if target.exists() or not legacy.exists():
        return
    # Validate before copying; a malformed journal must not hide history.
    for _ in _rows(legacy):
        pass
    temporary = folder / (".coordination-import-" + secrets.token_hex(8))
    try:
        with open(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as out:
            with legacy.open("rb") as source:
                import shutil
                shutil.copyfileobj(source, out)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, target)
        fd = os.open(folder, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        temporary.unlink(missing_ok=True)


def _rows(path: Path):
    """Stable oldest-first identities without rewriting legacy journal bytes.

    Older writers reused seq 2001 after trimming the journal. Retained duplicate
    rows receive increasing effective identities; their original number remains
    visible. Historical rows already trimmed by those writers are unrecoverable.
    New writers must never trim unread coordination history.
    """
    if not path.exists():
        return
    previous = 0
    # Decode inside the guarded JSON read so an interrupted UTF-8 append is
    # treated as unavailable history, without discarding its original bytes.
    with path.open('rb') as handle:
        for line in handle:
            try:
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError('invalid event record')
                stored = row.get('seq')
            except (ValueError, TypeError) as exc:
                raise OSError('Coordination history contains an invalid event.') from exc
            effective = max(previous + 1, stored if type(stored) is int and stored > 0 else 0)
            if effective != stored:
                row = dict(row, seq=effective, legacy_seq=stored)
            previous = effective
            yield row


def append_event(root: Path, *, actor: str, kind: str, summary: str, event_id: str | None = None, **fields) -> int:
    """Append one event; returns monotonic seq."""
    folder = _folder(root)
    path = folder / EVENTS_FILE
    handle = _lock(root)
    try:
        _inherit_legacy(folder)
        seq = 1
        duplicate = None
        for previous in _rows(path):
            seq = previous['seq'] + 1
            if event_id and previous.get('event_id') == event_id and previous.get('actor') == actor:
                duplicate = previous
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
        if event_id:
            row['event_id'] = event_id
        if duplicate:
            payload = {key:value for key, value in row.items() if key not in ('seq', 'at', 'ts')}
            if any(duplicate.get(key) != value for key, value in payload.items()):
                raise OSError('Coordination event identity already has different content.')
            return duplicate['seq']
        needs_separator = False
        if path.exists() and path.stat().st_size:
            with path.open('rb') as previous_bytes:
                previous_bytes.seek(-1, os.SEEK_END)
                needs_separator = previous_bytes.read(1) != b'\n'
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "a", encoding="utf-8") as out:
            if needs_separator:
                out.write('\n')
            out.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            out.flush()
            os.fsync(out.fileno())
        folder_fd = os.open(folder, os.O_RDONLY)
        try:
            os.fsync(folder_fd)
        finally:
            os.close(folder_fd)
        return seq
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def read_events(root: Path, *, since_seq: int = 0, limit: int = 80) -> list[dict]:
    from collections import deque
    rows = deque(maxlen=max(1, limit))
    for row in _rows(_read_path(root)):
        if row['seq'] > since_seq:
            rows.append(row)
    return list(rows)


def read_events_page(
    root: Path,
    *,
    since_seq: int = 0,
    page_size: int = 80,
) -> dict:
    """One oldest-first page after since_seq. Returns events, has_more, high_seq."""
    path = _read_path(root)
    limit = max(1, page_size)
    rows: list[dict] = []
    high_seq = since_seq
    has_more = False
    for row in _rows(path):
        seq = row['seq']
        if seq <= since_seq:
            continue
        if len(rows) >= limit:
            has_more = True
            break
        rows.append(row)
        high_seq = seq
    return {"events": rows, "has_more": has_more, "high_seq": high_seq}


def collect_events_since(
    root: Path,
    *,
    since_seq: int = 0,
    page_size: int = 40,
    max_pages: int = 6,
) -> dict:
    """Read events after since_seq across up to max_pages pages."""
    cursor = since_seq
    collected: list[dict] = []
    batch: dict = {"events": [], "has_more": False, "high_seq": since_seq}
    for _ in range(max(1, max_pages)):
        batch = read_events_page(root, since_seq=cursor, page_size=page_size)
        if not batch["events"]:
            break
        collected.extend(batch["events"])
        cursor = int(batch["high_seq"])
        if not batch["has_more"]:
            return {"events": collected, "truncated": False, "high_seq": cursor}
    truncated = bool(batch.get("has_more"))
    return {"events": collected, "truncated": truncated, "high_seq": cursor}


def read_events_since_paginated(
    root: Path,
    *,
    since_seq: int = 0,
    page_size: int = 80,
    max_pages: int = 8,
) -> list[dict]:
    """Read events after since_seq oldest-first, up to page_size * max_pages (single scan)."""
    cap = max(1, page_size) * max(1, max_pages)
    batch = read_events_page(root, since_seq=since_seq, page_size=cap)
    return batch["events"]


def latest_seq(root: Path) -> int:
    last = 0
    for row in _rows(_read_path(root)):
        last = row['seq']
    return last


def catchup_page(root: Path, *, since_seq: int, limit: int = 12) -> dict:
    """Pure read; the receipt binds exactly these events, not later arrivals."""
    if type(since_seq) is not int or since_seq < 0 or type(limit) is not int or not 1 <= limit <= 80:
        raise ValueError('Invalid catch-up cursor or page size.')
    page = read_events_page(root, since_seq=since_seq, page_size=limit)
    path = _read_path(root)
    if path.exists():
        with path.open('rb') as source:
            # A legacy writer may omit its final line separator. Import and
            # append add that separator without changing the first record.
            first = source.readline().rstrip(b'\r\n')
    else:
        first = b''
    journal_id = hashlib.sha256(str(root.resolve()).encode() + b'\0' + first).hexdigest()
    payload = dict(journal_id=journal_id, since_seq=since_seq, through_seq=page['high_seq'], events=page['events'])
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return dict(payload, receipt_sha256=digest, has_more=page['has_more'],
                history_gap=bool(page['events'] and page['events'][0]['seq'] > since_seq + 1),
                authority='Work records only; reading or acknowledging them authorizes no execution.')


def record_task_result(root: Path, row: dict, redact=lambda text:text) -> int:
    """Project the durable queue result, never a model's completion claim."""
    result = row.get('result') or ''
    digest = hashlib.sha256(result.encode()).hexdigest()
    acceptance = row.get('acceptance') or {}
    accepted = bool(row.get('status') == 'succeeded' and acceptance.get('accepted') is True
                    and row.get('result_sha256') == digest and acceptance.get('result_sha256') == digest)
    record = {key:row.get(key) for key in ('id', 'conversation_id', 'request_id', 'worker', 'status',
                                         'claimed_at', 'started_at', 'finished_at', 'result_path',
                                         'result_sha256', 'worktree', 'branch')}
    record.update(accepted_result=accepted, acceptance_method=acceptance.get('method'),
                  result_excerpt=result[:1500], error=row.get('error'),
                  artifact_verification='Use the saved result and acceptance records; this projection does not reinspect files.')
    record = json.loads(redact(json.dumps(record, ensure_ascii=False)))
    return append_event(root, actor='web-bob', kind='task-result', event_id='task-result:' + row['id'],
                        summary='Task ' + row['id'] + ': ' + row['status'] +
                                ('; accepted result recorded.' if accepted else '; inspect the recorded outcome and verification limits.'),
                        outcome=record)
