"""Replay the exposed priorities topic switch through real offline delivery."""
import json
from pathlib import Path

from app import Chat
from providers import Providers
from test_webbob_replyq_1856 import SessionFixture


CASES = json.loads(Path(__file__).with_name('fixtures').joinpath(
    'priorities_delivery_1006d.json').read_text())


class PrioritiesDeliveryTests(SessionFixture):
    def replay(self, case):
        # Recreate the exact saved context and correction before the topic switch.
        for turn in case['prior_turns']:
            answer = self.send(turn['prompt'])
            self.assertEqual(answer['status'], 'done')
            self.assertEqual(answer['content'], turn['content'])
        self.assertFalse(self.fake.calls)

        transports = []

        def runner(argv, **kwargs):
            self.assertEqual(argv[-1], 'gemini')
            transports.append(json.loads(kwargs['prompt']))
            return 0, case['raw_answer'], ''

        # Replace only the subprocess transport: prompt selection, output parsing,
        # safety guards, persistence, and terminal status use production code.
        provider = Providers(self.root, self.chat.redact, runner=runner)
        provider.route_order = lambda _: ('gemini',)
        self.chat.providers = provider
        prompt = case['transport_messages'][-1]['content']
        answer = self.send(prompt)
        self.assertEqual(len(transports), 1)
        self.assertEqual(transports[0]['messages'], case['transport_messages'])
        self.assertEqual(answer['status'], 'done')
        self.assertTrue(answer['content'].strip())
        self.assertEqual(answer['content'], case['raw_answer'].strip())
        self.assertEqual(answer['attempts'], [])
        self.assertEqual(answer['provider'], 'gemini')

        self.chat.close()
        self.chat = Chat(self.folder, self.root, self.fake)
        saved = self.chat.history(self.identifier)['messages'][-1]
        self.assertEqual(saved, answer)
        replay = self.chat.submit(self.identifier, prompt, answer['request_id'])
        self.assertEqual(replay['messages'][-1], answer)
        self.assertFalse(self.fake.calls)

    def test_exposed_sample_delivers_complete_answer(self):
        self.replay(CASES[0])

    def test_recovery_four_delivers_complete_answer(self):
        self.replay(CASES[1])
