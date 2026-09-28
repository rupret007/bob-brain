"""The failed live status observation, plus truthfulness at its boundaries."""
import copy
import json
import unittest
from pathlib import Path

from integration_rubric import style_errors
from reply_authority import format_operational_reply

FIXTURE = json.loads(Path(__file__).with_name("fixtures").joinpath("texting_diagdump_0810.json").read_text())


class TextingStatusVoiceTests(unittest.TestCase):
    def setUp(self):
        self.snap = copy.deepcopy(FIXTURE["snapshot"])

    def reply(self, question=None):
        answer = format_operational_reply(self.snap, text=question or FIXTURE["message"])
        self.assertEqual(style_errors(answer), [])
        self.assertLessEqual(len(answer.split()), 120)
        return answer

    def test_exact_failed_turn_uses_short_natural_status(self):
        self.assertEqual(self.reply(), "Codex is working on Web Bob. Gemini and MiniMax have work waiting to run. Claude and Cursor are idle.")
        self.assertIn("raw diagnostic dump", style_errors(FIXTURE["bad_reply"]))

    def test_each_forbidden_diagnostic_fails_the_rubric(self):
        for text in ("model not reported", "queue_counts: 4", "The job runner has 4 queued jobs.",
                     "Codex is working; Gemini is waiting; MiniMax is waiting."):
            with self.subTest(text=text):
                self.assertIn("raw diagnostic dump", style_errors(text))

    def test_status_paraphrases_share_the_same_observation(self):
        for text in ("status", "What's running?", "How's everything going?",
                     "Status without internal IDs or raw diagnostics, please"):
            self.assertEqual(self.reply(text), self.reply())

    def test_pending_or_unverified_work_is_never_presented_as_running(self):
        for state in ("claimed", "unverified", "paused"):
            with self.subTest(state=state):
                self.snap["work"][0]["state"] = state
                answer = self.reply()
                self.assertNotIn("working on", answer)
                self.assertIn("Codex is paused" if state == "paused" else "Codex has activity I can't confirm yet", answer)
                self.assertIn("Gemini and MiniMax have work waiting to run", answer)

    def test_busy_or_unattributed_activity_is_not_idle_or_assigned(self):
        self.snap["work"][0]["assignment_recorded"] = False
        self.snap["lane_locks"]["claude"] = dict(state="busy")
        answer = self.reply()
        self.assertIn("Codex and Claude have activity I can't confirm yet", answer)
        self.assertNotIn("working on", answer)

    def test_failed_inspection_does_not_claim_idle(self):
        self.snap["inspection"]["queue_available"] = False
        answer = self.reply()
        self.assertNotIn("idle", answer)
        self.assertIn("A live check failed", answer)

    def test_raw_titles_and_many_tasks_stay_bounded(self):
        self.snap["work"][0].update(project=None, task="# lane-webbob-texting-deploy-0702")
        self.assertIn("Codex is working on the current task", self.reply())
        self.snap["queue_jobs"]["queued"] *= 100
        self.snap["work"] *= 100
        self.reply()

    def test_known_models_stay_in_the_observation(self):
        self.snap["work"][0]["model"] = "gpt-observed"
        self.assertNotIn("gpt-observed", self.reply())
        self.assertEqual(self.snap["work"][0]["model"], "gpt-observed")


if __name__ == "__main__":
    unittest.main()
