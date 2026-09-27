#!/usr/bin/env python3
"""Offline security, persistence and provider regression tests; no live model calls."""
import http.client
import importlib.util
import io
import json
import os
import stat
import sys
import tempfile
import threading
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from app import Chat, RequestError, Server, password_at, private_write
from handback import append_turn, refresh_summary
from job_queue import parse_confirm, parse_start, queue_draft
from failover import AllDown
from providers import Cancelled, ProviderError, Providers, Redactor, clean_env, parse_codex, parse_cursor, parse_gemini, run

THREAD = "11111111-2222-3333-4444-555555555555"


class FakeProviders:
    def __init__(self):
        self.calls = []
        self.hold = threading.Event()
        self.hold.set()

    def health(self, conversation_id=None):
        return {"providers": {}, "order": [], "fast_order": []}

    def reply(self, conversation, cancel, progress):
        self.calls.append(conversation)
        progress("codex", [])
        while not self.hold.wait(0.01):
            if cancel.is_set():
                raise Cancelled("Reply stopped.")
        return {"content": "A saved reply.", "provider": "codex", "codex_thread_id": THREAD, "attempts": []}


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.folder = self.root / "conductor/webchat"
        self.folder.mkdir(parents=True)
        self.fake = FakeProviders()
        self.chat = Chat(self.folder, self.root, self.fake)
        self.identifier = self.chat.conversation_list()["conversations"][0]["id"]

    def tearDown(self):
        self.fake.hold.set()
        self.chat.close()
        self.tmp.cleanup()

    def wait(self, identifier=None):
        identifier = identifier or self.identifier
        info = self.chat.workers.get(identifier)
        if info:
            info["thread"].join(3)
            self.assertFalse(info["thread"].is_alive())


