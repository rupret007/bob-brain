import unittest
from webbob.fallback import fallback_notice
from webbob.fallback_copy import GROK_CONTINUE_MESSAGE


class FallbackTests(unittest.TestCase):
    def test_healthy_no_notice_and_each_down_offers_grok(self):
        health = {name: {"status": "up", "observed_at": 100} for name in ("webbob", "mini")}
        self.assertIsNone(fallback_notice(health, now=100))
        for name in health:
            altered = {**health, name: {"status": "down", "observed_at": 100}}
            notice = fallback_notice(altered, now=100)
            self.assertIn("Grok Bot", notice["message"])
            self.assertTrue(notice["message"].endswith(GROK_CONTINUE_MESSAGE))
            self.assertFalse(notice["auto_forward"])

    def test_missing_stale_future_and_nonfinite_health_are_unknown(self):
        for observed in (None, 1, 301, float("nan"), float("inf")):
            notice = fallback_notice({"webbob": {"status": "up", "observed_at": observed}}, now=300)
            self.assertIn("Could not verify", notice["message"])
            self.assertNotIn("is unavailable", notice["message"])

    def test_malformed_health_still_shows_unknown_fallback(self):
        for health in (None, [], {"webbob": None}, {"mini": {"observed_at": 100, "status": []}}):
            notice = fallback_notice(health, now=100)
            self.assertIn("Could not verify", notice["message"])
            self.assertIn("Grok Bot", notice["message"])
            self.assertFalse(notice["auto_forward"])


if __name__ == "__main__":
    unittest.main()
