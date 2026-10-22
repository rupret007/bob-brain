"""Report admission and ownership controls; no providers or live queue."""
import copy
import json
import tempfile
from pathlib import Path
import unittest

import web_dispatch
from web_dispatch import task_queue
import report_contract as contract


class ContractTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        self.prompt='Inspect the supplied Web Bob evidence and return a readiness report.'
        self.value=contract.build(conversation_id='chat',request_id='request',prompt=self.prompt,worker='codex',
            goal_id='project-web-bob',goal_revision=3,
            input_manifest=[dict(path='webchat/app.py',sha256='a'*64,bytes=1200,source_type='code')],
            expected_deliverable='A source-backed readiness report with two prioritized findings and limits.')

    def enqueue(self,value=None,**extra):
        args=dict(worker='codex',kind='bounded-report',attempt_limit=1,
                  report_contract=self.value if value is None else value)
        args.update(extra)
        return task_queue.enqueue(self.root,'chat','request',self.prompt,**args)

    def resigned(self,field,value):
        changed=copy.deepcopy(self.value);changed[field]=value
        changed['contract_sha256']=contract.digest({k:v for k,v in changed.items() if k!='contract_sha256'})
        return changed

    def test_first_event_binds_scope_inputs_output_attempt_and_owner(self):
        row=self.enqueue()
        first=json.loads((self.root/'conductor/state/queue.jsonl').read_text().splitlines()[0])
        self.assertEqual(first['report_contract'],self.value)
        self.assertEqual((first['attempt_limit'],first['max_attempts']),(1,1))
        self.assertEqual(row['id'],self.value['task_id'])
        self.assertEqual(self.enqueue(),row)
        self.assertEqual(len((self.root/'conductor/state/queue.jsonl').read_text().splitlines()),1)

    def test_unknown_effect_bad_digest_wrong_scope_and_unsafe_paths_never_enqueue(self):
        cases=[('allowed_effects',['send_text']),('scope','Different work'),('output_relative','../outside.md'),
               ('timeout_seconds',901),('timeout_seconds',True),('goal_revision',True),('version',True),
               ('permitted_workers',['codex','gemini']),('authorization_request_id','other'),
               ('input_manifest',[dict(path='../secrets',sha256='a'*64,bytes=5,source_type='code')]),
               ('input_manifest',[dict(path='app.py',sha256='a'*64,bytes=120001,source_type='code')])]
        for field,value in cases:
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):self.enqueue(self.resigned(field,value))
        bad=copy.deepcopy(self.value);bad['contract_sha256']='b'*64
        with self.assertRaises(ValueError):self.enqueue(bad)
        self.assertFalse(task_queue.tasks(self.root))

    def test_contract_cannot_attach_to_other_work_or_widen_existing_identity(self):
        for extra in (dict(kind='inspection'),dict(attempt_limit=2),dict(group_id='group',group_size=2,group_index=0),
                      dict(local_suite='webchat/test.py'),dict(publish_project='Web Bob'),dict(worker='gemini')):
            with self.subTest(extra=extra),self.assertRaises(ValueError):self.enqueue(**extra)
        self.enqueue()
        for field,value in [('goal_revision',4),('timeout_seconds',800),('expected_deliverable','Another report')]:
            with self.assertRaises(ValueError):self.enqueue(self.resigned(field,value))
        self.assertEqual(len(task_queue.tasks(self.root)),1)

    def test_pinned_worker_is_enforced_at_scheduler_and_claim_even_with_fallback(self):
        row=self.enqueue()
        health={w:dict(state='ready',budget=dict(tier='normal')) for w in task_queue.MODEL_WORKERS}
        health['codex']['state']='unavailable'
        self.assertEqual(web_dispatch.candidates(row,health),[])
        for worker in ('claude','gemini','cursor'):
            self.assertIsNone(task_queue.claim(self.root,worker,identifier=row['id'],allow_fallback=True))
        health['codex']['state']='ready'
        self.assertEqual(web_dispatch.candidates(row,health),['codex'])
        claimed=task_queue.claim(self.root,'codex',identifier=row['id'],now=100)
        self.assertEqual(claimed['execution_deadline'],1000)
        self.assertEqual(claimed['report_contract'],self.value)

    def test_failure_consumes_only_attempt_and_stale_token_cannot_complete(self):
        row=self.enqueue();claimed=task_queue.claim(self.root,'codex',identifier=row['id'],now=100)
        failed=task_queue.transition(self.root,row['id'],claimed['claim_token'],'retry',now=101,error='timeout')
        self.assertEqual(failed['status'],'failed')
        self.assertEqual(failed['attempts'],1)
        self.assertIsNone(task_queue.claim(self.root,'codex',identifier=row['id'],now=200))
        self.assertIsNone(task_queue.transition(self.root,row['id'],claimed['claim_token'],'succeeded',now=102,result='late'))

    def test_cancelled_contract_cannot_be_transferred_to_another_worker(self):
        row=self.enqueue();claimed=task_queue.claim(self.root,'codex',identifier=row['id'])
        task_queue.cancel_user_task(self.root,'chat',row['id'])
        self.assertIsNone(task_queue.transition(self.root,row['id'],claimed['claim_token'],'succeeded',result='late'))
        self.assertIsNone(task_queue.claim(self.root,'claude',identifier=row['id'],allow_fallback=True))


if __name__=='__main__':unittest.main()
