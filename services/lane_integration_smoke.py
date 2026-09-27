#!/usr/bin/env python3
"""Offline integration proof: real journals/screens/worktrees; simulated model answers."""
from __future__ import annotations

import argparse
import json
import shlex
import sys
import time
import uuid
from pathlib import Path
from unittest.mock import patch

import dispatch_request
import jobs
import queue_store as queue
import runtime
import scheduler
import state
import workspaces
import test_scheduler

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "webchat"))
from app import Chat
import lane_dispatch
import tools

REAL_CREATE = jobs.create_record
REAL_LAUNCH = jobs.launch
REAL_SCREENS = runtime.screen_sessions
REAL_DISPATCH_RUN = lane_dispatch.run

ADAPTER = '''import sys, time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, SERVICES)
import worker, state
def answer(lane, prompt, *, cwd, **kwargs):
    deadline = time.monotonic() + 30
    while not (state.ROOT / "release").exists():
        if time.monotonic() > deadline:
            raise RuntimeError("fixture release timed out")
        time.sleep(.05)
    return "SIMULATED provider answer; actual fixture read: " + (cwd / "README.md").read_text()
with patch.object(worker, "ask", side_effect=answer), patch.object(worker, "HEARTBEAT_SECONDS", .2):
    raise SystemExit(worker.execute(sys.argv[1], sys.argv[2]))
'''

DISPATCH_ADAPTER = '''import shlex, sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, SERVICES)
import dispatch_request, jobs, lanes, state
real_create = jobs.create_record
def create(spec, lane):
    record = real_create(spec, lane)
    (Path(record["job_dir"]) / "run.sh").write_text(
        "#!/bin/bash\\nexport BOB_ROOT=" + shlex.quote(str(state.ROOT)) + "\\nexec " +
        shlex.quote(sys.executable) + " " + shlex.quote(ADAPTER_PATH) + " " +
        shlex.quote(record["job_id"]) + ' "$1" < /dev/null\\n')
    return record
with patch.object(lanes, "refresh", side_effect=lambda: {lane: {"state": "ready"} for lane in lanes.SCHEDULER_LANES}), \\
        patch.object(jobs, "create_record", side_effect=create):
    dispatch_request.main()
'''


class NoChatProvider:
    def __init__(self):
        self.calls = []

    def health(self, conversation_id=None):
        return {"providers": {}, "order": [], "fast_order": []}

    def reply(self, *args):
        self.calls.append(args)
        raise AssertionError("The replay must finish through tools in the same reply.")


