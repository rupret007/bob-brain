"""Actual process identity parsing and bounded refresh/recovery obligations."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import solo
import runner_activation as runner
import state


class RunnerActivationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.core = self.root / 'conductor'
        (self.core / 'locks').mkdir(parents=True)
        (self.core / 'locks/job-runner.pid').write_text('1234\n')
        self.code = self.root / 'rollbacks/previous'
        (self.code / 'services').mkdir(parents=True)
        (self.code / 'services/job-runner.sh').write_text('#!/bin/bash\n')
        (self.code / 'webbob-build.json').write_text(json.dumps({'sha':'b'*40}))

    def test_process_root_not_dispatch_pin_establishes_loaded_code(self):
        command = '/bin/bash ' + str(self.code / 'services/job-runner.sh') + ' --locked'
        with patch.object(runner.runtime, 'screen_sessions', return_value={'svc-job-runner':'10.svc-job-runner'}), \
                patch.object(runner.runtime, 'service_lock_held', return_value=True), \
                patch.object(runner.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout=command)):
            observed = runner.observe(self.root)
            self.assertEqual(observed['code_root'], str(self.code))
            self.assertEqual(observed['sha'], 'b'*40)
            self.assertTrue(runner.matches(self.root, self.code))
            self.assertFalse(runner.matches(self.root, self.root / 'candidate'))

    def test_unrelated_pid_is_never_stopped(self):
        with patch.object(runner.runtime, 'screen_sessions', return_value={'svc-job-runner':'10.svc-job-runner'}), \
                patch.object(runner.runtime, 'service_lock_held', return_value=True), \
                patch.object(runner.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout='/bin/bash /other/services/job-runner.sh --locked')), \
                patch.object(runner.runtime, 'stop_service_process') as stop:
            with self.assertRaises((RuntimeError, FileNotFoundError)):
                runner.stop(self.root, [self.code])
            stop.assert_not_called()

    def test_drain_timeout_preserves_active_worker_and_pins(self):
        with patch.object(runner.task_queue, 'tasks', return_value={'job':{'status':'running'}}), \
                patch.object(runner, 'stop') as stop:
            with self.assertRaisesRegex(RuntimeError, 'active tasks'):
                runner.drain(self.root, timeout=0)
            stop.assert_not_called()

    def test_absent_service_is_not_enabled(self):
        record = dict(sha='a'*40, rollback=str(self.root/'rollbacks/new'),
                      runner_refresh={'required':False}, snapshots={'dispatch':str(self.code)})
        with patch.object(runner, 'start') as start, patch.object(runner, 'stop') as stop, \
                patch.object(runner, 'observe', return_value=None):
            with runner.refresh(self.root, {'dispatch':self.code}, {'record':record}):
                pass
            stop.assert_not_called()
            start.assert_not_called()

    def test_failure_after_stop_keeps_recovery_obligation_without_starting_partial_target(self):
        intent = {'record':{'runner_refresh':{'required':True,'prior':{'code_root':str(self.code)}},
                            'snapshots':{'dispatch':str(self.code)}, 'rollback':str(self.root / 'rollbacks/new')}}
        with patch.object(state, 'CONDUCTOR', self.core), patch.object(runner, 'drain'), \
                patch.object(runner, 'observe', return_value={'code_root':str(self.code)}), \
                patch.object(runner, 'stop') as stop, patch.object(runner, 'start') as start:
            with self.assertRaisesRegex(RuntimeError, 'activation failed'):
                with runner.refresh(self.root, {'dispatch':self.code}, intent):
                    raise RuntimeError('activation failed')
            stop.assert_called_once()
            start.assert_not_called()
            self.assertTrue(intent['record']['runner_refresh']['required'])

    def test_dead_claim_recovers_but_live_execution_lock_is_never_reaped(self):
        import fcntl
        row = runner.task_queue.enqueue(self.root, 'fixture', 'dead', 'Review supplied evidence')
        claim = runner.task_queue.claim(self.root, 'gemini', identifier=row['id'], now=1)
        runner.task_queue.transition(self.root, row['id'], claim['claim_token'], 'running', now=2)
        lock = self.core / 'locks' / ('dispatch-' + row['id'] + '.lock')
        with lock.open('a') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            with self.assertRaisesRegex(RuntimeError, 'active tasks'):
                runner.drain(self.root, timeout=0)
            self.assertEqual(runner.task_queue.tasks(self.root)[row['id']]['status'], 'running')
        runner.drain(self.root, timeout=0)
        self.assertEqual(runner.task_queue.tasks(self.root)[row['id']]['status'], 'queued')

    def test_late_enabled_runner_is_durably_preserved_before_stop(self):
        folder = self.root / 'rollbacks/new'
        folder.mkdir()
        record = dict(sha='a'*40, rollback=str(folder), runner_refresh={'required':False},
                      snapshots={'dispatch':str(self.code)}, original_pins={'dispatch':str(self.code)})
        with patch.object(runner, 'observe', return_value={'code_root':str(self.code), 'sha':'b'*40}), \
                patch.object(runner, 'stop') as stop, patch.object(runner, 'start'), patch.object(runner, 'drain'):
            def stopped(*_):
                self.assertTrue(runner.required(self.root, record))
                raise RuntimeError('controller died after obligation')
            stop.side_effect = stopped
            with self.assertRaisesRegex(RuntimeError, 'controller died'):
                with runner.refresh(self.root, {'dispatch':self.code}, {'record':record}):
                    pass
        self.assertTrue(runner.required(self.root, record))
