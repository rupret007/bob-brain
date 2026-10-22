"""An operator stop arriving during admission still prevents a restart."""
import unittest
from unittest.mock import patch

import test_storypool_actions as harness


class ExecutionGuardTests(unittest.TestCase):
    setUp = harness.GuardedAdapterTests.setUp

    def test_drain_during_claim_or_audit_stops_restart(self):
        draining = self.modules['cluster.control_plane.node_control'].is_draining
        draining.side_effect = [False, True]
        with patch('platform.system', return_value='Linux'):
            with self.assertRaises(RuntimeError):
                self.run({'kind': 'kick', 'service': 'dashboard'}, 'approval')
        self.assertEqual(draining.call_count, 2)
        self.assertTrue(all(call.args[0][0] == 'git' for call in self.process.call_args_list))

    def test_maintenance_during_final_renewal_stops_restart(self):
        def renew():
            if self.lease.renew.call_count == 2:
                (self.root / 'conductor').mkdir()
                (self.root / 'conductor/MAINTENANCE').touch()
        self.lease.renew.side_effect = renew
        with patch('platform.system', return_value='Linux'):
            with self.assertRaises(RuntimeError):
                self.run({'kind': 'kick', 'service': 'watchdog'}, 'approval')
        self.assertEqual(self.lease.renew.call_count, 2)
        self.assertTrue(all(call.args[0][0] == 'git' for call in self.process.call_args_list))


if __name__ == '__main__':
    unittest.main()
