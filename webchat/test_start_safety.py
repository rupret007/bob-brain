"""Private launcher checks: no actual screen, server, network or credential use."""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location('webbob_start_safety', Path(__file__).with_name('start.py'))
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class StartSafetyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='webbob-start-safety-')
        self.addCleanup(temporary.cleanup)
        self.here = Path(temporary.name)
        self.addCleanup(os.umask, os.umask(0o077))
        contexts = contextlib.ExitStack()
        self.addCleanup(contexts.close)
        self.output = contexts.enter_context(contextlib.redirect_stdout(io.StringIO()))
        contexts.enter_context(patch.object(launcher, 'HERE', self.here))
        contexts.enter_context(patch.dict(os.environ, {'BOB_ROOT': str(self.here)}, clear=True))
        self.health = contexts.enter_context(patch.object(launcher, 'healthy', return_value=False))
        self.sleep = contexts.enter_context(patch.object(launcher.time, 'sleep'))
        self.run = contexts.enter_context(patch.object(launcher.subprocess, 'run'))

    def inventory(self, stdout, code=0, stderr=''):
        self.run.return_value = subprocess.CompletedProcess(['/usr/bin/screen', '-ls'], code, stdout, stderr)

    def assert_only_inventory(self):
        self.assertEqual([call.args[0] for call in self.run.call_args_list], [['/usr/bin/screen', '-ls']])

    def test_healthy_server_needs_no_screen_operation(self):
        self.health.return_value = True
        self.assertEqual(launcher.main(), 0)
        self.run.assert_not_called()

    def test_slow_existing_server_is_never_quit_or_replaced(self):
        for state in ('Detached', 'Attached', 'Dead ???'):
            with self.subTest(state=state):
                self.run.reset_mock()
                self.inventory(f'There is a screen on:\n\t4321.svc-webchat\t({state})\n1 Socket in /fixture.\n')
                self.assertEqual(launcher.main(), 1)
                self.assert_only_inventory()

    def test_unavailable_inventory_cannot_start_or_quit(self):
        for code, stdout, stderr in ((1, '', 'Permission denied'), (0, '', ''),
                                     (2, 'No Sockets found in /fixture.', ''),
                                     (1, '1 Socket in /fixture.', '')):
            with self.subTest(code=code, stdout=stdout):
                self.run.reset_mock()
                self.inventory(stdout, code, stderr)
                self.assertEqual(launcher.main(), 1)
                self.assert_only_inventory()

    def test_inventory_timeout_has_no_launch_side_effect(self):
        self.run.side_effect = subprocess.TimeoutExpired('screen', 5)
        with self.assertRaises(subprocess.TimeoutExpired):
            launcher.main()
        self.assert_only_inventory()

    def assert_start(self, stdout, code=0, drills='0'):
        self.inventory(stdout, code)
        self.health.side_effect = [False, True]
        self.assertEqual(launcher.main(), 0)
        self.assertEqual([call.args[0] for call in self.run.call_args_list], [
            ['/usr/bin/screen', '-ls'],
            ['/usr/bin/screen', '-dmS', 'svc-webchat', '/bin/bash', str(self.here / 'run.sh')],
        ])
        self.assertEqual(self.run.call_args_list[-1].kwargs['env']['BOB_WEBCHAT_DRILLS'], drills)

    def test_confirmed_empty_inventory_starts_without_drills(self):
        self.assert_start('No Sockets found in /fixture.\n', 1)

    def test_other_sessions_are_preserved(self):
        self.assert_start('There is a screen on:\n\t1234.svc-watchdog\t(Detached)\n1 Socket in /fixture.\n')

    def test_explicit_fixture_drills_are_preserved(self):
        os.environ['BOB_WEBCHAT_DRILLS'] = '1'
        self.assert_start('No Sockets found in /fixture.\n', 1, drills='1')

    def test_failed_launch_is_not_retried(self):
        self.run.side_effect = [subprocess.CompletedProcess('screen', 1, 'No Sockets found in /fixture.', ''),
                                subprocess.CalledProcessError(1, 'screen')]
        with self.assertRaises(subprocess.CalledProcessError):
            launcher.main()
        self.assertEqual(self.run.call_count, 2)

    def test_startup_health_wait_stays_bounded(self):
        self.inventory('No Sockets found in /fixture.\n', 1)
        self.assertEqual(launcher.main(), 1)
        self.assertEqual(self.run.call_count, 2)
        self.assertEqual(self.health.call_count, 41)
        self.assertEqual(self.sleep.call_count, 40)


if __name__ == '__main__':
    unittest.main()
