"""Bob-the-Bot parity: durable memory, web research, and on-demand screenshots."""
from __future__ import annotations

import json
import re
import secrets
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REMEMBER = re.compile(r"^remember\s+that\s+(.+?)\s*\.?\s*$", re.I | re.S)
MEMORY_CONFIRM = re.compile(r"^yes[,.]?\s*save\s+memory\s*$", re.I)
MEMORY_CONFIRM_PROPOSAL = re.compile(
    r"^yes[,.]?\s*save\s+memory(?:\s+proposal\s+"
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}))?\s*$",
    re.I,
)
MEMORY_CANCEL = re.compile(r"^(?:never mind|cancel|dismiss)(?:\s+memory)?\s*$", re.I)
SCREENSHOT = re.compile(
    r"^(?:please\s+)?take\s+(?:a\s+)?screenshot(?:\s+of\s+(?:the\s+)?(.+?))?\s*\.?\s*$",
    re.I,
)
WEB_SEARCH = re.compile(
    r"\b(?:search\s+(?:the\s+)?web|look\s+up|google)\b|"
    r"(?:who\s+won|score\s+of).{0,120}\?",
    re.I,
)

CAPTURE_MAX_COUNT = 100
CAPTURE_MAX_AGE_DAYS = 7
PROFILE_MAX_BYTES = 512 * 1024


def profile_path(root: Path) -> Path:
    # User data must never dirty the bob-brain checkout (which may be on main).
    return root / "conductor/webchat/memory/profile.md"


def parse_remember(text: str) -> str | None:
    match = REMEMBER.match((text or "").strip())
    if not match:
        return None
    fact = match.group(1).strip()
    return fact[:2000] if fact else None


def parse_memory_confirm(text: str) -> tuple[bool, str | None]:
    stripped = (text or "").strip()
    match = MEMORY_CONFIRM_PROPOSAL.match(stripped)
    if match:
        return True, match.group(1)
    if MEMORY_CONFIRM.match(stripped):
        return True, None
    return False, None


def memory_confirm_prompt(fact: str) -> str:
    return f"I can save this to durable memory:\n\n**{fact}**\n\nReply `yes, save memory` to confirm."


def _trim_profile_lines(lines: list[str], max_bytes: int = PROFILE_MAX_BYTES) -> list[str]:
    sizes = [len(entry.encode("utf-8")) for entry in lines]
    total = sum(sizes)
    start = 0
    while start < len(lines) and total > max_bytes:
        total -= sizes[start]
        start += 1
    return lines[start:]


def _prune_captures(folder: Path, max_count: int = CAPTURE_MAX_COUNT, max_age_days: int = CAPTURE_MAX_AGE_DAYS) -> None:
    try:
        now = time.time()
        max_age_seconds = max_age_days * 24 * 60 * 60
        captures = [path for path in folder.glob("*.png") if path.is_file()]
        captures.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        to_delete = set(captures[max_count:])
        for path in captures:
            if now - path.stat().st_mtime > max_age_seconds:
                to_delete.add(path)
        for path in to_delete:
            path.unlink()
    except OSError:
        pass


def append_profile_memory(root: Path, fact: str, when: datetime | None = None) -> str:
    when = when or datetime.now(timezone.utc)
    stamp = when.astimezone().strftime("%Y-%m-%d")
    line = f"[{stamp}] {fact.strip()}\n"
    from memory_store import append_memory
    try:
        append_memory(root, line)
    except OSError as exc:
        raise OSError(f"Could not access private memory or lock {profile_path(root).parent / 'profile.lock'}: {exc}") from exc
    return line.strip()


def parse_screenshot(text: str) -> str | None:
    match = SCREENSHOT.match((text or "").strip())
    if not match:
        return None
    target = (match.group(1) or "").strip()
    return target[:120] if target else ""


def _escape_applescript_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _macos_window_id(app_name: str) -> int | None:
    if sys.platform != "darwin":
        raise RuntimeError("The screenshot feature is only available on macOS.")
    escaped_name = _escape_applescript_string(app_name)
    script = (
        'tell application "System Events" to id of first window of '
        f'(first process whose name contains "{escaped_name}")'
    )
    try:
        completed = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=12,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    try:
        return int(completed.stdout.strip())
    except ValueError:
        return None


