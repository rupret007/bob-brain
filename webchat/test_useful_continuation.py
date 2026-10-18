"""Plans survive bounded claim rejection without gaining execution authority."""
import json
import tempfile
from pathlib import Path

import claim_evidence
import dispatch_receipts
import resource_decision
import task_queue
from app import Chat
from test_webbob_replyq_1856 import SessionFixture


PURPOSES = (
    'To avoid unexpected metered charges, we should verify whether the route uses a subscription login or a separately billed API key.',
    'To prevent degradation, prepare matched comparisons.',
    'To limit spending, inspect the allowance and overage settings.',
    'We should inspect quotas without assuming equal quality.',
    'We should inspect quotas without assuming the Codex route guarantees equal quality.',
    'We should inspect quotas without assuming our Codex route guarantees equal quality.',
    'Without presuming free usage, inspect the account settings.',
    'To stay within current paid accounts without assuming unmetered capacity, the first step is to inspect the active quota, reset dates, and overage policies across Codex, Cursor, and Claude.',
)
ASSERTIONS = (
    'To avoid unexpected charges, this route guarantees zero costs.',
    'This route is guaranteed to prevent degradation.',
    'Inspect allowances without incurring charges.',
    'Without assuming free usage, this route nevertheless incurs no charges.',
    'Without assuming equal quality, the replacement preserves quality.',
    'Without assuming equal quality, replacements preserve continuity.',
    'Without assuming equal quality, Codex guarantees equivalent answers.',
    'Without assuming equivalent answers, use the route without charges.',
    'No fees, charges, or overages will be incurred.',
    'We should inspect quotas without assuming equal quality and guarantee zero charges.',
    'This route is sure to avoid charges.',
    'The route’s ability to avoid charges is established.',
    'We should inspect quotas without assuming equal quality and will guarantee zero charges.',
    'Without assuming free usage we guarantee zero charges.',
    'Without assuming free usage quality remains intact.',
)
CHECK = 'Prepare matched multi-turn comparisons with an owner correction, a topic switch and a return to the corrected task.'


