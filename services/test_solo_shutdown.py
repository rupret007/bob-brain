"""The watchdog and launchd cannot resurrect workers during solo operation."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import runtime
import state


class SoloShutdownTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.core = self.root / 'conductor'
        self.core.mkdir()
        (self.core / 'SOLO-WORKER').touch()
        for module in (state, runtime):
            for key, value in (('ROOT', self.root), ('CONDUCTOR', self.core)):
                p = patch.object(module, key, value)
                p.start()
                self.addCleanup(p.stop)
        p = patch.object(runtime, 'HEARTBEATS', self.core / 'heartbeats')
        p.start()
        self.addCleanup(p.stop)

    def test_solo_only_disables_worker_and_reviewer(self):
        self.assertFalse(runtime.service_enabled('job-runner'))
        self.assertFalse(runtime.service_enabled('reviewer'))
        self.assertTrue(runtime.service_enabled('watchdog'))
        self.assertTrue(runtime.service_enabled('dashboard-updater'))
        (self.core / 'SOLO-WORKER').unlink()
        self.assertTrue(runtime.service_enabled('job-runner'))

    def test_supervisor_does_not_restart_stopped_workers(self):
        screens = {'svc-watchdog': 'one', 'svc-dashboard-updater': 'two'}
        with patch.object(runtime, 'screen_sessions', return_value=screens), \
             patch.object(runtime, 'start_screen') as start:
            runtime.ensure_services()
        start.assert_not_called()

    def test_direct_cycles_cannot_invoke_model_or_dispatch(self):
        with patch.object(runtime, 'jobs', side_effect=AssertionError('review attempted')), \
             patch('web_dispatch.tick', side_effect=AssertionError('dispatch attempted')):
            runtime.reviewer_cycle()
            runtime.runner_cycle()


if __name__ == '__main__':
    unittest.main()
