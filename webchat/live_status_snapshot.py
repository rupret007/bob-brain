"""Read-only live mini status for every Web Bob provider prompt (shared across lanes)."""
from __future__ import annotations

import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

LANE_NAMES = ("codex", "claude", "cursor", "gemini", "minimax", "mini")
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
    for relative in ("conductor/jobs.jsonl", "conductor/queue.jsonl", "conductor/state/queue.jsonl"):
        for row in _read_jsonl(root / relative):
            job_id = row.get("job_id") or row.get("id")
            if not job_id:
                continue
            merged[str(job_id)] = {**merged.get(str(job_id), {}), **row, "job_id": str(job_id), "_journal": relative}
    return merged


def provider_health(root: Path, now: float | None = None) -> dict:
    """Generation health, distinct from scheduler locks and configuration probes."""
    now = time.time() if now is None else now
    entries = _read_json(root / "conductor/webchat/sessions/provider-health.json", {})
    events = {}
    try:
        with (root / "logs/webchat-failover.log").open("rb") as handle:
            handle.seek(0, 2)
            size = handle.tell()
            handle.seek(max(0, size - 65536))
            if size > 65536:
                handle.readline()
            lines = handle.read().decode("utf-8", "replace").splitlines()
        for line in lines:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if (event.get("context", "production") == "production" and not event.get("injected")
                    and event.get("event") in ("success", "failure")):
                events[event.get("provider")] = event
    except OSError:
        pass
    result = {}
    for name in ("codex", "claude", "cursor", "gemini", "minimax"):
        row = entries.get(name) or {}
        event = events.get(name) or {}
        checked = row.get("checked_at") or 0
        success, reason, retry = row.get("last_success"), row.get("reason"), row.get("retry_at") or 0
        if event.get("timestamp", 0) >= checked:
            checked = event.get("timestamp", checked)
            if event.get("event") == "success":
                success, reason, retry = checked, None, 0
            elif event.get("event") == "failure":
                reason, retry = event.get("reason"), event.get("retry_at", 0)
        state = "cooldown" if retry > now else "recovery_due" if reason else "ready" if success else "unchecked"
        result[name] = dict(state=state, reason=reason, retry_at=retry, checked_at=checked,
                            last_success=success, probe=row.get("probe"), probed_at=row.get("probed_at"),
                            last_event=event.get("event"), last_event_at=event.get("timestamp"))
    return result


def _job_bucket(record: dict) -> str:
    state = (record.get("status") or record.get("state") or "unknown").lower()
    outcome = (record.get("outcome") or "").lower()
    if state == "queued":
        return "queued"
    if state in ("launched", "running", "claimed"):
        return "claimed"
    if state == "succeeded":
        return "done"
    if state == "harvested":
        if outcome == "blocked":
            return "failed"
        return "done"
    if state in ("blocked", "failed") or outcome == "blocked":
        return "failed"
    return state


def _job_worker(record: dict, sessions: set[str]) -> str | None:
    for key in ("worker", "engine", "lane", "model", "requested_worker"):
        value = record.get(key)
        if value:
            return str(value)
    job_id = record.get("job_id")
    if job_id and job_id in sessions:
        return f"screen:{job_id}"
    return None


def _queue_jobs(jobs_map: dict[str, dict], sessions: set[str], *, limit: int = 24) -> dict:
    buckets: dict[str, list[dict]] = {"queued": [], "claimed": [], "done": [], "failed": []}
    rows = sorted(jobs_map.values(), key=lambda r: float(r.get("updated_at") or r.get("timestamp") or r.get("launched_at") or 0), reverse=True)
    for record in rows:
        bucket = _job_bucket(record)
        if bucket not in buckets:
            bucket = "failed" if bucket not in ("queued", "claimed", "done") else bucket
        entry = {
            "job_id": record.get("job_id"),
            "state": record.get("status") or record.get("state"),
            "bucket": bucket,
            "worker": _job_worker(record, sessions),
            "recovery": (record.get("recovery") or "")[:160] or None,
            "journal": record.get("_journal"),
            "updated_at": record.get("updated_at") or record.get("timestamp"),
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
            row["doing"] = f"service screen {name} is present"
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
    queue = _queue_jobs(jobs_map, session_names, limit=len(jobs_map))
    queue_counts = {key: len(rows) for key, rows in queue.items()}
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
    # Old drill fixtures have leaked into the dashboard/NOW ledger. A fixture
    # reference is not evidence of a currently running screen or task.
    if now_line and re.search(r"\b(?:handback|ready) drill\b|\bdrill-[\w-]+", now_line, re.I):
        now_line = None

    return {
        "captured_at": _stamp(now),
        "live_ops_source": live_ops_meta.get("source"),
        "live_ops_stale": bool(live_ops_meta.get("stale")),
        "now_line": now_line,
        "plain_summary": _plain_summary(
            screens=screens, queue=queue, services=services, disk=disk, now_line=now_line
        ),
        "screen_lanes": screens,
        "queue_counts": queue_counts,
        "queue_jobs": {key: rows[:24] for key, rows in queue.items()},
        "provider_health": provider_health(root, now),
        "provider_health_sources": ["conductor/webchat/sessions/provider-health.json", "logs/webchat-failover.log"],
        "lane_locks": {
            lane: {
                "state": (lanes.get(lane) or {}).get("state"),
                "detail": (lanes.get(lane) or {}).get("detail"),
                "checked_at": (lanes.get(lane) or {}).get("checked_at"),
                "active_jobs": [row["job_id"] for row in queue["claimed"] if row["worker"] == lane],
            }
            for lane in LANE_NAMES
        },
        "lane_log_tails": log_tails,
        "service_health": services,
        "disk": disk,
        "instruction": (
            "When Jeff asks what workers, lanes, jobs, or services are doing, answer from this "
            "snapshot only—quote job_id, screen name, worker, log tail lines, health, and disk numbers here. "
            "Queue counts include all jobs; lists show recent examples. Done/failed jobs are history, not active work. "
            "Lane lock reports are cached at checked_at; current queue claims and screen presence take precedence. "
            "Quote at least one full listed job_id; if no job is claimed, label finished jobs as history. "
            "active_jobs only covers journaled queue claims. Background work may hold a busy lane without a claim; "
            "an empty active_jobs list does not prove an idle or stale lock. Report unidentified work as unknown, "
            "and do not infer that all workers are idle from an empty queue. "
            "Do not say you cannot see workers if this block lists them."
            " Chat provider health comes only from provider_health, not old messages or lane locks. "
            "A successful probe checks configuration; last_success proves generation. "
            "A past failure followed by success is recovered, not a current outage."
        ),
    }


def encode_snapshot(snapshot: dict, max_chars: int) -> tuple[str, bool]:
    """Bound prompt size without cutting JSON or losing health/disk at the tail."""
    data = json.loads(json.dumps(snapshot))
    clipped = False
    while True:
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        if len(payload) <= max_chars:
            return payload, clipped
        # Trim history and logs before current workers. Counts retain totals.
        lists = [data["queue_jobs"][key] for key in ("failed", "done")]
        lists += list(data["lane_log_tails"].values())
        lists += [data["queue_jobs"][key] for key in ("queued", "claimed")]
        lists += [data["screen_lanes"]]
        target = next((rows for rows in lists if rows), None)
        if target is None:
            raise ValueError("Live status snapshot budget cannot fit required fields")
        target.pop()
        data["lists_trimmed"] = clipped = True
