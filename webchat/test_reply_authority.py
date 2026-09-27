import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from reply_authority import enforce, operational_reply
from test_worker_activity import PS, SCREENS
from worker_activity import parse_processes


class AuthorityTests(unittest.TestCase):
    def setUp(self):
        for name in ("_screen_sessions", "process_table"):
            sampler = patch("live_status_snapshot." + name, return_value={})
            sampler.start()
            self.addCleanup(sampler.stop)

    def test_model_cannot_confirm_a_queue_write(self):
        for text in ("I've added this job to the builder inbox.", "The job I queued is still running.",
                     "I queued a council pass.", "Started on Claude — job abc123.",
                     "I've queued it.", "Claude is working on it.", "I started the review.",
                     "Done — job abc123 is running.", "Job abc123 has been created.",
                     "You're all set — Claude has your task.", "Claude’s on it."):
            with self.subTest(text=text):
                answer = enforce(Path('/unused'), "Ok going now?", dict(content=text, provider="gemini"))
                self.assertEqual(answer, "What would you like me to work on?")

    def test_plain_answers_and_job_explanations_are_unchanged(self):
        for text in ("Got it — I’ll keep it short.", "Hi Jeff!", "A lease expires; a lock needs to be released.",
                     "Jobs wait in the queue until a worker is free.", "I can review PR #161.",
                     "A job is queued when every worker is busy.",
                     "The video is paused. Press play to continue.",
                     "Jobs can be paused before they start.",
                     "Here are the details:\n\n- First fact.\n- Second fact."):
            with self.subTest(text=text):
                self.assertEqual(enforce(Path('/unused'), "Tell me more", dict(content=text, provider="gemini")), text)

    def test_guard_keeps_the_answer_and_removes_only_the_false_claim(self):
        for claim in ("I've queued a task.", "Started on Claude — job abc123.",
                      "No server-confirmed job was created by this reply. Send `start a job: <task>` to create a tracked job."):
            with self.subTest(claim=claim):
                answer = enforce(Path('/unused'), "Please be brief", dict(content="Got it — I’ll keep it short.\n\n" + claim, provider="gemini"))
                self.assertEqual(answer, "Got it — I’ll keep it short.")

    def test_style_preference_never_gets_an_unsolicited_status_report(self):
        answer = enforce(Path('/unused'), "Keep replies short and friendly.",
                         dict(content="Hey! All quiet — no jobs running, ledger's synced. Nothing to report right now.", provider="claude"))
        self.assertEqual(answer, "Got it.")

    def test_no_work_notices_do_not_leak_into_casual_replies(self):
        for notice in ("No jobs running.", "No task has been queued.", "Nothing was started."):
            answer = enforce(Path('/unused'), "Hi Bob", dict(content="Hi Jeff! " + notice, provider="claude"))
            self.assertEqual(answer, "Hi Jeff!")

    def test_identity_and_health_are_derived_from_server_not_model(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch("live_status_snapshot._screen_sessions", return_value={}):
                answer = enforce(root, "How everything going. We using all resources now?",
                                 dict(provider="gemini", content="Cursor is handling our chat; Gemini and MiniMax are still failing."))
        self.assertIn("Gemini — no recent reply verified", answer)
        self.assertNotIn("Answering provider:", answer)
        self.assertNotIn("still failing", answer)
        self.assertNotIn("Cursor is handling", answer)

    def test_exact_progress_followup_uses_workers_instead_of_provider_empty_queue_claim(self):
        with tempfile.TemporaryDirectory() as folder, \
                patch("live_status_snapshot._screen_sessions", return_value=SCREENS), \
                patch("live_status_snapshot.process_table", return_value=parse_processes(PS)):
            root = Path(folder)
            (root / "conductor").mkdir()
            (root / "conductor/jobs.jsonl").write_text('{"job_id":"shelf-load-1659","state":"harvested"}\n')
            for text in ("is it going now?", "Ok great is it moving along now?", "Is anything running?", "Are things making progress?", "What's running?",
                         "Status without internal IDs or raw diagnostics, please"):
                with self.subTest(text=text):
                    answer = enforce(root, text, dict(provider="gemini", content=
                        "Nothing is running. All lanes are ready. Use `start a job: task`."))
                    self.assertIn("4 workers are running", answer)
                    self.assertIn("Projects push — Claude (opus) — running for 24 min", answer)
                    self.assertIn("Web Bob clean — Codex (gpt-fixture) — running for 18 min", answer)
                    self.assertIn("Web Bob clean 2 — Codex — running for 12 min", answer)
                    self.assertIn("Web Bob MiniMax — Codex — running for 8 min", answer)
                    for hidden in ("None", "shelf-load-1659", "lane-", "History:", "provider:", "start a job:", "All lanes"):
                        self.assertNotIn(hidden, answer)

    def test_internal_details_and_answering_model_are_available_when_requested(self):
        with tempfile.TemporaryDirectory() as folder, \
                patch("live_status_snapshot._screen_sessions", return_value=SCREENS), \
                patch("live_status_snapshot.process_table", return_value=parse_processes(PS)):
            answer = operational_reply(Path(folder), "gemini", "Status with screen names and PIDs; who is answering?")
        self.assertIn("lane-projects-push, 103", answer)
        self.assertIn("Gemini answered this message.", answer)
        self.assertNotIn("None", answer)

    def test_unverified_screens_and_unavailable_checks_never_claim_idle(self):
        with tempfile.TemporaryDirectory() as folder:
            for screens, processes in ((SCREENS, {}), ({}, None), (None, {})):
                with self.subTest(screens=screens, processes=processes), \
                        patch("live_status_snapshot._screen_sessions", return_value=screens), \
                        patch("live_status_snapshot.process_table", return_value=processes):
                    answer = operational_reply(Path(folder), "server")
                    self.assertNotIn("I don't see active work", answer)
                    self.assertNotIn("Yes", answer)
                    self.assertNotIn("None", answer)
                    self.assertIn("confirm", answer)

    def test_special_job_syntax_is_removed_regardless_of_how_model_phrases_it(self):
        for notice in ("Type `start a job: fix login`.", "Please submit using the start a job: prefix.",
                       "To get things moving, please use `start a job: <task description>`."):
            answer = enforce(Path('/unused'), "Hi Bob", dict(content="Hi Jeff! " + notice, provider="gemini"))
            self.assertEqual(answer, "Hi Jeff!")

    def test_removing_a_footer_preserves_answer_formatting(self):
        useful = "A lease expires. A lock needs to be released.\n\n- First fact.\n- Second fact."
        answer = enforce(Path('/unused'), "Tell me more", dict(provider="gemini", content=useful +
                         "\n\nNo server-confirmed job was created by this reply. Send `start a job: <task>` to create a tracked job."))
        self.assertEqual(answer, useful)

    def test_casual_chat_does_not_expand_a_model_claim_into_a_status_report(self):
        answer = enforce(Path('/unused'), "Hi Bob", dict(provider="gemini", content=
                         "Hi Jeff! Cursor is handling our chat; Gemini and MiniMax are still failing."))
        self.assertEqual(answer, "Hi Jeff!")
