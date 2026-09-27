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
    return "I can't tell from what I have here. Which file or detail should I look at?"


def is_drill_noise(text: str) -> bool:
    return bool(_DRILL_LEAK.search(text or ""))
