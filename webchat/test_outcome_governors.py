"""Requested outcomes survive intact; unsupported achieved outcomes do not."""
import json
import tempfile
from pathlib import Path

import claim_evidence
import resource_decision
import task_queue
from test_webbob_replyq_1856 import SessionFixture


VALID = (
    'Which access and retrieval mechanism should meet the quality requirement?',
    'Which storage and retrieval mechanism should preserve quality?',
    'Which storage or retrieval mechanism should meet the continuity requirement?',
    'Which storage and retrieval mechanisms should we compare without degrading quality?',
    '* **Key Unresolved Decision:** Which context storage and retrieval mechanism should be adopted to achieve durable cross-conversation memory without degrading texting stability or conversational quality?',
    'Audit saved events to ensure continuity records are unbroken.',
    'Audit saved events to verify whether continuity was preserved.',
    '* **Proposed Diagnostic Check:** Audit recorded event sequences for project state saves, context reloads, and handoff cursors to ensure continuity records are unbroken.',
    'Keeping quality intact is an acceptance requirement.',
    'Whether quality remains intact is unverified.',
    'Inspect quality records and continuity criteria.',
    'Quality must remain intact as an acceptance requirement.',
    'Quality may remain intact; the comparison must establish that.',
    'Whether continuity remains unaffected is unknown.',
    'Quality records remain intact.',
    'Quality is not known to remain intact.',
    'Quality is required to remain intact.',
    'Continuity might still be unaffected.',
    'Can quality remain intact with this route?',
    'Audit events to establish whether continuity survived, and record missing evidence.',
    'Audit access logs to ensure continuity remains intact.',
    'Audit return values to ensure continuity records are unbroken.',
    'Quality must remain unchanged as an acceptance requirement.',
    'Quality may remain protected.',
    'Quality is not known to remain unchanged.',
    'Which access and retrieval mechanism should be adopted without degrading quality?',
    'Quality cannot remain intact.',
    'Quality will never remain intact.',
    'Which guarantees and safeguards should be designed without degrading quality?',
    'Which quality guarantees and safeguards should be designed without degrading quality?',
    'Which storage, and the retrieval mechanism should meet the continuity requirement?',
    'Audit stored events and access logs to ensure checks preserve continuity.',
    'Audit stored events and the access logs to ensure continuity records are unbroken.',
    'Audit stored events and the access logs to check whether the plan is guaranteed to preserve quality.',
)

INVALID = (
    'Which mechanism should we inspect, now that quality remains intact?',
    'Which mechanism should we inspect, and Gemini’s quality remains intact?',
    'The audit ensures continuity remains intact.',
    'Audit saved events, and continuity is guaranteed.',
    'Keeping Gemini means quality remains intact.',
    'Inspect the records because quality remains intact.',
    'Audit results confirm that continuity is unaffected.',
    'Conversation quality remains intact.',
    'Quality will remain intact because we retained Gemini.',
    'Continuity is unaffected, although its measurements are unknown.',
    'Audit events to establish whether continuity survived, and this route preserves quality.',
    'Quality is known to remain intact.',
    'The quality criteria are unknown; conversation quality is unaffected.',
    'Audit results show that quality remains intact.',
    'Audit results indicate that continuity is unaffected.',
    'Which storage, and Gemini is free of charges?',
    'Can we inspect the provider, and we access files without charges?',
    'Can we inspect the provider, and the workers access files without charges?',
    'Can we inspect the provider, and the models run without charges?',
    'Can we inspect the provider, and the workers read files without charges?',
    'Check whether quality remains intact, and the plan to preserve continuity guarantees quality.',
    'Which storage, and the active provider is free of charges?',
    'Check whether quality remains intact, and the plan to ensure continuity guarantees quality.',
    'Check whether quality remains intact, and the plan to confirm continuity guarantees quality.',
    'Can we inspect the plan, and the proposal to ensure continuity guarantees equivalent quality?',
    'Audit stored events, and the plan to ensure continuity guarantees quality.',
    'Check whether quality remains intact, and the plan to preserve quality is free of charges.',
    'Check whether quality remains intact, and the plan to ensure continuity is guaranteed to preserve quality.',
    'Audit stored events, and the plan to ensure continuity is guaranteed to preserve quality.',
    'Can we inspect the plan, and the proposal to preserve continuity is guaranteed to maintain quality?',
    'Audit stored events and the plan to ensure continuity is guaranteed to preserve quality.',
    'Audit stored events and the plan to ensure continuity guarantees quality.',
    'We will stay on the active Gemini route so quality remains intact, rather than switching routes just to save on usage costs.',
)


class OutcomeGovernorTests(SessionFixture):
    def test_complete_requested_meaning_survives_actual_chat_delivery(self):
        for value in VALID:
            with self.subTest(value=value):
                self.assertFalse(claim_evidence.violations(value))
                self.fake.reply_text = value
                answer = self.send('Explain the pending evidence check without executing it.')
                self.assertEqual(answer['content'], value)
        self.assertFalse(task_queue.tasks(self.root))

    def test_asserted_outcomes_are_withheld_but_independent_next_step_survives(self):
        for value in INVALID:
            with self.subTest(value=value):
                self.assertTrue(claim_evidence.violations(value))
                self.fake.reply_text = value + ' Match the saved request identity next.'
                answer = self.send('Explain what evidence is still needed without executing work.')
                self.assertNotEqual(answer['content'], self.fake.reply_text)
                self.assertIn('Match the saved request identity next.',answer['content'])
        self.assertFalse(task_queue.tasks(self.root))

    def test_both_resource_formats_use_the_same_governors_and_keep_planned_steps(self):
        with tempfile.TemporaryDirectory() as folder:
            projection = resource_decision.project(Path(folder),dict(messages=[dict(role='user',
                id='owner',request_id='owner',content='Can our Codex subscription replace the API route?')]))
            for value in VALID:
                with self.subTest(value=value):
                    self.assertTrue(resource_decision.safe_reasoning(value))
                    for explanation in (value+' [fact:purchase_vs_usage]',
                                        [dict(fact='purchase_vs_usage'),dict(reasoning=value)]):
                        answer, receipt = resource_decision.render(json.dumps(dict(answer=explanation,
                            resource=None,steps=['inspect_allowance','preserve_standard'])),projection)
                        self.assertIn(value,answer)
                        self.assertFalse(receipt.get('partial'))
                        self.assertFalse(receipt['execution_started'])
            for value in INVALID:
                with self.subTest(value=value):
                    with self.assertRaises(ValueError):
                        resource_decision.render(json.dumps(dict(answer=value+' [fact:purchase_vs_usage]',
                            resource=None,steps=[])),projection)
                    answer,receipt = resource_decision.render(json.dumps(dict(answer=[dict(fact='purchase_vs_usage'),
                        dict(reasoning=value)],resource=None,steps=['inspect_allowance'])),projection)
                    self.assertTrue(receipt['partial'])
                    self.assertFalse(receipt['execution_started'])
                    self.assertIn('authentication route',answer)

    def test_offsets_preserve_question_and_check_before_independent_claim(self):
        for first in (VALID[0], VALID[5]):
            value = first + ' However, conversation quality remains intact. Record the missing evidence.'
            delivered, findings = claim_evidence.deliver(value)
            self.assertEqual(len(findings),1)
            self.assertEqual(value[findings[0]['start']:findings[0]['end']],
                             ', conversation quality remains intact.')
            predicate=findings[0]['claims'][0]
            self.assertEqual(value[predicate['start']:predicate['end']],'intact')
            self.assertIn(first,delivered)
            self.assertIn('Record the missing evidence.',delivered)
