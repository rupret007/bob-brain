#!/usr/bin/env python3
"""Acceptance tests for Web Bob gap closures (memory, research, screenshots)."""
import http.client
import json
import subprocess
import sys
import tempfile
import threading
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import URLError

from app import Chat, Server
from bob_gaps import (
    MEMORY_CANCEL,
    MEMORY_CONFIRM,
    MEMORY_CONFIRM_PROPOSAL,
    append_profile_memory,
    capture_screenshot,
    format_web_search_reply,
    needs_web_search,
    parse_memory_confirm,
    parse_remember,
    parse_screenshot,
    resolve_capture_path,
    web_search,
    _macos_window_id,
)


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

    def test_memory_dismiss_cancels_pending_save(self):
        self.submit("remember that I like tea")
        result = self.submit("cancel")
        self.assertIn("cancelled", result["messages"][-1]["content"].lower())
        self.assertEqual(result["messages"][-1]["action_card"]["state"], "cancelled")
        profile = self.root / "bob-brain/memory/profile.md"
        self.assertFalse(profile.exists())

    def test_stale_memory_proposal_is_rejected(self):
        first = self.submit("remember that first fact")
        stale_id = first["messages"][-1]["action_card"]["proposal_id"]
        self.submit("remember that second fact")
        result = self.submit(f"yes, save memory proposal {stale_id}")
        self.assertIn("stale", result["messages"][-1]["content"].lower())
        self.assertEqual(result["messages"][-1]["action_card"]["state"], "refused")
        profile = self.root / "bob-brain/memory/profile.md"
        self.assertFalse(profile.exists())

    def test_memory_turn_skipped_for_non_auto_provider(self):
        conversation = self.chat.conversations[self.identifier]
        request_id = str(uuid.uuid4())
        conversation["pending_memory"] = "secret"
        result = self.chat.bob_gaps_memory_turn(conversation, "yes, save memory", request_id, provider="codex")
        self.assertIsNone(result)
        self.assertEqual(conversation.get("pending_memory"), "secret")


class WebSearchGapTests(GapFixture):
    def test_mets_score_triggers_search_with_source_link(self):
        with patch(
            "app.web_search",
            return_value={"answer": "Mets beat the Phillies 4-2.", "source": "https://example.com/mets-score", "heading": "Mets"},
        ):
            result = self.submit("what was the score of the Mets game last night?")
        reply = result["messages"][-1]["content"]
        self.assertIn("4-2", reply)
        self.assertIn("https://example.com/mets-score", reply)

    def test_web_search_network_error_surfaces_in_chat(self):
        with patch("app.web_search", side_effect=URLError("network down")):
            result = self.submit("what was the score of the Mets game last night?")
        self.assertIn("could not complete a web search", result["messages"][-1]["content"].lower())


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

    def test_screenshot_failure_surfaces_in_chat(self):
        with patch("app.capture_screenshot", side_effect=RuntimeError("permission denied")):
            result = self.submit("take a screenshot")
        self.assertIn("permission denied", result["messages"][-1]["content"])

    def test_try_bob_gaps_skipped_when_ledger_root_mismatch(self):
        conversation = self.chat.conversations[self.identifier]
        other = self.root / "overlay"
        other.mkdir()
        with patch.object(self.chat, "ledger_root", return_value=other):
            result = self.chat.try_bob_gaps(conversation, "take a screenshot", str(uuid.uuid4()))
        self.assertIsNone(result)


class CaptureApiTests(GapFixture):
    def setUp(self):
        super().setUp()
        self.server = Server(("127.0.0.1", 0), self.chat, "https://mini.example.ts.net")
        self.port = self.server.server_address[1]
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()
        self.origin = "http://127.0.0.1:" + str(self.port)
        self.cookie, self.csrf = "", ""

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join(2)
        super().tearDown()

    def request(self, method, path, auth=True):
        headers = {}
        if auth and self.cookie:
            headers["Cookie"] = self.cookie
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        connection.request(method, path, headers=headers)
        response = connection.getresponse()
        body = response.read()
        status = response.status
        connection.close()
        return status, body

    def login(self):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        connection.request(
            "POST",
            "/login",
            "password=" + self.chat.password,
            {"Content-Type": "application/x-www-form-urlencoded", "Origin": self.origin},
        )
        response = connection.getresponse()
        self.assertEqual(response.status, 303)
        self.cookie = response.getheader("Set-Cookie").split(";", 1)[0]
        response.read()
        connection.close()

    def test_capture_endpoint_serves_png_and_rejects_invalid_id(self):
        self.login()
        capture_id = "a1b2c3d4e5f67890"
        png = self.root / "conductor/webchat/captures" / f"{capture_id}.png"
        png.parent.mkdir(parents=True, exist_ok=True)
        png.write_bytes(b"\x89PNG\r\n\x1a\n")
        status, body = self.request("GET", f"/api/captures/{capture_id}")
        self.assertEqual(status, 200)
        self.assertTrue(body.startswith(b"\x89PNG"))
        self.assertEqual(self.request("GET", "/api/captures/not-valid")[0], 404)
        self.assertEqual(self.request("GET", "/api/captures/" + ("f" * 16))[0], 404)


