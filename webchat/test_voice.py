"""Voice security, chat parity, transcript races, and credential contracts."""
import copy
import http.client
import json
from pathlib import Path
import subprocess
import sys
import time
import threading
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from app import Chat, RequestError
from failover import AllDown
from providers import Providers, clean_env, run
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

    def test_interrupted_waiting_story_allows_next_version_tool(self):
        user = self.entry('Tell me a very long story about a sailor.')
        self.save_entries(user)
        with patch.object(self.fake, 'reply', side_effect=AllDown([], time.time() + 300, 'saved prompt')):
            request = self.chat.voice.tool(self.call, self.owner, user['turn_id'])
            self.wait()
        self.save_entries(self.entry('The story is waiting.', role='assistant', turn=user['turn_id']),
                          self.entry('Stop. Just say okay Jeff.', order=1))
        result = self.chat.voice.interrupt(self.call, self.owner, user['turn_id'])
        self.assertTrue(result['settled'])
        rows = self.chat.get(self.identifier)['messages']
        answer = next(m for m in rows if m.get('request_id') == request['request_id'] and m['role'] == 'assistant')
        self.assertEqual(answer['status'], 'cancelled')
        self.assertNotIn('retry_prompt', self.chat.get(self.identifier))
        replay = self.chat.voice.tool(self.call, self.owner, user['turn_id'])
        self.assertEqual(replay['request_id'], request['request_id'])
        self.assertEqual(replay['conversation']['messages'], self.chat.public(self.chat.get(self.identifier))['messages'])
        version = self.entry('What version are you running?', order=2)
        self.save_entries(version)
        answer = self.chat.voice.tool(self.call, self.owner, version['turn_id'])['conversation']['messages'][-1]
        self.assertEqual(answer['provider'], 'dispatcher')

    def test_voice_interruption_before_admission_cannot_start_later(self):
        user = self.entry('Tell me a story.')
        self.save_entries(user)
        result = self.chat.voice.interrupt(self.call, self.owner, user['turn_id'])
        self.assertEqual(result['state'], 'not_started')
        self.assertTrue(result['settled'])
        for _ in range(2):
            with self.assertRaises(VoiceError):
                self.chat.voice.tool(self.call, self.owner, user['turn_id'])
        self.assertEqual(self.fake.calls, [])
        self.assertEqual(len(self.chat.get(self.identifier)['messages']), 1)

    def test_voice_interruption_is_owned_and_turn_bound(self):
        user = self.entry('Tell me a story.')
        self.save_entries(user)
        for call, owner, turn in ((self.call, 'other', user['turn_id']),
                                  (str(uuid.uuid4()), self.owner, user['turn_id']),
                                  (self.call, self.owner, str(uuid.uuid4())),
                                  (self.call, self.owner, 'invalid')):
            with self.subTest(call=call, owner=owner, turn=turn), self.assertRaises(VoiceError):
                self.chat.voice.interrupt(call, owner, turn)
        self.assertFalse(self.chat.voice.calls[self.call].get('interrupted_turns'))

    def test_late_voice_interruption_preserves_newer_reply_and_completed_effect(self):
        from task_dispatch import task_queue
        action = self.entry('Start a job: write unit tests for a pretend blue widget.')
        self.save_entries(action)
        receipt = self.chat.voice.tool(self.call, self.owner, action['turn_id'])
        before = copy.deepcopy(task_queue.tasks(self.root))
        later = self.entry('Tell me a short story.', order=1)
        self.save_entries(later)
        self.fake.hold.clear()
        try:
            next_request = self.chat.voice.tool(self.call, self.owner, later['turn_id'])
            info = self.chat.workers[self.identifier]
            result = self.chat.voice.interrupt(self.call, self.owner, action['turn_id'])
            self.assertEqual(result['state'], 'completed')
            self.assertTrue(result['settled'])
            self.assertFalse(info['cancel'].is_set())
            self.assertEqual(task_queue.tasks(self.root), before)
            replay = self.chat.voice.tool(self.call, self.owner, action['turn_id'])
            self.assertEqual(replay['request_id'], receipt['request_id'])
            self.assertNotEqual(next_request['request_id'], receipt['request_id'])
        finally:
            self.fake.hold.set()
            self.wait()

    def test_running_voice_interrupt_waits_for_matching_worker_exit(self):
        user = self.entry('Tell me a short story.')
        self.save_entries(user)
        self.fake.hold.clear()
        try:
            request = self.chat.voice.tool(self.call, self.owner, user['turn_id'])
            result = self.chat.voice.interrupt(self.call, self.owner, user['turn_id'])
            self.assertFalse(result['settled'])
            self.assertTrue(self.chat.workers[self.identifier]['cancel'].is_set())
            answer = next(m for m in self.chat.get(self.identifier)['messages']
                          if m.get('request_id') == request['request_id'] and m['role'] == 'assistant')
            self.assertEqual(answer['status'], 'cancelled')
        finally:
            self.fake.hold.set()
            self.wait()
        self.assertTrue(self.chat.voice.interrupt(self.call, self.owner, user['turn_id'])['settled'])

    def test_waiting_voice_interrupt_during_worker_cleanup_clears_retry(self):
        user = self.entry('Tell me a short story.')
        self.save_entries(user)
        observed = []
        save = self.chat.save
        def interrupt_waiting(value):
            save(value)
            if any(m.get('status') == 'waiting' for m in value['messages']):
                observed.append(self.chat.voice.interrupt(self.call, self.owner, user['turn_id']))
        with patch.object(self.chat, 'save', side_effect=interrupt_waiting), \
                patch.object(self.fake, 'reply', side_effect=AllDown([], time.time() + 300, 'saved prompt')):
            self.chat.voice.tool(self.call, self.owner, user['turn_id'])
            self.wait()
        self.assertEqual(len(observed), 1)
        self.assertFalse(observed[0]['settled'])
        value = self.chat.get(self.identifier)
        self.assertEqual(value['messages'][-1]['status'], 'cancelled')
        self.assertNotIn('retry_prompt', value)

    def test_pending_voice_reply_cannot_report_settled_without_matching_worker(self):
        user = self.entry('Tell me a short story.')
        self.save_entries(user)
        with patch.object(self.fake, 'reply', side_effect=AllDown([], time.time() + 300, 'saved prompt')):
            request = self.chat.voice.tool(self.call, self.owner, user['turn_id'])
            self.wait()
        answer = next(m for m in self.chat.get(self.identifier)['messages']
                      if m.get('request_id') == request['request_id'] and m['role'] == 'assistant')
        newer = {'reply_id': str(uuid.uuid4()), 'cancel': threading.Event()}
        try:
            for status, worker in (('waiting', newer), ('running', None), ('queued', None)):
                with self.subTest(status=status):
                    answer['status'] = status
                    if worker:
                        self.chat.workers[self.identifier] = worker
                    else:
                        self.chat.workers.pop(self.identifier, None)
                    result = self.chat.voice.interrupt(self.call, self.owner, user['turn_id'])
                    self.assertFalse(result['settled'])
                    self.assertEqual(result['state'], 'stopping')
                    self.assertEqual(answer['status'], status)
                    self.assertFalse(newer['cancel'].is_set())
        finally:
            self.chat.workers.pop(self.identifier, None)

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
                       lambda: self.chat.voice.interrupt(self.call, "other", str(uuid.uuid4())),
                       lambda: self.chat.voice.tool(self.call, "other", str(uuid.uuid4()))):
            with self.assertRaises(VoiceError) as cm: action()
            self.assertEqual(cm.exception.status, 404)
        with self.assertRaises(VoiceError) as cm: self.chat.voice.start(self.identifier, self.owner)
        self.assertEqual(cm.exception.status, 409)

    def test_private_text_history_is_not_in_voice_token_context(self):
        self.chat.voice.end(self.call, self.owner)
        value = self.chat.conversations[self.identifier]
        value['messages'].append(dict(id=str(uuid.uuid4()), role='assistant', status='done',
                                      content='Private message body and wbtxt-secret', texting=True))
        value['messages'].append(dict(id=str(uuid.uuid4()), role='assistant', status='done',
                                      content='Private memory view copper-puffin-739', private_memory=True))
        self.chat.voice.start(self.identifier, self.owner)
        prompt = json.dumps(self.configs[-1])
        self.assertNotIn('Private message body', prompt)
        self.assertNotIn('wbtxt-secret', prompt)
        self.assertNotIn('copper-puffin-739', prompt)

    def test_voice_text_command_marks_its_source_with_later_transcripts_present(self):
        source = self.entry('texting help')
        self.save_entries(source, self.entry('Later words', order=1))
        result = self.chat.voice.tool(self.call, self.owner, source['turn_id'])
        rows = result['conversation']['messages']
        self.assertTrue(rows[0]['texting'])
        self.assertFalse(rows[1].get('texting', False))
        self.assertEqual(rows[-1]['provider'], 'texting')

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
        self.assertIn("queued", queued["content"].lower())
        self.assertTrue(queued["task_id"])
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
        self.assertIn("queued", rows[1]["content"].lower())
        self.assertTrue(rows[1]["task_id"])
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
        source = next(m for m in reversed(self.fake.calls[-1]['messages']) if m['role'] == 'user')
        self.assertEqual(source['voice_call_id'], self.call)
        self.assertEqual(source['voice_turn_id'], first['turn_id'])

    def test_saved_spoken_answer_uses_auto_voice_route_and_typed_turn_does_not(self):
        spoken = self.entry('Tell me a very long story about a sailor. Start right away and keep going for several paragraphs.')
        self.save_entries(spoken)
        self.chat.voice.tool(self.call, self.owner, spoken['turn_id']); self.wait()
        provider = Providers(self.root, self.chat.redact)
        usage = {'gemini':dict(cap_usd=50, committed_usd=46), 'minimax':dict(cap_usd=48, committed_usd=8)}
        with patch.object(provider, 'spend', side_effect=lambda name:usage.get(name, {})), \
                patch.object(provider.circuit_for(self.identifier), 'snapshot', return_value={}):
            self.assertEqual(provider.route_order(self.fake.calls[-1])[0], 'gemini')
            self.chat.voice.end(self.call, self.owner)
            self.chat.submit(self.identifier, spoken['content'], str(uuid.uuid4())); self.wait()
            self.assertEqual(provider.route_order(self.fake.calls[-1])[0], 'minimax')

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

    def test_voice_request_reuses_one_user_and_creates_one_reply(self):
        user = self.entry("Hello Bob")
        self.save_entries(user)
        source = self.chat.history(self.identifier)["messages"][0]
        result = self.chat.voice.tool(self.call, self.owner, user["turn_id"])
        self.wait()
        self.chat.voice.tool(self.call, self.owner, user["turn_id"])
        rows = self.chat.history(self.identifier)["messages"]
        self.assertEqual([m["role"] for m in rows], ["user", "assistant"])
        self.assertEqual(rows[0]["id"], source["id"])
        self.assertEqual(rows[1]["voice_order"], source["voice_order"] + 1)
        self.assertEqual(rows[1]["request_id"], result["request_id"])
        self.assertEqual(len(self.fake.calls), 1)

    def test_legacy_source_without_voice_order_can_dispatch_and_save(self):
        user = self.entry("Hello from an older transcript")
        self.save_entries(user)
        del self.chat.conversations[self.identifier]["messages"][0]["voice_order"]
        self.chat.voice.tool(self.call, self.owner, user["turn_id"])
        self.wait()
        self.save_entries(self.entry("Next utterance", order=1))
        rows = self.chat.history(self.identifier)["messages"]
        self.assertEqual(rows[1]["voice_order"], 1)
        self.assertEqual(rows[1]["status"], "done")

    def test_invalid_voice_source_returns_generic_error_without_mutation(self):
        before = self.chat.history(self.identifier)
        with self.assertRaises(RequestError) as cm:
            self.chat.submit(self.identifier, "Hello", str(uuid.uuid4()), source_voice=str(uuid.uuid4()))
        self.assertEqual(cm.exception.status, 400)
        self.assertEqual(cm.exception.message, "Request could not be processed. Please try again.")
        self.assertEqual(self.chat.history(self.identifier), before)
        self.assertEqual(self.fake.calls, [])

    def test_timeout_falls_back_for_absent_or_stale_reply_id(self):
        for reply_id in (None, "stale", "pending"):
            with self.subTest(reply_id=reply_id):
                value = self.chat.conversations[self.identifier]
                value["messages"] = [{"id": "pending", "role": "assistant", "status": "running", "content": ""}]
                if reply_id == "pending":
                    value["messages"].append({"id": "later", "role": "user", "status": "done", "content": "Later speech"})
                self.chat.save(value)
                info = {"started_at": time.time() - self.chat.reply_deadline() - 1, "cancel": threading.Event()}
                if reply_id is not None:
                    info["reply_id"] = reply_id
                self.chat.workers[self.identifier] = info
                try:
                    self.chat.sweep_stuck()
                    self.assertTrue(info["cancel"].is_set())
                    saved = json.loads((self.chat.state / (self.identifier + ".json")).read_text())
                    self.assertEqual(saved["messages"][0]["status"], "error")
                    self.assertIn("timed out", saved["messages"][0]["content"])
                    if reply_id == "pending":
                        self.assertEqual(saved["messages"][1]["content"], "Later speech")
                finally:
                    self.chat.workers.pop(self.identifier)
        value["messages"] = []
        self.chat.workers[self.identifier] = info
        try:
            self.chat.sweep_stuck()  # Empty history must also be safe.
        finally:
            self.chat.workers.pop(self.identifier)

    def test_concurrent_voice_and_text_rejected(self):
        barrier = threading.Barrier(3)
        entries = [self.entry("Spoken turn " + str(n), order=n) for n in range(8)]
        def transcribe():
            barrier.wait(timeout=3)
            for entry in entries:
                self.save_entries(entry)
        def type_messages():
            barrier.wait(timeout=3)
            for _ in entries:
                with self.assertRaises(RequestError) as cm:
                    self.chat.submit(self.identifier, "Typed during voice", str(uuid.uuid4()))
                self.assertEqual(cm.exception.status, 409)
        with ThreadPoolExecutor(max_workers=2) as pool:
            writing, typing = pool.submit(transcribe), pool.submit(type_messages)
            barrier.wait(timeout=3)
            writing.result(timeout=5)
            typing.result(timeout=5)
        rows = self.chat.history(self.identifier)["messages"]
        self.assertEqual([m["content"] for m in rows], [e["content"] for e in entries])
        self.assertEqual(self.fake.calls, [])

    def test_concurrent_call_start_and_text_have_only_one_winner(self):
        self.chat.voice.end(self.call, self.owner)
        self.fake.hold.clear()
        barrier = threading.Barrier(3)
        def attempt(action):
            barrier.wait(timeout=3)
            try:
                action()
                return "accepted"
            except (VoiceError, RequestError) as exc:
                return exc.status
        with ThreadPoolExecutor(max_workers=2) as pool:
            voice = pool.submit(attempt, lambda: self.chat.voice.start(self.identifier, self.owner))
            text = pool.submit(attempt, lambda: self.chat.submit(self.identifier, "Hello", str(uuid.uuid4())))
            barrier.wait(timeout=3)
            results = [voice.result(timeout=5), text.result(timeout=5)]
        self.assertCountEqual(results, ["accepted", 409])
        self.assertNotEqual(self.chat.voice.active(self.identifier), self.identifier in self.chat.workers)

    def test_abandoned_tab_recovers_at_45_seconds_without_touching_other_call(self):
        self.chat.voice.end(self.call, self.owner)
        now = time.time()
        with patch("voice.time.time", return_value=now) as clock:
            abandoned = self.chat.voice.start(self.identifier, self.owner)["call_id"]
            other_id = self.chat.new_conversation()["id"]
            other = self.chat.voice.start(other_id, "other-session")["call_id"]
            clock.return_value = now + 44.999
            self.assertTrue(self.chat.voice.active(self.identifier))
            with self.assertRaises(VoiceError) as cm:
                self.chat.voice.start(self.identifier, self.owner)
            self.assertEqual(cm.exception.status, 409)
            self.chat.voice.pulse(other, "other-session")
            clock.return_value = now + 45
            self.assertFalse(self.chat.voice.active(self.identifier))
            for action in (lambda: self.chat.voice.pulse(abandoned, self.owner),
                           lambda: self.chat.voice.tool(abandoned, self.owner, str(uuid.uuid4()))):
                with self.assertRaises(VoiceError) as cm:
                    action()
                self.assertEqual(cm.exception.status, 410)
            self.chat.voice.transcript(abandoned, self.owner, [self.entry("Final words after tab loss")])
            replacement = self.chat.voice.start(self.identifier, self.owner)["call_id"]
            self.assertNotEqual(replacement, abandoned)
            self.assertTrue(self.chat.voice.active(other_id))
            self.assertEqual(self.chat.history(self.identifier)["messages"][0]["content"], "Final words after tab loss")

    def test_token_expiry_mid_call_allows_flush_but_requires_explicit_restart(self):
        self.chat.voice.end(self.call, self.owner)
        now = time.time()
        with patch("voice.time.time", return_value=now) as clock:
            call = self.chat.voice.start(self.identifier, self.owner)
            user = self.entry("Keep this near expiry")
            for elapsed in range(30, 600, 30):
                clock.return_value = now + elapsed
                self.chat.voice.pulse(call["call_id"], self.owner)
            clock.return_value = call["expires_at"] - .001
            self.chat.voice.pulse(call["call_id"], self.owner)
            self.assertTrue(self.chat.voice.active(self.identifier))
            clock.return_value = call["expires_at"]
            self.chat.voice.transcript(call["call_id"], self.owner, [user])
            for action in (lambda: self.chat.voice.pulse(call["call_id"], self.owner),
                           lambda: self.chat.voice.tool(call["call_id"], self.owner, user["turn_id"])):
                with self.assertRaises(VoiceError) as cm:
                    action()
                self.assertEqual(cm.exception.status, 410)
            self.assertFalse(self.chat.voice.active(self.identifier))
            self.assertEqual(len(self.configs), 2)  # No automatic refresh/mint.
            self.assertEqual(self.fake.calls, [])
            self.chat.voice.start(self.identifier, self.owner)
            self.assertIn(user["content"], self.configs[-1]["systemInstruction"]["parts"][0]["text"])

    def test_interrupted_tool_retry_keeps_transcript_and_dispatches_once(self):
        self.fake.hold.clear()
        user = self.entry("What is my favorite color?")
        self.save_entries(user)
        result = self.chat.voice.tool(self.call, self.owner, user["turn_id"])
        reply = self.entry("I am checking", role="assistant", turn=user["turn_id"], version=1)
        self.save_entries(reply)
        interrupted = dict(reply, interrupted=True, version=2)
        self.save_entries(interrupted)
        self.save_entries(reply)  # A delayed retry cannot undo the interruption.
        retry = self.chat.voice.tool(self.call, self.owner, user["turn_id"])
        self.assertEqual(retry["request_id"], result["request_id"])
        self.fake.hold.set()
        self.wait()
        later = self.entry("What about tomorrow?", order=1)
        self.save_entries(later)
        self.chat.voice.tool(self.call, self.owner, later["turn_id"])
        self.wait()
        rows = self.chat.history(self.identifier)["messages"]
        spoken = next(m for m in rows if m.get("provider") == "voice")
        self.assertTrue(spoken["voice_interrupted"])
        self.assertEqual(spoken["voice_version"], 2)
        receipts = [m for m in rows if m["role"] == "assistant" and m.get("request_id") == result["request_id"]]
        self.assertEqual(len(receipts), 1)
        self.assertEqual(receipts[0]["status"], "done")
        self.assertEqual(len(self.fake.calls), 2)

    def test_call_start_rejects_queued_running_and_waiting_chat_reply(self):
        self.chat.voice.end(self.call, self.owner)
        self.fake.hold.clear()
        entered = threading.Event()
        original = self.fake.reply
        def reply(*args):
            entered.set()
            return original(*args)
        with patch.object(self.fake, "reply", side_effect=reply):
            with self.chat.lock:
                self.chat.submit(self.identifier, "Tell me about the sky", str(uuid.uuid4()))
                self.assertEqual(self.chat.get(self.identifier)["messages"][-1]["status"], "queued")
                with self.assertRaises(VoiceError) as cm:
                    self.chat.voice.start(self.identifier, self.owner)
                self.assertEqual(cm.exception.status, 409)
            self.assertTrue(entered.wait(3))
            self.assertEqual(self.chat.get(self.identifier)["messages"][-1]["status"], "running")
            with self.assertRaises(VoiceError) as cm:
                self.chat.voice.start(self.identifier, self.owner)
            self.assertEqual(cm.exception.status, 409)
            self.chat.stop(self.identifier)
            self.wait()
        with patch.object(self.fake, "reply", side_effect=AllDown([], time.time() + 60, "pending prompt")):
            self.chat.submit(self.identifier, "What about the weather?", str(uuid.uuid4()))
            self.wait()
        self.assertNotIn(self.identifier, self.chat.workers)
        self.assertEqual(self.chat.get(self.identifier)["messages"][-1]["status"], "waiting")
        with self.assertRaises(VoiceError) as cm:
            self.chat.voice.start(self.identifier, self.owner)
        self.assertEqual(cm.exception.status, 409)
        self.assertEqual(len(self.configs), 1)
        self.chat.stop(self.identifier)
        self.assertTrue(self.chat.voice.start(self.identifier, self.owner)["call_id"])

    def test_token_limit_reserved_before_concurrent_provider_request_finishes(self):
        self.chat.voice.end(self.call, self.owner)
        for _ in range(8):
            call = self.chat.voice.start(self.identifier, self.owner)["call_id"]
            self.chat.voice.end(call, self.owner)
        other = self.chat.new_conversation()["id"]
        entered, release = threading.Event(), threading.Event()
        def mint(*args):
            entered.set()
            if not release.wait(5):
                raise RuntimeError("Test did not release token request")
            return "auth_tokens/test"
        with patch.object(self.chat.voice, "token_factory", side_effect=mint) as token:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(self.chat.voice.start, self.identifier, self.owner)
                try:
                    self.assertTrue(entered.wait(3))
                    with self.assertRaises(VoiceError) as cm:
                        self.chat.voice.start(other, self.owner)
                    self.assertEqual(cm.exception.status, 429)
                    self.assertEqual(token.call_count, 1)
                finally:
                    release.set()
                self.assertTrue(future.result(timeout=3)["call_id"])

    def test_call_start_checks_pending_reply_even_after_late_transcript(self):
        user = self.entry("Tell me about the sky")
        self.save_entries(user)
        with patch.object(self.fake, "reply", side_effect=AllDown([], time.time() + 60, "pending prompt")):
            self.chat.voice.tool(self.call, self.owner, user["turn_id"])
            self.wait()
        self.chat.voice.end(self.call, self.owner)
        self.save_entries(self.entry("Goodbye", order=1))
        with self.assertRaises(VoiceError) as cm:
            self.chat.voice.start(self.identifier, self.owner)
        self.assertEqual(cm.exception.status, 409)
        self.assertEqual(len(self.configs), 1)
        with self.assertRaises(RequestError) as cm:
            self.chat.submit(self.identifier, "Hello again", str(uuid.uuid4()))
        self.assertEqual(cm.exception.status, 409)
        self.chat.stop(self.identifier)
        rows = self.chat.history(self.identifier)["messages"]
        self.assertEqual(rows[1]["status"], "cancelled")
        self.assertEqual(rows[-1]["content"], "Goodbye")
        self.assertTrue(self.chat.voice.start(self.identifier, self.owner)["call_id"])

    def test_token_rate_limit_survives_hangup_and_resets_after_one_minute(self):
        self.chat.voice.end(self.call, self.owner)
        with patch("voice.time.monotonic", return_value=time.monotonic()) as clock:
            for _ in range(9):
                call = self.chat.voice.start(self.identifier, self.owner)["call_id"]
                self.chat.voice.end(call, self.owner)
            with self.assertRaises(VoiceError) as cm:
                self.chat.voice.start(self.identifier, self.owner)
            self.assertEqual(cm.exception.status, 429)
            self.assertEqual(len(self.configs), 10)
            self.assertFalse(self.chat.voice.active(self.identifier))
            clock.return_value += 60
            self.assertTrue(self.chat.voice.start(self.identifier, self.owner)["call_id"])

    def test_failed_token_requests_are_limited_even_across_login_sessions(self):
        self.chat.voice.end(self.call, self.owner)
        with patch.object(self.chat.voice, "token_factory", side_effect=VoiceError(503, "Unavailable")) as mint:
            for _ in range(9):
                with self.assertRaises(VoiceError) as cm:
                    self.chat.voice.start(self.identifier, self.owner)
                self.assertEqual(cm.exception.status, 503)
            with self.assertRaises(VoiceError) as cm:
                self.chat.voice.start(self.identifier, self.owner)
            self.assertEqual(cm.exception.status, 429)
            self.assertEqual(mint.call_count, 9)
            for n in range(10):
                with self.assertRaises(VoiceError) as cm:
                    self.chat.voice.start(self.identifier, "session-" + str(n))
                self.assertEqual(cm.exception.status, 503)
            with self.assertRaises(VoiceError) as cm:
                self.chat.voice.start(self.identifier, "another-login")
            self.assertEqual(cm.exception.status, 429)
            self.assertEqual(mint.call_count, 19)
            self.assertFalse(self.chat.voice.active(self.identifier))


