"""Jobs rendering contract: real journals and deterministic host observations."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jobs_view import build_jobs_view, result_text
from test_worker_activity import PS, SCREENS
from worker_activity import parse_processes


class JobsViewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for module, value in (("_screen_sessions", SCREENS), ("process_table", parse_processes(PS))):
            mock = patch("live_status_snapshot." + module, return_value=value)
            mock.start()
            self.addCleanup(mock.stop)

    def write(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)
        return path

    def queue(self, *rows, journal="conductor/state/queue.jsonl"):
        return self.write(journal, "".join(json.dumps(row) + "\n" for row in rows))

    def test_live_lanes_empty_queue_ignore_poisoned_dashboard_and_handback(self):
        poison = "Handback drill r10-2: running screen drill-r10-2 · abc1234 · Web Bob R38"
        self.write("conductor/dashboard.json", json.dumps({"live_ops": {"now_line": poison, "running_jobs": [{"plain_now": poison}]}}))
        self.write("conductor/state/NOW.md", poison)
        self.write("conductor/handback/HANDBACK-SUMMARY.md", poison)
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        view = build_jobs_view(self.root, now=10000)
        self.assertEqual(len(view["working"]), 4)
        clean = next(row for row in view["working"] if row["key"] == "lane-webbob-clean")
        self.assertEqual(clean["project"], "Web Bob")
        self.assertEqual(clean["elapsed_seconds"], 1080)
        self.assertEqual(clean["models"], ["Codex · gpt-fixture"])
        self.assertEqual(view["recently_finished"], [])
        for value in ("Handback", "abc1234", "R38", "command", "Private", "sha"):
            self.assertNotIn(value, json.dumps(view))
        self.assertEqual(before, {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_queue_claim_and_screen_are_one_card_with_queue_description(self):
        self.queue(dict(id="job", status="running", title="Fix the Web Bob login button", worker="codex", pid=201, started_at=9000))
        view = build_jobs_view(self.root, now=10000)
        self.assertEqual(len(view["working"]), 4)
        row = next(row for row in view["working"] if row["key"] == "lane-webbob-clean")
        self.assertEqual(row["task"], "Fix the Web Bob login button")
        self.assertEqual(row["project"], "Web Bob")

    def test_multiple_workers_in_a_lane_are_one_card(self):
        processes = parse_processes(PS + "\n204 201 05:00 S claude --model opus -p Task\n")
        with patch("live_status_snapshot.process_table", return_value=processes):
            view = build_jobs_view(self.root)
        self.assertEqual(len(view["working"]), 4)
        row = next(row for row in view["working"] if row["key"] == "lane-webbob-clean")
        self.assertEqual(row["models"], ["Codex · gpt-fixture", "Claude · opus"])

    def test_standalone_task_header_supplies_project_and_task(self):
        with patch("live_status_snapshot._screen_sessions", return_value={}), patch("live_status_snapshot.process_table", return_value=parse_processes(
                "10 1 04:00 S codex exec Follow-up 4 on draft/webbob-clean-0927: redesign Web Bob's Jobs tab. Private details\n")):
            row = build_jobs_view(self.root)["working"][0]
        self.assertEqual(row["project"], "Web Bob")
        self.assertEqual(row["task"], "Redesign Web Bob's Jobs tab")
        self.assertNotIn("Private", json.dumps(row))

    def test_finished_last_five_use_terminal_time_not_delivery_time(self):
        rows = [dict(id=f"job-{i}", status="succeeded", title=f"WebJam fix {i}", finished_at=100 + i, result=f"Actual result {i}") for i in range(8)]
        self.queue(*rows, dict(rows[0], delivered_at=1000, updated_at=1000),
                   dict(id="drill-r10-2", status="succeeded", finished_at=2000, result="abc1234"),
                   dict(id="waiting", status="queued", updated_at=3000))
        view = build_jobs_view(self.root, now=4000)
        self.assertEqual([row["key"] for row in view["recently_finished"]], [f"job-{i}" for i in (7, 6, 5, 4, 3)])
        self.assertEqual(view["details"]["queued"], 1)
        self.assertTrue(all(row["result_url"] for row in view["recently_finished"]))
        self.assertEqual(result_text(self.root, "job-7")["text"], "Actual result 7")
        self.assertIsNone(result_text(self.root, "drill-r10-2"))

    def test_result_links_are_backed_by_files_or_saved_text_and_safe_urls(self):
        path = self.write("job/RESULT.md", "Saved report")
        self.queue(dict(job_id="webjam-fix", state="harvested", result_path=str(path), pr_url="https://github.com/example/repo/pull/12"),
                   dict(job_id="missing", state="harvested", result_path="gone.md", recovery="deliverables persisted", pr_url="javascript:alert(1)"),
                   dict(job_id="outside", state="harvested", result_path="../outside.md", result_url="https://user:password@example.com/private"),
                   journal="conductor/jobs.jsonl")
        rows = {row["key"]: row for row in build_jobs_view(self.root)["recently_finished"]}
        self.assertEqual(result_text(self.root, "webjam-fix")["text"], "Saved report")
        self.assertTrue(rows["webjam-fix"]["pr_url"])
        self.assertIsNone(rows["missing"]["result_url"])
        self.assertIsNone(rows["missing"]["pr_url"])
        self.assertIsNone(rows["outside"]["result_url"])
        self.assertIsNone(rows["outside"]["external_result_url"])
        self.assertIsNone(result_text(self.root, "missing"))

    def test_symlink_result_outside_root_is_not_read(self):
        with tempfile.TemporaryDirectory() as outside:
            secret = Path(outside) / "private.md"
            secret.write_text("private")
            link = self.root / "result.md"
            link.symlink_to(secret)
            self.queue(dict(id="bad", status="succeeded", result_path=str(link)))
            self.assertIsNone(result_text(self.root, "bad"))

    def test_stale_claims_do_not_turn_into_live_cards_and_missing_checks_are_honest(self):
        self.queue(dict(id="old", status="running", pid=999, worker="codex", claimed_at=1))
        with patch("live_status_snapshot._screen_sessions", return_value={}), patch("live_status_snapshot.process_table", return_value={}):
            view = build_jobs_view(self.root)
        self.assertEqual(view["working"], [])
        self.assertEqual(view["details"]["unconfirmed"], 1)
        with patch("live_status_snapshot.process_table", return_value=None):
            view = build_jobs_view(self.root)
        self.assertFalse(view["inspection"]["processes_available"])
        self.assertEqual(len(view["working"]), 4)
        self.assertTrue(all(row["state"] == "unverified" for row in view["working"]))
        self.assertTrue(all(row["elapsed_seconds"] is None for row in view["working"]))

    def test_paused_and_failed_states_are_not_success(self):
        self.queue(dict(id="failed", status="failed", error="Check failed", finished_at=10))
        with patch("live_status_snapshot.process_table", return_value=parse_processes(PS.replace("24:00 S+", "24:00 T+"))):
            view = build_jobs_view(self.root)
        self.assertEqual(next(row for row in view["working"] if row["key"] == "lane-projects-push")["state"], "paused")
        self.assertEqual(view["recently_finished"][0]["state"], "failed")
        self.assertEqual(result_text(self.root, "failed")["text"], "Check failed")

    def test_health_and_cost_use_persisted_evidence(self):
        self.write("conductor/webchat/sessions/provider-health.json", json.dumps(dict(codex=dict(last_success=9500, checked_at=9500), minimax=dict(reason="rate limit", retry_at=11000, checked_at=9900))))
        self.queue(dict(call_id="1", cost_usd=None, reserved_usd=2), dict(call_id="1", cost_usd=1), dict(call_id="2", cost_usd=None, reserved_usd=.5), journal="conductor/ledger/minimax.jsonl")
        view = build_jobs_view(self.root, now=10000)
        health = {row["provider"]: row for row in view["details"]["health"]}
        self.assertEqual(health["Codex"]["state"], "ready")
        self.assertEqual(health["MiniMax"]["state"], "cooldown")
        self.assertEqual(health["Codex"]["age_seconds"], 500)
        self.assertEqual(view["details"]["costs"], [dict(provider="MiniMax", spent_usd=1, reserved_usd=.5)])


if __name__ == "__main__":
    unittest.main()
