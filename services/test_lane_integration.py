"""Cross-lane proof through actual screen workers and the Web Bob tool handlers."""
import unittest
import lane_integration_smoke


class LaneIntegrationTests(unittest.TestCase):
    def test_three_durable_jobs_and_same_reply_started_lane(self):
        result = lane_integration_smoke.drill()
        self.assertEqual(result["result"], "PASS")


if __name__ == "__main__":
    unittest.main()
