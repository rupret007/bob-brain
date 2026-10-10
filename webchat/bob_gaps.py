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
from urllib.error import URLError

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
    abstract = payload.get("AbstractText")
    abstract_url = payload.get("AbstractURL")
    heading = payload.get("Heading")
    if abstract is not None and not isinstance(abstract, str):
        raise ValueError("Search response was not an object")
    if abstract_url is not None and not isinstance(abstract_url, str):
        raise ValueError("Search response was not an object")
    if heading is not None and not isinstance(heading, str):
        raise ValueError("Search response was not an object")
    abstract = (abstract or "").strip()
    abstract_url = (abstract_url or "").strip()
    heading = (heading or "").strip()
    related = []
    related_text = ""
    related_url = ""
    topics = payload.get("RelatedTopics")
    if topics is not None and not isinstance(topics, list):
        raise ValueError("Search response was not an object")
    for topic in topics or []:
        if not isinstance(topic, dict):
            continue
        text = topic.get("Text")
        first_url = topic.get("FirstURL")
        if text is not None and not isinstance(text, str):
            raise ValueError("Search response was not an object")
        if first_url is not None and not isinstance(first_url, str):
            raise ValueError("Search response was not an object")
        if text and text.strip():
            related_text = text.strip()
            related_url = (first_url or "").strip()
            related.append({"text": related_text, "url": related_url})
            break
    if abstract:
        answer, source, status = abstract, abstract_url, "ok"
    elif related_text:
        # Related-topic URLs stay attached to that topic only. An unused
        # AbstractURL is not evidence for a different snippet.
        answer, source, status = related_text, related_url, "ok"
    else:
        answer, source, status = "", "", "empty"
    source = _web_lookup_source_url(source)
    return {
        "answer": answer[:16000],
        "source": source[:2000],
        "heading": heading[:500],
        "status": status,
        "abstract": abstract[:16000],
        "related": related,
        "query": query,
    }


def _web_lookup_source_url(url: str) -> str:
    parsed = urllib.parse.urlsplit((url or "").strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return ""
    return (url or "").strip()[:2000]


def _web_lookup_query(query: str) -> str:
    cleaned = re.sub(
        r"^(?:please\s+)?(?:search\s+(?:the\s+)?web|look\s+up|google)\s+(?:for\s+)?",
        "",
        (query or "").strip(),
        flags=re.I,
    )
    return cleaned[:200] or "the query"


def _web_lookup_status(result) -> str:
    if not isinstance(result, dict):
        return "invalid"
    status = result.get("status")
    if isinstance(status, str) and status.strip():
        return status.strip().lower()
    answer = result.get("answer") or result.get("abstract")
    if isinstance(answer, str) and answer.strip():
        return "ok"
    if result.get("error"):
        return "invalid"
    return "empty"


def web_lookup_receipt(query: str, result) -> str:
    """Honest Instant Answer receipt. Links are returned, never page evidence."""
    status = _web_lookup_status(result)
    label = _web_lookup_query(query if query else (result.get("query") if isinstance(result, dict) else "") or "")
    if status in ("http_error", "timeout"):
        return (
            f"DuckDuckGo Instant Answer lookup failed ({status}). "
            "Source pages were not opened."
        )
    if status == "invalid" or not isinstance(result, dict):
        return (
            "DuckDuckGo Instant Answer response was malformed or unreadable. "
            "Source pages were not opened."
        )
    answer = result.get("answer") or result.get("abstract") or ""
    if not isinstance(answer, str):
        return (
            "DuckDuckGo Instant Answer response was malformed or unreadable. "
            "Source pages were not opened."
        )
    answer = answer.strip()
    heading = result.get("heading") if isinstance(result.get("heading"), str) else ""
    heading = heading.strip()
    source = _web_lookup_source_url(result.get("source") if isinstance(result.get("source"), str) else "")
    if status == "empty" or not answer:
        return (
            f"DuckDuckGo Instant Answer returned no instant answer for {label}. "
            "Source pages were not opened."
        )
    lines = ["DuckDuckGo Instant Answer (source pages were not opened)."]
    if heading:
        lines.append(f"**{heading}** — {answer[:16000]}")
    else:
        lines.append(answer[:16000])
    if source:
        lines.append(f"Source link: {source}")
        lines.append("Those links are not verified page evidence.")
    return "\n".join(lines)


def format_web_search_reply(result: dict) -> str:
    query = result.get("query") if isinstance(result, dict) else ""
    return web_lookup_receipt(query or "", result)


def lookup_web(query: str, opener=None) -> str:
    """Chat/local-task adapter: Instant Answer receipt, no raw transport text."""
    try:
        return web_lookup_receipt(query, web_search(query, opener=opener))
    except TimeoutError:
        return web_lookup_receipt(query, {"status": "timeout"})
    except URLError:
        return web_lookup_receipt(query, {"status": "http_error"})
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return web_lookup_receipt(query, {"status": "invalid"})


def resolve_capture_path(root: Path, capture_id: str) -> Path | None:
    if not re.fullmatch(r"[0-9a-f]{16}", capture_id or ""):
        return None
    path = root / "conductor/webchat/captures" / f"{capture_id}.png"
    return path if path.is_file() else None