class StateTests(Fixture):
    def test_password_persistence_permissions_and_symlinks(self):
        self.assertEqual(password_at(self.folder), self.chat.password)
        self.assertGreaterEqual(len(self.chat.password), 32)
        self.assertEqual(stat.S_IMODE((self.folder / ".password").stat().st_mode), 0o600)
        other = self.root / "other"
        other.mkdir()
        (other / ".password").symlink_to(self.folder / ".password")
        with self.assertRaises(OSError):
            password_at(other)

    def test_restart_history_and_exact_thread_continuity(self):
        self.chat.submit(self.identifier, "Remember amber sailboat", str(uuid.uuid4()))
        self.wait()
        self.chat.submit(self.identifier, "What did I ask?", str(uuid.uuid4()))
        self.wait()
        self.assertEqual(self.fake.calls[1]["codex_thread_id"], THREAD)
        restored = Chat(self.folder, self.root, self.fake)
        self.assertEqual(len(restored.history(self.identifier)["messages"]), 4)
        self.assertNotIn("codex_thread_id", restored.history(self.identifier))
        self.assertEqual(restored.conversations[self.identifier]["codex_thread_id"], THREAD)
        self.assertEqual(stat.S_IMODE(restored.state.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((restored.state / (self.identifier + ".json")).stat().st_mode), 0o600)

    def test_duplicate_submission_is_durable_and_does_not_rerun(self):
        request_id = str(uuid.uuid4())
        self.chat.submit(self.identifier, "Hello", request_id)
        self.wait()
        restored = Chat(self.folder, self.root, self.fake)
        restored.submit(self.identifier, "Hello", request_id)
        self.assertEqual(len(self.fake.calls), 1)
        self.assertEqual(len(restored.history(self.identifier)["messages"]), 2)
        with self.assertRaises(RequestError):
            restored.submit(self.identifier, "Different", request_id)

    def test_single_reply_and_cancellation(self):
        self.fake.hold.clear()
        self.chat.submit(self.identifier, "Wait", str(uuid.uuid4()))
        with self.assertRaises(RequestError) as context:
            self.chat.submit(self.identifier, "Duplicate work", str(uuid.uuid4()))
        self.assertEqual(context.exception.status, 409)
        self.chat.stop(self.identifier)
        self.wait()
        self.assertEqual(self.chat.history(self.identifier)["messages"][-1]["status"], "cancelled")
        self.assertNotIn(self.identifier, self.chat.workers)

    def test_restart_interrupts_pending_and_never_replays(self):
        value = self.chat.conversations[self.identifier]
        value["codex_thread_id"] = THREAD
        value["messages"] = [{"role": "assistant", "content": "", "status": "running"}]
        self.chat.save(value)
        restored = Chat(self.folder, self.root, self.fake)
        self.assertEqual(restored.history(self.identifier)["messages"][-1]["status"], "error")
        self.assertIsNone(restored.conversations[self.identifier]["codex_thread_id"])
        self.assertEqual(self.fake.calls, [])

    def test_corrupt_state_fails_instead_of_losing_history(self):
        path = self.chat.state / (self.identifier + ".json")
        path.write_text("broken {")
        with self.assertRaises(ValueError):
            Chat(self.folder, self.root, self.fake)

    def test_secret_is_not_saved_or_forwarded(self):
        with self.assertRaises(RequestError):
            self.chat.submit(self.identifier, "Password is " + self.chat.password, str(uuid.uuid4()))
        self.assertEqual(self.chat.history(self.identifier)["messages"], [])
        self.assertEqual(self.fake.calls, [])
        value = "sk-" + "a" * 25
        self.assertNotIn(value, self.chat.redact(value))

    def test_invalid_unicode_and_failed_write_do_not_wedge_chat(self):
        with self.assertRaises(RequestError):
            self.chat.submit(self.identifier, "\ud800", str(uuid.uuid4()))
        with patch.object(self.chat, "save", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.chat.submit(self.identifier, "Try to save", str(uuid.uuid4()))
        self.assertNotIn(self.identifier, self.chat.workers)
        self.assertEqual(self.chat.history(self.identifier)["messages"], [])
        self.chat.submit(self.identifier, "The next message works", str(uuid.uuid4()))
        self.wait()
        self.assertEqual(self.chat.history(self.identifier)["messages"][-1]["status"], "done")

    def test_missing_report_and_fixed_paths(self):
        with self.assertRaises(RequestError) as context:
            self.chat.report("conductor/STATUS.md")
        self.assertEqual(context.exception.status, 404)
        with self.assertRaises(RequestError):
            self.chat.history("../../.password")


class HTTPTests(Fixture):
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

    def request(self, method, path, data=None, headers=None, auth=True):
        combined = {}
        if auth and self.cookie:
            combined["Cookie"] = self.cookie
        if data is not None:
            combined.update({"Content-Type": "application/json", "Origin": self.origin, "X-CSRF-Token": self.csrf})
            data = json.dumps(data)
        combined.update(headers or {})
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        connection.request(method, path, data, combined)
        response = connection.getresponse()
        body = response.read().decode()
        result = response.status, dict(response.getheaders()), body
        connection.close()
        return result

    def login(self):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        connection.request("POST", "/login", "password=" + self.chat.password,
                           {"Content-Type": "application/x-www-form-urlencoded", "Origin": self.origin})
        response = connection.getresponse()
        self.assertEqual(response.status, 303)
        cookie = response.getheader("Set-Cookie")
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Strict", cookie)
        self.cookie = cookie.split(";", 1)[0]
        response.read()
        connection.close()
        self.csrf = json.loads(self.request("GET", "/api/session")[2])["csrf"]

    def test_login_page_and_every_api_is_private(self):
        code, headers, body = self.request("GET", "/login")
        self.assertEqual(code, 200)
        self.assertIn("password", body)
        self.assertIn("no-store", headers["Cache-Control"])
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        for path in ("/api", "/api/status", "/api/review", "/api/jobs", "/api/conversations", "/api/conversations/" + self.identifier):
            for method in ("GET", "POST"):
                self.assertEqual(self.request(method, path)[0], 401, (method, path))
        self.assertEqual(self.request("GET", "/.password")[0], 404)
        self.assertEqual(self.request("GET", "/static/../../.password")[0], 404)

    def test_login_csrf_host_and_logout(self):
        self.login()
        self.assertEqual(self.request("POST", "/api/conversations", {})[0], 201)
        self.assertEqual(self.request("POST", "/api/conversations", {}, {"X-CSRF-Token": "wrong"})[0], 403)
        self.assertEqual(self.request("POST", "/api/conversations", {}, {"Origin": "https://evil.example"})[0], 403)
        self.assertEqual(self.request("POST", "/api/conversations", {}, {"Sec-Fetch-Site": "cross-site"})[0], 403)
        self.assertEqual(self.request("GET", "/api/status", headers={"Host": "evil.example"})[0], 403)
        self.assertEqual(self.request("POST", "/api/logout", {})[0], 200)
        self.assertEqual(self.request("GET", "/api")[0], 401)

    def test_bad_password_throttles_without_creating_sessions(self):
        for _ in range(10):
            with self.assertRaises(RequestError) as context:
                self.chat.login("wrong")
            self.assertEqual(context.exception.status, 401)
        with self.assertRaises(RequestError) as context:
            self.chat.login("wrong")
        self.assertEqual(context.exception.status, 429)
        self.assertEqual(self.chat.sessions, {})

    def test_cookie_expiry_and_malformed_cookie(self):
        self.login()
        for value in self.chat.sessions.values():
            value["expires"] = 0
        self.assertEqual(self.request("GET", "/api")[0], 401)
        self.assertEqual(self.request("GET", "/api", headers={"Cookie": "bob_session=forged"})[0], 401)

    def test_reports_and_jobs_are_authenticated_and_redacted(self):
        self.login()
        (self.root / "conductor/STATUS.md").write_text("Report " + self.chat.password)
        (self.root / "conductor/reviews").mkdir()
        (self.root / "conductor/reviews/LATEST.md").write_text("Gemini saved review")
        (self.root / "next-prompts").mkdir()
        (self.root / "next-prompts/INDEX.md").write_text("READY test job")
        (self.root / "conductor/MAINTENANCE").write_text("Scheduling paused")
        code, _, body = self.request("GET", "/api/status")
        self.assertEqual(code, 200)
        self.assertNotIn(self.chat.password, body)
        self.assertIn("modified_at", body)
        self.assertIn("Gemini saved review", self.request("GET", "/api/review")[2])
        with patch("app.run", return_value=(0, "123.svc-test (Detached)", "")):
            code, _, body = self.request("GET", "/api/jobs")
        self.assertEqual(code, 200)
        self.assertIn("svc-test", body)
        self.assertIn("READY test job", body)
        self.assertIn("Scheduling paused", body)

    def test_message_to_poll_round_trip(self):
        self.login()
        code, _, _ = self.request("POST", "/api/messages", {"conversation_id": self.identifier, "message": "Hi Bob", "request_id": str(uuid.uuid4())})
        self.assertEqual(code, 202)
        self.wait()
        code, _, body = self.request("GET", "/api/conversations/" + self.identifier)
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body)["messages"][-1]["content"], "A saved reply.")

    def test_tailnet_origin_and_secure_cookie(self):
        connection = http.client.HTTPConnection("127.0.0.1", self.port)
        connection.request("POST", "/login", "password=" + self.chat.password,
                           {"Content-Type": "application/x-www-form-urlencoded", "Host": "mini.example.ts.net", "Origin": "https://mini.example.ts.net"})
        response = connection.getresponse()
        self.assertEqual(response.status, 303)
        self.assertIn("; Secure", response.getheader("Set-Cookie"))
        response.read()
        connection.close()

    def test_invalid_input_has_no_provider_side_effect(self):
        self.login()
        for message in ("", "a" * 6001, None, []):
            self.assertEqual(self.request("POST", "/api/messages", {"conversation_id": self.identifier, "message": message, "request_id": str(uuid.uuid4())})[0], 400)
        self.assertEqual(self.fake.calls, [])
        self.assertEqual(self.request("POST", "/api/messages", {}, {"Content-Length": "9999999"})[0], 413)

    def test_cannot_bind_public_interface(self):
        with self.assertRaises(ValueError):
            Server(("0.0.0.0", 0), self.chat)


