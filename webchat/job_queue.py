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
CONFIRM_WITH_PROPOSAL = re.compile(
    r"^yes[,.]?\s*(?:start|queue|run)\s+(?:the\s+)?job(?:\s+proposal\s+"
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}))?\s*$",
    re.I,
)
COUNCIL = re.compile(r"^(?:run|start)\s+council(?:\s+on)?[:\s]+(.+)$", re.I | re.S)
COUNCIL_CONFIRM = re.compile(r"^yes[,.]?\s*run\s+council\s*$", re.I)
COUNCIL_CONFIRM_WITH_PROPOSAL = re.compile(
    r"^yes[,.]?\s*run\s+council(?:\s+proposal\s+"
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}))?\s*$",
    re.I,
)
COUNCIL_CANCEL = re.compile(r"^(?:never mind|cancel|dismiss)(?:\s+council)?\s*$", re.I)
DO_MORE = re.compile(
    r"^(?:i )?need you to do more\.?$|^(?:please )?(?:you )?(?:do it|handle it)\.?$|"
    r"^(?:don't|do not) tell me to (?:do it|run it|queue it) myself\.?$|"
    r"^(?:queue|launch|run) (?:that|this|it)(?: repair| brief| task)?\.?$|"
    r"^start (?:a )?(?:conductor )?job for me\.?$",
    re.I,
)
READY_ROUND = re.compile(r"start\s+(?:a\s+)?web\s+bob\s+ready\s+round", re.I)
DEFAULT_DO_MORE_GOAL = (
    "Web Bob conductor follow-up: review READY queue, assign next draft lane, report SHA (draft only)"
)
DEFAULT_READY_ROUND_GOAL = (
    "Web Bob READY phone round: fix lowest scores, failover both ways, council critique, "
    "tests + RESULT on draft branch (no merge, no Grok)"
)


def parse_start(text: str) -> str | None:
    match = START.match(text.strip())
    return match.group(1).strip()[:4000] if match else None


def parse_ready_round(text: str) -> str | None:
    stripped = (text or "").strip()
    if not stripped or len(stripped) > 400:
        return None
    if READY_ROUND.search(stripped):
        return DEFAULT_READY_ROUND_GOAL
    return None


def parse_do_more(text: str) -> str | None:
    stripped = (text or "").strip()
    if not stripped or len(stripped) > 400:
        return None
    if DO_MORE.match(stripped):
        return DEFAULT_DO_MORE_GOAL
    if parse_start(stripped) or parse_council(stripped) or parse_ready_round(stripped):
        return None
    return None


def parse_confirm(text: str) -> bool:
    return parse_job_confirm(text)[0]


def parse_job_confirm(text: str) -> tuple[bool, str | None]:
    stripped = text.strip()
    match = CONFIRM_WITH_PROPOSAL.match(stripped)
    if match:
        return True, match.group(1)
    if CONFIRM.match(stripped):
        return True, None
    return False, None


def parse_council(text: str) -> str | None:
    match = COUNCIL.match(text.strip())
    return match.group(1).strip()[:2000] if match else None


def parse_council_confirm(text: str) -> bool:
    return parse_council_confirm_proposal(text)[0]


def parse_council_confirm_proposal(text: str) -> tuple[bool, str | None]:
    stripped = text.strip()
    match = COUNCIL_CONFIRM_WITH_PROPOSAL.match(stripped)
    if match:
        return True, match.group(1)
    if COUNCIL_CONFIRM.match(stripped):
        return True, None
    return False, None


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


def count_ready_queue(root: Path) -> int:
    """Count READY rows in next-prompts/INDEX.md (scheduler backlog)."""
    return len(list_ready_queue_jobs(root, limit=999))


def _safe_prompt_path(prompts_dir: Path, filename: str) -> Path | None:
    name = (filename or "").strip()
    if not name or "/" in name or "\\" in name or name.startswith("."):
        return None
    try:
        resolved = (prompts_dir / name).resolve()
        if prompts_dir.resolve() not in resolved.parents and resolved != prompts_dir.resolve():
            return None
    except OSError:
        return None
    return resolved if resolved.is_file() else None


def _goal_from_prompt(path: Path) -> str:
    if not path.is_file():
        return ""
    text = path.read_text(errors="replace")
    match = re.search(r"##\s*Task\s*\n+(.+?)(?:\n##|\Z)", text, re.I | re.S)
    if match:
        goal = " ".join(match.group(1).strip().split())
        return goal[:200]
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped[:200]
    return ""


def list_ready_queue_jobs(root: Path, limit: int = 8) -> list[dict]:
    """READY rows in next-prompts/INDEX.md with plain-English goal from the prompt body."""
    index = root / "next-prompts" / "INDEX.md"
    if not index.is_file():
        return []
    prompts = root / "next-prompts"
    rows: list[dict] = []
    for line in index.read_text(errors="replace").splitlines():
        if not re.search(r"\|\s*READY\s*\|", line, re.I):
            continue
        file_match = re.search(r"`([^`]+\.md)`", line)
        if not file_match:
            continue
        filename = file_match.group(1)
        safe = _safe_prompt_path(prompts, filename)
        goal = _goal_from_prompt(safe) if safe else ""
        if not goal:
            goal = "Draft job waiting for the scheduler"
        rows.append({"id": filename, "goal": goal, "status": "READY", "position": len(rows) + 1})
        if len(rows) >= limit:
            break
    return rows


def queue_position_for_file(root: Path, filename: str) -> int | None:
    """1-based position among READY rows in INDEX.md (scheduler order)."""
    name = (filename or "").strip()
    if not name:
        return None
    for row in list_ready_queue_jobs(root, limit=999):
        if row.get("id") == name:
            return int(row.get("position") or 0) or None
    return None


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
    ready = count_ready_queue(root)
    position = queue_position_for_file(root, filename) or ready
    return {
        "ok": True,
        "file": filename,
        "path": str(path.relative_to(root)),
        "screen_hint": screens.strip()[:500] or "none",
        "queue_ready_count": ready,
        "queue_position": position,
    }
