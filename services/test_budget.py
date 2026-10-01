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

    def test_modern_gemini_reserves_future_rates_and_meters_thoughts_across_promotion_end(self):
        for at, expected in ((1798761599, .002175), (1798761600, .00435)):
            with self.subTest(at=at), patch.object(budget.time, 'time', return_value=at):
                row = budget.reserve('gemini', 'text', 8192, model_id='gemini-3.8-flash')
                self.assertAlmostEqual(row['reserved_usd'], (4100 * 1.5 + 8192 * 7.5) / 1_000_000)
                before = budget.totals('gemini')['spent_usd']
                budget.settle('gemini', row, dict(usageMetadata=dict(promptTokenCount=400,
                              candidatesTokenCount=200, thoughtsTokenCount=300)))
                self.assertAlmostEqual(budget.totals('gemini')['spent_usd'] - before, expected)

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

    def test_prepaid_policy_preserves_costs_and_unknown_balance(self):
        with patch.dict(os.environ, {}, clear=True):
            self.seed('gemini', 60)
            state.write_json(self.core / 'plan-usage.json', {'gemini': {'used_percent': 100}})
            reservation = budget.reserve('gemini', 'meter this prompt', 100)
            self.assertGreater(budget.totals('gemini')['committed_usd'], 60)
            budget.settle('gemini', reservation, {'usageMetadata': {'promptTokenCount': 12, 'candidatesTokenCount': 20}})
            usage = budget.check('gemini')
            self.assertIsNone(usage['cap_usd'])
            self.assertFalse(usage['quota_known'])
            self.assertFalse(usage['provider_balance_known'])
            self.assertEqual(usage['calls'], 2)
            self.assertGreater(usage['spent_usd'], 60)
            self.assertEqual(budget.cap('minimax'), 48)
            with patch.dict(os.environ, {'BOB_GEMINI_CAP_USD': '50'}):
                with self.assertRaises(budget.BudgetExceeded):
                    budget.reserve('gemini', 'cannot fit', 1)
            with patch.dict(os.environ, {'BOB_GEMINI_CAP_USD': '0'}):
                with self.assertRaises(budget.BudgetExceeded):
                    budget.check('gemini')

    def test_refill_latch_blocks_admission_without_hiding_or_erasing_costs(self):
        self.seed('gemini', 20)
        budget.reserve('gemini', 'uncertain transport', 100)
        before = budget.path('gemini').read_bytes()
        totals = budget.totals('gemini')
        budget.mark_refill_required()
        observed = (self.core / 'gemini-funding.json').read_bytes()
        budget.mark_refill_required()
        self.assertEqual((self.core / 'gemini-funding.json').read_bytes(), observed)
        self.assertEqual(budget.totals('gemini'), totals)
        self.assertEqual(budget.status('gemini')['reason'], 'refill_required')
        for action in (lambda: budget.check('gemini'), lambda: budget.reserve('gemini', 'blocked', 100)):
            with self.assertRaises(budget.RefillRequired):
                action()
        with self.assertRaises(ValueError):
            budget.authorize_refill_retry('')
        budget.authorize_refill_retry('Owner confirmed a refill; retry permitted')
        self.assertFalse(budget.status('gemini')['refill_required'])
        self.assertFalse(budget.funding('gemini')['balance_verified'])
        self.assertIn('observed_at', budget.funding('gemini')['previous_observation'])
        self.assertEqual(budget.path('gemini').read_bytes(), before)
        self.assertEqual(budget.check('gemini')['tier'], 'normal')

    def test_corrupt_funding_state_fails_closed_before_reservation(self):
        state.write_json(self.core / 'gemini-funding.json', {'refill_required': 'false'})
        with self.assertRaises(ValueError):
            budget.reserve('gemini', 'blocked', 100)
        self.assertFalse(budget.path('gemini').exists())
