"""Cap tiers, concurrent reservations, and observed plan quota regressions."""
import concurrent.futures
import os
import time
import unittest
from unittest.mock import patch

import budget
import lanes
import state
import test_services


class BudgetTests(unittest.TestCase):
    setUp = test_services.ServicesTest.setUp
    tearDown = test_services.ServicesTest.tearDown

    def seed(self, lane, spent):
        with state.lock("ledger-" + lane):
            state._append(budget.path(lane), dict(call_id="seed", cost_usd=spent))

    def test_lane_state_warns_at_70_and_stops_at_95_percent_of_cap(self):
        with patch.object(budget, "CAP_USD", 10), patch.object(budget, "GEMINI_CAP_USD", 10), patch.dict(os.environ, {"GEMINI_API_KEY": "test-key", "MINIMAX_API_KEY": "test-key"}), patch.object(lanes, "CURSOR") as cursor:
            cursor.is_file.return_value = False
            for lane in ("gemini", "minimax"):
                self.seed(lane, 7.1)
            health = lanes.refresh()
            for lane in ("gemini", "minimax"):
                self.assertEqual(health[lane]["state"], "budget_warning")
                self.assertEqual(health[lane]["capacity"], 3)
                self.seed(lane, 8.6)
            health = lanes.refresh()
            for lane in ("gemini", "minimax"):
                self.assertEqual(health[lane]["budget"]["tier"], "slow")
                self.assertEqual(health[lane]["capacity"], 1)
                self.seed(lane, 9.6)
            health = lanes.refresh()
            for lane in ("gemini", "minimax"):
                self.assertEqual(health[lane]["state"], "budget_exhausted")
                with self.assertRaises(budget.BudgetExceeded):
                    budget.reserve(lane, "test", 10)

    def test_both_api_reservations_stop_at_95_percent_under_concurrency(self):
        with patch.object(budget, "CAP_USD", .10), patch.object(budget, "GEMINI_CAP_USD", .10):
            for lane in ("gemini", "minimax"):
                def reserve(_):
                    try:
                        budget.reserve(lane, "evidence", 8192)
                        return True
                    except budget.BudgetExceeded:
                        return False
                with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
                    accepted = list(pool.map(reserve, range(24)))
                self.assertTrue(any(accepted))
                self.assertFalse(all(accepted))
                self.assertLessEqual(budget.totals(lane)["committed_usd"], .095)

    def test_plan_usage_is_unknown_without_observation_and_stops_when_observed(self):
        self.assertFalse(budget.status("codex")["quota_known"])
        state.write_json(self.core / "plan-usage.json", {"codex": {"used_percent": 96, "reset_at": time.time() + 60}})
        with self.assertRaises(budget.BudgetExceeded):
            budget.check("codex")
        state.write_json(self.core / "plan-usage.json", {"codex": {"used_percent": 96, "reset_at": time.time() - 60}})
        self.assertEqual(budget.check("codex")["tier"], "normal")
