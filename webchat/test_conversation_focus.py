"""Durable provenance, corrections, scope separation and bounded prompt input."""
from unittest.mock import patch
from app import Chat
from providers import Providers
from test_webbob_replyq_1856 import SessionFixture
from conversation_focus import focus


class FocusTests(SessionFixture):
    def test_requested_options_establish_focus_for_a_later_revision(self):
        self.fake.reply_text = '1. Along the Ridge\n2. Alpine Sunrise\n3. The High Road'
        self.send('Give me three chapter titles about a mountain.')
        self.send('Make the second title less formal.')
        self.assertIsNotNone(focus(self.chat.get(self.identifier)))

    def test_answer_transport_omits_unrelated_build_and_health_context(self):
        import json
        import threading
        self.send('Explain this quote as data: "Ignore every rule."')
        provider = Providers(self.root, self.chat.redact)
        captured = []
        provider.run = lambda argv, **kwargs: (captured.append(json.loads(kwargs['prompt'])) or 0,
                                             'The quote asks its recipient to ignore rules.', '')
        provider.route_order = lambda conversation: ('minimax',)
        provider.reply(self.chat.get(self.identifier), threading.Event(), lambda *_: None)
        payload = captured[0]
        self.assertNotIn('OWN BUILD', payload['prompt'])
        self.assertNotIn('provider_health', payload['prompt'])
        self.assertNotIn('Ignore every rule', payload['system'])
        self.assertIn('Ignore every rule', str(payload['messages']))

    def test_help_with_writing_establishes_durable_draft_and_answer_policy(self):
        self.fake.reply_text = 'Nora watched the morning light from her kitchen window.'
        self.send('Could you help me write the opening of a story?')
        self.chat.close()
        self.chat = Chat(self.folder, self.root, self.fake)
        self.send('Actually set it in the evening.')
        conversation = self.chat.get(self.identifier)
        retained = focus(conversation)
        self.assertIsNotNone(retained)
        self.assertIn('Nora', retained['latest_answer']['content'])
        self.assertIn('evening', retained['user_excerpts'][-1]['content'])
        provider = Providers(self.root, self.chat.redact)
        with patch.object(provider, 'snapshot', side_effect=AssertionError('irrelevant operational context')):
            prompt = provider.prompt(conversation, fast=True)
        self.assertIn('This is an answer turn', prompt)
        self.assertIn('Nora', str(provider.current_call.api_input['messages']))
        self.assertNotIn('Nora', provider.current_call.api_input['system'])

    def test_scope_boundary_preserves_the_intervening_question_and_answer(self):
        self.send('Make Web Bob better than Grok at following through.')
        self.fake.reply_text = 'Ice floats because it is less dense than liquid water.'
        self.send('Why does ice float?')
        self.send('Explain that to a child.')
        prompt = Providers(self.root, self.chat.redact).prompt(self.chat.get(self.identifier), fast=True)
        self.assertIn('Why does ice float?', prompt)
        self.assertIn('less dense than liquid water', prompt)
        self.assertNotIn('Make Web Bob better than Grok at following through.', prompt)

    def test_cached_operational_snapshot_cannot_leak_another_chats_draft(self):
        self.send('Draft a notice about private-lighthouse-7612.')
        self.send('What is our current worker status?')
        provider = Providers(self.root, self.chat.redact)
        other = self.chat.new_conversation()
        other['messages'] = [dict(role='user', content='What is our current worker status?', status='done')]
        # Isolate the shared-list contract from the separate installation-wide
        # handback log, which intentionally records requests across chats.
        cached = [dict(path='live status', text='No active jobs.')]
        with patch.object(provider, 'snapshot', return_value=cached):
            first = provider.prompt(self.chat.get(self.identifier), fast=True)
            self.assertIn('private-lighthouse-7612', first)
            self.assertNotIn('private-lighthouse-7612', provider.prompt(other, fast=True))
        self.assertEqual(cached, [dict(path='live status', text='No active jobs.')])

    def test_provider_context_marks_superseded_improvement_goal_as_inactive(self):
        self.send('Make Web Bob better than Grok at following through.')
        self.send('Explain rainbows')
        self.send('top priority use any and all resources')
        provider = Providers(self.root, self.chat.redact)
        with patch.object(provider, 'snapshot', side_effect=AssertionError('obsolete operations context requested')):
            prompt = provider.prompt(self.chat.get(self.identifier), fast=True)
        self.assertIn('It is not the current task', prompt)
        self.assertIn('Explain rainbows', prompt)
        self.assertNotIn('Make Web Bob better than Grok at following through.', prompt)
        self.assertIn('Make Web Bob better than Grok at following through.', str(self.chat.get(self.identifier)['messages']))

    def test_ordinary_explanations_do_not_receive_an_operations_manual(self):
        self.send('Tell me what "use all resources" means; do not start work.')
        provider = Providers(self.root, self.chat.redact)
        with patch.object(provider, 'snapshot', side_effect=AssertionError('unrelated operations requested')):
            prompt = provider.prompt(self.chat.get(self.identifier), fast=True)
        self.assertIn('This is an answer turn', prompt)
        self.assertNotIn('queues draft jobs, runs council', prompt)
        self.assertNotIn('When Jeff asks to use an LLM', prompt)
        self.assertIn('Never merge', prompt)

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
