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


class PinnedDeploymentAssignments(SessionFixture):
    def setUp(self):
        super().setUp()
        from build_info import CODE_ROOT
        self.code_root = CODE_ROOT
        self.pins = self.root / "conductor/state"
        self.pins.mkdir(parents=True, exist_ok=True)
        for name in ("webchat", "dispatch"):
            (self.pins / (name + "-code-root")).write_text(str(CODE_ROOT) + "\n")
        # Attempt 0204 had this screen only: no identifiable project lane.
        sampler = patch("live_status_snapshot._screen_sessions", return_value={
            "lane-integrate-deploy-0204": "53678.lane-integrate-deploy-0204"})
        sampler.start()
        self.addCleanup(sampler.stop)

    def test_attempt2_turn_one_dispatches_from_the_matching_release_pins(self):
        from integration_rubric import check_reply, sessions
        from live_status_snapshot import build_live_status_snapshot
        exchange = sessions()[0]["exchanges"][0]
        before = build_live_status_snapshot(self.root)
        self.assertEqual(before["queue_counts"]["queued"], 0)
        self.assertEqual(before["queue_counts"]["claimed"], 0)
        self.assertEqual(before["work_counts"]["running"], 0)
        self.assertEqual(len(before["work"]), 1)
        self.assertIsNone(before["work"][0]["project"])
        started = time.time()
        answer = self.send(exchange["message"])
        records = queue.tasks(self.root)
        after = build_live_status_snapshot(self.root)
        self.assertEqual(check_reply(answer, exchange, self.identifier, started, before, after, records), [])
        self.assertEqual(len(records), 2)
        self.assertEqual(after["work_counts"]["running"], 0)
        for row in records.values():
            self.assertEqual(row["status"], "queued")
            self.assertIsNone(row["source_job_id"])
            self.assertIn("Project: Web Bob", row["prompt"])
            self.assertIn("matching deployment pins", row["prompt"])
            self.assertIn("no current task or worker execution is confirmed", row["prompt"])
            self.assertNotIn("Ongoing task:", row["prompt"])
        self.assertFalse(self.fake.calls)
        self.chat.close()
        self.chat = Chat(self.folder, self.root, self.fake)
        replay = self.chat.submit(self.identifier, exchange["message"], answer["request_id"])["messages"][-1]
        self.assertEqual(replay["task_ids"], answer["task_ids"])
        self.assertEqual(replay["content"], answer["content"])
        self.assertEqual(set(queue.tasks(self.root)), set(records))

    def test_pins_are_context_without_an_open_screen_or_a_claim_of_running_work(self):
        with patch("live_status_snapshot._screen_sessions", return_value={}):
            answer = self.send(SESSIONS[0]["exchanges"][0]["message"])
            self.assertEqual(len(answer.get("task_ids", [])), 2)
            status = self.send("What are you working on?")
        self.assertIn("waiting to run", status["content"])
        self.assertNotIn("running for", status["content"])

    def test_missing_empty_relative_mismatched_and_unreadable_pins_fail_closed(self):
        for name in ("webchat", "dispatch"):
            pin = self.pins / (name + "-code-root")
            for value in (None, "", ".", str(self.root), str(self.root / "missing")):
                with self.subTest(pin=name, value=value):
                    pin.unlink(missing_ok=True)
                    if value is not None:
                        pin.write_text(value)
                    answer = self.send(SESSIONS[0]["exchanges"][0]["message"])
                    self.assertFalse(answer.get("task_ids"))
                    self.assertFalse(queue.tasks(self.root))
                    pin.write_text(str(self.code_root))
            pin.unlink()
            pin.mkdir()
            self.assertIn("couldn't assign", self.send(SESSIONS[0]["exchanges"][0]["message"])["content"])
            pin.rmdir()
            pin.write_text(str(self.code_root))

    def test_pinned_context_respects_project_global_and_partial_release_holds(self):
        for hold, release, permitted in (
            ("Hold off on Web Bob", None, False),
            ("Hold off", None, False),
            ("Hold off", "Resume WebJam", False),
            ("Hold off", "Resume Web Bob", True),
            ("Hold off on WebJam", None, True),
        ):
            with self.subTest(hold=hold, release=release):
                self.identifier = self.chat.new_conversation()["id"]
                self.send(hold)
                if release:
                    self.send(release)
                before = set(queue.tasks(self.root))
                answer = self.send(SESSIONS[0]["exchanges"][0]["message"])
                added = set(queue.tasks(self.root)) - before
                self.assertEqual(len(added), 2 if permitted else 0)
                if permitted:
                    for key in added:
                        self.assertTrue(queue.tasks(self.root)[key]["prompt"].startswith("Project: Web Bob\n"))
                else:
                    self.assertIn("current holds", answer["content"])

    def test_pins_do_not_authorize_other_projects_or_tool_workers(self):
        for text in ("Use Gemini and MiniMax for ongoing WebJam jobs",
                     "Use Codex for ongoing jobs", "Use all LLMs for ongoing jobs"):
            with self.subTest(text=text):
                self.assertIn("couldn't assign", self.send(text)["content"])
                self.assertFalse(queue.tasks(self.root))

    def test_parked_project_holds_survive_the_permitted_webbob_dispatch(self):
        conversation = self.chat.conversations[self.identifier]
        holds = {name: dict(request_id="parked", reason="Keep parked", released_projects=[])
                 for name in ("Barker", "Wildflower")}
        conversation["intent_state"]["holds"] = copy.deepcopy(holds)
        self.chat.save(conversation)
        answer = self.send(SESSIONS[0]["exchanges"][0]["message"])
        self.assertEqual(len(answer.get("task_ids", [])), 2)
        self.assertEqual(self.chat.get(self.identifier)["intent_state"]["holds"], holds)
        for row in queue.tasks(self.root).values():
            self.assertTrue(row["prompt"].startswith("Project: Web Bob\n"))
            self.assertIsNone(row["publish_project"])

    def test_rollback_copy_without_git_evidence_cannot_supply_report_context(self):
        rollback = self.root / "rollback-copy"
        rollback.mkdir()
        for name in ("webchat", "dispatch"):
            (self.pins / (name + "-code-root")).write_text(str(rollback))
        with patch("worker_assignment.CODE_ROOT", rollback):
            self.assertIn("couldn't assign", self.send(SESSIONS[0]["exchanges"][0]["message"])["content"])
        self.assertFalse(queue.tasks(self.root))

    def test_pinned_context_does_not_displace_a_permitted_ongoing_job(self):
        source = queue.enqueue(self.root, "external", "source", "Improve WebJam recording", kind="coding")
        answer = self.send(SESSIONS[0]["exchanges"][0]["message"])
        rows = queue.tasks(self.root)
        self.assertEqual([rows[key]["source_job_id"] for key in answer["task_ids"]], [source["id"], source["id"]])

    def test_pinned_context_still_respects_maintenance_and_provider_unavailability(self):
        maintenance = self.root / "conductor/MAINTENANCE"
        maintenance.touch()
        self.assertIn("maintenance", self.send(SESSIONS[0]["exchanges"][0]["message"])["content"])
        maintenance.unlink()
        for state in ("needs_key", "cooldown", "budget_exhausted"):
            with self.subTest(state=state):
                (self.root / "conductor/lanes.json").write_text(json.dumps({"minimax": {"state": state}}))
                self.assertIn(state.replace("_", " "), self.send(SESSIONS[0]["exchanges"][0]["message"])["content"])
                self.assertFalse(queue.tasks(self.root))


