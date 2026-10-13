"""Opt-in shared-machine execution lease: offline subprocess fixtures only."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'state'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'services'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import execution_lease
import task_queue
from providers import Providers


HELPER = Path(__file__).resolve().parents[1] / 'state' / 'execution_lease.py'


class ExecutionLeaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.lock = self.root / 'fixture-execution.lock'
        self.env = {
            execution_lease.PROFILE_ENV: '1',
            execution_lease.LOCK_ENV: str(self.lock),
            'BOB_EXECUTION_LEASE_TEST_ROOT': str(self.root),
        }
        self.patches = [
            patch.dict(os.environ, self.env, clear=False),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def child_env(self, **extra):
        env = dict(os.environ)
        env.update(self.env)
        env.update(extra)
        env.pop('BOB_SHARED_EXECUTION_LEASE_SLOTS', None)
        env['PYTHONUNBUFFERED'] = '1'
        return env

    def spawn(self, action='hold', crash=False, seconds='8', extra=None):
        ready = self.root / ('ready-%s.txt' % time.monotonic())
        env = self.child_env(
            BOB_EXECUTION_LEASE_TEST_CRASH='1' if crash else '0',
            BOB_EXECUTION_LEASE_TEST_SECONDS=seconds,
            BOB_EXECUTION_LEASE_TEST_READY=str(ready),
            **(extra or {}),
        )
        process = subprocess.Popen(
            [sys.executable, '-u', str(HELPER), action],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        process.ready_path = ready
        self.addCleanup(self._stop, process)
        return process

    def _stop(self, process):
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
        for stream in (process.stdout, process.stderr):
            if stream:
                stream.close()

    def wait_held(self, process):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if getattr(process, 'ready_path', None) and process.ready_path.exists():
                self.assertEqual(process.ready_path.read_text().strip(), 'HELD')
                return
            if process.poll() is not None:
                err = process.stderr.read() if process.stderr else ''
                self.fail('holder exited %s before the lease ready file appeared: %s' % (process.poll(), err))
            time.sleep(0.02)
        self.fail('holder did not publish a ready file')

    def enqueue(self, request='one', worker='codex', **fields):
        return task_queue.enqueue(
            self.root, 'conversation', request, 'Review this supplied task evidence.',
            worker=worker, kind='analysis', **fields)

    def test_two_background_lanes_cannot_run_at_once_when_enabled(self):
        first = self.spawn(seconds='8')
        self.wait_held(first)
        second = self.spawn(seconds='1')
        out, err = second.communicate(timeout=5)
        self.assertNotEqual(second.returncode, 0, msg='stdout=%r stderr=%r' % (out, err))
        self.assertIn(execution_lease.CAPACITY_REASON, err)
        with self.assertRaises(BlockingIOError):
            with execution_lease.hold(self.root):
                raise AssertionError('second background lane acquired the global slot')
        self.assertIsNone(first.poll())

    def test_crashed_holder_releases_the_slot(self):
        crashed = self.spawn(crash=True)
        self.wait_held(crashed)
        self.assertEqual(crashed.wait(timeout=5), 1)
        deadline = time.monotonic() + 3
        acquired = False
        while time.monotonic() < deadline:
            try:
                with execution_lease.hold(self.root):
                    acquired = True
                    break
            except BlockingIOError:
                time.sleep(0.05)
        self.assertTrue(acquired)

    def test_disabled_profile_keeps_current_parallel_behavior(self):
        with patch.dict(os.environ, {execution_lease.PROFILE_ENV: '0'}, clear=False):
            self.assertFalse(execution_lease.load_profile(self.root)['enabled'])
            first = self.spawn(seconds='3', extra={execution_lease.PROFILE_ENV: '0'})
            self.wait_held(first)
            second = self.spawn(seconds='0.2', extra={execution_lease.PROFILE_ENV: '0'})
            self.assertEqual(second.wait(timeout=5), 0)
            self.assertEqual(second.stdout.readline().strip(), 'HELD')
            with execution_lease.hold(self.root):
                with execution_lease.hold(self.root):
                    self.assertTrue(execution_lease.available(self.root))

    def test_deferral_does_not_consume_a_successful_result(self):
        row = self.enqueue()
        holder = self.spawn(seconds='8')
        self.wait_held(holder)
        self.assertIsNone(task_queue.claim(self.root, 'codex', identifier=row['id']))
        deferred = task_queue.tasks(self.root)[row['id']]
        self.assertEqual(deferred['status'], 'queued')
        self.assertIsNone(deferred.get('result'))
        self.assertNotEqual(deferred.get('event'), 'succeeded')
        self.assertEqual(deferred['error'], execution_lease.CAPACITY_REASON)
        self.assertEqual(deferred['event'], 'execution_deferred')
        self.assertIsNone(deferred.get('claim_token'))
        self.assertIsNone(holder.poll())

    def test_hold_and_budget_rejection_still_win(self):
        session = self.root / 'conductor/webchat/sessions/conversation.json'
        session.parent.mkdir(parents=True)
        session.write_text(json.dumps(dict(
            id='conversation',
            intent_state=dict(holds={'all': {'released_projects': []}}),
        )))
        held = self.enqueue('held', permission_file=session, project_scopes=['Web Bob'])
        holder = self.spawn(seconds='8')
        self.wait_held(holder)
        self.assertIsNone(task_queue.claim(self.root, 'codex', identifier=held['id']))
        held_row = task_queue.tasks(self.root)[held['id']]
        self.assertEqual(held_row['status'], 'queued')
        self.assertNotEqual(held_row.get('error'), execution_lease.CAPACITY_REASON)
        self.assertNotEqual(held_row.get('event'), 'execution_deferred')

        budgeted = task_queue.enqueue(
            self.root, 'budget-chat', 'budget', 'Review this supplied task evidence.', worker='codex')
        import generation_budget
        with patch.object(generation_budget, 'task_block', return_value='generation allowance exhausted'):
            self.assertIsNone(task_queue.claim(self.root, 'codex', identifier=budgeted['id']))
        budget_row = task_queue.tasks(self.root)[budgeted['id']]
        self.assertEqual(budget_row['status'], 'queued')
        self.assertEqual(budget_row['error'], 'generation allowance exhausted')
        self.assertEqual(budget_row['event'], 'generation_held')
        self.assertIsNone(budget_row.get('result'))
        self.assertIsNone(holder.poll())

    def test_interactive_chat_lane_stays_outside_the_global_lease(self):
        holder = self.spawn(seconds='8')
        self.wait_held(holder)
        providers = Providers(self.root, lambda text: text)
        with providers.lane('codex'):
            self.assertTrue((self.root / 'conductor/locks/chat-codex.lock').exists())
        self.assertIsNone(holder.poll())

    def test_fixture_refuses_production_lock_paths(self):
        env = self.child_env()
        env.pop(execution_lease.LOCK_ENV, None)
        result = subprocess.run(
            [sys.executable, str(HELPER), 'hold'],
            env=env, capture_output=True, text=True, timeout=5)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('production lock', result.stderr)
        self.assertFalse(Path('conductor/locks/execution-lease-0.lock').exists())


if __name__ == '__main__':
    unittest.main()
