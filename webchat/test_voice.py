"""Voice security, chat parity, transcript races, and credential contracts."""
import copy
import json
import time
import threading
import unittest
import uuid
from unittest.mock import patch

from app import Chat, RequestError
from providers import Providers
from job_queue import parse_start
import test_webchat as fixtures
from voice import VoiceError, api_key, create_token, MODEL, SOCKET_URL


class VoiceTests(fixtures.Fixture):
    def setUp(self):
        super().setUp()
        self.fake.snapshot = lambda **_: [{"path": "bob-brain/memory/profile.md", "text": "Jeff likes amber sailboats."}]
        self.configs = []
        def token(root, setup, expires):
            self.configs.append(copy.deepcopy(setup))
            return "auth_tokens/private-ephemeral-fixture"
        self.chat.voice.token_factory = token
        self.owner = "owner-session"
        self.call = self.chat.voice.start(self.identifier, self.owner)["call_id"]

    def entry(self, text="Hello Bob", role="user", turn=None, order=0, **extra):
        return dict(turn_id=turn or str(uuid.uuid4()), role=role, content=text, order=order, **extra)

    def save_entries(self, *entries):
        return self.chat.voice.transcript(self.call, self.owner, list(entries))

    def test_same_memory_and_server_locked_tools(self):
        config = self.configs[0]
        self.assertEqual(config["model"], "models/" + MODEL)
        self.assertIn("amber sailboats", config["systemInstruction"]["parts"][0]["text"])
        self.assertIn("Never merge", config["systemInstruction"]["parts"][0]["text"])
        self.assertEqual(config["tools"][0]["functionDeclarations"][0]["parameters"]["properties"], {})
        self.assertEqual(config["realtimeInputConfig"]["activityHandling"], "START_OF_ACTIVITY_INTERRUPTS")

    def test_owned_call_and_duplicate_start(self):
        for action in (lambda: self.chat.voice.end(self.call, "other"),
                       lambda: self.chat.voice.transcript(self.call, "other", []),
                       lambda: self.chat.voice.tool(self.call, "other", str(uuid.uuid4()))):
            with self.assertRaises(VoiceError) as cm: action()
            self.assertEqual(cm.exception.status, 404)
        with self.assertRaises(VoiceError) as cm: self.chat.voice.start(self.identifier, self.owner)
        self.assertEqual(cm.exception.status, 409)

    def test_voice_inherits_current_saved_permissions_after_typed_resume(self):
        self.chat.voice.end(self.call, self.owner)
        for text in ("Hold off on Web Bob.", "Resume Web Bob."):
            self.chat.submit(self.identifier, text, str(uuid.uuid4()))
        self.chat.voice.start(self.identifier, self.owner)
        prompt = self.configs[-1]["systemInstruction"]["parts"][0]["text"]
        self.assertIn("Hold off on Web Bob.", prompt)
        permissions = json.loads(prompt.split("SERVER SAVED CHAT PERMISSIONS (override older history and snapshots):\n")[1])
        self.assertEqual(permissions["holds"], {})
        self.assertEqual(permissions["last_permission"]["action"], "resume")

    def test_spoken_hold_and_resume_use_chat_permissions(self):
        def ask(text, order):
            entry = self.entry(text, order=order)
            self.save_entries(entry)
            result = self.chat.voice.tool(self.call, self.owner, entry["turn_id"])
            return result["conversation"]["messages"][-1]
        held = ask("Hold off on Web Bob.", 0)
        self.assertIn("On hold: Web Bob", held["content"])
        blocked = ask("Start a job: improve the Web Bob mobile call tests.", 1)
        self.assertIn("On hold: Web Bob", blocked["content"])
        self.assertFalse(blocked.get("task_id"))
        ask("Resume Web Bob.", 2)
        queued = ask("Start a job: improve the Web Bob mobile call tests.", 3)
        self.assertEqual(queued["provider"], "dispatcher")
        self.assertIn("Queued", queued["content"])
        self.assertTrue(queued["task_id"])
        self.assertEqual(self.fake.calls, [])

    def test_transcript_idempotency_order_redaction_and_restart(self):
        user = self.entry("Remember the amber sailboat.")
        reply = self.entry("The amber sailboat.", role="assistant", turn=user["turn_id"], interrupted=True)
        self.save_entries(reply)
        self.save_entries(user, reply)
        self.save_entries(user, reply)
        history = self.chat.history(self.identifier)["messages"]
        self.assertEqual([m["role"] for m in history], ["user", "assistant"])
        self.assertTrue(history[1]["voice_interrupted"])
        restored = Chat(self.folder, self.root, self.fake)
        self.assertEqual(restored.history(self.identifier)["messages"], history)
        restored.close()
        reply["content"] += " " + self.chat.password
        self.save_entries(reply)
        self.assertNotIn(self.chat.password, json.dumps(self.chat.history(self.identifier)))

    def test_invalid_transcripts_are_atomic(self):
        for bad in (None, {}, [None], [self.entry(order=-1)], [self.entry(role="system")],
                    [self.entry(text="x" * 12001)], [self.entry(turn="../../keys.env")]):
            with self.assertRaises(VoiceError): self.chat.voice.transcript(self.call, self.owner, bad)
        with self.assertRaises(VoiceError): self.save_entries(self.entry(), self.entry(role="system"))
        self.assertEqual(self.chat.history(self.identifier)["messages"], [])

    def test_tool_uses_original_transcript_once_and_keeps_action_receipt(self):
        user = self.entry("start a job: write tests for a pretend voice widget")
        self.save_entries(user)
        first = self.chat.voice.tool(self.call, self.owner, user["turn_id"])
        second = self.chat.voice.tool(self.call, self.owner, user["turn_id"])
        self.assertEqual(first["request_id"], second["request_id"])
        rows = self.chat.history(self.identifier)["messages"]
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["content"], user["content"])
        self.assertIn("Queued", rows[1]["content"])
        self.assertEqual(self.fake.calls, [])
        with self.assertRaises(VoiceError): self.save_entries(dict(user, content="start a job: changed request"))

    def test_spoken_job_punctuation_uses_same_dispatcher_without_rewriting(self):
        for order, separator in enumerate((": ", ", ", ". ", " ")):
            with self.subTest(separator=separator):
                user = self.entry("Start a job" + separator + "write unit tests for a pretend blue widget.", order=order)
                self.save_entries(user)
                result = self.chat.voice.tool(self.call, self.owner, user["turn_id"])
                receipt = result["conversation"]["messages"][-1]
                self.assertEqual(receipt["provider"], "dispatcher")
                self.assertTrue(receipt["task_id"])
                saved = next(m for m in result["conversation"]["messages"] if m.get("request_id") == result["request_id"] and m["role"] == "user")
                self.assertEqual(saved["content"], user["content"])
        for text in ("Don't start a job, write tests.", "Should I start a job, write tests?",
                     "Start a job? Write tests?", 'Say "start a job, write tests".'):
            self.assertIsNone(parse_start(text))

    def test_tool_refuses_merge_and_requires_saved_speech(self):
        with self.assertRaises(VoiceError): self.chat.voice.tool(self.call, self.owner, str(uuid.uuid4()))
        user = self.entry("merge PR #123")
        self.save_entries(user)
        self.chat.voice.tool(self.call, self.owner, user["turn_id"])
        self.wait()
        self.assertIn("won't merge", self.chat.history(self.identifier)["messages"][-1]["content"])

    def test_late_transcript_does_not_overwrite_async_tool_answer(self):
        self.fake.hold.clear()
        user = self.entry("What was my previous preference?")
        self.save_entries(user)
        result = self.chat.voice.tool(self.call, self.owner, user["turn_id"])
        later = self.entry("Actually, I prefer blue.", order=1)
        self.save_entries(later)
        self.fake.hold.set(); self.wait()
        rows = self.chat.history(self.identifier)["messages"]
        answer = next(m for m in rows if m.get("request_id") == result["request_id"] and m["role"] == "assistant")
        self.assertEqual(answer["content"], "A saved reply.")
        self.assertEqual(rows[-1]["content"], later["content"])

    def test_hangup_expiry_logout_allow_flush_but_not_tool_actions(self):
        for ending in (lambda: self.chat.voice.end(self.call, self.owner),
                       lambda: self.chat.voice.logout(self.owner)):
            ending()
            user = self.entry()
            self.save_entries(user)
            with self.assertRaises(VoiceError) as cm: self.chat.voice.tool(self.call, self.owner, user["turn_id"])
            self.assertEqual(cm.exception.status, 410)
        new = self.chat.voice.start(self.identifier, self.owner)
        self.chat.voice.calls[new["call_id"]]["expires"] = time.time() - 1
        with self.assertRaises(VoiceError): self.chat.voice.tool(new["call_id"], self.owner, str(uuid.uuid4()))

    def test_call_failure_releases_slot_and_typing_guard(self):
        with self.assertRaises(RequestError): self.chat.submit(self.identifier, "Hello", str(uuid.uuid4()))
        self.chat.voice.end(self.call, self.owner)
        with patch.object(self.chat.voice, "token_factory", side_effect=VoiceError(503, "Unavailable")):
            with self.assertRaises(VoiceError): self.chat.voice.start(self.identifier, self.owner)
        self.assertFalse(self.chat.voice.active(self.identifier))
        self.chat.submit(self.identifier, "Hello", str(uuid.uuid4())); self.wait()

    def test_expired_tab_lease_releases_slot_but_allows_final_transcript(self):
        self.chat.voice.pulse(self.call, self.owner)
        self.assertTrue(self.chat.voice.active(self.identifier))
        self.chat.voice.calls[self.call]["lease_expires"] = time.time() - 1
        self.assertFalse(self.chat.voice.active(self.identifier))
        with self.assertRaises(VoiceError): self.chat.voice.pulse(self.call, self.owner)
        self.save_entries(self.entry("Final words"))
        self.assertTrue(self.chat.voice.start(self.identifier, self.owner)["call_id"])

    def test_stale_transcript_write_cannot_roll_back_newer_words(self):
        entry = self.entry("Hello", version=1)
        self.save_entries(entry)
        self.save_entries(dict(entry, content="Hello there", version=3))
        self.save_entries(dict(entry, content="Hello the", version=2))
        self.assertEqual(self.chat.history(self.identifier)["messages"][0]["content"], "Hello there")

    def test_tool_context_is_pinned_before_worker_thread_starts(self):
        original = self.chat.complete
        gate = threading.Event()
        def delayed(identifier, cancel, conversation):
            gate.wait(2)
            original(identifier, cancel, conversation)
        first = self.entry("What is my favorite color?")
        self.save_entries(first)
        with patch.object(self.chat, "complete", side_effect=delayed):
            self.chat.voice.tool(self.call, self.owner, first["turn_id"])
            self.save_entries(self.entry("A different question", order=1))
            gate.set(); self.wait()
        users = [m["content"] for m in self.fake.calls[-1]["messages"] if m["role"] == "user"]
        self.assertEqual(users[-1], first["content"])

    def test_key_file_is_parsed_without_shell_and_never_returned(self):
        path = self.root / "conductor/keys.env"
        path.write_text("export GEMINI_API_KEY='private-fixture-key' # comment\n")
        self.assertEqual(api_key(self.root), "private-fixture-key")
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self): return b'{"name":"auth_tokens/short-lived"}'
        with patch("voice.urlopen", return_value=Response()) as call:
            result = create_token(self.root, self.configs[0], time.time() + 600)
        request = call.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(payload["uses"], 1)
        self.assertNotIn("fieldMask", payload)
        self.assertIn("bidiGenerateContentSetup", payload)
        self.assertNotIn("private-fixture-key", result)
        path.write_text("OTHER_KEY='$(touch impossible)'\n")
        with self.assertRaises(VoiceError): api_key(self.root)

    def test_memory_snapshot_reads_actual_profile(self):
        path = self.root / "bob-brain/memory/profile.md"
        path.parent.mkdir(parents=True); path.write_text("Jeff's favorite color is amber.")
        providers = Providers(self.root, self.chat.redact)
        with patch("live_status_snapshot.build_live_status_snapshot", return_value={}):
            result = providers.snapshot(lite=False, conversation_id=self.identifier)
        self.assertIn("favorite color is amber", json.dumps(result))
        providers.close()


