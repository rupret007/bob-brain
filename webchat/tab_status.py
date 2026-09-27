"""Read-only data for the phone tabs, without cached dashboard or review content."""
from __future__ import annotations

import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path

from live_status_snapshot import observe_work
from jobs_view import is_drill


def recorded_usage(root: Path, name: str, *, now: float) -> dict:
    """Read measured usage directly; a missing ledger is not zero dollars."""
    if name not in ("gemini", "minimax"):
        path = root / "conductor/plan-usage.json"
        try:
            row = json.loads(path.read_text()).get(name, {})
            percent, reset = row.get("used_percent"), row.get("reset_at")
            if (isinstance(percent, (int, float)) and not isinstance(percent, bool) and math.isfinite(percent) and 0 <= percent <= 100
                    and isinstance(reset, (int, float)) and math.isfinite(reset) and reset > now
                    and 0 <= now - path.stat().st_mtime < 86400):
                return dict(used_percent=percent, reset_at=reset, observed_at=path.stat().st_mtime)
        except (OSError, ValueError, TypeError, AttributeError):
            pass
        return {}
    path = root / "conductor/ledger" / (name + ".jsonl")
    try:
        rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        calls = {row["call_id"]: row for row in rows}
        if not calls:
            return {}
        spent = reserved = 0.0
        for row in calls.values():
            cost = row.get("cost_usd")
            value = cost if cost is not None else row.get("reserved_usd")
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value < 0:
                return {}
            if cost is None:
                reserved += value
            else:
                spent += value
        return dict(spent_usd=round(spent, 6), reserved_usd=round(reserved, 6),
                    observed_at=path.stat().st_mtime)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return {}


def overview(chat, conversation_id=None) -> dict:
    captured_at = datetime.now(timezone.utc).isoformat()
    observed = observe_work(chat.root)
    try:
        health = chat.providers.health(conversation_id).get("providers", {})
    except Exception:
        health = {}
    now = time.time()
    models = {}
    for name in ("codex", "cursor", "claude", "gemini", "minimax"):
        if name not in health:
            continue
        row = health[name]
        # Cached lane budgets and text are deliberately not part of this view.
        models[name] = {key: row.get(key) for key in ("state", "reason", "retry_at", "last_success")}
        models[name]["usage"] = recorded_usage(chat.root, name, now=now)
    try:
        status = chat.self_improve_status()
        automation = {key: status.get(key) for key in ("launchd_loaded", "launchd_files_ok")}
    except Exception:
        automation = {}
    return dict(
        captured_at=captured_at,
        inspection=observed["inspection"],
        work=[row for row in observed["work"] if not is_drill(row)],
        queued=[row for row in observed["queue"]["queued"] if not is_drill(row)],
        models=models,
        automation=automation,
    )
