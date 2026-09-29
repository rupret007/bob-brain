#!/usr/bin/env python3
"""Gentle webchat deploy restarts (03:40): defer while replies are in flight or batched too soon."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

RESTART_MIN_INTERVAL_SEC = 30 * 60
TYPING_GRACE_SEC = 2 * 60
STATE_NAME = ".deploy-restart-state.json"


def _state_path(root: Path) -> Path:
    return root / "conductor" / "webchat" / STATE_NAME


def load_state(root: Path) -> dict:
    path = _state_path(root)
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(root: Path, state: dict) -> None:
    path = _state_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name("." + path.name + ".tmp")
    temporary.write_text(json.dumps(state, indent=2) + "\n")
    os.replace(temporary, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def evaluate_restart(
    *,
    in_flight_replies: int,
    last_client_activity_ts: float | None = None,
    last_restart_ts: float | None = None,
    now: float | None = None,
) -> dict:
    """Return whether a deliberate deploy restart is allowed and why not."""
    now = now if now is not None else time.time()
    defer: list[str] = []
    if in_flight_replies > 0:
        defer.append("in_flight_replies")
    if last_client_activity_ts is not None and now - last_client_activity_ts < TYPING_GRACE_SEC:
        defer.append("recent_client_activity")
    if last_restart_ts is not None and now - last_restart_ts < RESTART_MIN_INTERVAL_SEC:
        defer.append("batch_window")
    return {
        "allowed": not defer,
        "defer_reasons": defer,
        "in_flight_replies": in_flight_replies,
        "restart_min_interval_sec": RESTART_MIN_INTERVAL_SEC,
        "typing_grace_sec": TYPING_GRACE_SEC,
    }


def authenticated_verdict(panel: dict) -> dict:
    """Honor the server's activity check; missing auth/status must fail closed."""
    verdict = panel.get("deploy_restart") if isinstance(panel, dict) else None
    active = panel.get("in_flight_replies") if isinstance(panel, dict) else None
    if not isinstance(verdict, dict) or not isinstance(active, int) or "allowed" not in verdict:
        return {"allowed": False, "defer_reasons": ["status_unavailable"]}
    if active:
        return {"allowed": False, "defer_reasons": ["in_flight_replies"]}
    return verdict


def record_restart(root: Path, reason: str, *, deferred: bool = False) -> dict:
    state = load_state(root)
    now = time.time()
    entry = {"at": now, "reason": (reason or "deploy")[:200], "deferred": bool(deferred)}
    history = state.get("history") or []
    history.append(entry)
    state["history"] = history[-40:]
    if not deferred:
        state["last_restart_at"] = now
    save_state(root, state)
    return entry


def append_restart_event(root: Path, reason: str, deferred: bool, defer_reasons: list[str]) -> None:
    events = root / "conductor" / "state" / "events.jsonl"
    events.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "actor": "webchat",
        "kind": "deploy-restart",
        "at": time.strftime("%Y-%m-%d %H:%M:%S CT"),
        "ts": time.time(),
        "reason": (reason or "deploy")[:200],
        "deferred": deferred,
        "defer_reasons": defer_reasons,
    }
    try:
        with events.open("a") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except OSError:
        pass
