#!/usr/bin/env python3
"""Acceptance tests for Web Bob gap closures (memory, research, screenshots)."""
import http.client
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
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
    PROFILE_MAX_BYTES,
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
    _prune_captures,
    _trim_profile_lines,
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
    def test_memory_overlay_preserves_main_checkout_and_invalidates_context(self):
        from providers import Providers
        base = self.root / 'bob-brain/memory/profile.md'
        base.parent.mkdir(parents=True)
        base.write_text('Existing baseline memory\n')
        provider = Providers(self.root, lambda text: text)
        self.chat.providers = provider
        provider.snapshot()
        provider.snapshot(lite=True)
        self.submit('remember that Instinct must never send replies automatically')
        self.submit('yes, save memory')
        self.assertEqual(base.read_text(), 'Existing baseline memory\n')
        for lite in (False, True):
            memory = next(r for r in provider.snapshot(lite=lite) if r['path'] == 'conductor/webchat/memory/profile.md')
            self.assertIn('Instinct must never send', memory['text'])

    def test_texting_or_version_turn_revokes_pending_memory(self):
        for interruption in ('texting help', 'what version are you?'):
            with self.subTest(interruption=interruption):
                self.submit('remember that stale memory must not be written')
                self.submit(interruption)
                reply = self.submit('yes, save memory')['messages'][-1]
                self.assertEqual(reply['provider'], 'state')
                self.assertIn('No memory is waiting', reply['content'])
                self.assertFalse((self.folder / 'memory/profile.md').exists())

    def test_remember_requires_confirmation_then_appends_profile(self):
        fact = "I prefer to use Claude for creative writing tasks"
        first = self.submit(f"remember that {fact}")
        assistant = first["messages"][-1]
        self.assertEqual(assistant["action_card"]["state"], "confirm")
        self.assertIn(fact, assistant["content"])
        profile = self.root / "conductor/webchat/memory/profile.md"
        self.assertFalse(profile.exists())
        second = self.submit("yes, save memory")
        self.assertIn("Saved to durable memory", second["messages"][-1]["content"])
        body = profile.read_text(encoding="utf-8")
        self.assertIn(fact, body)
        self.assertRegex(body, r"\[\d{4}-\d{2}-\d{2}\]")

    def test_memory_dismiss_cancels_pending_save(self):
        self.submit("remember that I like tea")
        result = self.submit("cancel")
        self.assertIn("cancelled", result["messages"][-1]["content"].lower())
        self.assertEqual(result["messages"][-1]["action_card"]["state"], "cancelled")
        profile = self.root / "conductor/webchat/memory/profile.md"
        self.assertFalse(profile.exists())

    def test_stale_memory_proposal_is_rejected(self):
        first = self.submit("remember that first fact")
        stale_id = first["messages"][-1]["action_card"]["proposal_id"]
        self.submit("remember that second fact")
        result = self.submit(f"yes, save memory proposal {stale_id}")
        self.assertIn("stale", result["messages"][-1]["content"].lower())
        self.assertEqual(result["messages"][-1]["action_card"]["state"], "refused")
        profile = self.root / "conductor/webchat/memory/profile.md"
        self.assertFalse(profile.exists())

    def test_memory_turn_skipped_for_non_auto_provider(self):
        conversation = self.chat.conversations[self.identifier]
        request_id = str(uuid.uuid4())
        conversation["pending_memory"] = "secret"
        result = self.chat.bob_gaps_memory_turn(conversation, "yes, save memory", request_id, provider="codex")
        self.assertIsNone(result)
        self.assertEqual(conversation.get("pending_memory"), "secret")

    def test_memory_save_oserror_surfaces_in_chat(self):
        self.submit("remember that disk full scenario")
        with patch("app.append_profile_memory", side_effect=OSError("disk full")):
            result = self.submit("yes, save memory")
        assistant = result["messages"][-1]
        self.assertIn("could not save memory", assistant["content"].lower())
        self.assertEqual(assistant["action_card"]["state"], "refused")
        self.assertEqual(self.chat.conversations[self.identifier].get("pending_memory"), "disk full scenario")


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
    def test_search_rejects_oversized_and_nonobject_responses(self):
        for body in (b'x' * (1024 * 1024 + 1), b'[]'):
            response = MagicMock()
            response.__enter__.return_value = response
            response.read.return_value = body
            with self.assertRaises(ValueError):
                web_search('Python', opener=lambda *args, **kwargs: response)
            response.read.assert_called_once_with(1024 * 1024 + 1)

    def test_parsers(self):
        self.assertEqual(parse_remember("remember that I like tea"), "I like tea")
        self.assertTrue(needs_web_search("what was the score of the Mets game last night?"))
        self.assertEqual(parse_screenshot("take a screenshot of the Calculator app"), "Calculator app")

    def test_needs_web_search_negative_cases(self):
        for query in ('What is my favorite color?', 'What was my previous preference?', 'What is in my uploaded file?'):
            self.assertFalse(needs_web_search(query))
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
            self.assertIn("test fact", (root / "conductor/webchat/memory/profile.md").read_text())

    def test_append_profile_memory_trims_when_oversized(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "conductor/webchat/memory/profile.md"
            path.parent.mkdir(parents=True)
            path.write_text("x" * (PROFILE_MAX_BYTES + 100) + "\n", encoding="utf-8")
            append_profile_memory(root, "newest")
            body = path.read_text(encoding="utf-8")
            self.assertLessEqual(len(body.encode("utf-8")), PROFILE_MAX_BYTES + 200)
            self.assertIn("newest", body)

    def test_append_profile_memory_concurrent_appends_not_lost(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            thread_count = 12
            barrier = threading.Barrier(thread_count)
            errors = []

            def worker(index):
                try:
                    barrier.wait(timeout=5)
                    append_profile_memory(root, f"concurrent fact {index}")
                except Exception as exc:  # pragma: no cover - surfaced via errors list
                    errors.append(exc)

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(thread_count)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(10)

            self.assertEqual(errors, [])
            body = (root / "conductor/webchat/memory/profile.md").read_text(encoding="utf-8")
            for i in range(thread_count):
                self.assertIn(f"concurrent fact {i}", body)
            self.assertEqual(len(body.splitlines()), thread_count)

    def test_trim_profile_lines_keeps_newest_under_budget(self):
        lines = [f"line-{i:05d}\n" for i in range(5000)]
        max_bytes = sum(len(entry.encode("utf-8")) for entry in lines[-100:])
        trimmed = _trim_profile_lines(lines, max_bytes=max_bytes)
        self.assertEqual(trimmed, lines[-100:])
        self.assertLessEqual(sum(len(e.encode("utf-8")) for e in trimmed), max_bytes)

    def test_trim_profile_lines_noop_when_under_budget(self):
        lines = ["a\n", "b\n", "c\n"]
        self.assertEqual(_trim_profile_lines(lines, max_bytes=1000), lines)

    def test_append_profile_memory_lock_open_failure_raises_oserror(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lock_path = root / "conductor/webchat/memory/profile.lock"
            lock_path.mkdir(parents=True)
            with self.assertRaises(OSError) as ctx:
                append_profile_memory(root, "should not save")
            self.assertIn(str(lock_path), str(ctx.exception))

    def test_prune_captures_enforces_max_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for index in range(5):
                path = folder / f"{index:016x}.png"
                path.write_bytes(b"png")
            now = time.time()
            for index, path in enumerate(sorted(folder.glob("*.png"))):
                stamp = now - (5 - index)
                os.utime(path, (stamp, stamp))
            _prune_captures(folder, max_count=2, max_age_days=365)
            remaining = list(folder.glob("*.png"))
            self.assertEqual(len(remaining), 2)

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
                read=lambda size: json.dumps({"AbstractText": "ok", "RelatedTopics": []}).encode(),
            )

        web_search("test query", opener=fake_opener)
        self.assertIn("WebBob", captured["ua"])


if __name__ == "__main__":
    unittest.main()
