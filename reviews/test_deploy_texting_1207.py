"""Isolated release-gate and rollback checks; never touch live services."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

HERE = Path(__file__).resolve().parent
WT = HERE.parents[1] / 'workspaces/webbob-texting-jobcomplete-1207'
spec = importlib.util.spec_from_file_location('deploy_texting_1207', HERE / 'deploy_texting_1207.py')
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)


class TextingReleaseGuards(unittest.TestCase):
    def exercise(self, reviews_pass, completion_failure=False):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as folder, patch.dict(os.environ):
            root = Path(folder)
            candidate, old = root / 'candidate', root / 'old'
            for p in (root/'conductor/state', root/'conductor/reviews', root/'conductor/webchat', root/'rollbacks', candidate/'webchat/fixtures', candidate/'services/fixtures', old):
                p.mkdir(parents=True)
            reviews = root/'conductor/reviews'
            (root/'conductor/webchat/.password').write_text('synthetic-password')
            (old/'webbob-build.json').write_text(json.dumps(dict(sha=deploy.PREVIOUS)))
            for name in ('webchat','dispatch'):
                (root/'conductor/state'/(name+'-code-root')).write_text(str(old))
            (candidate/'webchat/fixtures/texting_diagdump_0810.json').write_text((WT/'webchat/fixtures/texting_diagdump_0810.json').read_text())
            (candidate/'services/fixtures/texting_verification_0810.json').write_text((WT/'services/fixtures/texting_verification_0810.json').read_text())
            (candidate/'services/fixtures/texting_jobcompletion_1035.json').write_text((WT/'services/fixtures/texting_jobcompletion_1035.json').read_text())
            (candidate/'services/fixtures/texting_jobcompletion_1107.json').write_text((WT/'services/fixtures/texting_jobcompletion_1107.json').read_text())
            (reviews/'TEXTING-LIVE-1207.md').write_text('GATE: BOTH_PASS tip='+deploy.TIP[:7])
            outputs = {}
            for name in ('gemini','minimax'):
                output = reviews/(name+'.md')
                output.write_text('VERDICT: PASS\n')
                outputs[name] = dict(exit=0,verdict='PASS',output=str(output),output_sha256=hashlib.sha256(output.read_bytes()).hexdigest())
            gate = dict(sha=deploy.TIP,gate='BOTH_PASS' if reviews_pass else 'NOT_BOTH_PASS',reviews=outputs)
            (reviews/'TEXTING-LIVE-1207.json').write_text(json.dumps(gate))
            (reviews/'TEXTING-CLEAN-MERGE-1207.json').write_text(json.dumps(dict(merge_sha='merge-sha')))
            log = reviews/'test.log'
            log.write_text('OK')
            results = {name:dict(exit=0,skipped=0,log=str(log),log_sha256=hashlib.sha256(log.read_bytes()).hexdigest())
                       for name in ('webchat','services','eval','browser')}
            (reviews/'TEXTING-1207-tests.json').write_text(json.dumps(dict(sha=deploy.TIP,suite_exit=0,eval_exit=0,all_pass=True,results=results,eval=dict(passed=100,total=100))))
            def command(argv):
                if argv[0]=='gh':
                    return json.dumps(dict(isDraft=True,state='OPEN',headRefOid=deploy.TIP,baseRefName='draft/webbob-clean-0927'))
                if 'rev-parse' in argv: return deploy.TIP
                if 'ls-remote' in argv: return deploy.TIP+' refs/heads/'+deploy.BRANCH+'\nmerge-sha refs/heads/draft/webbob-clean-0927'
                if 'branch' in argv: return deploy.BRANCH
                return ''
            client=MagicMock()
            client.url='http://127.0.0.1:8787'
            versions=iter([dict(sha=deploy.PREVIOUS),dict(sha=deploy.TIP),dict(sha=deploy.PREVIOUS)])
            client.call.side_effect=lambda route: next(versions) if route=='/api/version' else {}
            args=['deploy_texting_1207.py','--root',str(root),'--candidate',str(candidate),'--attempt','1','--draft-pr','https://example.org/pr']
            with patch('sys.argv',args), patch.object(deploy,'run',side_effect=command), \
                 patch.object(deploy,'Client',return_value=client), patch.object(deploy,'latest_sessions',return_value=[]), \
                 patch.object(deploy,'restart',return_value=dict(other_screens_unchanged=True)) as restart, \
                 patch.object(deploy,'texting_smoke',side_effect=None if completion_failure else RuntimeError('synthetic smoke failure')), \
                 patch.object(deploy,'verify_executions',side_effect=RuntimeError('synthetic incomplete report')), \
                 contextlib.redirect_stdout(io.StringIO()):
                client.new.return_value = '1035-regression-conversation'
                self.assertEqual(deploy.main(),1)
            evidence=json.loads((reviews/'WEBBOB-TEXTING-DEPLOYMENT-0927-attempt1.json').read_text())
            self.assertFalse(evidence['all_pass'])
            self.assertNotIn('synthetic-password',json.dumps(evidence))
            if reviews_pass:
                self.assertEqual(restart.call_count,2)
                self.assertTrue(evidence['rolled_back'])
                self.assertEqual(evidence['restored_version']['sha'],deploy.PREVIOUS)
                self.assertIn('synthetic incomplete report' if completion_failure else 'synthetic smoke failure',evidence['failure'])
                if completion_failure:
                    self.assertEqual(evidence['cancelled_replay_jobs'], [evidence['jobcompletion_regression']['job_id']])
            else:
                restart.assert_not_called()
                self.assertNotIn('activated',evidence)
                self.assertIn('review SHA/gate mismatch',evidence['failure'])

    def test_bad_fresh_review_gate_never_activates(self):
        self.exercise(False)

    def test_failed_smoke_restores_and_verifies_a777736(self):
        self.exercise(True)

    def test_rollback_revokes_extra_1035_regression_conversation(self):
        self.assertEqual(deploy.replay_conversations(dict(sessions=[dict(replay_id="frozen-replay")],
            jobcompletion_regression=dict(conversation_id="1035-replay"))), {"frozen-replay", "1035-replay"})

    def test_failed_1035_completion_revokes_claim_and_restores_a777736(self):
        self.exercise(True, completion_failure=True)


if __name__=='__main__':
    unittest.main(verbosity=2)
