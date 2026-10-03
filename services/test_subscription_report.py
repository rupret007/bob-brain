"""Isolated bounded report completion and negative controls; never a live CLI."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import web_dispatch
import subscription_report as worker
import report_artifacts
import report_contract
import project_context
import task_queue
from command import run_input

ANSWER = ('# Readiness\nThe supplied module supports durable assignments. '
          'This is static evidence, not a claim that production was checked. [source:webchat/app.py]\n\n'
          'Priority: verify one completed report and its returned artifact before expanding routing. '
          'Keep current deployment until qualification passes. The next action is to test restart recovery. '
          'Pending decision: whether the sample covers the owner’s daily work. Limits: no live test results were supplied.')


def event_result():
    rows = [dict(type='system', subtype='init', tools=[], mcp_servers=[], slash_commands=[], apiKeySource='none',model='claude-opus-fixture'),
            dict(type='assistant', message=dict(model='claude-opus-fixture', content=[dict(type='text', text=ANSWER)])),
            dict(type='result', subtype='success', is_error=False, num_turns=1, result=ANSWER,
                 permission_denials=[], modelUsage={'claude-opus-fixture': {'inputTokens':123,'outputTokens':89}},
                 usage={'input_tokens':123,'output_tokens':89}, total_cost_usd=.04)]
    return rows


def process(rows=None, code=0):
    return subprocess.CompletedProcess(['fixture'], code, '\n'.join(json.dumps(r) for r in (rows or event_result())), '')


class SubscriptionReportTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup); self.root = Path(temp.name)
        project_context.change(self.root, 'Web Bob', [dict(operation='set', id='priority',kind='priority',value='Reliability first')],
            dict(conversation_id='chat',request_id='memory',message_id='m',sha256='a'*64),expected_revision=0)
        self.sources = [dict(path='webchat/app.py', text='def readiness(): return "evidence"\n')]
        self.contract = report_contract.build(conversation_id='chat', request_id='request', prompt='Inspect supplied evidence',
            worker='claude', goal_id='project-web-bob', goal_revision=1,
            input_manifest=[dict(path=s['path'],sha256=hashlib.sha256(s['text'].encode()).hexdigest(),
                                bytes=len(s['text'].encode()),source_type='code') for s in self.sources],
            expected_deliverable='A useful readiness report')
        report_artifacts.save_inputs(self.root,self.contract,self.sources)
        row=task_queue.enqueue(self.root,'chat','request',self.contract['scope'],worker='claude',kind='bounded-report',
                               attempt_limit=1,report_contract=self.contract)
        self.row=task_queue.claim(self.root,'claude',identifier=row['id'])
        self.token=self.row['claim_token']
        for name, value in [('subscription',dict(auth_mode='claude.ai',plan='pro',actual_incremental_charge_usd=None)),
                             ('budget.check',{}),('budget.record_cli',None)]:
            stub=patch('subscription_report.'+name,return_value=value); stub.start(); self.addCleanup(stub.stop)

    def execute(self, output=None):
        with patch.object(worker,'run_input',return_value=output or process()) as generation:
            result=worker.execute(self.root,self.row,self.token,lambda s:s)
        return result,generation

    def test_one_process_verified_artifact_and_truthful_model_provenance(self):
        result,generation=self.execute()
        self.assertEqual(result,0); self.assertEqual(generation.call_count,1)
        argv=generation.call_args.args[0]
        self.assertIn('--restricted',argv); self.assertIn('--safe-mode',argv)
        self.assertNotIn('--dangerously-bypass-approvals-and-sandbox',argv)
        self.assertEqual(argv[argv.index('--tools')+1],'')
        self.assertEqual(argv[argv.index('--effort')+1],'high')
        row=task_queue.tasks(self.root)[self.row['id']]
        self.assertEqual((row['status'],row['attempts'],row['report_checkpoint']),('succeeded',1,'artifact_verified'))
        self.assertEqual(report_artifacts.read(self.root,self.contract['output_relative']),(ANSWER+'\n').encode())
        self.assertEqual(row['acceptance']['model_evidence']['observed_models'],['claude-opus-fixture'])
        self.assertIsNone(row['acceptance']['model_evidence']['actual_charge_usd'])

    def test_cancelled_claim_never_generates_or_publishes(self):
        task_queue.cancel_user_task(self.root,'chat',self.row['id'])
        result,generation=self.execute()
        generation.assert_not_called()
        self.assertFalse((self.root/self.contract['output_relative']).exists())

    def test_source_tampering_and_stale_project_revision_stop_before_generation(self):
        path=self.root/report_artifacts.input_path(self.contract)
        original=path.read_text(); data=json.loads(original); data['sources'][0]['text']='unassigned'
        path.write_text(json.dumps(data))
        with patch.object(worker,'run_input') as generation,self.assertRaises(ValueError):
            worker.execute(self.root,self.row,self.token,lambda s:s)
        generation.assert_not_called()
        path.write_text(original)
        project_context.change(self.root,'Web Bob',[dict(operation='set',id='priority',kind='priority',value='Delivery first')],
            dict(conversation_id='chat',request_id='correct',message_id='m2',sha256='b'*64),expected_revision=1)
        with patch.object(worker,'run_input') as generation,self.assertRaisesRegex(RuntimeError,'context changed'):
            worker.execute(self.root,self.row,self.token,lambda s:s)
        generation.assert_not_called()

    def test_context_change_or_cancel_during_generation_prevents_publication(self):
        def cancelled(*args,**kwargs):
            task_queue.cancel_user_task(self.root,'chat',self.row['id']); return process()
        with patch.object(worker,'run_input',side_effect=cancelled):
            self.assertEqual(worker.execute(self.root,self.row,self.token,lambda s:s),1)
        self.assertFalse((self.root/self.contract['output_relative']).exists())

    def test_exhausted_deadline_or_budget_never_generates(self):
        with patch.object(worker,'run_input') as generation,patch.object(worker.budget,'check',side_effect=RuntimeError('budget stop')):
            with self.assertRaisesRegex(RuntimeError,'budget stop'):
                worker.execute(self.root,self.row,self.token,lambda s:s)
        generation.assert_not_called()
        expired=dict(self.row,execution_deadline=time.time()-1)
        with patch.object(worker,'run_input') as generation,self.assertRaisesRegex(RuntimeError,'deadline expired'):
            worker.execute(self.root,expired,self.token,lambda s:s)
        generation.assert_not_called()

    def test_interrupted_publication_cannot_complete_or_retry_a_second_attempt(self):
        with patch.object(report_artifacts,'put_once',side_effect=OSError('interrupted')),self.assertRaises(OSError):
            self.execute()
        self.assertNotEqual(task_queue.tasks(self.root)[self.row['id']]['status'],'succeeded')
        task_queue.transition(self.root,self.row['id'],self.token,'retry',error='Interrupted write')
        self.assertEqual(task_queue.tasks(self.root)[self.row['id']]['status'],'failed')
        self.assertIsNone(task_queue.claim(self.root,'claude',identifier=self.row['id'],now=time.time()+100))

    def test_unassigned_citations_and_tool_events_are_not_accepted(self):
        cases=[]
        rows=event_result(); rows[0]['tools']=['Bash']; cases.append(rows)
        rows=event_result(); rows[0]['apiKeySource']='ANTHROPIC_API_KEY'; cases.append(rows)
        rows=event_result(); rows[1]['message']['content']=[dict(type='tool_use',name='Bash')]; cases.append(rows)
        rows=event_result(); rows[1]['parent_tool_use_id']='agent'; cases.append(rows)
        rows=event_result(); rows[-1]['num_turns']=2; cases.append(rows)
        rows=event_result(); rows[-1]['modelUsage']['claude-sonnet-fixture']={}; cases.append(rows)
        rows=event_result(); rows[-1]['permission_denials']=['tool']; cases.append(rows)
        rows=event_result(); rows.append(copy.deepcopy(rows[-1])); cases.append(rows)
        for rows in cases:
            with self.subTest(rows=rows),self.assertRaises(RuntimeError):worker.parse_events(process(rows))
        with self.assertRaises(RuntimeError):worker.check_report(ANSWER+' [source:unassigned.txt]',self.contract)

    def test_installed_cli_metadata_preserves_restricted_one_turn_result(self):
        rows=event_result()
        rows[1]['message']['content'].insert(0,dict(type='redacted_thinking',data='opaque-uninterpreted-fixture'))
        rows.insert(1,dict(type='system',subtype='thinking_tokens',estimated_tokens=20,estimated_tokens_delta=5))
        rows.insert(2,dict(type='rate_limit_event',rate_limit_info=dict(status='allowed_warning',
            utilization=1.1,isUsingOverage=False,overageDisabledReason='org_level_disabled')))
        rows[-1]['subagent_stats']=dict(spawned=0,requested=dict(background=0,foreground=0,unset=0),
            started_in_background=0,max_depth=0,spawned_by_subagents=0,completed=0,failed=0,
            killed=dict(parent=0,user=0,system=0),refused=dict(depth_limit=0,concurrency_limit=0,budget=0),by_type={})
        answer,evidence,_=worker.parse_events(process(rows))
        self.assertEqual(answer,ANSWER)
        self.assertEqual(evidence['init_model'],'claude-opus-fixture')
        self.assertEqual(evidence['rate_limit_observations'][0]['utilization'],1.1)
        self.assertIsNone(evidence['actual_charge_usd'])
        for stats in (dict(spawned=1),dict(requested=dict(background=1)),dict(spawned=False),dict(unrecognized=0)):
            bad=copy.deepcopy(rows);bad[-1]['subagent_stats']=stats
            with self.subTest(stats=stats),self.assertRaises(RuntimeError):worker.parse_events(process(bad))

    def test_failed_validation_retains_decoded_usage_without_acceptance(self):
        rows=event_result();rows[0]['tools']=['Bash'];events=[]
        with self.assertRaises(RuntimeError):worker.parse_events(process(rows),events=events)
        self.assertEqual(events[-1]['total_cost_usd'],.04)
        self.assertEqual(events[-1]['modelUsage'],rows[-1]['modelUsage'])
        rows=event_result();rows[0]['model']='claude-sonnet-fixture'
        with self.assertRaises(RuntimeError):worker.parse_events(process(rows))

    def test_private_artifacts_refuse_links_and_conflicting_duplicate_content(self):
        output=self.contract['output_relative']
        report_artifacts.put_once(self.root,output,b'one')
        report_artifacts.put_once(self.root,output,b'one')
        with self.assertRaises(ValueError):report_artifacts.put_once(self.root,output,b'two')
        target=self.root/output; target.unlink(); target.symlink_to(self.root/report_artifacts.input_path(self.contract))
        with self.assertRaises(OSError):report_artifacts.put_once(self.root,output,b'one')
        with self.assertRaises(ValueError):report_artifacts.put_once(self.root,'../outside',b'one')

    def test_crash_between_link_publication_and_unlink_recovers_only_owned_pending_link(self):
        output=self.contract['output_relative']; target=self.root/output
        target.parent.mkdir(parents=True)
        pending=target.parent/('.pending-'+'a'*32)
        pending.write_bytes(b'complete bytes'); os.link(pending,target)
        self.assertEqual(target.stat().st_nlink,2)
        report_artifacts.put_once(self.root,output,b'complete bytes')
        self.assertFalse(pending.exists())
        self.assertEqual(report_artifacts.read(self.root,output),b'complete bytes')
        other=target.parent/'unrelated'; os.link(target,other)
        with self.assertRaises(ValueError):report_artifacts.put_once(self.root,output,b'complete bytes')
        self.assertTrue(other.exists())

    def test_blocking_io_after_generation_never_refunds_attempt(self):
        import contextlib
        import dispatch_worker
        def ran_then_failed(root,row,token,redact):
            task_queue.transition(root,row['id'],token,'executing')
            raise BlockingIOError('After generation')
        with patch.object(dispatch_worker,'ROOT',self.root),patch.object(dispatch_worker,'CONDUCTOR',self.root/'conductor'), \
                patch.object(dispatch_worker,'lock',side_effect=lambda *a,**k:contextlib.nullcontext()), \
                patch.object(dispatch_worker,'slot',side_effect=lambda *a,**k:contextlib.nullcontext()), \
                patch.object(dispatch_worker,'task_repository',return_value=('WebBob',self.root)), \
                patch.object(worker,'execute',side_effect=ran_then_failed):
            dispatch_worker.execute(self.row['id'],self.token)
        failed=task_queue.tasks(self.root)[self.row['id']]
        self.assertEqual((failed['status'],failed['attempts']),('failed',1))
        self.assertIsNone(task_queue.claim(self.root,'claude',identifier=self.row['id'],now=time.time()+100))


class BoundedCommandTests(unittest.TestCase):
    def test_evidence_is_stdin_and_output_is_bounded(self):
        result=run_input([sys.executable,'-c','import sys; print(sys.stdin.read().upper())'],'private evidence',timeout=5)
        self.assertEqual(result.stdout,'PRIVATE EVIDENCE\n')
        with self.assertRaisesRegex(RuntimeError,'output exceeded'):
            run_input([sys.executable,'-c','print("x"*10000)'],'input',timeout=5,max_output_bytes=100)

    def test_hung_command_is_killed_within_deadline(self):
        start=time.monotonic()
        with self.assertRaises(subprocess.TimeoutExpired):
            run_input([sys.executable,'-c','import time; time.sleep(10)'],'input',timeout=.05)
        self.assertLess(time.monotonic()-start,3)
