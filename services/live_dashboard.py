#!/usr/bin/env python3
"""Plain-English live ops slice for dashboard.json and agents-status.json (no secrets)."""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

from datetime import datetime, timezone

from state import CONDUCTOR, ROOT

MINIMAX_DISPLAY_CAP_USD = 59.0
_SCORE_ROW = re.compile(r"^\|\s*([^|]+?)\s*\|\s*[^|]*\|\s*\*\*([^*]+?)\*\*", re.M)
_HOME = re.compile(r"/Users/[^\s\"']+")
_SAFE_PUBLIC = re.compile(
    r"^(?:\[[\w]+\]|\s)*(?:PASS|FAIL|OK|error|warn|round|job|screen|svc-|drill-|cursor|codex|gemini|minimax|"
    r"claude|harvest|queued|running|stalled|tests?|commit|SHA|Web Bob|handback|drill|Round \d+)",
    re.I,
)


def _allowlisted_line(line: str) -> str | None:
    cleaned = _redact_line(line)
    if not cleaned or len(cleaned) < 4:
        return None
    if _SAFE_PUBLIC.match(cleaned) or re.search(r"\b(?:PASS|FAIL|tests? \d+|p50|drill-|handback)\b", cleaned, re.I):
        return cleaned
    if re.fullmatch(r"[\w .:,\-–—/|]+", cleaned) and not re.search(r"(?i)(password|secret|token|api[_-]?key|sk-|ghp_)", cleaned):
        return cleaned
    return None


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
    lines = []
    for line in text.splitlines():
        if not line.strip():
            continue
        allowed = _allowlisted_line(line)
        if allowed:
            lines.append(allowed)
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


SELF_IMPROVE_LOG_STALE_SECONDS = 24 * 3600


def _self_improve_log_age_seconds(root: Path) -> int | None:
    log_path = root / "logs/webchat-self-improve.log"
    if not log_path.is_file():
        return None
    try:
        return max(0, int(time.time() - log_path.stat().st_mtime))
    except OSError:
        return None


