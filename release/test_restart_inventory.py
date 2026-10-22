"""Finite scheduler completion must not look like a lost persistent service."""
from contextlib import contextmanager, nullcontext
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

import solo
import runner_activation as runner
import activation_journal as journal
from live_redeploy_check import CheckFailure


class RestartInventoryTests(unittest.TestCase):
    def setUp(self):
        self.durable = {'svc-webchat': '1.svc-webchat', 'svc-reviewer': '2.svc-reviewer',
                        'svc-watchdog': '3.svc-watchdog'}

    def test_no_finite_service_needs_no_wait_or_extra_probe(self):
        with patch('runtime.screen_sessions') as probe, patch.object(solo.time, 'sleep') as sleep:
            value = solo.settle_transient_services(self.durable)
        self.assertEqual(value, dict(before=self.durable, after=self.durable, observed=[]))
        probe.assert_not_called()
        sleep.assert_not_called()

    def test_tick_and_pass_finish_naturally_before_restart_baseline(self):
        before = dict(self.durable, **{'svc-project-tick': '4.svc-project-tick',
                                      'svc-conductor-pass': '5.svc-conductor-pass'})
        intermediate = dict(self.durable, **{'svc-conductor-pass': '5.svc-conductor-pass'})
        with patch('runtime.screen_sessions', side_effect=[intermediate, self.durable]) as probe, \
                patch.object(solo.time, 'sleep'):
            value = solo.settle_transient_services(before)
        self.assertEqual(value['before'], before)
        self.assertEqual(value['after'], self.durable)
        self.assertEqual(value['observed'], ['4.svc-project-tick', '5.svc-conductor-pass'])
        self.assertEqual(probe.call_count, 2)
        self.assertTrue(all(0 < call.kwargs['timeout'] <= 15 for call in probe.call_args_list))

    def test_persistent_service_disappearance_or_replacement_during_wait_fails(self):
        before = dict(self.durable, **{'svc-project-tick': '4.svc-project-tick'})
        for changed in (None, '99.svc-reviewer'):
            after = dict(self.durable)
            if changed is None:
                after.pop('svc-reviewer')
            else:
                after['svc-reviewer'] = changed
            with self.subTest(changed=changed), patch('runtime.screen_sessions', return_value=after), \
                    patch.object(solo.time, 'sleep'):
                with self.assertRaises(CheckFailure) as error:
                    solo.settle_transient_services(before)
            self.assertIn('svc-reviewer', str(error.exception))
            self.assertIn('2.svc-reviewer', str(error.exception))
            self.assertIn('before', str(error.exception))
            self.assertIn('after', str(error.exception))

    def test_unknown_service_is_never_treated_as_a_finite_scheduler(self):
        before = dict(self.durable, **{'svc-unknown': '4.svc-unknown'})
        value = solo.settle_transient_services(before)
        self.assertEqual(value['after'], before)
        with self.assertRaisesRegex(CheckFailure, 'svc-unknown'):
            solo.unchanged_services(value['after'], self.durable, {'svc-webchat'})

    def test_finite_service_timeout_preserves_failure_inventory(self):
        before = dict(self.durable, **{'svc-project-tick': '4.svc-project-tick'})
        with patch.object(solo.time, 'monotonic', side_effect=[0, 31]), \
                patch('runtime.screen_sessions') as probe:
            with self.assertRaisesRegex(CheckFailure, '4.svc-project-tick'):
                solo.settle_transient_services(before)
        probe.assert_not_called()

    def test_slow_inventory_cannot_extend_the_deadline(self):
        before = dict(self.durable, **{'svc-project-tick': '4.svc-project-tick'})
        with patch.object(solo.time, 'monotonic', side_effect=[0, 29, 29.5, 31]), \
                patch.object(solo.time, 'sleep'), patch('runtime.screen_sessions', return_value=self.durable) as probe:
            with self.assertRaisesRegex(CheckFailure, 'inventory exceeded'):
                solo.settle_transient_services(before)
        probe.assert_called_once_with(timeout=.5)

    def test_probe_failure_is_not_an_empty_inventory(self):
        before = dict(self.durable, **{'svc-project-tick': '4.svc-project-tick'})
        with patch.object(solo.time, 'sleep'), patch('runtime.screen_sessions',
                side_effect=subprocess.TimeoutExpired(['screen', '-ls'], .5)):
            with self.assertRaises(RuntimeError) as error:
                solo.settle_transient_services(before)
        self.assertIsInstance(error.exception.__cause__, subprocess.TimeoutExpired)
        self.assertIn('4.svc-project-tick', str(error.exception))
        self.assertIn('before', str(error.exception))
        self.assertIn('after', str(error.exception))
        self.assertIn('TimeoutExpired', str(error.exception))

    def test_normal_restart_excludes_only_its_explicitly_refreshed_services(self):
        before = dict(self.durable, **{'svc-job-runner': '4.svc-job-runner'})
        after = dict(before, **{'svc-webchat': '11.svc-webchat', 'svc-job-runner': '14.svc-job-runner'})
        solo.unchanged_services(before, after, {'svc-webchat', 'svc-job-runner'})
        after['svc-watchdog'] = '99.svc-watchdog'
        with self.assertRaisesRegex(CheckFailure, '3.svc-watchdog'):
            solo.unchanged_services(before, after, {'svc-webchat', 'svc-job-runner'})


class PrePinWaitRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.state = self.root / 'conductor/state'
        self.state.mkdir(parents=True)
        self.folder = self.root / 'release'
        self.folder.mkdir()
        self.path = self.folder / 'release.json'
        self.candidate = self.folder / 'candidate'
        self.candidate.mkdir()
        (self.candidate / 'webbob-build.json').write_text(json.dumps(dict(sha='c' * 40)))
        originals, snapshots = {}, {}
        for name in ('webchat', 'dispatch'):
            for collection, base, prefix in ((originals, self.root, 'old-'), (snapshots, self.folder, 'previous-')):
                target = base / (prefix + name)
                target.mkdir()
                (target / 'webbob-build.json').write_text(json.dumps(dict(sha='b' * 40)))
                collection[name] = str(target)
            (self.state / (name + '-code-root')).write_text(originals[name] + '\n')
        self.pins = {name: (self.state / (name + '-code-root')).read_text() for name in originals}
        self.record = dict(sha='c' * 40, previous='b' * 40, rollback=str(self.folder), snapshots=snapshots,
            snapshot_hashes={name: solo.source_digest(Path(path)) for name, path in snapshots.items()},
            original_pins=originals, at=1, runner_refresh=dict(required=True,
                prior=dict(pid=123, sha='b' * 40, code_root=originals['dispatch'], screen='123.svc-job-runner')))
        self.running = Path(originals['dispatch'])
        self.refreshes = 0

    @contextmanager
    def refresh(self, _root, _pins, _intent):
        self.refreshes += 1
        required = self.record['runner_refresh']['required']
        if required:
            self.running = None
        yield dict(required=required)
        self.fail('Failed pre-pin wait must skip normal post-yield startup')

    def start(self, _root, target):
        self.running = Path(target)
        return dict(sha='b' * 40, code_root=str(target))

    def versions(self, _root, expected):
        for name in ('webchat', 'dispatch'):
            target = Path((self.state / (name + '-code-root')).read_text().strip())
            if json.loads((target / 'webbob-build.json').read_text())['sha'] != expected:
                raise RuntimeError('Fixture version differs')
        return {name: dict(sha=expected) for name in ('local', 'public')}

    def attempt(self, *, restore_fails=False, change_pin=False):
        def failed_wait(_before):
            if change_pin:
                (self.state / 'dispatch-code-root').write_text(str(self.root / 'foreign') + '\n')
            raise CheckFailure('finite pass still active; saved inventory')
        with patch.object(runner, 'refresh', side_effect=self.refresh), \
                patch.object(runner, 'drain'), \
                patch.object(runner, 'start', side_effect=RuntimeError('restore fixture failure') if restore_fails else self.start) as start, \
                patch.object(runner, 'matches', side_effect=lambda _root, target: self.running == Path(target)), \
                patch.object(solo, 'settle_transient_services', side_effect=failed_wait), \
                patch('runtime.screen_sessions', return_value={'svc-conductor-pass': '9.svc-conductor-pass'}), \
                patch.object(solo, 'versions', side_effect=self.versions), \
                patch.object(solo, 'require_disk_space'), patch.object(solo, 'release_recovery'), \
                patch.object(solo, 'run') as web_process_command:
            with self.assertRaises((CheckFailure, RuntimeError)) as error:
                solo.transaction(self.root, self.record, self.path,
                    lambda: solo.restart(self.root, {name: self.candidate for name in self.pins}),
                    Mock(side_effect=AssertionError('Live checks must not run')))
            web_process_command.assert_not_called()
        return start, error.exception

    def assert_pins_unchanged(self):
        for name, expected in self.pins.items():
            self.assertEqual((self.state / (name + '-code-root')).read_text(), expected)

    def test_timeout_restores_required_runner_and_transaction_clears_recovery(self):
        start, error = self.attempt()
        start.assert_called_once_with(self.root, Path(self.pins['dispatch'].strip()))
        self.assertEqual(self.refreshes, 1)
        self.assertEqual(self.running, Path(self.pins['dispatch'].strip()))
        self.assertIsInstance(error, CheckFailure)
        self.assertEqual(str(error), 'finite pass still active; saved inventory')
        self.assert_pins_unchanged()
        saved = json.loads(self.path.read_text())
        self.assertEqual(saved['status'], 'ROLLED_BACK')
        self.assertFalse(saved['rollback_restart_needed'])
        self.assertIn('finite pass still active', saved['failure'])
        self.assertIsNone(journal.pending(self.root))

    def test_failed_restoration_preserves_both_errors_and_pending_recovery(self):
        start, error = self.attempt(restore_fails=True)
        self.assertEqual(start.call_count, 2)  # activation and transaction recovery
        self.assertIsNone(self.running)
        self.assert_pins_unchanged()
        saved = json.loads(self.path.read_text())
        for field in ('failure', 'rollback_error'):
            self.assertIn('finite pass still active', saved[field])
            self.assertIn('restore fixture failure', saved[field])
        self.assertIsNotNone(journal.pending(self.root))

    def test_originally_disabled_runner_is_not_enabled_on_timeout(self):
        self.record['runner_refresh'] = dict(required=False, prior=None)
        self.running = None
        start, _error = self.attempt()
        start.assert_not_called()
        self.assertIsNone(self.running)
        self.assert_pins_unchanged()
        self.assertTrue(json.loads(self.path.read_text())['rolled_back'])
        self.assertIsNone(journal.pending(self.root))

    def test_changed_pin_refuses_runner_restoration_and_retains_journal(self):
        start, error = self.attempt(change_pin=True)
        start.assert_not_called()
        self.assertIn('Pins changed during pre-restart wait', str(error))
        self.assertIsNotNone(journal.pending(self.root))


