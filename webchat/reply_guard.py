"""Guardrails for assistant replies (no hollow progress promises)."""
from __future__ import annotations

import re

_HOLLOW_PROGRESS = re.compile(
    r"(?is)"
    r"(?:\b(?:i(?:'m| am) (?:still )?(?:looking|checking|going through|scanning|investigating))\b"
    r"|(?:\b(?:one moment|another minute|minute or two|shouldn't take (?:too )?much longer)\b)"
    r"|(?:\b(?:i'll (?:check|look|get back|find)|let me (?:check|look|find))\b[^.]{0,80}\.(?:\s|$)))"
)

_DRILL_LEAK = re.compile(
    r"\b(?:handback drill|drill-r\d|drill open item|Reply with exactly:\s*drill)\b",
    re.I,
)


def is_hollow_progress_reply(text: str) -> bool:
    """True when the reply promises background work without delivering an answer."""
    if not text or len(text) < 40:
        return False
    if _HOLLOW_PROGRESS.search(text):
        # Substantive answers often include SHAs, links, or bullet facts — not pure stall.
        has_fact = bool(re.search(r"\b[a-f0-9]{7,12}\b|https?://|^\s*[-*]\s+\S", text, re.I | re.M))
        return not has_fact
    return False


def repair_hollow_progress(text: str) -> str:
    if not is_hollow_progress_reply(text):
        return text
    return (
        "I can't run a background scan from this chat — I only answer from what's already on the mini "
        "(STATE, handback, and the snapshots loaded for this turn). "
        "Ask again with a specific path or paste what you see, and I'll work from that."
    )


_READONLY_DISCLAIMER = re.compile(
    r"(?is)"
    r"\b(?:read[- ]only chat|cannot dispatch|can't dispatch|cannot launch|can't launch|"
    r"cannot execute changes|can't execute|cannot run council|can't run council|"
    r"can't directly interact with the file system|requires a direct action on your part|"
    r"you or bob must|jeff or bob must)\b"
)


def is_readonly_disclaimer(text: str) -> bool:
    if not text or len(text) < 50:
        return False
    return bool(_READONLY_DISCLAIMER.search(text))


def repair_readonly_disclaimer(text: str) -> str:
    if not is_readonly_disclaimer(text):
        return text
    return (
        "I can queue draft jobs, run council on the mini, and append builder inbox lines from this chat — "
        "say `start a job: …`, `run council on: …`, or `tell the builder: …`, then approve the card. "
        "I never merge, send, or spend without your yes."
    )


def repair_assistant_reply(text: str) -> str:
    return repair_readonly_disclaimer(repair_hollow_progress(text))


def is_drill_noise(text: str) -> bool:
    return bool(_DRILL_LEAK.search(text or ""))


_EXACT_REPLY_RE = re.compile(r"^Reply with exactly:\s*(.+?)\s*$", re.I)


def try_exact_reply(text: str) -> str | None:
    """Honor explicit echo asks without a model round-trip (ready drill, smoke tests)."""
    stripped = (text or "").strip()
    if "\n" in stripped or "\r" in stripped:
        return None
    match = _EXACT_REPLY_RE.match(stripped)
    if not match:
        return None
    payload = match.group(1).strip()
    if not payload or len(payload) > 80 or "\n" in payload:
        return None
    return payload
