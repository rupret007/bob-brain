import unittest
from webbob.parity_gate import CAPABILITIES, RECOVERY, GoLiveDenied, ParityGate


class ParityTests(unittest.TestCase):
    def setUp(self):
        self.sha = "a" * 40
        self.gate = ParityGate(lambda name, sha, receipt: receipt == "observed:" + name and sha == self.sha,
                               lambda sha, receipt: sha == self.sha and receipt == "karen-pass",
                               lambda sha, receipt: sha == self.sha and receipt == "jeff-accept")
        self.evidence = {name: {"sha": self.sha, "result": "PASS", "receipt": "observed:" + name} for name in (*CAPABILITIES, *RECOVERY)}

    def test_all_fourteen_capabilities_and_four_recovery_checks_mandatory(self):
        self.assertEqual(len(CAPABILITIES), 14)
        self.assertEqual(self.gate.require(self.sha, self.evidence, "karen-pass", "jeff-accept")["checks"], 18)
        for name in self.evidence:
            incomplete = dict(self.evidence)
            incomplete.pop(name)
            with self.assertRaises(GoLiveDenied):
                self.gate.require(self.sha, incomplete, "karen-pass", "jeff-accept")

    def test_waived_not_run_forged_stale_or_unapproved_release_denied(self):
        for state in ("FAIL", "NOT RUN", "WAIVED", "PARTIAL"):
            changed = dict(self.evidence, workspace={"sha": self.sha, "result": state, "receipt": "observed:workspace"})
            with self.assertRaises(GoLiveDenied):
                self.gate.require(self.sha, changed, "karen-pass", "jeff-accept")
        for sha, karen, jeff in [("b" * 40, "karen-pass", "jeff-accept"), (self.sha, "old-QA-file", "jeff-accept"), (self.sha, "karen-pass", "missing")]:
            with self.assertRaises(GoLiveDenied):
                self.gate.require(sha, self.evidence, karen, jeff)
        changed = dict(self.evidence, workspace={"sha": self.sha, "result": "PASS", "receipt": "invented"})
        with self.assertRaises(GoLiveDenied):
            self.gate.require(self.sha, changed, "karen-pass", "jeff-accept")


if __name__ == "__main__":
    unittest.main()
