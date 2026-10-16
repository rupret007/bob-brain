from datetime import datetime
from pathlib import Path
import tempfile
import threading
import unittest
from webbob.spend_cap import SpendCap


class SpendTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "spend.sqlite"
        self.now = datetime.fromisoformat("2026-10-31T23:59:59-05:00")
        self.clock = lambda: self.now
        # Claude-tagged models are quota-exempt so these tests isolate monthly caps.
        self.caps = {"claude-a": 100, "claude-b": 200}
        self.budget = SpendCap(self.path, self.caps, self.clock)

    def test_concurrent_calls_cannot_overspend_cap(self):
        start = threading.Barrier(2)
        results = []
        def reserve(ident):
            start.wait()
            results.append(self.budget.reserve(ident, "claude-a", 60))
        threads = [threading.Thread(target=reserve, args=(str(i),)) for i in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(5)
            self.assertFalse(thread.is_alive())
        self.assertEqual(len(results), 2)
        self.assertEqual(sum(r["admitted"] for r in results), 1)
        self.assertTrue(self.budget.reserve("other-model", "claude-b", 200)["admitted"])

    def test_restart_unknown_cost_keeps_reservation_and_replay_never_readmits(self):
        self.budget.reserve("one", "claude-a", 90)
        restarted = SpendCap(self.path, self.caps, self.clock)
        self.assertFalse(restarted.reserve("two", "claude-a", 11)["admitted"])
        self.assertFalse(restarted.reserve("one", "claude-a", 90)["admitted"])
        restarted.settle("one", 20)
        self.assertTrue(restarted.reserve("two", "claude-a", 80)["admitted"])
        with self.assertRaises(ValueError):
            restarted.settle("one", 0)

    def test_month_rollover_threshold_alerts_and_unknown_model(self):
        self.budget.reserve("oct", "claude-a", 100)
        self.assertEqual({a["level"] for a in self.budget.alerts()}, {"80", "95", "100"})
        self.now = datetime.fromisoformat("2026-11-01T00:00:01-05:00")
        self.assertTrue(self.budget.reserve("nov", "claude-a", 100)["admitted"])
        self.assertEqual(len(self.budget.alerts()), 6)
        with self.assertRaises(ValueError):
            self.budget.reserve("unknown", "unconfigured", 1)

    def test_settle_rejects_overrun_and_records_alert(self):
        self.budget.reserve("call", "claude-a", 50)
        with self.assertRaisesRegex(ValueError, "exceeds reservation"):
            self.budget.settle("call", 51)
        self.assertEqual({a["level"] for a in self.budget.alerts() if a["level"] == "overrun"}, {"overrun"})
        self.budget.settle("call", 40)
        with self.assertRaises(ValueError):
            self.budget.settle("call", 30)


if __name__ == "__main__":
    unittest.main()
