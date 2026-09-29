"""Capability questions must be fast, honest, and free of side effects."""
import uuid

from capabilities import QUESTIONS, reply, topic
from test_webchat import Fixture
from texting import Andrea, BlueBubbles, Texting
from texting_fixture import MockMessaging
from task_dispatch import task_queue


class CapabilityTests(Fixture):
    def ask(self, text, request=None):
        return self.chat.submit(self.identifier, text, request or str(uuid.uuid4()), actor='a' * 64)

    def test_all_supported_questions_are_server_owned_and_idempotent(self):
        for phrases in QUESTIONS.values():
            for question in phrases:
                with self.subTest(question=question):
                    request = str(uuid.uuid4())
                    result = self.ask(question + '?', request)
                    answer = result['messages'][-1]
                    self.assertEqual(answer['provider'], 'capabilities')
                    self.assertEqual(answer['status'], 'done')
                    self.assertFalse(answer['attempts'])
                    self.assertEqual(self.ask(question + '?', request), result)
        self.assertFalse(self.fake.calls)
        self.assertFalse(task_queue.tasks(self.root))
        self.assertFalse(self.chat.get(self.identifier).get('_texting', {}).get('audit'))

    def test_requests_and_quoted_questions_are_not_intercepted(self):
        for text in ('Can you send texts to Alex: On my way', 'Can you remind me to stretch in 10 minutes?',
                     'Can you read files and summarize this PDF?', 'Explain the phrase "can we talk?"',
                     'Remember that my question is can you remember things',
                     'Can you start workers? Fix WebJam.', 'What can you do about this traceback?'):
            self.assertIsNone(topic(text), text)
        result = self.ask('What can you do about this traceback?')
        self.wait()
        self.assertTrue(self.fake.calls)

    def test_git_explanations_answer_the_question_without_execution_or_refusal(self):
        for prompt, expected in (
            ('What does force-push mean?', 'remote branch'),
            ('Explain force push.', 'remote branch'),
            ('Explain gh pr ready.', 'ready for review'),
            ('What does undraft mean?', 'ready for review'),
            ('What does merging a PR mean?', 'target branch'),
        ):
            with self.subTest(prompt=prompt):
                result = self.ask(prompt)['messages'][-1]
                self.assertEqual(result['provider'], 'capabilities')
                self.assertIn(expected, result['content'])
                self.assertNotIn('action_card', result)
                self.assertFalse(result['attempts'])
        self.assertFalse(self.fake.calls)
        self.assertFalse(task_queue.tasks(self.root))

    def test_explanation_words_do_not_hide_execution_requests(self):
        from app import hard_rule_refusal
        for prompt in ('Explain force-push, then force-push the branch.',
                       'What does undraft mean? Undraft it now.',
                       'Explain gh pr ready and run it.', 'Please merge #158',
                       'Can you force-push?', 'Run gh pr ready'):
            with self.subTest(prompt=prompt):
                self.assertIsNone(topic(prompt))
                self.assertIsNotNone(hard_rule_refusal(prompt))

    def test_capability_answer_revokes_pending_actions_and_memory(self):
        self.ask('remember that this must not be saved')
        conv = self.chat.get(self.identifier)
        self.assertTrue(conv.get('pending_memory'))
        conv.update(pending_job='Fix WebJam', pending_job_id='old',
                    pending_council='Review WebJam', pending_council_id='old')
        self.ask('What can you do?')
        conv = self.chat.get(self.identifier)
        for key in ('pending_memory', 'pending_memory_id', 'pending_job', 'pending_job_id',
                    'pending_council', 'pending_council_id'):
            self.assertNotIn(key, conv)
        result = self.ask('yes, save memory')['messages'][-1]
        self.assertIn('No memory is waiting', result['content'])

    def test_capability_question_cancels_exact_text_approval(self):
        mock = MockMessaging(self.root)
        self.addCleanup(mock.close)
        mock.enable_web_bob_send = True
        self.chat.texting = Texting(BlueBubbles(mock.config_db), Andrea(mock.base, mock.token))
        self.chat.texting.instinct.bind_state(self.folder)
        card = self.ask('draft reply to Alex Morgan: Do not send this.')['messages'][-1]['text_draft']
        self.ask('Can you send texts?')
        rejected = self.ask(card['confirm_message'])['messages'][-1]
        self.assertIn('already used, cancelled, or replaced', rejected['content'])
        self.assertFalse(mock.sends)
        self.assertFalse(mock.unexpected_writes)

    def test_capabilities_explain_boundaries_without_exposing_saved_memory(self):
        memory = self.folder / 'memory/profile.md'
        memory.parent.mkdir()
        memory.write_text('Private fixture: copper-puffin-739')
        text = self.ask('Is my memory private?')['messages'][-1]['content']
        self.assertIn('future model context', text)
        self.assertIn('confirmation', text)
        self.assertNotIn('copper-puffin', text)
        self.assertIn('read-only', reply('Can you text Instinct?', self.root))
        self.assertIn('not phone push', reply('Can you set reminders?', self.root))
        self.assertIn('sampled frames', reply('Can you watch videos?', self.root))
        self.assertIn('delivery is unconfirmed', reply('Can you send texts?', self.root))
        self.assertIn('without resending', reply('Can you send texts?', self.root))

    def test_worker_capability_uses_current_solo_and_maintenance_markers(self):
        self.assertIn('can be queued', reply('Can you start workers?', self.root))
        for marker in ('SOLO-WORKER', 'MAINTENANCE'):
            path = self.root / 'conductor' / marker
            path.touch()
            self.assertIn('paused', reply('Can you start workers?', self.root))
            self.assertIn('paused', reply('What can you do?', self.root))
            path.unlink()
