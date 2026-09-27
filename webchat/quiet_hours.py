"""Central Time quiet hours for Web Bob (no push / optional speak)."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

CT = ZoneInfo("America/Chicago")


def in_quiet_hours(now: datetime | None = None) -> bool:
    """True between 11 PM and 7 AM America/Chicago (Jeff ADDED 02:51)."""
    now = now or datetime.now(CT)
    if now.tzinfo is None:
        now = now.replace(tzinfo=CT)
    else:
        now = now.astimezone(CT)
    hour = now.hour
    return hour >= 23 or hour < 7
