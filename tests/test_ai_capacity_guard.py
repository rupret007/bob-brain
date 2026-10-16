import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

from webbob.spend_cap import (
    MEASURED_QUOTA_PROVIDERS,
    UNMEASURED_QUOTA_PROVIDERS,
    SpendCap,
    provider_quota_check,
)


def capacity_doc(provider: str, remaining, *, stale=False, rows=None):
    if rows is None:
        rows = [
            {
                "provider": provider,
                "used_pct": None,
                "remaining_pct": remaining,
                "reset_ts": None,
                "reset_ct": None,
                "source": "",
                "observed_ts": None,
                "freshness": None,
                "status": "ok",
                "note": "",
            }
        ]
    return {
        "schema": "ai-capacity/v1",
        "generated_ts": 1.0,
        "snapshot_stale": stale,
        "rows": rows,
    }


class ProviderQuotaGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "spend.sqlite"
        self.now = datetime.fromisoformat("2026-10-31T23:59:59-05:00")
        self.caps = {"codex-main": 1_000_000, "claude-main": 1_000_000, "minimax-main": 1_000_000}

    def test_blocks_when_remaining_below_five(self):
        snap = capacity_doc("Codex (ChatGPT)", 4.5)
        budget = SpendCap(self.path, self.caps, clock=lambda: self.now, capacity_snapshot=snap)
        result = budget.reserve("a", "codex-main", 10)
        self.assertFalse(result["admitted"])
        self.assertEqual(result["reason"], "provider_quota_low")

    def test_allows_at_or_above_five_percent(self):
        snap = capacity_doc("Codex (ChatGPT)", 5.0)
        budget = SpendCap(self.path, self.caps, clock=lambda: self.now, capacity_snapshot=snap)
        self.assertTrue(budget.reserve("b", "codex-main", 10)["admitted"])

    def test_measured_unknown_remaining_blocks_reserve(self):
        snap = capacity_doc("Codex (ChatGPT)", None)
        budget = SpendCap(self.path, self.caps, clock=lambda: self.now, capacity_snapshot=snap)
        result = budget.reserve("c", "codex-main", 10)
        self.assertFalse(result["admitted"])
        self.assertEqual(result["reason"], "provider_quota_blocked")

    def test_unmeasured_unknown_remaining_passes_quota_not_monthly_cap(self):
        snap = capacity_doc("Claude Code (Max/Pro)", None)
        check = provider_quota_check("claude-main", snap)
        self.assertFalse(check["blocks_reserve"])
        self.assertEqual(check["reason"], "quota_check_exempt")
        budget = SpendCap(self.path, self.caps, clock=lambda: self.now, capacity_snapshot=snap)
        self.assertTrue(budget.reserve("d", "claude-main", 10)["admitted"])

    def test_no_snapshot_blocks_measured_provider(self):
        check = provider_quota_check("codex-main", None)
        self.assertTrue(check["blocks_reserve"])
        self.assertEqual(check["reason"], "no_capacity_snapshot")
        budget = SpendCap(self.path, {**self.caps, "codex-main": 1_000_000}, clock=lambda: self.now, capacity_snapshot=None)
        result = budget.reserve("e", "codex-main", 10)
        self.assertFalse(result["admitted"])
        self.assertEqual(result["reason"], "provider_quota_blocked")

    def test_snapshot_stale_blocks_measured_provider(self):
        snap = capacity_doc("Codex (ChatGPT)", 90.0, stale=True)
        check = provider_quota_check("codex-main", snap)
        self.assertTrue(check["blocks_reserve"])
        self.assertEqual(check["reason"], "snapshot_stale")

    def test_provider_missing_from_snapshot_blocks(self):
        snap = capacity_doc("Claude only", 90.0)
        check = provider_quota_check("minimax-main", snap)
        self.assertTrue(check["blocks_reserve"])
        self.assertEqual(check["reason"], "provider_unmatched")

    def test_non_finite_remaining_blocks(self):
        for bad in (float("nan"), float("inf"), float("-inf"), -1.0, 101.0, 10**1000):
            with self.subTest(remaining=bad):
                snap = capacity_doc("MiniMax (general)", bad)
                check = provider_quota_check("minimax-main", snap)
                self.assertTrue(check["blocks_reserve"])
                self.assertEqual(check["reason"], "remaining_invalid")

    def test_remaining_rejects_non_numeric_values(self):
        for bad in (True, False, "90", [], {}):
            with self.subTest(remaining=bad):
                check = provider_quota_check("codex", capacity_doc("Codex", bad))
                self.assertTrue(check["blocks_reserve"])
                self.assertEqual(check["reason"], "remaining_invalid")

    def test_remaining_range_includes_zero_and_one_hundred(self):
        for remaining, reason, blocked in ((0, "provider_quota_low", True), (100, "ok", False)):
            with self.subTest(remaining=remaining):
                check = provider_quota_check("codex", capacity_doc("Codex", remaining))
                self.assertEqual(check["reason"], reason)
                self.assertEqual(check["blocks_reserve"], blocked)

    def test_unmeasured_list_is_hardcoded_not_env(self):
        snap = capacity_doc("Claude Code", 1.0)
        os.environ["UNMEASURED_QUOTA_PROVIDERS"] = "codex"
        try:
            check = provider_quota_check("claude-main", snap)
            self.assertEqual(check["reason"], "quota_check_exempt")
            check_codex = provider_quota_check("codex-main", capacity_doc("Codex", None))
            self.assertTrue(check_codex["blocks_reserve"])
        finally:
            os.environ.pop("UNMEASURED_QUOTA_PROVIDERS", None)

    def test_default_deny_unknown_provider_name(self):
        check = provider_quota_check("openai-main", capacity_doc("Codex", 90.0))
        self.assertTrue(check["blocks_reserve"])
        self.assertEqual(check["reason"], "provider_not_quota_gated")

    def test_non_ai_spend_model_skips_quota_guard(self):
        check = provider_quota_check("brave_search", None)
        self.assertFalse(check["blocks_reserve"])
        self.assertEqual(check["reason"], "quota_check_not_applicable")

    def test_non_measured_reservations_skip_snapshot_but_keep_monthly_caps(self):
        models = ("brave", "brave_search", " ＢＲＡＶＥ ", "claude", "claude-main",
                  "claude-a", "claude-b", "gemini", "xai", "grok", "cursor")
        snapshot = Mock(side_effect=AssertionError("unexpected capacity snapshot"))
        budget = SpendCap(self.path, dict.fromkeys(models, 5), clock=lambda: self.now,
                          capacity_snapshot=snapshot)
        for model in models:
            with self.subTest(model=model):
                self.assertTrue(budget.reserve(f"first-{model}", model, 3)["admitted"])
                result = budget.reserve(f"second-{model}", model, 3)
                self.assertFalse(result["admitted"])
                self.assertEqual(result["reason"], "monthly_cap")
        snapshot.assert_not_called()

    def test_unknown_provider_reservation_denied_without_snapshot(self):
        snapshot = Mock(side_effect=AssertionError("unexpected capacity snapshot"))
        budget = SpendCap(self.path, {"openai-main": 100}, clock=lambda: self.now,
                          capacity_snapshot=snapshot)
        result = budget.reserve("unknown-provider", "openai-main", 1)
        self.assertFalse(result["admitted"])
        self.assertEqual(result["reason"], "provider_quota_blocked")
        self.assertEqual(result["quota"]["reason"], "provider_not_quota_gated")
        self.assertEqual([alert["level"] for alert in budget.alerts()], ["quota_blocked"])
        snapshot.assert_not_called()

    def test_measured_reservations_read_current_snapshot_with_normalized_aliases(self):
        for model, provider in (("codex", "Codex"), ("codex-main", "Codex"),
                                (" ＣＯＤＥＸ－ＭＡＩＮ ", "Codex"),
                                ("minimax", "MiniMax"), ("minimax-main", "MiniMax"),
                                (" MiNiMaX ", "MiniMax")):
            with self.subTest(model=model):
                snapshot = Mock(side_effect=[capacity_doc(provider, 5), capacity_doc(provider, 4)])
                budget = SpendCap(self.path, {model: 100}, clock=lambda: self.now,
                                  capacity_snapshot=snapshot)
                self.assertTrue(budget.reserve(f"fresh-{model}", model, 1)["admitted"])
                result = budget.reserve(f"low-{model}", model, 1)
                self.assertFalse(result["admitted"])
                self.assertEqual(result["reason"], "provider_quota_low")
                self.assertEqual(snapshot.call_count, 2)

    def test_unmeasured_still_subject_to_monthly_cap(self):
        snap = capacity_doc("Claude Code", None)
        budget = SpendCap(self.path, {"claude-main": 5}, clock=lambda: self.now, capacity_snapshot=snap)
        self.assertTrue(budget.reserve("f1", "claude-main", 3)["admitted"])
        result = budget.reserve("f2", "claude-main", 3)
        self.assertFalse(result["admitted"])
        self.assertEqual(result["reason"], "monthly_cap")

    def test_exempt_ignores_low_remaining_in_snapshot(self):
        snap = capacity_doc("Claude Code (Max/Pro)", 1.0)
        check = provider_quota_check("claude-main", snap)
        self.assertFalse(check["blocks_reserve"])
        budget = SpendCap(self.path, self.caps, clock=lambda: self.now, capacity_snapshot=snap)
        self.assertTrue(budget.reserve("g", "claude-main", 10)["admitted"])

    def test_measured_and_unmeasured_constants_cover_policy(self):
        self.assertEqual(MEASURED_QUOTA_PROVIDERS, frozenset({"codex", "minimax"}))
        self.assertEqual(UNMEASURED_QUOTA_PROVIDERS, frozenset({"claude", "gemini", "xai", "cursor"}))


if __name__ == "__main__":
    unittest.main()
