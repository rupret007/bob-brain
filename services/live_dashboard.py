#!/usr/bin/env python3
"""Plain-English live ops slice for dashboard.json and agents-status.json (no secrets)."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from datetime import datetime, timezone

from state import CONDUCTOR, ROOT

MINIMAX_DISPLAY_CAP_USD = 59.0
_SCORE_ROW = re.compile(r"^\|\s*([^|]+?)\s*\|\s*[^|]*\|\s*\*\*([^*]+?)\*\*", re.M)
_HOME = re.compile(r"/Users/[^\s\"']+")


def _redact_line(line: str) -> str:
    line = _HOME.sub("[mini]", line)
    for pattern in (r"gh[pousr]_[A-Za-z0-9]{20,}", r"AIza[0-9A-Za-z_-]{20,}", r"sk-[A-Za-z0-9_-]{16,}"):
        line = re.sub(pattern, "[redacted]", line)
    return line.strip()[:240]


def _tail_lines(path: Path, count: int = 3) -> list[str]:
    if not path.is_file():
        return []
    try:
        text = path.read_text(errors="replace")
    except OSError:
        return []
    lines = [_redact_line(line) for line in text.splitlines() if line.strip()]
    return lines[-count:]


def _job_log_lines(job_dir: Path, job_id: str) -> list[str]:
    candidates = [
        job_dir / "worker.log",
        job_dir / "run.log",
        job_dir / "screen.log",
        ROOT / "logs" / (job_id + ".log"),
        ROOT / "logs" / (job_id + "-screen.log"),
    ]
    for path in candidates:
        lines = _tail_lines(path)
        if lines:
            return lines
    return []


def _plain_english(job_id: str, engine: str | None, state: str, log_lines: list[str]) -> str:
    if log_lines:
        return log_lines[-1]
    if state == "running":
        return f"{engine or 'worker'} job {job_id[:24]} is active on a screen session."
    if state == "blocked":
        return f"{job_id[:24]} is blocked waiting on recovery."
    return f"{job_id[:24]} is {state}."


def _git_head(job_dir: Path) -> dict:
    if not job_dir.is_dir():
        return {}
    git_dir = job_dir / ".git"
    head = job_dir / ".git" / "HEAD"
    if not head.is_file() and not git_dir.is_file():
        return {}
    from command import run

    result = run(["git", "-C", str(job_dir), "log", "-1", "--format=%h|%s"], capture_output=True, text=True, timeout=8)
    if result.returncode or "|" not in result.stdout:
        return {}
    sha, message = result.stdout.strip().split("|", 1)
    return {"sha": sha[:12], "message": _redact_line(message)[:160]}


def _webchat_round() -> int | None:
    reviews = CONDUCTOR / "reviews"
    best = 0
    for path in reviews.glob("WEBCHAT-READY-R*-RESULT.md"):
        match = re.search(r"R(\d+)-RESULT", path.name)
        if match:
            best = max(best, int(match.group(1)))
    return best or None


def _scores_table() -> list[dict]:
    reviews = sorted((CONDUCTOR / "reviews").glob("WEBCHAT-READY-R*-RESULT.md"),
                     key=lambda p: p.stat().st_mtime, reverse=True)
    if not reviews:
        return []
    text = reviews[0].read_text(errors="replace")
    rows = []
    for area, score in _SCORE_ROW.findall(text):
        area = area.strip()
        score = score.strip().split()[0]
        if area.lower() in ("area", "check"):
            continue
        if re.match(r"^[\d.]+$", score.split("·")[0].strip()):
            rows.append({"area": area, "score": score.split("·")[0].strip()})
    return rows[:16]


def _lane_roles(lanes: dict, sessions: set[str]) -> dict:
    building = reviewing = None
    for name, lane in (lanes or {}).items():
        state = (lane or {}).get("state", "")
        if state == "busy" and name in ("cursor", "codex"):
            building = name
        if state == "busy" and name in ("gemini", "minimax", "claude"):
            reviewing = reviewing or name
    if "svc-reviewer" in sessions:
        reviewing = reviewing or "reviewer"
    if "svc-job-runner" in sessions:
        building = building or "scheduler"
    return {"building": building, "reviewing": reviewing}


def _stalled(record: dict, now: float, live: bool) -> str:
    state = record.get("state", "unknown")
    if state in ("harvested", "blocked"):
        return "finished" if state == "harvested" else "stalled"
    launched = float(record.get("launched_at") or record.get("timestamp") or now)
    age = now - launched
    if not live and state == "running":
        return "stalled"
    if live and age > 6 * 3600:
        return "stalled"
    return "running" if live else state


def build_live_ops(*, sessions: dict, jobs_map: dict, lanes: dict, spend: dict, now: float | None = None) -> dict:
    now = time.time() if now is None else now
    session_names = set(sessions)
    svc_screens = {name for name in session_names if name.startswith("svc-") or name.startswith("drill-")}
    active_jobs = []
    for job_id, record in jobs_map.items():
        if record.get("state") not in ("running", "launched", "queued"):
            continue
        live = job_id in session_names
        if not live and record.get("state") != "running":
            continue
        job_dir = Path(record.get("job_dir") or ROOT / job_id)
        log_lines = _job_log_lines(job_dir, job_id)
        launched = float(record.get("launched_at") or record.get("timestamp") or now)
        active_jobs.append({
            "job_id": job_id,
            "engine": record.get("engine") or record.get("model"),
            "state": record.get("state"),
            "live_screen": live,
            "stall_state": _stalled(record, now, live),
            "started_at": datetime.fromtimestamp(launched, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00") if launched else None,
            "elapsed_seconds": round(max(0, now - launched)),
            "plain_now": _plain_english(job_id, record.get("engine"), record.get("state", ""), log_lines),
            "log_tail": log_lines,
            "last_commit": _git_head(job_dir),
            "round": _webchat_round(),
        })
    active_jobs.sort(key=lambda row: (0 if row["live_screen"] else 1, -row["elapsed_seconds"]))
    minimax = spend.get("minimax") or {}
    roles = _lane_roles(lanes, session_names)
    return {
        "generated_at": datetime.fromtimestamp(now, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
        "webchat_round": _webchat_round(),
        "scores": _scores_table(),
        "minimax_spend": {
            "committed_usd": round(float(minimax.get("committed_usd") or 0), 4),
            "cap_usd": MINIMAX_DISPLAY_CAP_USD,
            "remaining_usd": round(max(0, MINIMAX_DISPLAY_CAP_USD - float(minimax.get("committed_usd") or 0)), 4),
        },
        "roles": roles,
        "service_screens": sorted(svc_screens),
        "running_jobs": active_jobs[:12],
    }


def public_live_ops(live_ops: dict) -> dict:
    """Strip local paths and ids for GitHub Pages payload."""
    jobs = []
    for row in live_ops.get("running_jobs") or []:
        jobs.append({
            "engine": row.get("engine") or "worker",
            "stall_state": row.get("stall_state"),
            "elapsed_seconds": row.get("elapsed_seconds"),
            "plain_now": row.get("plain_now"),
            "log_tail": row.get("log_tail"),
            "last_commit": row.get("last_commit"),
            "round": row.get("round"),
            "live_screen": row.get("live_screen"),
        })
    return {
        "webchat_round": live_ops.get("webchat_round"),
        "scores": live_ops.get("scores"),
        "minimax_spend": live_ops.get("minimax_spend"),
        "roles": live_ops.get("roles"),
        "running_jobs": jobs,
    }
