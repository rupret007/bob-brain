"""Plain-English job card fields for Jobs tab (shared contract for UI tests)."""
from __future__ import annotations

from typing import Optional


def filter_events(events):
    rows = events or []
    return [e for e in rows if isinstance(e, dict) and (e.get("text") or e.get("sha") or e.get("state"))]


def job_card_headline(job: dict) -> str:
    events = filter_events(job.get("events"))
    if events:
        status = next((e.get("text") for e in events if e.get("kind") == "status"), None)
        if status:
            return status
    return job.get("plain_now") or "Working…"


def job_card_log_lines(job: dict) -> list[str]:
    events = filter_events(job.get("events"))
    if events:
        return [e["text"] for e in events if e.get("kind") == "log" and e.get("text")][-3:]
    return list(job.get("log_tail") or [])[-3:]


def job_card_stall_state(job: dict) -> Optional[str]:
    events = filter_events(job.get("events"))
    stall = next((e.get("state") for e in events if e.get("kind") == "stall"), None)
    return stall or job.get("stall_state")
