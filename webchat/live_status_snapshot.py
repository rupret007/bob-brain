"""Read-only live mini status for every Web Bob provider prompt (shared across lanes)."""
from __future__ import annotations

import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

LANE_NAMES = ("codex", "claude", "cursor", "gemini", "minimax")
SERVICE_INTERVALS = {"job-runner": 60, "reviewer": 300, "dashboard-updater": 300, "watchdog": 180}
_SCREEN_RE = re.compile(r"(?m)^\s*(\d+)\.([\w.-]+)\s*\((?:Detached|Attached)\)")
_HOME = re.compile(r"/Users/[^\s\"']+")


def _stamp(now: float | None = None) -> str:
    ts = now if now is not None else time.time()
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _read_json(path: Path, default=None):
    if not path.is_file():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(errors="replace"))
    except (OSError, json.JSONDecodeError, ValueError):
        return default if default is not None else {}


def _read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows: list[dict] = []
    try:
        text = path.read_text(errors="replace")
    except OSError:
        return []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _screen_sessions(root: Path) -> dict[str, str]:
    try:
        result = subprocess.run(
            ["/usr/bin/screen", "-ls"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        text = (result.stdout or "") + (result.stderr or "")
    except (OSError, subprocess.TimeoutExpired):
        return {}
    if "Sockets in" not in text and "No Sockets found" not in text:
        return {}
    return {m.group(2): m.group(1) + "." + m.group(2) for m in _SCREEN_RE.finditer(text)}


def _latest_jobs(root: Path) -> dict[str, dict]:
    merged: dict[str, dict] = {}
    for relative in ("conductor/jobs.jsonl", "conductor/queue.jsonl"):
        for row in _read_jsonl(root / relative):
            job_id = row.get("job_id") or row.get("id")
            if not job_id:
                continue
            merged[str(job_id)] = {**merged.get(str(job_id), {}), **row, "job_id": str(job_id), "_journal": relative}
    return merged


def _job_bucket(record: dict) -> str:
    state = (record.get("state") or "unknown").lower()
    outcome = (record.get("outcome") or "").lower()
    if state == "queued":
        return "queued"
    if state in ("launched", "running", "claimed"):
        return "claimed"
    if state == "harvested":
        if outcome == "blocked" or record.get("recovery"):
            return "failed"
        return "done"
    if state == "blocked" or outcome == "blocked":
        return "failed"
    return state


def _job_worker(record: dict, sessions: set[str]) -> str | None:
    for key in ("engine", "lane", "model", "worker"):
        value = record.get(key)
        if value:
            return str(value)
    job_id = record.get("job_id")
    if job_id and job_id in sessions:
        return f"screen:{job_id}"
    return None


def _queue_jobs(jobs_map: dict[str, dict], sessions: set[str], *, limit: int = 24) -> dict:
    buckets: dict[str, list[dict]] = {"queued": [], "claimed": [], "done": [], "failed": []}
    rows = sorted(jobs_map.values(), key=lambda r: float(r.get("timestamp") or r.get("launched_at") or 0), reverse=True)
    for record in rows:
        bucket = _job_bucket(record)
        if bucket not in buckets:
            bucket = "failed" if bucket not in ("queued", "claimed", "done") else bucket
        entry = {
            "job_id": record.get("job_id"),
            "state": record.get("state"),
            "bucket": bucket,
            "worker": _job_worker(record, sessions),
            "recovery": (record.get("recovery") or "")[:160] or None,
            "journal": record.get("_journal"),
        }
        buckets[bucket].append(entry)
    for key in buckets:
        buckets[key] = buckets[key][:limit]
    return buckets


def _screen_lanes(sessions: dict[str, str], jobs_map: dict[str, dict], live_ops: dict) -> list[dict]:
    live_by_job = {row.get("job_id"): row for row in (live_ops.get("running_jobs") or []) if row.get("job_id")}
    lanes: list[dict] = []
    for name in sorted(sessions):
        row: dict = {"screen": name, "pid_session": sessions[name]}
        if name.startswith("svc-"):
            row["role"] = "service"
            row["service"] = name.removeprefix("svc-")
        elif name in jobs_map:
            record = jobs_map[name]
            row["role"] = "job"
            row["job_id"] = name
            row["worker"] = _job_worker(record, set(sessions))
            row["state"] = record.get("state")
        else:
            row["role"] = "other"
        live = live_by_job.get(name)
        if live:
            row["doing"] = live.get("plain_now") or (live.get("log_tail") or [None])[-1]
            row["stall_state"] = live.get("stall_state")
        elif row.get("role") == "service":
            row["doing"] = f"service screen {name} is attached"
        elif row.get("role") == "job":
            row["doing"] = f"job screen {name} ({row.get('state', 'unknown')})"
        else:
            row["doing"] = "screen session running (no job journal match)"
        lanes.append(row)
    return lanes[:32]


def _service_health(root: Path, sessions: set[str], now: float) -> dict:
    heartbeats = root / "conductor/heartbeats"
    services: dict[str, dict] = {}
    for name, interval in SERVICE_INTERVALS.items():
        path = heartbeats / name
        age = None
        if path.is_file():
            try:
                age = round(max(0, now - path.stat().st_mtime), 1)
            except OSError:
                age = None
        screen_name = "svc-" + name
        healthy = age is not None and age <= 3 * interval and screen_name in sessions
        services[name] = {
            "heartbeat_age_seconds": age,
            "screen_running": screen_name in sessions,
            "healthy": healthy,
            "interval_seconds": interval,
        }
    return services


def _disk_usage(root: Path) -> dict:
    try:
        result = subprocess.run(
            ["/bin/df", "-k", str(root)],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return {"available": False}
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        if len(lines) < 2:
            return {"available": False}
        parts = lines[-1].split()
        if len(parts) < 5:
            return {"available": False}
        total_kb, used_kb, avail_kb = int(parts[1]), int(parts[2]), int(parts[3])
        mount = parts[-1]
        pct = round(100 * used_kb / total_kb) if total_kb else None
        return {
            "available": True,
            "mount": mount,
            "total_gb": round(total_kb / 1_048_576, 2),
            "used_gb": round(used_kb / 1_048_576, 2),
            "avail_gb": round(avail_kb / 1_048_576, 2),
            "used_percent": pct,
        }
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return {"available": False}


def _redact_line(line: str) -> str:
    line = _HOME.sub("[mini]", line)
    return line.strip()[:240]


def _tail_file(path: Path, count: int = 3) -> list[str]:
    if not path.is_file():
        return []
    try:
        lines = [ln.strip() for ln in path.read_text(errors="replace").splitlines() if ln.strip()]
    except OSError:
        return []
    return [_redact_line(ln) for ln in lines[-count:]]


def _lane_log_tails(root: Path, lanes: dict) -> dict[str, list[str]]:
    tails: dict[str, list[str]] = {}
    for lane in LANE_NAMES:
        lane_info = lanes.get(lane) or {}
        busy = lane_info.get("state") == "busy"
        candidates = [
            root / "conductor/status" / ("notes-" + lane + ".md"),
            root / "logs" / (lane + ".log"),
            root / "logs" / ("lane-" + lane + ".log"),
        ]
        collected: list[str] = []
        for path in candidates:
            collected.extend(_tail_file(path, 3))
        if busy or collected:
            tails[lane] = collected[-3:]
    for service in SERVICE_INTERVALS:
        lines = _tail_file(root / "logs" / (service + ".log"), 2)
        if lines:
            tails["svc-" + service] = lines
    return tails


def _plain_summary(
    *,
    screens: list[dict],
    queue: dict,
    services: dict,
    disk: dict,
    now_line: str | None,
) -> str:
    healthy = sum(1 for row in services.values() if row.get("healthy"))
    claimed = len(queue.get("claimed") or [])
    queued = len(queue.get("queued") or [])
    parts = [
        f"Services {healthy}/{len(services)} healthy; {claimed} claimed job(s), {queued} queued.",
        f"{len(screens)} screen session(s) on the mini.",
    ]
    if now_line:
        parts.append("NOW: " + now_line[:200])
    if disk.get("available"):
        parts.append(f"Disk {disk.get('avail_gb')} GB free on {disk.get('mount')} ({disk.get('used_percent')}% used).")
    return " ".join(parts)


def build_live_status_snapshot(root: Path, *, now: float | None = None) -> dict:
    """Single shared live status blob for gemini, minimax, codex, claude, and cursor prompts."""
    root = Path(root)
    now = time.time() if now is None else now
    sessions = _screen_sessions(root)
    session_names = set(sessions)
    jobs_map = _latest_jobs(root)
    lanes = _read_json(root / "conductor/lanes.json", {})
    live_ops: dict = {}
    live_ops_meta: dict = {}
    try:
        from ops_panel import load_live_ops

        loaded = load_live_ops(root, max_age=300.0)
        live_ops = loaded.get("live_ops") or {}
        live_ops_meta = loaded.get("meta") or {}
    except Exception:
        live_ops_meta = {"source": "unavailable", "stale": True}

    screens = _screen_lanes(sessions, jobs_map, live_ops)
    queue = _queue_jobs(jobs_map, session_names)
    services = _service_health(root, session_names, now)
    disk = _disk_usage(root)
    log_tails = _lane_log_tails(root, lanes)
    now_line = live_ops.get("now_line")
    if not now_line:
        now_path = root / "conductor/state/NOW.md"
        for line in _tail_file(now_path, 5):
            if line:
                now_line = line
                break

    return {
        "captured_at": _stamp(now),
        "live_ops_source": live_ops_meta.get("source"),
        "live_ops_stale": bool(live_ops_meta.get("stale")),
        "now_line": now_line,
        "plain_summary": _plain_summary(
            screens=screens, queue=queue, services=services, disk=disk, now_line=now_line
        ),
        "screen_lanes": screens,
        "queue_jobs": queue,
        "lane_locks": {
            lane: {
                "state": (lanes.get(lane) or {}).get("state"),
                "detail": (lanes.get(lane) or {}).get("detail"),
            }
            for lane in LANE_NAMES
        },
        "lane_log_tails": log_tails,
        "service_health": services,
        "disk": disk,
        "instruction": (
            "When Jeff asks what workers, lanes, jobs, or services are doing, answer from this "
            "snapshot only—quote job_id, screen name, worker, log tail lines, health, and disk numbers here. "
            "Do not say you cannot see workers if this block lists them."
        ),
    }
