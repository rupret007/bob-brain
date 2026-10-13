"""Grounded multi-step status projection. Fixture jobs only; no planner or network."""
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from app import Chat
from bob_gaps import (
    dispatch_status_from_conversation,
    dispatch_status_question,
    dispatch_status_receipt,
    format_dispatch_status,
)
import chat_intent


GOAL = "Publish the write-up"
ONE_STEP = ["Draft the outline."]
THREE_STEPS = ["Draft the outline.", "Write the draft.", "Review the result."]
NOW = 1_000_000.0
PLANNER_VERBS = (
    "i will schedule",
    "permission granted",
    "hold lifted",
    "queued a new",
    "starting the next step",
    "i assigned",
    "new work was queued",
)


class FakeProviders:
    def health(self, conversation_id=None):
        return {"providers": {}, "order": [], "fast_order": []}


def _job(**overrides):
    row = dict(
        id="job-writeup",
        task=GOAL,
        status="queued",
        progress=0,
        result="",
        started_at=NOW,
        heartbeat_at=NOW,
        updated_at=NOW,
    )
    row.update(overrides)
    return row


def _accepted(receipt, ok=True):
    return {"ok": ok, "receipt": receipt}


def _assert_no_planner_or_permission(test, text):
    lowered = text.lower()
    for phrase in PLANNER_VERBS:
        test.assertNotIn(phrase, lowered, phrase)
    test.assertNotIn("permission granted", lowered)
    test.assertNotIn("hold lifted", lowered)


class DispatchStatusFormatterTests(unittest.TestCase):
    def test_one_step_queued_names_unresolved_stage(self):
        text = format_dispatch_status(GOAL, ONE_STEP, [_job(status="queued")], now=NOW)
        self.assertIn(f"Goal: {GOAL}.", text)
        self.assertIn("Current recorded stage: queued.", text)
        self.assertIn("Next unresolved step: 1. Draft the outline.", text)
        self.assertIn("unresolved", text)
        self.assertNotIn("Completed steps with evidence", text)
        _assert_no_planner_or_permission(self, text)

    def test_three_step_running_completed_outline_from_accepted_result(self):
        text = format_dispatch_status(
            GOAL,
            THREE_STEPS,
            [_job(status="running", progress=1)],
            accepted=_accepted("accepted: outline ready"),
            now=NOW,
        )
        self.assertIn("Current recorded stage: running.", text)
        self.assertIn("step 2 of 3", text)
        self.assertIn("Completed steps with evidence: Draft the outline.", text)
        self.assertIn("Next unresolved step: 2. Write the draft.", text)
        self.assertNotIn("Review the result", text.split("Completed steps with evidence:")[1].split(".")[0])
        _assert_no_planner_or_permission(self, text)

    def test_partial_failure_keeps_accepted_outline_and_marks_later_unknown(self):
        text = format_dispatch_status(
            GOAL,
            THREE_STEPS,
            [_job(status="partial-failure", progress=1, result="failed: worker crashed after the outline")],
            accepted=_accepted("accepted: outline ready"),
            now=NOW,
        )
        self.assertIn("Current recorded stage: partial-failure.", text)
        self.assertIn("failed", text)
        self.assertIn("unknown", text)
        self.assertIn("Completed steps with evidence: Draft the outline.", text)
        self.assertIn("Later steps are unknown.", text)
        _assert_no_planner_or_permission(self, text)

    def test_held_keeps_hold_and_does_not_grant_permission(self):
        text = format_dispatch_status(
            GOAL,
            THREE_STEPS,
            [_job(status="held")],
            hold={"active": True, "reason": "safety hold"},
            now=NOW,
        )
        self.assertIn("Current recorded stage: held.", text)
        self.assertIn("unresolved", text)
        self.assertIn("Hold remains in effect.", text)
        self.assertNotIn("permission granted", text.lower())
        self.assertNotIn("hold lifted", text.lower())
        _assert_no_planner_or_permission(self, text)

    def test_restart_receipt_is_not_step_evidence(self):
        text = format_dispatch_status(
            GOAL,
            THREE_STEPS,
            [_job(
                status="running",
                progress=2,
                result="accepted: restarted after worker drop",
            )],
            now=NOW,
        )
        self.assertIn("Current recorded stage: running.", text)
        self.assertIn("step 1 of 3", text)
        self.assertNotIn("Completed steps with evidence", text)
        _assert_no_planner_or_permission(self, text)

    def test_completed_requires_accepted_result_for_every_step(self):
        text = format_dispatch_status(
            GOAL,
            THREE_STEPS,
            [_job(status="completed", progress=3)],
            accepted=_accepted("accepted: outline, draft, and review are done"),
            now=NOW,
        )
        self.assertIn("Current recorded stage: completed.", text)
        self.assertIn("complete", text)
        self.assertIn("Draft the outline", text)
        self.assertIn("Write the draft", text)
        self.assertIn("Review the result", text)
        self.assertIn("No unresolved step remains.", text)
        _assert_no_planner_or_permission(self, text)

    def test_proposed_plan_without_jobs(self):
        text = format_dispatch_status(GOAL, THREE_STEPS, [], now=NOW)
        self.assertIn("This plan is proposed.", text)
        self.assertIn("Current recorded stage: proposed.", text)
        self.assertIn("Next unresolved step: 1. Draft the outline.", text)
        _assert_no_planner_or_permission(self, text)

    def test_stale_worker_activity_cannot_imply_progress(self):
        text = format_dispatch_status(
            GOAL,
            THREE_STEPS,
            [_job(status="running", progress=2, heartbeat_at=NOW - 400, updated_at=NOW - 400)],
            now=NOW,
        )
        self.assertIn("unknown", text)
        self.assertNotIn("step 2 of 3", text)
        self.assertNotIn("Completed steps with evidence", text)
        _assert_no_planner_or_permission(self, text)

    def test_progress_and_heartbeat_alone_do_not_complete_a_step(self):
        text = format_dispatch_status(
            GOAL,
            THREE_STEPS,
            [_job(status="running", progress=2)],
            accepted={"ok": True, "receipt": "worker heartbeat"},
            now=NOW,
        )
        self.assertNotIn("Completed steps with evidence", text)
        self.assertIn("step 1 of 3", text)

    def test_receipt_wrapper_reads_existing_record_shape(self):
        text = dispatch_status_receipt(
            {
                "task": GOAL,
                "subtasks": THREE_STEPS,
                "jobs": [_job(status="queued")],
            },
            now=NOW,
        )
        self.assertIn("Current recorded stage: queued.", text)
        self.assertIn("Next unresolved step: 1. Draft the outline.", text)


class DispatchStatusChatTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.folder = self.root / "conductor/webchat"
        self.folder.mkdir(parents=True)
        self.chat = Chat(self.folder, self.root, FakeProviders())
        self.identifier = self.chat.conversation_list()["conversations"][0]["id"]
        guard = patch("urllib.request.OpenerDirector.open", side_effect=AssertionError("Network forbidden"))
        guard.start()
        self.addCleanup(guard.stop)
        for name in ("_screen_sessions", "process_table"):
            sampler = patch("live_status_snapshot." + name, return_value={})
            sampler.start()
            self.addCleanup(sampler.stop)

    def tearDown(self):
        self.chat.close()
        self.tmp.cleanup()

    def seed_plan(self, **intent):
        conversation = self.chat.conversations[self.identifier]
        payload = dict(
            goal=GOAL,
            prompt=GOAL,
            subtasks=THREE_STEPS,
            jobs=[_job(status="running", progress=1, heartbeat_at=time.time(), updated_at=time.time())],
            accepted=_accepted("accepted: outline ready"),
        )
        payload.update(intent)
        conversation["messages"].append({
            "id": str(uuid.uuid4()),
            "request_id": str(uuid.uuid4()),
            "role": "assistant",
            "content": "Saving your task for a worker…",
            "status": "done",
            "created_at": time.time(),
            "dispatch_intent": payload,
        })
        self.chat.save(conversation)

    def submit(self, text):
        with patch("app.parse_work", side_effect=AssertionError("Status entered coding route")):
            return self.chat.submit(self.identifier, text, str(uuid.uuid4()))["messages"][-1]

    def test_status_question_routes_to_grounded_projection(self):
        self.seed_plan()
        self.assertTrue(dispatch_status_question("what's the status of the write-up"))
        reply = self.submit("what's the status of the write-up")
        self.assertEqual(reply["provider"], "state")
        self.assertIn("Current recorded stage: running.", reply["content"])
        self.assertIn("Completed steps with evidence: Draft the outline.", reply["content"])
        self.assertIn("step 2 of 3", reply["content"])
        self.assertNotIn("permission granted", reply["content"].lower())

    def test_where_are_we_uses_same_projection(self):
        self.seed_plan()
        reply = self.submit("where are we on the blog draft")
        self.assertIn("Goal: Publish the write-up.", reply["content"])
        self.assertIn("Next unresolved step: 2. Write the draft.", reply["content"])

    def test_hold_is_named_and_not_erased(self):
        self.seed_plan(jobs=[_job(status="held", heartbeat_at=time.time())], accepted=None)
        conversation = self.chat.conversations[self.identifier]
        chat_intent.state_for(conversation)
        conversation["intent_state"]["holds"] = {"all": {"reason": "safety hold"}}
        self.chat.save(conversation)
        reply = self.submit("what's the status of the write-up")
        self.assertIn("Current recorded stage: held.", reply["content"])
        self.assertIn("Hold remains in effect.", reply["content"])
        self.assertNotIn("permission granted", reply["content"].lower())
        self.assertNotIn("hold lifted", reply["content"].lower())
        self.assertTrue(self.chat.conversations[self.identifier]["intent_state"]["holds"])

    def test_formatter_only_does_not_invent_a_plan(self):
        conversation = {"messages": []}
        text = dispatch_status_from_conversation(conversation)
        self.assertIn("Current recorded stage: proposed.", text)
        _assert_no_planner_or_permission(self, text)


if __name__ == "__main__":
    unittest.main()