def capture_screenshot(root: Path, target: str | None = None) -> tuple[str, Path]:
    if sys.platform != "darwin":
        raise RuntimeError("The screenshot feature is only available on macOS.")
    folder = root / "conductor/webchat/captures"
    folder.mkdir(parents=True, exist_ok=True)
    _prune_captures(folder)
    capture_id = secrets.token_hex(8)
    path = folder / f"{capture_id}.png"
    command = ["screencapture", "-x"]
    if target:
        window_id = _macos_window_id(target)
        if window_id is None:
            raise RuntimeError(f"I could not find an open window matching “{target}”.")
        command.extend(["-l", str(window_id)])
    command.append(str(path))
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"Screenshot capture failed ({exc}).") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or "").strip()
        message = f"Screenshot capture failed (exit {completed.returncode})"
        if detail:
            message = f"{message}: {detail}"
        raise RuntimeError(message)
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError("Screenshot capture produced no image.")
    return capture_id, path


def capture_reply(capture_id: str, target: str | None) -> str:
    label = target or "your screen"
    return (
        f"Captured **{label}**.\n\n"
        f"![screenshot](/api/captures/{capture_id})"
    )


def needs_web_search(text: str) -> bool:
    stripped = (text or "").strip()
    if not stripped or len(stripped) > 600:
        return False
    return bool(WEB_SEARCH.search(stripped))


class NoSearchRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError("Web lookup redirect refused; no result was verified.")


def web_search(query: str, opener=None) -> dict:
    # Shared with direct local lookups/routines: one bounded GET, without
    # environment proxies, cookies, credentials or redirect followups.
    if opener is None:
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), NoSearchRedirect()).open
    query = re.sub(r"^(?:please\s+)?(?:search\s+(?:the\s+)?web|look\s+up|google)\s+(?:for\s+)?", "", query.strip(), flags=re.I)
    url = "https://api.duckduckgo.com/?" + urllib.parse.urlencode(
        {"q": query, "format": "json", "no_redirect": 1, "no_html": 1, "skip_disambig": 1}
    )
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "WebBob/1.0 (bob-gaps web research)"},
    )
    with opener(request, timeout=10) as response:
        raw = response.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise ValueError("Search response exceeded the size limit")
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Search response was not an object")
    answer = (payload.get("AbstractText") or "").strip()
    source = (payload.get("AbstractURL") or "").strip()
    heading = (payload.get("Heading") or "").strip()
    if not answer and payload.get("RelatedTopics"):
        for topic in payload["RelatedTopics"]:
            if isinstance(topic, dict) and topic.get("Text"):
                answer = topic["Text"].strip()
                source = (topic.get("FirstURL") or source).strip()
                break
    if not answer:
        answer = "I searched the web but did not get a clear instant answer. Try a more specific query."
    if urllib.parse.urlsplit(source).scheme not in ("http", "https"):
        source = ""
    return {"answer": answer[:16000], "source": source[:2000], "heading": heading[:500]}


def format_web_search_reply(result: dict) -> str:
    lines = [result.get("answer", "")]
    if result.get("heading"):
        lines[0] = f"**{result['heading']}** — {lines[0]}"
    if result.get("source"):
        lines.append(f"Source: [{result['source']}]({result['source']})")
    return "\n\n".join(lines)


def resolve_capture_path(root: Path, capture_id: str) -> Path | None:
    if not re.fullmatch(r"[0-9a-f]{16}", capture_id or ""):
        return None
    path = root / "conductor/webchat/captures" / f"{capture_id}.png"
    return path if path.is_file() else None


DISPATCH_STATUS_QUESTION = re.compile(
    r"^(?:please\s+)?(?:what(?:['’]s| is) the status of|where are we on)\b.+$",
    re.I,
)
_DISPATCH_STATUS_GENERIC = re.compile(
    r"\b(?:workers?|models?|llms?|queue|system|resources?|services?|disk|storage)\b",
    re.I,
)
_ACCEPTED_STOPWORDS = frozenset(
    {"with", "from", "that", "this", "step", "task", "into", "after", "accepted"}
)
_STALE_SECONDS = 180


def dispatch_status_question(text: str) -> bool:
    stripped = (text or "").strip()
    if not stripped or len(stripped) > 400:
        return False
    if _DISPATCH_STATUS_GENERIC.search(stripped):
        return False
    return bool(DISPATCH_STATUS_QUESTION.match(stripped))


