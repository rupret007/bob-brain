"""Bob-the-Bot parity: durable memory, web research, and on-demand screenshots."""
from __future__ import annotations

import json
import re
import secrets
import subprocess
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
    r"(?:what\s+(?:was|is)|who\s+won|score\s+of).{0,120}\?",
    re.I,
)


def profile_path(root: Path) -> Path:
    return root / "bob-brain/memory/profile.md"


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


def append_profile_memory(root: Path, fact: str, when: datetime | None = None) -> str:
    when = when or datetime.now(timezone.utc)
    stamp = when.astimezone().strftime("%Y-%m-%d")
    line = f"[{stamp}] {fact.strip()}\n"
    path = profile_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)
    return line.strip()


def parse_screenshot(text: str) -> str | None:
    match = SCREENSHOT.match((text or "").strip())
    if not match:
        return None
    target = (match.group(1) or "").strip()
    return target[:120] if target else ""


def _macos_window_id(app_name: str) -> int | None:
    script = (
        'tell application "System Events" to id of first window of '
        f'(first process whose name contains "{app_name}")'
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
    folder = root / "conductor/webchat/captures"
    folder.mkdir(parents=True, exist_ok=True)
    capture_id = secrets.token_hex(8)
    path = folder / f"{capture_id}.png"
    command = ["screencapture", "-x"]
    if target:
        window_id = _macos_window_id(target)
        if window_id is None:
            raise RuntimeError(f"I could not find an open window matching “{target}”.")
        command.extend(["-l", str(window_id)])
    command.append(str(path))
    subprocess.run(command, check=True, timeout=45)
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


def web_search(query: str, opener=urllib.request.urlopen) -> dict:
    url = "https://api.duckduckgo.com/?" + urllib.parse.urlencode(
        {"q": query, "format": "json", "no_redirect": 1, "no_html": 1, "skip_disambig": 1}
    )
    with opener(url, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
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
    return {"answer": answer, "source": source, "heading": heading}


def format_web_search_reply(result: dict) -> str:
    lines = [result["answer"]]
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
