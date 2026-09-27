"""Integration regressions for the dispatch journal in provider context."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from live_status_snapshot import build_live_status_snapshot, encode_snapshot, provider_health
from providers import Providers
from test_worker_activity import PS, SCREENS
from worker_activity import parse_processes


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "conductor/state").mkdir(parents=True)
        self.queue = self.root / "conductor/state/queue.jsonl"
        sampler = patch("live_status_snapshot.process_table", return_value={})
        sampler.start()
        self.addCleanup(sampler.stop)

    def snapshot(self):
        with patch("live_status_snapshot._screen_sessions", return_value={"svc-job-runner": "123.svc-job-runner"}), \
                patch("ops_panel.load_live_ops", return_value={"live_ops": {"now_line": "Handback drill r10: running screen drill-r10"}}):
            return build_live_status_snapshot(self.root)

    def test_latest_dispatch_states_workers_and_torn_tail_are_read_only(self):
        rows = [dict(id="task-a", status="queued", requested_worker="cursor", updated_at=1),
                dict(id="task-a", status="running", worker="cursor", updated_at=3),
                dict(id="task-b", status="succeeded", worker="gemini", updated_at=2),
                dict(id="task-c", status="failed", worker="minimax", updated_at=4),
                dict(id="task-d", status="queued", requested_worker="claude", updated_at=5)]
        original = "\n".join(json.dumps(row) for row in rows) + '\n{"id":"torn'
        self.queue.write_text(original)
        snap = self.snapshot()
        self.assertEqual(snap["queue_counts"], dict(queued=1, claimed=1, done=1, failed=1))
        self.assertEqual(snap["queue_jobs"]["claimed"][0]["job_id"], "task-a")
        self.assertEqual(snap["queue_jobs"]["queued"][0]["worker"], "claude")
        self.assertEqual(snap["lane_locks"]["cursor"]["active_jobs"], ["task-a"])
        self.assertEqual(self.queue.read_text(), original)
        self.assertIsNone(snap["now_line"])

    def test_recovered_generation_overrides_old_failure_and_ignores_drills(self):
        path = self.root / "conductor/webchat/sessions/provider-health.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"gemini": {"reason": "network", "retry_at": 500, "checked_at": 100},
                                   "minimax": {"reason": "network", "retry_at": 500, "checked_at": 100, "probe": "ok"}}))
        log = self.root / "logs/webchat-failover.log"
        log.parent.mkdir()
        log.write_text('\n'.join(json.dumps(r) for r in [
            dict(provider="gemini", event="success", timestamp=200, context="production"),
            dict(provider="gemini", event="failure", timestamp=300, context="live-drill", reason="network"),
            dict(provider="minimax", event="probe", result="ok", timestamp=400, context="production")]))
        health = provider_health(self.root, now=450)
        self.assertEqual(health["gemini"]["state"], "ready")
        self.assertIsNone(health["gemini"]["reason"])
        self.assertEqual(health["minimax"]["state"], "cooldown")
        self.assertEqual(provider_health(self.root, now=600)["minimax"]["state"], "recovery_due")
        self.assertEqual(health["cursor"]["state"], "unchecked")

    def test_successful_harvest_recovery_is_done_and_counts_include_omitted_rows(self):
        rows = [dict(job_id=f"job-{i}", state="harvested", outcome="result",
                     recovery="harvest_complete", timestamp=i) for i in range(30)]
        (self.root / "conductor/jobs.jsonl").write_text("\n".join(json.dumps(row) for row in rows))
        snap = self.snapshot()
        self.assertEqual(snap["queue_counts"]["done"], 30)
        self.assertEqual(len(snap["queue_jobs"]["done"]), 24)
        self.assertEqual(snap["queue_jobs"]["done"][0]["job_id"], "job-29")
        self.assertEqual(snap["queue_jobs"]["failed"], [])

    def test_live_lane_work_overrides_cached_ready_and_survives_prompt_budget(self):
        (self.root / "conductor/lanes.json").write_text(json.dumps({name: dict(state="ready") for name in ("claude", "codex")}))
        self.queue.write_text(json.dumps(dict(id="old-private-id", status="succeeded", updated_at=1)))
        with patch("live_status_snapshot._screen_sessions", return_value=SCREENS), \
                patch("live_status_snapshot.process_table", return_value=parse_processes(PS)):
            snap = build_live_status_snapshot(self.root)
        self.assertEqual(snap["queue_counts"]["claimed"], 0)
        self.assertEqual(snap["work_counts"], dict(running=4, paused=0, claimed=0, unverified=0))
        for name in ("claude", "codex"):
            self.assertEqual(snap["lane_locks"][name]["state"], "busy")
            self.assertEqual(snap["lane_locks"][name]["cached_state"], "ready")
        self.assertIn("4 live worker(s) running", snap["plain_summary"])
        self.assertEqual(sum(row["role"] == "worker" for row in snap["screen_lanes"]), 4)
        snap["queue_jobs"]["done"] *= 100
        payload, clipped = encode_snapshot(snap, 8000)
        self.assertTrue(clipped)
        self.assertEqual(json.loads(payload)["work"], snap["work"])

    def test_failed_inspection_is_not_reported_as_an_empty_successful_check(self):
        with patch("live_status_snapshot._screen_sessions", return_value=None), \
                patch("live_status_snapshot.process_table", return_value=None):
            snap = build_live_status_snapshot(self.root)
        self.assertEqual(snap["inspection"], dict(screens_available=False, processes_available=False))

    def test_status_does_not_refresh_or_write_live_ledger_when_dashboard_is_stale(self):
        dashboard = self.root / "conductor/dashboard.json"
        dashboard.write_text(json.dumps(dict(live_ops=dict(generated_at="2020-01-01T00:00:00+00:00", running_jobs=[]))))
        before = {str(path): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        with patch("ops_panel.inline_live_ops") as refresh, \
                patch("live_status_snapshot._screen_sessions", return_value={}):
            snap = build_live_status_snapshot(self.root)
        refresh.assert_not_called()
        self.assertTrue(snap["live_ops_stale"])
        self.assertEqual(before, {str(path): path.read_bytes() for path in self.root.rglob("*") if path.is_file()})

    def test_prompt_budget_keeps_valid_json_current_jobs_health_and_disk(self):
        self.queue.write_text(json.dumps(dict(id="current-task", status="running", worker="codex")) + "\n")
        snap = self.snapshot()
        snap["queue_jobs"]["done"] = [dict(job_id="old-job-" + str(i), recovery="x" * 160) for i in range(100)]
        payload, clipped = encode_snapshot(snap, 8000)
        parsed = json.loads(payload)
        self.assertTrue(clipped)
        self.assertLessEqual(len(payload), 8000)
        self.assertEqual(parsed["service_health"], snap["service_health"])
        self.assertEqual(parsed["disk"], snap["disk"])
        self.assertEqual(parsed["queue_jobs"]["claimed"][0]["job_id"], "current-task")
        provider = Providers(self.root, lambda text: text)
        self.addCleanup(provider.close)
        for lite in (True, False):
            with patch("live_status_snapshot.build_live_status_snapshot", return_value=snap):
                parts = provider.snapshot(lite=lite)
            part = next(p for p in parts if p["path"].startswith("live_status_snapshot"))
            self.assertIn("disk", json.loads(part["text"]))


if __name__ == "__main__":
    unittest.main()
