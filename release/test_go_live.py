"""Staging and exact-head admission; activation and external services mocked."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import go_live


class GoLiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.sha = 'a' * 40
        raw = self.root / 'synthetic-runner-output.txt'
        raw.write_text('Synthetic test evidence. Never a production verdict.')
        self.common = dict(sha=self.sha, verdict='PASS', unresolved_blockers=[], evidence=[
            dict(path=str(raw), sha256=hashlib.sha256(raw.read_bytes()).hexdigest())])
        self.karen = dict(self.common, reviewer='Karen', findings=['Synthetic fixture only'])
        paired = dict(sha=self.sha, verdict='PASS', reviewers=['Claude', 'Codex'])
        self.scores = dict(self.common, reviewers=['Claude', 'Codex'],
                           main=dict(paired, score=144), holdout=paired)
        self.karen_path, self.scores_path = self.root / 'karen.json', self.root / 'scores.json'
        self.write(self.karen_path, self.karen); self.write(self.scores_path, self.scores)

    def write(self, path, value):
        path.write_text(json.dumps(value)); path.chmod(0o600)

    def test_plan_has_no_activation_or_external_side_effects(self):
        with patch.object(go_live.solo, 'deploy') as deploy, patch.object(go_live, 'github_gates') as github:
            value = go_live.plan(self.sha)
        deploy.assert_not_called(); github.assert_not_called()
        self.assertTrue(value['stage_only'])
        self.assertEqual(value['previous'], 'cf83a9a80e0426d6998a0bf7b3a0574e52ac8e1a')
        self.assertIn('two complete live rounds', value['health'])

    def test_exact_karen_pair_and_raw_evidence_binding(self):
        go_live.external_gates(self.sha, self.karen_path, self.scores_path)
        cases = [(self.karen_path, self.karen, {'sha': 'b' * 40}),
                 (self.karen_path, self.karen, {'verdict': 'FAIL'}),
                 (self.karen_path, self.karen, {'reviewer': 'needs-karen'}),
                 (self.karen_path, self.karen, {'unresolved_blockers': ['not ready']}),
                 (self.scores_path, self.scores, {'reviewers': ['Grok', 'Codex']}),
                 (self.scores_path, self.scores, {'main': dict(self.scores['main'], score=143)}),
                 (self.scores_path, self.scores, {'main': dict(self.scores['main'], score=float('nan'))}),
                 (self.scores_path, self.scores, {'holdout': dict(self.scores['holdout'], sha='b' * 40)}),
                 (self.scores_path, self.scores, {'holdout': dict(self.scores['holdout'], verdict='FAIL')})]
        for path, original, change in cases:
            with self.subTest(change=change):
                self.write(path, dict(original, **change))
                with self.assertRaises(RuntimeError):
                    go_live.external_gates(self.sha, self.karen_path, self.scores_path)
                self.write(path, original)
        Path(self.common['evidence'][0]['path']).write_text('changed')
        with self.assertRaisesRegex(RuntimeError, 'evidence changed'):
            go_live.external_gates(self.sha, self.karen_path, self.scores_path)

    def test_github_requires_latest_trusted_success_at_exact_head(self):
        pr = dict(headRefOid=self.sha, isDraft=True, state='OPEN')
        checks = dict(total_count=len(go_live.CI_NAMES), check_runs=[dict(id=i, name=name, head_sha=self.sha,
            app=dict(slug='github-actions'), conclusion='success', status='completed')
            for i, name in enumerate(sorted(go_live.CI_NAMES))])
        with patch.object(go_live.subprocess, 'check_output', side_effect=[json.dumps(pr), json.dumps(checks)]):
            go_live.github_gates(self.sha, '161', '/fake/gh')
        failed = dict(checks['check_runs'][0], id=100, conclusion='failure')
        for change in (dict(failed), dict(failed, conclusion='success', head_sha='b' * 40),
                       dict(failed, conclusion='success', app=dict(slug='untrusted-app'))):
            rows = [change] if change != failed else checks['check_runs'] + [failed]
            with self.subTest(change=change), patch.object(go_live.subprocess, 'check_output',
                    side_effect=[json.dumps(pr), json.dumps(dict(total_count=len(rows), check_runs=rows))]):
                with self.assertRaises(RuntimeError): go_live.github_gates(self.sha, '161', '/fake/gh')

    def test_privacy_is_required_even_when_all_runtime_suites_are_green(self):
        pr = dict(headRefOid=self.sha, isDraft=True, state='OPEN')
        runtime = [dict(id=i, name=name, head_sha=self.sha, app=dict(slug='github-actions'),
                        conclusion='success', status='completed')
                   for i, name in enumerate(('python-ubuntu-latest', 'python-macos-latest', 'unittest'))]
        privacy = dict(id=10, name='public-privacy', head_sha=self.sha,
                       app=dict(slug='github-actions'), conclusion='success', status='completed')
        cases = [[], [dict(privacy, conclusion='failure')], [dict(privacy, conclusion='skipped')],
                 [dict(privacy, status='in_progress', conclusion=None)],
                 [dict(privacy, head_sha='b' * 40)],
                 [dict(privacy, app=dict(slug='untrusted-app'))],
                 [privacy, dict(privacy, id=11, conclusion='failure')]]
        for extra in cases:
            rows = runtime + extra
            with self.subTest(extra=extra), patch.object(go_live.subprocess, 'check_output',
                    side_effect=[json.dumps(pr), json.dumps(dict(total_count=len(rows), check_runs=rows))]):
                with self.assertRaises(RuntimeError):
                    go_live.github_gates(self.sha, '161', '/fake/gh')
        rows = runtime + [privacy]
        with patch.object(go_live.subprocess, 'check_output',
                side_effect=[json.dumps(pr), json.dumps(dict(total_count=len(rows), check_runs=rows))]):
            go_live.github_gates(self.sha, '161', '/fake/gh')

    def test_activation_requires_jeff_and_preserves_original_controller(self):
        args = argparse.Namespace(root=self.root, jeff_ok=None, karen=self.karen_path,
            scores=self.scores_path, pr='161', gh=Path('/fake/gh'), checks=self.root/'checks', review=self.root/'review')
        with patch.object(go_live.solo, 'identity', return_value=self.sha), \
                patch.object(go_live.solo, 'deploy') as deploy, \
                patch.object(go_live.solo.qualification_scope, 'selected', return_value=None), \
                patch.object(go_live.solo, 'git', return_value=go_live.PREVIOUS), \
                patch.object(go_live, 'github_gates') as github, \
                patch.object(go_live.solo, 'verify_gates') as gates, \
                patch.object(go_live.solo, 'versions') as versions:
            with self.assertRaisesRegex(RuntimeError, 'Jeff exact-SHA'): go_live.activate(args)
            deploy.assert_not_called(); github.assert_not_called()
            args.jeff_ok = go_live.approval_text(self.sha)
            go_live.activate(args)
            gates.assert_called_once_with(self.sha, 'improve', args.checks, args.review)
            versions.assert_called_once_with(self.root, go_live.PREVIOUS)
            deploy.assert_called_once()
            self.assertEqual(deploy.call_args.args[0].previous, go_live.PREVIOUS)
            self.assertEqual(deploy.call_args.args[0].feature, 'improve')
            deploy.reset_mock()
            gates.side_effect = RuntimeError('original gate failed')
            with self.assertRaisesRegex(RuntimeError, 'original gate failed'): go_live.activate(args)
            deploy.assert_not_called()