class UnitTests(unittest.TestCase):
    def test_parsers(self):
        self.assertEqual(parse_remember("remember that I like tea"), "I like tea")
        self.assertTrue(needs_web_search("what was the score of the Mets game last night?"))
        self.assertEqual(parse_screenshot("take a screenshot of the Calculator app"), "Calculator app")

    def test_needs_web_search_negative_cases(self):
        self.assertFalse(needs_web_search(""))
        self.assertFalse(needs_web_search("   "))
        self.assertFalse(needs_web_search("hello there"))
        self.assertFalse(needs_web_search("x" * 601))

    def test_memory_regexes(self):
        self.assertTrue(MEMORY_CANCEL.match("never mind"))
        self.assertTrue(MEMORY_CANCEL.match("cancel memory"))
        self.assertTrue(MEMORY_CONFIRM.match("yes, save memory"))
        match = MEMORY_CONFIRM_PROPOSAL.match("yes, save memory proposal 11111111-2222-3333-4444-555555555555")
        self.assertTrue(match)
        self.assertEqual(match.group(1), "11111111-2222-3333-4444-555555555555")

    def test_parse_memory_confirm(self):
        self.assertEqual(parse_memory_confirm("yes, save memory"), (True, None))
        confirmed, proposal = parse_memory_confirm(
            "yes, save memory proposal aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        )
        self.assertTrue(confirmed)
        self.assertEqual(proposal, "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        self.assertEqual(parse_memory_confirm("no thanks"), (False, None))

    def test_append_profile_memory_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            when = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)
            line = append_profile_memory(root, "test fact", when=when)
            expected = when.astimezone().strftime("%Y-%m-%d")
            self.assertIn(f"[{expected}]", line)
            self.assertIn("test fact", (root / "bob-brain/memory/profile.md").read_text())

    def test_format_web_search_reply_tolerates_missing_keys(self):
        self.assertEqual(format_web_search_reply({}), "")
        reply = format_web_search_reply({"heading": "Title", "source": "https://example.com"})
        self.assertIn("Title", reply)
        self.assertIn("https://example.com", reply)

    def test_resolve_capture_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertIsNone(resolve_capture_path(root, "../etc/passwd"))
            capture_id = "0123456789abcdef"
            path = root / "conductor/webchat/captures" / f"{capture_id}.png"
            path.parent.mkdir(parents=True)
            path.write_bytes(b"png")
            self.assertEqual(resolve_capture_path(root, capture_id), path)

    @patch("bob_gaps.sys.platform", "linux")
    def test_capture_screenshot_requires_macos(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError) as ctx:
                capture_screenshot(Path(tmp))
            self.assertIn("macOS", str(ctx.exception))

    @patch("bob_gaps.sys.platform", "darwin")
    def test_macos_window_id_escapes_injection_payload(self):
        malicious = 'Finder" & do shell script "touch /tmp/pwned" & "'
        with patch("bob_gaps.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="")
            self.assertIsNone(_macos_window_id(malicious))
        script = run.call_args[0][0][-1]
        self.assertNotIn('do shell script "touch', script)
        self.assertIn('\\"', script)
        self.assertEqual(run.call_args[0][0][:2], ["osascript", "-e"])

    @patch("bob_gaps.sys.platform", "darwin")
    def test_web_search_sets_user_agent(self):
        captured = {}

        def fake_opener(request, timeout=20):
            captured["ua"] = request.headers.get("User-agent") or request.headers.get("User-Agent")
            return MagicMock(
                __enter__=lambda self: self,
                __exit__=lambda *args: None,
                read=lambda: json.dumps({"AbstractText": "ok", "RelatedTopics": []}).encode(),
            )

        web_search("test query", opener=fake_opener)
        self.assertIn("WebBob", captured["ua"])


if __name__ == "__main__":
    unittest.main()
