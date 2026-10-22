"""Screen policy regressions using snapshots and mocks; no live restarts."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import deploy_texting_2256 as deploy


class ScreenIsolation(unittest.TestCase):
    def setUp(self):
        self.peers = {name: f"{index}.{name}" for index, name in enumerate((
            "svc-reviewer", "svc-dashboard-updater", "svc-disk-watch",
            "svc-watchdog", "svc-webbob-reviewers", "svc-future-durable"), start=10)}

    def test_each_durable_peer_identity_change_fails(self):
        for name in self.peers:
            with self.subTest(name=name):
                after = dict(self.peers, **{name: "999." + name})
                result = deploy.screen_isolation(self.peers, after)
                self.assertFalse(result["other_screens_unchanged"])
                self.assertEqual(set(result["changed_durable_screens"]), {name})

    def test_each_durable_peer_disappearance_fails(self):
        for name in self.peers:
            with self.subTest(name=name):
                after = {key: value for key, value in self.peers.items() if key != name}
                result = deploy.screen_isolation(self.peers, after)
                self.assertFalse(result["other_screens_unchanged"])
                self.assertIsNone(result["changed_durable_screens"][name]["after"])

    def test_optional_and_nondurable_churn_passes(self):
        for name in ("svc-project-tick", "svc-conductor-pass", "lane-project-codex",
                     deploy.OWN_LANE, "coding-agent-123", "adhoc-shell"):
            present = dict(self.peers, **{name: "111." + name})
            changed = dict(self.peers, **{name: "222." + name})
            for before, after in ((present, self.peers), (self.peers, present), (present, changed)):
                with self.subTest(name=name, before=before, after=after):
                    result = deploy.screen_isolation(before, after)
                    self.assertTrue(result["other_screens_unchanged"])
                    self.assertEqual(result["protected_screens"], self.peers)
                    self.assertIn(name, result["ignored_screens"])

    def test_restarted_pair_identity_change_passes(self):
        before = dict(self.peers, **{name: "111." + name for name in deploy.RESTARTED_SCREENS})
        after = dict(self.peers, **{name: "222." + name for name in deploy.RESTARTED_SCREENS})
        self.assertTrue(deploy.screen_isolation(before, after)["other_screens_unchanged"])

    def test_new_durable_peer_does_not_change_existing_peers(self):
        after = dict(self.peers, **{"svc-new": "123.svc-new"})
        self.assertTrue(deploy.screen_isolation(self.peers, after)["other_screens_unchanged"])

    def test_authoritative_attempt6_optional_exit_passes(self):
        original = dict(other_screens_unchanged=False, before=dict(self.peers, **{"svc-project-tick": "111.svc-project-tick"}), after=self.peers)
        self.assertFalse(original["other_screens_unchanged"])
        result = deploy.screen_isolation(original["before"], original["after"])
        self.assertTrue(result["other_screens_unchanged"])
        self.assertEqual(len(result["protected_screens"]), 6)
        self.assertIsNone(result["ignored_screens"]["svc-project-tick"]["after"])

    def test_restart_uses_original_raw_snapshots_and_records_policy(self):
        before = dict(self.peers, **{"svc-project-tick": "111.svc-project-tick"})
        raw = dict(before=before, after=self.peers, other_screens_unchanged=False,
                   restarted_services=["webchat", "job-runner"], permitted_replay_exits=[])
        pins = dict(webchat=Path("candidate"), dispatch=Path("candidate"))
        with patch.object(deploy, "restart_services", return_value=raw) as restart:
            result = deploy.restart(Path("root"), pins, expected_exits=["cancelled-job-id"])
        restart.assert_called_once_with(Path("root"), pins)
        self.assertTrue(result["other_screens_unchanged"])
        self.assertFalse(result["legacy_other_screens_unchanged"])
        self.assertEqual(result["cancelled_replay_job_ids"], ["cancelled-job-id"])
        self.assertEqual(result["before"], before)
        self.assertEqual(result["after"], self.peers)

    def test_expected_exits_cannot_exempt_a_durable_screen(self):
        raw = dict(before=self.peers, after={}, other_screens_unchanged=False)
        with patch.object(deploy, "restart_services", return_value=raw):
            result = deploy.restart(Path("root"), {}, expected_exits=list(self.peers))
        self.assertFalse(result["other_screens_unchanged"])
        self.assertEqual(set(result["changed_durable_screens"]), set(self.peers))

    def test_restart_error_is_not_masked(self):
        with patch.object(deploy, "restart_services", side_effect=RuntimeError("unhealthy restart")):
            with self.assertRaisesRegex(RuntimeError, "unhealthy restart"):
                deploy.restart(Path("root"), {})

    def test_own_lane_and_service_screens_pass_preflight(self):
        screens = dict(self.peers, **{deploy.OWN_LANE: "123." + deploy.OWN_LANE})
        with patch("runtime.screen_sessions", return_value=screens):
            self.assertEqual(deploy.check_lane_isolation(), screens)

    def test_other_webbob_lane_blocks_preflight(self):
        screens = dict(self.peers, **{"lane-webbob-other": "123.lane-webbob-other"})
        with patch("runtime.screen_sessions", return_value=screens):
            with self.assertRaisesRegex(RuntimeError, "Other active Web Bob lanes"):
                deploy.check_lane_isolation()


if __name__ == "__main__":
    unittest.main(verbosity=2)