class UsefulContinuationTests(SessionFixture):
    def projection(self):
        return resource_decision.project(self.root,dict(messages=[dict(role='user',request_id='owner',
            content='Can our Codex subscription replace the API route without lowering the quality standard?')]))

    def test_purpose_and_negated_assumption_survive_actual_chat(self):
        for value in PURPOSES:
            with self.subTest(value=value):
                self.assertFalse(claim_evidence.violations(value))
                self.fake.reply_text=value
                self.assertIn(value,self.send('Explain the proposed verification and its next step.')['content'])
        self.assertFalse(task_queue.tasks(self.root))

    def test_appended_guarantees_stay_checked_in_both_formats(self):
        projection=self.projection()
        for value in ASSERTIONS:
            with self.subTest(value=value):
                self.assertFalse(resource_decision.safe_reasoning(value))
                for body in (value+' '+CHECK+' [fact:purchase_vs_usage]',
                             [dict(fact='purchase_vs_usage'),dict(reasoning=value),dict(reasoning=CHECK)]):
                    delivered,receipt=resource_decision.render(json.dumps(dict(answer=body,resource=None,
                        steps=['inspect_allowance','preserve_standard'])),projection)
                    self.assertTrue(receipt['partial'])
                    self.assertIn(CHECK,delivered)
                    self.assertNotIn(value,delivered)
                    self.assertFalse(receipt['execution_started'])
                    self.assertFalse(receipt['model_proposal_accepted'])

    def test_resource_purpose_survives_both_formats(self):
        projection=self.projection()
        for value in PURPOSES:
            with self.subTest(value=value):
                for body in (value+' [fact:purchase_vs_usage]',
                             [dict(fact='purchase_vs_usage'),dict(reasoning=value)]):
                    delivered,receipt=resource_decision.render(json.dumps(dict(answer=body,resource=None,
                        steps=['inspect_allowance'])),projection)
                    self.assertIn(value,delivered)
                    self.assertFalse(receipt.get('partial'))

    def test_rejected_premise_cannot_promote_a_dependent_recommendation(self):
        projection=self.projection()
        invalid='Codex has unlimited free capacity.'
        for dependent in ('Therefore Codex should handle all requests.',
                          'Codex should handle all requests.',
                          'With that capacity, move all work to Codex.',
                          'Move all work to Codex, therefore.',
                          'Inspect current account settings. Therefore move all conversation traffic to Codex.',
                          'Therefore: Prepare a migration to Codex.',
                          'It can take over the task.'):
            for body in (invalid+' '+dependent+' '+CHECK+' [fact:purchase_vs_usage]',
                         [dict(fact='purchase_vs_usage'),dict(reasoning=invalid),
                          dict(reasoning=dependent),dict(reasoning=CHECK)]):
                with self.subTest(dependent=dependent,body=type(body).__name__):
                    delivered,receipt=resource_decision.render(json.dumps(dict(answer=body,resource=None,
                        steps=['preserve_standard'])),projection)
                    self.assertNotIn(invalid,delivered)
                    self.assertNotIn(dependent,delivered)
                    self.assertNotIn('Therefore',delivered)
                    self.assertIn(CHECK,delivered)
                    self.assertTrue(receipt['partial'])

    def test_invalid_only_legacy_packet_still_fails(self):
        with self.assertRaises(ValueError):
            resource_decision.render(json.dumps(dict(answer='[fact:purchase_vs_usage] This route guarantees zero costs.',
                resource=None,steps=[])),self.projection())

    def test_negated_passive_preserves_held_plan_and_owner_scope_choice(self):
        self.fake.reply_text='Choose whether the report should examine static configuration or recorded transcripts.'
        self.send('Help plan a read-only Web Bob readiness report. Hold execution until I choose its scope.')
        plan=('Prepare the evidence checklist common to both options. No outbound test transmissions are dispatched during the check. '
              'For static configuration, compare the saved permissions with the proposed report contract. '
              'For recorded transcripts, match each correction to the next delivered answer. '
              'The owner still needs to choose between static configuration and recorded transcripts before execution.')
        for prompt in ('Keep going with the plan, but the hold still applies.',
                       'Continue preparing the options while keeping execution held.'):
            self.fake.reply_text=plan
            answer=self.send(prompt)
            self.assertIn(plan,answer['content'])
            self.assertNotEqual(answer['content'],dispatch_receipts.NO_DISPATCH)
        self.chat.close();self.chat=Chat(self.folder,self.root,self.fake)
        self.assertTrue(self.chat.get(self.identifier)['messages'])
        self.assertFalse(task_queue.tasks(self.root))

    def test_negated_subject_never_shields_other_actor_or_appended_receipt(self):
        for value in ('No diagnostic audits have been launched.',
                      'Zero outbound verification tasks will be dispatched.',
                      'No outbound test transmissions are dispatched during the check.'):
            with self.subTest(value=value):self.assertFalse(dispatch_receipts.claims_dispatch(value))
        for value in ('No outbound tests are dispatched, but Codex has queued the review.',
                      'No diagnostic audits from the worker that has launched your task are available.',
                      'No outbound tests are dispatched. I queued the review.',
                      'No logs remain because Codex has queued the review.',
                      'No doubt Codex has queued the review.',
                      'No doubt the worker is queued.',
                      'No doubt your task has been dispatched.',
                      'No outbound tests are dispatched. webchat-0123456789abcdef0123456789abcdef'):
            with self.subTest(value=value):self.assertTrue(dispatch_receipts.claims_dispatch(value))

    def test_rejected_dispatch_does_not_erase_independent_check(self):
        bad='I queued the review.'
        self.fake.reply_text=bad+' Therefore wait for the result. '+CHECK
        answer=self.send('Give me the comparison plan and concrete next step without execution.')
        self.assertNotIn(bad,answer['content'])
        self.assertNotIn('wait for the result',answer['content'])
        self.assertIn(CHECK,answer['content'])
        self.assertFalse(task_queue.tasks(self.root))

    def test_restart_effects_are_checked_without_erasing_negation_or_proposals(self):
        for value in ('I will restart the review.', 'I will get the project restarted.',
                      'I will get the project restarted before inspection.',
                      'We get it assigned by the dispatcher.', 'Restarted the review.'):
            with self.subTest(value=value):
                self.assertTrue(dispatch_receipts.claims_dispatch(value))
                self.fake.reply_text=value+' '+CHECK
                delivered=self.send('Give the proposed next check without executing it.')['content']
                self.assertNotIn(value,delivered)
                self.assertIn(CHECK,delivered)
        for value in ('No work is restarted.', 'No reviews have been restarted.',
                      'We get the assigned inputs.', 'We get reports from the restarted service.',
                      'We get reports from the restarted, overloaded service.',
                      'I can get the project restarted.', 'Ask Bob to restart the review when ready.'):
            with self.subTest(value=value):self.assertFalse(dispatch_receipts.claims_dispatch(value,reference='Explain the proposed options.'))

    def test_quality_followup_delivers_comparison_not_denial(self):
        self.fake.reply_text=json.dumps(dict(answer=[dict(fact='quality_bar'),dict(reasoning=CHECK)],
            resource=None,steps=['preserve_standard']))
        self.send('I pay for Codex and Cursor subscriptions. Help plan a replacement for the API route.')
        answer=self.send("I don't want worse answers to save a few cents.")
        self.assertIn(CHECK,answer['content'])
        self.assertNotEqual(answer['content'],dispatch_receipts.NO_DISPATCH)
        self.assertFalse(task_queue.tasks(self.root))

    def test_foreign_actor_rejection_does_not_rebind_its_hold(self):
        self.fake.reply_text='The supplied record is held.'
        self.send('Reason about this fictional task record: K-63 is held before execution. Explain its status.')
        self.fake.reply_text='K-63 remains held. Codex has queued the review. It remains on hold. '+CHECK
        answer=self.send('Explain the next check for K-63.')
        self.assertNotIn('Codex has queued',answer['content'])
        self.assertNotIn('It remains on hold',answer['content'])
        self.assertIn(CHECK,answer['content'])

    def test_cross_sentence_actor_effect_keeps_original_context(self):
        self.fake.reply_text='Codex is the proposed reviewer. It has queued the review. '+CHECK
        answer=self.send('Explain the proposed comparison without execution.')
        self.assertNotIn('It has queued',answer['content'])
        self.assertIn(CHECK,answer['content'])

    def test_false_permission_does_not_leave_its_consequence(self):
        self.fake.reply_text='The hold is cleared. Therefore proceed with the inspection. '+CHECK
        answer=self.send('Explain the proposed comparison without execution.')
        self.assertNotIn('The hold is cleared',answer['content'])
        self.assertNotIn('Therefore proceed',answer['content'])
        self.assertIn(CHECK,answer['content'])

    def test_unbound_reference_keeps_evidence_limits_but_not_action_consequences(self):
        self.fake.reply_text='The supplied record is held.'
        self.send('Reason about this fictional task record: T-8 is held before execution. A cached return for T-7 claims completion; no execution receipts are verified.')
        evidence='The cached return is a received claim, not proof that T-7 was validly executed or that T-8 is complete.'
        self.fake.reply_text='The backup service remains on hold. '+evidence+' Therefore resume execution. '+CHECK
        answer=self.send('Explain what the received evidence establishes and the next checks.')
        self.assertIn(evidence,answer['content'])
        self.assertNotIn('Therefore resume execution',answer['content'])
        self.assertNotIn('backup service remains on hold',answer['content'])
        self.assertIn(CHECK,answer['content'])
