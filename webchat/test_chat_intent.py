"""Regressions for Jeff's multi-project push and stale hold incident."""
import json
import uuid
from unittest.mock import patch

from app import Chat
from chat_intent import projects
from providers import Providers
from reply_authority import enforce
from task_dispatch import task_queue as queue
from test_webchat import Fixture

PRIORITY = "Ok prioritize making Web Bob better, then WebJam, then AdoptIQ, then Storyboard."
PUSH = "Now push everything to the max and fix anything you find along the way."
HOLD = ("Hold off on any coding jobs or service restarts for Web Bob. Bob has Codex fixing job pickup right now, "
        "and two fixes at once will clash. You can keep answering questions and reporting status, "
        "but don't queue, start, or restart anything for Web Bob until I say go.")
NAMES = ["Web Bob", "WebJam", "AdoptIQ", "StoryBoard"]


class IntentTests(Fixture):
    def test_literal_project_push_saves_scoped_publication_authority(self):
        receipt = self.submit("push WebJam and AdoptIQ")["messages"][-1]
        rows = [queue.tasks(self.root)[identifier] for identifier in receipt["task_ids"]]
        self.assertEqual({row["publish_project"] for row in rows}, {"WebJam", "AdoptIQ"})
        single = self.submit("push WebJam")["messages"][-1]
        self.assertEqual(queue.tasks(self.root)[single["task_id"]]["publish_project"], "WebJam")
        local = self.submit("Improve WebJam")["messages"][-1]
        self.assertIsNone(queue.tasks(self.root)[local["task_id"]]["publish_project"])

    def submit(self, text, request_id=None, **kwargs):
        value = self.chat.submit(self.identifier, text, request_id or str(uuid.uuid4()), **kwargs)
        self.wait()
        return self.chat.history(self.identifier) if self.identifier in self.chat.conversations else value

    def reload(self):
        self.chat.close()
        self.chat = Chat(self.folder, self.root, self.fake)

    def ready(self, *lanes):
        (self.root / "conductor/lanes.json").write_text(json.dumps({lane: dict(state="ready", active=0) for lane in lanes}))

    def test_exact_live_push_creates_two_jobs_and_releases_only_named_holds(self):
        self.ready("codex", "cursor")
        self.submit("hold")
        request = str(uuid.uuid4())
        receipt = self.submit("push WebJam and AdoptIQ", request)["messages"][-1]
        rows = list(queue.tasks(self.root).values())
        self.assertEqual([row["title"] for row in rows], ["WebJam", "AdoptIQ"])
        self.assertEqual(set(receipt["task_ids"]), {row["id"] for row in rows})
        self.assertEqual({row["kind"] for row in rows}, {"coding"})
        self.assertNotIn("hold", receipt["content"].lower())
        self.reload()
        self.submit("push WebJam and AdoptIQ", request)
        self.assertEqual(len(queue.tasks(self.root)), 2)
        self.assertIn("On hold", self.submit("fix Web Bob login")["messages"][-1]["content"])
        self.assertFalse(self.fake.calls)

    def test_exact_live_going_question_uses_server_status_without_generation(self):
        answer = self.submit("is it going now?")["messages"][-1]
        self.assertEqual(answer["provider"], "state")
        self.assertIn("are idle", answer["content"])
        self.assertFalse(queue.tasks(self.root))
        self.assertFalse(self.fake.calls)

    def test_incident_two_turn_request_persists_one_real_job_per_project(self):
        self.ready("codex", "cursor", "claude", "gemini", "minimax")
        self.submit(PRIORITY)
        self.assertFalse(queue.tasks(self.root))
        self.reload()
        request = str(uuid.uuid4())
        value = self.submit(PUSH, request)
        receipt = value["messages"][-1]
        rows = list(queue.tasks(self.root).values())
        self.assertEqual([row["title"] for row in rows], NAMES)
        self.assertEqual([row["requested_worker"] for row in rows], ["codex", "cursor", "codex", "cursor"])
        self.assertEqual({row["kind"] for row in rows}, {"coding"})
        self.assertEqual(set(receipt["task_ids"]), {row["id"] for row in rows})
        self.assertEqual(len(receipt["content"].splitlines()), 4)
        self.assertTrue((self.root / "conductor/state/queue.jsonl").is_file())
        for row in rows:
            self.assertEqual(projects(row["prompt"]), [row["title"]])
            self.assertEqual(row["status"], "queued")
            self.assertIn(row["title"], receipt["content"])
            self.assertIn(row["requested_worker"].title(), receipt["content"])
            self.assertIn(row["id"], receipt["content"])
        self.submit(PUSH, request)
        self.reload()
        self.submit(PUSH, request)
        self.assertEqual(len(queue.tasks(self.root)), 4)
        self.assertFalse(self.fake.calls)

    def test_inline_request_deduplicates_aliases_and_go_uses_saved_priorities(self):
        receipt = self.submit("Push everything to the max: WebBob, WebJam, AdoptIQ, StoryBoard, web bob.")["messages"][-1]
        self.assertEqual(len(receipt["task_ids"]), 4)
        self.identifier = self.chat.new_conversation()["id"]
        self.submit(PRIORITY)
        receipt = self.submit("go")["messages"][-1]
        self.assertEqual(len(receipt["task_ids"]), 4)
        self.assertNotIn("task_ids", self.submit("go")["messages"][-1])
        self.assertEqual(len(queue.tasks(self.root)), 8)

    def test_named_go_dispatches_current_project_plan_once(self):
        self.submit(HOLD)
        self.submit(PRIORITY)
        self.reload()
        request = str(uuid.uuid4())
        text = "Go ahead with Web Bob, WebJam, AdoptIQ and StoryBoard."
        receipt = self.submit(text, request)["messages"][-1]
        rows = list(queue.tasks(self.root).values())
        self.assertEqual([row["title"] for row in rows], NAMES)
        self.assertEqual(set(receipt["task_ids"]), {row["id"] for row in rows})
        self.assertFalse(self.chat.history(self.identifier)["intent_state"]["holds"])
        self.reload()
        self.submit(text, request)
        self.assertNotIn("task_ids", self.submit(text)["messages"][-1])
        self.assertEqual(len(queue.tasks(self.root)), 4)

    def test_named_resume_only_accepts_a_matching_saved_task(self):
        self.submit("Hold WebJam")
        self.submit("Fix WebJam login")
        self.submit("Resume Web Bob")
        self.assertFalse(queue.tasks(self.root))
        self.assertIn("WebJam", self.chat.history(self.identifier)["intent_state"]["holds"])
        receipt = self.submit("Please resume WebJam.")["messages"][-1]
        row = queue.tasks(self.root)[receipt["task_id"]]
        self.assertEqual(row["prompt"], "Fix WebJam login")
        self.assertFalse(self.chat.history(self.identifier)["intent_state"]["holds"])
        self.identifier = self.chat.new_conversation()["id"]
        self.submit(PRIORITY)
        self.submit("Go ahead with Web Bob")
        self.assertEqual(len(queue.tasks(self.root)), 1)

    def test_analysis_spreads_across_free_compatible_workers_and_real_claims_update_receipt(self):
        self.ready("claude", "gemini", "minimax", "codex", "cursor")
        receipt = self.submit("Compare Web Bob, WebJam, AdoptIQ and StoryBoard using this evidence: each has one queued task.")["messages"][-1]
        rows = [queue.tasks(self.root)[identifier] for identifier in receipt["task_ids"]]
        self.assertEqual(len({row["requested_worker"] for row in rows}), 4)
        for row in rows:
            claim = queue.claim(self.root, row["requested_worker"], identifier=row["id"])
            self.assertIsNotNone(claim)
            queue.transition(self.root, row["id"], claim["claim_token"], "running")
        self.chat.reconcile_tasks()
        updated = self.chat.history(self.identifier)["messages"][-1]
        self.assertEqual(updated["content"], receipt["content"])
        self.assertEqual(updated["action_card"]["state"], "running")
        self.assertTrue(all(task["status"] == "running" for task in updated["action_card"]["tasks"]))

    def test_busy_lane_and_existing_claim_do_not_get_free_worker_preference(self):
        self.ready("codex", "cursor")
        existing = queue.enqueue(self.root, "other", "busy", "Fix a bug", worker="codex", kind="coding")
        queue.claim(self.root, "codex", identifier=existing["id"])
        receipt = self.submit("Fix Web Bob and WebJam")["messages"][-1]
        first = queue.tasks(self.root)[receipt["task_ids"][0]]
        self.assertEqual(first["requested_worker"], "cursor")
        board = self.root / "conductor/lanes.json"
        board.write_text(json.dumps({"codex": dict(state="busy"), "cursor": dict(state="ready")}))
        receipt = self.submit("Fix AdoptIQ and StoryBoard")["messages"][-1]
        self.assertEqual({queue.tasks(self.root)[job]["requested_worker"] for job in receipt["task_ids"]}, {"cursor"})

    def test_project_batch_partial_enqueue_recovers_frozen_plan_once(self):
        original = queue.enqueue
        calls = []
        def fail_second(*args, **kwargs):
            calls.append(1)
            if len(calls) == 2:
                raise OSError("interrupted append")
            return original(*args, **kwargs)
        with patch.object(queue, "enqueue", side_effect=fail_second):
            with self.assertRaises(OSError):
                self.submit("Push everything to the max: Web Bob, WebJam, AdoptIQ, StoryBoard")
        rows = list(queue.tasks(self.root).values())
        self.assertEqual(len(rows), 1)
        self.assertIsNone(queue.claim(self.root, rows[0]["requested_worker"]))
        self.assertNotIn("task_ids", self.chat.conversations[self.identifier]["messages"][-1])
        self.ready("cursor")
        self.reload()
        self.assertEqual(len(queue.tasks(self.root)), 4)
        self.assertEqual(len(self.chat.history(self.identifier)["messages"][-1]["task_ids"]), 4)
        self.assertEqual({row["requested_worker"] for row in queue.tasks(self.root).values()}, {"codex", "cursor"})

    def test_project_batch_initial_save_failure_has_no_queue_effect(self):
        with patch.object(self.chat, "save", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.submit("Fix Web Bob and WebJam")
        self.assertFalse(queue.tasks(self.root))

    def test_hold_is_scoped_durable_and_resume_dispatches_waiting_work_once(self):
        self.submit(HOLD)
        self.assertIn("Web Bob", self.chat.history(self.identifier)["intent_state"]["holds"])
        self.reload()
        blocked = self.submit("Fix Web Bob login")["messages"][-1]
        self.assertIn("On hold", blocked["content"])
        self.assertFalse(queue.tasks(self.root))
        self.submit("Fix WebJam login")
        # Work on another project must not erase the waiting Web Bob request.
        self.assertIn("Web Bob", self.chat.history(self.identifier)["intent_state"]["holds"])
        self.reload()
        request = str(uuid.uuid4())
        receipt = self.submit("Okay, please resume.", request)["messages"][-1]
        self.assertIn("task_id", receipt)
        self.assertFalse(self.chat.history(self.identifier)["intent_state"]["holds"])
        self.submit("Okay, please resume.", request)
        self.reload()
        self.assertFalse(self.chat.history(self.identifier)["intent_state"]["holds"])
        self.assertEqual(len(queue.tasks(self.root)), 2)
        self.assertNotIn("hold", self.submit("Are we still on hold?")["messages"][-1]["content"].lower())

    def test_go_clears_hold_without_replaying_old_jobs_and_rehold_is_explicit(self):
        self.submit(HOLD)
        self.submit("go")
        self.assertFalse(self.chat.history(self.identifier)["intent_state"]["holds"])
        self.assertFalse(queue.tasks(self.root))
        self.submit("Hold off on Web Bob again.")
        self.assertIn("Web Bob", self.chat.history(self.identifier)["intent_state"]["holds"])
        self.assertNotIn("task_id", self.submit("fix Web Bob login")["messages"][-1])
        self.submit("go ahead and fix Web Bob login")
        self.assertEqual(len(queue.tasks(self.root)), 1)

    def test_hold_preserves_current_offer_for_go(self):
        value = self.chat.conversations[self.identifier]
        value["messages"].append(dict(id=str(uuid.uuid4()), role="assistant", status="done", content="I can review PR #161."))
        self.chat.save(value)
        self.submit("hold")
        self.reload()
        receipt = self.submit("go")["messages"][-1]
        self.assertEqual(queue.tasks(self.root)[receipt["task_id"]]["prompt"], "review PR #161")

    def test_global_hold_scoped_release_and_explicit_release_with_no_duplicates(self):
        self.submit("Pause all work.")
        self.submit("Resume Web Bob.")
        self.assertIn("task_id", self.submit("Fix Web Bob login")["messages"][-1])
        self.assertNotIn("task_id", self.submit("Fix WebJam login")["messages"][-1])
        self.submit("The hold is lifted. Bob already started WebJam #161, AdoptIQ #26, StoryBoard #47, and Shelf #10 on Claude, so don't start duplicates.")
        self.assertFalse(self.chat.history(self.identifier)["intent_state"]["holds"])
        self.assertEqual(len(queue.tasks(self.root)), 1)

    def test_historical_user_directives_migrate_once_and_assistant_holds_are_ignored(self):
        value = self.chat.conversations[self.identifier]
        value.pop("intent_state")
        for role, content in (("user", HOLD), ("assistant", "On hold."), ("user", "go"),
                              ("assistant", "Your earlier hold still applies."), ("user", PRIORITY)):
            value["messages"].append(dict(id=str(uuid.uuid4()), role=role, status="done", content=content))
        self.chat.save(value)
        self.reload()
        state = self.chat.history(self.identifier)["intent_state"]
        self.assertFalse(state["holds"])
        self.assertEqual(state["project_order"], NAMES)
        self.assertFalse(queue.tasks(self.root))
        self.assertEqual(len(self.submit(PUSH)["messages"][-1]["task_ids"]), 4)

    def test_incident_hold_priority_push_is_fresh_authorization(self):
        self.submit(HOLD)
        self.submit(PRIORITY)
        receipt = self.submit(PUSH)["messages"][-1]
        self.assertEqual(len(receipt["task_ids"]), 4)
        self.assertFalse(self.chat.history(self.identifier)["intent_state"]["holds"])
        self.assertNotIn("hold", receipt["content"].lower())

    def test_questions_negations_quotes_and_old_go_do_not_change_permissions_or_dispatch(self):
        self.submit(HOLD)
        for text in ("Is it going now?", "Don't resume yet", 'What does "go" mean?',
                     "Don't push everything to the max: Web Bob, WebJam", "Should we push everything to the max?",
                     'Jeff said "resume" yesterday.', "Explain max mode for WebJam and AdoptIQ", "Go was my earlier instruction."):
            self.submit(text)
            self.assertIn("Web Bob", self.chat.history(self.identifier)["intent_state"]["holds"])
        self.assertFalse(queue.tasks(self.root))

    def test_missing_project_context_asks_without_creating_generic_max_tasks(self):
        receipt = self.submit(PUSH)["messages"][-1]
        self.assertEqual(receipt["content"], "Which projects should I work on?")
        self.assertFalse(queue.tasks(self.root))

    def test_push_without_targets_preserves_saved_permissions(self):
        for hold in (HOLD, "Pause all work."):
            with self.subTest(hold=hold):
                self.identifier = self.chat.new_conversation()["id"]
                self.submit(hold)
                before = self.chat.history(self.identifier)["intent_state"]
                receipt = self.submit(PUSH)["messages"][-1]
                self.assertEqual(receipt["content"], "Which projects should I work on?")
                self.reload()
                self.assertEqual(self.chat.history(self.identifier)["intent_state"], before)
                self.submit("Prioritize Web Bob")
                before = self.chat.history(self.identifier)["intent_state"]
                receipt = self.submit("Push everything to the max except Web Bob")["messages"][-1]
                self.assertEqual(receipt["content"], "Which projects should I work on?")
                self.reload()
                self.assertEqual(self.chat.history(self.identifier)["intent_state"], before)
                self.assertFalse(queue.tasks(self.root))

    def test_project_exclusions_and_single_saved_project_keep_scope(self):
        self.submit(PRIORITY)
        receipt = self.submit("Push everything to the max except Web Bob")["messages"][-1]
        self.assertEqual([queue.tasks(self.root)[job]["title"] for job in receipt["task_ids"]], NAMES[1:])
        self.identifier = self.chat.new_conversation()["id"]
        self.submit("Prioritize Web Bob")
        receipt = self.submit("Push everything to the max")["messages"][-1]
        row = queue.tasks(self.root)[receipt["task_id"]]
        self.assertEqual(row["kind"], "coding")
        self.assertEqual(projects(row["prompt"]), ["Web Bob"])

    def test_new_hold_defers_saved_unqueued_intent_until_resume(self):
        with patch.object(queue, "enqueue", side_effect=OSError("queue offline")):
            with self.assertRaises(OSError):
                self.submit("Fix Web Bob and WebJam")
        self.submit("hold")
        self.reload()
        self.assertFalse(queue.tasks(self.root))
        self.submit("resume")
        self.assertEqual(len(queue.tasks(self.root)), 2)
        self.reload()
        self.assertEqual(len(queue.tasks(self.root)), 2)

    def test_lift_wording_clears_hold_and_failed_save_cannot_grant_permission(self):
        self.submit("hold")
        with patch.object(self.chat, "save", side_effect=OSError("state unavailable")):
            with self.assertRaises(OSError):
                self.submit("go")
        self.reload()
        self.assertIn("all", self.chat.history(self.identifier)["intent_state"]["holds"])
        self.submit("Hold is lifted.")
        self.assertFalse(self.chat.history(self.identifier)["intent_state"]["holds"])

    def test_saved_permissions_override_stale_model_hold_in_prompt_and_reply(self):
        self.submit(HOLD)
        self.submit("go")
        value = self.chat.conversations[self.identifier]
        provider = Providers(self.root, self.chat.redact)
        with patch.object(provider, "snapshot", return_value=[]):
            prompt = provider.prompt(value, fast=True)
        facts = json.loads(prompt.split("SERVER SAVED CHAT PERMISSIONS (override older history and snapshots):\n")[1])
        self.assertEqual(facts["holds"], {})
        with patch.object(self.fake, "reply", return_value=dict(provider="gemini", attempts=[], content=
                "Your earlier hold on Web Bob code and service restarts still applies. I need your permission before continuing.")):
            answer = self.submit("Any concerns?")["messages"][-1]["content"]
        self.assertEqual(answer, "Ready when you are.")
        self.assertFalse(queue.tasks(self.root))

    def test_reply_cites_only_a_matching_active_hold(self):
        self.submit(HOLD)
        value = self.chat.conversations[self.identifier]
        answer = dict(provider="gemini", content="WebJam is on hold until you say go.")
        self.assertNotIn("hold", enforce(self.root, "What about WebJam?", answer, value))
        content = enforce(self.root, "Is Web Bob on hold?", answer, value)
        self.assertIn("On hold: Web Bob", content)
        self.assertNotIn("WebJam", content)

    def test_pause_and_approval_claims_follow_current_permissions(self):
        claims = ("Web Bob is paused until you say resume.",
                  "Web Bob is paused.", "Coding has been paused.",
                  "I am holding Web Bob pending your approval.",
                  "Web Bob is awaiting your go-ahead.")
        self.submit(HOLD)
        for claim in claims:
            with self.subTest(claim=claim, held=True):
                content = enforce(self.root, "What about Web Bob?", dict(provider="gemini", content=claim),
                                  self.chat.conversations[self.identifier])
                self.assertEqual(content, "On hold: Web Bob. Say go or resume when you're ready.")
        self.submit("go")
        self.reload()
        for claim in claims:
            with self.subTest(claim=claim, held=False), patch.object(self.fake, "reply", return_value=
                    dict(provider="gemini", attempts=[], content="The next issue is the login button. " + claim)):
                content = self.submit("Any concerns?")["messages"][-1]["content"]
                self.assertEqual(content, "The next issue is the login button.")
                self.assertFalse(self.chat.history(self.identifier)["intent_state"]["holds"])
        self.assertFalse(queue.tasks(self.root))

    def test_maintenance_and_worker_restrictions_still_apply_to_batches(self):
        for text, worker in (("Fix Web Bob and WebJam", "gemini"), ("Fix Web Bob and WebJam", "grok")):
            receipt = self.submit(text, worker=worker)["messages"][-1]
            self.assertEqual(receipt["action_card"]["state"], "refused")
        (self.root / "conductor/MAINTENANCE").touch()
        receipt = self.submit("Fix Web Bob and WebJam")["messages"][-1]
        self.assertEqual(receipt["action_card"]["state"], "refused")
        self.assertFalse(queue.tasks(self.root))
