import unittest
from webbob.status_view import render_status, status_rows


class StatusTests(unittest.TestCase):
    def test_four_bots_always_visible_missing_and_stale_are_unknown(self):
        rows = status_rows({"bob": {"state": "up", "observed_at": 100}, "webbob": {"state": "up", "observed_at": 1}}, now=200)
        self.assertEqual(len(rows), 4)
        self.assertEqual([r["state"] for r in rows], ["up", "unknown", "unknown", "unknown"])

    def test_known_down_and_review_pending_preserved(self):
        row = status_rows({"webbob": {"state": "down", "observed_at": 100, "pending": 2, "review": "PENDING"}}, now=110)[1]
        self.assertEqual((row["state"], row["pending"], row["review"]), ("down", 2, "PENDING"))

    def test_private_fields_invalid_state_and_nonfinite_time_do_not_render(self):
        html = render_status({"bob": {"observed_at": 100, "state": "<script>bad</script>", "credential": "FAKE_PRIVATE",
                                      "inbox": "PRIVATE_BODY"}, "karen": {"observed_at": float("nan"), "state": "up"}}, now=100)
        for value in ("<script>", "FAKE_PRIVATE", "PRIVATE_BODY"):
            self.assertNotIn(value, html)
        self.assertIn("Karen", html)
        self.assertIn("unknown", html)


if __name__ == "__main__":
    unittest.main()