class PostStartupInventoryTests(unittest.TestCase):
    def setUp(self):
        PrePinWaitRecoveryTests.setUp(self)

    def restart(self, final):
        before = {'svc-webchat': '1.svc-webchat', 'svc-reviewer': '2.svc-reviewer'}
        after_web = dict(before, **{'svc-webchat': '11.svc-webchat'})
        observations = [before, after_web, final]
        def inventory():
            # Every observation, including the post-runner one, remains under
            # the supervisor lock; a different open description cannot take it.
            import fcntl
            with (self.root / 'conductor/locks/supervisor.lock').open('a') as handle:
                with self.assertRaises(BlockingIOError):
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return observations.pop(0)
        prior = self.record['runner_refresh']['prior']
        with patch.object(journal, 'permit_restart'), \
                patch.object(journal, 'pending', return_value=dict(record=self.record)), \
                patch.object(runner, 'observe', return_value=prior), patch.object(runner, 'drain'), \
                patch.object(runner, 'stop', return_value=prior), \
                patch.object(runner, 'start', return_value=dict(sha='c' * 40, code_root=str(self.candidate))) as start, \
                patch('runtime.screen_sessions', side_effect=inventory), \
                patch.object(solo.subprocess, 'run', return_value=Mock(returncode=1, stdout='')), \
                patch.object(solo, 'run'), \
                patch('urllib.request.urlopen', return_value=nullcontext(Mock(status=200, headers={'X-Bob-Webchat': '1'}))):
            try:
                return solo.restart(self.root, {name: self.candidate for name in self.pins})
            finally:
                start.assert_called_once_with(self.root, self.candidate)
                self.assertEqual(observations, [])

    def test_final_inventory_is_verified_after_the_runner_starts(self):
        final = {'svc-webchat': '11.svc-webchat', 'svc-reviewer': '2.svc-reviewer',
                 'svc-job-runner': '44.svc-job-runner'}
        result = self.restart(final)
        self.assertEqual(result['after'], final)
        self.assertEqual(result['runner']['after']['sha'], 'c' * 40)

    def test_persistent_service_loss_during_runner_startup_is_not_success(self):
        for replacement in (None, '99.svc-reviewer'):
            final = {'svc-webchat': '11.svc-webchat', 'svc-job-runner': '44.svc-job-runner'}
            if replacement:
                final['svc-reviewer'] = replacement
            with self.subTest(replacement=replacement):
                with self.assertRaisesRegex(CheckFailure, '2.svc-reviewer'):
                    self.restart(final)


if __name__ == '__main__':
    unittest.main()
