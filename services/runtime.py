#!/usr/bin/env python3
"""Independent service cycles and a bounded, shared screen restart policy."""
from __future__ import annotations

import base64
import fcntl
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

from command import run
from state import CONDUCTOR, ROOT, alert, append_event, atomic_write, job_event, jobs, journal_rows, lock, log, read_json, stamp, write_json

INTERVALS = {"job-runner": 60, "reviewer": 300, "dashboard-updater": 300, "watchdog": 180}
SERVICES = CONDUCTOR / "services"
HEARTBEATS = CONDUCTOR / "heartbeats"


def screen_sessions():
    result = run(["screen", "-ls"], capture_output=True, text=True, timeout=15)
    text = result.stdout + result.stderr
    if not ("Sockets in" in text or "No Sockets found" in text):
        raise RuntimeError("screen inventory unavailable; refusing to guess")
    return {m.group(2): m.group(1) + "." + m.group(2)
            for m in re.finditer(r"(?m)^\s*(\d+)\.([\w.-]+)\s*\((?:Detached|Attached)\)", text)}


def health(now=None, sessions=None):
    now = time.time() if now is None else now
    sessions = screen_sessions() if sessions is None else sessions
    result = {}
    for name, interval in INTERVALS.items():
        path = HEARTBEATS / name
        age = max(0, now - path.stat().st_mtime) if path.exists() else None
        result[name] = {"interval_seconds": interval, "heartbeat_age_seconds": round(age, 1) if age is not None else None,
                        "screen_running": "svc-" + name in sessions,
                        "healthy": age is not None and age <= 3 * interval and "svc-" + name in sessions}
    return result


def service_lock_held(name):
    try:
        with lock("service-" + name, blocking=False):
            return False
    except BlockingIOError:
        return True


def stop_service_process(name):
    """`screen -X quit` orphans the login/bash loop on macOS, leaving its lifetime lock held.

    The loop exec'd from lock-service keeps the pid recorded in locks/<name>.pid; stop that
    process (its trap also stops the running cycle) so a restart can take the lock.
    """
    try:
        pid = int((CONDUCTOR / "locks" / (name + ".pid")).read_text().strip())
        command = run(["ps", "-o", "command=", "-p", str(pid)], capture_output=True, text=True, timeout=15).stdout
    except (OSError, ValueError):
        return
    if (name + ".sh") not in command:
        return
    for sig, wait in ((signal.SIGTERM, 25), (signal.SIGKILL, 10)):
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            return
        for _ in range(wait):
            if not service_lock_held(name):
                return
            time.sleep(0.2)


def start_screen(name):
    """screen can return zero before its child exec fails on macOS. Verify it."""
    config = CONDUCTOR / "screenrc" / name
    screen_log = ROOT / "logs" / (name + "-screen.log")
    atomic_write(config, "logfile " + json.dumps(str(screen_log)) + "\nlogfile flush 1\nlog on\n")
    result = run(["screen", "-c", str(config), "-L", "-dmS", "svc-" + name,
                             "/bin/bash", str(SERVICES / (name + ".sh"))], capture_output=True, timeout=15, detach=True)
    if result.returncode:
        return False
    for _ in range(30):
        time.sleep(0.2)
        if "svc-" + name in screen_sessions() and service_lock_held(name):
            return True
    return False


def ensure_services(check_stale=False, self_name=None):
    """All entrypoints share this lock and rate cap, including both launchd jobs."""
    with lock("supervisor", blocking=False):
        path = CONDUCTOR / "supervisor.json"
        state = read_json(path, {})
        sessions = screen_sessions()
        now = time.time()
        failed = []
        for name, interval in INTERVALS.items():
            if name == self_name:
                continue
            session = "svc-" + name
            entry = state.setdefault(name, {})
            recent = [t for t in entry.get("restarts", []) if t > now - 3600]
            entry["restarts"] = recent
            heartbeat = HEARTBEATS / name
            last_good = heartbeat.stat().st_mtime if heartbeat.exists() else 0
            last_observed = max(last_good, entry.get("started_at", 0))
            missing = session not in sessions
            stale = now - last_observed > interval * 3
            if not missing and not (check_stale and stale):
                continue
            initial = not entry.get("ever_started") and missing
            if not initial and len(recent) >= 3:
                alert("restart-" + name, name + " reached 3 restarts/hour; automatic restarts paused until the rolling window clears")
                log(name + " restart capped at 3/hour")
                continue
            if not initial:
                recent.append(now)
                entry["restarts_total"] = entry.get("restarts_total", 0) + 1
            entry.update(ever_started=True, started_at=now, restarts=recent,
                         reason="missing screen" if missing else "stale heartbeat")
            # Save BEFORE attempting restart; failures and supervisor crashes count.
            write_json(path, state)
            if not missing:
                stopped = run(["screen", "-S", sessions[session], "-X", "quit"],
                                         capture_output=True, timeout=15)
                if stopped.returncode:
                    log(name + " could not stop stale screen")
                    continue
            if not initial:
                stop_service_process(name)
            started = start_screen(name)
            entry["last_start_ok"] = started
            if not started:
                failed.append(name)
            append_event("service-restarts", {"service": name, "initial": initial, "ok": started,
                                               "reason": entry["reason"]})
            log(("started " if initial else "restarted ") + session + " verified=" + str(started))
            if len(recent) >= 3:
                alert("restart-" + name, name + " reached 3 restarts/hour; automatic restarts paused until the rolling window clears")
            elif started:
                alert("restart-" + name)
        write_json(path, state)
        if failed:
            alert("service-start", "screen startup failed for " + ", ".join(failed) + "; inspect logs/*-screen.log and run start-all.sh from Terminal")
        elif all("svc-" + n in screen_sessions() for n in INTERVALS if n != self_name):
            alert("service-start")


