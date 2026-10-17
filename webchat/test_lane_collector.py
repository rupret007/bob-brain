"""Lane collector fixtures: screen -ls and ps output only."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lane_collector import collect_bob_lanes, prompt_slug
from test_worker_activity import PS, SCREENS
from worker_activity import parse_processes


class LaneCollectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "logs").mkdir()
        (self.root / "reviews").mkdir()
        (self.root / "conductor/state").mkdir(parents=True)

    def collect(self, *, now=100_000):
        with patch("live_status_snapshot._screen_sessions", return_value=SCREENS), \
                patch("worker_activity.process_table", return_value=parse_processes(PS)):
            return collect_bob_lanes(self.root, now=now, sessions=SCREENS, processes=parse_processes(PS))

    def test_live_lanes_map_llm_project_task_and_elapsed(self):
        (self.root / "logs/webbob-clean-prompt.txt").write_text(
            "Project: Web Bob\nTask: Fix chat replies for overnight lanes.\nWrite reviews/WEBBOB-LANES-READY-0927.md\n")
        (self.root / "logs/webbob-clean.log").write_text("working\n")
        (self.root / "reviews/WEBBOB-LANES-READY-0927.md").write_text("# ready\n")
        bob = self.collect()
        live = {row["screen"]: row for row in bob["live"]}
        self.assertEqual(len(live), 4)
        clean = live["lane-webbob-clean"]
        self.assertEqual(clean["llm"], "codex")
        self.assertEqual(clean["model"], "gpt-fixture")
        self.assertEqual(clean["project"], "Web Bob")
        self.assertIn("Fix chat replies", clean["task"])
        self.assertEqual(clean["elapsed_seconds"], 18 * 60)
        self.assertEqual(clean["result_path"], "reviews/WEBBOB-LANES-READY-0927.md")

    def test_finished_lane_within_twelve_hours(self):
        prompt = self.root / "logs/webbob-old-prompt.txt"
        prompt.write_text("Project: WebJam\nTask: Ship the login fix.\nWrite reviews/WEBJAM-DONE.md\n")
        review = self.root / "reviews/WEBJAM-DONE.md"
        review.write_text("done\n")
        now = 200_000.0
        for path in (prompt, review):
            path.touch()
        import os

        os.utime(prompt, (now - 3600, now - 3600))
        os.utime(review, (now - 1800, now - 1800))
        with patch("live_status_snapshot._screen_sessions", return_value={}), \
                patch("worker_activity.process_table", return_value={}):
            bob = collect_bob_lanes(self.root, now=now, sessions={}, processes={})
        self.assertEqual(len(bob["live"]), 0)
        self.assertEqual(len(bob["finished_recent"]), 1)
        finished = bob["finished_recent"][0]
        self.assertEqual(finished["screen"], "lane-webbob-old")
        self.assertEqual(finished["project"], "WebJam")
        self.assertEqual(finished["result_path"], "reviews/WEBJAM-DONE.md")
        self.assertEqual(finished['state'], 'not_observed')
        self.assertIsNone(finished['finished_at'])
        self.assertEqual(finished['last_activity_at'], now - 1800)

    def test_failed_screen_inspection_does_not_infer_ended_lanes(self):
        (self.root / 'logs/webbob-old-prompt.txt').write_text('Task: Fix the login.\n')
        observed = dict(sessions={}, work=[], inspection=dict(screens_available=False, processes_available=True))
        bob = collect_bob_lanes(self.root, observed=observed)
        self.assertEqual(bob['finished_recent'], [])

    def test_archived_lane_diagnostic_does_not_claim_completion(self):
        from reply_authority import _lane_line
        line = _lane_line(dict(screen='lane-old', task='Fix login', state='not_observed', elapsed_seconds=60))
        self.assertIn('outcome unverified', line)
        self.assertIn('last activity', line)
        self.assertNotIn('finished', line)
        self.assertNotIn('session open', line)

    def test_prompt_slug_strips_dates(self):
        self.assertEqual(prompt_slug("proj-adoptiq-2004-prompt"), "lane-proj-adoptiq")


if __name__ == "__main__":
    unittest.main()
