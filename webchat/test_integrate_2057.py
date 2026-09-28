"""Every original Jeff turn, plus forged effects and failed dispatches."""
import copy
import json
import time
import uuid
from pathlib import Path
from unittest.mock import patch

from app import Chat
from dispatch_receipts import NO_DISPATCH, receipt_errors
from reply_authority import enforce
from task_dispatch import task_queue as queue
from test_webbob_replyq_1856 import SessionFixture

SESSIONS = json.loads(Path(__file__).with_name("fixtures").joinpath("integrate_sessions_0927.json").read_text())["sessions"]


class IntegratedSessions(SessionFixture):
    def seed(self):
        return queue.enqueue(self.root, "external-project-work", str(uuid.uuid4()),
                             "Improve WebJam recording reliability", kind="coding", worker="codex", title="WebJam")

    def test_all_17_original_messages_in_conversation_order(self):
        self.seed()
        checked = 0
        for source in SESSIONS:
            self.identifier = self.chat.new_conversation()["id"]
            for index, exchange in enumerate(source["exchanges"]):
                with self.subTest(session=source["source_id"], turn=index + 1, message=exchange["message"]):
                    before = set(queue.tasks(self.root))
                    started = time.time()
                    answer = self.send(exchange["message"])
                    records = queue.tasks(self.root)
                    identifiers = answer.get("task_ids") or ([answer["task_id"]] if answer.get("task_id") else [])
                    self.assertEqual(set(identifiers), set(records) - before)
                    self.assertEqual(receipt_errors(answer, records, self.identifier, answer["request_id"], started), [])
                    self.assertNotRegex(answer["content"], r"(?i)I'll make sure|actively adding work|ready|unknown task")
                    if source["source_id"].startswith("b33fac"):
                        if index in (0, 1, 5):
                            self.assertEqual([records[i]["requested_worker"] for i in identifiers], ["gemini", "minimax"])
                            self.assertEqual([records[i]["kind"] for i in identifiers], ["audit", "test-writing"])
                            for identifier in identifiers:
                                self.assertIn(records[identifier]["title"], answer["content"])
                        elif index == 6:
                            self.assertEqual(len(identifiers), 1)
                            self.assertEqual(records[identifiers[0]]["kind"], "coding")
                        else:
                            self.assertEqual(answer["provider"], "state")
                            self.assertFalse(identifiers)
                            for name in ("Codex", "Claude", "Cursor", "Gemini", "MiniMax"):
                                self.assertIn(name, answer["content"])
                            self.assertIn("waiting to run", answer["content"])
                    elif source["source_id"].startswith("8126301c"):
                        if index == 0:
                            self.assertEqual(answer["content"], "Which projects should I work on?")
                        elif index == 5:
                            self.assertEqual([records[i]["title"] for i in identifiers], ["WebJam", "AdoptIQ", "StoryBoard", "Fantasy Football"])
                        elif index == 6:
                            self.assertEqual(answer["content"], "Hi Jeff!")
                            self.assertFalse(identifiers)
                        else:
                            self.assertEqual(answer["provider"], "state")
                    else:
                        self.assertEqual([records[i]["title"] for i in identifiers], ["WebJam", "AdoptIQ"])
                    # An HTTP retry and restart must preserve exact receipt IDs.
                    self.chat.submit(self.identifier, exchange["message"], answer["request_id"])
                    self.assertEqual(set(queue.tasks(self.root)), set(records))
                    checked += 1
        replacement = Chat(self.folder, self.root, self.fake)
        try:
            self.assertEqual(set(queue.tasks(self.root)), set(records))
            self.assertEqual(replacement.get(self.identifier)["messages"][-1]["content"], answer["content"])
        finally:
            replacement.close()
        self.assertEqual(checked, 17)

    def test_unsupported_promises_cannot_escape_the_model_boundary(self):
        claims = [
            "I'll make sure they're utilized for ongoing jobs.",
            "Yes, the system is actively adding work for them.",
            "I'll make sure to maximize the use of all available resources.",
            "I assigned a Gemini audit and MiniMax tests.",
            "The workers have started those jobs.",
            "Your tasks were queued and delegated to Gemini.",
            "I have put Gemini and MiniMax to work.",
            "Gemini is now working on it.",
            "I queued job `webchat-" + "a" * 32 + "`.",
        ]
        for claim in claims:
            with self.subTest(claim=claim):
                self.fake.reply_text = claim
                answer = self.send("Thanks Bob")
                self.assertEqual(answer["content"], NO_DISPATCH)
                self.assertFalse(queue.tasks(self.root))

    def test_fake_stale_foreign_and_missing_receipts_fail(self):
        self.seed()
        started = time.time()
        answer = self.send("Use Gemini and MiniMax for ongoing jobs")
        records = queue.tasks(self.root)
        valid = (self.identifier, answer["request_id"], started)
        self.assertFalse(receipt_errors(answer, records, *valid))
        for mutation in ("absent", "old", "foreign", "uncited", "omitted", "invented"):
            rows, reply = copy.deepcopy(records), copy.deepcopy(answer)
            identifier = reply["task_ids"][0]
            if mutation == "absent": rows.pop(identifier)
            if mutation == "old": rows[identifier]["created_at"] = started - 30
            if mutation == "foreign": rows[identifier]["request_id"] = "another-turn:0"
            if mutation == "uncited": reply["content"] = reply["content"].replace(identifier, "")
            if mutation == "omitted": reply["task_ids"].pop()
            if mutation == "invented": reply["content"] += " webchat-" + "0" * 32
            self.assertTrue(receipt_errors(reply, rows, *valid), mutation)

    def test_context_survives_restart_and_a_hold_still_blocks_assignment(self):
        self.seed()
        self.send("Use Gemini and MiniMax for ongoing jobs")
        self.chat.close()
        self.chat = Chat(self.folder, self.root, self.fake)
        answer = self.send("Are you going to add work for them to do?")
        self.assertEqual(len(answer["task_ids"]), 2)
        self.send("Hold off")
        before = set(queue.tasks(self.root))
        answer = self.send("We want them workout too take everything to the max.")
        self.assertIn("couldn't assign", answer["content"])
        self.assertEqual(set(queue.tasks(self.root)), before)

    def test_empty_status_says_idle_and_queued_assignments_are_not_idle(self):
        answer = self.send("Is work being performed on all of them now?")
        self.assertIn("are idle", answer["content"])
        self.seed()
        self.send("Use Gemini and MiniMax for ongoing jobs")
        answer = self.send("What about Gemini and MiniMax?")
        self.assertIn("Gemini is on", answer["content"])
        self.assertIn("MiniMax is on", answer["content"])
        self.assertIn("waiting to run", answer["content"])
        self.assertNotIn("ready", answer["content"])

    def test_all_llms_directive_makes_a_real_job_per_named_worker(self):
        self.seed()
        answer = self.send("Use all LLMs for ongoing work")
        records = queue.tasks(self.root)
        self.assertEqual([records[i]["requested_worker"] for i in answer["task_ids"]], list(queue.MODEL_WORKERS))
        self.assertFalse(self.fake.calls)
