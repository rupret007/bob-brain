"""Questions and requirements survive delivery; neighboring assertions stay checked."""
import json
import tempfile
from pathlib import Path

from test_webbob_replyq_1856 import SessionFixture
import claim_evidence
import resource_decision


VALID = (
    'No determination can be made regarding which proposal is better, more cost-effective, or lower risk.',
    'No conclusion can be drawn about whether the alternative offers equivalent quality.',
    'No conclusion can be drawn about whether this route guarantees equivalent quality.',
    'No conclusion can be drawn about whether the subscription route with the supplied context guarantees equivalent quality.',
    'No ranking can be established without both proposals.',
    'Next, we should outline the specific plan and verification criteria for maintaining cross-conversation continuity for your review.',
    'When you are ready to release the hold, what target scope do you want the report to evaluate: **a static audit of configuration, queue, and memory records**, or a **dry-run transcript simulation testing multi-turn continuity**?',
    'When you choose to release the hold, should the investigation scope remain restricted solely to **static file/code inspection**, or do you wish to permit **offline dry-run test scripts** once their isolation contracts have been verified?',
    '**No Guaranteed Outcomes:** Cannot assume cross-conversation continuity or preserved texting quality are automatic; they are requirements to be designed for and verified.',
    '**No Presumed Outcomes:** Zero regressions, preserved conversation quality, and conversation continuity cannot be assumed as inherent system behaviors; they are requirements to be designed for and verified.',
    'Zero costs and preserved quality cannot be assumed.',
    'Zero fees, equal quality and continuity are not established.',
    'We cannot assume equal quality and zero charges.',
    'We cannot assume equal quality and zero charges are automatic.',
    'Can we check whether the script is read-only before proposing it?',
    'Define acceptance criteria for avoiding regressions while maintaining quality.',
    'We should outline the next comparison and preserve quality as a requirement.',
    'Outline the criteria for this rollout to preserve quality.',
    '1. **Quality criteria:** Compare outputs and preserve quality as an acceptance requirement.\n2. **Verification:** Can the test command run read-only?',
    'You cannot determine which proposal is stronger, more cost-effective, or preferable, since the decision explicitly requires comparing both.',
    "Avoiding extra charges depends entirely on your subscription's actual remaining allowance and overage rules, which have not yet been verified.",
    'Preventing degradation requires representative comparisons.',
    'We cannot conclude that equivalent quality is established.',
    'No prices, relative advantages, or cost differences can be determined without both inputs.',
    'Neither fees nor quality differences can be established from the supplied evidence.',
    'We cannot determine costs, relative advantages, or quality differences without both inputs.',
    '**Comparative Strengths or Rankings:** No trade-offs, relative advantages, cost differences, or feasibility rankings can be determined without Proposal B\'s contents.',
    'No cost comparisons can be determined. Prepare the missing input next.',
    'No prices, fees, or API costs can be determined without both inputs.',
    'No cost claims, quota reports, or API limits can be verified without the records.',
    'No completed cost reports or API comparisons can be verified without the records.',
)

INVALID = (
    'No determination can be made without incurring charges.',
    'No determination can be made regarding rankings at no cost.',
    'No conclusion can be drawn about fees for zero charges.',
    'No payment will be made for these invocations.',
    'No conclusion can be drawn about costs, with this route guaranteeing equivalent quality.',
    'No determination can be made regarding which option is cheaper, but this route guarantees lower charges.',
    'No conclusion can be drawn about which route is cheaper, and the alternative guarantees equivalent quality.',
    'We cannot assume equal quality and this route is free of charges.',
    'We cannot assume equal quality and Codex is free of charges.',
    'We cannot assume equal quality and all generation is free of charges.',
    'We cannot assume equal quality, and subscriptions are free of charges.',
    'We cannot assume equal quality, and prepaid subscriptions are free of charges.',
    'No evidence of preserved quality, the test command is read-only.',
    'No assurances of equal quality, the test command is read-only.',
    'If login succeeds then the route guarantees equal quality without charges.',
    'If we use this subscription, zero costs are guaranteed.',
    'The criteria for this rollout preserve quality.',
    'The criteria for this rollout establish zero charges.',
    'Can we inspect the script now that the test command is read-only?',
    'Can we check the script because the test command is read-only?',
    '**No Guaranteed Outcomes:** This route guarantees equal quality.',
    'We specified the plan, and the configuration preserves continuity.',
    'Zero fees are established, and preserved quality cannot be assumed.',
    'We cannot determine which proposal is more cost-effective, but this route cannot incur charges.',
    'Avoiding charges depends on unverified allowance and overage rules; therefore this invocation is free of charges.',
    'Preventing degradation guarantees equivalent quality.',
    'No fees, charges, or overages will be incurred.',
    'No cost comparisons can be determined, and this route is free of charges.',
    'No cost comparisons can be determined; this route guarantees equivalent quality.',
    'No costs are known, guaranteeing zero charges.',
    'No costs are known, making this invocation free of charges.',
)


