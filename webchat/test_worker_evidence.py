"""Lane metadata must not become an inferred worker assignment."""
import unittest
from unittest.mock import patch

from test_webbob_replyq_1856 import SessionFixture
from task_dispatch import task_queue
from worker_activity import collect_work, parse_processes
from worker_evidence import _task


LANE = "lane-webbob-texting-disk-evidence-fix-2003"


class TaskEvidenceTests(unittest.TestCase):
    def test_bare_lane_and_service_metadata_are_not_tasks(self):
        for text in (LANE, "# " + LANE, "## `" + LANE + "` ##",
                     "# svc-deploy-check", "Task: " + LANE,
                     "Project: Web Bob\n# " + LANE,
                     "# " + LANE + "\n\nHistorical notes: Fix an old failure."):
            with self.subTest(text=text):
                self.assertIsNone(_task(text))

    def test_explicit_assignment_survives_a_lane_heading(self):
        for label in ("Task", "Goal", "Assignment"):
            with self.subTest(label=label):
                prompt = "# " + LANE + "\n\n" + label + ": Fix Web Bob checkpoint persistence.\n"
                self.assertEqual(_task(prompt), "Fix Web Bob checkpoint persistence")
        self.assertEqual(_task("Fix " + LANE + " checkpoint persistence"),
                         "Fix " + LANE + " checkpoint persistence")


class LaneAssignmentEvidenceTests(SessionFixture):
    def test_running_lane_without_assignment_uses_explicit_evidence_limit(self):
        logs = self.root / "logs"
        logs.mkdir()
        prompt = logs / (LANE.removeprefix("lane-") + "-prompt.txt")
        prompt.write_text("# " + LANE + "\n\nHistorical notes: Fix an old failure.\n")
        processes = parse_processes(
            "100 1 02:00 Ss SCREEN -dmS " + LANE + " bash\n"
            "101 100 01:59 S codex exec --model gpt-fixture Private prompt\n")
        work = collect_work({LANE: "100." + LANE}, [], processes, 10000, root=self.root)
        self.assertEqual(len(work), 1)
        self.assertEqual(work[0]["state"], "running")
        self.assertIsNone(work[0]["task"])
        with patch("worker_assignment.observe_work", return_value=dict(records={}, work=work)):
            answer = self.send("Use Gemini and MiniMax for ongoing jobs")
        records = task_queue.tasks(self.root)
        self.assertEqual(len(answer["task_ids"]), 2)
        for identifier in answer["task_ids"]:
            row = records[identifier]
            self.assertIn("original task prompt was not recorded", row["prompt"])
            self.assertIn("Do not invent the lane's exact assignment", row["prompt"])
            self.assertNotIn("Ongoing task:\n# " + LANE, row["prompt"])
            self.assertIsNone(row["source_job_id"])
        self.assertFalse(self.fake.calls)


if __name__ == "__main__":
    unittest.main()
