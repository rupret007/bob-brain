import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from webbob.spend_cap import SpendCap, provider_quota_check


def capacity_with_remaining(provider: str, remaining):
    return {
        "schema": "ai-capacity/v1",
        "generated_ts": 1.0,
        "rows": [{"provider": provider, "used_pct": None, "remaining_pct": remaining,
                  "reset_ts": None, "reset_ct": None, "source": "", "observed_ts": None,
                  "freshness": None, "status": "ok", "note": ""}],
    }


class ProviderQuotaGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "spend.sqlite"
        self.now = datetime.fromisoformat("2026-10-31T23:59:59-05:00")
        self.caps = {"codex-main": 1_000_000, "claude-main": 1_000_000}

    def test_blocks_when_remaining_below_five(self):
        snap = capacity_with_remaining("Codex (ChatGPT)", 4.5)
        budget = SpendCap(self.path, self.caps, clock=lambda: self.now, capacity_snapshot=snap)
        result = budget.reserve("a", "codex-main", 10)
        self.assertFalse(result["admitted"])
        self.assertEqual(result["reason"], "provider_quota_low")

    def test_allows_at_or_above_five_percent(self):
        snap = capacity_with_remaining("Codex (ChatGPT)", 5.0)
        budget = SpendCap(self.path, self.caps, clock=lambda: self.now, capacity_snapshot=snap)
        self.assertTrue(budget.reserve("b", "codex-main", 10)["admitted"])

    def test_unknown_remaining_does_not_block_but_flags(self):
        snap = capacity_with_remaining("Claude Code (Max/Pro)", None)
        check = provider_quota_check("claude-main", snap)
        self.assertFalse(check["low_quota"])
        self.assertTrue(check["unknown_quota"])
        self.assertTrue(check["flagged"])
        budget = SpendCap(self.path, self.caps, clock=lambda: self.now, capacity_snapshot=snap)
        self.assertTrue(budget.reserve("c", "claude-main", 10)["admitted"])


if __name__ == "__main__":
    unittest.main()
