"""Correct requirement/criteria wording is not an unsupported outcome claim."""
import unittest

import claim_evidence


OUTAGE_T3 = (
    'No, keeping requests short and sequential does not guarantee avoiding extra charges '
    'or maintaining quality. Short prompts still consume quota and can trigger overage fees '
    'if an allowance is already exhausted. Fragmenting a comparative analysis can also '
    'degrade answer quality by breaking necessary context across separate turns. Preserving '
    'quality and staying within paid limits remain requirements to verify against account '
    'terms and test benchmarks, not guaranteed outcomes of prompt size.'
)
HOLD_RESUME_T1 = (
    '* **Acceptance Criteria:**\n'
    '  * **Pass:** Texting pipelines show no blocking defects, cross-conversation continuity '
    'meets retention requirements, and quality standards are preserved.\n'
)


class GuardExemptionTests(unittest.TestCase):
    def test_outage_quality_requirement_sentence_is_not_a_violation(self):
        self.assertEqual(claim_evidence.violations(OUTAGE_T3), [])
        delivered, findings = claim_evidence.deliver(OUTAGE_T3)
        self.assertFalse(findings)
        self.assertIn('remain requirements', delivered)
        self.assertIn('not guaranteed outcomes', delivered)

    def test_acceptance_criteria_pass_bullet_is_not_a_violation(self):
        self.assertEqual(claim_evidence.violations(HOLD_RESUME_T1), [])
        delivered, findings = claim_evidence.deliver(HOLD_RESUME_T1)
        self.assertFalse(findings)
        self.assertIn('quality standards are preserved', delivered)
        self.assertNotIn('unverified from what’s available here', delivered)

    def test_standalone_outcome_claims_still_flag(self):
        self.assertTrue(claim_evidence.violations(
            'Quality standards are preserved, with no regressions.'))
        self.assertTrue(claim_evidence.violations('This route will not incur extra charges.'))
        delivered, findings = claim_evidence.deliver(
            'Quality standards are preserved, with no regressions.')
        self.assertTrue(findings)
        self.assertNotIn('Quality standards are preserved, with no regressions.', delivered)


if __name__ == '__main__':
    unittest.main()
