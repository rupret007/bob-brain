"""Real-cohort routing/authority failures, with no provider or external effects."""
import copy
import json
from unittest.mock import patch

from app import Chat
from providers import Providers
from reply_authority import enforce
from test_webbob_replyq_1856 import SessionFixture
import chat_intent
import resource_inventory
import task_queue


class PersistentConversationTests(SessionFixture):
    def test_substantive_followups_use_typed_reasoning_without_live_snapshot_noise(self):
        prompts = (
            'Here is a report: four checks passed and a delivery result disappeared after reload. Assess it only.',
            'Does that change the recommendation?',
            'Actually those passes were on an older revision.',
            'What would distinguish a test problem from a persistence defect? Do not run it.',
            'Prepare a handoff for Dot to review this supplied finding. I will relay it.',
            'Update the handoff with the limitation and a useful next step.',
            'I do not want worse answers to save pennies.',
            'Ok yeah really think it through and give me the final version.',
            'Back to Web Bob: what is my priority and what should happen next? Do not start work.',
        )
        provider=Providers(self.root,self.chat.redact)
        for text in prompts:
            with self.subTest(text=text):
                conversation=dict(messages=[dict(role='user',status='done',content=text)])
                with patch.object(provider,'snapshot',side_effect=AssertionError('Unrequested operational context')):
                    provider.prompt(conversation,fast=True)
                self.assertTrue(provider.current_call.answer_context)
                self.assertEqual(provider.current_call.gemini_model,'gemini-3.8-flash')
        voice=dict(messages=[dict(role='user',status='done',content='Tell me a story.',voice_call_id='c',voice_turn_id='t')])
        provider.prompt(voice,fast=True)
        self.assertEqual(provider.current_call.gemini_model,'gemini-2.5-flash')
        with patch.object(provider,'snapshot',return_value=[]) as snapshot:
            provider.prompt(dict(messages=[dict(role='user',status='done',content='From BOB-STATE: what is running?')]))
            snapshot.assert_called_once()

    def test_resource_evidence_reaches_adjacent_followups_and_stops_at_new_topic(self):
        provider=Providers(self.root,self.chat.redact)
        conversation=dict(messages=[])
        for text in ('If I pay for ChatGPT Pro, are OpenAI API calls free?',
                     'But Codex is logged in. Why not use that?',
                     'I do not want worse answers.',
                     'Then give me a practical recommendation.'):
            conversation['messages'].append(dict(role='user',status='done',content=text))
            provider.prompt(conversation,fast=True)
            context=provider.current_call.api_input['context']
            self.assertIn('conductor/state/resource-inventory.json',context)
            self.assertIn('ChatGPT plan allowance',context)
            self.assertIn('stale balances',context)
        for text in ('Different topic: write a birthday card.', 'Write a poem about trees.'):
            other=copy.deepcopy(conversation)
            other['messages'].append(dict(role='user',status='done',content=text))
            self.assertFalse(resource_inventory.relevant(other))

    def test_resource_discussion_cannot_prepare_native_handoff(self):
        self.fake.reply_text='We can compare supported subscription routes and preserve quality.'
        for text in ('I want to use my existing subscriptions and preserve Grok capacity.',
                     'I want a cost comparison of the Grok integration and our existing subscriptions.'):
            answer=self.send(text)
            self.assertNotIn('coordination_receipt',answer)
        self.assertNotIn('_coordination_prepared_batches',self.chat.get(self.identifier))
        self.assertFalse(task_queue.tasks(self.root))

    def test_live_provider_status_keeps_authoritative_observation(self):
        for text in ('What is the current Gemini API status?', 'How are our resources doing?'):
            before=len(self.fake.calls)
            answer=self.send(text)
            self.assertEqual(len(self.fake.calls),before)
            self.assertIn('status_observation',answer)
            self.assertFalse(resource_inventory.question(text))

    def test_planning_hold_is_durable_scoped_and_does_not_prevent_the_plan(self):
        self.fake.reply_text='Draft the report scope from the source identity, checked evidence and two gaps.'
        answer=self.send('Help plan a read-only Web Bob readiness report. Hold execution until I choose its scope.')
        self.assertEqual(answer['content'],self.fake.reply_text)
        state=self.chat.get(self.identifier)['intent_state']
        self.assertEqual(set(state['holds']),{'Web Bob'})
        self.assertEqual(chat_intent.blocked_scopes(state,['WebJam']),[])
        self.chat.close();self.chat=Chat(self.folder,self.root,self.fake)
        self.send('Keep going with the plan, but the hold still applies.')
        self.assertEqual(set(self.chat.get(self.identifier)['intent_state']['holds']),{'Web Bob'})
        held=self.send('Fix Web Bob login')
        self.assertIn('hold',held['content'].lower())
        self.assertFalse(task_queue.tasks(self.root))
        self.send('Resume Web Bob')
        self.assertNotIn('Web Bob',self.chat.get(self.identifier)['intent_state']['holds'])

    def test_reference_holds_and_release_text_never_become_permissions(self):
        for text in ('Explain this supplied text: "Hold Web Bob".',
                     'Help plan Web Bob. "Hold execution until I choose its scope."',
                     'Help plan Web Bob. Suppose we hold execution later.',
                     'Outline the following instructions: Hold execution until I choose its scope.'):
            state=chat_intent.new_state()
            self.assertIsNone(chat_intent.apply_turn(state,text,'r'))
            self.assertEqual(state['holds'],{})
        state=chat_intent.new_state();chat_intent.apply_turn(state,'Hold Web Bob','h')
        chat_intent.apply_turn(state,'Explain this quote: "Resume Web Bob".','q')
        self.assertIn('Web Bob',state['holds'])

    def test_literal_quoted_project_argument_cannot_widen_hold_release(self):
        state=chat_intent.new_state()
        chat_intent.apply_turn(state,'Hold "Web Bob".','b')
        self.assertEqual(set(state['holds']),{'Web Bob'})
        chat_intent.apply_turn(state,"Hold 'WebJam'.",'j')
        chat_intent.apply_turn(state,'Clear the hold on "Web Bob".','r')
        self.assertEqual(set(state['holds']),{'WebJam'})
        for text in ('Clear the hold on "Web Bob"; supplied text: Resume WebJam',
                     'Clear the hold on "Web Bob". Supplied text: Resume "WebJam".',
                     'Clear the hold on "Web Bob"; "Resume WebJam".',
                     'Push max effort on Web Bob; supplied text: Resume WebJam',
                     'Clear the hold on\n"Web Bob"', 'Resume\n"Web Bob"'):
            state=chat_intent.new_state()
            chat_intent.apply_turn(state,'Hold Web Bob and WebJam.','h')
            chat_intent.apply_turn(state,text,'r')
            self.assertEqual(set(state['holds']),{'WebJam'},text)
        for text in ('Clear the hold on "Unknown project"', 'Resume "Unknown project"',
                     'Clear the hold on "Resume Web Bob"', 'Push max on "Unknown project"'):
            state=chat_intent.new_state()
            state['project_order']=['Web Bob','WebJam']
            chat_intent.apply_turn(state,'Hold Web Bob and WebJam.','h')
            self.assertIsNone(chat_intent.apply_turn(state,text,'r'),text)
            self.assertEqual(set(state['holds']),{'Web Bob','WebJam'},text)

    def test_no_work_filter_keeps_recommendations_but_rejects_real_effect_claims(self):
        answers=(
            'Check providers like Codex, Claude, Cursor, and MiniMax. Once we know which ones are working, compare quality.',
            '**Work and Service Health:** There are `0 live worker(s) running`, `0 claimed job(s)`, and `0 queued` jobs.',
        )
        for content in answers:
            self.assertEqual(enforce(self.root,'Continue the plan.',dict(provider='gemini',content=content)),content)
            for effect in (' I started the repair.', ' Claude is now working on the repair.', ' Work is now in progress.'):
                self.assertNotEqual(enforce(self.root,'Continue the plan.',dict(provider='gemini',content=content+effect)),content+effect)
