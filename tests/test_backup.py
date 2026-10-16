import copy
import json
from pathlib import Path
import tempfile
import unittest
from webbob.backup import snapshot, read_snapshot


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "2026-10-16.json"
        self.facts = [{"id": "timezone", "revision": 2, "body": "Use Chicago time.", "at": 123,
                       "provenance": {"kind": "accepted_memory", "uri": "memory/profile.md#L1", "sha256": "b" * 64,
                                      "accepted_by": "grok-bot-profile", "accepted_at": "2026-10-16"},
                       "classification": "accepted_fact", "execution_authority": False}]
        self.config = {"timezone": "America/Chicago", "release_sha": "a" * 40,
                       "model_caps_microdollars": {"model-a": 0}, "routines_paused": True}

    def test_round_trip_restores_selected_memory_config_and_integrity(self):
        receipt = snapshot(self.path, self.facts, self.config)
        restored = read_snapshot(self.path)
        self.assertEqual(restored, {"facts": self.facts, "config": self.config})
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(receipt["facts"], 1)
        body = json.loads(self.path.read_text())
        body["payload"]["facts"][0]["body"] = "tampered"
        self.path.write_text(json.dumps(body))
        with self.assertRaises(ValueError):
            read_snapshot(self.path)

    def test_secrets_and_private_sources_rejected_before_any_file_written(self):
        for change in [dict(self.config, credentials="FAKE"), dict(self.config, BRAVE_API_KEY="FAKE")]:
            with self.assertRaises(ValueError):
                snapshot(self.path, self.facts, change)
        for body in ["password is dummy", "api_key=dummy", "Bearer dummy", "AKIA0123456789012345",
                     "xoxb-1234567890-abcdefghij", "+1 312 555 0199", "voice memo transcript sample"]:
            facts = copy.deepcopy(self.facts)
            facts[0]["body"] = body
            with self.assertRaises(ValueError):
                snapshot(self.path, facts, self.config)
        for kind in ("private_text", "raw_voice", "credentials"):
            facts = copy.deepcopy(self.facts)
            facts[0]["provenance"]["kind"] = kind
            with self.assertRaises(ValueError):
                snapshot(self.path, facts, self.config)
        self.assertEqual(list(self.path.parent.iterdir()), [])

    def test_duplicate_nightly_snapshot_does_not_overwrite(self):
        snapshot(self.path, self.facts, self.config)
        original = self.path.read_bytes()
        with self.assertRaises(ValueError):
            snapshot(self.path, [], self.config)
        self.assertEqual(self.path.read_bytes(), original)

    def test_provenance_cannot_carry_private_payloads_and_directory_is_private(self):
        for mutation in ({"raw_message": "Unshared conversation"}, {"uri": "sessions/private.json"},
                         {"sha256": "missing"}, {"accepted_by": ""}):
            facts = copy.deepcopy(self.facts)
            facts[0]["provenance"].update(mutation)
            with self.assertRaises(ValueError):
                snapshot(self.path, facts, self.config)
        self.path.parent.chmod(0o755)
        with self.assertRaises(ValueError):
            snapshot(self.path, self.facts, self.config)
        self.assertEqual(list(self.path.parent.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
