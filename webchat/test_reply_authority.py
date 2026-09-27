import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from reply_authority import enforce


class AuthorityTests(unittest.TestCase):
    def test_model_cannot_confirm_a_queue_write(self):
        for text in ("I've added this job to the builder inbox.", "The job I queued is still running.",
                     "I queued a council pass."):
            with self.subTest(text=text):
                answer = enforce(Path('/unused'), "Ok going now?", dict(content=text, provider="gemini"))
                self.assertIn("No server-confirmed job", answer)

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
