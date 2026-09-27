"""Dashboard live_ops + conductor read snapshot for Web Bob status panel."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

LIVE_OPS_MAX_AGE = 120.0


def _parse_generated_at(live_ops: dict) -> float | None:
    raw = live_ops.get("generated_at")
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        return datetime.fromisoformat(raw).timestamp()
    except (TypeError, ValueError):
        return None


def inline_live_ops(root: Path) -> dict:
    services = str(root / "conductor/services")
    if services not in sys.path:
        sys.path.insert(0, services)
    from runtime import snapshot

    return snapshot().get("live_ops") or {}


def load_live_ops(root: Path, *, max_age: float = LIVE_OPS_MAX_AGE) -> dict:
    dash_path = root / "conductor/dashboard.json"
    meta = {"source": "none", "dashboard_modified_at": None, "generated_at": None, "stale": True}
    live_ops: dict = {}
    if dash_path.exists():
        try:
            meta["dashboard_modified_at"] = dash_path.stat().st_mtime
            payload = json.loads(dash_path.read_text(errors="replace"))
            live_ops = payload.get("live_ops") or {}
            meta["generated_at"] = live_ops.get("generated_at")
            generated = _parse_generated_at(live_ops)
            age = time.time() - generated if generated else time.time() - meta["dashboard_modified_at"]
            if live_ops and age <= max_age:
                meta.update(source="dashboard.json", stale=False)
                return {"live_ops": live_ops, "meta": meta}
        except (OSError, json.JSONDecodeError, ValueError):
            live_ops = {}
    try:
        live_ops = inline_live_ops(root)
        meta.update(source="inline_snapshot", stale=False, generated_at=live_ops.get("generated_at"))
    except Exception:
        meta["source"] = "dashboard_stale" if live_ops else "unavailable"
        meta["stale"] = True
    return {"live_ops": live_ops, "meta": meta}


def conductor_snapshot(root: Path) -> dict:
    conductor = root / "conductor"
    branch = "unknown"
    head = "unknown"
    try:
        branch = subprocess.check_output(
            ["git", "-C", str(conductor), "branch", "--show-current"],
            text=True,
            timeout=5,
        ).strip() or "unknown"
        head = subprocess.check_output(
            ["git", "-C", str(conductor), "rev-parse", "HEAD"],
            text=True,
            timeout=5,
        ).strip()
    except (subprocess.SubprocessError, OSError):
        pass
    latest_result = None
    reviews = sorted(conductor.glob("reviews/WEBCHAT-READY-R*-RESULT.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    if reviews:
        latest_result = {"name": reviews[0].name, "modified_at": reviews[0].stat().st_mtime}
    pass_schedule = {}
    path = conductor / "pass-schedule.json"
    if path.exists():
        try:
            pass_schedule = json.loads(path.read_text(errors="replace"))
        except (OSError, json.JSONDecodeError, ValueError):
            pass_schedule = {}
    maintenance = (conductor / "MAINTENANCE").exists()
    round_match = None
    if latest_result:
        round_match = re.search(r"R(\d+)-RESULT", latest_result["name"])
    return {
        "draft_branch": branch,
        "head_sha": head,
        "maintenance": maintenance,
        "webchat_round": int(round_match.group(1)) if round_match else None,
        "latest_result": latest_result,
        "pass_schedule": {
            "state": pass_schedule.get("state"),
            "next_due": pass_schedule.get("next_due"),
            "pass_id": pass_schedule.get("pass_id"),
        },
        "council_hint": "From chat: run council on: <question> then yes, run council (queues Gemini+MiniMax+Claude on the mini; no Grok).",
        "safety": "Drafts only · confirm before merge/send/spend · never Grok",
        "read_at": time.time(),
    }
