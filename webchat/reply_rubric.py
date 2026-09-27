"""Concrete rubric checks for Web Bob reply quality."""
from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

from worker_activity import WORKER_NAMES

_UNKNOWN = re.compile(r"\bunknown task\b|task details unavailable\b", re.I)
_MAGIC = re.compile(r"</?bob-webchat-reply>", re.I)
_EMPTY_PROMISE = re.compile(
    r"(?is)\b(?:i understand\.?\s*)?i(?:'ll| will) focus on\b|"
    r"\bproviding more detailed(?: and useful)? updates\b|"
    r"\bokay, i'll focus on getting\b",
)
_ANSWER_DEFER = re.compile(
    r"^(?:okay[,!]?|ok[,!]?|sure[,!]?|got it[,!]?|i understand)\s*[-—]?\s*"
    r"(?:i(?:'ll| will)|let me)\b",
    re.I,
)
_STATUS_DUMP = re.compile(r"\bJob runner:\b.*\bService sessions:\b", re.S)
_SEND_CLAIM = re.compile(r"\b(?:i (?:sent|texted)|message sent|sms sent)\b", re.I)


def line_count(text: str) -> int:
    return len([line for line in (text or "").splitlines() if line.strip()])


def check_answer_first(reply: str) -> tuple[bool, str]:
    first = next((line.strip() for line in (reply or "").splitlines() if line.strip()), "")
    if not first:
        return False, "empty reply"
    if _ANSWER_DEFER.match(first) and not re.search(r"\b\d+\b|https?://|[-*]\s", reply):
        return False, "opens with deferral instead of an answer"
    return True, ""


def check_no_unknown_task(reply: str) -> tuple[bool, str]:
    if _UNKNOWN.search(reply or ""):
        return False, "contains unknown/unavailable task wording"
    return True, ""


def check_no_magic_prefix(reply: str) -> tuple[bool, str]:
    if _MAGIC.search(reply or ""):
        return False, "leaked bob-webchat-reply tags"
    return True, ""


def check_no_empty_promises(reply: str) -> tuple[bool, str]:
    if _EMPTY_PROMISE.search(reply or ""):
        return False, "hollow progress / empty promise"
    return True, ""


def check_status_max_lines(reply: str, limit: int = 8) -> tuple[bool, str]:
    count = line_count(reply)
    if count > limit:
        return False, f"{count} lines (max {limit})"
    return True, ""


def check_version_short_sha(reply: str) -> tuple[bool, str]:
    body = (reply or "").strip()
    if not re.fullmatch(r"[0-9a-f]{7}", body, re.I):
        return False, "version reply should be only the short SHA"
    return True, ""


def check_hold_coherent(reply: str) -> tuple[bool, str]:
    if not (reply or "").strip():
        return False, "empty hold reply"
    return True, ""


def check_draft_only_no_send(reply: str) -> tuple[bool, str]:
    if _SEND_CLAIM.search(reply or ""):
        return False, "claims a text was sent"
    return True, ""


def check_not_status_only(reply: str, meta: dict) -> tuple[bool, str]:
    if meta.get("jobs_created") or meta.get("task_ids"):
        return True, ""
    if _STATUS_DUMP.search(reply or ""):
        return False, "action request answered with status dump only"
    if re.search(r"\bJob runner:\b", reply or "") and line_count(reply) > 4:
        return False, "long status-style reply without queued work"
    return False, "no jobs or task ids recorded"


def check_action_creates_jobs(meta: dict) -> tuple[bool, str]:
    if meta.get("jobs_created") or meta.get("task_ids") or meta.get("action_queued"):
        return True, ""
    return False, "expected server-confirmed job or queue action"


def _format_reset(ts: float) -> set[str]:
    labels = set()
    for tz in (timezone.utc,):
        dt = datetime.fromtimestamp(ts, tz=tz)
        labels.add(dt.strftime("%-I:%M %p").lower().replace("  ", " "))
        labels.add(dt.strftime("%I:%M %p").lstrip("0").lower())
    labels.add(str(int(ts)))
    return labels


def check_reset_attribution(reply: str, root: Path) -> tuple[bool, str]:
    text = reply or ""
    if not re.search(r"\breset", text, re.I):
        return True, "no reset claims"
    path = root / "conductor/plan-usage.json"
    if not path.is_file():
        return True, "no plan-usage ledger"
    try:
        usage = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return True, "unreadable plan-usage"
    for name, row in usage.items():
        reset = row.get("reset_at")
        if not isinstance(reset, (int, float)) or not math.isfinite(reset):
            continue
        label = WORKER_NAMES.get(name, name)
        window = re.search(rf"{re.escape(label)}[^.\n]{{0,120}}", text, re.I)
        if not window or "reset" not in window.group(0).lower():
            continue
        snippet = window.group(0).lower()
        allowed = _format_reset(float(reset))
        if not any(token in snippet for token in allowed):
            return False, f"{label} reset time does not match plan-usage.json"
        for other, other_row in usage.items():
            if other == name:
                continue
            other_reset = other_row.get("reset_at")
            if not isinstance(other_reset, (int, float)) or not math.isfinite(other_reset):
                continue
            other_labels = _format_reset(float(other_reset))
            if any(token in snippet for token in other_labels):
                return False, f"{label} line cites another model's reset time"
    return True, ""


CHECKS = {
    "answer_first": lambda reply, root, meta: check_answer_first(reply),
    "no_unknown_task": lambda reply, root, meta: check_no_unknown_task(reply),
    "no_magic_prefix": lambda reply, root, meta: check_no_magic_prefix(reply),
    "no_empty_promises": lambda reply, root, meta: check_no_empty_promises(reply),
    "status_max_lines": lambda reply, root, meta: check_status_max_lines(reply),
    "reset_attribution": lambda reply, root, meta: check_reset_attribution(reply, root),
    "version_short_sha": lambda reply, root, meta: check_version_short_sha(reply),
    "hold_coherent": lambda reply, root, meta: check_hold_coherent(reply),
    "draft_only_no_send": lambda reply, root, meta: check_draft_only_no_send(reply),
    "not_status_only": lambda reply, root, meta: check_not_status_only(reply, meta),
    "action_creates_jobs": lambda reply, root, meta: check_action_creates_jobs(meta),
}


def evaluate_rubrics(reply: str, root: Path, rubrics: list[str], meta: dict) -> list[dict]:
    rows = []
    for name in rubrics:
        checker = CHECKS.get(name)
        if not checker:
            rows.append(dict(rubric=name, ok=False, detail="unknown rubric"))
            continue
        ok, detail = checker(reply, root, meta)
        rows.append(dict(rubric=name, ok=bool(ok), detail=detail))
    return rows
