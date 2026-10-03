"""Protected conclusions need support beyond adjacent true facts or conditions."""
import json
import tempfile
import unittest
from pathlib import Path

from test_webbob_replyq_1856 import SessionFixture
import claim_evidence
import resource_decision


class ClaimScopeTests(unittest.TestCase):
    def test_outcome_predicates_do_not_depend_on_modifiers(self):
        for words in ('unverified generation', 'future marginal API', 'previously unobserved provider', ''):
            value = 'Planning proceeds without incurring ' + words + ' charges.'
            with self.subTest(value=value):
                self.assertTrue(claim_evidence.violations(value))
        for value in (
            'The comparison won’t incur extra charges.',
            'Once budget admission is verified, the new model guarantees equivalent answers without extra charges.',
            'Keeping this route protects conversation continuity and prevents quality drops.',
            'The risk assessment guarantees zero texting regressions.',
            'An empty response proves the record was never persisted.',
            'If retrieval returns empty, that proof points to a persistence failure.',
            'Run the local test suite in read-only mode; it cannot change files.',
            'The tests are read-only.',
        ):
            with self.subTest(value=value):
                self.assertTrue(claim_evidence.violations(value))

    def test_proposals_questions_and_uncertainty_remain_useful(self):
        for value in (
            'We cannot promise the comparison will avoid extra charges. Inspect allowance and billing settings first.',
            'If access and budget admission are verified, compare matched tasks before considering a switch.',
            'Keeping the configuration unchanged avoids introducing a routing change; current availability and quality still need evidence.',
            'Matched tasks may reveal regressions.',
            'Require zero texting regression.',
            'Compare outputs to protect quality.',
            'Prepare inputs without purchasing another subscription.',
            'Can the comparison avoid extra charges?',
            'Check whether the test command is read-only.',
            'A missing result does not prove persistence failure.',
            'An empty response leaves several possible causes, including save, identity, access and retrieval.',
            'A stored record and matching successful retrieval with absent rendering support a client-side diagnosis for that path.',
        ):
            with self.subTest(value=value):
                self.assertEqual(claim_evidence.violations(value), [])

    def test_scope_cannot_transfer_to_an_appended_assurance(self):
        safe = 'We cannot promise the comparison will avoid extra charges'
        for separator in ('. ', '; ', ', but '):
            value = safe + separator + 'This route works without unforeseen invocation charges.'
            self.assertTrue(claim_evidence.violations(value), value)
        source = 'Explain the claim "This route incurs no extra charges."'
        quoted = 'The claim "This route incurs no extra charges." lacks evidence.'
        self.assertFalse(claim_evidence.violations(quoted, source=source))
        self.assertTrue(claim_evidence.violations(quoted + ' But Web Bob guarantees those costs.', source=source))
        self.assertTrue(claim_evidence.violations('This route will reduce demand and preserve quality.'))
        self.assertFalse(claim_evidence.violations('Compare outputs and preserve quality as an acceptance requirement.'))
        self.assertFalse(claim_evidence.violations('Inspect settings, compare outputs and preserve quality as an acceptance requirement.'))
        for boundary in (', but ', ' and ', ', however '):
            value = 'Inspect settings' + boundary + 'these models reduce demand and preserve quality.'
            self.assertTrue(claim_evidence.violations(value), value)
        self.assertFalse(claim_evidence.violations('Without current billing data, we cannot choose a provider.'))
        self.assertFalse(claim_evidence.violations('No changes to billing settings are proposed.'))
        self.assertTrue(claim_evidence.violations('It runs without extra charges after checking billing settings.'))
        self.assertTrue(claim_evidence.violations('It runs without incurring charges despite missing billing data.'))
        self.assertTrue(claim_evidence.violations('This route incurs no extra charges per the billing records.'))
        forbidden = 'Do not claim "no extra charges".'
        self.assertTrue(claim_evidence.violations('There are "no extra charges".', source=forbidden))
        self.assertTrue(claim_evidence.violations('The claim "no extra charges" is correct.', source=forbidden))
        self.assertTrue(claim_evidence.violations('I confirm the statement "no extra charges".', source=forbidden))
        self.assertTrue(claim_evidence.violations('The claim "no extra charges" has been verified.', source=forbidden))
        self.assertTrue(claim_evidence.violations('The risk analysis guarantees zero regression.',
            source='Draft a Web Bob handoff.', artifact=True))

    def test_exact_support_is_not_permission_for_a_stronger_conclusion(self):
        supported = 'This exact test command is read-only.'
        self.assertFalse(claim_evidence.violations(supported, trusted_facts=[supported]))
        self.assertTrue(claim_evidence.violations(supported + ' It guarantees zero regressions.', trusted_facts=[supported]))
        self.assertTrue(claim_evidence.violations('All test commands are read-only.', trusted_facts=[supported]))

    def test_legacy_and_structured_advice_share_protected_claim_checks(self):
        with tempfile.TemporaryDirectory() as temp:
            conversation = dict(messages=[dict(role='user', id='1', request_id='1',
                content='Which paid subscription should handle our project?')])
            projection = resource_decision.project(Path(temp), conversation)
            bad = 'Planning continues without incurring unverified generation charges.'
            structured = dict(answer=[dict(fact='purchase_vs_usage'), dict(reasoning=bad)],
                              resource=None, steps=['inspect_allowance', 'preserve_standard'])
            delivered, receipt = resource_decision.render(json.dumps(structured), projection)
            self.assertNotIn(bad, delivered)
            self.assertIn('acceptance criteria', delivered)
            self.assertTrue(receipt['partial'])
            self.assertFalse(receipt['execution_started'])
            self.assertTrue(receipt['rejected_blocks'][0]['claim_findings'])
            legacy = dict(structured, answer=bad + ' [fact:purchase_vs_usage]')
            with self.assertRaises(ValueError):
                resource_decision.render(json.dumps(legacy), projection)


class DeliveredClaimTests(SessionFixture):
    def test_ordinary_diagnostic_keeps_concrete_next_step_and_records_partial(self):
        self.fake.reply_text = 'An empty response proves persistence failure. Trace the same request through save and retrieval.'
        answer = self.send('Explain the possible causes of a missing result. Do not run anything.')
        self.assertNotIn('An empty response proves', answer['content'])
        self.assertIn('Trace the same request', answer['content'])
        self.assertIn('does not identify its cause', answer['content'])
        self.assertTrue(answer['claim_review']['partial'])

    def test_requested_commitment_and_draft_quote_do_not_become_app_effects(self):
        artifact = 'We’ll finish this workflow before adding integrations.'
        self.fake.reply_text = json.dumps(dict(artifact=artifact, commentary=''))
        answer = self.send('Write a note saying: '+artifact)
        self.assertEqual(answer['content'], artifact)
        self.assertTrue(answer['artifact']['accepted'])
        self.fake.reply_text = json.dumps(dict(artifact=artifact,
            commentary='This rollout guarantees zero texting regressions.'))
        answer = self.send('Revise the note and explain the rollout risk.')
        self.assertIn(artifact, answer['content'])
        self.assertNotIn('guarantees zero texting', answer['content'])
        self.assertIn('outcome is unverified', answer['content'])


if __name__ == '__main__':
    unittest.main()
