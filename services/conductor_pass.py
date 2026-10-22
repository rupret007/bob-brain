#!/usr/bin/env python3
"""Two-hour council assessment. Proposed improvements never edit the live core."""
import json
import time
from datetime import datetime, timezone

from council import run as council_run
import drafts
from runtime import snapshot, status_report
from state import CONDUCTOR, ROOT, atomic_write, lock, log, read_json, write_json


def main():
    if (CONDUCTOR / "MAINTENANCE").exists():
        return
    with lock("conductor-pass", blocking=False):
        started = time.time()
        pass_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        folder = CONDUCTOR / "passes" / pass_id
        folder.mkdir(parents=True, exist_ok=True)
        with lock("pass-schedule"):
            write_json(CONDUCTOR / "pass-schedule.json", {"last_started": started, "next_due": started + 7200,
                       "interval_seconds": 7200, "pass_id": pass_id, "state": "running"})
        write_json(folder / "snapshot.json", snapshot())
        workspace, baseline = drafts.prepare(ROOT, folder)
        status, path, answered = council_run(
            "Critique this pass's own work and conductor/scorecard.md (what is wrong, missing or unproven). "
            "Assess reliability, blocked jobs and project priority. Propose the highest-value next improvement. "
            "Assessment only: never modify the live core. Include file names and validation needed for a future reviewed change.",
            [folder / "snapshot.json", workspace / "conductor/PROMPT.md",
             workspace / "conductor/BUILD-SERVICES.md", workspace / "conductor/scorecard.md",
             workspace / "conductor/services/worker.py", workspace / "conductor/services/jobs.py"], folder)
        # An assessment is not a code change. If a draft exists, independently
        # validate it; never promote it or roll back concurrent live edits.
        draft = drafts.finish(workspace, baseline, folder, agent_ok=status == "synthesized")
        write_json(folder / "result.json", {"assessment": status, "answered": answered,
                   "improvement_verified": draft["draft_verified"], "improvement_applied": False,
                   "verification_failure": draft["verification_failure"]})
        atomic_write(CONDUCTOR / "status/notes-council.md", "Assessment " + pass_id + ": " + status +
                     "; answered " + ", ".join(answered) + "; " + str(path) + "\n")
        with lock("pass-schedule"):
            state = read_json(CONDUCTOR / "pass-schedule.json", {})
            state.update(state="finished", last_finished=time.time(), assessment=status)
            write_json(CONDUCTOR / "pass-schedule.json", state)
        status_report()
        log("assessment complete: " + status)


if __name__ == "__main__":
    try:
        main()
    except BlockingIOError:
        log("assessment already running")
