"""Regression coverage for incomplete lists and locally scoped evidence claims."""
import unittest
import tempfile
from pathlib import Path

from test_webbob_replyq_1856 import SessionFixture  # shared module search paths
import resource_decision
import claim_evidence


class DeliveryPrecisionTests(unittest.TestCase):
    def test_route_guidance_uses_the_supplied_identity_source(self):
        from providers import ANSWER_RULES, REFERENCE_RULES
        with tempfile.TemporaryDirectory() as directory:
            conversation = {'messages': [
                {'role': 'assistant', 'status': 'done', 'provider': 'gemini', 'content': 'Earlier reply.'},
                {'role': 'user', 'content': 'Can our Claude subscription replace the API route?'}]}
            projection = resource_decision.project(Path(directory), conversation)
        self.assertEqual(projection['current_route']['source'], 'last completed reply')
        for rules in (resource_decision.RULES, ANSWER_RULES, REFERENCE_RULES):
            rules = ' '.join(rules.split())
            self.assertIn('Attribute route identity to the supplied current_route.source', rules)
            self.assertIn('"last completed reply" identifies the provider of that reply, not a saved configuration', rules)
            self.assertIn('Neither source establishes current availability', rules)

    def test_diagnostic_branch_cannot_exclude_a_still_possible_cause(self):
        raw = ('### Branch: Storage\n'
               '* **Positive evidence condition:** Match the durable commit and read key.\n'
               '* **Rules out:** Timing defect, Query defect, Rendering defect.\n'
               '* **Still-possible alternatives:** timing defect, Query defect, Rendering defect.\n'
               '* **Next distinguishing check:** Inspect the read response.\n'
               '### Branch: Rendering\n'
               '* **Rules out:** Storage defect.\n'
               '* **Still-possible alternatives:** Query defect.\n')
        delivered, findings = claim_evidence.deliver(raw)
        self.assertTrue(findings)
        self.assertNotIn('**Rules out:** Timing defect', delivered)
        self.assertIn('**Still-possible alternatives:** timing defect, Query defect, Rendering defect.', delivered)
        self.assertIn('**Positive evidence condition:** Match the durable commit and read key.', delivered)
        self.assertIn('**Rules out:** Storage defect.', delivered)
        self.assertIn('Inspect the read response.', delivered)
        # The same cause in different branches is not a contradiction.
        separate = ('### Branch A\nRules out: Query defect.\n'
                    '### Branch B\nStill-possible alternatives: Query defect.')
        self.assertEqual(claim_evidence.deliver(separate), (separate, []))

    def test_missing_receipts_cannot_assert_nonexecution_with_a_neighboring_caveat(self):
        raw = (Path(__file__).parent / 'fixtures/readiness_missing_receipts.txt').read_text()
        delivered, findings = claim_evidence.deliver(raw)
        self.assertTrue(findings)
        self.assertNotIn('readiness verification unexecuted', delivered)
        self.assertIn('absence of a receipt does not prove external execution never occurred', delivered)
        self.assertIn('active hold', delivered)
        for action in ('execution', 'inspection', 'verification', 'dispatch'):
            for predicate in ('unexecuted', 'not performed', 'not completed', 'has not started', 'was not issued'):
                bad = action.capitalize() + ' ' + predicate + ' and operational status unverified.'
                self.assertTrue(claim_evidence.violations(bad), bad)
                safe = 'It is not established whether ' + action + ' was ' + predicate + '.'
                self.assertFalse(claim_evidence.violations(safe), safe)
        supported = 'Inspection was not performed.'
        self.assertFalse(claim_evidence.violations(supported, trusted_facts=[supported]))
        from providers import ANSWER_RULES, REFERENCE_RULES
        for rules in (ANSWER_RULES, REFERENCE_RULES):
            self.assertIn('the predicate itself must be "unverified" or "not established"', ' '.join(rules.split()))

    def test_filtered_lists_never_retain_an_unfulfilled_count_promise(self):
        projection = {'unavailable': [], 'missing_inputs': False}
        for header, items in (
            ('The candidate must satisfy four acceptance criteria before qualification:', [
                '1. Reasoning: It distinguishes records from predictions.',
                '2. Usefulness: The answer completes the requested task.',
                '3. Constraints: It retains the correction.',
                '4. Evidence: The model leaves external execution unverified.']),
            ('Prepare a matched 4-turn qualification comparison:', [
                '- Turn 1: Request a draft while respecting their constraints.',
                '- Turn 2: Issue a correction.',
                '- Turn 3: Introduce a topic change.',
                '- Turn 4: Return to their initial task.']),
        ):
            with self.subTest(header=header):
                blocks = [{'fact': 'known'}, {'reasoning': 'The route guarantees zero charges.'},
                          {'reasoning': header + '\n' + '\n'.join(items)}]
                delivered, _, rejected, _ = resource_decision.compose_blocks(
                    blocks, {'known': 'Recorded resource fact.'}, projection)
                self.assertTrue(rejected)
                self.assertNotIn('guarantees zero charges', delivered)
                retained = sum(item in delivered for item in items)
                self.assertTrue(retained == 4 or header not in delivered, delivered)
                # Removing a promise must never resurrect a rejected child.
                self.assertNotIn(items[0], delivered)
                self.assertTrue(any(u['reason'] == 'incomplete_counted_list'
                                    for r in rejected for u in r['units']))
        complete = ('Prepare a matched 2-turn qualification comparison:\n'
                    '- Turn 1: Issue a draft request.\n- Turn 2: Introduce a correction.')
        delivered, _, rejected, _ = resource_decision.compose_blocks(
            [{'fact': 'known'}, {'reasoning': complete}], {'known': 'Recorded fact.'}, projection)
        self.assertIn(complete, delivered)
        self.assertFalse(rejected)
