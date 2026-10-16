import copy
import unittest
from webbob.release_board import validate_release_record


class ReleaseContractTests(unittest.TestCase):
    def setUp(self):
        self.row = {"repo": "rupret007/bob-brain", "owner": "webbob", "claim_id": "claim:1", "pr": 7,
                    "sha": "a" * 40, "status": "PROPOSED", "evidence": ["tests:pending"],
                    "karen_receipt": None, "jeff_receipt": None, "handoff": "BOB-HANDOFF.md"}

    def test_proposal_is_a_record_not_approval(self):
        result = validate_release_record(self.row)
        self.assertTrue(result["valid_contract"])
        self.assertFalse(result["execution_authority"])

    def test_approved_record_requires_both_exact_commit_receipts(self):
        self.row["status"] = "APPROVED"
        with self.assertRaises(ValueError):
            validate_release_record(self.row)
        self.row["karen_receipt"] = {"id": "karen:1", "sha": self.row["sha"]}
        self.row["jeff_receipt"] = {"id": "jeff:1", "sha": self.row["sha"]}
        self.assertTrue(validate_release_record(self.row)["valid_contract"])
        self.row["sha"] = "b" * 40
        with self.assertRaises(ValueError):
            validate_release_record(self.row)

    def test_missing_claim_or_evidence_cannot_enter_board(self):
        for field in ("claim_id", "evidence", "handoff"):
            changed = dict(self.row, **{field: None})
            with self.assertRaises(ValueError):
                validate_release_record(changed)


if __name__ == "__main__":
    unittest.main()
