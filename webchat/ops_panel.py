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
_REFRESH_COOLDOWN = 45.0
_last_refresh_spawn = 0.0


def maybe_spawn_dashboard_refresh(root: Path) -> bool:
    """Non-blocking dashboard-updater tick when dashboard.json is stale."""
    global _last_refresh_spawn
    now = time.time()
    if now - _last_refresh_spawn < _REFRESH_COOLDOWN:
        return False
    dash = root / "conductor/dashboard.json"
    if dash.exists() and now - dash.stat().st_mtime <= LIVE_OPS_MAX_AGE:
        return False
    lock = root / "conductor/locks/webchat-dashboard-refresh.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        handle = lock.open("a")
        try:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, ImportError):
            handle.close()
            return False
        handle.close()
    except OSError:
        return False
    services = root / "conductor/services"
    script = (
        f"import sys; sys.path.insert(0, '{services}'); "
        "from runtime import dashboard_cycle; dashboard_cycle()"
    )
    try:
        subprocess.Popen(
            [sys.executable, "-c", script],
            cwd=str(root),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        _last_refresh_spawn = now
        return True
    except OSError:
        return False


def draft_head_sha(root: Path) -> str | None:
    conductor = root / "conductor"
    for base in (conductor, root):
        if not (base / ".git").exists():
            continue
        try:
            return subprocess.check_output(
                ["git", "-C", str(base), "rev-parse", "--short", "HEAD"],
                text=True,
                timeout=5,
            ).strip()
        except (subprocess.SubprocessError, OSError):
            continue
    return None


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
            meta["stale"] = True
        except (OSError, json.JSONDecodeError, ValueError):
            live_ops = {}
    cached_ops = live_ops
    try:
        inline = inline_live_ops(root)
        generated = _parse_generated_at(inline)
        inline_age = time.time() - generated if generated else None
        if inline and inline_age is not None and inline_age <= max_age:
            meta.update(
                source="inline_snapshot",
                stale=False,
                generated_at=inline.get("generated_at"),
            )
            return {"live_ops": inline, "meta": meta}
    except Exception:
        pass
    if cached_ops:
        meta.update(source="dashboard.json", stale=True, generated_at=cached_ops.get("generated_at"))
        return {"live_ops": cached_ops, "meta": meta}
    meta.update(source="unavailable", stale=True)
    return {"live_ops": {}, "meta": meta}


def _stall_plain(stall: str, live: bool) -> str:
    if stall == "stalled":
        return "Stalled — no heartbeat" if live else "Marked stalled"
    if stall == "running":
        return "Running normally" if live else "Tracked as running"
    if stall == "queued":
        return "Waiting to start"
    return "Status unknown"


def enrich_live_ops(live_ops: dict) -> dict:
    """Plain-English display fields for Jobs dashboard (phone)."""
    if not live_ops:
        return live_ops
    jobs = []
    for row in live_ops.get("running_jobs") or []:
        job = dict(row)
        live = bool(job.get("live_screen"))
        stall = job.get("stall_state") or "unknown"
        state = job.get("state") or ""
        job["stall_plain"] = _stall_plain(stall, live)
        if live and stall == "stalled":
            job["display_state"] = "Stalled on screen"
        elif live:
            job["display_state"] = "Live on screen"
        elif state in ("running", "launched"):
            job["display_state"] = "Marked running; screen unconfirmed"
        elif state == "queued":
            job["display_state"] = "Queued"
        else:
            job["display_state"] = "Tracked"
        jobs.append(job)
    screens = live_ops.get("service_screens") or []
    return {**live_ops, "running_jobs": jobs, "service_screen_count": len(screens)}


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
        "council_hint": "Tap Ask council in Jobs or chat, then approve the card (Gemini + MiniMax + Claude on the mini; no Grok).",
        "round_hint": "Tap Start round in Jobs or chat, then approve the card to queue a draft screen job.",
        "safety": "Drafts only · never merge, send, or spend · no Grok",
        "read_at": time.time(),
    }
