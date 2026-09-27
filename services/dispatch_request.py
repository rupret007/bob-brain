#!/usr/bin/env python3
"""Run a bounded scheduler tick for one durable request and return launch evidence."""
from __future__ import annotations

import argparse
import contextlib
import json
import sys
import time

import queue_store as queue
import scheduler
import state


def receipt(identifier):
    from runtime import screen_sessions
    request = queue.snapshot()[identifier]
    record = scheduler.execution_for(request, state.jobs()) or {}
    # A launch intent alone is not evidence that a worker actually started.
    observed = bool(record.get("worker_pid") and record.get("heartbeat") and
                    time.time() - record["heartbeat"] <= scheduler.STALE_SECONDS and
                    record.get("attempt_token") == request.get("attempt_token"))
    live = (observed and record.get("state") == "running" and record.get("recovery") == "worker executing"
            and record["job_id"] in screen_sessions())
    finished = observed and record.get("verified") and record.get("state") in ("running", "harvested")
    return {"queue_id": identifier, "status": request["status"], "started": bool(live or finished),
            "lane": request.get("owner"), "execution_id": request.get("execution_id"),
            "worker_pid": record.get("worker_pid"), "heartbeat": record.get("heartbeat"),
            "reason": request.get("reason", ""), "screen_observed": bool(live)}


def start_request(identifier, wait_seconds=3):
    if identifier not in queue.snapshot():
        raise ValueError("unknown queue request")
    if scheduler.paused():
        return dict(receipt(identifier), started=False, reason="Scheduling is paused (MAINTENANCE/STOP-WEBBOB).")
    try:
        scheduler.tick(request_ids={identifier})
    except BlockingIOError:
        return dict(receipt(identifier), reason="The scheduler is busy; the durable request remains queued.")
    deadline = time.monotonic() + wait_seconds
    while True:
        result = receipt(identifier)
        if result["started"] or result["status"] != "running" or time.monotonic() >= deadline:
            return result
        time.sleep(.05)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("queue_id")
    args = parser.parse_args()
    # Keep stdout machine-readable even though normal scheduler logs use stdout.
    with contextlib.redirect_stdout(sys.stderr):
        result = start_request(args.queue_id)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