def takeover():
    sessions = screen_sessions()
    if not all("svc-" + name in sessions for name in INTERVALS):
        log("takeover pending: waiting for all four service screens")
        return
    if "mini-conductor" in sessions:
        # Old run-conductor left this PID lock while its pass was active.
        old_lock = Path("/tmp/mini-conductor.lock")
        if old_lock.exists():
            try:
                os.kill(int(old_lock.read_text().strip()), 0)
                log("old conductor pass still active; takeover will retry")
                return
            except (ProcessLookupError, ValueError):
                pass
            except PermissionError:
                log("cannot verify old pass PID; leaving it until the next check")
                return
        stopped = run(["screen", "-S", sessions["mini-conductor"], "-X", "quit"], capture_output=True, timeout=15)
        if stopped.returncode:
            raise RuntimeError("old mini-conductor screen could not be stopped")
        log("retired mini-conductor screen; job-runner owns ticks and the two-hour pass")
    # Old installed timers would otherwise duplicate the schedule. The new wrappers
    # also use locks, so an unloaded/absent legacy launchd job is harmless.
    marker = CONDUCTOR / "takeover.json"
    if not marker.exists():
        for label in ("com.jeff.mini-conductor", "com.jeff.mini-tick"):
            run(["launchctl", "bootout", "gui/%s/%s" % (os.getuid(), label)],
                           capture_output=True, timeout=10)
        write_json(marker, {"at": stamp(), "legacy_screen_retired": True})


def schedule_pass():
    if (CONDUCTOR / "MAINTENANCE").exists():
        return
    with lock("pass-schedule"):
        path = CONDUCTOR / "pass-schedule.json"
        state = read_json(path, {})
        if not state:
            old_log = ROOT / "logs/conductor.log"
            baseline = old_log.stat().st_mtime if old_log.exists() else 0
            state = {"next_due": baseline + 7200, "interval_seconds": 7200}
            write_json(path, state)
        if time.time() < state["next_due"]:
            return
        sessions = screen_sessions()
        if "svc-conductor-pass" in sessions:
            return
        # No due-time advance until run-conductor actually claims the pass lock.
        result = run(["screen", "-dmS", "svc-conductor-pass", "/bin/bash", str(CONDUCTOR / "run-conductor.sh")],
                                capture_output=True, timeout=15, detach=True)
        if result.returncode:
            raise RuntimeError("could not schedule two-hour conductor pass")
        log("scheduled two-hour run-conductor.sh pass")


def runner_cycle():
    from jobs import tick
    from scheduler import paused
    tick()
    if not paused():
        schedule_pass()
    status_report()


def reviewer_cycle():
    from api import critique
    candidates = [r for r in jobs().values() if r["state"] == "harvested" and r.get("result_path") and not r.get("queue_id")]
    # Newest unreviewed result first on migration; one result per cycle bounds cost/time.
    candidates.sort(key=lambda r: (r.get("review_attempt_at", 0), -r.get("launched_at", 0)))
    for record in candidates:
        result = Path(record["result_path"])
        if not result.exists():
            continue
        digest = hashlib.sha256(result.read_bytes()).hexdigest()
        if record.get("reviewed_sha256") == digest:
            continue
        prompt = "Harvested result: " + result.name + "\n" + result.read_text(errors="replace")[:18000]
        outcomes = {}
        for model in ("claude", "cursor", "minimax", "gemini"):
            outcomes[model] = critique(model, prompt, result.with_name(result.name + "." + model + ".md"))
        job_event(record["job_id"], review_models=outcomes,
                  reviewed_sha256=digest if all(outcomes.values()) else None, review_attempt_at=time.time())
        log("review cycle " + record["job_id"] + " " + json.dumps(outcomes))
        return
    log("review cycle: no pending harvested result")


