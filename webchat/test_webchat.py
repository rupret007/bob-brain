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
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from app import Chat, RequestError, Server, password_at, private_write
from handback import append_turn, refresh_summary
from job_queue import parse_confirm, parse_council, parse_council_cancel, parse_council_confirm, parse_do_more, parse_start, queue_draft, sanitize_council_question
from failover import AllDown
from providers import Cancelled, ProviderError, Providers, Redactor, RULES, clean_env, parse_codex, parse_cursor, parse_gemini, run

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
        # Unit/HTTP fixtures have a private queue and private host observations.
        for name in ("_screen_sessions", "process_table"):
            sampler = patch("live_status_snapshot." + name, return_value={})
            sampler.start()
            self.addCleanup(sampler.stop)

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
        for path in ("/api", "/api/status", "/api/review", "/api/jobs", "/api/jobs/activity", "/api/jobs/result?id=job",
                     "/api/conversations", "/api/conversations/" + self.identifier):
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

    def test_jobs_activity_and_result_are_read_only_and_redacted(self):
        self.login()
        journal = self.root / "conductor/state/queue.jsonl"
        journal.parent.mkdir(parents=True, exist_ok=True)
        journal.write_text(json.dumps(dict(id="job", status="succeeded", title="Web Bob result", finished_at=time.time(),
                                            result="Saved result " + self.chat.password)) + "\n")
        before = journal.read_bytes()
        code, _, body = self.request("GET", "/api/jobs/activity")
        self.assertEqual(code, 200)
        view = json.loads(body)
        self.assertEqual(view["working"], [])
        self.assertEqual(view["recently_finished"][0]["result_url"], "/api/jobs/result?id=job")
        code, _, body = self.request("GET", "/api/jobs/result?id=job")
        self.assertEqual(code, 200)
        self.assertIn("Saved result", body)
        self.assertNotIn(self.chat.password, body)
        self.assertEqual(self.request("GET", "/api/jobs/result?id=missing")[0], 404)
        self.assertEqual(before, journal.read_bytes())
        self.assertEqual(self.fake.calls, [])

    def test_explicit_providers_reach_model_and_reject_unknown_provider(self):
        self.login()
        for provider in ("minimax", "gemini", "codex", "claude", "cursor"):
            with self.subTest(provider=provider), patch("app.state_ledger.try_status_reply", return_value="local shortcut"):
                code, _, _ = self.request("POST", "/api/messages", {
                    "conversation_id": self.identifier, "message": "Hello Bob",
                    "request_id": str(uuid.uuid4()), "provider": provider})
                self.assertEqual(code, 202)
                self.wait()
                self.assertEqual(self.fake.calls[-1]["preferred_provider"], provider)
                answer = self.chat.history(self.identifier)["messages"][-1]
                self.assertEqual("A saved reply.", answer["content"])
                self.assertNotIn("Answering provider:", answer["content"])
        for provider in ("grok", "unknown", None):
            self.assertEqual(self.request("POST", "/api/messages", {
                "conversation_id": self.identifier, "message": "hello",
                "request_id": str(uuid.uuid4()), "provider": provider})[0], 400)
        self.assertEqual(len(self.fake.calls), 5)

    def test_progress_status_is_local_plain_and_does_not_start_duplicate_work(self):
        from test_worker_activity import PS, SCREENS
        from worker_activity import parse_processes
        self.login()
        with patch("live_status_snapshot._screen_sessions", return_value=SCREENS), \
                patch("live_status_snapshot.process_table", return_value=parse_processes(PS)):
            for text in ("The hold is lifted. Bob already started WebJam #161, AdoptIQ #26, StoryBoard #47, and Shelf #10 on Claude, "
                         "so don't start duplicates. For anything new, use start a job: plus the task. When I ask for status, give it in plain words from the real queue.",
                         "Ok great is it moving along now?"):
                code, _, body = self.request("POST", "/api/messages", dict(conversation_id=self.identifier,
                    message=text, request_id=str(uuid.uuid4())))
                self.assertEqual(code, 202)
                answer = json.loads(body)["messages"][-1]
                self.assertEqual(answer["status"], "done")
                if text.startswith("The hold"):
                    self.assertEqual(answer["content"], "Ready when you are.")
                else:
                    self.assertEqual(answer["content"].count("running for"), 4)
                self.assertNotIn("start a job:", answer["content"])
                self.assertNotIn("None", answer["content"])
        self.assertEqual(self.fake.calls, [])
        self.assertFalse((self.root / "conductor/state/queue.jsonl").exists())

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

    def test_lite_snapshot_includes_handoff_digest(self):
        folder = self.root / "conductor/handback"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "BOB-STATE.md").write_text("Running: council review\n")
        (folder / "HANDBACK-LOG.md").write_text("")
        (folder / "HANDBACK-SUMMARY.md").write_text("# HANDBACK-SUMMARY\n\n## Running\n- council review\n")
        provider = self.provider()
        value = self.chat.conversations[self.identifier]
        value["messages"] = [{"role": "user", "content": "hey", "status": "done"}]
        prompt = provider.prompt(value, fast=True)
        self.assertIn("handoff-digest", prompt)
        self.assertIn("council review", prompt.lower())

    def test_live_status_snapshot_builder_reads_jobs_and_lanes(self):
        from live_status_snapshot import build_live_status_snapshot

        conductor = self.root / "conductor"
        conductor.mkdir(parents=True, exist_ok=True)
        (conductor / "jobs.jsonl").write_text(
            json.dumps(
                {
                    "job_id": "webbob-context-fixture",
                    "state": "running",
                    "engine": "cursor",
                    "timestamp": time.time(),
                }
            )
            + "\n"
        )
        (conductor / "lanes.json").write_text(
            json.dumps({"cursor": {"state": "busy", "detail": "lane lease held"}})
        )
        snap = build_live_status_snapshot(self.root)
        self.assertIn("webbob-context-fixture", json.dumps(snap))
        self.assertEqual(snap["lane_locks"]["cursor"]["state"], "busy")
        self.assertIn("queue_jobs", snap)

    def test_gemini_prompt_includes_live_status_snapshot(self):
        conductor = self.root / "conductor"
        conductor.mkdir(parents=True, exist_ok=True)
        (conductor / "jobs.jsonl").write_text(
            json.dumps(
                {
                    "job_id": "gemini-live-status-marker",
                    "state": "queued",
                    "engine": "gemini",
                    "timestamp": time.time(),
                }
            )
            + "\n"
        )
        provider = self.provider()
        value = self.chat.conversations[self.identifier]
        value["messages"] = [{"role": "user", "content": "what are workers doing?", "status": "done"}]
        prompt = provider.prompt(value, fast=True)
        self.assertIn("live_status_snapshot", prompt)
        self.assertIn("gemini-live-status-marker", prompt)

    def test_minimax_call_receives_live_status_snapshot_prompt(self):
        conductor = self.root / "conductor"
        conductor.mkdir(parents=True, exist_ok=True)
        (conductor / "jobs.jsonl").write_text(
            json.dumps(
                {
                    "job_id": "minimax-live-status-marker",
                    "state": "running",
                    "engine": "minimax",
                    "timestamp": time.time(),
                }
            )
            + "\n"
        )
        prompts = []

        def runner(argv, **kwargs):
            prompts.append(kwargs.get("prompt") or "")
            return 0, "<bob-webchat-reply>ok</bob-webchat-reply>", ""

        provider = self.provider(runner)
        value = self.chat.conversations[self.identifier]
        value["messages"] = [{"role": "user", "content": "status?", "status": "done"}]
        provider.call("minimax", provider.prompt(value, fast=True), None, threading.Event())
        self.assertTrue(prompts)
        self.assertIn("live_status_snapshot", prompts[0])
        self.assertIn("minimax-live-status-marker", prompts[0])

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

    def test_handback_pickup_uses_ledger_open_asks(self):
        ledger_dir = self.root / "conductor/state"
        sys.path.insert(0, str(ledger_dir))
        import ledger as state_ledger

        state_ledger.add_open_ask(self.root, "approve demo sketch")
        append_turn(self.root, ask="drill done", provider="gemini", jobs=[], files=[], commits=["abc1234567"],
                    confirmations=[], refusals=[], open_items=[])
        refresh_summary(self.root)
        summary = (self.root / "conductor/handback/HANDBACK-SUMMARY.md").read_text()
        self.assertIn("Open ask", summary)
        self.assertIn("approve demo sketch", summary)
        self.assertIn("Recent commit: abc1234567", summary)
        self.assertNotIn("Open: drill done", summary)

    def test_handback_idempotent_request_id(self):
        rid = str(uuid.uuid4())
        kwargs = dict(ask="ping", provider="gemini", jobs=[], files=[], commits=[], confirmations=[], refusals=[], open_items=[])
        self.assertTrue(append_turn(self.root, request_id=rid, **kwargs))
        self.assertFalse(append_turn(self.root, request_id=rid, **kwargs))
        log = (self.root / "conductor/handback/HANDBACK-LOG.md").read_text()
        self.assertEqual(log.count(f"**Request:** {rid}"), 1)

    def test_music_demo_receipt_stable(self):
        from music_demo import demo_receipt
        self.assertEqual(demo_receipt("a", "b"), demo_receipt("a", "b"))
        self.assertNotEqual(demo_receipt("a", "b"), demo_receipt("a", "c"))

    def test_council_question_sanitized(self):
        self.assertNotIn("$", sanitize_council_question("$(rm -rf /)"))
        self.assertTrue(parse_council_cancel("cancel council"))

    def test_council_confirm_queues_draft_row(self):
        (self.root / "next-prompts").mkdir(parents=True)
        (self.root / "next-prompts/INDEX.md").write_text("| Pri | File | Project | Kind | Status | Notes |\n| --- | --- | --- | --- | --- | --- |\n")
        self.assertEqual(parse_council("run council on: score mobile UX"), "score mobile UX")
        self.assertTrue(parse_council_confirm("yes, run council"))
        self.chat.submit(self.identifier, "run council on: mobile sheet UX", str(uuid.uuid4()))
        self.assertEqual(self.chat.conversations[self.identifier].get("pending_council"), "mobile sheet UX")
        self.chat.submit(self.identifier, "yes, run council", str(uuid.uuid4()))
        self.wait()
        from task_dispatch import task_queue
        answer = self.chat.history(self.identifier)["messages"][-1]
        rows = [task_queue.tasks(self.root)[key] for key in answer["task_ids"]]
        self.assertEqual([row["requested_worker"] for row in rows], ["gemini", "minimax", "claude"])
        self.assertEqual([row["kind"] for row in rows], ["audit", "test-writing", "analysis"])
        for row in rows:
            self.assertIn(row["id"], answer["content"])
            self.assertIn("council question", row["prompt"])
        self.assertNotIn("pending_council", self.chat.conversations[self.identifier])

    def test_job_confirm_dispatches_durable_task(self):
        (self.root / "next-prompts").mkdir(parents=True)
        (self.root / "next-prompts/INDEX.md").write_text("| Pri | File | Project | Kind | Status | Notes |\n| --- | --- | --- | --- | --- | --- |\n")
        self.assertEqual(parse_start("start a job: fix the webchat panel"), "fix the webchat panel")
        self.assertEqual(parse_start("queue job: polish handback chip"), "polish handback chip")
        self.assertTrue(parse_confirm("yes, start job"))
        request_id = str(uuid.uuid4())
        self.chat.submit(self.identifier, "do it", request_id)
        self.chat.conversations[self.identifier]["pending_job"] = "fix the webchat panel"
        self.chat.submit(self.identifier, "yes, start job", str(uuid.uuid4()))
        self.wait()
        from task_dispatch import task_queue
        tasks = list(task_queue.tasks(self.root).values())
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["prompt"], "fix the webchat panel")
        self.assertEqual(tasks[0]["conversation_id"], self.identifier)
        assistant = self.chat.conversations[self.identifier]["messages"][-1]
        self.assertEqual(assistant["action_card"]["state"], "queued")
        self.assertIn("webchat-", assistant["action_card"].get("queue_id", ""))
        self.assertEqual(assistant["action_card"].get("goal_text"), "fix the webchat panel")
        self.assertEqual(assistant["content"], "I queued “fix the webchat panel” for the next available worker (job `" + assistant["task_id"] + "`).")

    def test_job_merge_refused_before_queue(self):
        self.chat.submit(self.identifier, "start a job: merge #158", str(uuid.uuid4()))
        self.assertNotIn("pending_job", self.chat.conversations[self.identifier])

    def test_do_more_asks_for_the_task_instead_of_inventing_one(self):
        self.assertIsNotNone(parse_do_more("I need you to do more"))
        self.chat.submit(self.identifier, "I need you to do more", str(uuid.uuid4()))
        pending = self.chat.conversations[self.identifier].get("pending_job")
        self.assertIsNone(pending)
        last = self.chat.conversations[self.identifier]["messages"][-1]
        self.assertEqual(last["content"], "What would you like me to work on?")

    def test_do_more_does_not_match_negation(self):
        self.assertIsNone(parse_do_more("please do not run it yourself"))

    def test_provider_rules_not_readonly_chat(self):
        lower = RULES.lower()
        self.assertNotIn("read-only chat", lower)
        self.assertIn("conductor when bob is away", lower)
        self.assertIn("server handlers execute", lower)

    def test_enrich_live_ops_display_state(self):
        from ops_panel import enrich_live_ops

        out = enrich_live_ops(
            {
                "running_jobs": [
                    {"live_screen": True, "stall_state": "running", "state": "running"},
                    {"live_screen": False, "stall_state": "running", "state": "running"},
                ],
                "service_screens": ["svc-a", "svc-b"],
            }
        )
        self.assertEqual(out["service_screen_count"], 2)
        self.assertEqual(out["running_jobs"][0]["display_state"], "Live on screen")
        self.assertEqual(out["running_jobs"][1]["display_state"], "Marked running; screen unconfirmed")
        self.assertIn("stall_plain", out["running_jobs"][0])
        self.assertEqual(out["running_jobs"][0]["stall_plain"], "Running normally")

    def test_self_improve_bootstrap_command(self):
        launchd = self.root / "conductor/launchd"
        launchd.mkdir(parents=True, exist_ok=True)
        (launchd / "com.jeff.bob-webchat-self-improve.plist").write_text("<plist/>")
        (self.root / "conductor/webchat/self_improve_tick.sh").write_text("#!/bin/bash\n")
        bootstrap = self.root / "conductor/webchat/bootstrap_self_improve_launchd.sh"
        bootstrap.write_text("#!/bin/bash\n")
        status = self.chat.self_improve_status()
        self.assertTrue(status["install_ready"])
        cmd = status.get("bootstrap_command") or ""
        self.assertIn("bootstrap_self_improve_launchd.sh", cmd)
        self.assertIn("cd ", cmd)
        self.assertIn("plain_status", status)
        self.assertTrue(status["plain_status"])

    def test_quiet_hours_ct(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo

        from quiet_hours import in_quiet_hours

        ct = ZoneInfo("America/Chicago")
        self.assertTrue(in_quiet_hours(datetime(2026, 9, 27, 23, 30, tzinfo=ct)))
        self.assertTrue(in_quiet_hours(datetime(2026, 9, 27, 6, 0, tzinfo=ct)))
        self.assertFalse(in_quiet_hours(datetime(2026, 9, 27, 12, 0, tzinfo=ct)))

    def test_quiet_hours_js_harness(self):
        import subprocess

        script = Path(__file__).resolve().parent / "test_quiet_hours_js.mjs"
        subprocess.run(["node", str(script)], check=True, cwd=str(self.root))

    def test_panel_includes_quiet_hours(self):
        panel = self.chat.panel()
        qh = panel.get("quiet_hours") or {}
        self.assertIn("active", qh)
        self.assertIn("read_aloud_blocked", qh)
        self.assertEqual(qh["read_aloud_blocked"], qh["active"])

    def test_public_live_ops_carries_display_fields(self):
        from ops_panel import enrich_live_ops

        services = Path(__file__).resolve().parent.parent / "services"
        if str(services) not in sys.path:
            sys.path.insert(0, str(services))
        import live_dashboard
        raw = {
            "running_jobs": [
                {"live_screen": True, "stall_state": "running", "state": "running", "plain_now": "ok"},
                {"live_screen": False, "stall_state": "running", "state": "running", "plain_now": "tracked"},
            ]
        }
        enriched = enrich_live_ops(raw)
        public = live_dashboard.public_live_ops(enriched)
        for row in public["running_jobs"]:
            self.assertIn("display_state", row)
            self.assertIn("stall_plain", row)
            self.assertTrue(row["display_state"])
            self.assertTrue(row["stall_plain"])

    def test_inbox_work_request_creates_executable_task(self):
        request_id = str(uuid.uuid4())
        value = self.chat.submit(self.identifier, "tell the builder: fix Jobs tab copy", request_id)
        assistant = value["messages"][-1]
        self.assertEqual(assistant["status"], "done")
        self.assertEqual(assistant.get("provider"), "dispatcher")
        from task_dispatch import task_queue
        task = task_queue.tasks(self.root)[assistant["task_id"]]
        self.assertEqual(task["prompt"], "fix Jobs tab copy")
        self.assertEqual(task["status"], "queued")

    def test_status_chip_answers_from_state_without_model(self):
        ledger_dir = Path(__file__).resolve().parent.parent / "state"
        if str(ledger_dir) not in sys.path:
            sys.path.insert(0, str(ledger_dir))
        import ledger as state_ledger

        state_ledger.write_now(self.root, "Idle on mini · tests running")
        request_id = str(uuid.uuid4())
        value = self.chat.submit(self.identifier, "status", request_id)
        assistant = value["messages"][-1]
        self.assertEqual(assistant["status"], "done")
        self.assertEqual(assistant.get("provider"), "state")
        self.assertIn("mini", assistant["content"].lower())
        self.assertNotIn("provider-health.json", assistant["content"])
        self.assertNotIn("tests running", assistant["content"])

    def test_panel_and_handback_api_shape(self):
        data = self.chat.panel()
        self.assertIn("lanes", data)
        self.assertIn("alignment", data)
        self.assertIn("handback", data)
        self.assertIn("recent_results", data)
        self.assertIn("live_ops", data)
        self.assertIn("conductor", data)
        self.assertIn("live_ops_meta", data)
        self.assertIn("self_improve", data)
        self.assertIn("summary", data["self_improve"])
        self.assertIn("launchd_loaded", data["self_improve"])

    def test_self_improve_status_from_handback(self):
        log = self.root / "conductor/handback/HANDBACK-LOG.md"
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text("## 2026-09-27 02:00:00 CT\n- **Ask:** webchat self-improve tick\n- **Outcome:** chat\n")
        status = self.chat.self_improve_status()
        self.assertIn("2026-09-27 02:00:00 CT", status["last_logged"] or "")
        self.assertIn("self-improve", status["summary"].lower())

    def test_self_improve_launchctl_probe(self):
        launchd = self.root / "conductor/launchd"
        launchd.mkdir(parents=True, exist_ok=True)
        (launchd / "com.jeff.bob-webchat-self-improve.plist").write_text("<plist/>")
        (self.root / "conductor/webchat/self_improve_tick.sh").write_text("#!/bin/bash\n")
        with patch.object(type(self.chat), "_launchd_job_loaded", return_value=True):
            status = self.chat.self_improve_status()
        self.assertTrue(status["launchd_loaded"])
        self.assertIn("Launchd job loaded", status["summary"])

    def test_hollow_progress_reply_repaired(self):
        from reply_guard import is_hollow_progress_reply, repair_hollow_progress

        bad = (
            "I'm still looking for that file in drill-r9-test. "
            "Maybe another minute or two to scan the directory."
        )
        self.assertTrue(is_hollow_progress_reply(bad))
        fixed = repair_hollow_progress(bad)
        self.assertNotIn("minute or two", fixed.lower())
        self.assertIn("can't", fixed.lower())

    def test_status_hides_drill_open_asks(self):
        ledger_dir = Path(__file__).resolve().parent.parent / "state"
        if str(ledger_dir) not in sys.path:
            sys.path.insert(0, str(ledger_dir))
        import ledger as state_ledger

        state_ledger.add_open_ask(self.root, "drill open item (r9-test)")
        state_ledger.add_open_ask(self.root, "approve WebJam feel-check")
        reply = state_ledger.try_status_reply(self.root, "status")
        self.assertIsNotNone(reply)
        self.assertIn("approve WebJam", reply)
        self.assertNotIn("drill open item", reply)

    def test_overlay_pin_lifecycle_during_blocked_reply(self):
        from drill_fixture import new_fixture_root

        fixture = new_fixture_root(self.folder)
        conv = self.identifier
        self.chat.overlay_roots[conv] = fixture
        self.fake.hold.clear()
        self.chat.submit(conv, "hello overlay pin", str(uuid.uuid4()))
        time.sleep(0.08)
        self.assertIn(conv, self.chat.overlay_pins)
        with self.chat.lock:
            self.chat.overlay_roots.pop(conv, None)
        self.assertEqual(self.chat.ledger_root(conv), fixture)
        self.fake.hold.set()
        self.wait(conv)
        self.assertNotIn(conv, self.chat.overlay_pins)

    def test_drill_overlay_pinned_for_inflight_reply(self):
        from drill_fixture import new_fixture_root

        fixture = new_fixture_root(self.folder)
        conv = self.identifier
        with self.chat.lock:
            self.chat.overlay_roots[conv] = fixture
            self.chat.overlay_pins[conv] = fixture
            self.chat.overlay_roots.pop(conv, None)
        self.assertEqual(self.chat.ledger_root(conv), fixture)
        real = Providers(self.root, self.chat.redact, overlay_roots=self.chat.overlay_roots, overlay_pins=self.chat.overlay_pins)
        self.assertEqual(real.context_root(conv), fixture)
        with self.chat.lock:
            self.chat.overlay_pins.pop(conv, None)

    def test_handback_drill_isolated_fixture(self):
        from drill_fixture import assert_prod_unchanged, events_ok, ledger_round, new_fixture_root, prod_fingerprint, try_bob_state_running_line

        before = prod_fingerprint(self.root)
        fixture = new_fixture_root(self.folder)
        result = ledger_round(fixture, "unit-test")
        self.assertTrue(result["ledger_ok"])
        self.assertTrue(events_ok(fixture, "unit-test"))
        assert_prod_unchanged(before, self.root)
        line = try_bob_state_running_line(fixture, "From BOB-STATE only: what's running?")
        self.assertIn("drill-unit-test", (line or "").lower())

    def test_record_webchat_turn_skips_ready_drill_on_prod(self):
        ledger_dir = Path(__file__).resolve().parent.parent / "state"
        if str(ledger_dir) not in sys.path:
            sys.path.insert(0, str(ledger_dir))
        import alignment_events
        import ledger as state_ledger

        before = alignment_events.latest_seq(self.root)
        state_ledger.record_webchat_turn(self.root, ask="Reply with exactly: drill A1", provider="gemini")
        self.assertEqual(alignment_events.latest_seq(self.root), before)

    def test_purge_drill_open_asks(self):
        ledger_dir = Path(__file__).resolve().parent.parent / "state"
        if str(ledger_dir) not in sys.path:
            sys.path.insert(0, str(ledger_dir))
        import ledger as state_ledger

        state_ledger.add_open_ask(self.root, "drill open item (r9-test)")
        state_ledger.add_open_ask(self.root, "real Jeff ask")
        dropped = state_ledger.purge_drill_open_asks(self.root)
        self.assertGreaterEqual(dropped, 1)
        reply = state_ledger.try_status_reply(self.root, "status")
        self.assertIsNotNone(reply)
        self.assertIn("real Jeff", reply or "")

    def test_panel_round_changelog(self):
        reviews = self.root / "conductor/reviews"
        reviews.mkdir(parents=True, exist_ok=True)
        (reviews / "WEBCHAT-READY-R99-RESULT.md").write_text(
            "# R99\n\n## Changelog\nApprove buttons bind to proposal IDs.\n\n| iPhone design | 9.5 | **9.6** · chat bubbles |\n"
        )
        data = self.chat.panel()
        self.assertIn("round_changelog", data)
        self.assertEqual(data["round_changelog"].get("round"), 99)
        self.assertIn("proposal", (data["round_changelog"].get("line") or "").lower())

    def test_job_confirm_rejects_stale_proposal_id(self):
        (self.root / "next-prompts").mkdir(parents=True)
        (self.root / "next-prompts/INDEX.md").write_text("| Pri | File | Project | Kind | Status | Notes |\n| --- | --- | --- | --- | --- | --- |\n")
        proposal = str(uuid.uuid4())
        stale = str(uuid.uuid4())
        self.chat.conversations[self.identifier].update(pending_job="review PR #161", pending_job_id=proposal)
        self.chat.save(self.chat.conversations[self.identifier])
        self.assertEqual(self.chat.conversations[self.identifier].get("pending_job_id"), proposal)
        value = self.chat.submit(self.identifier, f"yes, start job proposal {stale}", str(uuid.uuid4()))
        assistant = value["messages"][-1]
        self.assertEqual(assistant["action_card"]["state"], "refused")
        self.assertIn("pending_job", self.chat.conversations[self.identifier])
        self.chat.submit(self.identifier, f"yes, start job proposal {proposal}", str(uuid.uuid4()))
        self.wait()
        self.assertNotIn("pending_job", self.chat.conversations[self.identifier])

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


    def test_music_coach_cheap_reply(self):
        from music_notebook import try_music_coach_reply
        self.assertIn("chorus", (try_music_coach_reply("help with chorus hook") or "").lower())
        refrain_only = (try_music_coach_reply("polish the refrain") or "").lower()
        self.assertIn("refrain", refrain_only)
        self.assertIn("versions", refrain_only)
        verse_only = (try_music_coach_reply("tighten the verse lyrics") or "").lower()
        self.assertIn("verse", verse_only)
        self.assertNotIn("chorus/refrain tip", verse_only)
        hook_only = (try_music_coach_reply("sharpen the hook line only") or "").lower()
        self.assertIn("hook", hook_only)
        self.assertNotIn("chorus/refrain tip", hook_only)
        self.assertIn("rhyme", (try_music_coach_reply("fix the rhyme scheme") or "").lower())
        self.assertIn("bridge", (try_music_coach_reply("help with song structure and bridge") or "").lower())
        self.assertIn("bpm", (try_music_coach_reply("what tempo bpm should I use") or "").lower())
        self.assertIn("4/4", (try_music_coach_reply("what time signature 4/4") or "").lower())
        self.assertIn("modulation", (try_music_coach_reply("help with modulation key change") or "").lower())
        self.assertIn("outro", (try_music_coach_reply("write an outro fade ending") or "").lower())
        self.assertIn("modulation", (try_music_coach_reply("key change for the last chorus") or "").lower())
        self.assertIn("pre-chorus", (try_music_coach_reply("help with pre-chorus lift") or "").lower())
        self.assertIn("capo", (try_music_coach_reply("what capo fret for G shapes") or "").lower())
        self.assertIn("intro", (try_music_coach_reply("write an intro riff for my song") or "").lower())
        self.assertIn("breakdown", (try_music_coach_reply("help with song dynamics and breakdown") or "").lower())
        self.assertIsNone(try_music_coach_reply("give me a breakdown of running jobs"))
        self.assertIsNone(try_music_coach_reply("write an intro for my presentation"))
        self.assertIn("modulation", (try_music_coach_reply("intro key change on the chorus") or "").lower())
        outro_chorus = (try_music_coach_reply("outro chorus tag line") or "").lower()
        self.assertIn("tag", outro_chorus)
        self.assertNotIn("chorus tip", outro_chorus)
        self.assertIn("double", (try_music_coach_reply("double chorus ending") or "").lower())
        self.assertIn("post-chorus", (try_music_coach_reply("add a post-chorus riff") or "").lower())
        tag_bridge = (try_music_coach_reply("add a tag line on the bridge") or "").lower()
        self.assertIn("tag", tag_bridge)
        hyphen = (try_music_coach_reply("double-chorus lift") or "").lower()
        self.assertIn("double", hyphen)

    def test_self_improve_schedule_hint_from_plist(self):
        plist = self.root / "conductor/launchd/com.jeff.bob-webchat-self-improve.plist"
        plist.parent.mkdir(parents=True, exist_ok=True)
        plist.write_text(
            "<plist><dict><key>Hour</key><integer>4</integer><key>Minute</key><integer>30</integer></dict></plist>"
        )
        hint = self.chat._self_improve_schedule_hint(plist)
        self.assertIn("04:30", hint or "")
        status = self.chat.self_improve_status()
        self.assertEqual(status.get("schedule_hint"), hint)

    def test_job_card_view_from_events(self):
        from job_card_view import job_card_headline, job_card_log_lines, job_card_stall_state

        job = {
            "plain_now": "fallback",
            "stall_state": "running",
            "events": [
                {"kind": "status", "text": "Running tests on Web Bob"},
                {"kind": "log", "text": "PASS 67 tests"},
                {"kind": "log", "text": "handback drill OK"},
                {"kind": "commit", "sha": "abc1234", "message": "fix panel"},
                {"kind": "stall", "state": "stalled"},
            ],
        }
        self.assertEqual(job_card_headline(job), "Running tests on Web Bob")
        self.assertEqual(job_card_log_lines(job), ["PASS 67 tests", "handback drill OK"])
        self.assertEqual(job_card_stall_state(job), "stalled")

    def test_load_live_ops_does_not_spawn_refresh(self):
        from ops_panel import load_live_ops

        dash = self.root / "conductor/dashboard.json"
        dash.parent.mkdir(parents=True, exist_ok=True)
        old = time.time() - 3600
        dash.write_text(
            json.dumps({"live_ops": {"generated_at": "2020-01-01T00:00:00+00:00", "now_line": "stale"}})
        )
        os.utime(dash, (old, old))
        with patch("ops_panel.subprocess.Popen") as popen:
            with patch(
                "ops_panel.inline_live_ops",
                return_value={"generated_at": datetime.now(timezone.utc).isoformat(), "now_line": "fresh"},
            ):
                out = load_live_ops(self.root, max_age=120.0)
        popen.assert_not_called()
        self.assertFalse(out["meta"]["stale"])
        self.assertEqual(out["meta"]["source"], "inline_snapshot")

    def test_load_live_ops_stale_inline_keeps_stale_dashboard(self):
        from ops_panel import load_live_ops

        dash = self.root / "conductor/dashboard.json"
        dash.parent.mkdir(parents=True, exist_ok=True)
        dash.write_text(json.dumps({"live_ops": {"generated_at": "2020-01-01T00:00:00+00:00", "now_line": "cached"}}))
        with patch("ops_panel.inline_live_ops", return_value={"generated_at": "2019-01-01T00:00:00+00:00"}):
            out = load_live_ops(self.root, max_age=120.0)
        self.assertTrue(out["meta"]["stale"])
        self.assertEqual(out["live_ops"].get("now_line"), "cached")

    def test_load_live_ops_read_only_skips_inline_snapshot(self):
        from ops_panel import load_live_ops

        dash = self.root / "conductor/dashboard.json"
        dash.parent.mkdir(parents=True, exist_ok=True)
        old = time.time() - 3600
        dash.write_text(
            json.dumps({"live_ops": {"generated_at": "2020-01-01T00:00:00+00:00", "now_line": "cached-only"}})
        )
        os.utime(dash, (old, old))
        with patch("ops_panel.inline_live_ops") as inline:
            out = load_live_ops(self.root, max_age=120.0, read_only=True)
        inline.assert_not_called()
        self.assertTrue(out["meta"]["stale"])
        self.assertEqual(out["live_ops"].get("now_line"), "cached-only")

    def test_maybe_spawn_dashboard_refresh_respects_fresh_dashboard(self):
        from ops_panel import maybe_spawn_dashboard_refresh

        dash = self.root / "conductor/dashboard.json"
        dash.parent.mkdir(parents=True, exist_ok=True)
        dash.write_text("{}")
        with patch("ops_panel.subprocess.Popen") as popen:
            self.assertFalse(maybe_spawn_dashboard_refresh(self.root))
        popen.assert_not_called()

    def test_self_improve_start_line_not_loop_ready(self):
        (self.root / "conductor/launchd").mkdir(parents=True, exist_ok=True)
        (self.root / "conductor/launchd/com.jeff.bob-webchat-self-improve.plist").write_text("plist")
        (self.root / "conductor/webchat/self_improve_tick.sh").write_text("#!/bin/bash\n")
        (self.root / "logs").mkdir(parents=True, exist_ok=True)
        (self.root / "logs/webchat-self-improve.log").write_text(
            "[2026-09-27] self-improve tick started\n"
        )
        with patch.object(self.chat, "_cached_launchd_loaded", return_value=True):
            status = self.chat.self_improve_status()
        self.assertFalse(status.get("loop_ready"))
        self.assertEqual(status.get("tick_ok_streak", 0), 0)

    def test_self_improve_healthy_flag(self):
        (self.root / "conductor/launchd").mkdir(parents=True, exist_ok=True)
        (self.root / "conductor/launchd/com.jeff.bob-webchat-self-improve.plist").write_text("plist")
        (self.root / "conductor/webchat/self_improve_tick.sh").write_text("#!/bin/bash\n")
        (self.root / "logs").mkdir(parents=True, exist_ok=True)
        (self.root / "logs/webchat-self-improve.log").write_text("[2026-09-27] self-improve tick OK webchat=0 failover=0 sha=abc\n")
        with patch.object(self.chat, "_cached_launchd_loaded", return_value=True):
            status = self.chat.self_improve_status()
        self.assertTrue(status.get("healthy"))
        self.assertIn("tick_ok_streak", status)
        self.assertIn("loop_ready", status)
        self.assertTrue(status.get("loop_ready"))
        self.assertGreaterEqual(status.get("tick_ok_streak", 0), 1)

    def test_assistant_reply_carries_request_id(self):
        request_id = str(uuid.uuid4())
        value = self.chat.submit(self.identifier, "status", request_id)
        assistant = next(m for m in value["messages"] if m["role"] == "assistant")
        self.assertEqual(assistant.get("request_id"), request_id)

    def test_provider_reply_preserves_request_id(self):
        self.fake.hold.clear()
        request_id = str(uuid.uuid4())
        self.chat.submit(self.identifier, "What does this mean in one sentence?", request_id)
        self.fake.hold.set()
        self.wait()
        assistant = self.chat.history(self.identifier)["messages"][-1]
        self.assertEqual(assistant["status"], "done")
        self.assertEqual(assistant.get("request_id"), request_id)
        self.assertEqual(assistant.get("provider"), "codex")

    def test_self_improve_failed_line_not_recent_ok(self):
        (self.root / "conductor/launchd").mkdir(parents=True, exist_ok=True)
        (self.root / "conductor/launchd/com.jeff.bob-webchat-self-improve.plist").write_text("plist")
        (self.root / "conductor/webchat/self_improve_tick.sh").write_text("#!/bin/bash\n")
        (self.root / "logs").mkdir(parents=True, exist_ok=True)
        (self.root / "logs/webchat-self-improve.log").write_text(
            "[2026-09-27] self-improve tick failed tests\n"
        )
        status = self.chat.self_improve_status()
        self.assertFalse(status.get("recent_tick_ok"))
        self.assertFalse(status.get("loop_ready"))

    def test_conductor_snapshot_plain_hints(self):
        from ops_panel import conductor_snapshot

        snap = conductor_snapshot(self.root)
        self.assertIn("round_hint", snap)
        self.assertNotIn("run council on:", snap.get("council_hint", "").lower())
        self.assertIn("approve", snap.get("council_hint", "").lower())

    def test_music_coach_in_chat(self):
        request_id = str(uuid.uuid4())
        value = self.chat.submit(self.identifier, "suggest chords for a folk song", request_id)
        assistant = value["messages"][-1]
        self.assertEqual(assistant["status"], "done")
        self.assertEqual(assistant.get("provider"), "state")
        self.assertIn("chord", assistant["content"].lower())

    def test_bob_parity_eval_runs(self):
        from bob_parity_eval import run_eval
        from app import state_ledger

        state_ledger.write_now(self.root, "offline parity fixture", sha="fedcba1")
        result = run_eval(self.root)
        self.assertEqual(result["passed"], result["total"], result["cases"])
        self.assertEqual(result["total"], 96)

    def test_catchup_event_ack_cursor(self):
        ledger_dir = Path(__file__).resolve().parent.parent / "state"
        if str(ledger_dir) not in sys.path:
            sys.path.insert(0, str(ledger_dir))
        import ledger as state_ledger
        import alignment_events

        state_ledger.record_webchat_turn(self.root, ask="ack drill turn", provider="state")
        state_ledger.write_catchup(self.root)
        self.assertIn("ack drill", (self.root / "conductor/state/BOB-CATCHUP.md").read_text())
        seq = alignment_events.latest_seq(self.root)
        state_ledger.ack_events_for_bob(self.root, seq=seq)
        loaded = state_ledger.load_state(self.root)
        self.assertGreaterEqual(int(loaded.get("bob_events_ack_seq") or 0), seq)

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
