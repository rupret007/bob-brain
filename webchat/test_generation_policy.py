"""Authenticated turn identity and held work retain server budget attribution."""
import json
import time
import uuid

from app import Chat
from failover import AllDown
from test_webbob_replyq_1856 import SessionFixture
import generation_budget
import task_queue


class BindingTests(SessionFixture):
    def test_held_report_preserves_product_stage_and_stale_stage_never_consumes_attempt(self):
        self.policy()
        with generation_budget.locked(self.root,'proof') as (path,data):
            data.update(stage_required=True,active_stage='product',stages={'product':dict(status='active',
                source_sha='fixture',deadline=time.time()+300,max_http_attempts=9)})
            generation_budget.atomic(path,data)
        self.send('For the Web Bob project, remember the priority: reliable daily assistance.')
        self.send('Hold all work')
        self.send('Create a read-only Web Bob readiness report')
        contract=self.chat.get(self.identifier)['held_job']['report_contract']
        self.assertEqual(contract['generation_binding']['stage_id'],'product')
        self.chat.close();self.chat=Chat(self.folder,self.root,self.fake)
        self.send('Resume')
        row=task_queue.tasks(self.root)[contract['task_id']]
        self.assertEqual(row['report_contract'],contract)
        with generation_budget.locked(self.root,'proof') as (path,data):
            data['stages']['product']['status']='finished';data['active_stage']=None
            generation_budget.atomic(path,data)
        self.assertIsNone(task_queue.claim(self.root,'claude',identifier=row['id']))
        saved=task_queue.tasks(self.root)[row['id']]
        self.assertEqual(saved['attempts'],0)
        self.assertIn('stage',saved['error'])

    def policy(self,identifier='proof'):
        directory=self.root/'conductor/state/generation-budgets';directory.mkdir(parents=True,exist_ok=True)
        generation_budget.atomic(directory/(identifier+'.json'),dict(schema=1,id=identifier,status='active',
            deadline=time.time()+600,phase='product',providers=['gemini','claude'],chat_providers=['gemini'],calls={},
            limits=dict(api_usd=1,reserve_usd=0,direct_attempts=4,reserve_attempts=0,native_invocations=2,product_jobs=2)))
        path=self.root/'conductor/state/generation-policy.json'
        path.write_text(json.dumps(dict(budget_id=identifier,accounting_root=str(self.root),purpose='product')))
        return path

    def test_same_request_replay_cannot_change_provider_exclusivity(self):
        self.policy();rid=str(uuid.uuid4())
        self.chat.submit(self.identifier,'A brief greeting.',rid,provider='gemini',provider_mode='only',actor='fixture-owner')
        info=self.chat.workers.get(self.identifier)
        if info:info['thread'].join(5)
        value=self.chat.get(self.identifier)
        user=next(m for m in value['messages'] if m.get('request_id')==rid and m['role']=='user')
        self.assertEqual(user['_generation']['id'],'proof')
        before=len(self.fake.calls)
        self.chat.submit(self.identifier,'A brief greeting.',rid,provider='gemini',provider_mode='only',actor='fixture-owner')
        self.assertEqual(len(self.fake.calls),before)
        with self.assertRaises(Exception):
            self.chat.submit(self.identifier,'A brief greeting.',rid,provider='gemini',provider_mode='fallback')
        self.assertNotIn('_generation',self.chat.public(value)['messages'][-2])

    def test_pre_policy_waiting_turn_binds_before_resumed_generation(self):
        original=self.fake.reply
        def down(*args):raise AllDown([],time.time()-1,'saved prompt')
        self.fake.reply=down
        rid=str(uuid.uuid4());self.chat.submit(self.identifier,'Explain a tide.',rid)
        info=self.chat.workers.get(self.identifier)
        if info:info['thread'].join(5)
        self.assertEqual(self.chat.get(self.identifier)['messages'][-1]['status'],'waiting')
        self.policy();self.fake.reply=original
        self.chat.retry_queued()
        info=self.chat.workers.get(self.identifier)
        if info:info['thread'].join(5)
        user=self.fake.calls[-1]['messages'][-2]
        self.assertEqual(user['_generation']['id'],'proof')
        self.assertEqual(user['_generation']['request_id'],rid)

    def test_exhausted_request_is_terminal_across_queue_poll_and_restart(self):
        self.policy()
        with generation_budget.locked(self.root,'proof') as (path,data):
            data['limits']['total_http_attempts']=10
            generation_budget.atomic(path,data)
        attempts=[]
        def down(conversation,*args):
            user=next(m for m in reversed(conversation['messages']) if m['role']=='user')
            env=generation_budget.bound_environment(user['_generation'],{})
            for _ in range(3):attempts.append(generation_budget.reserve('gemini',.01,env=env))
            raise AllDown([],time.time()-1,'saved prompt')
        self.fake.reply=down
        answer=self.send('Explain ocean tides.')
        self.assertEqual(answer['status'],'error')
        self.assertIn('automatic retry is stopped',answer['content'])
        self.chat.retry_queued()
        self.chat.close();self.chat=Chat(self.folder,self.root,self.fake)
        self.chat.retry_queued()
        self.assertEqual(len(attempts),3)
        self.assertEqual(self.chat.get(self.identifier)['messages'][-1]['status'],'error')

    def test_held_report_keeps_original_budget_when_current_policy_changes(self):
        self.policy('first')
        self.send('For the Web Bob project, remember the priority: reliable daily assistance.')
        self.send('Hold all work')
        self.send('Create a read-only Web Bob readiness report')
        contract=self.chat.get(self.identifier)['held_job']['report_contract']
        self.assertEqual(contract['generation_binding']['id'],'first')
        self.policy('second')
        self.chat.close();self.chat=Chat(self.folder,self.root,self.fake)
        self.send('Resume')
        row=task_queue.tasks(self.root)[contract['task_id']]
        self.assertEqual(row['report_contract']['generation_binding']['id'],'first')
        self.assertEqual(row['report_contract']['contract_sha256'],contract['contract_sha256'])

    def test_expired_and_malformed_policy_preserve_hold_cancel_and_context_controls(self):
        path=self.policy()
        self.send('For the Web Bob project, remember the priority: reliable daily assistance.')
        self.send('Hold all work')
        self.send('Create a read-only Web Bob readiness report')
        budget=self.root/'conductor/state/generation-budgets/proof.json'
        value=json.loads(budget.read_text());value['deadline']=time.time()-1;generation_budget.atomic(budget,value)
        answer=self.send('Cancel task')
        self.assertIn('Cancelled',answer['content'])
        self.assertFalse(task_queue.tasks(self.root))
        path.write_text('{malformed')
        answer=self.send('Hold all work')
        self.assertEqual(answer['provider'],'dispatcher')
        answer=self.send('For the Web Bob project, remember the priority: delivery reliability comes first.')
        self.assertEqual(answer['status'],'done')
        before=len(self.fake.calls)
        answer=self.send('Explain ocean tides.')
        self.assertEqual(answer['status'],'error')
        self.assertEqual(len(self.fake.calls),before)

    def test_generic_executor_cannot_escape_normal_policy_via_detached_worker(self):
        self.policy()
        for prompt in ('Have Codex fix the Web Bob sidebar.', 'Use Gemini and MiniMax for ongoing Web Bob jobs'):
            answer=self.send(prompt)
            self.assertFalse(task_queue.tasks(self.root))
            self.assertNotIn('I queued',answer['content'])
        self.assertFalse(self.fake.calls)

    def test_legacy_migration_retains_receipt_without_blocking_startup(self):
        self.send('What is two plus two?')
        value=self.chat.get(self.identifier)
        message=value['messages'][-1]
        message['action_card']=dict(state='queued',queue_id='legacy-fixture.md')
        self.chat.save(value)
        folder=self.root/'next-prompts';folder.mkdir(exist_ok=True)
        (folder/'legacy-fixture.md').write_text('## Task\n\nReview source evidence.\n')
        self.policy()
        self.chat.close();self.chat=Chat(self.folder,self.root,self.fake)
        saved=self.chat.get(self.identifier)['messages'][-1]
        self.assertEqual(saved['action_card']['queue_id'],'legacy-fixture.md')
        self.assertIn('budget-bound',saved['action_card']['admission_block'])
        self.assertFalse(task_queue.tasks(self.root))
        self.assertEqual(self.send('Hold all work')['status'],'done')
