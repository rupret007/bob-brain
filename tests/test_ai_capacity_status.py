import json
import unittest

from webbob.status_view import capacity_rows, render_capacity


class CapacityStatusTests(unittest.TestCase):
    def test_capacity_rows_show_unknown_honestly(self):
        doc = {
            "rows": [
                {"provider": "Gemini API", "used_pct": None, "remaining_pct": None,
                 "reset_ct": None, "freshness": None, "status": "key valid"},
            ]
        }
        row = capacity_rows(doc)[0]
        self.assertEqual(row["used_pct"], "unknown")
        self.assertEqual(row["remaining_pct"], "unknown")
        self.assertEqual(row["reset_ct"], "unknown")

    def test_render_capacity_includes_provider_and_stale_banner(self):
        doc = {"snapshot_stale": True, "snapshot_note": "refresh failed",
               "rows": [{"provider": "MiniMax (general)", "used_pct": 20, "remaining_pct": 80,
                         "reset_ct": "Fri Oct 16  5:00 PM CT", "freshness": "2m ago", "status": "ok"}]}
        html = render_capacity(doc)
        self.assertIn("MiniMax", html)
        self.assertIn("80%", html)
        self.assertIn("refresh failed", html)


if __name__ == "__main__":
    unittest.main()