def _status_words(text: str) -> set[str]:
    return {
        word for word in re.findall(r"[a-z0-9]+", (text or "").lower())
        if len(word) > 3 and word not in _ACCEPTED_STOPWORDS
    }


def _step_text(step, index: int) -> str:
    if isinstance(step, str):
        return step.strip() or f"Step {index}"
    if isinstance(step, dict):
        return (
            step.get("text") or step.get("title") or step.get("prompt") or f"Step {index}"
        ).strip()
    return f"Step {index}"


def _accepted_matches_step(accepted, step) -> bool:
    if not isinstance(accepted, dict) or not accepted.get("ok"):
        return False
    receipt = accepted.get("receipt")
    if not isinstance(receipt, str) or "accepted" not in receipt.lower():
        return False
    step_text = step if isinstance(step, str) else _step_text(step, 0)
    return bool(_status_words(receipt) & _status_words(step_text))


def _job_observed_at(job) -> float | None:
    if not isinstance(job, dict):
        return None
    for key in ("heartbeat_at", "updated_at", "started_at"):
        value = job.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value
    return None


def format_dispatch_status(goal, steps, jobs, accepted=None, hold=None, now=None) -> str:
    """Project recorded plan/job evidence. Not a planner or permission change."""
    steps = list(steps or [])
    jobs = [job for job in (jobs or []) if isinstance(job, dict)]
    job = jobs[-1] if jobs else None
    now = time.time() if now is None else now
    stage = str(job.get("status") or "unknown") if job else "proposed"
    completed = []
    for index, step in enumerate(steps, 1):
        if _accepted_matches_step(accepted, step):
            completed.append((index, _step_text(step, index)))
    stale = False
    observed = _job_observed_at(job) if job else None
    if job and stage in ("running", "queued") and observed is not None and (now - observed) > _STALE_SECONDS:
        stale = True
    completed_indexes = {index for index, _ in completed}
    next_unresolved = None
    for index, step in enumerate(steps, 1):
        if index not in completed_indexes:
            next_unresolved = (index, _step_text(step, index))
            break
    lines = [f"Goal: {(goal or '').strip() or 'this work'}."]
    if stage == "proposed":
        lines.append("This plan is proposed.")
    if completed:
        lines.append(
            "Completed steps with evidence: "
            + ", ".join(text.rstrip(".") for _, text in completed)
            + "."
        )
    lines.append(f"Current recorded stage: {stage}.")
    if stage == "running" and not stale and next_unresolved and steps:
        lines.append(f"Currently on step {next_unresolved[0]} of {len(steps)}.")
    if next_unresolved and not (stale and not completed) and stage != "completed":
        index, text = next_unresolved
        lines.append(f"Next unresolved step: {index}. {text}")
    if stage == "completed":
        if next_unresolved is None:
            lines.append("No unresolved step remains.")
        lines.append("The recorded work is complete.")
    if stage == "partial-failure":
        lines.append("A later step failed.")
        lines.append("Later steps are unknown.")
    if stale:
        lines.append("Recent worker evidence is unknown.")
    if isinstance(hold, dict) and hold.get("active"):
        lines.append("Hold remains in effect.")
    return " ".join(lines)


def dispatch_status_receipt(record, hold=None, now=None) -> str:
    record = record if isinstance(record, dict) else {}
    goal = record.get("task") or record.get("text") or record.get("goal") or ""
    steps = record.get("subtasks") or record.get("steps") or []
    return format_dispatch_status(
        goal,
        steps,
        record.get("jobs") or [],
        accepted=record.get("accepted"),
        hold=hold if hold is not None else record.get("hold"),
        now=now,
    )


def dispatch_status_from_conversation(conversation, hold=None, now=None) -> str:
    record = {"task": "", "subtasks": [], "jobs": []}
    for message in reversed((conversation or {}).get("messages") or []):
        intent = message.get("dispatch_intent") or {}
        if not (intent.get("goal") or intent.get("subtasks") or intent.get("steps") or intent.get("jobs")):
            continue
        record = {
            "task": intent.get("goal") or intent.get("prompt") or intent.get("task") or "",
            "text": intent.get("prompt") or intent.get("text") or "",
            "subtasks": intent.get("subtasks") or intent.get("steps") or [],
            "jobs": intent.get("jobs") or message.get("jobs") or [],
            "accepted": intent.get("accepted") or message.get("accepted"),
        }
        break
    return dispatch_status_receipt(record, hold=hold, now=now)
