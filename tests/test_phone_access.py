import unittest
from webbob.phone_access import REQUIRED, evaluate_phone_access


class PhoneTests(unittest.TestCase):
    def test_missing_and_old_build_evidence_never_approve_access(self):
        sha = "a" * 40
        self.assertFalse(evaluate_phone_access(sha, {})["ready"])
        evidence = {name: {"sha": sha, "result": "PASS", "receipt": "local-test:" + name} for name in REQUIRED}
        self.assertTrue(evaluate_phone_access(sha, evidence)["ready"])
        self.assertFalse(evaluate_phone_access("b" * 40, evidence)["ready"])
        for name in REQUIRED:
            changed = dict(evidence, **{name: {"sha": sha, "result": "NOT RUN", "receipt": "unexecuted"}})
            self.assertEqual(evaluate_phone_access(sha, changed)["missing"], [name])

    def test_permission_prompts_remain_owner_actions(self):
        result = evaluate_phone_access("a" * 40, {})
        self.assertFalse(result["automate_permission_prompts"])
        self.assertIn("needs Jeff", result["desktop_permissions"])


if __name__ == "__main__":
    unittest.main()