class ProviderTests(Fixture):
    def long_conversation(self):
        value = self.chat.conversations[self.identifier]
        value["messages"] = [{"role": "user", "content": "Please summarize the overnight conductor work in detail. " * 8, "status": "done"}]
        return value

    def provider(self, runner=run):
        return Providers(self.root, self.chat.redact, runner)

    def test_fallback_order_and_no_claude(self):
        provider = self.provider()
        attempted, progress = [], []
        def call(name, *_args):
            attempted.append(name)
            if name != "gemini":
                raise ProviderError("usage limit reached")
            return "Gemini answered", None
        with patch.object(provider, "call", side_effect=call):
            result = provider.reply(self.long_conversation(), threading.Event(), lambda name, attempts: progress.append(name))
        self.assertEqual(attempted, ["codex", "cursor", "gemini"])
        self.assertEqual(progress, attempted)
        self.assertEqual(result["provider"], "gemini")
        self.assertEqual(len(result["attempts"]), 2)

    def test_all_failures_are_reported_and_cancel_does_not_fallback(self):
        provider = self.provider()
        with patch.object(provider, "call", side_effect=ProviderError("timed out")):
            with self.assertRaises(AllDown):
                provider.reply(self.long_conversation(), threading.Event(), lambda *_: None)
        for name in (*provider.circuit.entries.keys(),):
            provider.circuit.entries[name].update(failures=0, retry_at=0, reason=None)
        provider.circuit.save()
        with patch.object(provider, "call", side_effect=Cancelled("Reply stopped")) as call:
            with self.assertRaises(Cancelled):
                provider.reply(self.long_conversation(), threading.Event(), lambda *_: None)
            self.assertEqual(call.call_count, 1)

    def test_codex_complete_answer_not_tool_or_commentary(self):
        events = [{"type": "thread.started", "thread_id": THREAD},
                  {"type": "item.completed", "item": {"type": "command_execution", "text": "secret tool result"}},
                  {"type": "item.completed", "item": {"type": "agent_message", "text": "Working"}},
                  {"type": "item.completed", "item": {"type": "agent_message", "text": "Final answer"}},
                  {"type": "turn.completed"}]
        output = "\n".join(map(json.dumps, events))
        self.assertEqual(parse_codex(output), ("Final answer", THREAD))
        with self.assertRaises(ProviderError):
            parse_codex("\n".join(map(json.dumps, events[:-1])))
        with self.assertRaises(ProviderError):
            parse_cursor('{"result":"partial", "is_error":true}')

    def test_codex_exact_resume_safe_flags_and_private_stdin(self):
        calls = []
        def runner(argv, **kwargs):
            calls.append((argv, kwargs))
            if "--help" in argv:
                return 0, "SESSION_ID", ""
            return 0, '\n'.join(map(json.dumps, [{"type": "thread.started", "thread_id": THREAD}, {"type": "item.completed", "item": {"type": "agent_message", "text": "Hello"}}, {"type": "turn.completed"}])), ""
        provider = self.provider(runner)
        self.assertEqual(provider.call("codex", "private transcript", THREAD, threading.Event()), ("Hello", THREAD))
        argv, kwargs = calls[-1]
        self.assertEqual(argv[-3:], ["resume", THREAD, "-"])
        self.assertIn('forced_login_method="chatgpt"', argv)
        self.assertIn('sandbox_mode="read-only"', argv)
        self.assertNotIn("--last", argv)
        self.assertNotIn("private transcript", argv)
        self.assertEqual(kwargs["prompt"], "private transcript")

    def test_cursor_uses_trust_ask_and_gemini_stdin(self):
        calls = []
        def runner(argv, **kwargs):
            calls.append((argv, kwargs))
            return (0, '{"result":"Cursor answer"}', "") if "--trust" in argv else (0, "<bob-webchat-reply>Gemini answer</bob-webchat-reply>", "")
        provider = self.provider(runner)
        provider.call("cursor", "context", None, threading.Event())
        self.assertIn("--trust", calls[-1][0])
        self.assertIn("ask", calls[-1][0])
        self.assertNotIn("--force", calls[-1][0])
        provider.call("gemini", "context", None, threading.Event())
        self.assertIn("api_call.py", calls[-1][0][-2])
        self.assertEqual(calls[-1][0][-1], "gemini")
        self.assertTrue(calls[-1][1]["prompt"].startswith("context"))
        self.assertIn("<bob-webchat-reply>", calls[-1][1]["prompt"])

    def test_gemini_short_answers_and_retry_logs(self):
        self.assertEqual(parse_gemini("HTTP retry failed\n<bob-webchat-reply>Hi</bob-webchat-reply>\n"), "Hi")
        for output in ("", "HTTP retry failed", "<bob-webchat-reply> </bob-webchat-reply>"):
            with self.assertRaises(ProviderError):
                parse_gemini(output)

    def test_parallel_conversations_do_not_block_each_other(self):
        second = self.chat.new_conversation()["id"]
        self.fake.hold.clear()
        self.chat.submit(self.identifier, "First", str(uuid.uuid4()))
        self.chat.submit(second, "Second", str(uuid.uuid4()))
        time.sleep(0.05)
        self.assertEqual(len(self.chat.workers), 2)
        self.fake.hold.set()
        for cid in (self.identifier, second):
            self.wait(cid)
        self.assertEqual(len(self.fake.calls), 2)

    def test_merge_refused_without_provider(self):
        request_id = str(uuid.uuid4())
        conversation = self.chat.submit(self.identifier, "Please merge #158", request_id)
        self.assertEqual(conversation["messages"][-1]["status"], "done")
        self.assertIn("won't merge", conversation["messages"][-1]["content"])
        self.assertEqual(self.fake.calls, [])

    def test_busy_cli_lane_falls_through_to_next_provider(self):
        provider = self.provider()
        attempted = []
        def call(name, *_args, **_kwargs):
            attempted.append(name)
            if name in ("codex", "cursor"):
                raise ProviderError("busy with another job")
            return "Gemini answered", None
        with patch.object(provider, "call", side_effect=call):
            result = provider.reply(self.long_conversation(), threading.Event(), lambda *_: None)
        self.assertEqual(result["provider"], "gemini")
        self.assertEqual(attempted[:3], ["codex", "cursor", "gemini"])

    def test_fast_path_prefers_gemini_for_short_messages(self):
        provider = self.provider()
        value = self.chat.conversations[self.identifier]
        value["messages"] = [{"role": "user", "content": "Hi Bob", "status": "done"}]
        self.assertEqual(provider.route_order(value)[0], "gemini")

    def test_fast_prompt_uses_lite_snapshot(self):
        provider = self.provider()
        (self.root / "conductor/reviews").mkdir(parents=True, exist_ok=True)
        (self.root / "conductor/reviews/LATEST.md").write_text("X" * 20000)
        value = self.chat.conversations[self.identifier]
        value["messages"] = [{"role": "user", "content": "quick status?", "status": "done"}]
        prompt = provider.prompt(value, fast=True)
        self.assertLess(len(prompt), len(provider.prompt(value, fast=False)))
        self.assertNotIn("X" * 500, prompt)

    def test_handoff_questions_use_full_snapshot_on_fast_path(self):
        from providers import needs_handoff_context

        self.assertTrue(needs_handoff_context("From BOB-STATE: what's running right now?"))
        provider = self.provider()
        (self.root / "bob-brain/memory").mkdir(parents=True)
        (self.root / "bob-brain/memory/profile.md").write_text("Y" * 15000)
        value = self.chat.conversations[self.identifier]
        value["messages"] = [{"role": "user", "content": "From BOB-STATE only: what's running?", "status": "done"}]
        prompt = provider.prompt(value, fast=True)
        self.assertIn("Y" * 500, prompt)

    def test_gemini_uses_direct_api_helper(self):
        calls = []
        def runner(argv, **kwargs):
            calls.append(argv)
            return 0, "<bob-webchat-reply>Gemini answer</bob-webchat-reply>", ""
        provider = self.provider(runner)
        provider.call("gemini", "context", None, threading.Event())
        self.assertIn("api_call.py", calls[-1][1])

    def test_busy_cli_lane_does_not_start_competing_process(self):
        provider = self.provider()
        other = self.provider()
        with provider.lane("codex"):
            with patch.object(other, "run") as runner:
                with self.assertRaisesRegex(ProviderError, "busy with another job"):
                    other.call("codex", "test", None, threading.Event())
                runner.assert_not_called()

    def test_recent_turns_and_brain_are_in_fallback_prompt(self):
        (self.root / "BOB-HANDOFF.md").write_text("Current hard rules")
        (self.root / "bob-brain/memory").mkdir(parents=True)
        (self.root / "bob-brain/memory/profile.md").write_text("Jeff's memory")
        value = self.chat.conversations[self.identifier]
        value["messages"] = [{"role": "user", "content": "turn-%02d" % i, "status": "done"} for i in range(25)]
        prompt = self.provider().prompt(value)
        self.assertIn("Current hard rules", prompt)
        self.assertIn("Jeff's memory", prompt)
        self.assertNotIn("turn-04", prompt)
        self.assertIn("turn-05", prompt)
        self.assertIn("turn-24", prompt)

    def test_parent_tokens_are_not_forwarded(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test", "CODEX_THREAD_ID": "parent", "CURSOR_API_KEY": "test", "GITHUB_TOKEN": "test"}):
            env = clean_env()
        self.assertNotIn("OPENAI_API_KEY", env)
        self.assertNotIn("CODEX_THREAD_ID", env)
        self.assertNotIn("CURSOR_API_KEY", env)
        self.assertNotIn("GITHUB_TOKEN", env)

    def test_timeout_kills_own_process_group(self):
        marker = self.root / "should-not-exist"
        child = "import time,pathlib; time.sleep(0.7); pathlib.Path(" + repr(str(marker)) + ").touch()"
        parent = "import subprocess,sys,time; subprocess.Popen([sys.executable,'-c'," + repr(child) + "]); time.sleep(60)"
        with self.assertRaisesRegex(ProviderError, "timed out"):
            run([sys.executable, "-c", parent], cwd=self.root, env=clean_env(), cancel=threading.Event(), timeout=0.2)
        time.sleep(0.8)
        self.assertFalse(marker.exists())


class HandbackJobTests(Fixture):
    def test_handback_summary_groups(self):
        folder = self.root / "conductor/handback"
        folder.mkdir(parents=True)
        append_turn(self.root, ask="merge #1", provider=None, jobs=[], files=[], commits=[], confirmations=[],
                    refusals=["drafts only"], open_items=[])
        append_turn(self.root, ask="music demo: rock", provider="minimax-music", jobs=[], files=["demo.mp3"],
                    commits=[], confirmations=[], refusals=[], open_items=[])
        refresh_summary(self.root)
        text = (folder / "HANDBACK-SUMMARY.md").read_text()
        self.assertIn("## Done", text)
        self.assertIn("## Risks", text)

    def test_handback_log_and_summary(self):
        folder = self.root / "conductor/handback"
        folder.mkdir(parents=True)
        (folder / "BOB-STATE.md").write_text("Running: test job")
        append_turn(self.root, ask="status?", provider="gemini", jobs=[], files=[], commits=[], confirmations=[], refusals=[], open_items=["status"])
        self.assertTrue((folder / "HANDBACK-LOG.md").exists())
        refresh_summary(self.root)
        summary = (folder / "HANDBACK-SUMMARY.md").read_text()
        self.assertIn("status?", summary)
        self.assertIn("Running: test job", summary)

    def test_music_demo_receipt_stable(self):
        from music_demo import demo_receipt
        self.assertEqual(demo_receipt("a", "b"), demo_receipt("a", "b"))
        self.assertNotEqual(demo_receipt("a", "b"), demo_receipt("a", "c"))

    def test_job_confirm_queues_draft_row(self):
        (self.root / "next-prompts").mkdir(parents=True)
        (self.root / "next-prompts/INDEX.md").write_text("| Pri | File | Project | Kind | Status | Notes |\n| --- | --- | --- | --- | --- | --- |\n")
        self.assertEqual(parse_start("start a job: fix the webchat panel"), "fix the webchat panel")
        self.assertEqual(parse_start("queue job: polish handback chip"), "polish handback chip")
        self.assertTrue(parse_confirm("yes, start job"))
        request_id = str(uuid.uuid4())
        self.chat.submit(self.identifier, "start a job: fix the webchat panel", request_id)
        self.assertEqual(self.chat.conversations[self.identifier].get("pending_job"), "fix the webchat panel")
        self.chat.submit(self.identifier, "yes, start job", str(uuid.uuid4()))
        self.wait()
        index = (self.root / "next-prompts/INDEX.md").read_text()
        self.assertIn("webchat-", index)
        self.assertIn("READY", index)

    def test_job_merge_refused_before_queue(self):
        self.chat.submit(self.identifier, "start a job: merge #158", str(uuid.uuid4()))
        self.assertNotIn("pending_job", self.chat.conversations[self.identifier])
        self.chat.submit(self.identifier, "start a job: safe task", str(uuid.uuid4()))
        self.chat.submit(self.identifier, "hello bob", str(uuid.uuid4()))
        self.assertNotIn("pending_job", self.chat.conversations[self.identifier])

    def test_panel_and_handback_api_shape(self):
        data = self.chat.panel()
        self.assertIn("lanes", data)
        self.assertIn("handback", data)
        self.assertIn("recent_results", data)
        self.assertIn("live_ops", data)
        self.assertIn("conductor", data)
        self.assertIn("live_ops_meta", data)

    def test_handback_drill_backup_restore(self):
        from live_handback_drill import backup_handback, restore_handback
        folder = self.root / "conductor/handback"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "BOB-STATE.md").write_text("original state\n")
        saved = backup_handback(self.root)
        (folder / "BOB-STATE.md").write_text("drill overwrite\n")
        restore_handback(self.root, saved)
        self.assertEqual((folder / "BOB-STATE.md").read_text(), "original state\n")

    def test_song_notebook_roundtrip(self):
        from music_notebook import get_project, list_projects, save_project
        project = save_project(self.root, {"title": "Night Drive", "lyrics": "Verse one", "chords": "Am G F"})
        self.assertTrue(list_projects(self.root))
        loaded = get_project(self.root, project["id"])
        self.assertEqual(loaded["lyrics"], "Verse one")

    def test_music_demo_dry_run(self):
        from music_demo import generate_demo
        result = generate_demo(self.root, lyrics="hook line", style="folk", dry_run=True)
        self.assertTrue(result["dry_run"])

    def test_music_demo_local_sketch_when_hosted_unavailable(self):
        from music_demo import generate_demo
        with patch("music_demo._reserve_music_budget", return_value="test-call"), patch("music_demo._finalize_music_budget"), \
                patch("music_demo._try_minimax_hosted", return_value=None), patch("music_demo._try_replicate", return_value=None):
            result = generate_demo(self.root, lyrics="Verse one\nVerse two", style="acoustic folk")
        self.assertEqual(result.get("engine"), "local-sketch")
        self.assertGreater(result.get("bytes", 0), 1000)

    def test_audio_upload_and_fetch(self):
        from music_demo import resolve_audio, store_upload
        stored = store_upload(self.root, b"\x00\x01\x02", ".mp3")
        path = resolve_audio(self.root, stored["audio_id"])
        self.assertTrue(path.exists())


