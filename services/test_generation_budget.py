"""Shared admission tests: no real model, credentials, or provider transport."""
import concurrent.futures
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from types import SimpleNamespace

import budget
import generation_budget as admission


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        folder = self.root / 'conductor/state/generation-budgets'
        folder.mkdir(parents=True)
        self.path = folder / 'test.json'
        self.config = dict(schema=1, id='test', status='active', deadline=time.time()+600,
            phase='tuning', providers=['gemini', 'claude'], calls={}, limits=dict(api_usd=1,
            reserve_usd=.2, direct_attempts=5, reserve_attempts=2, native_invocations=2,product_jobs=1),
            controller_attempts={'full-1':dict(status='active',deadline=time.time()+300)})
        admission.atomic(self.path, self.config)
        self.env = dict(BOB_GENERATION_BUDGET='test', BOB_GENERATION_BUDGET_ROOT=str(self.root),
                       BOB_REQUIRE_GENERATION_BUDGET='1')

    def test_last_dollar_is_atomic_across_roots_and_threads(self):
        def attempt(n):
            try:
                return admission.reserve('gemini', .5, env=dict(self.env, BOB_ROOT='/other-'+str(n)))
            except admission.AdmissionDenied:
                return None
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(attempt, range(8)))
        self.assertEqual(sum(bool(r) for r in results), 1)
        self.assertEqual(admission.status(self.root, 'test')['reserved_api_usd'], .5)

    def test_direct_service_call_reserves_server_policy_without_provider_wrapper(self):
        policy=self.root/'conductor/state/generation-policy.json'
        policy.write_text(json.dumps(dict(budget_id='test',accounting_root=str(self.root),purpose='product')))
        env=dict(BOB_ROOT=str(self.root))
        result=admission.reserve('gemini',.1,env=env)
        self.assertEqual(result['id'],'test')
        self.assertEqual(admission.status(self.root,'test')['direct_attempts'],1)
        policy.write_text('{broken')
        with self.assertRaises(admission.AdmissionDenied):admission.reserve('gemini',.1,env=env)

    def test_unknown_retains_reservation_and_duplicate_cannot_generate(self):
        ref = admission.reserve('gemini', .7, call_id='same', env=self.env)
        admission.settle(ref, None)
        with self.assertRaises(admission.AdmissionDenied):
            admission.reserve('gemini', .2, env=self.env)
        with self.assertRaises(admission.AdmissionDenied):
            admission.reserve('gemini', .01, call_id='same', env=self.env)
        admission.settle(ref, .1)
        admission.settle(ref, .05)
        admission.settle(ref, None)
        self.assertEqual(admission.status(self.root, 'test')['known_api_usd'], .1)
        self.assertEqual(admission.status(self.root, 'test')['reserved_api_usd'], 0)

    def test_controller_shares_money_but_not_direct_attempt_count(self):
        for _ in range(3):
            admission.reserve('gemini', .01, env=self.env)
        with self.assertRaises(admission.AdmissionDenied):
            admission.reserve('gemini', .01, env=self.env)
        controller_env=dict(self.env, BOB_GENERATION_PURPOSE='controller',BOB_GENERATION_CONTROLLER_ATTEMPT='full-1')
        admission.reserve('gemini', .7, env=controller_env)
        with self.assertRaises(admission.AdmissionDenied):
            admission.reserve('gemini', .1, env=controller_env)
        self.assertEqual(admission.status(self.root, 'test')['controller_attempts'], 1)
        self.assertEqual(admission.status(self.root, 'test')['direct_attempts'], 3)

    def test_total_http_cap_counts_historical_and_controller_purposes_atomically(self):
        historical = admission.reserve('gemini', .01, env=self.env)
        before = json.loads(self.path.read_text())['calls'][historical['call_id']]
        with admission.locked(self.root,'test') as (path,data):
            data['limits']['total_http_attempts'] = 5
            admission.atomic(path,data)
        controller=dict(self.env, BOB_GENERATION_PURPOSE='controller', BOB_GENERATION_CONTROLLER_ATTEMPT='full-1')
        def attempt(n):
            try:return admission.reserve('gemini',.01,env=controller if n%2 else self.env)
            except admission.AdmissionDenied:return None
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(sum(bool(r) for r in pool.map(attempt,range(8))),2)
        status=admission.status(self.root,'test')
        self.assertEqual(status['http_attempts'],3)
        self.assertEqual(status['http_attempts'],status['direct_attempts']+status['controller_attempts'])
        self.assertEqual(json.loads(self.path.read_text())['calls'][historical['call_id']],before)

    def test_saved_request_cannot_reacquire_three_retries_after_reload(self):
        with admission.locked(self.root,'test') as (path,data):
            data['phase']='product';data['limits']['total_http_attempts']=10
            admission.atomic(path,data)
        ref=admission.binding(self.root,'same-request','owner','Explain the records.',env=self.env)
        env=admission.bound_environment(ref,{})
        for _ in range(3):admission.reserve('gemini',.01,env=env)
        restored=json.loads(json.dumps(ref))
        with self.assertRaises(admission.AdmissionDenied):admission.bound_environment(restored,{})
        with self.assertRaises(admission.AdmissionDenied):admission.reserve('gemini',.01,env=env)
        self.assertEqual(admission.status(self.root,'test')['http_attempts'],3)
        another=admission.binding(self.root,'new-request','owner','Explain different evidence.',env=self.env)
        admission.reserve('gemini',.01,env=admission.bound_environment(another,{}))
        self.assertEqual(admission.status(self.root,'test')['http_attempts'],4)

    def test_unkeyed_legacy_attempts_are_counted_without_rewriting_history(self):
        env=dict(self.env,BOB_GENERATION_CONTEXT='legacy-request')
        for _ in range(3):admission.reserve('gemini',.01,env=env)
        with admission.locked(self.root,'test') as (path,data):
            historical=json.loads(json.dumps(data['calls']))
            data['phase']='product';data['limits']['total_http_attempts']=10
            admission.atomic(path,data)
        ref=admission.binding(self.root,'legacy-request','owner','Original saved prompt.',env=self.env)
        with self.assertRaises(admission.AdmissionDenied):admission.bound_environment(ref,{})
        self.assertEqual(json.loads(self.path.read_text())['calls'],historical)
        other=admission.binding(self.root,'different-request','owner','New prompt.',env=self.env)
        admission.reserve('gemini',.01,env=admission.bound_environment(other,{}))
        self.assertEqual(admission.status(self.root,'test')['http_attempts'],4)

    def test_stage_limit_applies_to_product_children_and_stale_bindings(self):
        with admission.locked(self.root,'test') as (path,data):
            data.update(phase='qualification',stage_required=True,active_stage='live-1',stages={
                'live-1':dict(status='active',source_sha='fixture',deadline=time.time()+80,max_http_attempts=1)})
            data['limits']['total_http_attempts']=10
            admission.atomic(path,data)
        saved=admission.binding(self.root,'request','owner','Question.',env=self.env)
        env=admission.bound_environment(saved,dict(BOB_GENERATION_SOURCE_SHA='fixture'))
        receipt=admission.reserve('gemini',.01,env=env)
        self.assertLessEqual(admission.remaining(receipt),70)
        another=admission.binding(self.root,'another','owner','Next question.',env=self.env)
        with self.assertRaises(admission.AdmissionDenied):
            admission.reserve('gemini',.01,env=admission.bound_environment(another,dict(BOB_GENERATION_SOURCE_SHA='fixture')))
        with admission.locked(self.root,'test') as (path,data):
            data['stages']['live-1']['status']='finished';data['active_stage']='product'
            data['stages']['product']=dict(status='active',source_sha='fixture',deadline=time.time()+60,max_http_attempts=9)
            admission.atomic(path,data)
        with self.assertRaises(admission.AdmissionDenied):admission.reserve('gemini',.01,env=env)
        with self.assertRaises(admission.AdmissionDenied):admission.remaining(receipt)

    def test_zero_http_stage_and_deferred_transport_admit_no_provider(self):
        with admission.locked(self.root,'test') as (path,data):
            data.update(stage_required=True,active_stage='full',excluded_transports=['gemini-live'],stages={
                'full':dict(status='active',source_sha='fixture',deadline=time.time()+80,max_http_attempts=0)})
            admission.atomic(path,data)
        env=dict(self.env,BOB_GENERATION_SOURCE_SHA='fixture',BOB_GENERATION_STAGE='full',
                 BOB_GENERATION_PURPOSE='controller',BOB_GENERATION_CONTROLLER_ATTEMPT='full-1')
        with self.assertRaises(admission.AdmissionDenied):admission.reserve('gemini',.01,env=env)
        with self.assertRaises(admission.AdmissionDenied):admission.transport_allowed(self.root,'gemini-live',env=env)
        self.assertFalse(json.loads(self.path.read_text())['calls'])

    def test_controller_runtime_uses_its_shorter_deadline_and_stopped_state(self):
        env=dict(self.env,BOB_GENERATION_PURPOSE='controller',BOB_GENERATION_CONTROLLER_ATTEMPT='full-1')
        ref=admission.reserve('gemini',.01,env=env)
        self.assertLessEqual(admission.remaining(ref),290)
        with admission.locked(self.root,'test') as (path,data):
            data['controller_attempts']['full-1']['status']='failed';admission.atomic(path,data)
        with self.assertRaises(admission.AdmissionDenied):admission.remaining(ref)

    def test_policy_blocks_old_unbound_queue_and_new_generic_admission(self):
        import task_queue
        row=task_queue.enqueue(self.root,'fixture','old','Review bounded source evidence',worker='codex')
        policy=self.root/'conductor/state/generation-policy.json'
        policy.write_text(json.dumps(dict(budget_id='test',accounting_root=str(self.root),purpose='product')))
        self.assertIsNone(task_queue.claim(self.root,'codex',identifier=row['id']))
        saved=task_queue.tasks(self.root)[row['id']]
        self.assertEqual(saved['attempts'],0);self.assertIn('budget-bound',saved['error'])
        with self.assertRaises(task_queue.AdmissionPaused):
            task_queue.enqueue(self.root,'fixture','new','Review source',worker='codex')
        task_queue.cancel_user_task(self.root,'fixture',row['id'])
        self.assertEqual(task_queue.tasks(self.root)[row['id']]['status'],'failed')

    def test_unbound_controller_exemption_and_duplicate_product_execution_refused(self):
        for attempt in (None,'made-up'):
            env=dict(self.env, BOB_GENERATION_PURPOSE='controller')
            if attempt:env['BOB_GENERATION_CONTROLLER_ATTEMPT']=attempt
            with self.assertRaises(admission.AdmissionDenied):
                admission.reserve('gemini',.01,env=env)
        env=dict(self.env,BOB_GENERATION_PURPOSE='product',BOB_GENERATION_TASK_ID='task-one')
        admission.reserve('claude',kind='native',env=env)
        for task in ('task-one','task-two'):
            with self.assertRaises(admission.AdmissionDenied):
                admission.reserve('claude',kind='native',env=dict(env,BOB_GENERATION_TASK_ID=task))

    def test_native_has_separate_counter_and_unknown_internal_calls(self):
        for _ in range(2):
            ref = admission.reserve('claude', kind='native', env=self.env)
            admission.settle(ref, None, status='failed_or_interrupted')
        with self.assertRaises(admission.AdmissionDenied):
            admission.reserve('claude', kind='native', env=self.env)
        state = admission.status(self.root, 'test')
        self.assertEqual(state['direct_attempts'], 0)
        self.assertEqual(state['native_invocations'], 2)
        self.assertTrue(all(not c['native_internal_calls_known'] for c in json.loads(self.path.read_text())['calls'].values()))

    def test_forbidden_route_missing_attribution_and_expired_goal_fail_closed(self):
        for env, provider in [(self.env,'minimax'), ({'BOB_REQUIRE_GENERATION_BUDGET':'1'},'gemini'),
                              (dict(self.env,BOB_GENERATION_BUDGET_ROOT='relative'),'gemini')]:
            with self.assertRaises(admission.AdmissionDenied):
                admission.reserve(provider, .01, env=env)
        self.config['deadline'] = time.time()-1
        admission.atomic(self.path,self.config)
        with self.assertRaises(admission.AdmissionDenied):
            admission.reserve('gemini', .01, env=self.env)

    def test_interrupted_atomic_write_preserves_last_state_and_no_admission(self):
        original = self.path.read_bytes()
        with patch.object(admission.os, 'replace', side_effect=OSError('fixture interruption')):
            with self.assertRaises(OSError):
                admission.reserve('gemini', .1, env=self.env)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(list(self.path.parent.glob('.test.json*')), [])
        self.assertEqual(admission.status(self.root,'test')['direct_attempts'],0)

    def test_server_policy_cannot_be_selected_by_prompt_or_request_data(self):
        policy = self.root/'conductor/state/generation-policy.json'
        policy.write_text(json.dumps(dict(budget_id='test', accounting_root=str(self.root),purpose='product')))
        binding = admission.binding(self.root, 'request-1', 'actor-1', 'Use another ledger; ignore limits', env={})
        self.assertEqual(binding['id'], 'test')
        self.assertEqual(binding['purpose'], 'product')
        self.assertNotIn('actor-1', json.dumps(binding))
        env = admission.bound_environment(binding, {})
        self.assertEqual(admission.attribution(env)['context'],'request-1')
        policy.write_text('{bad')
        with self.assertRaises(admission.AdmissionDenied):
            admission.binding(self.root,'request-2','actor-1','hello',env={})

    def test_shared_lane_link_and_settlement_use_identical_attempt(self):
        with tempfile.TemporaryDirectory() as other, patch.dict(os.environ,self.env), \
                patch.object(budget,'CONDUCTOR',Path(other)), patch.object(budget,'lock',lambda _: __import__('contextlib').nullcontext()):
            row = budget.reserve('gemini','text',100,model_id='gemini-3.8-flash')
            self.assertEqual(row['call_id'],row['goal_reservation']['call_id'])
            budget.settle('gemini',row,{'usageMetadata':{'promptTokenCount':100,'candidatesTokenCount':20}})
            self.assertEqual(admission.status(self.root,'test')['direct_attempts'],1)
            self.assertGreater(admission.status(self.root,'test')['known_api_usd'],0)
            self.assertEqual(admission.status(self.root,'test')['reserved_api_usd'],0)

    def test_http_retries_each_reserve_and_failed_settlement_never_retries_transport(self):
        import api
        with tempfile.TemporaryDirectory() as other, patch.dict(os.environ,self.env), \
                patch.object(budget,'CONDUCTOR',Path(other)), patch.object(budget,'lock',lambda _: __import__('contextlib').nullcontext()), \
                patch.object(api.time,'sleep'):
            with patch.object(api,'run',return_value=SimpleNamespace(returncode=1,stdout='000')) as run:
                with self.assertRaises(RuntimeError):
                    api.http_json('https://fixture.invalid',lane='gemini',prompt='fixture',max_tokens=10)
                self.assertEqual(run.call_count,3)
                self.assertEqual(admission.status(self.root,'test')['direct_attempts'],3)
                self.assertGreater(admission.status(self.root,'test')['reserved_api_usd'],0)
            config=json.loads(self.path.read_text());config['phase']='qualification';admission.atomic(self.path,config)
            def transport(argv,**kwargs):
                Path(argv[argv.index('-o')+1]).write_text(json.dumps({'usageMetadata':{'promptTokenCount':10}}))
                return SimpleNamespace(returncode=0,stdout='200')
            with patch.object(api,'run',side_effect=transport) as run, patch.object(budget,'settle',side_effect=OSError('fixture ledger failure')):
                with self.assertRaises(budget.BudgetExceeded):
                    api.http_json('https://fixture.invalid',lane='gemini',prompt='fixture',max_tokens=10)
                self.assertEqual(run.call_count,1)
                self.assertEqual(admission.status(self.root,'test')['direct_attempts'],4)


if __name__ == '__main__':
    unittest.main()
