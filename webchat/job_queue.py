#!/usr/bin/env python3
"""Draft-only Web Bob job requests into next-prompts (scheduler picks up READY rows)."""
from __future__ import annotations

import re
import fcntl
import secrets
import shlex
import subprocess
import time
from pathlib import Path
from failover import atomic_text

START = re.compile(r"^(?:start|queue|run) (?:a )?job[:\s]+(.+)$", re.I | re.S)
CONFIRM = re.compile(r"^yes[,.]?\s*(?:start|queue|run)\s+(?:the\s+)?job\s*$", re.I)
COUNCIL = re.compile(r"^(?:run|start)\s+council(?:\s+on)?[:\s]+(.+)$", re.I | re.S)
COUNCIL_CONFIRM = re.compile(r"^yes[,.]?\s*run\s+council\s*$", re.I)
COUNCIL_CANCEL = re.compile(r"^(?:never mind|cancel|dismiss)(?:\s+council)?\s*$", re.I)


def parse_start(text: str) -> str | None:
    match = START.match(text.strip())
    return match.group(1).strip()[:4000] if match else None


def parse_confirm(text: str) -> bool:
    return bool(CONFIRM.match(text.strip()))


def parse_council(text: str) -> str | None:
    match = COUNCIL.match(text.strip())
    return match.group(1).strip()[:2000] if match else None


def parse_council_confirm(text: str) -> bool:
    return bool(COUNCIL_CONFIRM.match(text.strip()))


def parse_council_cancel(text: str) -> bool:
    return bool(COUNCIL_CANCEL.match(text.strip()))


def sanitize_council_question(question: str) -> str:
    """Strip shell metacharacters; council question is data, not a script."""
    cleaned = re.sub(r"[`$\\;|&<>(){}[\]!#*?~]", " ", question or "")
    return " ".join(cleaned.split())[:1800]


def council_job_description(question: str) -> str:
    safe = sanitize_council_question(question)
    quoted = shlex.quote(safe)
    return (
        "Run Web Bob council on the mini (Gemini + MiniMax + Claude; no Grok). "
        "Draft branch only; never merge.\n\n"
        f"Question: {safe}\n\n"
        "Command (no Grok; question passed as a single quoted argument):\n"
        "set -a; . conductor/keys.env; set +a; "
        f"python3 conductor/services/council.py --context conductor/WEBCHAT-READY.md "
        f"--out conductor/reviews/webchat-phone-council-$(date +%Y%m%d-%H%M%S) {quoted}"
    )


def running_screens(root: Path) -> str:
    try:
        result = subprocess.run(
            ["/usr/bin/screen", "-ls"], cwd=root, capture_output=True, text=True, timeout=5,
        )
        return result.stdout if result.returncode in (0, 1) else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def duplicate_task(screens: str, description: str) -> bool:
    needle = description.lower()[:80]
    return needle and needle in screens.lower()


def queue_draft(root: Path, description: str) -> dict:
    maintenance = root / "conductor/MAINTENANCE"
    if maintenance.exists():
        return {"ok": False, "error": "Scheduling is paused (MAINTENANCE). Jobs were not queued."}
    screens = running_screens(root)
    if duplicate_task(screens, description):
        return {"ok": False, "error": "A screen session may already be running this task. Check Jobs before queueing again."}
    locks = root / "conductor/locks"
    locks.mkdir(parents=True, exist_ok=True)
    with (locks / "queue.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"ok": False, "error": "The scheduler is updating the queue. Your job was not queued; try a new request shortly."}
        return _write_queue(root, description, screens)


def _write_queue(root, description, screens):
    prompts = root / "next-prompts"
    prompts.mkdir(parents=True, exist_ok=True)
    inbox = prompts / "_inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    token = secrets.token_hex(4)
    stamp = time.strftime("%Y%m%d-%H%M")
    filename = f"webchat-{stamp}-{token}.md"
    body = (
        f"# Web Bob job request ({stamp})\n\n"
        f"**Source:** Web Bob chat (draft only; Jeff must still approve any outward action.)\n\n"
        f"## Task\n\n{description.strip()}\n\n"
        f"## Rules\n\nDrafts only. No merge, undraft, or force-push. One WebJam coder at a time.\n"
    )
    path = prompts / filename
    atomic_text(path, body)
    atomic_text(inbox / filename, body)
    index = prompts / "INDEX.md"
    row = f"| 99 | `{filename}` | WebBob | non-coding | READY | Web Bob queued {stamp} |\n"
    if index.exists():
        text = index.read_text()
        if filename not in text:
            atomic_text(index, text.rstrip() + "\n" + row)
    else:
        atomic_text(index, "# next-prompts queue\n\n| Pri | File | Project | Kind | Status | Notes |\n| --- | --- | --- | --- | --- | --- |\n" + row)
    return {"ok": True, "file": filename, "path": str(path.relative_to(root)), "screen_hint": screens.strip()[:500] or "none"}
