"""Poll Web Bob's durable queue and refill every available worker lane."""
from __future__ import annotations

import os
import signal
import sys
import time
from pathlib import Path

from command import run
from state import CONDUCTOR, ROOT, atomic_write, lock, log
import lanes

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "state"))
import task_queue


def worker_alive(row):
    try:
        with lock("dispatch-" + row["id"], blocking=False):
            return False
    except BlockingIOError:
        if row.get("lease_until", 0) <= time.time():
            reap_expired_worker(row)
        return True


def reap_expired_worker(row):
    """Reap a hung claim only after verifying its PID, task ID and claim token."""
    pid = row.get("pid")
    if not isinstance(pid, int) or not row.get("claim_token"):
        return False
    result = run(["ps", "-axo", "pid=,ppid=,pgid=,command="], capture_output=True, text=True, timeout=5)
    if result.returncode:
        return False
    processes = {}
    for line in result.stdout.splitlines():
        parts = line.strip().split(None, 3)
        if len(parts) == 4 and all(p.isdigit() for p in parts[:3]):
            processes[int(parts[0])] = (int(parts[1]), int(parts[2]), parts[3])
    command = processes.get(pid, (0, 0, ""))[2]
    if not all(part in command.split() for part in (row["id"], row["claim_token"])) or "dispatch_worker.py" not in command:
        return False  # PID reuse or unverifiable ownership: never kill a bystander.
    owned = {pid}
    while True:
        children = {child for child, (parent, _, _) in processes.items() if parent in owned} - owned
        if not children:
            break
        owned.update(children)
    # Model commands create process groups. Stop verified descendant groups and
    # then the wrapper; its execution lock must be released before a new claim.
    groups = {group for child, (_, group, _) in processes.items() if child in owned - {pid} and group in owned}
    for group in groups:
        try:
            os.killpg(group, signal.SIGKILL)
        except ProcessLookupError:
            pass
    for child in sorted(owned, reverse=True):
        try:
            os.kill(child, signal.SIGKILL)
        except ProcessLookupError:
            pass
    log("Reaped expired Web Bob worker " + row["id"])
    return True


def launch(row):
    folder = CONDUCTOR / "state/task-runs" / row["id"]
    folder.mkdir(parents=True, exist_ok=True)
    # screen starts a detached process; it does not inherit the runner's lifetime
    # lock. The child sources fresh keys even if screen's own environment is old.
    script = Path(__file__).with_name("dispatch-worker.sh")
    result = run(["screen", "-dmS", row["id"], "/bin/bash", str(script), row["id"], row["claim_token"]],
                 env=dict(os.environ, BOB_ROOT=str(ROOT)), capture_output=True, timeout=10, detach=True)
    if result.returncode:
        raise RuntimeError("Worker launch failed")


def tick():
    if (CONDUCTOR / "MAINTENANCE").exists():
        return 0
    with lock("web-dispatch", blocking=False):
        task_queue.recover(ROOT, worker_alive)
        health = lanes.refresh()
        launched = 0
        # Tool workers can inspect a repository even when a request supplies no
        # evidence. Explicit API/review routes remain pinned to their own lane.
        for lane in ("cursor", "codex", "gemini", "minimax", "claude"):
            if health.get(lane, {}).get("state") != "ready":
                continue
            row = task_queue.claim(ROOT, lane)
            if not row:
                continue
            try:
                launch(row)
                launched += 1
                log("Web Bob claimed " + row["id"] + " worker=" + lane)
            except Exception as exc:
                task_queue.transition(ROOT, row["id"], row["claim_token"], "retry",
                                      error="Worker launch failed: " + type(exc).__name__)
        return launched


if __name__ == "__main__":
    raise SystemExit(tick() and 0)
