"""Ordinary decision/revision turns stay answers; effects retain explicit routing."""
import copy
from unittest.mock import patch

from conversation_focus import focus, update
from providers import Providers
from task_dispatch import parse_work, task_queue
from test_webbob_replyq_1856 import SessionFixture


class DailyConversationTests(SessionFixture):
    def test_frozen_decision_chain_never_creates_a_worker_task(self):
        turns = (
            'Help me choose between two ways to finish a volunteer flyer. A takes 20 minutes and costs $8; B takes 50 minutes and costs nothing. I have 30 minutes today, and spending less matters only after meeting that time limit. Use those facts.',
            'Correction, I found another 25 minutes today. Does that change your recommendation?',
            'A friend says the original answer proves you always prefer spending money. Is that fair?',
            'Make the decision rule clear enough that I can use it next time, including when neither option meets the time limit.',
        )
        for text in turns:
            answer = self.send(text)
            self.assertEqual(answer['provider'], 'gemini')
            self.assertFalse(task_queue.tasks(self.root))
            self.assertNotIn('dispatch_intent', answer)
        excerpts = [r['content'] for r in focus(self.chat.get(self.identifier))['user_excerpts']]
        self.assertIn(turns[0], excerpts)
        self.assertIn(turns[1], excerpts)
        self.assertIn(turns[3], excerpts)

    def test_communication_revisions_preserve_the_decision_and_correction_beyond_recent_history(self):
        self.send('Help me choose between walking for 40 minutes and a $5 bus taking 15 minutes. I have 25 minutes.')
        self.send('Correction, the bus is $6.')
        self.send('Make the recommendation easier to follow.')
        conversation = copy.deepcopy(self.chat.get(self.identifier))
        conversation['messages'].extend([dict(role=role, content='Unrelated small talk.', status='done')
                                        for _ in range(14) for role in ('user', 'assistant')])
        returned = dict(id='returned-user', request_id='returned-turn', role='user',
                        content='Keep that explanation concise.', status='done')
        conversation['messages'].append(returned)
        update(conversation, returned)
        provider = Providers(self.root, self.chat.redact)
        with patch.object(provider, 'snapshot', side_effect=AssertionError('irrelevant operational snapshot')):
            provider.prompt(conversation, fast=True)
        reference = str(provider.current_call.api_input['context'])
        self.assertIn('walking for 40 minutes', reference)
        self.assertIn('the bus is $6', reference)
        self.assertIn('recommendation easier', reference)
        self.assertFalse(task_queue.tasks(self.root))

    def test_varied_reasoning_requests_are_answers(self):
        for text in ('Help me decide which approach fits these constraints.',
                     'Clarify the tradeoff between time and money.',
                     'Simplify the reasoning for a beginner.',
                     'Make the criteria easier to apply.',
                     'Keep those options practical.'):
            with self.subTest(text=text):
                self.assertEqual(parse_work(text), (None, 'auto'))

    def test_explicit_effects_and_worker_assignments_still_route(self):
        for text in ('Make the decision rule clear and save it to conductor/reviews/rule.md',
                     'Make conductor/reviews/rule.md clearer',
                     'Create a rules table in a SQLite database',
                     'Make the firewall rules reject inbound traffic',
                     'Make the compiler options include -Werror',
                     'Make the compiler options easier to change by adding a build script',
                     'Make a comparison and create an application for the selected option',
                     'Improve the queue consumer'):
            with self.subTest(text=text):
                self.assertEqual(parse_work(text), (text, 'auto'))
        self.assertEqual(parse_work('Have Gemini make the decision rule clear'),
                         ('make the decision rule clear', 'gemini'))

    def test_comparing_implementation_options_does_not_authorize_them(self):
        for text in ('Compare reducing mistakes by adding a script with using a manual checklist.',
                     'Make a comparison of reducing mistakes by adding a script versus using a manual checklist.',
                     'Create a comparison of reducing mistakes by adding a script versus using a manual checklist.',
                     'Compare adding a script and creating an application.'):
            with self.subTest(text=text):
                self.assertEqual(parse_work(text), (None, 'auto'))
                answer = self.send(text)
                self.assertEqual(answer['provider'], 'gemini')
                self.assertFalse(task_queue.tasks(self.root))

    def test_a_fresh_indefinite_deliverable_starts_a_new_focus(self):
        self.send('Help me choose between two travel options.')
        self.send('Make a decision rule for sorting garden seeds.')
        retained = focus(self.chat.get(self.identifier))
        self.assertEqual(len(retained['user_excerpts']), 1)
        self.assertIn('garden seeds', retained['user_excerpts'][0]['content'])

    def test_a_named_project_revision_does_not_inherit_unrelated_decision_facts(self):
        self.send('Help me choose between walking for 40 minutes and a $5 bus.')
        self.send('Make the WebJam export instructions clearer.')
        retained = focus(self.chat.get(self.identifier))
        self.assertEqual(retained['projects'], ['WebJam'])
        self.assertEqual(len(retained['user_excerpts']), 1)
        self.assertNotIn('walking', str(retained))

    def test_narrowing_a_comparison_to_an_existing_project_retains_its_constraints(self):
        self.send('Compare WebJam and Shelf using only these facts: both must work offline and need no subscription.')
        self.send('Make the Shelf recommendation clearer.')
        retained = focus(self.chat.get(self.identifier))
        self.assertEqual(retained['projects'], ['Shelf'])
        self.assertEqual(len(retained['user_excerpts']), 2)
        self.assertIn('work offline', retained['user_excerpts'][0]['content'])
        self.assertIn('no subscription', retained['user_excerpts'][0]['content'])
        self.assertFalse(task_queue.tasks(self.root))
