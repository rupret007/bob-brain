"""Real subprocess startup regressions and isolated launcher recovery; no live requests."""
import contextlib
import errno
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import record_texting_deploy_2003 as wrapper
from texting_deploy_record import atomic_json, claim_record, launch_environment

TIP = '1' * 40
HERE = Path(__file__).resolve().parent


class LauncherTests(unittest.TestCase):
    def test_runner_imports_reviewed_modules_from_changed_cwd_and_relative_pythonpath(self):
        code = ('import sys,json; sys.path.insert(0, sys.argv[1]); import deploy_texting_2003 as d; '
                'print(json.dumps({n:sys.modules[n].__file__ for n in '
                '("deploy_parity","live_redeploy_check","providers","task_dispatch")}))')
        for cwd in (HERE.parent / 'webchat', Path('/private/tmp')):
            with self.subTest(cwd=cwd):
                result = subprocess.run([sys.executable, '-c', code, str(HERE)], cwd=cwd,
                    env=dict(os.environ, PYTHONPATH='webchat:services:state'), capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                for path in json.loads(result.stdout).values():
                    self.assertTrue(Path(path).is_relative_to(HERE.parent), path)

    def test_environment_does_not_retain_relative_pythonpath(self):
        with patch.dict(os.environ, PYTHONPATH='webchat:services:state'):
            env = launch_environment(HERE.parent, HERE.parent)
        self.assertTrue(all(Path(p).is_absolute() for p in env['PYTHONPATH'].split(os.pathsep)))
        self.assertEqual(env['BOB_ROOT'], str(HERE.parent))

    def test_atomic_initial_record_and_duplicate_slot_preservation(self):
        with tempfile.TemporaryDirectory() as folder:
            record = Path(folder) / 'attempt.json'
            claim_record(record, dict(status='PREFLIGHT'))
            with self.assertRaises(FileExistsError):
                claim_record(record, dict(status='REPLACED'))
            self.assertEqual(json.loads(record.read_text()), dict(status='PREFLIGHT'))
            with patch('texting_deploy_record.os.replace', side_effect=OSError('disk failure')):
                with self.assertRaises(OSError):
                    atomic_json(record, dict(status='REPLACED'))
            self.assertEqual(json.loads(record.read_text()), dict(status='PREFLIGHT'))

    def exercise(self, mode):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as folder:
            root = Path(folder)
            reviews, candidate = root / 'conductor/reviews', root / 'candidate'
            for path in (reviews, root / 'conductor/webchat', candidate / 'reviews', candidate / 'webchat'):
                path.mkdir(parents=True, exist_ok=True)
            (root / 'conductor/webchat/.password').write_text('synthetic-password')
            runner = candidate / 'reviews/deploy_texting_2003.py'
            runner.write_text('raise ModuleNotFoundError("synthetic missing deploy_parity")\n')
            record = reviews / 'WEBBOB-TEXTING-DEPLOYMENT-0927-attempt13.json'
            baseline = {name: dict(sha=wrapper.PREVIOUS) for name in ('local', 'public')}
            current = dict(baseline)
            if mode == 'stale_preflight':
                current['public'] = dict(sha=TIP)
            calls = []
            real_run = subprocess.run

            def run(command, **kwargs):
                initial = json.loads(record.read_text())
                if '--rollback' not in command:
                    self.assertFalse(initial['all_pass'])
                self.assertTrue(all(Path(p).is_absolute() for p in kwargs['env']['PYTHONPATH'].split(os.pathsep)))
                calls.append(command)
                if mode not in ('timeout_after_activation', 'final_report_io', 'record_read_io'):
                    return real_run(command, **kwargs)
                if '--rollback' not in command:
                    initial.update(activated=True, rollback=initial['planned_rollback'], status='ACTIVATING')
                    atomic_json(record, initial)
                    current.update({name: dict(sha=TIP) for name in ('local', 'public')})
                    if mode in ('final_report_io', 'record_read_io'):
                        initial.update(status='LIVE_PASS', all_pass=True)
                        atomic_json(record, initial)
                        return subprocess.CompletedProcess(command, 0)
                    raise subprocess.TimeoutExpired(command, 1)
                initial.update(rolled_back=True, restored_version=baseline['local'], restored_public_version=baseline['public'])
                atomic_json(record, initial)
                current.update(baseline)
                return subprocess.CompletedProcess(command, 0, stdout='', stderr='')

            real_read = wrapper.read
            def read(path):
                if mode == 'record_read_io':
                    raise OSError(errno.EIO, 'synthetic record read I/O failure')
                return real_read(path)

            real_text = wrapper.atomic_text
            def publish(path, body):
                if mode == 'final_report_io' and 'RESULT: LIVE_PASS' in body:
                    raise OSError(errno.EIO, 'synthetic final report I/O failure')
                return real_text(path, body)

            with patch.object(wrapper, 'versions', side_effect=lambda root: dict(current)), \
                 patch.object(wrapper.subprocess, 'run', side_effect=run), \
                 patch.object(wrapper, 'atomic_text', side_effect=publish), \
                 patch.object(wrapper, 'read', side_effect=read), \
                 patch('texting_deploy_record.RECOVERY_BYTES', 1024**2), \
                 patch.dict(os.environ, PYTHONPATH='webchat:services:state'), \
                 contextlib.redirect_stdout(io.StringIO()):
                code = wrapper.main(['--root', str(root), '--candidate', str(candidate), '--tip', TIP,
                                     '--attempt', '13', '--draft-pr', 'https://example.invalid/pr'])
            self.assertEqual(code, 1)
            evidence = json.loads(record.read_text())
            report = (reviews / 'TEXTING-DEPLOY-2003.md').read_text()
            self.assertEqual(evidence['status'], 'FAIL_OR_ROLLBACK')
            self.assertIn(str(record), report)
            self.assertIn('RESULT: FAIL_OR_ROLLBACK', report)
            self.assertIn('0 captured turns', report)
            self.assertNotIn('synthetic-password', report + json.dumps(evidence))
            self.assertEqual(evidence['rollback_version_verified'], mode != 'stale_preflight')
            if mode == 'import_failure':
                self.assertIn('ModuleNotFoundError: synthetic missing deploy_parity', report)
                self.assertIn('Traceback', evidence['child_error_tail'])
                self.assertEqual(len(calls), 1)
            elif mode == 'stale_preflight':
                self.assertEqual(calls, [])
                self.assertIn('preflight no longer matches', evidence['wrapper_failure'])
            else:
                self.assertEqual(len(calls), 2)
                self.assertIn('--rollback', calls[1])
                if mode != 'record_read_io':
                    self.assertTrue(evidence['rolled_back'])
                self.assertIn('record read I/O' if mode == 'record_read_io' else 'final report I/O' if mode == 'final_report_io' else 'TimeoutExpired', evidence['wrapper_failure'])

    def test_record_read_io_still_uses_planned_rollback_and_verifies_versions(self):
        self.exercise('record_read_io')

    def test_final_marker_io_failure_retracts_pass_and_rolls_back(self):
        self.exercise('final_report_io')

    def test_child_import_failure_keeps_evidence_and_exact_traceback(self):
        self.exercise('import_failure')

    def test_early_preflight_failure_always_has_evidence(self):
        self.exercise('stale_preflight')

    def test_parent_timeout_recovers_and_verifies_both_versions(self):
        self.exercise('timeout_after_activation')

    def test_report_counts_captured_turns_not_reserved_frozen_turns(self):
        evidence = dict(sha=TIP, draft_pr='draft', attempt=13, child_log='log',
                        sessions=[dict(exchanges=[dict(message='frozen')] * 19)])
        self.assertIn('0 captured turns', wrapper.report_text(evidence, Path('evidence.json')))


if __name__ == '__main__':
    unittest.main(verbosity=2)