def _self_improve_plain_line(root: Path) -> str | None:
    """Plain-English self-improve status for dashboard_plain (no secrets)."""
    tick = root / "conductor/webchat/self_improve_tick.sh"
    plist = root / "conductor/launchd/com.jeff.bob-webchat-self-improve.plist"
    log_path = root / "logs/webchat-self-improve.log"
    stale_prefix = ""
    age = _self_improve_log_age_seconds(root)
    if age is not None and age > SELF_IMPROVE_LOG_STALE_SECONDS:
        hours = max(1, int(age // 3600))
        stale_prefix = f"Stale (>{hours}h since log) — "
    if not tick.is_file():
        return stale_prefix + "Pull the draft branch — self-improve scripts missing"
    if not plist.is_file():
        return stale_prefix + "Install nightly loop — tap Copy install in Settings"
    if log_path.is_file():
        try:
            tail = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-12:]
        except OSError:
            tail = []
        for line in reversed(tail):
            low = line.lower()
            if "self-improve tick" not in low:
                continue
            if re.search(r"self-improve tick ok\b|tick ok\b", low) and "failed" not in low:
                base = "Nightly self-improve loop healthy — last tick OK"
                return stale_prefix + base if stale_prefix else base
            if "failed" in low:
                return stale_prefix + "Last self-improve tick failed — check logs on the mini"
    base = "Launchd ready — waiting for first successful tick"
    return stale_prefix + base if stale_prefix else base


def _result_round(path: Path) -> int:
    match = re.search(r"R(\d+)-RESULT", path.name)
    return int(match.group(1)) if match else 0


def _scores_table(root: Path | None = None) -> list[dict]:
    if root is not None:
        reviews_dir = root / "conductor" / "reviews"
    else:
        reviews_dir = CONDUCTOR / "reviews"
    reviews = sorted(
        reviews_dir.glob("WEBCHAT-READY-R*-RESULT.md"),
        key=_result_round,
        reverse=True,
    )
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



def _bob_catchup_preview(root: Path | None = None) -> list[str]:
    """First few plain-English lines from BOB-CATCHUP for Jobs/Models (no secrets)."""
    base = root or ROOT
    catch = base / "conductor" / "state" / "BOB-CATCHUP.md"
    if not catch.is_file():
        return []
    lines: list[str] = []
    for line in catch.read_text(errors="replace").splitlines():
        cleaned = line.strip().lstrip("-•* ").strip()
        if not cleaned or cleaned.startswith("#"):
            continue
        allowed = _allowlisted_line(cleaned) or _redact_line(cleaned)
        if allowed and len(allowed) >= 8:
            lines.append(allowed[:200])
        if len(lines) >= 3:
            break
    return lines


def _scores_measured_at() -> str | None:
    reviews = sorted(
        (CONDUCTOR / "reviews").glob("WEBCHAT-READY-R*-RESULT.md"),
        key=_result_round,
        reverse=True,
    )
    if not reviews:
        return None
    try:
        mtime = reviews[0].stat().st_mtime
    except OSError:
        return None
    return datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _scores_weakest(rows: list[dict]) -> dict:
    weakest_area = None
    weakest_value = None
    min_v = 11.0
    for row in rows:
        raw = str(row.get("score") or "").split("·")[0].strip()
        try:
            value = float(raw)
        except ValueError:
            continue
        if value < min_v:
            min_v = value
            weakest_area = row.get("area")
            weakest_value = value
    if not weakest_area:
        return {}
    return {"area": weakest_area, "value": weakest_value}


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


def _structured_events(row: dict, tail: list[str], commit: dict, plain: str | None) -> list[dict]:
    events: list[dict] = []
    if plain:
        events.append({"kind": "status", "text": plain})
    for line in tail:
        events.append({"kind": "log", "text": line})
    if commit.get("sha"):
        events.append({"kind": "commit", "sha": commit.get("sha"), "message": commit.get("message")})
    stall = row.get("stall_state")
    if stall:
        events.append({"kind": "stall", "state": stall})
    return events[:8]


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
        stall_state = _stalled(record, now, live)
        plain_now = _plain_english(job_id, record.get("engine"), record.get("state", ""), log_lines)
        last_commit = _git_head(job_dir)
        row = {
            "job_id": job_id,
            "engine": record.get("engine") or record.get("model"),
            "state": record.get("state"),
            "live_screen": live,
            "stall_state": stall_state,
            "started_at": datetime.fromtimestamp(launched, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00") if launched else None,
            "elapsed_seconds": round(max(0, now - launched)),
            "plain_now": plain_now,
            "log_tail": log_lines,
            "last_commit": last_commit,
            "round": _webchat_round(),
        }
        row["events"] = _structured_events(row, log_lines[-3:], last_commit, plain_now)
        active_jobs.append(row)
    active_jobs.sort(key=lambda row: (0 if row["live_screen"] else 1, -row["elapsed_seconds"]))
    minimax = spend.get("minimax") or {}
    roles = _lane_roles(lanes, session_names)
    now_line = None
    now_path = CONDUCTOR / "state" / "NOW.md"
    if now_path.is_file():
        for line in now_path.read_text(errors="replace").splitlines():
            if line.strip():
                now_line = _redact_line(line.strip())[:240]
                break
    dash_path = CONDUCTOR / "dashboard.json"
    dashboard_freshness_seconds = None
    if dash_path.is_file():
        try:
            dashboard_freshness_seconds = round(max(0, now - dash_path.stat().st_mtime))
        except OSError:
            dashboard_freshness_seconds = None
    scores = _scores_table()
    committed = float(minimax.get("committed_usd") or 0)
    cap = MINIMAX_DISPLAY_CAP_USD
    pct_used = round(min(100.0, max(0.0, 100.0 * committed / cap)), 1) if cap > 0 else None
    return {
        "generated_at": datetime.fromtimestamp(now, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
        "scores_measured_at": _scores_measured_at(),
        "now_line": now_line,
        "webchat_round": _webchat_round(),
        "dashboard_freshness_seconds": dashboard_freshness_seconds,
        "scores": scores,
        "scores_weakest": _scores_weakest(scores),
        "minimax_spend": {
            "committed_usd": round(committed, 4),
            "cap_usd": cap,
            "remaining_usd": round(max(0, cap - committed), 4),
            "percent_used": pct_used,
        },
        "roles": roles,
        "service_screens": sorted(svc_screens),
        "running_jobs": active_jobs[:12],
    }


def _stall_plain(stall: str, live: bool) -> str:
    if stall == "stalled":
        return "Stalled — no heartbeat" if live else "Marked stalled"
    if stall == "running":
        return "Running normally" if live else "Tracked as running"
    if stall == "queued":
        return "Waiting to start"
    return "Status unknown"


def enrich_running_jobs_display(live_ops: dict) -> dict:
    """Plain-English stall/display fields shared by Web Bob and GitHub Pages payload."""
    live_ops = live_ops or {}
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


def attach_scheduler_queue(live_ops: dict, root: Path) -> dict:
    """READY backlog from next-prompts (same source as Web Bob panel)."""
    webchat = root / "conductor" / "webchat"
    repo_webchat = Path(__file__).resolve().parent.parent / "webchat"
    for candidate in (webchat, repo_webchat):
        if candidate.is_dir() and str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))
            break
    try:
        from job_queue import count_ready_queue, list_ready_queue_jobs
    except ImportError:
        return live_ops
    ready = list_ready_queue_jobs(root, limit=6)
    next_preview = ""
    if ready:
        goal = (ready[0].get("goal") or "").strip()
        if goal:
            next_preview = _redact_line(goal)[:120]
    return {
        **live_ops,
        "queue_ready_count": count_ready_queue(root),
        "queued_jobs": ready,
        "queue_next_preview": next_preview or None,
        "tracked_job_count": len(live_ops.get("running_jobs") or []),
    }


def _ops_snapshot_age_seconds(live_ops: dict, now: float | None = None) -> int | None:
    raw = live_ops.get("generated_at")
    if not raw:
        return None
    now = now if now is not None else time.time()
    try:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return round(max(0, now - parsed.timestamp()))
    except (TypeError, ValueError):
        return None


def _ops_snapshot_plain_text(live_ops: dict) -> str:
    """Plain-English ops bundle freshness for Jobs dashboard (never silent when missing data)."""
    age = live_ops.get("ops_snapshot_age_seconds")
    if isinstance(age, int) and age >= 0:
        if age > 600:
            return f"Stale — last refresh {age // 60}m ago"
        if age > 180:
            return f"May be stale — {age}s ago"
        return f"{age}s ago"
    raw = live_ops.get("generated_at")
    if not raw:
        return "Unknown — cannot verify freshness"
    return "Unknown — timestamp unreadable"


def _build_dashboard_plain(live_ops: dict) -> list[dict]:
    """Mobile-friendly key/value rows for ADDED 02:03 live dashboard (no secrets)."""

    def _row(label: str, value, action: dict | None = None) -> dict | None:
        if value is None:
            return None
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            text = str(value)
        elif isinstance(value, str):
            text = value.strip()
        else:
            return None
        if not text or text == "—":
            return None
        cleaned = _redact_line(text)[:240]
        if not cleaned:
            return None
        item = {"label": label, "value": cleaned}
        if action and isinstance(action, dict) and action.get("type") == "focus_live_job":
            idx = action.get("index")
            if isinstance(idx, int) and idx >= 0:
                item["action"] = {"type": "focus_live_job", "index": idx}
        return item

    rows: list[dict] = []
    for item in (
        _row("Now", live_ops.get("now_line")),
        _row("Live activity", live_ops.get("live_activity_preview")),
        _row(
            "Dashboard age",
            f"{live_ops['dashboard_freshness_seconds']}s ago"
            if live_ops.get("dashboard_freshness_seconds") is not None
            else None,
        ),
        _row("Ops snapshot", _ops_snapshot_plain_text(live_ops)),
        _row("Round", f"Web Bob R{live_ops['webchat_round']}" if live_ops.get("webchat_round") else None),
    ):
        if item:
            rows.append(item)
    roles = live_ops.get("roles") or {}
    if roles.get("building"):
        r = _row("Builder", roles.get("building"))
        if r:
            rows.append(r)
    if roles.get("reviewing"):
        r = _row("Reviewers", roles.get("reviewing"))
        if r:
            rows.append(r)
    spend = live_ops.get("minimax_spend") or {}
    if spend.get("committed_usd") is not None:
        cap = spend.get("cap_usd") or MINIMAX_DISPLAY_CAP_USD
        pct = spend.get("percent_used")
        mini = f"${float(spend['committed_usd']):.2f} of ${cap:.0f}"
        if pct is not None:
            mini += f" ({pct}% used)"
        r = _row("MiniMax spend", mini)
        if r:
            rows.append(r)
    weak = live_ops.get("scores_weakest") or {}
    if weak.get("area"):
        r = _row("Weakest score", f"{weak['area']} ({weak.get('value', '—')})")
        if r:
            rows.append(r)
    si_plain = live_ops.get("self_improve_plain")
    if isinstance(si_plain, str) and si_plain.strip():
        r = _row("Self-improve", si_plain.strip()[:240])
        if r:
            rows.append(r)
    in_flight = live_ops.get("in_flight_replies")
    if isinstance(in_flight, int) and in_flight >= 0:
        r = _row("Replies in flight", str(in_flight))
        if r:
            rows.append(r)
    deploy_sha = live_ops.get("deploy_head_sha")
    if isinstance(deploy_sha, str) and deploy_sha.strip():
        r = _row("Deploy version", deploy_sha.strip()[:12])
        if r:
            rows.append(r)
    deploy_restart = live_ops.get("deploy_restart") or {}
    if isinstance(deploy_restart, dict):
        if deploy_restart.get("allowed"):
            r = _row("Safe restart", "OK — no chats mid-reply")
        else:
            reasons = deploy_restart.get("defer_reasons") or []
            if reasons:
                r = _row("Safe restart", ", ".join(str(x) for x in reasons)[:200])
            else:
                r = None
        if r:
            rows.append(r)
    measured = live_ops.get("scores_measured_at")
    if isinstance(measured, str) and measured.strip():
        stamp = measured.replace("T", " ").replace("Z", " UTC")[:22]
        r = _row("Scores updated", stamp)
        if r:
            rows.append(r)
    live_jobs = [j for j in (live_ops.get("running_jobs") or []) if j.get("live_screen")]
    stalled = sum(1 for j in live_jobs if j.get("stall_state") == "stalled")
    if stalled:
        r = _row("Stalled jobs", f"{stalled} on screen need attention")
        if r:
            rows.append(r)
    if live_jobs:
        job = live_jobs[0]
        elapsed = job.get("elapsed_seconds")
        el_note = f" · {int(elapsed // 60)}m elapsed" if isinstance(elapsed, (int, float)) else ""
        round_n = job.get("round")
        r_note = f" · round {round_n}" if round_n else ""
        commit = job.get("last_commit") or {}
        sha_note = f" · {commit['sha']}" if commit.get("sha") else ""
        headline = job.get("plain_now") or "Live job on screen"
        r = _row(
            "Top live job",
            f"{headline}{r_note}{el_note}{sha_note}",
            action={"type": "focus_live_job", "index": 0},
        )
        if r:
            rows.append(r)
        commit = job.get("last_commit") or {}
        if isinstance(commit, dict) and commit.get("message"):
            msg = _allowlisted_line(str(commit["message"])) or _redact_line(str(commit["message"]))
            sha = commit.get("sha") or ""
            r = _row("Last commit", f"{sha} — {msg}"[:240] if sha else msg[:240])
            if r:
                rows.append(r)
        tail = job.get("log_tail") or []
        if tail:
            last = tail[-1]
            if isinstance(last, str):
                allowed = _allowlisted_line(last) or _redact_line(last)
                r = _row("Latest log line", allowed)
                if r:
                    rows.append(r)
            if len(tail) >= 2:
                parts = []
                for line in tail[-3:]:
                    if isinstance(line, str):
                        allowed = _allowlisted_line(line) or _redact_line(line)
                        if allowed:
                            parts.append(allowed[:100])
                if parts:
                    r = _row("Recent logs", " · ".join(parts)[:240])
                    if r:
                        rows.append(r)
    if len(live_jobs) >= 2:
        job2 = live_jobs[1]
        elapsed2 = job2.get("elapsed_seconds")
        el2 = f" · {int(elapsed2 // 60)}m elapsed" if isinstance(elapsed2, (int, float)) else ""
        headline2 = job2.get("plain_now") or "Another job on screen"
        stall2 = " · stalled" if job2.get("stall_state") == "stalled" else ""
        r = _row(
            "Also running",
            f"{headline2}{el2}{stall2}"[:240],
            action={"type": "focus_live_job", "index": 1},
        )
        if r:
            rows.append(r)
        tail2 = job2.get("log_tail") or []
        if tail2:
            last2 = tail2[-1]
            if isinstance(last2, str) and last2.strip():
                allowed2 = _allowlisted_line(last2) or _redact_line(last2)
                r = _row(
                    "Also job log",
                    allowed2[:240],
                    action={"type": "focus_live_job", "index": 1},
                )
                if r:
                    rows.append(r)
    if len(live_jobs) >= 3:
        extra = len(live_jobs) - 2
        stalled_extra = sum(
            1 for j in live_jobs[2:] if j.get("stall_state") == "stalled"
        )
        summary = f"{extra} more on screen"
        if stalled_extra:
            summary += f" ({stalled_extra} stalled)"
        r = _row(
            "More live jobs",
            summary[:240],
            action={"type": "focus_live_job", "index": 2},
        )
        if r:
            rows.append(r)
    ready = live_ops.get("queue_ready_count")
    if isinstance(ready, int) and ready > 0:
        r = _row("Scheduler queue", f"{ready} ready · next: {live_ops.get('queue_next_preview') or 'see Jobs tab'}")
        if r:
            rows.append(r)
    preview = live_ops.get("bob_catchup_preview") or []
    if isinstance(preview, list) and preview:
        joined = " · ".join(str(x).strip() for x in preview[:3] if str(x).strip())
        r = _row("Bob catch-up", joined[:240] if joined else None)
        if r:
            rows.append(r)
    cap = 18
    omitted = max(0, len(rows) - cap)
    if omitted > 0:
        kept = rows[: cap - 1]
        kept.append({"label": "More fields", "value": f"+{omitted} in Jobs ops detail below"})
        return kept, omitted
    return rows[:cap], 0


def _live_activity_preview(live_ops: dict) -> str | None:
    """One plain-English line for ops panels (first live screen job + last log line)."""
    for row in live_ops.get("running_jobs") or []:
        if not row.get("live_screen"):
            continue
        parts: list[str] = []
        plain = row.get("plain_now")
        if isinstance(plain, str) and plain.strip():
            parts.append(_redact_line(plain.strip())[:160])
        tail = row.get("log_tail") or []
        if tail:
            last = tail[-1]
            if isinstance(last, str) and last.strip():
                allowed = _allowlisted_line(last) or _redact_line(last)
                if allowed and (not parts or allowed not in parts[0]):
                    parts.append(allowed[:160])
        if parts:
            return " · ".join(parts)[:240]
    now = live_ops.get("now_line")
    return now if isinstance(now, str) and now.strip() else None


def enrich_live_ops_bundle(live_ops: dict, root: Path | None = None) -> dict:
    live_ops = enrich_running_jobs_display(live_ops)
    age = _ops_snapshot_age_seconds(live_ops)
    if age is not None:
        live_ops = {**live_ops, "ops_snapshot_age_seconds": age}
    else:
        live_ops = {**live_ops, "ops_snapshot_freshness_unknown": True}
    preview_line = _live_activity_preview(live_ops)
    if preview_line:
        live_ops = {**live_ops, "live_activity_preview": preview_line}
    if root is not None:
        live_ops = attach_scheduler_queue(live_ops, root)
        preview = _bob_catchup_preview(root)
        if preview:
            live_ops["bob_catchup_preview"] = preview
        si_line = _self_improve_plain_line(root)
        if si_line:
            live_ops["self_improve_plain"] = si_line
        si_age = _self_improve_log_age_seconds(root)
        if si_age is not None:
            live_ops["self_improve_log_stale_24h"] = si_age > SELF_IMPROVE_LOG_STALE_SECONDS
    plain_rows, plain_omitted = _build_dashboard_plain(live_ops)
    live_ops = {
        **live_ops,
        "dashboard_plain": plain_rows,
        "dashboard_plain_omitted": plain_omitted,
    }
    return live_ops


def public_live_ops(live_ops: dict) -> dict:
    """Strip local paths and ids for GitHub Pages payload."""

    def _public_screen_count(source: dict) -> int:
        screens = source.get("service_screens")
        if isinstance(screens, (list, tuple, set)):
            base = len(screens)
        else:
            base = 0
        raw = source.get("service_screen_count")
        if isinstance(raw, bool):
            return min(base, 64)
        if isinstance(raw, int):
            return min(max(0, raw), 64)
        if isinstance(raw, float) and raw.is_integer():
            return min(max(0, int(raw)), 64)
        return min(base, 64)

    jobs = []
    for row in live_ops.get("running_jobs") or []:
        tail = []
        for line in row.get("log_tail") or []:
            allowed = _allowlisted_line(line) if isinstance(line, str) else None
            if allowed:
                tail.append(allowed)
        plain = row.get("plain_now")
        if isinstance(plain, str):
            plain = _allowlisted_line(plain) or _redact_line(plain)[:160]
        commit = row.get("last_commit") or {}
        message = commit.get("message")
        if isinstance(message, str):
            message = _allowlisted_line(message) or _redact_line(message)[:120]
            commit = {"sha": commit.get("sha"), "message": message}
        events = _structured_events(row, tail[-3:], commit, plain)
        jobs.append({
            "engine": row.get("engine") or "worker",
            "state": row.get("state"),
            "stall_state": row.get("stall_state"),
            "display_state": row.get("display_state"),
            "stall_plain": row.get("stall_plain"),
            "started_at": row.get("started_at"),
            "elapsed_seconds": row.get("elapsed_seconds"),
            "plain_now": plain,
            "log_tail": tail[-3:],
            "events": events,
            "last_commit": commit,
            "round": row.get("round"),
            "live_screen": row.get("live_screen"),
        })
    screens = live_ops.get("service_screens") or []
    ready = live_ops.get("queue_ready_count")
    if isinstance(ready, bool):
        ready = None
    elif isinstance(ready, (int, float)):
        ready = min(max(0, int(ready)), 999)
    else:
        ready = None
    queued = []
    for row in live_ops.get("queued_jobs") or []:
        if not isinstance(row, dict):
            continue
        goal = row.get("goal")
        if isinstance(goal, str):
            goal = _allowlisted_line(goal) or _redact_line(goal)[:160]
        else:
            goal = ""
        if goal:
            qid = row.get("id") or row.get("file")
            entry = {"goal": goal, "status": "READY"}
            if isinstance(qid, str) and qid and "/" not in qid and "\\" not in qid:
                entry["id"] = qid[:120]
            pos = row.get("position")
            if isinstance(pos, int) and 1 <= pos <= 999:
                entry["position"] = pos
            queued.append(entry)
        if len(queued) >= 6:
            break
    preview = []
    for line in live_ops.get("bob_catchup_preview") or []:
        if isinstance(line, str):
            allowed = _allowlisted_line(line) or _redact_line(line)
            if allowed:
                preview.append(allowed[:200])
        if len(preview) >= 3:
            break
    next_preview = live_ops.get("queue_next_preview")
    if isinstance(next_preview, str) and next_preview:
        next_preview = _allowlisted_line(next_preview) or _redact_line(next_preview)[:120]
    else:
        next_preview = None
    tracked = live_ops.get("tracked_job_count")
    if isinstance(tracked, bool):
        tracked = None
    elif isinstance(tracked, (int, float)):
        tracked = min(max(0, int(tracked)), 99)
    else:
        tracked = None
    return {
        "generated_at": live_ops.get("generated_at"),
        "scores_measured_at": live_ops.get("scores_measured_at"),
        "bob_catchup_preview": preview,
        "now_line": live_ops.get("now_line"),
        "live_activity_preview": live_ops.get("live_activity_preview"),
        "dashboard_plain": live_ops.get("dashboard_plain") or [],
        "dashboard_plain_omitted": live_ops.get("dashboard_plain_omitted") or 0,
        "webchat_round": live_ops.get("webchat_round"),
        "dashboard_freshness_seconds": live_ops.get("dashboard_freshness_seconds"),
        "ops_snapshot_age_seconds": live_ops.get("ops_snapshot_age_seconds"),
        "ops_snapshot_freshness_unknown": bool(live_ops.get("ops_snapshot_freshness_unknown")),
        "scores": live_ops.get("scores"),
        "scores_weakest": live_ops.get("scores_weakest"),
        "minimax_spend": live_ops.get("minimax_spend"),
        "roles": live_ops.get("roles"),
        "service_screen_count": _public_screen_count(live_ops),
        "queue_ready_count": ready,
        "queue_next_preview": next_preview,
        "tracked_job_count": tracked,
        "queued_jobs": queued,
        "running_jobs": jobs,
    }
