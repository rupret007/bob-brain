"""Security regressions: exact policy identity and untrusted snapshot handling."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from webbob import ai_capacity, research_limits, spend_cap
from webbob.ai_capacity import AiCapacity, sanitize_capacity_snapshot, validate_document
from webbob.spend_cap import provider_quota_check


def snapshot(provider="codex", remaining=90, generated_ts=1000):
    return {"schema": "ai-capacity/v1", "generated_ts": generated_ts,
            "rows": [{"provider": provider, "remaining_pct": remaining}]}


class ProviderIdentitySecurityTests(unittest.TestCase):
    def test_unknown_providers_default_deny(self):
        for name in ("gpt-5", "o3", "mistral", "", "cl\u0430ude",
                     "brave_search-extra", "not-claude", "claude-unknown"):
            with self.subTest(name=name):
                result = provider_quota_check(name, snapshot())
                self.assertTrue(result["blocks_reserve"])
                self.assertTrue(result["unknown_quota"])
                self.assertEqual(result["reason"], "provider_not_quota_gated")

    def test_non_ai_allowlist_is_exact_and_hardcoded(self):
        self.assertIsInstance(spend_cap.NON_AI_PROVIDERS, frozenset)
        self.assertEqual(spend_cap.NON_AI_PROVIDERS, {"brave", "brave_search"})
        with patch.dict(os.environ, {"NON_AI_PROVIDERS": "gpt-5"}):
            for name in ("brave", "brave_search"):
                self.assertFalse(provider_quota_check(name, None)["blocks_reserve"])
            self.assertTrue(provider_quota_check("gpt-5", None)["blocks_reserve"])

    def test_provider_names_use_nfkc_casefold_and_strip(self):
        for name in (" ＣｏＤｅＸ ", " MiniMaX "):
            with self.subTest(name=name):
                self.assertEqual(provider_quota_check(name, None)["reason"], "no_capacity_snapshot")
        self.assertEqual(provider_quota_check(" ＣＬＡＵＤＥ ", None)["reason"], "quota_check_exempt")
        self.assertEqual(provider_quota_check(" ＢＲＡＶＥ ", None)["reason"], "quota_check_not_applicable")

    def test_mixed_provider_names_cannot_inherit_exemption(self):
        for name in ("minimax-claude", "claude-minimax"):
            with self.subTest(name=name):
                result = provider_quota_check(name, snapshot("minimax", 0))
                self.assertTrue(result["blocks_reserve"])
                self.assertEqual(result["reason"], "provider_not_quota_gated")

    def test_measured_policy_takes_precedence_over_exemptions(self):
        overlap = spend_cap.UNMEASURED_QUOTA_PROVIDERS | {"codex", "minimax"}
        with patch.object(spend_cap, "UNMEASURED_QUOTA_PROVIDERS", overlap):
            for name in ("codex", "minimax"):
                with self.subTest(name=name):
                    result = provider_quota_check(name, snapshot(name, 0))
                    self.assertTrue(result["blocks_reserve"])
                    self.assertEqual(result["reason"], "provider_quota_low")

    def test_capacity_rows_require_normalized_exact_identity(self):
        doc = snapshot("untrusted-codex", 99)
        doc["rows"].append({"provider": " ＣｏＤｅＸ ", "remaining_pct": 1})
        result = provider_quota_check("codex", doc)
        self.assertTrue(result["blocks_reserve"])
        self.assertEqual(result["reason"], "provider_quota_low")
        self.assertEqual(result["remaining_pct"], 1)


class CapacitySnapshotSecurityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / "capacity.json"
        self.script = self.root / "capacity.sh"
        self.script.write_text("#!/bin/sh\n")

    def test_runner_unicode_decode_error_fails_closed(self):
        for cached in (False, True):
            with self.subTest(cached=cached):
                if cached:
                    self.path.write_text(json.dumps(snapshot(generated_ts=1)))
                runner = Mock(side_effect=UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid"))
                store = AiCapacity(self.path, self.script, clock=lambda: 2000, runner=runner)
                doc = store.snapshot()
                runner.assert_called_once()
                self.assertTrue(doc["snapshot_stale"])
                self.assertEqual(provider_quota_check("codex", doc)["reason"], "snapshot_stale")
                self.assertEqual(len(doc["rows"]), int(cached))

    def test_file_unicode_decode_error_fails_closed(self):
        self.path.write_bytes(b"\xff")
        store = AiCapacity(self.path, self.script, clock=lambda: 2000)
        doc = store.snapshot(refresh=False)
        self.assertTrue(doc["snapshot_stale"])
        self.assertEqual(doc["rows"], [])
        self.assertTrue(provider_quota_check("codex", doc)["blocks_reserve"])

    def test_nan_percentages_are_rejected(self):
        # NaN passes ordinary < 0 / > 100 comparisons: isfinite is essential.
        for field in ("used_pct", "remaining_pct"):
            with self.subTest(field=field):
                doc = snapshot()
                doc["rows"][0][field] = float("nan")
                with self.assertRaisesRegex(ValueError, "invalid percent"):
                    validate_document(doc)

    def test_row_note_is_scrubbed(self):
        doc = snapshot()
        doc["rows"][0]["note"] = "password=synthetic-test-value"
        clean = sanitize_capacity_snapshot(doc)
        self.assertEqual(clean["rows"][0]["note"], "")
        self.assertEqual(doc["rows"][0]["note"], "password=synthetic-test-value")

    def test_age_marks_stale_without_refresh_failure(self):
        self.path.write_text(json.dumps(snapshot(generated_ts=1)))
        for refresh in (False, True):
            with self.subTest(refresh=refresh):
                runner = Mock(return_value=subprocess.CompletedProcess(
                    [], 0, stdout=json.dumps(snapshot(generated_ts=1))))
                store = AiCapacity(self.path, self.script, clock=lambda: 2000, runner=runner)
                doc = store.snapshot(refresh=refresh)
                self.assertTrue(doc["snapshot_stale"])
                self.assertIn("older than", doc["snapshot_note"])
                self.assertTrue(provider_quota_check("codex", doc)["blocks_reserve"])
                self.assertEqual(runner.call_count, int(refresh))

    def test_home_lookup_is_lazy_and_overrides_avoid_it(self):
        spec = importlib.util.spec_from_file_location("capacity_import_probe", ai_capacity.__file__)
        module = importlib.util.module_from_spec(spec)
        with patch.object(Path, "home", side_effect=AssertionError("eager home lookup")):
            spec.loader.exec_module(module)
            explicit = module.AiCapacity(self.path, self.script)
            self.assertEqual(explicit.path, self.path)
            with patch.dict(os.environ, {"AI_CAPACITY_JSON": str(self.path), "AI_CAPACITY_SCRIPT": str(self.script)}):
                configured = module.AiCapacity()
                self.assertEqual(configured.path, self.path)
                self.assertEqual(configured.script, self.script)
        with patch.dict(os.environ, {"AI_CAPACITY_JSON": "", "AI_CAPACITY_SCRIPT": ""}), \
                patch.object(Path, "home", return_value=self.root) as home:
            defaults = module.AiCapacity()
            home.assert_called()
            self.assertEqual(defaults.path, self.root / "Documents/bob-overnight-inject/sync/ai-capacity.json")
            self.assertEqual(defaults.script, self.root / "Documents/bob-overnight-inject/bin/ai-capacity.sh")

    def test_production_cap_uses_live_snapshot_and_fails_closed(self):
        self.path.write_text(json.dumps(snapshot()))
        with patch.object(research_limits, "_RESEARCH_CAP_STORE", self.root), \
                patch.dict(os.environ, {"AI_CAPACITY_JSON": str(self.path), "AI_CAPACITY_SCRIPT": str(self.script)}), \
                patch.object(ai_capacity.time, "time", return_value=1000), \
                patch.object(ai_capacity, "_default_runner", return_value=subprocess.CompletedProcess([], 1)):
            budget, daily, cost = research_limits.research_spend_and_daily_caps()
            # Exercise a measured provider on the real production-created cap.
            budget.caps["codex"] = 100
            self.assertTrue(budget.reserve("fresh", "codex", 1)["admitted"])
            self.path.write_text(json.dumps(snapshot(remaining=1)))
            self.assertEqual(budget.reserve("low", "codex", 1)["reason"], "provider_quota_low")
            self.path.write_text(json.dumps(snapshot(generated_ts=1)))
            blocked = budget.reserve("stale", "codex", 1)
            self.assertFalse(blocked["admitted"])
            self.assertEqual(blocked["quota"]["reason"], "snapshot_stale")
            self.path.unlink()
            self.assertFalse(budget.reserve("missing", "codex", 1)["admitted"])
            self.assertTrue(budget.reserve("search", "brave_search", cost)["admitted"])
            self.assertTrue(daily.admit())


if __name__ == "__main__":
    unittest.main()
