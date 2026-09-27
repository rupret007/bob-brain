#!/usr/bin/env python3
"""Two-way Bob ↔ Web Bob ledger under conductor/handback/."""
from __future__ import annotations

import os
import re
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

CT = ZoneInfo("America/Chicago")
FOLDER = Path("conductor/handback")
STATE = "BOB-STATE.md"
LOG = "HANDBACK-LOG.md"
SUMMARY = "HANDBACK-SUMMARY.md"
LAST_SEEN = ".bob-last-seen"


def _folder(root: Path) -> Path:
    path = root / FOLDER
    path.mkdir(parents=True, exist_ok=True)
    return path


def _now_ct() -> str:
    return datetime.now(CT).strftime("%Y-%m-%d %H:%M:%S CT")


def read_slice(root: Path, name: str, limit: int = 12000, tail: bool = False) -> dict:
    path = _folder(root) / name
    try:
        text = path.read_text(errors="replace")
        stamp = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(path.stat().st_mtime))
        clipped = len(text) > limit
        body = text[-limit:] if tail else text[:limit]
        return {"path": str(path.relative_to(root)), "modified": stamp, "truncated": clipped, "text": body, "available": True}
    except OSError:
        return {"path": name, "available": False}


def refresh_summary(root: Path) -> None:
    folder = _folder(root)
    seen = folder / LAST_SEEN
    cutoff = seen.stat().st_mtime if seen.exists() else 0.0
    log_path = folder / LOG
    entries = []
    if log_path.exists():
        for block in re.split(r"\n(?=## )", log_path.read_text(errors="replace")):
            if not block.strip():
                continue
            m = re.search(r"^## (\d{4}-\d{2}-\d{2} .+?)\n", block)
            if not m:
                continue
            try:
                when = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S CT").replace(tzinfo=CT).timestamp()
            except ValueError:
                when = log_path.stat().st_mtime
            if when >= cutoff:
                entries.append(block.strip())
    state = read_slice(root, STATE, 4000)
    lines = [
        "# HANDBACK-SUMMARY",
        "",
        f"Updated {_now_ct()} · digest since Bob last saw handback ({seen.name if seen.exists() else 'never'})",
        "",
        "## Bob state (snapshot)",
        state.get("text", "(unavailable)") if state.get("available") else "(BOB-STATE.md missing)",
        "",
        "## Web Bob turns since last seen",
    ]
    if entries:
        lines.extend(entries)
    else:
        lines.append("_No Web Bob turns logged since last Bob read._")
    lines += ["", "## Grouped (manual digest)", "- **Done:** see log entries marked done", "- **Running:** see BOB-STATE", "- **Waiting on Jeff:** confirmations in log", "- **Risks:** drafts only; no merge/send without yes"]
    (folder / SUMMARY).write_text("\n".join(lines) + "\n")


def append_turn(root: Path, *, ask: str, provider: str | None, jobs: list[str], files: list[str], commits: list[str],
                confirmations: list[str], refusals: list[str], open_items: list[str]) -> None:
    folder = _folder(root)
    log_path = folder / LOG
    block = [
        f"## {_now_ct()}",
        f"- **Ask:** {ask.strip()[:2000]}",
        f"- **Provider:** {provider or 'none'}",
    ]
    if jobs:
        block.append("- **Jobs:** " + "; ".join(jobs[:20]))
    if files:
        block.append("- **Files:** " + "; ".join(files[:30]))
    if commits:
        block.append("- **Commits/SHAs:** " + "; ".join(commits[:20]))
    if confirmations:
        block.append("- **Jeff confirmed:** " + "; ".join(confirmations[:10]))
    if refusals:
        block.append("- **Refused:** " + "; ".join(refusals[:10]))
    if open_items:
        block.append("- **Open:** " + "; ".join(open_items[:15]))
    block.append("")
    with log_path.open("a") as handle:
        handle.write("\n".join(block))
        handle.flush()
        os.fsync(handle.fileno())
    refresh_summary(root)


def public_digest(root: Path, redact) -> dict:
    refresh_summary(root)
    state = read_slice(root, STATE, 2500)
    summary = read_slice(root, SUMMARY, 3500, tail=True)
    if state.get("available"):
        state["text"] = redact(state["text"])
    if summary.get("available"):
        summary["text"] = redact(summary["text"])
    return {"bob_state": state, "summary": summary, "read_at": time.time()}
