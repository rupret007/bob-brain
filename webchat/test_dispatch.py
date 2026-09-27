"""Chat dispatch contracts: saved intent, routing and restart-safe result outbox."""
import json
import time
import uuid
from unittest.mock import patch

from app import Chat
from task_dispatch import parse_work, task_queue as queue
from test_webchat import Fixture


class ChatDispatchTests(Fixture):
    def test_plain_review_phrases_start_real_jobs(self):
        for text, worker in (("review PR 161", "auto"), ("Claude review PR #161", "claude")):
            reply = self.chat.submit(self.identifier, text, str(uuid.uuid4()))
            row = queue.tasks(self.root)[reply["messages"][-1]["task_id"]]
            self.assertEqual(row["requested_worker"], worker)
            self.assertIn("161", row["prompt"])
        self.assertFalse(self.fake.calls)

    def submit(self, message="Review the supplied evidence: queued jobs have no consumer.", worker=None):
        return self.chat.submit(self.identifier, message, str(uuid.uuid4()), worker=worker)

    def complete_task(self, row=None, result="The queue needs a polling consumer and a durable result outbox."):
        row = row or next(iter(queue.tasks(self.root).values()))
        claim = queue.claim(self.root, row["requested_worker"] if row["requested_worker"] != "auto" else "gemini")
        queue.transition(self.root, claim["id"], claim["claim_token"], "running")
        return queue.transition(self.root, claim["id"], claim["claim_token"], "succeeded", result=result)

    def test_explicit_job_and_natural_work_dispatch_without_an_extra_confirmation(self):
        for text in ("start a job: review the task evidence", "Can you fix the queue consumer?", "Please analyze this: 12 + 18", "Use Gemini to review this invariant: one claim per worker"):
            with self.subTest(text=text):
                value = self.submit(text)
                self.assertIn("task_id", value["messages"][-1])
                self.assertNotIn("pending_job", value)
        self.assertEqual(len(queue.tasks(self.root)), 4)
        self.assertEqual(self.fake.calls, [])

    def test_live_incident_conversational_work_request_is_durable(self):
        value = self.submit("Ok figure out what’s wrong with Gemini and minimax")
        receipt = value["messages"][-1]
        row = queue.tasks(self.root)[receipt["task_id"]]
        self.assertEqual(row["status"], "queued")
        self.assertIn(row["id"], receipt["content"])
        self.assertFalse(self.fake.calls)
        claim = queue.claim(self.root, "gemini")
        queue.transition(self.root, claim["id"], claim["claim_token"], "running")
        self.chat.reconcile_tasks()
        receipt = self.chat.history(self.identifier)["messages"][-1]
        self.assertEqual(receipt["content"], "Started on Gemini — job " + row["id"] + ".")
        self.assertEqual(receipt["action_card"]["worker"], "gemini")

    def test_explicit_file_write_uses_a_tool_worker(self):
        value = self.submit("start a job: write hello to /tmp/wb-proof.txt", worker="claude")
        row = queue.tasks(self.root)[value["messages"][-1]["task_id"]]
        self.assertEqual(row["kind"], "artifact")
        self.assertIsNotNone(queue.claim(self.root, "claude"))

    def test_api_file_requests_are_refused_before_saving_dispatch_intent(self):
        for worker in ("minimax", "gemini"):
            for prompt in ("write hello to /tmp/wb-proof.txt", "Review services/dispatch_worker.py"):
                with self.subTest(worker=worker, prompt=prompt):
                    value = self.submit("start a job: " + prompt, worker=worker)
                    message = value["messages"][-1]
                    self.assertEqual(message["action_card"]["state"], "refused")
                    self.assertIn("API-only", message["content"])
                    self.assertNotIn("dispatch_intent", message)
        self.assertFalse(queue.tasks(self.root))

    def test_exact_answer_literal_does_not_turn_a_confirmation_into_coding(self):
        for worker in ("minimax", "gemini"):
            value = self.submit("start a job: write one sentence confirming you ran, into your answer. "
                                "Include the exact phrase 'WEBBOB-MINIMAX-FIX-0927 " + worker + "'.", worker=worker)
            row = queue.tasks(self.root)[value["messages"][-1]["task_id"]]
            self.assertEqual(row["kind"], "analysis")
            self.assertEqual(row["requested_worker"], worker)

    def test_file_inspection_auto_routes_to_a_worker_with_read_tools(self):
        value = self.submit("start a job: Review services/dispatch_worker.py")
        row = queue.tasks(self.root)[value["messages"][-1]["task_id"]]
        self.assertEqual(row["kind"], "inspection")
        for worker in ("minimax", "gemini", "claude"):
            self.assertIsNone(queue.claim(self.root, worker))
        self.assertIsNotNone(queue.claim(self.root, "cursor"))

    def test_polite_file_requests_keep_the_required_worker_capabilities(self):
        for prompt in ("Can you please review services/dispatch_worker.py", "Okay, could you inspect services/dispatch_worker.py?"):
            with self.subTest(prompt=prompt):
                value = self.submit(prompt)
                row = queue.tasks(self.root)[value["messages"][-1]["task_id"]]
                self.assertEqual(row["kind"], "inspection")
                value = self.submit(prompt, worker="minimax")
                self.assertEqual(value["messages"][-1]["action_card"]["state"], "refused")
                self.assertNotIn("dispatch_intent", value["messages"][-1])

    def test_answer_rejection_delivers_one_failed_result_after_restart(self):
        self.submit(worker="minimax")
        row = queue.claim(self.root, "minimax")
        queue.transition(self.root, row["id"], row["claim_token"], "running")
        queue.transition(self.root, row["id"], row["claim_token"], "rejected",
                         error="Answer did not complete the task: unrelated answer",
                         rejected_result="Here are some gardening tips.", acceptance={"accepted": False})
        replacement = Chat(self.folder, self.root, self.fake)
        try:
            for _ in range(3):
                replacement.reconcile_tasks()
            messages = replacement.history(self.identifier)["messages"]
            results = [message for message in messages if message.get("task_status")]
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["task_status"], "failed")
            self.assertIn("failed after 1 attempts on minimax", results[0]["content"])
            self.assertIn("unrelated answer", results[0]["content"])
            self.assertNotIn("finished on", results[0]["content"])
            card = next(message["action_card"] for message in messages if message.get("action_card"))
            self.assertEqual(card["state"], "blocked")
            self.assertIsNotNone(queue.tasks(self.root)[row["id"]]["delivered_at"])
        finally:
            replacement.close()

    def test_max_mode_api_file_package_is_rejected_before_any_enqueue(self):
        value = self.submit("Max mode: review.\n[minimax] Read services/worker.py.\n[gemini] Analyze supplied evidence.")
        self.assertEqual(value["messages"][-1]["action_card"]["state"], "refused")
        self.assertIn("API-only", value["messages"][-1]["content"])
        self.assertFalse(queue.tasks(self.root))

    def test_natural_requests_have_short_server_confirmed_receipts(self):
        for text, prompt, worker in (
                ("fix X", "fix X", "auto"),
                ("review PR #161", "review PR #161", "auto"),
                ("have Claude do Y", "do Y", "claude"),
                ("Please have Claude review PR #161", "review PR #161", "claude"),
                ("Okay, can you please fix the login button?", "can you please fix the login button?", "auto")):
            with self.subTest(text=text):
                receipt = self.submit(text)["messages"][-1]
                row = queue.tasks(self.root)[receipt["task_id"]]
                self.assertEqual((row["prompt"], row["requested_worker"]), (prompt, worker))
                label = "Queued for Claude" if worker == "claude" else "Queued"
                self.assertEqual(receipt["content"], label + " — job " + row["id"] + ".")
        self.assertEqual(len(queue.tasks(self.root)), 5)
        self.assertFalse(self.fake.calls)

    def offer(self, text):
        with patch.object(self.fake, "reply", return_value=dict(content=text, provider="gemini", attempts=[])):
            self.submit("What could you help with next?")
            self.wait()

    def test_go_resolves_only_the_current_concrete_offer(self):
        self.offer("I can have Claude review PR #161.")
        receipt = self.submit("go")["messages"][-1]
        row = queue.tasks(self.root)[receipt["task_id"]]
        self.assertEqual((row["prompt"], row["requested_worker"]), ("review PR #161", "claude"))
        # A new request ID with another "go" must not duplicate the accepted task.
        answer = self.submit("go")["messages"][-1]
        self.assertEqual(answer["content"], "What would you like me to work on?")
        self.assertEqual(len(queue.tasks(self.root)), 1)

    def test_go_recovers_a_saved_proposal_after_chat_reload(self):
        self.offer("Shall I review PR #161?")
        replacement = Chat(self.folder, self.root, self.fake)
        try:
            value = replacement.submit(self.identifier, "go ahead", str(uuid.uuid4()))
            self.assertEqual(queue.tasks(self.root)[value["messages"][-1]["task_id"]]["prompt"], "review PR #161")
        finally:
            replacement.close()

    def test_go_understands_a_natural_offer_with_a_confirmation_question(self):
        for text in ("Happy to take a look at PR #162 — want me to prep a review job for it?",
                     "I can offer to take a look at PR #162 whenever you want — just say go and I'll queue it.",
                     "I can review PR #161. Want me to?", "I could review PR #161 — shall I go ahead?"):
            with self.subTest(text=text):
                self.offer(text)
                receipt = self.submit("go")["messages"][-1]
                self.assertTrue(queue.tasks(self.root)[receipt["task_id"]]["prompt"].startswith("review PR #16"))

    def test_polite_go_accepts_a_single_saved_proposal(self):
        self.offer("I can review PR #161.")
        receipt = self.submit("Okay, please go ahead.")["messages"][-1]
        self.assertEqual(queue.tasks(self.root)[receipt["task_id"]]["prompt"], "review PR #161")

    def test_go_accepts_an_existing_pending_job(self):
        conversation = self.chat.conversations[self.identifier]
        conversation["pending_job"] = "fix the login button"
        self.chat.save(conversation)
        receipt = self.submit("go")["messages"][-1]
        self.assertEqual(queue.tasks(self.root)[receipt["task_id"]]["prompt"], "fix the login button")

    def test_ambiguous_requests_ask_one_question_without_queueing(self):
        for text in ("go", "go ahead", "do it", "yes please", "fix", "fix it", "have Claude", "have Claude do it", "I need you to do more"):
            with self.subTest(text=text):
                receipt = self.submit(text)["messages"][-1]
                self.assertEqual(receipt["content"], "What would you like me to work on?")
                self.assertNotIn("task_id", receipt)
        self.assertFalse(queue.tasks(self.root))
        self.assertFalse(self.fake.calls)

    def test_go_does_not_choose_between_options_or_use_old_context(self):
        for offer in ("I can review PR #161 or fix the login button.", "I can fix it.",
                      "I can review PR #161. I can also fix the login button."):
            self.offer(offer)
            self.assertNotIn("task_id", self.submit("go")["messages"][-1])
        self.offer("I can review PR #161.")
        self.submit("Thanks!")
        self.wait()
        self.assertNotIn("task_id", self.submit("go")["messages"][-1])
        self.assertFalse(queue.tasks(self.root))

    def test_chat_preferences_and_negated_requests_stay_in_chat(self):
        for text in ("Keep replies short", "Make your replies shorter and friendlier", "Hi Bob", "Thanks!",
                     "Don't fix X", "Could you explain what a queue is?", "What does review PR #161 mean?"):
            with self.subTest(text=text):
                self.submit(text)
                self.wait()
                expected = "Got it." if text in ("Keep replies short", "Make your replies shorter and friendlier") else "A saved reply."
                self.assertEqual(self.chat.history(self.identifier)["messages"][-1]["content"], expected)
        self.assertFalse(queue.tasks(self.root))

    def test_enqueue_failure_has_no_success_receipt_or_job_id(self):
        with patch.object(queue, "enqueue", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.submit("have Claude review PR #161")
        message = self.chat.conversations[self.identifier]["messages"][-1]
        self.assertNotIn("task_id", message)
        self.assertNotIn("Queued", message["content"])
        self.assertNotIn("Started", message["content"])
        self.assertFalse(queue.tasks(self.root))

    def test_worker_routing_and_grok_rejected(self):
        self.submit(worker="cursor-agent")
        self.assertEqual(next(iter(queue.tasks(self.root).values()))["requested_worker"], "cursor")
        for text, worker in (("Use grok to review the task", None), ("Review this task", "grok"), ("Fix the service", "gemini")):
            value = self.submit(text, worker)
            self.assertEqual(value["messages"][-1]["action_card"]["state"], "refused")
        self.assertEqual(len(queue.tasks(self.root)), 1)

    def test_questions_remain_chat_and_prohibited_action_never_queues(self):
        self.assertEqual(parse_work("What is the difference between a lease and a lock?")[0], None)
        value = self.submit("start a job: merge #158")
        self.assertEqual(value["messages"][-1]["action_card"]["state"], "refused")
        self.assertFalse(queue.tasks(self.root))
        self.assertNotIn("Queued", self.chat.history(self.identifier)["messages"][-1]["content"])

    def test_duplicate_request_creates_one_task(self):
        request = str(uuid.uuid4())
        for _ in range(3):
            self.chat.submit(self.identifier, "Review the supplied task evidence", request)
        self.assertEqual(len(queue.tasks(self.root)), 1)
        self.assertEqual(len(self.chat.history(self.identifier)["messages"]), 2)

    def test_failed_initial_save_never_enqueues(self):
        with patch.object(self.chat, "save", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.submit()
        self.assertEqual(queue.tasks(self.root), {})

    def test_crash_after_intent_save_is_recovered_on_restart(self):
        with patch.object(queue, "enqueue", side_effect=OSError("interrupted queue write")):
            with self.assertRaises(OSError):
                self.submit()
        self.assertFalse(queue.tasks(self.root))
        replacement = Chat(self.folder, self.root, self.fake)
        try:
            self.assertEqual(len(queue.tasks(self.root)), 1)
            self.assertIn("task_id", replacement.history(self.identifier)["messages"][-1])
        finally:
            replacement.close()

    def test_queue_commit_then_ack_save_failure_does_not_duplicate(self):
        real_save = self.chat.save
        calls = []
        def save(value):
            calls.append(1)
            if len(calls) == 2:
                raise OSError("crash after enqueue")
            real_save(value)
        with patch.object(self.chat, "save", side_effect=save):
            with self.assertRaises(OSError):
                self.submit()
        self.chat.reconcile_tasks()
        self.assertEqual(len(queue.tasks(self.root)), 1)
        self.assertIn("task_id", self.chat.history(self.identifier)["messages"][-1])

    def test_result_survives_restart_and_posts_to_original_chat_once(self):
        self.submit(worker="gemini")
        original = self.identifier
        second = self.chat.new_conversation()["id"]
        task = self.complete_task()
        replacement = Chat(self.folder, self.root, self.fake)
        try:
            for _ in range(3):
                replacement.reconcile_tasks()
            messages = replacement.history(original)["messages"]
            results = [m for m in messages if m.get("task_status") == "succeeded"]
            self.assertEqual(len(results), 1)
            self.assertIn(task["result"], results[0]["content"])
            self.assertEqual(replacement.history(second)["messages"], [])
            self.assertIsNotNone(queue.tasks(self.root)[task["id"]]["delivered_at"])
        finally:
            replacement.close()

    def test_chat_write_failure_keeps_outbox_pending(self):
        self.submit()
        task = self.complete_task()
        with patch.object(self.chat, "save", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.chat.reconcile_tasks()
        self.assertIsNone(queue.tasks(self.root)[task["id"]]["delivered_at"])
        self.chat.reconcile_tasks()
        self.assertEqual(self.chat.history(self.identifier)["messages"][-1]["task_status"], "succeeded")

    def test_delivery_ack_failure_does_not_duplicate_saved_answer(self):
        self.submit()
        self.complete_task()
        with patch.object(queue, "delivered", side_effect=OSError("outbox unavailable")):
            with self.assertRaises(OSError):
                self.chat.reconcile_tasks()
        self.chat.reconcile_tasks()
        self.assertEqual(sum(bool(m.get("task_status")) for m in self.chat.history(self.identifier)["messages"]), 1)

    def test_async_result_waits_for_active_chat_reply(self):
        self.submit()
        self.complete_task()
        self.fake.hold.clear()
        self.chat.submit(self.identifier, "Explain worker lease semantics briefly.", str(uuid.uuid4()))
        self.chat.reconcile_tasks()
        self.assertFalse(any(m.get("task_status") for m in self.chat.conversations[self.identifier]["messages"]))
        self.fake.hold.set()
        self.wait()
        self.chat.reconcile_tasks()
        messages = self.chat.history(self.identifier)["messages"]
        self.assertEqual(messages[-2]["content"], "A saved reply.")
        self.assertEqual(messages[-1]["task_status"], "succeeded")

    def test_legacy_accepted_webbob_row_migrates_once(self):
        prompts = self.root / "next-prompts"
        prompts.mkdir()
        (prompts / "webchat-old.md").write_text("# Old task\n\n## Task\n\nReview the supplied evidence.\n\n## Rules\nDraft only.")
        value = self.chat.conversations[self.identifier]
        value["messages"].append(dict(id=str(uuid.uuid4()), request_id=str(uuid.uuid4()), role="assistant", status="done", content="Queued", created_at=time.time(), action_card={"state": "queued", "queue_id": "webchat-old.md"}))
        self.chat.save(value)
        self.chat.migrate_legacy_tasks()
        self.chat.migrate_legacy_tasks()
        rows = list(queue.tasks(self.root).values())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["conversation_id"], self.identifier)
        self.assertEqual(rows[0]["source_file"], "webchat-old.md")

    def test_exhausted_retries_report_failure_in_chat(self):
        self.submit(worker="gemini")
        for attempt in range(5):
            now = time.time() + attempt * 100
            row = queue.claim(self.root, "gemini", now=now)
            queue.transition(self.root, row["id"], row["claim_token"], "retry", now=now+1, error="Provider unavailable")
        self.chat.reconcile_tasks()
        result = self.chat.history(self.identifier)["messages"][-1]
        self.assertEqual(result["task_status"], "failed")
        self.assertIn("5 attempts", result["content"])

    def test_max_mode_enqueues_one_row_per_idle_lane_with_shared_group_id(self):
        health = {lane: {"state": "ready"} for lane in ("codex", "cursor", "gemini", "minimax")}
        (self.root / "conductor/lanes.json").write_text(json.dumps(health))
        value = self.submit("Go to the max: review this queue protocol for correctness, testing, scaling and recovery.")
        rows = list(queue.tasks(self.root).values())
        self.assertEqual(len(rows), 4)
        self.assertEqual({r["requested_worker"] for r in rows}, set(health))
        self.assertEqual(len({r["group_id"] for r in rows}), 1)
        self.assertEqual(len({r["prompt"] for r in rows}), 4)
        group = value["messages"][-1]["group_id"]
        for row in rows[:-1]:
            self.complete_task(row, result="Evidence from " + row["requested_worker"])
        self.chat.reconcile_tasks()
        self.assertFalse(any(m.get("task_status") for m in self.chat.history(self.identifier)["messages"]))
        self.complete_task(rows[-1], result="Recovery findings")
        for _ in range(3):
            self.chat.reconcile_tasks()
        results = [m for m in self.chat.history(self.identifier)["messages"] if m.get("task_status")]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["group_id"], group)
        self.assertEqual(len(results[0]["subtasks"]), 4)
        self.assertTrue(all(r["delivered_at"] for r in queue.tasks(self.root).values()))

    def test_max_mode_explicit_packages_and_recovery_from_partial_enqueue(self):
        prompt = "Max mode: review this supplied evidence.\n[codex] Check invariants.\n[claude] Critique assumptions.\n[mini] Run services/test_services.py."
        real = queue.enqueue
        count = []
        def enqueue(*args, **kwargs):
            count.append(1)
            if len(count) == 2:
                raise OSError("Interrupted group append")
            return real(*args, **kwargs)
        with patch.object(queue, "enqueue", side_effect=enqueue):
            with self.assertRaises(OSError):
                self.submit(prompt)
        self.assertIsNone(queue.claim(self.root, "codex"))
        self.chat.reconcile_tasks()
        rows = list(queue.tasks(self.root).values())
        self.assertEqual(len(rows), 3)
        self.assertEqual({r["kind"] for r in rows}, {"analysis", "local"})
        self.assertIsNotNone(queue.claim(self.root, "codex"))

    def test_max_mode_delivery_ack_crash_posts_one_merged_answer(self):
        self.submit("Max mode: review evidence.\n[gemini] Check scaling.\n[minimax] Check recovery.")
        for row in queue.tasks(self.root).values():
            self.complete_task(row)
        with patch.object(queue, "delivered", side_effect=OSError("Acknowledgement failed")):
            with self.assertRaises(OSError):
                self.chat.reconcile_tasks()
        replacement = Chat(self.folder, self.root, self.fake)
        try:
            results = [m for m in replacement.history(self.identifier)["messages"] if m.get("task_status")]
            self.assertEqual(len(results), 1)
        finally:
            replacement.close()

    def test_max_mode_chat_save_failure_keeps_every_result_pending(self):
        self.submit("Max mode: review evidence.\n[gemini] Check scaling.\n[minimax] Check recovery.")
        for row in queue.tasks(self.root).values():
            self.complete_task(row)
        with patch.object(self.chat, "save", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.chat.reconcile_tasks()
        self.assertTrue(all(row["delivered_at"] is None for row in queue.tasks(self.root).values()))
        self.chat.reconcile_tasks()
        self.chat.reconcile_tasks()
        answers = [m for m in self.chat.history(self.identifier)["messages"] if m.get("task_status")]
        self.assertEqual(len(answers), 1)
        self.assertTrue(all(row["delivered_at"] for row in queue.tasks(self.root).values()))

    def test_max_mode_rejects_grok_and_keeps_code_packages_independent(self):
        value = self.submit("Max mode: review evidence.\n[grok] Critique.\n[codex] Check.")
        self.assertEqual(value["messages"][-1]["action_card"]["state"], "refused")
        self.assertFalse(queue.tasks(self.root))
        self.submit("Max mode: implement a new task grouping feature and its regression tests.")
        rows = {r["requested_worker"]: r for r in queue.tasks(self.root).values()}
        self.assertEqual(set(rows), set(queue.WORKERS))
        self.assertEqual({worker for worker, row in rows.items() if row["kind"] == "coding"}, {"codex", "cursor"})
        self.assertIn("production files only", rows["codex"]["prompt"])
        self.assertIn("test files only", rows["cursor"]["prompt"])
        self.assertEqual(rows["mini"]["kind"], "local")
