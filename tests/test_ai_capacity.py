import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from webbob.ai_capacity import AiCapacity, validate_document


def sample_doc(generated_ts=1_000_000.0):
    return {
        "schema": "ai-capacity/v1",
        "generated_ts": generated_ts,
        "generated_ct": "Mon Jan  1 12:00 PM CT",
        "host": "mini",
        "rows": [
            {
                "provider": "Codex (ChatGPT, weekly)",
                "used_pct": 10.0,
                "remaining_pct": 90.0,
                "reset_ts": None,
                "reset_ct": None,
                "source": "codex",
                "observed_ts": generated_ts,
                "freshness": "1m ago",
                "status": "ok",
                "note": "",
            }
        ],
    }


class AiCapacityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "ai-capacity.json"
        self.script = Path(self.tmp.name) / "ai-capacity.sh"
        self.now = 1_000_900.0

    def test_validate_rejects_malformed_json_shape(self):
        with self.assertRaises(ValueError):
            validate_document({"schema": "ai-capacity/v2"})
        with self.assertRaises(ValueError):
            validate_document({"schema": "ai-capacity/v1", "generated_ts": "bad", "rows": []})

    def test_fresh_file_loads_without_runner(self):
        self.path.write_text(json.dumps(sample_doc(self.now - 60)))
        calls = []

        def runner(argv, timeout):
            calls.append(argv)
            return subprocess.CompletedProcess(argv, 0, stdout="{}", stderr="")

        store = AiCapacity(self.path, self.script, clock=lambda: self.now, runner=runner)
        doc = store.snapshot()
        self.assertEqual(doc["rows"][0]["remaining_pct"], 90.0)
        self.assertFalse(doc.get("snapshot_stale"))
        self.assertEqual(calls, [])

    def test_stale_triggers_refresh_and_falls_back(self):
        self.path.write_text(json.dumps(sample_doc(self.now - 3600)))
        stale = sample_doc(self.now)

        def runner(argv, timeout):
            self.assertEqual(argv[-1], "--json")
            return subprocess.CompletedProcess(argv, 0, stdout=json.dumps(stale), stderr="")

        store = AiCapacity(self.path, self.script, clock=lambda: self.now, runner=runner, max_age_seconds=900)
        doc = store.snapshot()
        self.assertEqual(doc["generated_ts"], self.now)
        self.assertFalse(doc.get("snapshot_stale"))

    def test_refresh_failure_marks_last_data_stale(self):
        self.path.write_text(json.dumps(sample_doc(self.now - 3600)))

        def runner(argv, timeout):
            return subprocess.CompletedProcess(argv, 1, stdout="", stderr="fail")

        store = AiCapacity(self.path, self.script, clock=lambda: self.now, runner=runner, max_age_seconds=60)
        doc = store.snapshot()
        self.assertTrue(doc["snapshot_stale"])
        self.assertIn("refresh failed", doc["snapshot_note"])
        self.assertEqual(doc["rows"][0]["remaining_pct"], 90.0)

    def test_missing_file_and_failed_refresh_returns_empty_unknown(self):
        def runner(argv, timeout):
            return subprocess.CompletedProcess(argv, 1, stdout="", stderr="")

        store = AiCapacity(self.path, self.script, clock=lambda: self.now, runner=runner)
        doc = store.snapshot()
        self.assertEqual(doc["rows"], [])
        self.assertTrue(doc["snapshot_stale"])


if __name__ == "__main__":
    unittest.main()
