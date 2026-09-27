import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from reply_authority import enforce


class AuthorityTests(unittest.TestCase):
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
        self.assertIn("Answering provider: gemini", answer)
        self.assertIn("gemini=unchecked", answer)
        self.assertNotIn("still failing", answer)
        self.assertNotIn("Cursor is handling", answer)

    def test_removing_a_footer_preserves_answer_formatting(self):
        useful = "A lease expires. A lock needs to be released.\n\n- First fact.\n- Second fact."
        answer = enforce(Path('/unused'), "Tell me more", dict(provider="gemini", content=useful +
                         "\n\nNo server-confirmed job was created by this reply. Send `start a job: <task>` to create a tracked job."))
        self.assertEqual(answer, useful)

    def test_casual_chat_does_not_expand_a_model_claim_into_a_status_report(self):
        answer = enforce(Path('/unused'), "Hi Bob", dict(provider="gemini", content=
                         "Hi Jeff! Cursor is handling our chat; Gemini and MiniMax are still failing."))
        self.assertEqual(answer, "Hi Jeff!")