class InstallerTests(Fixture):
    def test_webchat_only_leaves_other_agents_alone(self):
        source = Path(__file__).resolve().parents[1] / "launchd/install.py"
        spec = importlib.util.spec_from_file_location("webchat_test_installer", source)
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        launchd = self.root / "conductor/launchd"
        launchd.mkdir()
        (launchd / "com.jeff.bob-webchat.plist").write_text("test fixture")
        (launchd / "com.jeff.bob-services.plist").write_text("test fixture")
        with patch.object(installer, "ROOT", self.root), patch.object(installer, "CONDUCTOR", self.root / "conductor"), \
             patch.object(Path, "home", return_value=self.root / "home"), patch.object(installer, "run") as command, \
             patch.object(sys, "argv", ["install.py", "--webchat-only"]), patch("sys.stdout", new_callable=io.StringIO):
            installer.main()
        commands = [call.args[0] for call in command.call_args_list]
        bootstrap = [argv for argv in commands if argv[:2] == ["launchctl", "bootstrap"]]
        self.assertEqual(len(bootstrap), 1)
        self.assertTrue(bootstrap[0][-1].endswith("com.jeff.bob-webchat.plist"))
        self.assertFalse(any("services/start-all.sh" in arg or "mini-conductor" in arg for argv in commands for arg in argv))
        self.assertTrue(command.call_args_list[-1].kwargs["detach"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
