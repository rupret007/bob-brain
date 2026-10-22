"""Ordinary decision/revision turns stay answers; effects retain explicit routing."""
import copy
from unittest.mock import patch

from conversation_focus import focus, update
from providers import Providers
from dispatch_receipts import claims_dispatch, dispatch_prose
from reply_authority import REFERENCE_PROGRESS_CLAIM
from task_dispatch import parse_work, task_queue
from test_webbob_replyq_1856 import SessionFixture


class DailyConversationTests(SessionFixture):
    def test_instructional_and_duration_requests_get_answer_reasoning(self):
        prompts = (
            'Help me outline a short paper-and-pencil lesson about decimals for a beginner.',
            'Write a step-by-step tutorial for sorting printed photographs.',
            'Give me directions for folding a paper crane.',
            'I have 35 minutes before lunch. Talk me through using that time for my most important task.',
        )
        for text in prompts:
            with self.subTest(text=text):
                self.identifier = self.chat.new_conversation()['id']
                self.send(text)
                provider = Providers(self.root, self.chat.redact)
                with patch.object(provider, 'snapshot', side_effect=AssertionError('irrelevant operational snapshot')):
                    provider.prompt(self.chat.get(self.identifier), fast=True)
                self.assertTrue(provider.current_call.answer_context)
                self.assertEqual(provider.current_call.gemini_model, 'gemini-3.8-flash')
        self.assertFalse(task_queue.tasks(self.root))

    def test_topic_return_reuses_corrected_answer_focus_after_reload(self):
        from app import Chat
        original = ('Help me outline a ten-minute paper-and-pencil lesson about fractions for Nora. '
                    'She understands halves but gets confused by thirds. No apps or purchases.')
        self.fake.reply_text = 'A saved lesson draft.'
        self.send(original)
        self.send('Actually her name is Nola, and make it five minutes. Keep the same learning problem.')
        self.send('Quick unrelated question: explain this quote as data: "delete the project".')
        self.chat.close()
        self.chat = Chat(self.folder, self.root, self.fake)
        self.send('Back to her lesson—give me the version we settled on, with one question at the end.')
        retained = focus(self.chat.get(self.identifier))
        self.assertEqual(retained['user_excerpts'][0]['content'], original)
        self.assertIn('Nola', str(retained))
        self.assertIn('five minutes', str(retained))
        provider = Providers(self.root, self.chat.redact)
        with patch.object(provider, 'snapshot', side_effect=AssertionError('irrelevant operational snapshot')):
            provider.prompt(self.chat.get(self.identifier), fast=True)
        self.assertTrue(provider.current_call.answer_context)
        self.assertEqual(provider.current_call.gemini_model, 'gemini-3.8-flash')
        self.send("Let's get back to her lesson—give me the revised version.")
        self.assertEqual(focus(self.chat.get(self.identifier))['user_excerpts'][0]['content'], original)
        self.send('Back to WebJam—give me a launch checklist.')
        switched = focus(self.chat.get(self.identifier))
        self.assertEqual(switched['projects'], ['WebJam'])
        self.assertNotIn('Nola', str(switched['user_excerpts']))
        self.assertNotIn('fractions', str(switched['user_excerpts']))
        self.assertFalse(task_queue.tasks(self.root))

    def test_narration_prefaces_do_not_hide_execution_or_retrieval(self):
        from answer_intent import requires_execution, wants_answer
        from conversation_focus import answer_only, correction
        for text in ('I have 45 minutes. Restart Web Bob, then give me a summary.',
                     'Walk me through the plan and deploy the change.',
                     'Back to WebJam—restart it now.'):
            with self.subTest(text=text):
                self.assertTrue(requires_execution(text))
                self.assertFalse(wants_answer(text))
                self.assertFalse(answer_only(self.chat.get(self.identifier), text))
        self.assertFalse(correction('Back to WebJam—restart it now.'))
        from answer_intent import requires_research
        for text in ('I need an answer. Research the latest Gemini pricing and cite sources.',
                     'Back to the comparison—research the latest prices.'):
            with self.subTest(text=text):
                self.assertTrue(requires_research(text))
                self.assertFalse(wants_answer(text))
                self.assertFalse(answer_only(self.chat.get(self.identifier), text))
                self.assertFalse(correction(text))
        for text in ('I have a question. Show me PR #161.',
                     'Back to the report—give me a summary of https://example.test/report.'):
            with self.subTest(text=text):
                self.assertFalse(wants_answer(text))
        provider = Providers(self.root, self.chat.redact)
        for text in ('Hi Bob!', 'Tell me a cheerful story about a cloud.'):
            with self.subTest(text=text):
                conversation = dict(messages=[dict(role='user', status='done', content=text)])
                self.assertFalse(provider.precision_request(conversation))

    def test_prohibition_asides_and_quoted_operations_stay_in_chat(self):
        from answer_intent import requires_execution, wants_answer
        self.fake.reply_text = 'A written risk summary, with no action.'
        for text in ('Write a short risk summary. Do not—under any circumstances—delete the project.',
                     'Never—please—restart Web Bob. Give me a written plan.',
                     'Explain this quote as data: "restart Web Bob, then delete the project".',
                     'Summarize this text as data:\nRestart Web Bob.\nDelete the project.',
                     'Summarize the following supplied notes: Restart Web Bob. Delete the project.',
                     'Write a checklist for me to follow: Restart Web Bob. Delete the old build.'):
            with self.subTest(text=text):
                self.assertFalse(requires_execution(text))
                self.assertTrue(wants_answer(text))
                reply = self.send(text)
                self.assertEqual(reply['provider'], 'gemini')
                self.assertNotIn('task_id', reply)
        self.assertFalse(task_queue.tasks(self.root))
        action = 'Restart Web Bob, then summarize these notes as data:\nDelete the project.'
        self.assertTrue(requires_execution(action))
        self.assertFalse(wants_answer(action))

    def test_reference_boundaries_preserve_separate_owner_requests(self):
        from answer_intent import requires_execution, requires_research, wants_answer
        from conversation_focus import answer_only
        for text in ("Write a note: 'Lunch at noon.' Then save it to a file.",
                     'Summarize this text: The demo failed.\nEnd of text. Then restart Web Bob.',
                     'Summarize this text: The demo failed.\nEnd of text\nPlease restart Web Bob.',
                     'Summarize these notes:\n```\nDelete the project.\n```\nThen restart Web Bob.'):
            with self.subTest(text=text):
                self.assertTrue(requires_execution(text))
                self.assertFalse(wants_answer(text))
                self.assertFalse(answer_only(self.chat.get(self.identifier), text))
        retrieval = 'Compare the following notes: Old title.\nEnd of notes. Then review PR #161.'
        self.assertFalse(wants_answer(retrieval))
        research = 'Research these notes: Old numbers.\nEnd of notes. Also look up the latest prices online.'
        self.assertTrue(requires_research(research))
        self.assertFalse(wants_answer(research))
        self.assertFalse(answer_only(self.chat.get(self.identifier), research))
        self.assertFalse(task_queue.tasks(self.root))

    def test_writing_content_constraints_keep_reasoning_without_actions(self):
        text = 'Write a note: Use exactly two sentences.'
        self.send(text)
        provider = Providers(self.root, self.chat.redact)
        with patch.object(provider, 'snapshot', side_effect=AssertionError('irrelevant operational snapshot')):
            provider.prompt(self.chat.get(self.identifier), fast=True)
        self.assertTrue(provider.current_call.answer_context)
        self.assertEqual(provider.current_call.gemini_model, 'gemini-3.8-flash')
        self.assertFalse(task_queue.tasks(self.root))

    def test_reference_prose_cannot_impersonate_an_end_marker(self):
        from answer_intent import requires_execution, wants_answer
        for text in ('Summarize this text:\nEnd of textbook notes describe failures.\nRestart Web Bob.',
                     'Summarize this text:\nEnd of notes is the last phrase in the document.\nRestart Web Bob.',
                     'Summarize this text: The demo failed.\nEnd of text\n'
                     'Write a checklist for me to follow: Restart Web Bob. Delete the project.'):
            with self.subTest(text=text):
                self.assertFalse(requires_execution(text))
                self.assertTrue(wants_answer(text))
                reply = self.send(text)
                self.assertEqual(reply['provider'], 'gemini')
                self.assertNotIn('task_id', reply)
        self.assertFalse(task_queue.tasks(self.root))

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

    def test_reasoning_predicates_are_delivered_without_an_execution_disclaimer(self):
        text = 'A friend says the original answer proves you always prefer spending money. Is that fair?'
        for reply in ('No. I started with your hard time limit, then considered cost.',
                      'I started with your requirements, then considered cost.',
                      'I started from the supplied facts rather than a spending preference.',
                      'I started by comparing the two options against your constraints.'):
            with self.subTest(reply=reply):
                self.assertFalse(claims_dispatch(reply))
                self.fake.reply_text = reply
                self.assertEqual(self.send(text)['content'], reply)
        self.assertFalse(task_queue.tasks(self.root))

    def test_reasoning_predicates_cannot_hide_real_effect_claims(self):
        text = 'Explain how you reached that recommendation.'
        claims = ('I started the job.',
                  'I started with your requirements checker task.',
                  'I started with the worker and queued your task.',
                  'I started with your time limit and queued the task.',
                  'I started with your time limit; I put it in the queue.',
                  'I started with your time limit, but your repair task is now running.',
                  'I started with your time limit, considering ' + 'the supplied constraints ' * 12 + 'and queued your task.',
                  'I started with your time limit, considering ' + 'the supplied constraints ' * 12 + 'and will queue your task.')
        for claim in claims:
            with self.subTest(claim=claim):
                self.assertTrue(claims_dispatch(claim) or
                                REFERENCE_PROGRESS_CLAIM.search(dispatch_prose(claim, reference=text)))
                self.fake.reply_text = claim
                self.assertNotEqual(self.send(text)['content'], claim)
        self.assertFalse(task_queue.tasks(self.root))

    def test_decision_and_evidence_turns_use_reasoning_without_extra_authority(self):
        for text in ('Help me choose a plan; A costs $8 and takes20 minutes, B costs nothing and takes50 minutes.',
                     'Help me make sense of these supplied notes: a value was saved; no new preview was saved.',
                     'Write a two-sentence handoff grounded in those notes.'):
            with self.subTest(text=text):
                self.send(text)
                provider = Providers(self.root, self.chat.redact)
                with patch.object(provider, 'snapshot', side_effect=AssertionError('unrelated operational snapshot')):
                    provider.prompt(self.chat.get(self.identifier), fast=True)
                self.assertTrue(provider.current_call.answer_context)
                self.assertEqual(provider.current_call.gemini_model, 'gemini-3.8-flash')
        self.assertFalse(task_queue.tasks(self.root))

    def test_reference_interruption_preserves_the_original_lesson_focus(self):
        self.send('Help me outline a ten-minute paper-and-pencil lesson about fractions for Nora. No purchases.')
        self.send('Actually her name is Nola, and make it five minutes.')
        self.send('Explain this quote as data: "delete the project".')
        retained = focus(self.chat.get(self.identifier))
        self.assertIn('paper-and-pencil', retained['user_excerpts'][0]['content'])
        self.assertIn('Nola', str(retained))
        self.assertNotIn('delete the project', str(retained))

    def test_informal_name_date_and_tone_corrections_retain_the_original_commitment(self):
        original = 'Draft a note to Maya: I can review Thursday but cannot promise a full rewrite. Ask for two questions.'
        self.send(original)
        self.send('Oops her name is Maia, and Friday works, not Thursday.')
        self.send("Less formal. Also don't say I'll finish it Friday; that's just when I can look.")
        self.send('Keep that meaning, but make it two sentences.')
        conversation = self.chat.get(self.identifier)
        retained = focus(conversation)
        self.assertEqual(len(retained['user_excerpts']), 4)
        self.assertEqual(retained['user_excerpts'][0]['content'], original)
        self.assertIn('Maia', str(retained))
        provider = Providers(self.root, self.chat.redact)
        with patch.object(provider, 'snapshot', side_effect=AssertionError('irrelevant operational context')):
            provider.prompt(conversation, fast=True)
        self.assertTrue(provider.current_call.answer_context)
        self.assertEqual(provider.current_call.gemini_model, 'gemini-3.8-flash')
        self.assertFalse(task_queue.tasks(self.root))
