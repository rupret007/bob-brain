"""Jeff's 6d6ee27 incident, through the authenticated send/history path."""
import threading
import uuid
from unittest.mock import patch

from app import Chat, Server
from live_redeploy_check import Client
from providers import Providers
from task_dispatch import task_queue
from test_webchat import Fixture


PROMPT = ("Go ahead and restart the AdoptIQ, Fantasy Football and WebJam projects back up "
          "but I want you to only use Gemini and Minimax on them for right now.")
ANSWER = ("AdoptIQ, Fantasy Football and WebJam can be scoped to Gemini and MiniMax. "
          "The worker runner is stopped, so those projects have not restarted. "
          "I can help plan the next step for each project here.")


class StickyGreetingTests(Fixture):
    def test_unsupported_restart_promise_retains_requested_scope_without_claiming_effects(self):
        raw = ("Okay, I'll get AdoptIQ, Fantasy Football, and WebJam restarted. "
               "I'll make sure to only use Gemini and MiniMax for those projects right now.")
        (self.root / 'conductor/SOLO-WORKER').touch()
        with patch.object(self.fake, 'reply', return_value=dict(content=raw, provider='gemini', attempts=[])):
            self.chat.submit(self.identifier, PROMPT, str(uuid.uuid4()))
            self.wait()
        answer = self.chat.history(self.identifier)['messages'][-1]['content']
        for phrase in ('AdoptIQ', 'Fantasy Football', 'WebJam', 'Gemini', 'MiniMax',
                       'not been applied', 'paused in solo mode'):
            self.assertIn(phrase, answer)
        self.assertNotIn("I'll", answer)
        self.assertNotIn('Ready when you are', answer)
        self.assertFalse(task_queue.tasks(self.root))

    def test_restart_scope_fallback_does_not_infer_other_projects_or_saved_model_choice(self):
        from reply_authority import enforce
        from dispatch_receipts import NO_DISPATCH
        raw = dict(content="I'll make sure to maximize the workers.", provider='gemini')
        answer = enforce(self.root, 'Go ahead and restart WebJam using only MiniMax.', raw)
        self.assertIn('WebJam', answer)
        self.assertIn('MiniMax', answer)
        for absent in ('AdoptIQ', 'Gemini', 'paused in solo mode'):
            self.assertNotIn(absent, answer)
        self.assertIn('not been applied', answer)
        self.assertEqual(enforce(self.root, 'Thanks Bob', raw), NO_DISPATCH)
        self.assertEqual(enforce(self.root, 'Do not restart WebJam', raw), NO_DISPATCH)
        self.assertEqual(enforce(self.root, 'Restart all projects', raw), NO_DISPATCH)

    def test_requested_literal_greeting_is_not_rejected(self):
        provider = Providers(self.root, lambda value: value)
        conversation = dict(id=self.identifier, messages=[dict(role='user', content='Go ahead and say exactly: Ready when you are.')])
        with patch.object(provider, 'route_order', return_value=('gemini',)), \
                patch.object(provider, 'prompt', return_value='Say exactly: Ready when you are.'), \
                patch.object(provider, '_call_timed', return_value=('Ready when you are.', None)) as call:
            answer = provider.reply(conversation, threading.Event(), lambda *args: None)
        self.assertEqual(answer['content'], 'Ready when you are.')
        self.assertEqual(call.call_count, 1)

    def start_http(self):
        server = Server(('127.0.0.1', 0), self.chat)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        client = Client('http://127.0.0.1:' + str(server.server_port), self.folder / '.password')
        client.login()
        return client

    def test_exact_prompt_twice_and_after_reload_reaches_model_with_original_turn(self):
        client = self.start_http()
        calls = []

        def model(conversation, cancel, progress):
            user = next(m for m in reversed(conversation['messages']) if m['role'] == 'user')
            calls.append(user['content'])
            return dict(content=ANSWER, provider='gemini', attempts=[])

        with patch.object(self.fake, 'reply', side_effect=model):
            for _ in range(2):
                request = str(uuid.uuid4())
                value, answer = client.submit(self.identifier, PROMPT, request)
                self.assertEqual(answer['provider'], 'gemini')
                self.assertEqual(answer['content'], ANSWER)
                again, duplicate = client.submit(self.identifier, PROMPT, request)
                self.assertEqual(duplicate, answer)
                self.assertEqual(len(again['messages']), len(value['messages']))
            self.assertEqual(calls, [PROMPT, PROMPT])
            self.chat.close()
            self.chat = Chat(self.folder, self.root, self.fake)
            restored = self.start_http()
            _, answer = restored.submit(self.identifier, PROMPT)
            self.assertEqual(answer['content'], ANSWER)
            self.assertEqual(calls, [PROMPT] * 3)
        self.assertFalse(task_queue.tasks(self.root))

    def test_substantive_resume_suffix_survives_existing_hold_and_sticky_history(self):
        self.chat.submit(self.identifier, 'Hold WebJam', str(uuid.uuid4()))
        self.chat.submit(self.identifier, 'go', str(uuid.uuid4()))
        self.assertEqual(self.chat.history(self.identifier)['messages'][-1]['content'], 'Ready when you are.')
        for prompt in (PROMPT, 'Go ahead and explain the next steps.',
                       'Resume with an explanation of the tradeoffs.'):
            self.chat.submit(self.identifier, prompt, str(uuid.uuid4()))
            self.wait()
            answer = self.chat.history(self.identifier)['messages'][-1]
            self.assertEqual(answer['content'], 'A saved reply.')
            self.assertEqual(self.fake.calls[-1]['messages'][-2]['content'], prompt)
        self.assertFalse(task_queue.tasks(self.root))

    def test_model_sticky_greeting_is_discarded_and_next_provider_answers(self):
        provider = Providers(self.root, lambda value: value)
        conversation = dict(id=self.identifier, messages=[dict(role='user', content=PROMPT)])
        with patch.object(provider, 'route_order', return_value=('gemini', 'minimax')), \
                patch.object(provider, 'prompt', return_value=PROMPT), \
                patch.object(provider, '_call_timed', side_effect=[('Ready when you are.', None), (ANSWER, None)]) as call:
            answer = provider.reply(conversation, threading.Event(), lambda *args: None)
        self.assertEqual(answer['provider'], 'minimax')
        self.assertEqual(answer['content'], ANSWER)
        self.assertEqual(answer['attempts'][0]['kind'], 'invalid_output')
        self.assertEqual(call.call_count, 2)
