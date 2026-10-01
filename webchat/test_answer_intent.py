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
                     "Queued means the job is waiting in line for a worker to pick it up — it's been assigned but not started yet. Running means a worker has grabbed it and is actively doing the work.",
                     'Running means execution has begun; queued means it is waiting.'):
            self.fake.reply_text = text
            self.assertEqual(self.send('What is the difference between queued and running?')['content'], text)

    def test_requested_deliverables_are_answered_in_chat(self):
        self.fake.reply_text = 'Here is the requested answer from the supplied evidence.'
        for prompt in ('Write a four-line poem about the lake.',
                       'Please write a four-line poem about the lake.',
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


    def test_explicit_execution_targets_and_worker_choices_remain_tasks(self):
        for prompt in ('Write hello to /tmp/answer-intent-proof.txt',
                       'Review PR #161',
                       'Review services/api.py', 'Fix Web Bob login tests',
                       'Have Gemini research Web Bob browser support',
                       'Codex: write a parser with regression tests',
                       'Create a pull request for the parser fix'):
            with self.subTest(prompt=prompt):
                self.assertIsNotNone(parse_work(prompt)[0])

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
        conversation['messages'] = [dict(role='user',content='Explain the supplied numbers.',status='done')]
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
