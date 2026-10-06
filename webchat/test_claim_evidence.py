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
        self.assertNotIn('[Unverified claim withheld]', answer['content'])

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
        self.assertNotIn('[Unverified claim withheld]', answer['content'])


class DeliveryCleanupTests(unittest.TestCase):
    def test_withheld_claims_read_as_finished_prose_without_guard_tags(self):
        source = ('Context Architecture Assessment: this route guarantees equal quality.\n'
                  'Next, inspect the stored evidence and name the acceptance check.')
        delivered, findings = claim_evidence.deliver(source)
        self.assertTrue(findings)
        self.assertNotIn('[Unverified claim withheld]', delivered)
        self.assertNotIn('guarantees equal quality', delivered)
        self.assertIn('inspect the stored evidence', delivered)
        self.assertEqual(delivered.count('The quality or continuity outcome is unverified'), 1)

    def test_empty_heading_and_empty_list_item_are_dropped_and_lists_renumber(self):
        source = ('1. Record the request identity.\n'
                  '2. This route guarantees zero charges.\n'
                  '3. Inspect the stored evidence.\n'
                  '5. **Operational State & Authorization:**')
        delivered, findings = claim_evidence.deliver(source)
        self.assertTrue(findings)
        self.assertNotIn('Operational State', delivered)
        self.assertNotRegex(delivered, r'(?m)^\s*\d+[.)]\s+(?:\*\*)?[^\n:]+:(?:\*\*)?\s*$')
        self.assertIn('1. Record the request identity.', delivered)
        self.assertIn('Inspect the stored evidence.', delivered)
        self.assertNotIn('guarantees zero charges', delivered)

    def test_global_queue_and_process_state_need_evidence_unlike_record_scope(self):
        safe = "This conversation hasn't started a task. No start receipt is recorded."
        self.assertFalse(claim_evidence.violations(safe))
        delivered, _ = claim_evidence.deliver(safe)
        self.assertIn("hasn't started a task", delivered)
        self.assertIn('no start receipt is recorded', delivered.lower())
        for value in (
            'With no active tasks or pending assignments currently queued. Draft the next check.',
            'There are zero completed effects. Draft the next check.',
            'Task status is Not Running. Draft the next check.',
            'I confirmed the running source SHA. Draft the next check.',
        ):
            with self.subTest(value=value):
                self.assertTrue(claim_evidence.violations(value), value)
                text, _ = claim_evidence.deliver(value)
                self.assertNotIn('[Unverified claim withheld]', text)
                self.assertIn('Draft the next check.', text)
                self.assertNotIn('currently queued', text)
                self.assertNotIn('Not Running', text)
                self.assertNotRegex(text.lower(), r'confirmed the running source sha')

    def test_journal_cursors_and_unretrieved_links_are_not_user_facing(self):
        source = ('Saved facts at journal cursor 57/60/66. See [pricing](https://learn.chatgpt.com/docs/pricing).\n'
                  'Inspect the stored evidence next.')
        delivered, _ = claim_evidence.deliver(source)
        self.assertNotIn('57', delivered)
        self.assertNotIn('journal cursor', delivered.lower())
        self.assertNotIn('learn.chatgpt.com', delivered)
        self.assertIn('Inspect the stored evidence next.', delivered)
        asked = claim_evidence.finish_delivery(
            'The journal cursor is 12.', source='What is the journal cursor?')
        self.assertIn('12', asked)
        kept = claim_evidence.finish_delivery(
            'Source: [docs](https://example.com/retrieved)',
            source='see https://example.com/retrieved')
        self.assertIn('https://example.com/retrieved', kept)

    def test_resource_packets_omit_incomplete_boilerplate_and_unretrieved_links(self):
        with tempfile.TemporaryDirectory() as temp:
            projection = resource_decision.project(Path(temp), dict(messages=[dict(
                role='user', id='1', request_id='1',
                content='Can our Codex subscription replace the API route?')]))
            delivered, receipt = resource_decision.render(json.dumps(dict(
                answer=[dict(fact='purchase_vs_usage'),
                        dict(reasoning='This route guarantees zero charges.')],
                resource=None, steps=['inspect_allowance'])), projection)
            self.assertTrue(receipt['partial'])
            self.assertNotIn('this answer is incomplete', delivered.lower())
            self.assertNotIn('Part of the proposed reasoning could not be verified', delivered)
            self.assertNotIn('learn.chatgpt.com', delivered)
            self.assertNotIn('[Unverified claim withheld]', delivered)
            self.assertNotIn("couldn't verify one proposed claim", delivered)
            self.assertIn('authentication route', delivered)


    def test_orphan_subordinate_fragments_are_dropped_after_guard_edits(self):
        leftover = ('No, keeping requests short guarantees neither outcome.\n'
                    'as neither route\'s analytical performance has been evaluated on this task yet.\n'
                    'Inspect the stored evidence next.')
        delivered = claim_evidence.finish_delivery(leftover)
        self.assertNotIn('as neither route', delivered)
        self.assertIn('Inspect the stored evidence next.', delivered)
        planning = ('Since we are in planning only and have no active tasks running.\n'
                    'Outline the next check.')
        delivered = claim_evidence.finish_delivery(planning)
        self.assertNotIn('Since we are in planning only', delivered)
        self.assertIn('Outline the next check.', delivered)
        complete = ('Because the hold remains active, keep the next check read-only.\n'
                    'As a result, inspect the stored evidence.')
        delivered = claim_evidence.finish_delivery(complete)
        self.assertIn('Because the hold remains active, keep the next check read-only.', delivered)
        self.assertIn('As a result, inspect the stored evidence.', delivered)

    def test_gapped_lists_and_removed_step_refs_are_repaired(self):
        gapped = '1. Record the request identity.\n3. Inspect the stored evidence.\n4. Keep the hold.\n6. Compare artifacts.'
        delivered = claim_evidence.finish_delivery(gapped)
        self.assertIn('1. Record the request identity.', delivered)
        self.assertIn('2. Inspect the stored evidence.', delivered)
        self.assertIn('3. Keep the hold.', delivered)
        self.assertIn('4. Compare artifacts.', delivered)
        self.assertNotIn('6.', delivered)
        table = ('| Step 1 | Record identity |\n'
                 '| Step 3 | Inspect evidence; this step passes steps 1 and 2 |\n'
                 '| Step 4 | Keep the hold |')
        delivered = claim_evidence.finish_delivery(table)
        self.assertIn('| Step 1 | Record identity |', delivered)
        self.assertIn('| Step 2 |', delivered)
        self.assertIn('| Step 3 |', delivered)
        self.assertNotIn('Step 4', delivered)
        self.assertNotIn('passes steps 1 and 2', delivered)
        self.assertIn('passes step 1', delivered)
        separate = '1. First list item.\n2. Second list item.\n\n1. Other list starts.\n2. Other list continues.'
        delivered = claim_evidence.finish_delivery(separate)
        self.assertIn('1. First list item.', delivered)
        self.assertIn('2. Second list item.', delivered)
        self.assertIn('1. Other list starts.', delivered)
        self.assertIn('2. Other list continues.', delivered)

    def test_repeated_fact_blocks_are_not_restated_on_later_turns(self):
        fact = resource_decision.facts({'resources': [], 'observed_at': 0})['purchase_vs_usage']
        first = fact + '\n\nInspect allowance dashboards next.'
        delivered = claim_evidence.drop_repeated_paragraphs(
            fact + '\n\nName the remaining unknowns before any comparison.', first)
        self.assertNotIn(fact, delivered)
        self.assertIn('Name the remaining unknowns before any comparison.', delivered)
        with tempfile.TemporaryDirectory() as temp:
            projection = resource_decision.project(Path(temp), dict(messages=[dict(
                role='user', id='1', request_id='1',
                content='Can our Codex subscription replace the API route?')]))
            packet = json.dumps(dict(answer=[dict(fact='purchase_vs_usage'),
                                             dict(reasoning='Name the remaining unknowns before any comparison.')],
                                     resource=None, steps=[]))
            delivered, _ = resource_decision.render(packet, projection, prior=fact)
            self.assertNotIn(fact, delivered)
            self.assertIn('Name the remaining unknowns', delivered)

    def test_observed_path_epochs_are_attributed_to_the_saved_record(self):
        source = ('Project memory: `conductor/webchat/memory/projects.json` '
                  '(observed timestamp `1791312692.083752`).\n\n'
                  'Queue state: conductor/state/queue.jsonl observed at 1791312692.\n\n'
                  'Inspect the stored evidence next.')
        delivered = claim_evidence.finish_delivery(source)
        self.assertNotIn('1791312692', delivered)
        self.assertNotIn('observed timestamp', delivered.lower())
        self.assertNotIn('conductor/webchat/memory/projects.json', delivered)
        self.assertIn('saved project record loaded with this chat', delivered)
        self.assertIn('as of the saved record', delivered)
        self.assertIn('Inspect the stored evidence next.', delivered)
        kept = 'Sign-in was observed recently. Remaining allowance is unverified until observed.'
        self.assertEqual(claim_evidence.finish_delivery(kept), kept)

    def test_repeated_resource_blocks_become_one_line_refs_when_facts_are_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            conversation = dict(messages=[dict(role='user', id='1', request_id='1',
                content='Suppose Gemini is depleted and Grok is unavailable. What can our subscriptions do?')])
            projection = resource_decision.project(Path(temp), conversation)
            packet = json.dumps(dict(answer=[dict(fact='availability'),
                dict(reasoning='Prepare a bounded comparison before any generation.')],
                resource=None, steps=['inspect_allowance', 'preserve_standard']))
            first, _ = resource_decision.render(packet, projection)
            self.assertIn('unavailable', first)
            self.assertNotIn('Same constraints as above', first)
            self.assertNotIn('BOTH', resource_decision.facts({'resources': [], 'observed_at': 0})['route_boundaries'])
            self.assertIn('configured route registry', resource_decision.facts({'resources': [], 'observed_at': 0})['route_boundaries'])
            second, _ = resource_decision.render(packet, projection, prior=first)
            self.assertNotIn(projection['facts']['availability'], second)
            self.assertIn('Same constraints as above', second)
            self.assertIn('Prepare a bounded comparison before any generation.', second)
            self.assertTrue(second.index('Prepare a bounded comparison') < second.index('Same constraints as above'))
            changed = dict(projection, unavailable=['gemini'], facts=dict(projection['facts'],
                availability='According to the current supplied constraints, gemini is unavailable. Preserve the quality standard, but do not depend on an unavailable route for generation. Prepare evidence and qualify an available candidate before switching; no alternative is qualified by subscription ownership alone.'))
            third, _ = resource_decision.render(json.dumps(dict(answer=[dict(fact='availability'),
                dict(reasoning='Name the remaining allowance check.')], resource=None, steps=[])),
                changed, prior=first + '\n\n' + second)
            self.assertIn('gemini is unavailable', third)
            self.assertIn('Name the remaining allowance check.', third)

    def test_repeated_preparation_steps_and_quality_bar_are_not_restated(self):
        with tempfile.TemporaryDirectory() as temp:
            projection = resource_decision.project(Path(temp), dict(messages=[dict(
                role='user', id='1', request_id='1',
                content='Can our Codex subscription replace the API route?')]))
            packet = json.dumps(dict(answer=[dict(fact='quality_bar'),
                dict(reasoning='This route guarantees zero charges.')],
                resource=None, steps=['inspect_allowance', 'preserve_standard']))
            first, receipt = resource_decision.render(packet, projection)
            self.assertTrue(receipt['partial'])
            self.assertIn('Proposed preparation steps (not started)', first)
            self.assertIn(projection['facts']['quality_bar'], first)
            second, _ = resource_decision.render(packet, projection, prior=first)
            self.assertNotIn(projection['facts']['quality_bar'], second)
            self.assertNotIn('Proposed preparation steps (not started)', second)
            self.assertIn('The previously listed preparation steps still apply.', second)


if __name__ == '__main__':
    unittest.main()