def snapshot():
    from live_dashboard import build_live_ops
    from scheduler import lane_board

    records = list(jobs().values())
    runs = [r for r in journal_rows("model-runs") if r.get("timestamp", 0) > time.time() - 86400]
    supervisor = read_json(CONDUCTOR / "supervisor.json", {})
    sessions = screen_sessions()
    pending = [r for r in records if r["state"] != "harvested"]
    spend = {lane: __import__("budget").totals(lane) for lane in __import__("lanes").LANES}
    lanes = read_json(CONDUCTOR / "lanes.json", {})
    live_ops = build_live_ops(sessions=sessions, jobs_map=jobs(), lanes=lanes, spend=spend)
    try:
        ledger_dir = str(CONDUCTOR / "state")
        if ledger_dir not in sys.path:
            sys.path.insert(0, ledger_dir)
        import ledger as state_ledger

        head = None
        result = run(["git", "-C", str(CONDUCTOR), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            head = result.stdout.strip()
        state_ledger.sync_from_live_ops(ROOT, live_ops, head_sha=head, webchat_round=live_ops.get("webchat_round"))
        refreshed = state_ledger.read_now_line(ROOT)
        if refreshed:
            live_ops["now_line"] = refreshed
    except Exception:
        pass
    return {"generated_at": stamp(), "live_ops": live_ops, "lane_board": lane_board(), "services": health(sessions=sessions),
            "jobs": {"total": len(records), "launched": sum(r["state"] == "launched" for r in records),
                     "running": sum(r["state"] == "running" for r in records),
                     "harvested": sum(r["state"] == "harvested" for r in records),
                     "blocked_closeouts": sum(r["state"] == "blocked" for r in records),
                     "queued": sum(r["state"] == "queued" for r in records),
                     "unharvested": [{"job_id": r["job_id"], "state": r["state"], "recovery": r.get("recovery"),
                                      "screen_running": r["job_id"] in sessions} for r in pending],
                     "orphaned": sum(r["job_id"] not in sessions for r in pending)},
            "restarts_last_hour": {name: sum(t > time.time() - 3600 for t in e.get("restarts", [])) for name, e in supervisor.items()},
            "restarts_total": {name: e.get("restarts_total", 0) for name, e in supervisor.items()},
            "models_succeeded_last_24h": sorted(set(r["model"] for r in runs if r.get("ok"))),
            "models_attempted_last_24h": sorted(set(r["model"] for r in runs)),
            "alerts": read_json(CONDUCTOR / "alerts.json", {}),
            "lanes": lanes,
            "spend": spend}


def github_token():
    if os.environ.get("BOB_DASHBOARD_TOKEN"):
        return os.environ["BOB_DASHBOARD_TOKEN"]
    result = run(["gh", "auth", "token", "--hostname", "github.com"], capture_output=True, text=True, timeout=10)
    if result.returncode or not result.stdout.strip():
        raise RuntimeError("GitHub push credentials unavailable")
    return result.stdout.strip()


def push_dashboard(data):
    from api import http_json
    from live_dashboard import public_live_ops
    token = github_token()
    base = "https://api.github.com/repos/rupret007/bob-ops-dashboard"
    headers = {"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28"}
    # This is a data-only Contents commit, never a merge or a force-push.
    repo = http_json(base, headers=headers)
    if not repo.get("permissions", {}).get("push"):
        raise RuntimeError("GitHub token has no dashboard push permission")
    url = base + "/contents/agents-status.json"
    from urllib.parse import quote
    old = http_json(url + "?ref=" + quote(os.environ["BOB_DASHBOARD_DRAFT_BRANCH"], safe=""), headers=headers, allowed=(200, 404))
    models = data["models_succeeded_last_24h"]
    sessions = screen_sessions()
    agents = []
    for engine, title in (("codex", "Codex"), ("claude", "Claude"), ("cursor", "Cursor"), ("gemini", "Gemini"), ("minimax", "MiniMax")):
        active = any(r["state"] == "running" and r.get("engine") == engine and r["job_id"] in sessions for r in jobs().values())
        used = any(engine in name.lower() for name in models)
        agents.append({"id": engine, "name": title, "state": data.get("lanes", {}).get(engine, {}).get("state", "running" if active else "idle" if used else "unknown"),
                       "detail": "Active local job" if active else "Completed local work in last 24h" if used else "No confirmed run in last 24h",
                       "checked_at": data["generated_at"]})
    # Public payload intentionally excludes job names, private PRs, local paths,
    # prompts, logs, status prose, alerts and credentials.
    public = {"source": "mini-conductor-services", "checked_at": data["generated_at"], "agents": agents,
              "live_ops": public_live_ops(data.get("live_ops") or {}),
              "conductor": {"services": data["services"], "models_succeeded_last_24h": models,
                            "jobs_running": data["jobs"]["running"], "jobs_unharvested": len(data["jobs"]["unharvested"]),
                            "restarts_last_hour": data["restarts_last_hour"]}}
    payload = {"message": "chore: refresh Mini conductor status data", "branch": os.environ["BOB_DASHBOARD_DRAFT_BRANCH"],
               "content": base64.b64encode((json.dumps(public, indent=2) + "\n").encode()).decode()}
    if old.get("sha"):
        payload["sha"] = old["sha"]
    pushed = http_json(url, "PUT", payload, headers)
    return pushed.get("commit", {}).get("sha")


def dashboard_cycle():
    data = snapshot()
    # Local output is committed before any remote operation; remote failure cannot
    # prevent this cycle from completing or its heartbeat from advancing.
    write_json(CONDUCTOR / "dashboard.json", data)
    try:
        if not os.environ.get("BOB_DASHBOARD_DRAFT_BRANCH", "").startswith("draft/"):
            data["publication"] = {"ok": True, "mode": "local", "reason": "draft-only publication; no default-branch writes"}
            write_json(CONDUCTOR / "dashboard.json", data)
            alert("dashboard")
            return
        sha = push_dashboard(data)
        if not sha:
            raise RuntimeError("dashboard update returned no commit")
        alert("dashboard")
        data["publication"] = {"ok": True, "commit": sha, "path": "agents-status.json"}
        log("dashboard data pushed " + sha)
    except Exception as exc:
        reason = str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__
        alert("dashboard", "dashboard push unavailable (" + reason + "); current snapshot is conductor/dashboard.json")
        data["publication"] = {"ok": False, "error": reason, "local": "conductor/dashboard.json"}
        log("dashboard local fallback: " + reason)
    write_json(CONDUCTOR / "dashboard.json", data)


def status_report():
    data = snapshot()
    healthy = sum(s["healthy"] for s in data["services"].values())
    lines = ["# STATUS — " + stamp(),
             "SERVICES: %s/4 healthy; job-runner 1m, reviewer 5m, dashboard-updater 5m, watchdog 3m." % healthy,
             "HEARTBEATS: " + "; ".join(n + " " + str(s["heartbeat_age_seconds"]) + "s" for n, s in data["services"].items()),
             "JOBS: %(launched)s launched, %(running)s running, %(harvested)s harvested; %(blocked_closeouts)s blocked jobs retained." % data["jobs"],
             "RECOVERY: %s unharvested; %s without a live job screen (see jobs.jsonl)." % (len(data["jobs"]["unharvested"]), data["jobs"]["orphaned"]),
             "RESTARTS (last hour): " + json.dumps(data["restarts_last_hour"], sort_keys=True),
             "MODELS confirmed in last 24h: " + (", ".join(data["models_succeeded_last_24h"]) or "none; see model-runs.jsonl"),
             "CONDUCTOR: single scheduler; two-hour council assessment only; live core read-only.",
             "LANES: " + "; ".join(n + "=" + v["state"] for n, v in data["lanes"].items()),
             "MINIMAX: $%.4f spent + $%.4f reserved / $48 hard cap." % (data["spend"]["minimax"]["spent_usd"], data["spend"]["minimax"]["reserved_usd"])]
    from datetime import datetime, timezone
    def cell(value):
        return str(value if value is not None else "—").replace("|", "\\|").replace("\n", " ")
    def when(value):
        return datetime.fromtimestamp(value, timezone.utc).isoformat(timespec="seconds") if value else "—"
    lines += ["", "## Lane board", "", "| Lane | State | Job | Started (UTC) | Heartbeat (UTC) | Result / stage |",
              "| --- | --- | --- | --- | --- | --- |"]
    for row in data["lane_board"]:
        lines.append("| " + " | ".join(cell(v) for v in (row["lane"], row["state"], row["job"],
                     when(row["started"]), when(row["heartbeat"]), row["result"] + (" — " + row["result_path"] if row["result_path"] else ""))) + " |")
    for note in sorted((CONDUCTOR / "status").glob("notes-*.md")):
        lines.append(note.stem + ": " + " ".join(note.read_text(errors="replace").split())[:1500])
    with lock("status"):
        entries = read_json(CONDUCTOR / "alerts.json", {})
        # Group model failures to keep the human status below 15 lines.
        grouped = []
        for key, message in sorted(entries.items()):
            grouped.append("JEFF: " + message + " [svc:" + key + "]")
        if len(grouped) > 5:
            grouped = grouped[:4] + ["JEFF: additional active alerts in conductor/alerts.json (" + str(len(entries)) + " total). [svc:more]"]
        atomic_write(CONDUCTOR / "STATUS.md", "\n".join(lines + grouped) + "\n")
    return data


def lock_service(name, args):
    if name not in INTERVALS:
        raise ValueError("unknown service")
    (CONDUCTOR / "locks").mkdir(parents=True, exist_ok=True)
    handle = (CONDUCTOR / "locks" / ("service-" + name + ".lock")).open("a+")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        log(name + " already running (lifetime lock)")
        return 0
    atomic_write(CONDUCTOR / "locks" / (name + ".pid"), str(os.getpid()) + "\n")
    fd = handle.fileno()
    os.set_inheritable(fd, True)
    env = dict(os.environ, BOB_SERVICE_LOCK_FD=str(fd))
    os.execve("/bin/bash", ["/bin/bash", str(SERVICES / (name + ".sh")), "--locked"] + args, env)


def rotate_log(name):
    path = ROOT / "logs" / (name + ".log")
    if path.exists() and path.stat().st_size > 5 * 1024 * 1024:
        with path.open("rb") as handle:
            handle.seek(-1024 * 1024, 2)
            tail = handle.read().decode("utf-8", "replace")
        atomic_write(path.with_suffix(".log.1"), tail)
        # Retain the inode: the loop's append descriptor continues writing here.
        with path.open("r+") as handle:
            handle.truncate(0)


def cycle(name):
    # Only the loop shell owns the lifetime lock. Its children must not retain it
    # after a screen is stopped or while a separately scheduled pass runs.
    if os.environ.get("BOB_SERVICE_LOCK_FD"):
        os.close(int(os.environ.pop("BOB_SERVICE_LOCK_FD")))
    rotate_log(name)
    log(name + " cycle start")
    if name == "job-runner":
        runner_cycle()
    elif name == "reviewer":
        reviewer_cycle()
    elif name == "dashboard-updater":
        dashboard_cycle()
    elif name == "watchdog":
        ensure_services(check_stale=True, self_name="watchdog")
        try:
            takeover()
            alert("takeover")
        except Exception as exc:
            alert("takeover", "legacy takeover deferred: " + type(exc).__name__)
        status_report()
    else:
        raise ValueError("unknown service")
    HEARTBEATS.mkdir(parents=True, exist_ok=True)
    (HEARTBEATS / name).touch()
    log(name + " cycle good; heartbeat updated")


def main():
    command = sys.argv[1]
    if command == "lock-service":
        return lock_service(sys.argv[2], sys.argv[3:])
    if command == "cycle":
        cycle(sys.argv[2])
    elif command == "tick":
        from jobs import tick
        return tick()
    elif command == "legacy-shim":
        try:
            with lock("service-job-runner", blocking=False):
                pass
        except BlockingIOError:
            log("services already own orchestration; legacy shim exits")
            return 0
        ensure_services()
    elif command == "start-all":
        ensure_services(check_stale="--watchdog-guard" in sys.argv)
        time.sleep(1)
        takeover()
        missing = [n for n in INTERVALS if "svc-" + n not in screen_sessions()]
        if missing:
            raise RuntimeError("screens missing after start: " + ", ".join(missing))
    elif command == "status":
        print(json.dumps(status_report(), indent=2))
    else:
        raise ValueError("unknown command")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BlockingIOError:
        log("another cycle or supervisor owns the lock; retry next cycle")
        raise SystemExit(0)
    except Exception as exc:
        # Exception details from subprocesses can contain prompts or API keys.
        reason = str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__
        log("cycle error: " + reason)
        raise SystemExit(1)
    finally:
        # All services persist alerts, but STATUS has this one rendering path.
        # Render after failed cycles too, so missing keys/restart limits are visible.
        if len(sys.argv) > 1 and sys.argv[1] in ("cycle", "start-all"):
            try:
                status_report()
            except Exception as exc:
                log("status refresh pending: " + type(exc).__name__)
