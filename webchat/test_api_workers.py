"""The reported Jeff turn must cause assignments, never a model acknowledgement."""
import json
import uuid
from unittest.mock import patch

from app import Chat
from task_dispatch import task_queue as queue
from test_webbob_replyq_1856 import SessionFixture
from worker_assignment import requested_workers
from reply_authority import enforce, operational_reply
from jobs_view import build_jobs_view

REQUEST = "remember you can use Gemini and MiniMax for the ongoing jobs"


class APIAssignmentTests(SessionFixture):
    def source(self, project="Web Bob"):
        return queue.enqueue(self.root, self.identifier, str(uuid.uuid4()),
                             "Improve " + project + " queue recovery", kind="coding", worker="codex", title=project)

    def test_real_incident_assigns_both_and_restart_does_not_duplicate(self):
        source = self.source()
        request = str(uuid.uuid4())
        value = self.chat.submit(self.identifier, REQUEST, request)
        message = value["messages"][-1]
        rows = [queue.tasks(self.root)[key] for key in message["task_ids"]]
        self.assertEqual([r["requested_worker"] for r in rows], ["gemini", "minimax"])
        self.assertEqual([r["kind"] for r in rows], ["audit", "test-writing"])
        for row in rows:
            self.assertEqual(row["source_job_id"], source["id"])
            self.assertIn(row["id"], message["content"])
            self.assertIn(row["title"], message["content"])
        self.assertNotIn("ready", message["content"].lower())
        self.assertFalse(self.fake.calls)
        self.chat.submit(self.identifier, REQUEST, request)
        replacement = Chat(self.folder, self.root, self.fake)
        try:
            replacement.reconcile_tasks()
            self.assertEqual(len(queue.tasks(self.root)), 3)
        finally:
            replacement.close()

    def test_single_worker_names_the_actual_task_in_queued_and_started_receipts(self):
        self.source()
        value = self.chat.submit(self.identifier, "Use MiniMax for current work", str(uuid.uuid4()))
        row = queue.tasks(self.root)[value["messages"][-1]["task_id"]]
        self.assertIn("test-case drafts", value["messages"][-1]["content"])
        claim = queue.claim(self.root, "minimax")
        queue.transition(self.root, row["id"], claim["claim_token"], "running")
        self.chat.reconcile_tasks()
        reply = self.chat.history(self.identifier)["messages"][-1]["content"]
        self.assertIn("Started on MiniMax", reply)
        self.assertIn(row["title"], reply)

    def test_assignments_deliver_one_attributed_result_without_reassigning_coder(self):
        source = self.source()
        coder = queue.claim(self.root, "codex")
        queue.transition(self.root, coder["id"], coder["claim_token"], "running")
        self.chat.submit(self.identifier, REQUEST, str(uuid.uuid4()))
        for lane in ("gemini", "minimax"):
            row = queue.claim(self.root, lane)
            queue.transition(self.root, row["id"], row["claim_token"], "running")
            queue.transition(self.root, row["id"], row["claim_token"], "succeeded", result=lane + " specific report")
        for _ in range(2):
            self.chat.reconcile_tasks()
        messages = [m for m in self.chat.history(self.identifier)["messages"] if m.get("task_status")]
        self.assertEqual(len(messages), 1)
        self.assertIn("Worker assignments completed: 2/2", messages[0]["content"])
        self.assertIn("gemini specific report", messages[0]["content"])
        self.assertIn("minimax specific report", messages[0]["content"])
        self.assertEqual(queue.tasks(self.root)[source["id"]]["claim_token"], coder["claim_token"])

    def test_unrelated_hold_does_not_block_an_allowed_source_project(self):
        self.source("WebJam")
        self.chat.submit(self.identifier, "Hold off on Web Bob", str(uuid.uuid4()))
        value = self.chat.submit(self.identifier, REQUEST, str(uuid.uuid4()))
        self.assertEqual(len(value["messages"][-1]["task_ids"]), 2)
        self.assertIn("WebJam", value["messages"][-1]["content"])

    def test_honest_no_jobs_hold_maintenance_and_missing_key_outcomes(self):
        value = self.chat.submit(self.identifier, REQUEST, str(uuid.uuid4()))
        self.assertIn("couldn't assign", value["messages"][-1]["content"])
        self.assertFalse(queue.tasks(self.root))
        self.source()
        self.chat.submit(self.identifier, "Hold off on Web Bob", str(uuid.uuid4()))
        value = self.chat.submit(self.identifier, REQUEST, str(uuid.uuid4()))
        self.assertIn("current holds", value["messages"][-1]["content"])
        self.chat.submit(self.identifier, "The hold is lifted", str(uuid.uuid4()))
        (self.root / "conductor/MAINTENANCE").touch()
        value = self.chat.submit(self.identifier, REQUEST, str(uuid.uuid4()))
        self.assertIn("maintenance", value["messages"][-1]["content"])
        (self.root / "conductor/MAINTENANCE").unlink()
        (self.root / "conductor/lanes.json").write_text(json.dumps({"minimax": {"state": "needs_key"}}))
        value = self.chat.submit(self.identifier, REQUEST, str(uuid.uuid4()))
        self.assertIn("needs key", value["messages"][-1]["content"])
        self.assertEqual(len(queue.tasks(self.root)), 1)
        self.assertFalse(self.fake.calls)

    def test_status_and_jobs_show_exact_api_model_and_task(self):
        self.source()
        value = self.chat.submit(self.identifier, REQUEST, str(uuid.uuid4()))
        processes = {}
        for index, (lane, model) in enumerate((("gemini", "gemini-2.5-pro"), ("minimax", "MiniMax-M2.7"))):
            claim = queue.claim(self.root, lane)
            pid = 7200 + index
            queue.transition(self.root, claim["id"], claim["claim_token"], "running", pid=pid)
            queue.transition(self.root, claim["id"], claim["claim_token"], "executing", model=model)
            processes[pid] = dict(pid=pid, ppid=1, command="python3 /code/dispatch_worker.py " + claim["id"],
                                  process_state="S", elapsed_seconds=12)
        with patch("live_status_snapshot.process_table", return_value=processes):
            status = operational_reply(self.root, "server", "status")
            jobs = build_jobs_view(self.root)
        for model in ("gemini-2.5-pro", "MiniMax-M2.7"):
            self.assertIn(model, status)
            self.assertIn(model, json.dumps(jobs["working"]))
        self.assertEqual(len(jobs["working"]), 2)
        self.assertIn("Whole-repo audit", status)
        self.assertIn("test-case drafts", status)

    def test_forbidden_provider_and_acknowledgement_fallback(self):
        self.source()
        value = self.chat.submit(self.identifier, "Use Gemini and Grok for ongoing jobs", str(uuid.uuid4()))
        self.assertIn("never Grok", value["messages"][-1]["content"])
        self.assertEqual(len(queue.tasks(self.root)), 1)
        for reply in ("Got it! Gemini and MiniMax are ready", "I've assigned both to the jobs."):
            guarded = enforce(self.root, REQUEST, dict(content=reply, provider="gemini"))
            self.assertIn("haven't assigned", guarded)
        for text in ("Are Gemini and MiniMax useful for ongoing jobs?", "Don't use Gemini for ongoing work",
                     "Remember Gemini pricing", "Use Gemini to research queues"):
            self.assertIsNone(requested_workers(text))
        for text in ("Remember to use Gemini and MiniMax for ongoing work", "Remember, we can use Gemini and MiniMax"):
            self.assertEqual(requested_workers(text), ["gemini", "minimax"])

    def test_natural_task_types_queue_on_requested_api_workers(self):
        for text, kind in (("Use Gemini to audit the whole repo", "audit"),
                           ("Use Gemini to plan Web Bob improvements", "planning"),
                           ("Use Gemini to research durable queue designs", "research"),
                           ("Use MiniMax to write test cases for queue recovery", "test-writing"),
                           ("Use MiniMax to grade eval results for Web Bob", "eval-grading")):
            with self.subTest(text=text):
                value = self.chat.submit(self.identifier, text, str(uuid.uuid4()))
                row = queue.tasks(self.root)[value["messages"][-1]["task_id"]]
                self.assertEqual(row["kind"], kind)

    def test_multiple_project_api_reports_do_not_get_coding_instructions(self):
        value = self.chat.submit(self.identifier, "Use Gemini to research Web Bob and WebJam", str(uuid.uuid4()))
        rows = [queue.tasks(self.root)[key] for key in value["messages"][-1]["task_ids"]]
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertEqual(row["kind"], "research")
            self.assertIn("reviews/", row["prompt"])
            self.assertNotIn("assigned worktree", row["prompt"])
