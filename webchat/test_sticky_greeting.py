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
