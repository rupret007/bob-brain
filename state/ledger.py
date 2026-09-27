#!/usr/bin/env python3
"""Single source of truth: conductor/state/STATE.json → NOW.md + BOB-CATCHUP.md."""
from __future__ import annotations

import fcntl
import json
import os
import re
import secrets
import time
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

CT = ZoneInfo("America/Chicago")
STATE_DIR = Path("conductor/state")
STATE_FILE = "STATE.json"
NOW_FILE = "NOW.md"
INBOX_FILE = "INBOX.md"
CATCHUP_FILE = "BOB-CATCHUP.md"
LAST_SEEN = Path("conductor/handback/.bob-last-seen")
MAX_CATCHUP_LINES = 25
STALL_SECONDS = 600

_STATUS_RE = re.compile(
    r"^(?:status|what(?:'s| is) (?:the )?status|anything (?:i need to do|running)|"
    r"what(?:'s| is) running\??|quick status)\s*[.!?]*$",
    re.I,
)
_HANDOFF_CONTEXT_RE = re.compile(
    r"\b(?:bob[- ]?state|handback|handoff|hand[\s-]?back|from bob-state|handback drill|"
    r"quote the running|open (?:asks|items)|waiting on jeff|takeover|pick up where)\b",
    re.I,
)
_INBOX_RE = re.compile(r"^tell the builder:\s*(.+)$", re.I)


