"""Complete propositions and independent plans survive real answer delivery."""
import hashlib
import json
from pathlib import Path

import claim_evidence
import resource_decision
import task_queue
from reported_records import units
from test_webbob_replyq_1856 import SessionFixture


VALID = (
    'A passing majority does not clear the single failed browser check, which may point to an active regression or test defect.',
    'While the running code SHA is identified, there is no verified test execution record, build artifact validation, or live service-health check establishing that the server environment operates without latent regressions.',
    'No audit evidence establishes zero fees.',
    'No verified execution record establishes that the route preserves quality.',
    'The draft plan for the read-only readiness report, the isolation of the two primary gaps (functional build/test verification vs. multi-turn continuity/quality), and the diagnostic evaluation protocol are drafted in this chat.',
    'Prepare a read-only test report listing build/test evidence.',
    'Inspect the execution log or test artifact.',
    'We cannot assume (the route preserves quality).',
    'Check whether (the command is read-only).',
    '| Gap | Evidence |\n| Build/test validation vs. dialogue quality | Draft a read-only readiness report. |',
)
INVALID = (
    'The passing majority guarantees zero regressions.',
    'This route does not cause regressions.',
    'No fees are incurred.',
    'No verified execution record exists, but the route preserves quality.',
    'There is no verified record establishing safety, and the route guarantees zero regressions.',
    'No evidence establishes zero fees. This route is free of charges.',
    'The build/test command is read-only.',
    'Run the local test suite in read-only mode.',
    'The script will be read-only.',
    'The command is read-only today.',
    'The script is read-only when executed.',
    'The script remains read-only.',
    'The command currently is read-only.',
    'The script is (read-only).',
    'This route (preserves) quality.',
    'Do not assume (there are no fees. The command is read-only).',
    'Do not assume (there are no fees; the command is read-only).',
    'Do not assume ((there are no fees. The command is read-only)).',
    'Do not assume (the route preserves quality (the command is read-only)).',
    'Prepare a report (the test is guaranteed read-only).',
    'Prepare a report (including notes (the test is side-effect-free)).',
    'Prepare a read-only report, but the test is read-only.',
)
PLAN = ('Once funding settings are verified, run a matched 4-turn qualification comparison before changing defaults:\n'
    '- Turn 1 (Baseline task): Issue a realistic draft planning request under the saved constraints.\n'
    '- Turn 2 (Correction): Introduce a specific adjustment, verifying that the candidate retains it.\n'
    '- Turn 3 (Topic shift): Switch to an unrelated technical question to test context handling.\n'
    '- Turn 4 (Return to task): Ask the model to finalize the corrected plan.\n\n'
    'Acceptance criteria:\n'
    '- Delivered usefulness: Concrete reasoning without boilerplate evasion.\n'
    '- Constraint retention: Strict adherence to planning only across all turns.\n'
    '- Evidence integrity: Zero unverified claims or fabricated tool actions.')


