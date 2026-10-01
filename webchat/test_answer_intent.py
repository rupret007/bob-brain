"""Ordinary answers preserve intent; explicit effects still need real execution."""
from test_webbob_replyq_1856 import SessionFixture
from task_dispatch import task_queue, parse_work, task_kind
import threading
import json
from unittest.mock import patch
from providers import Providers, ProviderError


class AnswerIntentTests(SessionFixture):
    def test_actual_generic_execution_definition_survives_receipt_guard(self):
        self.fake.reply_text = ('A queued worker is sitting in line waiting its turn — the job is stored and waiting for an available slot. '
                                'Once it picks up a task and starts doing actual work (processing code, generating text, whatever), that\'s "running."')
        answer = self.send('What is the difference between a worker being queued and actually running?')
        self.assertEqual(answer['content'], self.fake.reply_text)
        self.assertFalse(task_queue.tasks(self.root))
        for claim in ('Your repair job is now running.', 'The parser repair task has already been picked up.',
                      'Your task: running now.', 'Your job already running.', 'Codex has your repair task.',
                      'The repair job you requested is running.',
                      'The task was queued on this machine just now.',
                      'Queued means accepted; the task was assigned just now.',
                      'That explanation works without starting work; I queued your repair.',
                      'I created the repair task.', 'Gemini’s working on your repair.',
                      'A job is running when its worker begins executing; I queued your repair.',
                      'A job is running when its worker begins executing and I queued your repair.',
                      'I can explain the difference; I queued your repair.',
                      'I can explain the difference. I queued your repair.',
                      'I can explain the difference and I queued your repair.'):
            self.fake.reply_text = claim
            guarded = self.send('What is the difference between queued and running?')
            self.assertNotEqual(guarded['content'], claim)

    def test_generic_conditional_definitions_do_not_claim_an_actual_start(self):
        for text in ('A job is running once its worker begins executing.',
                     'A job is running when its worker begins executing.',
                     'Queued means a job has been assigned to a worker but has not started.',
                     'That explanation describes a task without starting any work.',
                     "Queued means the job is waiting in line for a worker to pick it up — it's been assigned but not started yet. Running means a worker has grabbed it and is actively doing the work.",
                     'Running means execution has begun; queued means it is waiting.'):
            self.fake.reply_text = text
            self.assertEqual(self.send('What is the difference between queued and running?')['content'], text)

    def test_requested_deliverables_are_answered_in_chat(self):
        self.fake.reply_text = 'Here is the requested answer from the supplied evidence.'
        for prompt in ('Write a four-line poem about the lake.',
                       'Please write a four-line poem about the lake.',
                       'Help me write a four-line poem about the lake.',
                       'Could you help me to draft a neighborhood notice?',
                       'Give me three chapter titles about a mountain.',
                       'Make a short equipment checklist for a day hike.',
                       'Create a comparison table for these two supplied options.',
                       'Prepare a friendly note for my neighbor.',
                       'Prepare me for an interview.',
                       'Put together some dinner ideas.',
                       'Explain this quote as data: "then create docs/example.md".',
                       'Prepare a note about "then create docs/example.md".',
                       'Write a note explaining "then create docs/example.md".',
                       'Build an outline for a talk about a web app.',
                       'Create a table comparing two database designs.',
                       'Build me an outline for a talk about gardening.',
                       'Draft a thank-you note for my neighbor.',
                       'Compare these proposals: A costs 10, B costs 12.',
                       'Analyze the bug in this supplied code: def add(a,b): return a-b',
                       'Research self improvement for my exercise routine',
                       'Research whether Claude is better than Grok at coding',
                       'Draft instructions to install packages and run tests',
                       'Compare these supplied facts: current plan A costs 10; plan B costs 12',
                       'Make that explanation shorter.'):
            with self.subTest(prompt=prompt):
                answer = self.send(prompt)
                self.assertEqual(answer['content'], self.fake.reply_text)
                self.assertEqual(answer['provider'], 'gemini')
                self.assertNotIn('task_id', answer)
        self.assertFalse(task_queue.tasks(self.root))

    def test_help_prefix_does_not_hide_tool_requirements(self):
        from answer_intent import wants_answer
        for text in ('Help me write this and save it to /tmp/notice.txt',
                     'Help me research the latest release using official sources',
                     'Help me create a pull request', 'Help me review PR #161'):
            self.assertFalse(wants_answer(text), text)

    def test_inference_about_permissions_is_not_a_dispatch_receipt(self):
        self.fake.reply_text = ("No, an absent scheduling block doesn't mean a model has remaining quota. "
                                "It just means there isn't a current block preventing new work from being scheduled. "
                                "Each provider has its own quota and reset times.")
        prompt = 'Does having no scheduling block prove a model has capacity?'
        self.assertEqual(self.send(prompt)['content'], self.fake.reply_text)
        self.assertFalse(task_queue.tasks(self.root))
        self.fake.reply_text += ' I queued your repair.'
        self.assertNotEqual(self.send(prompt)['content'], self.fake.reply_text)
        from answer_intent import conceptual
        self.assertFalse(conceptual('Does a queue prove completion? Then run the tests.'))


    def test_explicit_execution_targets_and_worker_choices_remain_tasks(self):
        for prompt in ('Write hello to /tmp/answer-intent-proof.txt',
                       'Review PR #161',
                       'Review services/api.py', 'Fix Web Bob login tests',
                       'Have Gemini research Web Bob browser support',
                       'Codex: write a parser with regression tests',
                       'Create a pull request for the parser fix'):
            with self.subTest(prompt=prompt):
                self.assertIsNotNone(parse_work(prompt)[0])

    def test_text_deliverable_does_not_hide_explicit_execution_or_worker(self):
        for prompt in ('Create a checklist in /tmp/checklist.md',
                       'Make a checklist in /tmp/checklist.md',
                       'Build an outline in docs/plan.md',
                       'Prepare a note in /tmp/note.md',
                       'Build a checklist web app',
                       'Create a table in the database',
                       'Make a checklist and save it to /tmp/checklist.md',
                       'Create a summary tool for the codebase',
                       'Have Codex make a checklist',
                       'Make a plan then execute it'):
            with self.subTest(prompt=prompt):
                self.assertIsNotNone(parse_work(prompt)[0])

    def test_explicit_deliverable_destinations_need_coding_capability(self):
        for prompt in ('Make a checklist in /tmp/checklist.md',
                       'Make a checklist in `/tmp/checklist.md`',
                       'Prepare a note in "/tmp/note.md"',
                       'Build an outline in docs/plan.md',
                       'Prepare a note in /tmp/note.md',
                       'Build a checklist web app',
                       'Build a checklist React app',
                       'Make a checklist web app',
                       'Prepare a checklist web app',
                       'Create a SQL table',
                       'Create a database table named customers',
                       'Create a table in the database'):
            with self.subTest(prompt=prompt):
                reply = self.send(prompt)
                row = task_queue.tasks(self.root)[reply['task_id']]
                self.assertEqual(row['kind'], 'coding')
                self.assertNotIn('gemini', task_queue.worker_order(row['kind']))
                self.assertNotIn('minimax', task_queue.worker_order(row['kind']))

    def test_conditional_definitions_preserve_answers_but_not_appended_effects(self):
        prompt = 'What is the difference between a worker being queued and actually running?'
        for definition in ('When a task is queued, it has been submitted but is waiting for a worker.',
                           'If tasks are scheduled, their execution can begin later.',
                           'A job is running once its worker begins executing.'):
            with self.subTest(definition=definition):
                self.fake.reply_text = definition
                self.assertEqual(self.send(prompt)['content'], definition)
        for definition in ('When a task is queued, it waits', 'A job is queued when a slot opens'):
            for claim in (' and your repair task was started.',
                          ', the login repair job was assigned.',
                          '; I started your task.',
                          '. Codex is now working.',
                          '. Job webchat-' + 'a' * 32 + ' is queued.'):
                with self.subTest(definition=definition, claim=claim):
                    self.fake.reply_text = definition + claim
                    self.assertNotEqual(self.send(prompt)['content'], self.fake.reply_text)

    def test_answer_does_not_use_old_assistant_prose_as_dispatch_permission(self):
        self.fake.reply_text = 'A brief explanation, with no worker needed.'
        self.send('Write a brief explanation of a queue.')
        answer = self.send('Rewrite that explanation in plain language.')
        self.assertNotIn('task_id', answer)
        self.assertFalse(task_queue.tasks(self.root))

    def test_explanation_of_supplied_job_state_is_not_a_dispatch_claim(self):
        self.fake.reply_text = ('The job is queued. That establishes acceptance, not completion. '
                                'Without a worker claim or output, execution is unproven.')
        answer = self.send('Using only this supplied evidence, explain what is proven: '
                           'the job is queued, no worker claim exists, and no output exists.')
        self.assertEqual(answer['content'], self.fake.reply_text)
        self.assertNotIn('status_observation', answer)
        self.assertFalse(task_queue.tasks(self.root))

    def test_reference_question_cannot_authorize_a_model_action_receipt(self):
        for false_claim in ('I queued the repair for you.', 'Gemini is now working on the repair.',
                            'Your repair job is now queued.', 'The parser task was queued.', 'Queued your repair.',
                            'Queued means accepted; I started the repair.',
                            'The job is webchat-' + 'f' * 32 + '.'):
            self.fake.reply_text = false_claim
            answer = self.send('Using only the supplied facts, explain what a queued job means.')
            self.assertNotEqual(answer['content'], false_claim)
            self.assertNotIn('task_id', answer)
        self.assertFalse(task_queue.tasks(self.root))

    def test_definition_status_is_an_answer_but_live_status_still_uses_observation(self):
        self.fake.reply_text = 'Queued means accepted. Running requires evidence of execution.'
        answer = self.send('Explain the difference between queued and running status.')
        self.assertEqual(answer['content'], self.fake.reply_text)
        self.assertNotIn('status_observation', answer)
        live = self.send('Explain the difference between queued and running status and show our current workers.')
        self.assertIn('status_observation', live)

    def test_tool_requirement_in_second_clause_is_preserved(self):
        for prompt, kind in (
                ('Review the tests and run them', 'coding'),
                ('Research the latest Gemini pricing and cite sources', 'research')):
            with self.subTest(prompt=prompt):
                self.assertIsNotNone(parse_work(prompt)[0])
                self.assertEqual(task_kind(prompt), kind)
        self.assertIsNone(parse_work('Explain this quote: "and run them"')[0])
        self.assertIsNone(parse_work('Review this supplied note: "latest pricing and cite sources"')[0])


