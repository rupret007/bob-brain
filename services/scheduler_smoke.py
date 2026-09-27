#!/usr/bin/env python3
"""Real screen/worktree/queue drill with explicitly simulated provider responses.

No production queue, credentials, network models, or source branches are touched.
The fixture adapter lives only in the temporary test directory, never in workers.
"""
from __future__ import annotations

import argparse
import json
import shlex
import sys
import time
from pathlib import Path
from unittest.mock import patch

import jobs
import queue_store as queue
import runtime
import scheduler
import state
import workspaces
from test_scheduler import SchedulerTest

REAL_LAUNCH = jobs.launch
REAL_SCREENS = runtime.screen_sessions
REAL_CREATE = jobs.create_record

ADAPTER = '''import sys, time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, SERVICES)
import worker, state, workspaces
record = state.jobs()[sys.argv[1]]
def answer(lane, prompt, *, cwd, **kwargs):
    deadline = time.monotonic() + 30
    while not (state.ROOT / "release").exists():
        if time.monotonic() > deadline:
            raise RuntimeError("fixture release timed out")
        time.sleep(.05)
    if record["role"] == "build":
        name = record["scope"][0]
        (cwd / name).write_text("smoke-tested\\n")
        workspaces.git(cwd, "add", name)
        workspaces.git(cwd, "commit", "-m", "isolated scheduler smoke change")
        workspaces.git(cwd, "push", "origin", "HEAD")
        return "Fixture build committed and pushed to the temporary bare remote. Tests are independently run by worker.py."
    observed = (cwd / "src/a").read_text().strip()
    return "SIMULATED provider reply; actual read of src/a: " + observed + "\\nVERDICT: PASS"
with patch.object(worker, "ask", side_effect=answer), patch.object(worker, "HEARTBEAT_SECONDS", .2):
    raise SystemExit(worker.execute(sys.argv[1], sys.argv[2]))
'''


def drill(evidence=None):
    case = SchedulerTest()
    case.setUp()
    try:
        root = case.root
        original_head = workspaces.git(case.repo, "rev-parse", "HEAD")
        adapter = root / "proof_worker.py"
        adapter.write_text("SERVICES = " + repr(str(Path(__file__).resolve().parent)) + "\n" + ADAPTER)
        gate = "from pathlib import Path; import time; p=Path(" + repr(str(root / "release")) + "); "
        gate += "exec('for _ in range(600):\\n if p.exists(): break\\n time.sleep(.05)\\nelse: raise RuntimeError(\"release timed out\")')"
        def create(spec, lane):
            record = REAL_CREATE(spec, lane)
            script = Path(record["job_dir"]) / "run.sh"
            script.write_text("#!/bin/bash\nexport BOB_ROOT=" + shlex.quote(str(root)) + "\nexec " +
                              shlex.quote(sys.executable) + " " + shlex.quote(str(adapter)) + " " +
                              shlex.quote(record["job_id"]) + ' "$1" < /dev/null\n')
            return record
        case.enqueue("goal-build", goal="Build independent fixture areas", parts=[
            dict(goal="Change A", role="build", scope=["src/a"], test_commands=[[sys.executable, "-c", "assert open('src/a').read() == 'smoke-tested\\n'"]]),
            dict(goal="Change B", role="build", scope=["src/b"], test_commands=[[sys.executable, "-c", "assert open('src/b').read() == 'smoke-tested\\n'"]]),
        ])
        case.enqueue("goal-audit", goal="Research and critique fixture", parts=[
            dict(goal="Read fixture evidence", role="research"), dict(goal="Critique fixture evidence", role="critique")])
        case.enqueue("goal-checks", goal="Review and test fixture", parts=[
            dict(goal="Review fixture evidence", role="review"),
            dict(goal="Run local tests", role="test", test_commands=[[sys.executable, "-c", gate],
                 [sys.executable, "-c", "assert open('src/a').read() == 'baseline\\n'"]])])
        with patch.object(jobs, "launch", REAL_LAUNCH), patch.object(jobs, "create_record", side_effect=create), \
                patch.object(runtime, "screen_sessions", REAL_SCREENS):
            scheduler.tick()
            deadline = time.monotonic() + 20
            while True:
                records = list(state.jobs().values())
                if len(records) == 6 and all(r.get("worker_pid") and r.get("heartbeat", 0) > r["started_at"] + .2 for r in records):
                    break
                if time.monotonic() > deadline:
                    raise AssertionError("six actual workers did not establish heartbeats: " + json.dumps(records))
                time.sleep(.1)
            sessions = REAL_SCREENS()
            assert all(r["job_id"] in sessions for r in records)
            assert {r["engine"] for r in records} == set(scheduler.lanes.SCHEDULER_LANES)
            runtime.status_report()
            busy_status = (case.core / "STATUS.md").read_text()
            busy_board = scheduler.lane_board()
            print("Six real screen workers have fresh heartbeats: " + ", ".join(r["lane"] for r in busy_board), flush=True)
            (root / "release").touch()
            deadline = time.monotonic() + 45
            goals = ("goal-build", "goal-audit", "goal-checks")
            while not all(queue.snapshot()[i]["status"] == "jeff-draft" for i in goals):
                scheduler.tick()
                if time.monotonic() > deadline:
                    raise AssertionError("promotion timed out: " + json.dumps(queue.snapshot(), indent=2))
                time.sleep(.2)
            final = queue.snapshot()
            assert workspaces.git(case.repo, "rev-parse", "HEAD") == original_head
            summary = {"ok": True, "provider_responses": "simulated fixture adapters; no network calls",
                       "real_screens": 6, "goals": {i: final[i]["status"] for i in goals},
                       "requests_including_promotions": len(final), "executions": len(state.jobs()),
                       "builds": [{"id": r["queue_id"], "branch": r["branch"], "sha": r["head_sha"],
                                   "tests_sha": r["tests_sha"], "tests_passed": r["tests_passed"]}
                                  for r in state.jobs().values() if r.get("role") == "build"],
                       "source_head_unchanged": original_head}
            if evidence:
                evidence.parent.mkdir(parents=True, exist_ok=True)
                evidence.write_text("# Scheduler screen drill evidence\n\n"
                    "Generated by `python3 services/scheduler_smoke.py`. Provider responses use fixture adapters; "
                    "screens, queue journals, heartbeat threads, Git worktrees, branch commits/pushes to a local bare remote, "
                    "tests, sibling conflict checks and promotion transitions are real. Temporary paths below were removed after the drill.\n\n"
                    "```json\n" + json.dumps(summary, indent=2) + "\n```\n\n" +
                    busy_status[busy_status.index("## Lane board"):])
            return summary
    finally:
        (case.root / "release").touch()
        try:
            sessions = REAL_SCREENS()
            for record in state.jobs().values():
                if record["job_id"] in sessions or scheduler.lease_held("worker-" + record["job_id"]):
                    scheduler.stop_stale_worker(record, record["job_id"] in sessions)
        finally:
            case.doCleanups()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    print(json.dumps(drill(args.evidence), indent=2))