def _folder(root: Path) -> Path:
    path = root / STATE_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def _atomic_write(path: Path, value: str) -> None:
    temporary = path.with_name("." + path.name + "." + secrets.token_hex(6))
    try:
        with open(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _now_ct() -> str:
    return datetime.now(CT).strftime("%Y-%m-%d %H:%M:%S CT")


_REQUIRED_KEYS = (
    "version",
    "updated_at",
    "active_round",
    "last_sha",
    "owner",
    "jobs",
    "open_asks",
    "decisions",
    "now_history",
    "inbox",
    "webchat_turns",
)


def default_state() -> dict:
    return {
        "version": 1,
        "revision": 0,
        "updated_at": _now_ct(),
        "active_round": None,
        "last_sha": None,
        "owner": None,
        "jobs": [],
        "open_asks": [],
        "decisions": [],
        "now_history": [],
        "inbox": [],
        "webchat_turns": [],
    }


def _validate_state(data: dict) -> bool:
    return isinstance(data, dict) and all(key in data for key in _REQUIRED_KEYS)


def _log_corrupt(root: Path, reason: str) -> None:
    try:
        path = _folder(root) / ".STATE.corrupt.log"
        with path.open("a") as handle:
            handle.write(f"{_now_ct()} {reason}\n")
    except OSError:
        pass


def _state_lock(root: Path):
    lock_path = _folder(root) / ".STATE.lock"
    handle = lock_path.open("a")
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
    return handle


def load_state(root: Path) -> dict:
    path = _folder(root) / STATE_FILE
    if not path.exists():
        return default_state()
    try:
        data = json.loads(path.read_text(errors="replace"))
        if _validate_state(data):
            if "revision" not in data:
                data["revision"] = 0
            return data
        _log_corrupt(root, "schema mismatch")
    except (OSError, json.JSONDecodeError) as err:
        _log_corrupt(root, f"parse error: {err}")
    return default_state()


def save_state(root: Path, state: dict) -> None:
    state["updated_at"] = _now_ct()
    state["revision"] = int(state.get("revision") or 0) + 1
    _atomic_write(_folder(root) / STATE_FILE, json.dumps(state, ensure_ascii=False, indent=2) + "\n")


def _mutate(root: Path, fn, *, inbox: bool = False, now_line: str | None = None, catchup: bool = True):
    handle = _state_lock(root)
    try:
        state = load_state(root)
        result = fn(state)
        save_state(root, state)
        if inbox:
            _rewrite_inbox_md(root, state)
        if now_line is not None:
            _atomic_write(_folder(root) / NOW_FILE, f"{now_line}\n")
        if catchup:
            _write_catchup_body(root, state)
        return result
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def _rewrite_inbox_md(root: Path, state: dict) -> None:
    inbox_path = _folder(root) / INBOX_FILE
    lines = [f"# Builder inbox · updated {_now_ct()}", ""]
    for row in state.get("inbox") or []:
        flag = "DONE" if row.get("status") == "done" else "OPEN"
        lines.append(f"- [{flag}] ({row.get('source', '?')}) {row.get('body', '')[:500]}")
    _atomic_write(inbox_path, "\n".join(lines) + "\n")


def parse_inbox_message(text: str) -> str | None:
    if not text:
        return None
    match = _INBOX_RE.match(text.strip())
    return match.group(1).strip() if match else None


def append_inbox(root: Path, body: str, *, source: str = "web-bob", request_id: str | None = None) -> dict:
    item = {
        "id": str(uuid.uuid4()),
        "status": "new",
        "body": body.strip()[:4000],
        "source": source,
        "request_id": request_id,
        "at": _now_ct(),
    }

    def _apply(state: dict) -> dict:
        state.setdefault("inbox", []).append(item)
        state["inbox"] = state["inbox"][-80:]
        return item

    return _mutate(root, _apply, inbox=True, catchup=True)


def record_webchat_turn(root: Path, *, ask: str, provider: str | None, request_id: str | None = None) -> None:
    turn = {"at": _now_ct(), "ask": ask.strip()[:500], "provider": provider or "none", "request_id": request_id}

    def _apply(state: dict) -> None:
        state.setdefault("webchat_turns", []).append(turn)
        state["webchat_turns"] = state["webchat_turns"][-40:]

    _mutate(root, _apply, catchup=True)


def record_decision(root: Path, text: str, *, kind: str = "jeff") -> None:
    entry = {"at": _now_ct(), "kind": kind, "text": text.strip()[:800]}

    def _apply(state: dict) -> None:
        state.setdefault("decisions", []).append(entry)
        state["decisions"] = state["decisions"][-50:]

    _mutate(root, _apply, catchup=True)


def add_open_ask(root: Path, body: str, *, status: str = "new", finished_sha: str | None = None) -> str:
    ask_id = str(uuid.uuid4())[:8]
    row = {"id": ask_id, "body": body.strip()[:500], "status": status, "finished_sha": finished_sha, "at": _now_ct()}

    def _apply(state: dict) -> str:
        state.setdefault("open_asks", []).append(row)
        state["open_asks"] = state["open_asks"][-60:]
        return ask_id

    return _mutate(root, _apply, catchup=True)


def write_now(root: Path, line: str, *, step: str | None = None, elapsed_seconds: int | None = None,
              sha: str | None = None) -> None:
    plain = line.strip()[:500]
    if elapsed_seconds is not None:
        plain += f" · {elapsed_seconds // 60}m elapsed"
    if sha:
        plain += f" · {sha[:12]}"
    if step:
        plain += f" · step {step}"
    entry = {"at": _now_ct(), "line": plain}

    def _apply(st: dict) -> None:
        st.setdefault("now_history", []).append(entry)
        st["now_history"] = st["now_history"][-40:]

    _mutate(root, _apply, now_line=plain, catchup=True)


def _commits_since(root: Path, since: float) -> list[str]:
    conductor = root / "conductor"
    if not (conductor / ".git").exists():
        return []
    import subprocess

    try:
        out = subprocess.check_output(
            ["git", "-C", str(conductor), "log", f"--since={int(since)}", "--format=%h %s"],
            text=True,
            timeout=8,
        )
        return [line.strip() for line in out.splitlines() if line.strip()][:12]
    except (subprocess.SubprocessError, OSError):
        return []


def _write_catchup_body(root: Path, state: dict) -> None:
    seen = root / LAST_SEEN
    since = seen.stat().st_mtime if seen.exists() else 0.0
    lines: list[str] = [f"# Bob catch-up · {_now_ct()} · since last Bob read", ""]
    blockers: list[str] = []
    progress: list[str] = []
    done: list[str] = []
    for ask in state.get("open_asks") or []:
        if ask.get("status") in ("new", "in_progress"):
            blockers.append(f"Ask {ask.get('id')}: {ask.get('body', '')[:120]} ({ask.get('status')})")
        elif ask.get("status") == "done":
            done.append(f"Finished ask {ask.get('id')}: {ask.get('body', '')[:80]} → {ask.get('finished_sha') or 'sha?'}")
    for item in state.get("inbox") or []:
        if item.get("status") != "done":
            blockers.append(f"Inbox ({item.get('source')}): {item.get('body', '')[:120]}")
    for job in state.get("jobs") or []:
        if job.get("stall") == "stalled":
            blockers.append(f"Stalled job {job.get('job_id', '?')[:24]}: {job.get('plain_now', 'no heartbeat')}")
        elif job.get("live"):
            progress.append(f"Running {job.get('engine', 'job')} · {job.get('plain_now', 'active')[:100]}")
    now_line = (state.get("now_history") or [{}])[-1].get("line") if state.get("now_history") else None
    if now_line:
        progress.insert(0, f"Now: {now_line}")
    for commit in _commits_since(root, since):
        done.append(f"Commit {commit}")
    for turn in reversed(state.get("webchat_turns") or []):
        done.append(f"Web Bob ({turn.get('provider')}): {turn.get('ask', '')[:100]}")
    for path in sorted((root / "conductor/reviews").glob("WEBCHAT-READY-R*-RESULT.md"),
                       key=lambda p: p.stat().st_mtime, reverse=True)[:2]:
        if path.stat().st_mtime >= since:
            done.append(f"Round result {path.name}")
    ordered = blockers + progress + done
    seen_ids: set[str] = set()
    unique: list[str] = []
    for row in ordered:
        key = row[:80]
        if key in seen_ids:
            continue
        seen_ids.add(key)
        unique.append(row)
    if not unique:
        unique.append("No changes since Bob last read — Web Bob and ledger are in sync.")
    for row in unique[:MAX_CATCHUP_LINES]:
        lines.append(f"- {row}")
    _atomic_write(_folder(root) / CATCHUP_FILE, "\n".join(lines) + "\n")


def write_catchup(root: Path) -> None:
    """Refresh BOB-CATCHUP.md from current STATE.json under lock."""
    _mutate(root, lambda _state: None, catchup=True)


def sync_from_live_ops(root: Path, live_ops: dict, *, head_sha: str | None = None,
                       webchat_round: int | None = None) -> dict:
    now_plain: str | None = None
    elapsed_for_now: int | None = None
    sha_for_now: str | None = None

    def _apply(state: dict) -> None:
        nonlocal now_plain, elapsed_for_now, sha_for_now
        if head_sha:
            state["last_sha"] = head_sha
        round_no = webchat_round or live_ops.get("webchat_round")
        if round_no:
            state["active_round"] = {"number": round_no, "label": "webchat-ready"}
        jobs_out = []
        for row in live_ops.get("running_jobs") or []:
            stalled = row.get("stall_state") == "stalled"
            jobs_out.append({
                "job_id": row.get("job_id") or row.get("engine"),
                "engine": row.get("engine"),
                "plain_now": row.get("plain_now"),
                "live": bool(row.get("live_screen")),
                "stall": "stalled" if stalled else "running",
                "round": row.get("round"),
                "last_commit": (row.get("last_commit") or {}).get("sha"),
            })
        state["jobs"] = jobs_out[:12]
        lead = next((j for j in jobs_out if j.get("live")), jobs_out[0] if jobs_out else None)
        if lead and lead.get("live"):
            elapsed_for_now = None
            for row in live_ops.get("running_jobs") or []:
                if lead.get("job_id") and row.get("job_id") == lead.get("job_id"):
                    elapsed_for_now = row.get("elapsed_seconds")
                    break
            if elapsed_for_now is None:
                for row in live_ops.get("running_jobs") or []:
                    if row.get("engine") == lead.get("engine"):
                        elapsed_for_now = row.get("elapsed_seconds")
                        break
            sha_for_now = lead.get("last_commit") or head_sha
            plain = lead.get("plain_now") or f"{lead.get('engine', 'job')} is running"
            if elapsed_for_now is not None:
                plain += f" · {int(elapsed_for_now) // 60}m elapsed"
            if sha_for_now:
                plain += f" · {str(sha_for_now)[:12]}"
            now_plain = plain
            entry = {"at": _now_ct(), "line": plain[:500]}
            state.setdefault("now_history", []).append(entry)
            state["now_history"] = state["now_history"][-40:]
        elif head_sha:
            now_plain = f"Idle on mini · last commit {head_sha[:12]}"
            entry = {"at": _now_ct(), "line": now_plain}
            state.setdefault("now_history", []).append(entry)
            state["now_history"] = state["now_history"][-40:]

    _mutate(
        root,
        _apply,
        now_line=f"{now_plain}\n" if now_plain else None,
        catchup=True,
    )
    return load_state(root)


def read_now_line(root: Path) -> str | None:
    path = _folder(root) / NOW_FILE
    if not path.exists():
        return None
    for line in path.read_text(errors="replace").splitlines():
        if line.strip():
            return line.strip()
    return None


def try_status_reply(root: Path, text: str) -> str | None:
    """Cheap-first status from ledger (no model). Skipped for handback/takeover phrasing."""
    if _HANDOFF_CONTEXT_RE.search(text or ""):
        return None
    stripped = (text or "").strip()
    if not stripped or len(stripped) > 120:
        return None
    if not _STATUS_RE.match(stripped) and "status" not in stripped.lower():
        return None
    state = load_state(root)
    parts: list[str] = []
    now = read_now_line(root)
    if now:
        parts.append(now)
    jobs = [j for j in state.get("jobs") or [] if j.get("live")]
    if jobs:
        for job in jobs[:3]:
            parts.append(f"{job.get('engine', 'job')}: {job.get('plain_now', 'running')[:120]}")
    elif state.get("last_sha"):
        parts.append(f"Draft HEAD {state['last_sha'][:12]}.")
    open_inbox = [i for i in state.get("inbox") or [] if i.get("status") != "done"]
    if open_inbox:
        parts.append(f"{len(open_inbox)} inbox item(s) for the builder.")
    open_asks = [a for a in state.get("open_asks") or [] if a.get("status") in ("new", "in_progress")]
    if open_asks:
        parts.append(f"Open asks: {open_asks[0].get('body', '')[:100]}")
    if not parts:
        catchup = _folder(root) / CATCHUP_FILE
        if catchup.exists():
            for line in catchup.read_text(errors="replace").splitlines():
                if line.startswith("- "):
                    parts.append(line[2:][:200])
                    break
    if not parts:
        return None
    return " ".join(parts)[:1200]


def public_slice(root: Path) -> dict:
    state = load_state(root)
    return {
        "now_line": read_now_line(root),
        "open_asks": [a for a in state.get("open_asks") or [] if a.get("status") in ("new", "in_progress")][:8],
        "inbox_open": sum(1 for i in state.get("inbox") or [] if i.get("status") != "done"),
        "active_round": state.get("active_round"),
        "last_sha": state.get("last_sha"),
        "updated_at": state.get("updated_at"),
    }