class IntactDeliveryTests(SessionFixture):
    def test_complete_qualification_sequences_survive_rejected_assurances(self):
        from answer_fragments import independent_after_rejection

        samples = json.loads((Path(__file__).parent / 'fixtures' / 'qualification_answers.json').read_text())
        for blocks in samples:
            with self.subTest(blocks=blocks):
                known = {b['fact']: 'Recorded resource fact.' for b in blocks if 'fact' in b}
                delivered, _, rejected, _ = resource_decision.compose_blocks(blocks, known, self.projection())
                protocol = blocks[-1]['reasoning']
                # Preserve original numbering and the entire rubric, not just a count.
                start = protocol.index('1. ')
                end = protocol.find(' The saved project record', start)
                self.assertIn(protocol[start:end if end >= 0 else None], delivered)
                self.assertTrue(rejected)  # Billing assurances still lack evidence.
        self.assertFalse(claim_evidence.violations('Keep the existing route while preserving our quality bar.'))
        for claim in ('Keeping the existing route preserves quality.',
                      'The existing route preserves our quality bar.',
                      'Testing ensures we incur no unexpected billing.',
                      'Preserving the quality bar guarantees equivalent answers.',
                      'The route preserves the quality bar and continuity.'):
            self.assertTrue(claim_evidence.violations(claim), claim)
        self.assertTrue(independent_after_rejection('Introduce a sample and check whether it meets the format.'))
        self.assertFalse(independent_after_rejection('Check whether it can take over everything.'))
        for child in ('- Switching all conversation traffic to the candidate.',
                      'Acceptance criteria: The candidate qualifies only if checks pass, '
                      'and the candidate should handle all requests.'):
            blocks = [dict(fact='quality_bar'), dict(reasoning='The route guarantees zero charges.'),
                      dict(reasoning='Prepare a qualification comparison:\n'+child)]
            delivered, _, _, _ = resource_decision.compose_blocks(blocks, {'quality_bar': 'Keep the standard.'}, self.projection())
            self.assertNotIn(child, delivered)

    def projection(self):
        return resource_decision.project(self.root,dict(messages=[dict(role='user',request_id='owner',
            content='Can our Codex subscription replace the API route without lowering the quality standard?')]))

    def test_original_propositions_survive_ordinary_delivery_and_resource_formats(self):
        projection=self.projection()
        for value in VALID:
            with self.subTest(value=value):
                self.assertEqual(''.join(units(value)),value)
                self.assertFalse(claim_evidence.violations(value))
                self.fake.reply_text=value
                self.assertEqual(self.send('Explain the draft and evidence gaps without executing anything.')['content'],value)
                for body in (value+' [fact:purchase_vs_usage]',
                             [dict(fact='purchase_vs_usage'),dict(reasoning=value)]):
                    delivered,receipt=resource_decision.render(json.dumps(dict(answer=body,resource=None,
                        steps=['inspect_allowance'])),projection)
                    self.assertIn(value,delivered)
                    self.assertFalse(receipt.get('partial'))

    def test_sibling_and_embedded_assertions_remain_checked_with_original_offsets(self):
        for value in INVALID:
            with self.subTest(value=value):
                findings=claim_evidence.violations(value)
                self.assertTrue(findings)
                for finding in findings:
                    original=value[finding['start']:finding['end']]
                    self.assertEqual(finding['sha256'],hashlib.sha256(original.encode()).hexdigest())
                delivered,_=claim_evidence.deliver(value)
                self.assertNotEqual(value,delivered)
                self.assertEqual(delivered.count('('),delivered.count(')'))
                self.assertNotRegex(delivered,r'\n[.)]+\s*$')
        table='| Type | Conclusion |\n| Test | The test is read-only. |\nInspect the command contract next.'
        delivered,_=claim_evidence.deliver(table)
        self.assertNotIn('| Test |',delivered)
        self.assertIn('Inspect the command contract next.',delivered)

    def test_independent_conditional_protocol_survives_rejected_premise(self):
        bad='Retaining Gemini preserves conversation continuity and answer quality.'
        for body in (bad+'\n'+PLAN+' [fact:purchase_vs_usage]',
                     [dict(fact='purchase_vs_usage'),dict(reasoning=bad),dict(reasoning=PLAN)]):
            delivered,receipt=resource_decision.render(json.dumps(dict(answer=body,resource=None,
                steps=['inspect_allowance','preserve_standard'])),self.projection())
            self.assertNotIn(bad,delivered)
            self.assertIn(PLAN,delivered)
            self.assertTrue(receipt['partial'])
            self.assertFalse(receipt['execution_started'])
        self.fake.reply_text='I queued the review.\n'+PLAN
        delivered=self.send('Give a comparison plan without executing it.')['content']
        self.assertNotIn('I queued',delivered)
        self.assertIn(PLAN,delivered)
        self.assertFalse(task_queue.tasks(self.root))

    def test_plan_scope_cannot_certify_results_or_causal_recommendations(self):
        bad='Retaining Gemini preserves conversation continuity and answer quality.'
        for extra in ('Therefore move all conversation traffic to Codex.',
                      '- Result: The route guarantees zero charges.',
                      '- It can take over everything.',
                      'Since verification passed, Codex should handle all requests.',
                      'Acceptance criteria are already met.',
                      '- Recommendation: Codex should handle all requests.',
                      'Inspect current settings. Therefore quality is protected.'):
            with self.subTest(extra=extra):
                body=[dict(fact='purchase_vs_usage'),dict(reasoning=bad),dict(reasoning=PLAN+'\n'+extra)]
                delivered,receipt=resource_decision.render(json.dumps(dict(answer=body,resource=None,
                    steps=['preserve_standard'])),self.projection())
                self.assertIn(PLAN,delivered)
                self.assertNotIn(extra,delivered)
                self.assertNotIn('Therefore',delivered)
                self.assertTrue(receipt['partial'])

    def test_attached_steps_do_not_launder_operational_recommendations(self):
        bad='Retaining Gemini preserves conversation continuity and answer quality.'
        opener=PLAN.split('\n',1)[0]
        for child in ('- Switch all conversation traffic to Codex.',
                      '- Switch all conversation traffic to Codex for every topic.',
                      '- Check current account settings. Codex should handle all requests.',
                      '- Issue a realistic planning request. Codex should handle all requests.',
                      '- Issue a realistic planning request, and Codex should handle all requests.',
                      '- Introduce a placeholder and check its spelling. It can take over the task.'):
            with self.subTest(child=child):
                body=[dict(fact='purchase_vs_usage'),dict(reasoning=bad),dict(reasoning=opener+'\n'+child)]
                delivered,_=resource_decision.render(json.dumps(dict(answer=body,resource=None,
                    steps=['preserve_standard'])),self.projection())
                self.assertNotIn(child,delivered)
        criteria=opener+'\nAcceptance criteria:\n- Recommendation: Switch all conversation traffic to Codex.'
        body=[dict(fact='purchase_vs_usage'),dict(reasoning=bad),dict(reasoning=criteria)]
        delivered,_=resource_decision.render(json.dumps(dict(answer=body,resource=None,
            steps=['preserve_standard'])),self.projection())
        self.assertNotIn('Switch all conversation traffic',delivered)
        body=[dict(fact='purchase_vs_usage'),dict(reasoning=bad),dict(reasoning=
            'Prepare a protocol to move all work to Codex:\n- Switch all conversation traffic to Codex.')]
        delivered,_=resource_decision.render(json.dumps(dict(answer=body,resource=None,
            steps=['preserve_standard'])),self.projection())
        self.assertNotIn('Switch all conversation traffic',delivered)
        markdown=PLAN.replace('Acceptance criteria:','### Acceptance criteria')
        delivered,_=resource_decision.render(json.dumps(dict(answer=[dict(fact='purchase_vs_usage'),
            dict(reasoning=bad),dict(reasoning=markdown)],resource=None,steps=['preserve_standard'])),self.projection())
        self.assertIn(markdown,delivered)

    def test_facts_and_unrelated_headings_do_not_clear_dependency(self):
        bad='Retaining Gemini preserves conversation continuity and answer quality.'
        for blocks in (
            [dict(reasoning=bad),dict(fact='quality_bar'),dict(reasoning='It can take over everything.')],
            [dict(reasoning=bad),dict(reasoning=PLAN),dict(reasoning='Results:\n- Codex should handle all requests.')],
        ):
            delivered,receipt=resource_decision.render(json.dumps(dict(answer=[dict(fact='purchase_vs_usage'),*blocks],
                resource=None,steps=['preserve_standard'])),self.projection())
            self.assertNotIn('It can take over',delivered)
            self.assertNotIn('Codex should handle all requests',delivered)
            self.assertTrue(receipt['partial'])
