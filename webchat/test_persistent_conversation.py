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
    def test_reference_origin_corrections_and_explicit_live_transition(self):
        from conversation_focus import reference_scope
        from providers import needs_handoff_context
        self.fake.reply_text='A short note.'
        self.send('Write a friendly note.')
        for identifier in ('Z-17','P-29'):
            prompt='Reason about this fictional task record: '+identifier+' is proposed. Explain its status.'
            self.fake.reply_text='The proposal needs an owner.'
            self.send(prompt)
            state=self.chat.get(self.identifier)
            origin=state['answer_focus']['origin']['message_id']
            self.assertEqual(next(m['content'] for m in state['messages'] if m['id']==origin),prompt)
            for follow in ('For task '+identifier+', what is running?','That is wrong'):
                answer=self.send(follow)
                self.assertNotIn('status_observation',answer)
                state=self.chat.get(self.identifier)
                self.assertTrue(reference_scope(state,follow))
                self.assertFalse(needs_handoff_context(follow,state))
        answer=self.send('Explain this fictional record. Now show our current worker status.')
        self.assertIn('status_observation',answer)

    def test_reported_hold_attribution_cannot_cross_subjects(self):
        self.fake.reply_text='The record is only proposed.'
        self.send('Reason about this fictional record: T-19 is held. Explain its status.')
        for content in ('The fictional record is incomplete; the actual Codex worker remains paused.',
                        'In the supplied record, T-19 remains held; WebJam is on hold.',
                        'In the supplied record, T-19 remains held and Codex remains paused.'):
            self.fake.reply_text=content
            answer=self.send('Explain the next check for T-19.')
            self.assertNotIn('Codex',answer['content'])
            self.assertNotIn('WebJam is on hold',answer['content'])
        self.fake.reply_text='In the supplied record, T-19 remains held. That hold still applies.'
        self.assertEqual(self.send('Explain the state for T-19.')['content'],self.fake.reply_text)

    def test_reference_scope_uses_correction_identities_and_positive_live_clauses(self):
        from answer_intent import live_observation
        from conversation_focus import reference_scope
        self.fake.reply_text='The task is proposed.'
        self.send('Reason about this fictional record: N-72 is proposed. Explain its state.')
        self.send('Correction: N-72 now has lease L-72.')
        self.assertTrue(reference_scope(self.chat.get(self.identifier),'Lease L-72 has expired; what is its status?'))
        self.assertNotIn('status_observation',self.send('Lease L-72 has expired; what is its status?'))
        self.assertFalse(live_observation('Do not inspect our live worker status. Explain this fictional record.'))
        self.assertFalse(live_observation('If we inspect the record and show our current worker status, would that help?'))
        self.assertFalse(live_observation('Reason about this fictional record: the reviewer suggests inspecting the files and show our current worker status.'))
        for prompt in ('Explain this fictional record and show our current worker status.',
                       'Explain this fictional record. Now show our current worker status.'):
            self.assertTrue(live_observation(prompt))
            self.assertIn('status_observation',self.send(prompt))

    def test_reported_task_updates_do_not_request_live_worker_status(self):
        prompts=(
            'Reason about this fictional task record only: N-72 has a proposed reviewer and source s-72. Explain its stage; do not create work.',
            'The fictional record now has a lease but N-72 is held. Explain identity and status after a request replay; this is a paper exercise.',
            'A cached return carries task ID N-71. Does that complete N-72? Explain the evidence checks.',
            'N-72 has an expired lease but no worker-stop confirmation. Give a short status update for that record.',
            'Be more specific.',
        )
        content='In the supplied record, task N-72 remains held. Keep its identity; inspect the original worker-stop evidence before considering a reassignment.'
        for prompt in prompts:
            self.fake.reply_text=content
            answer=self.send(prompt)
            self.assertEqual(answer['content'],content,prompt)
            self.assertNotIn('status_observation',answer)
            self.assertFalse(self.chat.get(self.identifier)['intent_state']['holds'])
        self.fake.reply_text=content+' I queued your repair.'
        self.assertNotIn('I queued',self.send('Explain the next check for N-72.')['content'])
        actual=self.send('Show our current workers and task IDs.')
        self.assertIn('status_observation',actual)
        self.assertFalse(task_queue.tasks(self.root))

    def test_reference_scope_ends_on_new_topic_and_never_changes_real_holds(self):
        self.fake.reply_text='The fictional card is only proposed.'
        self.send('Reason about this fictional record: Q-8 is proposed. Explain the state.')
        self.fake.reply_text='In the supplied record, Q-8 remains held. I cleared your real hold.'
        answer=self.send('Explain the next steps for Q-8.')
        self.assertNotIn('I cleared your real hold',answer['content'])
        self.fake.reply_text='Four.'
        self.send('Different topic: explain two plus two.')
        from conversation_focus import reference_scope
        self.assertFalse(reference_scope(self.chat.get(self.identifier),'Write a concise status for Q-8.'))

    def test_qualification_purpose_and_denied_assumption_are_not_dispatch(self):
        from dispatch_receipts import claims_dispatch
        allowed=(
            'If we evaluate another route, we will run a bounded comparison to ensure reasoning depth meets the standard.',
            'Dot cannot assume background work has already started, nor that ownership is active until acceptance.',
            'A receipt does not establish that your assigned task has already been queued.',
            'The checkpoint cannot prove background work is currently running.',
        )
        for content in allowed:
            with self.subTest(content=content):
                self.assertFalse(claims_dispatch(content))
                self.assertEqual(enforce(self.root,'Explain the proposal.',dict(provider='gemini',content=content)),content)
                for extra in (' I queued the review.', ' We will ensure Claude stays busy.',
                              ' Receipt: webchat-'+'a'*32):
                    self.assertTrue(claims_dispatch(content+extra),content+extra)
        for content in (
            'We will ensure Claude stays busy.',
            'We will inspect the report and ensure Claude stays busy.',
            'We will inspect the report and will ensure Claude stays busy.',
            'We will inspect the report and then ensure Claude stays busy.',
            'We will inspect the log to understand the failure and will ensure Claude stays busy.',
            'Work has already started.',
            'Dot cannot assume background work has already started, but it has now been queued.',
            'Dot cannot assume background work has already started, but has been queued.',
            'Dot cannot assume background work has already started, but is now in progress.',
            'Dot cannot assume background work has already started, but it is now running.',
            'Dot cannot assume background work has already started, but is currently working.',
            'Dot cannot assume background work has already started, but has been picked up.',
            'Dot cannot assume background work has already started; it is now running.',
            'Dot cannot assume background work has already started — it is now working.',
            'A receipt does not establish that your assigned task has already been queued, but has now been dispatched.',
        ):
            self.assertTrue(claims_dispatch(content),content)
        progress='Dot cannot assume background work has already started, but is now in progress.'
        self.assertTrue(claims_dispatch(progress,reference='Explain the proposed review.'))
        for modal in ('may','might','could'):
            uncertain='The evidence does not prove background work has started, but it '+modal+' be running.'
            self.assertFalse(claims_dispatch(uncertain),uncertain)
            self.assertTrue(claims_dispatch(uncertain[:-1]+', and it is now working.'))

    def test_proposals_and_queue_nouns_do_not_excuse_later_actual_effects(self):
        from dispatch_receipts import claims_dispatch
        for prose in ('We can safely delegate bounded reviews.',
                      'We could inspect the inputs and queue a bounded task.',
                      'We could inspect the inputs and put your task into the queue.',
                      'We can ask Codex to start a bounded task.',
                      'We can ask Codex to review the inputs and put your task into the queue.',
                      "We could inspect Codex's report and put your task into the queue.",
                      'Should we keep the report limited to memory and queue state?',
                      'Claude can prepare a report; we should compare the findings.'):
            with self.subTest(prose=prose):
                self.assertFalse(claims_dispatch(prose))
                for extra in (' I queued your repair.',' and queued your repair.',
                              ' and will queue your repair.',' webchat-'+'b'*32):
                    self.assertTrue(claims_dispatch(prose+extra))
        for prose in ('We queue your task now.','We put your task into the queue.',
                      'The task is queued.','I have delegated your repair.',
                      'We can inspect it and have queued your task.',
                      'We checked the inputs and put your task into the queue.',
                      'We reviewed the report and delegated your task to Codex.'):
            self.assertTrue(claims_dispatch(prose))
        for prose in ('We could inspect inputs and Bob checked the logs and put your task into the queue.',
                      'We could inspect inputs and Codex reviewed the logs and put your task into the queue.',
                      'We asked Codex to start a bounded task.'):
            self.assertTrue(claims_dispatch(prose))

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

    def test_identifier_headers_and_assigned_inputs_are_not_actor_dispatch(self):
        from dispatch_receipts import claims_dispatch
        answers=(
            '**Review (`project-bob`, checkpoint 82):** Casey is the assigned owner for a proposed read-only review.',
            '**Handoff (`project_codex`, checkpoint 82):** Casey is the assigned owner for a proposed read-only review.',
            '**Codex review:** In this draft, Casey is assigned the bounded review.',
            'Codex handles chat, reserving Cursor for assigned worktrees.',
            'Local workers like Codex or Cursor access assigned files through their executor.',
            'Codex has read access to assigned worktrees.',
        )
        for content in answers:
            self.assertFalse(claims_dispatch(content),content)
            self.assertEqual(enforce(self.root,'Explain the available approach.',dict(provider='gemini',content=content)),content)
            for effect in (' I queued the follow-up task.', ' Codex started the repair.',
                           ' Your repair task was assigned.', ' Codex: assigned the repair.',
                           ' Job webchat-'+'a'*32+' is running.'):
                self.assertTrue(claims_dispatch(content+effect),content+effect)
        for claim in ('Bob assigned the review.', 'Web Bob queued the repair.',
                      'Codex assigned worktrees to Cursor.', 'Codex: queued the review.',
                      '**Codex:** queued the repair.', '**Codex**: queued the repair.',
                      '**Bob:** assigned the review.', '_Gemini_: started the audit.',
                      '**Review:** has been assigned.', 'Task: queued.'):
            self.assertTrue(claims_dispatch(claim),claim)
