"""Isolated release-gate and rollback checks; never touch live services."""
import contextlib
import errno
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

TEST_TIP = "1" * 40
HERE = Path(__file__).resolve().parent
WT = HERE.parent
spec = importlib.util.spec_from_file_location('deploy_texting_2256', HERE / 'deploy_texting_2256.py')
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)


class TextingReleaseGuards(unittest.TestCase):
    def exercise(self, reviews_pass, completion_failure=False, screen_failure=False, version_failure=False, restart_failure=False, disk_failure=None):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as folder, patch.dict(os.environ):
            root = Path(folder)
            candidate, old = root / 'candidate', root / 'old'
            for p in (root/'conductor/state', root/'conductor/reviews', root/'conductor/webchat', root/'rollbacks', candidate/'webchat/fixtures', candidate/'services/fixtures', old):
                p.mkdir(parents=True)
            reviews = root/'conductor/reviews'
            (root/'conductor/webchat/.password').write_text('synthetic-password')
            (root/'conductor/webchat/.public-origin').write_text('https://synthetic.example')
            (old/'webbob-build.json').write_text(json.dumps(dict(sha=deploy.PREVIOUS)))
            for name in ('webchat','dispatch'):
                (root/'conductor/state'/(name+'-code-root')).write_text(str(old))
            (candidate/'webchat/fixtures/texting_diagdump_0810.json').write_text((WT/'webchat/fixtures/texting_diagdump_0810.json').read_text())
            (candidate/'services/fixtures/texting_verification_0810.json').write_text((WT/'services/fixtures/texting_verification_0810.json').read_text())
            (candidate/'services/fixtures/texting_jobcompletion_1035.json').write_text((WT/'services/fixtures/texting_jobcompletion_1035.json').read_text())
            (candidate/'services/fixtures/texting_jobcompletion_1107.json').write_text((WT/'services/fixtures/texting_jobcompletion_1107.json').read_text())
            (candidate/'services/fixtures/texting_jobcompletion_1403.json').write_text((WT/'services/fixtures/texting_jobcompletion_1403.json').read_text())
            (candidate/'services/fixtures/texting_action_plan_1605.json').write_text((WT/'services/fixtures/texting_action_plan_1605.json').read_text())
            (candidate/'services/fixtures/texting_regression_drafts_1658.json').write_text((WT/'services/fixtures/texting_regression_drafts_1658.json').read_text())
            (candidate/'services/fixtures/texting_minimax_probe_2256.json').write_text((WT/'services/fixtures/texting_minimax_probe_2256.json').read_text())
            (candidate/'services/fixtures/texting_guard_consistency_1803.json').write_text((WT/'services/fixtures/texting_guard_consistency_1803.json').read_text())
            (reviews/'TEXTING-LIVE-2256.md').write_text('GATE: BOTH_PASS tip='+TEST_TIP[:7])
            context = reviews / 'context.md'
            context.write_text('Reviewed synthetic context')
            context_hash = hashlib.sha256(context.read_bytes()).hexdigest()
            outputs = {}
            for name in ('gemini','minimax'):
                output = reviews/(name+'.md')
                output.write_text('VERDICT: PASS\n')
                outputs[name] = dict(sha=TEST_TIP, attempt=14, context=str(context), context_sha256=context_hash, exit=0,verdict='PASS',output=str(output),output_sha256=hashlib.sha256(output.read_bytes()).hexdigest())
            gate = dict(context_sha256=context_hash, sha=TEST_TIP,attempt=14,gate='BOTH_PASS' if reviews_pass else 'NOT_BOTH_PASS',reviews=outputs)
            (reviews/'TEXTING-LIVE-2256.json').write_text(json.dumps(gate))
            (reviews/'TEXTING-CLEAN-MERGE-2256.json').write_text(json.dumps(dict(merge_sha='merge-sha')))
            log = reviews/'test.log'
            log.write_text('OK')
            results = {name:dict(exit=0,skipped=0,log=str(log),log_sha256=hashlib.sha256(log.read_bytes()).hexdigest())
                       for name in ('webchat','services','eval','browser')}
            (reviews/'TEXTING-2256-tests.json').write_text(json.dumps(dict(sha=TEST_TIP,suite_exit=0,eval_exit=0,all_pass=True,results=results,eval=dict(passed=100,total=100))))
            (candidate/'reviews').mkdir()
            scripts = {}
            for name in deploy.REQUIRED_SCRIPTS:
                data = (HERE/name).read_bytes()
                (candidate/'reviews'/name).write_bytes(data)
                scripts[name] = hashlib.sha256(data).hexdigest()
            (reviews/'TEXTING-2256-runner-checks.json').write_text(json.dumps(dict(sha=TEST_TIP,all_pass=True,log=str(log),log_sha256=hashlib.sha256(log.read_bytes()).hexdigest(),scripts=scripts)))
            def command(argv):
                if argv[0]=='gh':
                    return json.dumps(dict(isDraft=True,state='OPEN',headRefOid=TEST_TIP,baseRefName='draft/webbob-clean-0927'))
                if 'rev-parse' in argv: return TEST_TIP
                if 'ls-remote' in argv: return TEST_TIP+' refs/heads/'+deploy.BRANCH+'\nmerge-sha refs/heads/draft/webbob-clean-0927'
                if 'branch' in argv: return deploy.BRANCH
                return ''
            client=MagicMock()
            client.url='http://127.0.0.1:8787'
            client.call.return_value = {}
            restarts = []
            real_atomic = deploy.atomic_json
            failed_io = False
            def checkpoint(path, value):
                nonlocal failed_io
                if disk_failure == 'checkpoint' and value.get('status') == 'LIVE_REPLAY':
                    failed_io = True
                if failed_io:
                    raise OSError(errno.ENOSPC, 'synthetic persistent evidence ENOSPC')
                return real_atomic(path, value)
            def capacity(root, candidate, stage):
                if disk_failure == stage:
                    raise OSError(errno.ENOSPC, '5 GiB free-space gate failed at ' + stage)
                return dict(stage=stage, minimum_free_bytes=8 * 1024**3)

            def restart_release(root, pins, **kwargs):
                restarts.append(pins)
                for name, path in pins.items():
                    (root/'conductor/state'/(name+'-code-root')).write_text(str(path))
                if restart_failure and len(restarts) == 1:
                    raise RuntimeError('synthetic unhealthy restart')
                return dict(other_screens_unchanged=not (screen_failure and len(restarts)==1))
            def pair(root, expected):
                if version_failure and expected == TEST_TIP:
                    raise RuntimeError('Local/public version mismatch: stale public a777736')
                return {name:dict(sha=expected) for name in ('local','public')}
            def smoke(client, root, evidence, save):
                if completion_failure or disk_failure in ('checkpoint', 'LIVE_REPLAY'):
                    evidence['texting_smoke'] = dict(all_pass=True)
                else:
                    raise RuntimeError('synthetic smoke failure')
            args=['deploy_texting_2256.py','--root',str(root),'--candidate',str(candidate),'--attempt','14','--tip',TEST_TIP,'--draft-pr','https://example.org/pr']
            with patch('sys.argv',args), patch.object(deploy,'run',side_effect=command), \
                 patch.object(deploy,'CANDIDATE_CODE',candidate), \
                 patch.object(deploy,'require_disk_space',side_effect=capacity), \
                 patch.object(deploy,'atomic_json',side_effect=checkpoint), \
                 patch('texting_deploy_record.RECOVERY_BYTES',1024**2), \
                 patch.object(deploy,'version_pair',side_effect=pair), \
                 patch.object(deploy,'check_lane_isolation',return_value={}), \
                 patch.object(deploy,'verify_clean_merge',return_value=dict(ancestor=True,tree_equal=True)), \
                 patch.object(deploy,'verify_worker_probes',return_value=dict(all_pass=True)), \
                 patch.object(deploy,'Client',return_value=client), patch.object(deploy,'scoped_sessions',return_value=([], {})), \
                 patch.object(deploy,'restart',side_effect=restart_release) as restart, \
                 patch.object(deploy,'texting_smoke',side_effect=smoke) as smoking, \
                 patch.object(deploy,'verify_executions',side_effect=RuntimeError('synthetic incomplete report')), \
                 contextlib.redirect_stdout(io.StringIO()):
                client.new.return_value = '1035-regression-conversation'
                self.assertEqual(deploy.main(),1)
            evidence=json.loads((reviews/'WEBBOB-TEXTING-DEPLOYMENT-0927-attempt14.json').read_text())
            self.assertFalse(evidence['all_pass'])
            self.assertNotIn('synthetic-password',json.dumps(evidence))
            if disk_failure == 'BEFORE_ACTIVATION':
                restart.assert_not_called()
                self.assertNotIn('activated', evidence)
                self.assertIn('5 GiB free-space gate', evidence['failure'])
            elif reviews_pass:
                self.assertEqual(restart.call_count,2)
                self.assertTrue(evidence['rolled_back'])
                self.assertEqual(evidence['restored_version']['sha'],deploy.PREVIOUS)
                self.assertEqual(evidence['restored_public_version']['sha'],deploy.PREVIOUS)
                if version_failure or restart_failure or screen_failure:
                    smoking.assert_not_called()
                expected_failure = ('synthetic persistent evidence ENOSPC' if disk_failure == 'checkpoint' else
                                    '5 GiB free-space gate' if disk_failure else
                                    'synthetic unhealthy restart' if restart_failure else
                                    'Local/public version mismatch' if version_failure else
                                    'Unrelated screens changed during restart' if screen_failure else
                                    'synthetic incomplete report' if completion_failure else 'synthetic smoke failure')
                self.assertIn(expected_failure,evidence['failure'])
                if completion_failure:
                    self.assertEqual(set(evidence['cancelled_replay_jobs']), {
                        evidence['jobcompletion_regression']['job_id'], evidence['action_plan_regression']['job_id'], evidence['regression_drafts_regression']['job_id']})
            else:
                restart.assert_not_called()
                self.assertNotIn('activated',evidence)
                self.assertIn('review SHA/gate mismatch',evidence['failure'])

    def test_disk_shortfall_before_activation_never_restarts(self):
        self.exercise(True, disk_failure='BEFORE_ACTIVATION')

    def test_live_replay_disk_shortfall_rolls_back(self):
        self.exercise(True, disk_failure='LIVE_REPLAY')

    def test_persistent_checkpoint_enospc_cannot_block_rollback(self):
        self.exercise(True, disk_failure='checkpoint')

    def test_stale_public_version_never_runs_smoke_and_rolls_back(self):
        self.exercise(True, version_failure=True)

    def test_unhealthy_restart_rolls_back_even_after_pins_change(self):
        self.exercise(True, restart_failure=True)

    def test_bad_fresh_review_gate_never_activates(self):
        self.exercise(False)

    def test_failed_smoke_restores_and_verifies_a777736(self):
        self.exercise(True)

    def test_durable_screen_failure_restores_and_verifies_a777736(self):
        self.exercise(True, screen_failure=True)

    def test_rollback_revokes_extra_1035_regression_conversation(self):
        self.assertEqual(deploy.replay_conversations(dict(sessions=[dict(replay_id="frozen-replay")],
            jobcompletion_regression=dict(conversation_id="1035-replay"),
            action_plan_regression=dict(conversation_id="f2c47-replay"),
            regression_drafts_regression=dict(conversation_id="20bfc-replay"))), {"frozen-replay", "1035-replay", "f2c47-replay", "20bfc-replay"})

    def test_failed_1035_completion_revokes_claim_and_restores_a777736(self):
        self.exercise(True, completion_failure=True)

    def test_named_regressions_require_exact_accepted_saved_deliverables(self):
        from result_acceptance import ResultRejected
        for key, name in (("jobcompletion_regression", "texting_jobcompletion_1035.json"),
                          ("action_plan_regression", "texting_action_plan_1605.json"),
                          ("regression_drafts_regression", "texting_regression_drafts_1658.json")):
            fixture = json.loads((WT/'services/fixtures'/name).read_text())
            with tempfile.TemporaryDirectory(dir='/private/tmp') as folder:
                path = Path(folder)/'result.md'
                answer = fixture['complete_answer']
                path.write_text(answer)
                row = dict(prompt=fixture['prompt'], kind=fixture['kind'], worker='minimax', model='MiniMax-M2.7',
                           status='succeeded', execution_started_at=1, result=answer,
                           result_sha256=hashlib.sha256(answer.encode()).hexdigest(), result_path=str(path),
                           acceptance=dict(accepted=True))
                evidence = {key:dict(pass_check=False)}
                deploy.record_accepted_regression(evidence, key, row, fixture)
                self.assertTrue(evidence[key]['pass_check'])
                for changed in (dict(prompt='different task'), dict(acceptance=dict(accepted=False)),
                                dict(result_sha256='bad'), dict(status='running'), dict(worker='gemini')):
                    with self.subTest(key=key, changed=changed), self.assertRaises(RuntimeError):
                        deploy.record_accepted_regression({key:dict(pass_check=False)}, key, dict(row, **changed), fixture)
                bad = fixture['answer']
                with self.assertRaises(ResultRejected):
                    deploy.record_accepted_regression({key:dict(pass_check=False)}, key,
                        dict(row, result=bad, result_sha256=hashlib.sha256(bad.encode()).hexdigest()), fixture)
                path.write_text('changed after acceptance')
                with self.assertRaisesRegex(RuntimeError, 'not saved'):
                    deploy.record_accepted_regression({key:dict(pass_check=False)}, key, row, fixture)

    def test_worker_probe_receipt_requires_unchanged_saved_and_prompt_files(self):
        from audit_texting_probes_2256 import audit_probe
        from result_acceptance import check_answer
        names = ('texting_regression_drafts_1658.json', 'texting_action_plan_1605.json',
                 'texting_jobcompletion_1107.json', 'texting_guard_consistency_1803.json')
        complete_answer = json.loads((WT / 'services/fixtures/texting_regression_drafts_1658.json').read_text())['complete_answer']
        with tempfile.TemporaryDirectory(dir='/private/tmp') as folder:
            root = Path(folder)
            reviews = root / 'conductor/reviews'
            reviews.mkdir(parents=True)
            rows = []
            for index, name in enumerate(names):
                fixture = json.loads((WT / 'services/fixtures' / name).read_text())
                report, prompt = root / f'report-{index}.md', root / f'prompt-{index}.txt'
                answer = complete_answer if index in (0, 2) else complete_answer.replace('Unblock plan:', 'Action plan:')
                report.write_text(answer + '\n')
                prompt.write_text(fixture['prompt'])
                worker = 'gemini' if index == 3 else 'minimax'
                rows.append(dict(id=f'job-{index}', prompt=fixture['prompt'], kind=fixture['kind'], worker=worker,
                    model='gemini-2.5-pro' if worker == 'gemini' else 'MiniMax-M2.7',
                    status='succeeded', execution_started_at=1, result=answer,
                    result_sha256=hashlib.sha256(answer.encode()).hexdigest(),
                    result_path=str(report), saved_report_sha256=hashlib.sha256(report.read_bytes()).hexdigest(),
                    prompt_file=str(prompt), worker_prompt_sha256=hashlib.sha256(prompt.read_bytes()).hexdigest(),
                    acceptance=dict(accepted=True, method='task-answer-review', reason='Synthetic independent acceptance'),
                    evidence=dict(head=TEST_TIP)))
            receipt = dict(sha=TEST_TIP, all_pass=True, guard_contradiction_rejects=0,
                           jobs=rows[:3], guard_consistency_job=rows[3])
            path = reviews / 'TEXTING-WORKER-2256.json'
            path.write_text(json.dumps(receipt))
            audit = audit_probe(receipt, TEST_TIP)
            audit_path = reviews / 'TEXTING-2256-probe-assertion-audit.json'
            audit_path.write_text(json.dumps(audit))
            with patch('result_acceptance.check_answer', wraps=check_answer) as semantic_check:
                verified = deploy.verify_worker_probes(root, WT, TEST_TIP)
                self.assertEqual(verified['jobs'], receipt['jobs'])
                self.assertEqual(verified['assertion_audit']['sha256'], hashlib.sha256(audit_path.read_bytes()).hexdigest())
                self.assertEqual(semantic_check.call_count, 8)
                for index in (0, 3):
                    with self.subTest(worker=rows[index]['worker']):
                        report = Path(rows[index]['result_path'])
                        # Strip-equivalent content still needs the exact saved file hash.
                        report.write_text(rows[index]['result'] + '\n\n')
                        with self.assertRaisesRegex(RuntimeError, 'accepted saved report changed'):
                            deploy.verify_worker_probes(root, WT, TEST_TIP)
                        report.write_text(rows[index]['result'] + '\n')
                        prompt = Path(rows[index]['prompt_file'])
                        original = prompt.read_text()
                        prompt.write_text(original + '\nchanged')
                        with self.assertRaisesRegex(RuntimeError, 'worker prompt changed'):
                            deploy.verify_worker_probes(root, WT, TEST_TIP)
                        prompt.write_text(original)
                for tamper in ('saved_hash', 'case_classification', 'case_hash', 'count'):
                    changed = json.loads(json.dumps(audit))
                    if tamper == 'saved_hash':
                        changed['jobs'][0]['saved_report_sha256'] = 'tampered'
                    elif tamper == 'case_classification':
                        changed['jobs'][0]['cases'][0]['classification'] = 'semantic-reviewed'
                    elif tamper == 'case_hash':
                        changed['jobs'][0]['cases'][0]['draft_sha256'] = 'tampered'
                    else:
                        changed['literal_guard_count'] -= 1
                    audit_path.write_text(json.dumps(changed))
                    with self.subTest(tamper=tamper), self.assertRaisesRegex(RuntimeError, 'audit differs'):
                        deploy.verify_worker_probes(root, WT, TEST_TIP)


if __name__=='__main__':
    unittest.main(verbosity=2)