class VoiceHTTPTests(fixtures.HTTPTests):
    def test_http_voice_interrupt_reaps_real_writer_tree_without_replay(self):
        self.login()
        self.chat.providers.snapshot = lambda **_: []
        self.chat.voice.token_factory = lambda *_: 'auth_tokens/test'
        marker = self.root / 'owned-writer.json'
        invocations = []
        original_reply = self.fake.reply
        def blocked_writer(conversation, cancel, progress):
            invocations.append(conversation['messages'][-1]['request_id'])
            progress('gemini', [])
            run([sys.executable, str(Path(__file__).with_name('drill_child.py')), str(marker)],
                cwd=self.root, env=dict(clean_env(), BOB_WEBCHAT_DRILLS='1'), cancel=cancel, timeout=5)
            raise AssertionError('Cancelled writer returned normally')
        self.fake.reply = blocked_writer
        code, _, body = self.request('POST', '/api/voice/start', {'conversation_id': self.identifier})
        self.assertEqual(code, 201)
        call, turn = json.loads(body)['call_id'], str(uuid.uuid4())
        payload = dict(call_id=call, turn_id=turn)
        entry = dict(turn_id=turn, role='user', content='Tell me a story about a sailor.', order=0)
        self.assertEqual(self.request('POST', '/api/voice/transcript', dict(call_id=call, entries=[entry]))[0], 200)
        try:
            code, _, body = self.request('POST', '/api/voice/tool', payload)
            self.assertEqual(code, 200)
            request = json.loads(body)['request_id']
            deadline = time.monotonic() + 3
            identities = None
            while time.monotonic() < deadline:
                try:
                    identities = json.loads(marker.read_text())
                    break
                except (OSError, ValueError):
                    time.sleep(.01)
            self.assertIsNotNone(identities)
            self.assertEqual(self.request('POST', '/api/voice/interrupt', payload)[0], 200)
            self.wait()
            for pid in (identities['parent'], *identities['children']):
                state = subprocess.run(['ps', '-p', str(pid), '-o', 'stat='],
                                       capture_output=True, text=True, timeout=2).stdout.strip()
                self.assertTrue(not state or state.startswith('Z'), (pid, state))
            for _ in range(2):
                self.assertEqual(self.request('POST', '/api/voice/tool', payload)[0], 200)
            self.assertEqual(invocations, [request])
            self.assertNotIn(self.identifier, self.chat.workers)
        finally:
            self.chat.stop(self.identifier)
            self.wait()
            self.fake.reply = original_reply
        self.assertEqual(self.request('POST', '/api/voice/end', {'call_id': call})[0], 200)
        code, _, _ = self.request('POST', '/api/messages', dict(conversation_id=self.identifier,
            message='Describe a blue cloud.', request_id=str(uuid.uuid4()), provider='gemini'))
        self.assertEqual(code, 202)
        self.wait()
        self.assertEqual(self.chat.history(self.identifier)['messages'][-1]['content'], 'A saved reply.')

    def test_owned_http_voice_interrupt_cancels_waiting_reply_then_accepts_next_tool(self):
        self.login()
        self.chat.providers.snapshot = lambda **_: []
        self.chat.voice.token_factory = lambda *_: 'auth_tokens/test'
        code, _, body = self.request('POST', '/api/voice/start', {'conversation_id': self.identifier})
        self.assertEqual(code, 201)
        call = json.loads(body)['call_id']
        turn = str(uuid.uuid4())
        payload = {'call_id': call, 'turn_id': turn}
        entry = {'turn_id': turn, 'role': 'user', 'content': 'Tell me a long story.', 'order': 0}
        self.assertEqual(self.request('POST', '/api/voice/transcript', {'call_id': call, 'entries': [entry]})[0], 200)
        with patch.object(self.fake, 'reply', side_effect=AllDown([], time.time() + 300, 'saved prompt')):
            self.assertEqual(self.request('POST', '/api/voice/tool', payload)[0], 200)
            self.wait()
        self.assertEqual(self.request('POST', '/api/voice/interrupt', payload, {'Origin': 'https://evil.example'})[0], 403)
        code, _, body = self.request('POST', '/api/voice/interrupt', payload)
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body), {'ok': True, 'state': 'cancelled', 'settled': True})
        self.assertEqual(self.request('POST', '/api/voice/interrupt', payload)[0], 200)
        later = dict(entry, turn_id=str(uuid.uuid4()), content='What version are you running?', order=1)
        self.assertEqual(self.request('POST', '/api/voice/transcript', {'call_id': call, 'entries': [later]})[0], 200)
        code, _, body = self.request('POST', '/api/voice/tool', dict(payload, turn_id=later['turn_id']))
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body)['conversation']['messages'][-1]['provider'], 'dispatcher')

    def test_logout_during_token_request_returns_no_credential_and_leaves_reads_responsive(self):
        self.login()
        self.chat.providers.snapshot = lambda **_: []
        entered, release = threading.Event(), threading.Event()

        def mint(*_):
            entered.set()
            if not release.wait(5):
                raise AssertionError("Fixture request was not released")
            return "auth_tokens/private-late-fixture"

        with patch.object(self.chat.voice, "token_factory", side_effect=mint) as factory:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(self.request, "POST", "/api/voice/start", {"conversation_id": self.identifier})
                try:
                    self.assertTrue(entered.wait(2))
                    self.assertEqual(self.request("GET", "/api/version")[0], 200)
                    self.assertEqual(self.request("POST", "/api/logout", {})[0], 200)
                    self.assertFalse(future.done())
                finally:
                    release.set()
                code, _, body = future.result(3)
            self.assertEqual(factory.call_count, 1)
        self.assertEqual(code, 401)
        self.assertNotIn("token", json.loads(body))
        self.assertNotIn("private-late-fixture", body)
        self.assertFalse(self.chat.voice.busy(self.identifier))

    def test_session_revoked_after_dispatch_is_rechecked_before_token_request(self):
        self.login()
        original = self.chat.voice.start

        def after_dispatch(*args, **kwargs):
            with self.chat.auth_lock:
                self.chat.sessions.clear()
            return original(*args, **kwargs)

        with patch.object(self.chat.voice, "start", side_effect=after_dispatch), \
                patch.object(self.chat.voice, "token_factory") as mint:
            code, _, body = self.request("POST", "/api/voice/start", {"conversation_id": self.identifier})
        self.assertEqual(code, 401)
        mint.assert_not_called()
        self.assertEqual(self.chat.voice.calls, {})
        self.assertNotIn("token", json.loads(body))

    def test_session_expiring_during_token_request_is_rechecked_before_response(self):
        self.login()
        self.chat.providers.snapshot = lambda **_: []

        def mint(*_):
            with self.chat.auth_lock:
                for session in self.chat.sessions.values():
                    session["expires"] = time.time() - 1
            return "auth_tokens/private-expired-fixture"

        with patch.object(self.chat.voice, "token_factory", side_effect=mint):
            code, _, body = self.request("POST", "/api/voice/start", {"conversation_id": self.identifier})
        self.assertEqual(code, 401)
        self.assertNotIn("token", json.loads(body))
        self.assertNotIn("private-expired-fixture", body)
        self.assertFalse(self.chat.voice.busy(self.identifier))

    def test_voice_auth_csrf_origin_and_tailnet(self):
        for route in ("start", "transcript", "tool", "interrupt", "end", "pulse"):
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

    def test_voice_csrf_required(self):
        self.login()
        first_csrf = self.csrf
        self.login()  # A token belonging to another authenticated session is invalid too.
        for token in (None, "", "wrong", first_csrf):
            for route in ("start", "transcript", "tool", "interrupt", "end", "pulse"):
                with self.subTest(route=route, token=token):
                    # Send raw JSON so the fixture does not insert a CSRF header.
                    connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
                    headers = {"Cookie": self.cookie, "Origin": self.origin, "Content-Type": "application/json"}
                    if token is not None:
                        headers["X-CSRF-Token"] = token
                    with patch.object(self.chat.voice, route) as action:
                        connection.request("POST", "/api/voice/" + route, "{}", headers)
                        response = connection.getresponse()
                        response.read()
                        connection.close()
                        self.assertEqual(response.status, 403)
                        action.assert_not_called()

    def test_voice_token_rate_limit_http(self):
        self.login()
        self.chat.providers.snapshot = lambda **_: []
        with patch.object(self.chat.voice, "token_factory", return_value="auth_tokens/test") as mint:
            for _ in range(10):
                code, _, body = self.request("POST", "/api/voice/start", {"conversation_id": self.identifier})
                self.assertEqual(code, 201)
                call = json.loads(body)["call_id"]
                self.assertEqual(self.request("POST", "/api/voice/end", {"call_id": call})[0], 200)
            code, _, body = self.request("POST", "/api/voice/start", {"conversation_id": self.identifier})
            self.assertEqual(code, 429)
            self.assertEqual(mint.call_count, 10)
            self.assertNotIn("token", json.loads(body))


def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite(loader.loadTestsFromTestCase(VoiceTests))
    for name in VoiceHTTPTests.__dict__:
        if name.startswith("test_"):
            suite.addTest(VoiceHTTPTests(name))
    return suite


if __name__ == "__main__":
    unittest.main()
