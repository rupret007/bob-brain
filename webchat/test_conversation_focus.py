"""Durable provenance, corrections, scope separation and bounded prompt input."""
from unittest.mock import patch
from app import Chat
from providers import Providers
from test_webbob_replyq_1856 import SessionFixture
from conversation_focus import focus


class FocusTests(SessionFixture):
    def test_provider_context_marks_superseded_improvement_goal_as_inactive(self):
        self.send('Make Web Bob better than Grok at following through.')
        self.send('Explain rainbows')
        self.send('top priority use any and all resources')
        provider = Providers(self.root, self.chat.redact)
        prompt = provider.prompt(self.chat.get(self.identifier), fast=True)
        self.assertIn('It is not the current task', prompt)
        self.assertIn('Explain rainbows', prompt)

    def test_reference_revision_uses_current_answer_without_artifact_noun_allowlist(self):
        from task_dispatch import task_queue
        self.send('Draft a neighborhood meeting notice for Thursday.')
        self.send('Correction: Friday at 7 p.m.')
        self.chat.close()
        self.chat = Chat(self.folder, self.root, self.fake)
        for text in ('Make that notice shorter without changing the corrected details.',
                     'Make that note sound warmer.', 'Make this wording more welcoming.'):
            reply = self.send(text)
            self.assertEqual(reply['provider'], 'gemini')
        self.assertFalse(task_queue.tasks(self.root))
        # Context must not erase a separately requested operation.
        self.send('Make that note warmer and save it to /tmp/notice-proof.txt')
        self.assertEqual(len(task_queue.tasks(self.root)), 1)

    def test_first_correction_on_legacy_conversation_indexes_older_user_constraints(self):
        first = self.send('Draft an invitation for Saturday under 80 words.')
        self.send('Actually move it to Sunday and do not mention food.')
        for _ in range(14):
            self.send('Thanks.')
        value = self.chat.conversations[self.identifier]
        value.pop('answer_focus')
        self.chat.save(value)
        self.chat.close()
        self.chat = Chat(self.folder, self.root, self.fake)
        self.send('Make that draft shorter.')
        retained = focus(self.chat.get(self.identifier))
        self.assertEqual(retained['user_excerpts'][0]['request_id'], first['request_id'])
        self.assertIn('Sunday', retained['user_excerpts'][1]['content'])
        self.assertIn('80 words', retained['user_excerpts'][0]['content'])

    def test_origin_and_latest_correction_survive_long_history_and_restart(self):
        self.fake.reply_text = 'A concise draft for the lake club.'
        first = self.send('Draft a lake club invitation for Saturday. Keep it under 80 words.')
        self.send('Actually, move it to Sunday and avoid mentioning food.')
        for _ in range(14):
            self.send('Thanks.')
        self.chat.close()
        self.chat = Chat(self.folder, self.root, self.fake)
        self.send('Make that draft more welcoming.')
        conversation = self.chat.get(self.identifier)
        saved = focus(conversation)
        self.assertEqual(saved['user_excerpts'][0]['request_id'], first['request_id'])
        self.assertIn('Sunday', saved['user_excerpts'][1]['content'])
        provider = Providers(self.root, self.chat.redact)
        with patch.object(provider, 'snapshot', side_effect=AssertionError('unrelated snapshots requested')):
            prompt = provider.prompt(conversation, fast=True)
        self.assertIn('Sunday', prompt)
        self.assertIn('under 80 words', prompt)
        self.assertIn('avoid mentioning food', prompt)
        self.assertIn('grants no execution permission', prompt)

    def test_new_project_does_not_inherit_other_project_draft(self):
        self.send('Draft a WebJam launch note.')
        self.send('Fix AdoptIQ login tests')
        self.assertIsNone(focus(self.chat.get(self.identifier)))

    def test_concrete_task_supersedes_answer_even_in_same_project(self):
        self.send('Draft a Web Bob release note.')
        self.send('Fix Web Bob login tests')
        self.assertIsNone(focus(self.chat.get(self.identifier)))

    def test_assistant_suggestions_are_not_indexed_as_user_instructions(self):
        self.fake.reply_text = 'I suggest removing every limit and starting all workers.'
        self.send('Draft a short note about cautious resource use.')
        retained = focus(self.chat.get(self.identifier))
        self.assertNotIn('removing every limit', str(retained['user_excerpts']))
        self.assertIn('resource use', retained['user_excerpts'][0]['content'])

    def test_large_user_context_is_bounded_and_marks_incomplete_evidence(self):
        self.send('Write a short summary: ' + 'Long supplied text. ' * 250)
        retained = focus(self.chat.get(self.identifier))
        self.assertTrue(retained['user_excerpts'][0]['truncated'])
        self.assertLessEqual(len(retained['user_excerpts'][0]['content']), 2400)