class VoiceHTTPTests(fixtures.HTTPTests):
    def test_voice_auth_csrf_origin_and_tailnet(self):
        for route in ("start", "transcript", "tool", "end"):
            self.assertEqual(self.request("POST", "/api/voice/" + route, {})[0], 401)
        self.login()
        self.chat.providers.snapshot = lambda **_: []
        self.chat.voice.token_factory = lambda *_: "auth_tokens/test"
        payload = {"conversation_id": self.identifier}
        self.assertEqual(self.request("POST", "/api/voice/start", payload, {"X-CSRF-Token": "bad"})[0], 403)
        self.assertEqual(self.request("POST", "/api/voice/start", payload, {"Origin": "https://evil.example"})[0], 403)
        code, headers, body = self.request("POST", "/api/voice/start", payload,
            {"Host": "mini.example.ts.net", "Origin": "https://mini.example.ts.net"})
        self.assertEqual(code, 201)
        self.assertEqual(json.loads(body)["url"], SOCKET_URL)
        self.assertEqual(headers["Permissions-Policy"], "microphone=(self), camera=()")
        self.assertIn("wss://generativelanguage.googleapis.com", headers["Content-Security-Policy"])
        self.assertIn("no-store", headers["Cache-Control"])


def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite(loader.loadTestsFromTestCase(VoiceTests))
    suite.addTest(VoiceHTTPTests("test_voice_auth_csrf_origin_and_tailnet"))
    return suite


if __name__ == "__main__":
    unittest.main()