class DeliveredScopeTests(SessionFixture):
    def test_negative_subject_keeps_its_predicate_and_independent_claims_stay_separate(self):
        denial='No cost comparisons can be determined'
        source=denial+', and this route is free of charges. Prepare the missing input next.'
        delivered,findings=claim_evidence.deliver(source)
        self.assertIn(denial,delivered)
        self.assertIn('Prepare the missing input next.',delivered)
        self.assertEqual(len(findings),1)
        self.assertEqual(source[findings[0]['start']:findings[0]['end']],'this route is free of charges.')
        value='No fees, charges, or overages will be incurred.'
        delivered,findings=claim_evidence.deliver(value)
        self.assertEqual(value[findings[0]['start']:findings[0]['end']],value)
        self.assertNotIn('will be incurred',delivered)

    def test_retained_questions_denials_and_requirements_survive_ordinary_delivery(self):
        self.fake.reply_text = 'Choose the inspection scope.'
        self.send('Help plan a read-only Web Bob readiness report. Hold execution until I choose its scope.')
        for value in VALID:
            with self.subTest(value=value):
                self.assertFalse(claim_evidence.violations(value))
                self.fake.reply_text = value
                answer = self.send('Explain the scope and next evidence check; do not execute it.')
                self.assertEqual(answer['content'], value)
        for value in (
            'What is waiting for you is choosing the scope of the investigation so we know exactly which static files and checks you want examined under the hold.',
            'Compare the remaining evidence scope under the hold.',
            'Compare the remaining evidence scope under the hold on Web Bob before proposing changes.',
            'Under the hold, compare the saved evidence before proposing changes.',
            'Under the hold on Web Bob, compare the saved evidence.',
            'What remains unclear is whether the payment gateway is under the hold.',
        ):
            self.fake.reply_text = value
            self.assertEqual(self.send('Explain the pending scope decision.')['content'], value)
        for value in ('Discuss scope under the hold that is no longer active.',
                      'Discuss scope under the hold, which no longer applies.',
                      'The payment gateway remains under the hold.',
                      'The payment gateway is currently under the hold.',
                      'The payment gateway has remained under the hold.',
                      'The payment gateway is still subject to the hold.'):
            self.fake.reply_text = value
            self.assertNotEqual(self.send('Explain the pending scope decision.')['content'], value)
        self.fake.reply_text = 'What is confirmed is that the payment gateway remains under the hold.'
        self.assertNotEqual(self.send('Explain the pending scope decision.')['content'],self.fake.reply_text)
        self.fake.reply_text = 'Check whether billing is configured because the payment gateway remains under the hold.'
        self.assertNotEqual(self.send('Explain the pending scope decision.')['content'],self.fake.reply_text)
        self.send('Resume Web Bob')
        self.fake.reply_text = 'Compare the remaining evidence scope under the hold.'
        self.assertNotEqual(self.send('Explain the pending scope decision.')['content'], self.fake.reply_text)

    def test_independent_conclusions_are_not_exempted_by_neighboring_scope(self):
        for value in INVALID:
            with self.subTest(value=value):
                self.assertTrue(claim_evidence.violations(value))
                self.fake.reply_text = value + ' Match the request identity against saved state next.'
                answer = self.send('Explain the next evidence check; do not execute it.')
                self.assertNotEqual(answer['content'], self.fake.reply_text)
                self.assertIn('Match the request identity', answer['content'])

    def test_methodological_prevention_survives_without_establishing_quality(self):
        for source in (
            'Rejecting pacing guarantees prevents bias without establishing equal quality.',
            'No pacing guarantee is offered, which prevents rushing without establishing quality.',
            'All preparation prevents bias without establishing quality.',
            'While pacing cannot be guaranteed, preparation prevents bias without preserving quality.',
        ):
            with self.subTest(source=source):
                self.assertFalse(claim_evidence.violations(source))
                delivered, findings = claim_evidence.deliver(source)
                self.assertEqual(delivered, source)
                self.assertFalse(findings)

    def test_rejected_clauses_keep_independent_next_step_and_complete_list_items(self):
        source = ('1. Compare outputs, but this route guarantees zero regressions, and inspect the stored evidence.\n'
                  '2. This route guarantees zero regressions.\n3. Record the request identity.')
        answer, findings = claim_evidence.deliver(source)
        self.assertTrue(findings)
        self.assertIn('1. Compare outputs.',answer)
        self.assertIn('inspect the stored evidence.',answer)
        self.assertNotIn('[Unverified claim withheld]',answer)
        self.assertIn('Record the request identity.',answer)
        self.assertNotIn('2. This route guarantees zero regressions.',answer)
        self.assertNotIn(', but',answer)
        self.assertNotIn(', and',answer)
        for source in ('If login succeeds then the route guarantees zero charges.',
                       'If we use this subscription, zero costs are guaranteed.'):
            self.assertNotIn('If ',claim_evidence.deliver(source)[0])

    def test_resource_string_and_block_packets_share_scope_without_losing_steps(self):
        with tempfile.TemporaryDirectory() as folder:
            projection = resource_decision.project(Path(folder),dict(messages=[dict(role='user',
                id='owner', request_id='owner', content='Can our Codex subscription replace the API route?')]))
            for value in VALID:
                with self.subTest(value=value):
                    self.assertTrue(resource_decision.safe_reasoning(value))
                    for explanation in (value+' [fact:purchase_vs_usage]',
                                        [dict(fact='purchase_vs_usage'),dict(reasoning=value)]):
                        answer, receipt = resource_decision.render(json.dumps(dict(answer=explanation,
                            resource=None, steps=['inspect_allowance','preserve_standard'])),projection)
                        self.assertIn(value,answer)
                        self.assertFalse(receipt.get('partial'))
                        self.assertFalse(receipt['execution_started'])
            for value in INVALID:
                with self.subTest(value=value):
                    with self.assertRaises(ValueError):
                        resource_decision.render(json.dumps(dict(answer=value+' [fact:purchase_vs_usage]',
                            resource=None,steps=[])),projection)
                    answer,receipt = resource_decision.render(json.dumps(dict(answer=[
                        dict(fact='purchase_vs_usage'),dict(reasoning=value)], resource=None,
                        steps=['inspect_allowance'])),projection)
                    self.assertTrue(receipt['partial'])
                    self.assertFalse(receipt['execution_started'])
                    self.assertIn('authentication route',answer)