def drill():
    case = test_scheduler.SchedulerTest()
    case.setUp()
    chat = None
    try:
        # All actions target a throwaway repository, not the checkout or live core.
        workspaces.git(case.core, "init", "-b", "draft/integration-fixture")
        workspaces.git(case.core, "config", "user.name", "Lane Integration Test")
        workspaces.git(case.core, "config", "user.email", "lane-integration@localhost")
        (case.core / "README.md").write_text("Lane integration fixture\n")
        workspaces.git(case.core, "add", "README.md")
        workspaces.git(case.core, "commit", "-m", "Local integration fixture")
        source_head = workspaces.git(case.core, "rev-parse", "HEAD")
        adapter = case.root / "integration_worker.py"
        adapter.write_text("SERVICES = " + repr(str(Path(__file__).resolve().parent)) + "\n" + ADAPTER)
        dispatcher = case.root / "integration_dispatch.py"
        dispatcher.write_text("SERVICES = " + repr(str(Path(__file__).resolve().parent)) +
                              "\nADAPTER_PATH = " + repr(str(adapter)) + "\n" + DISPATCH_ADAPTER)

        def create(spec, lane):
            record = REAL_CREATE(spec, lane)
            (Path(record["job_dir"]) / "run.sh").write_text(
                "#!/bin/bash\nexport BOB_ROOT=" + shlex.quote(str(case.root)) + "\nexec " +
                shlex.quote(sys.executable) + " " + shlex.quote(str(adapter)) + " " +
                shlex.quote(record["job_id"]) + ' "$1" < /dev/null\n')
            return record

        dispatch_calls = []
        def dispatch(argv, **kwargs):
            assert Path(argv[1]) == Path(__file__).resolve().parent / "dispatch_request.py"
            assert kwargs["env"]["BOB_ROOT"] == str(case.root.resolve())
            dispatch_calls.append(argv)
            # Only install fixture availability/provider adapters in the child.
            # The production client, subprocess, scheduler entrypoint and JSON receipt are real.
            return REAL_DISPATCH_RUN([argv[0], str(dispatcher), *argv[2:]], **kwargs)

        with patch.object(jobs, "create_record", side_effect=create), patch.object(jobs, "launch", REAL_LAUNCH), \
                patch.object(runtime, "screen_sessions", REAL_SCREENS), patch.object(lane_dispatch, "run", side_effect=dispatch):
            identifiers = [tools.dispatch("queue_add", {"description": goal}, root=case.root)["data"]["queue_id"]
                           for goal in ("Inspect draft evidence", "Research the queue backlog", "Assess the next draft task")]
            before = queue.snapshot()
            assert len(before) == 3 and all(row["status"] == "queued" for row in before.values())
            # Remove the compatibility index: the JSONL journal alone drives assignment.
            (case.root / "next-prompts/INDEX.md").unlink()
            scheduler.tick()
            deadline = time.monotonic() + 10
            while True:
                assigned = [dispatch_request.receipt(identifier) for identifier in identifiers]
                if all(row["started"] and row["screen_observed"] for row in assigned):
                    break
                if time.monotonic() >= deadline:
                    raise AssertionError("Three real workers did not start: " + json.dumps(assigned))
                time.sleep(.05)
            assert len({row["lane"] for row in assigned}) == 3
            assert not (case.root / "next-prompts/INDEX.md").exists()
            first_journal = (case.core / "state/queue.jsonl").read_text()

            provider = NoChatProvider()
            chat = Chat(case.core / "webchat", case.root, provider)
            conversation = chat.conversation_list()["conversations"][0]["id"]
            request_id = str(uuid.uuid4())
            history = chat.submit(conversation, "I need you to do more", request_id)
            reply = history["messages"][-1]
            card = reply["action_card"]
            assert reply["status"] == "done" and card["state"] == "started", reply
            assert "Queued draft job" in reply["content"] and "Started lane" in reply["content"], reply
            assert card["started"] and card["screen_observed"] and card["worker_pid"], card
            assert not provider.calls
            rows = [json.loads(line) for line in (case.core / "state/queue.jsonl").read_text().splitlines()]
            assert any(row["id"] == card["queue_id"] and row["status"] == "queued" for row in rows)
            assert queue.snapshot()[card["queue_id"]]["execution_id"] == card["execution_id"]
            chat.submit(conversation, "I need you to do more", request_id)
            assert len(queue.snapshot()) == 4 and len(state.jobs()) == 4
            assert len(dispatch_calls) == 1
            chat.close()
            chat = Chat(case.core / "webchat", case.root, provider)
            chat.submit(conversation, "I need you to do more", request_id)
            assert len(queue.snapshot()) == 4 and len(state.jobs()) == 4
            assert workspaces.git(case.core, "rev-parse", "HEAD") == source_head
            records = state.jobs()
            return {
                "result": "PASS", "provider_responses": "simulated; no model or network calls",
                "scheduler": {"result": "PASS", "journal": "conductor/state/queue.jsonl",
                              "index_present_at_dispatch": False, "queued_before": list(before.values()),
                              "assignments": assigned, "journal_at_assignment": first_journal},
                "replay": {"result": "PASS", "input": "I need you to do more", "reply": reply,
                           "chat_provider_calls": len(provider.calls), "requests_after_replays": len(queue.snapshot()),
                           "executions_after_replays": len(records), "deduplicated_after_chat_restart": True,
                           "scheduler_subprocess_calls": len(dispatch_calls)},
                "workers": [{key: row.get(key) for key in ("job_id", "engine", "state", "worktree", "branch", "worker_pid", "heartbeat")}
                            for row in records.values()],
                "fixture_source_head_unchanged": source_head,
            }
    finally:
        if chat:
            chat.close()
        (case.root / "release").touch()
        try:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and any(scheduler.lease_held("worker-" + row["job_id"]) for row in state.jobs().values()):
                time.sleep(.05)
            sessions = REAL_SCREENS()
            for record in state.jobs().values():
                if record["job_id"] in sessions or scheduler.lease_held("worker-" + record["job_id"]):
                    assert scheduler.stop_stale_worker(record, record["job_id"] in sessions)
        finally:
            case.doCleanups()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    result = drill()
    result["implementation_sha"] = workspaces.git(Path(__file__).resolve().parents[1], "rev-parse", "HEAD")
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text("# Lane integration proof\n\nReal durable journals, named screen workers, heartbeat receipts, "
                                "Git worktrees and Chat.submit replay; simulated provider answers and availability. "
                                "Fixture paths were removed after the proof. No pushes, PRs or service restarts.\n\n```json\n" +
                                json.dumps(result, indent=2) + "\n```\n")
    print(json.dumps({"result": result["result"], "assignments": result["scheduler"]["assignments"],
                      "reply": result["replay"]["reply"]["content"]}, indent=2))
