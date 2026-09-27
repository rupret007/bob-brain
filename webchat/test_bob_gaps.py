#!/usr/bin/env python3
"""Acceptance tests for Web Bob gap closures (memory, research, screenshots)."""
import json
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from app import Chat, Server
from bob_gaps import append_profile_memory, needs_web_search, parse_remember, parse_screenshot


class FakeProviders:
    def health(self, conversation_id=None):
        return {"providers": {}, "order": [], "fast_order": []}


class GapFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.folder = self.root / "conductor/webchat"
        self.folder.mkdir(parents=True)
        self.fake = FakeProviders()
        self.chat = Chat(self.folder, self.root, self.fake)
        self.identifier = self.chat.conversation_list()["conversations"][0]["id"]
        for name in ("_screen_sessions", "process_table"):
            sampler = patch("live_status_snapshot." + name, return_value={})
            sampler.start()
            self.addCleanup(sampler.stop)

    def tearDown(self):
        self.chat.close()
        self.tmp.cleanup()

    def submit(self, text):
        request_id = str(uuid.uuid4())
        return self.chat.submit(self.identifier, text, request_id)


class MemoryGapTests(GapFixture):
    def test_remember_requires_confirmation_then_appends_profile(self):
        fact = "I prefer to use Claude for creative writing tasks"
        first = self.submit(f"remember that {fact}")
        assistant = first["messages"][-1]
        self.assertEqual(assistant["action_card"]["state"], "confirm")
        self.assertIn(fact, assistant["content"])
        profile = self.root / "bob-brain/memory/profile.md"
        self.assertFalse(profile.exists())
        second = self.submit("yes, save memory")
        self.assertIn("Saved to", second["messages"][-1]["content"])
        body = profile.read_text(encoding="utf-8")
        self.assertIn(fact, body)
        self.assertRegex(body, r"\[\d{4}-\d{2}-\d{2}\]")


class WebSearchGapTests(GapFixture):
    def test_mets_score_triggers_search_with_source_link(self):
        payload = {
            "AbstractText": "Mets beat the Phillies 4-2.",
            "AbstractURL": "https://example.com/mets-score",
            "Heading": "Mets",
            "RelatedTopics": [],
        }

        with patch(
            "app.web_search",
            return_value={"answer": "Mets beat the Phillies 4-2.", "source": "https://example.com/mets-score", "heading": "Mets"},
        ):
            result = self.submit("what was the score of the Mets game last night?")
        reply = result["messages"][-1]["content"]
        self.assertIn("4-2", reply)
        self.assertIn("https://example.com/mets-score", reply)


class ScreenshotGapTests(GapFixture):
    def test_calculator_screenshot_shown_in_chat(self):
        capture_id = "abcd1234ef567890"
        png = self.root / "conductor/webchat/captures" / f"{capture_id}.png"
        png.parent.mkdir(parents=True)
        png.write_bytes(b"\x89PNG\r\n\x1a\n")

        def fake_capture(root, target=None):
            self.assertEqual(target, "calculator app")
            return capture_id, png

        with patch("app.capture_screenshot", side_effect=fake_capture):
            result = self.submit("take a screenshot of the calculator app")
        content = result["messages"][-1]["content"]
        self.assertIn(f"/api/captures/{capture_id}", content)


class UnitTests(unittest.TestCase):
    def test_parsers(self):
        self.assertEqual(parse_remember("remember that I like tea"), "I like tea")
        self.assertTrue(needs_web_search("what was the score of the Mets game last night?"))
        self.assertEqual(parse_screenshot("take a screenshot of the Calculator app"), "Calculator app")

    def test_append_profile_memory_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            when = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)
            line = append_profile_memory(root, "test fact", when=when)
            expected = when.astimezone().strftime("%Y-%m-%d")
            self.assertIn(f"[{expected}]", line)
            self.assertIn("test fact", (root / "bob-brain/memory/profile.md").read_text())


if __name__ == "__main__":
    unittest.main()