class IntegratedSessions(SessionFixture):
    def seed(self):
        return queue.enqueue(self.root, "external-project-work", str(uuid.uuid4()),
                             "Improve WebJam recording reliability", kind="coding", worker="codex", title="WebJam")

    def test_all_19_captured_messages_in_conversation_order(self):
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
                        elif index == 7:
                            self.assertEqual(answer["content"], "Hi Jeff!")
                            self.assertFalse(identifiers)
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
        self.assertEqual(checked, 19)

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

    def test_observed_active_project_lane_can_supply_missing_prompt_context(self):
        observed = dict(records={}, work=[dict(state="running", worker="codex", project="Web Bob",
                                               title="Web Bob integration", task=None)])
        with patch("worker_assignment.observe_work", return_value=observed):
            answer = self.send("Use Gemini and MiniMax for ongoing jobs")
        records = queue.tasks(self.root)
        self.assertEqual(len(answer["task_ids"]), 2)
        for identifier in answer["task_ids"]:
            self.assertIn("original task prompt was not recorded", records[identifier]["prompt"])
            self.assertIn("Project: Web Bob", records[identifier]["prompt"])
            self.assertIn(identifier, answer["content"])

    def test_frozen_turn_one_with_only_an_unverified_project_lane(self):
        from integration_rubric import check_reply, sessions
        from live_status_snapshot import build_live_status_snapshot
        # Failed attempt 2205: no queued/claimed jobs, no confirmed worker,
        # and these two open screens. Only the review lane identifies a project.
        screens = {"lane-integrate-deploy-2205": "68531.lane-integrate-deploy-2205",
                   "lane-webbob-llm-reviews": "29817.lane-webbob-llm-reviews"}
        exchange = sessions()[0]["exchanges"][0]
        with patch("live_status_snapshot._screen_sessions", return_value=screens):
            before = build_live_status_snapshot(self.root)
            self.assertEqual(before["queue_counts"]["queued"], 0)
            self.assertEqual(before["queue_counts"]["claimed"], 0)
            self.assertEqual(before["work_counts"]["running"], 0)
            self.assertEqual(before["work_counts"]["unverified"], 2)
            started = time.time()
            answer = self.send(exchange["message"])
            records = queue.tasks(self.root)
            after = build_live_status_snapshot(self.root)
            self.assertEqual(check_reply(answer, exchange, self.identifier, started, before, after, records), [])
            self.assertEqual(len(records), 2)
            self.assertEqual(after["work_counts"]["running"], 0)
            for row in records.values():
                self.assertIsNone(row["source_job_id"])
                self.assertEqual(row["status"], "queued")
                self.assertIn("Project: Web Bob", row["prompt"])
                self.assertIn("worker activity is unverified", row["prompt"])
                self.assertNotIn("Ongoing task:", row["prompt"])
            self.assertFalse(self.fake.calls)
        self.chat.close()
        self.chat = Chat(self.folder, self.root, self.fake)
        replay = self.chat.submit(self.identifier, exchange["message"], answer["request_id"])["messages"][-1]
        self.assertEqual(replay["task_ids"], answer["task_ids"])
        self.assertEqual(replay["content"], answer["content"])
        self.assertEqual(set(queue.tasks(self.root)), set(records))

    def test_unverified_project_context_respects_scope_and_api_only_work(self):
        screens = {"lane-webbob-llm-reviews": "29817.lane-webbob-llm-reviews"}
        with patch("live_status_snapshot._screen_sessions", return_value=screens):
            for text in ("Use Gemini and MiniMax for ongoing WebJam jobs",
                         "Use Codex for ongoing jobs", "Use all LLMs for ongoing jobs"):
                with self.subTest(text=text):
                    self.assertIn("couldn't assign", self.send(text)["content"])
                    self.assertFalse(queue.tasks(self.root))
            self.send("Hold off on Web Bob")
            self.assertIn("current holds", self.send(SESSIONS[0]["exchanges"][0]["message"])["content"])
            self.assertFalse(queue.tasks(self.root))

    def test_unverified_lane_fallback_does_not_displace_an_ongoing_job(self):
        source = self.seed()
        with patch("live_status_snapshot._screen_sessions", return_value={"lane-webbob-llm-reviews": "29817.lane-webbob-llm-reviews"}):
            answer = self.send(SESSIONS[0]["exchanges"][0]["message"])
        records = queue.tasks(self.root)
        self.assertEqual([records[key]["source_job_id"] for key in answer["task_ids"]], [source["id"], source["id"]])

    def test_unidentified_screens_and_unassigned_processes_do_not_supply_projects(self):
        from worker_activity import parse_processes
        with patch("live_status_snapshot._screen_sessions", return_value={"lane-integrate-deploy-2205": "68531.lane-integrate-deploy-2205"}), \
                patch("live_status_snapshot.process_table", return_value=parse_processes("40 1 01:00 S codex exec -\n")):
            self.assertIn("couldn't assign", self.send(SESSIONS[0]["exchanges"][0]["message"])["content"])
            self.assertFalse(queue.tasks(self.root))

    def test_health_probes_and_unattributed_processes_are_not_task_execution(self):
        from worker_activity import collect_work, parse_processes
        table = parse_processes("10 1 01:00 S cursor-agent status\n"
                                "20 1 01:00 S codex exec resume --help\n"
                                "30 1 01:00 S claude --version\n"
                                "40 1 01:00 S codex exec -\n")
        rows = collect_work({}, [], table, time.time(), root=self.root)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["worker"], "codex")
        self.assertEqual(rows[0]["state"], "unverified")
        self.assertFalse(rows[0]["assignment_recorded"])
        with patch("live_status_snapshot.process_table", return_value=table):
            reply = self.send("What is working on what?")
        self.assertIn("Codex has CLI activity, but no recorded task", reply["content"])
        self.assertNotIn("running for", reply["content"])
        self.assertNotIn("Worker process", reply["content"])

    def test_verbose_completion_is_concise_with_full_report_available(self):
        from integration_rubric import style_errors
        from jobs_view import result_text
        self.seed()
        answer = self.send("Fix Web Bob queue recovery")
        identifier = answer["task_id"]
        row = queue.claim(self.root, "codex", identifier=identifier)
        queue.transition(self.root, identifier, row["claim_token"], "running")
        report = ("Fixed a verified quiet-hours bypass.\n\nReproduced with a failing test. Tests pass.\n\n"
                  "Changed paths: app.js. test_quiet_hours_js.mjs.\n\nWorktree is clean. No push or deployment.\n" * 10)
        queue.transition(self.root, identifier, row["claim_token"], "succeeded", result=report)
        self.chat.reconcile_tasks()
        completion = self.chat.history(self.identifier)["messages"][-1]
        self.assertFalse(style_errors(completion["content"]))
        self.assertIn("Fixed a verified quiet-hours bypass", completion["content"])
        self.assertIn("/api/jobs/result?id=" + identifier, completion["content"])
        self.assertEqual(result_text(self.root, identifier)["text"], report)
        original = next(m for m in self.chat.get(self.identifier)["messages"] if m["id"] == answer["id"])
        self.assertEqual(original["content"], answer["content"])
