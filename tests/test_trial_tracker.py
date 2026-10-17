import unittest
from webbob.trial_tracker import SCENARIOS, record_result, summarize, trial_template


class TrialTests(unittest.TestCase):
    def test_seven_day_pairs_begin_not_run_without_invented_metrics(self):
        trial = trial_template("2026-10-16", "a" * 40)
        self.assertEqual(len(trial["rows"]), 7 * len(SCENARIOS) * 2)
        self.assertEqual(len({r["date"] for r in trial["rows"]}), 7)
        self.assertTrue(all(r["result"] == "NOT RUN" and r["cost_microdollars"] is None for r in trial["rows"]))
        self.assertEqual(summarize(trial)["webbob"]["observed"], 0)

    def test_real_receipt_required_build_mismatch_and_overwrite_rejected(self):
        trial = trial_template("2026-10-16", "a" * 40)
        kwargs = dict(result="PASS", receipt="receipt:1", latency_ms=350, cost_microdollars=None, build="b" * 40)
        with self.assertRaises(ValueError):
            record_result(trial, "2026-10-16", "daily_brief", "webbob", **kwargs)
        kwargs["build"] = "a" * 40
        record_result(trial, "2026-10-16", "daily_brief", "webbob", **kwargs)
        with self.assertRaises(ValueError):
            record_result(trial, "2026-10-16", "daily_brief", "webbob", **kwargs)
        report = summarize(trial)
        self.assertEqual(report["webbob"]["pass"], 1)
        self.assertEqual(report["webbob"]["unknown_cost_count"], 1)
        self.assertFalse(report["replacement_approved"])


if __name__ == "__main__":
    unittest.main()