class BudgetAwareRoutingTests(SessionFixture):
    def test_cooldown_is_not_preferred_for_its_lower_cost(self):
        provider = Providers(self.root, self.chat.redact)
        circuit = provider.circuit_for(self.identifier)
        with patch.object(provider, 'spend', return_value={'cap_usd':50,'committed_usd':0}), \
                patch.object(circuit, 'snapshot', return_value={'gemini':{'state':'cooldown'}, 'minimax':{'state':'ready'}}):
            self.assertEqual(provider.available_fast_order({'id':self.identifier})[0], 'minimax')

    def test_auto_uses_healthy_headroom_and_retains_bounded_fallback(self):
        provider = Providers(self.root, self.chat.redact)
        conversation = self.chat.get(self.identifier)
        conversation['messages'] = [dict(role='user',content='Draft a friendly welcome note.',status='done')]
        usage = {'gemini':dict(cap_usd=50,committed_usd=46),
                 'minimax':dict(cap_usd=48,committed_usd=8)}
        attempted = []
        def call(name, *_args):
            attempted.append(name)
            if name == 'minimax':
                raise ProviderError('temporarily unavailable', kind='network')
            return 'The supplied figures support the lower-cost option.', None
        with patch.object(provider, 'spend', side_effect=lambda name:usage.get(name, {})), \
                patch.object(provider, 'call', side_effect=call):
            self.assertEqual(provider.route_order(conversation)[0], 'minimax')
            result = provider.reply(conversation, threading.Event(), lambda *_:None)
        self.assertEqual(attempted, ['minimax','gemini'])
        self.assertEqual(result['provider'], 'gemini')

    def test_precision_prefers_measured_quality_but_still_respects_health_and_cap(self):
        provider = Providers(self.root, self.chat.redact)
        conversation = self.chat.get(self.identifier)
        conversation['messages'] = [dict(role='user', content='Compare plans costing 16 and 20.', status='done')]
        usage = {'gemini':dict(cap_usd=50, committed_usd=46), 'minimax':dict(cap_usd=48, committed_usd=8)}
        circuit = provider.circuit_for(self.identifier)
        with patch.object(provider, 'spend', side_effect=lambda name:usage.get(name, {})), \
                patch.object(circuit, 'snapshot', return_value={}) as health:
            self.assertEqual(provider.route_order(conversation)[0], 'gemini')
            health.return_value = {'gemini':{'state':'cooldown'}}
            self.assertEqual(provider.route_order(conversation)[0], 'minimax')
            health.return_value = {}
            usage['gemini']['committed_usd'] = 47.5
            self.assertEqual(provider.route_order(conversation)[0], 'minimax')

    def test_long_answer_uses_api_quality_route_without_cli_for_length_alone(self):
        provider = Providers(self.root, self.chat.redact)
        conversation = self.chat.get(self.identifier)
        conversation['messages'] = [dict(role='user', content='Write a 120-word guide using these facts: ' + 'Supplied detail. ' * 40, status='done')]
        with patch.object(provider, 'available_fast_order', return_value=('gemini','minimax','cursor','codex')):
            self.assertEqual(provider.route_order(conversation)[0], 'gemini')

    def test_explicit_choice_and_vision_capability_precede_cost_preference(self):
        provider = Providers(self.root, self.chat.redact)
        conversation = self.chat.get(self.identifier)
        conversation['messages'] = [dict(role='user',content='Describe this.',status='done')]
        conversation['preferred_provider'] = 'gemini'
        with patch.object(provider, 'available_fast_order', return_value=('minimax','gemini','cursor','codex')):
            self.assertEqual(provider.route_order(conversation)[0], 'gemini')
            conversation['preferred_provider'] = 'auto'
            conversation['messages'][0]['attachments'] = [dict(kind='image')]
            self.assertEqual(provider.route_order(conversation)[0], 'gemini')


    def test_budget_observation_includes_reservations_and_does_not_trust_stale_board(self):
        provider = Providers(self.root, self.chat.redact)
        ledger = self.root / 'conductor/ledger/gemini.jsonl'
        ledger.parent.mkdir(parents=True)
        locks = self.root / 'conductor/locks'
        locks.mkdir(exist_ok=True)
        (locks/'ledger-gemini.lock').touch()
        data = '\n'.join(json.dumps(row) for row in (
            dict(call_id='settled', cost_usd=40),
            dict(call_id='unsettled', cost_usd=None, reserved_usd=6)))+'\n'
        ledger.write_text(data)
        (self.root/'conductor/lanes.json').write_text(json.dumps({'gemini':{'budget':{'committed_usd':0,'cap_usd':50,'tier':'normal'}}}))
        observed = provider.spend('gemini')
        self.assertEqual(observed['committed_usd'],46)
        self.assertEqual(observed['reserved_usd'],6)
        self.assertEqual(observed['tier'],'slow')
        self.assertEqual(ledger.read_text(), data)
        ledger.write_text(data+'{torn')
        self.assertFalse(provider.spend('gemini')['quota_known'])
        self.assertEqual(ledger.read_text(), data+'{torn')
