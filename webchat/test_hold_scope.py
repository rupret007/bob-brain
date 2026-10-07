"""Complete pending decisions and contrary claims through actual Chat delivery."""
import copy
import json
from pathlib import Path

from test_webbob_replyq_1856 import SessionFixture
import task_queue

HOLD_RESUME_T2 = json.loads(Path(__file__).with_name('fixtures').joinpath(
    'hold_resume_delivery_1006d.json').read_text())


class HoldScopeTests(SessionFixture):
    def prepare_hold(self):
        self.fake.reply_text='The report scope remains to be chosen.'
        self.send('Help plan a read-only Web Bob readiness report. Hold execution until I choose its scope.')
        self.fake.reply_text='Source identity, verified evidence, and two largest gaps.'
        self.send('Include source identity, what is verified, and the two largest gaps. No texting or changes.')

    def test_pending_decision_preserves_coordination_quantifiers_and_purpose(self):
        self.prepare_hold()
        state=copy.deepcopy(self.chat.get(self.identifier)['intent_state'])
        choices=(
            '* Selecting and approving the inspection scope (e.g., all three phases versus narrowing strictly to continuity) so work can proceed under your chosen boundaries while respecting the hold.',
            '* Choosing all three inspection phases while respecting the hold.',
            '* Selecting and approving the scope under the hold on Web Bob.',
            '* The pending decision is choosing the scope while respecting the existing hold.',
            '* Choosing whether to inspect every section while respecting the hold.',
            '* Comparing all worker configurations under the hold on Web Bob.',
            '* Specifying every acceptance condition while honoring the current hold.',
            '* Choosing all phases while carefully respecting the hold.',
            '* Choosing all phases or only continuity under the hold.',
            '* Choosing the scope and resource requirements under the hold.',
            '* Choosing the scope and project priorities under the hold.',
            '* Comparing service functions and configuration under the hold.',
            '* Comparing functions under the hold.',
            '* Choosing the scope so that work can proceed while respecting the hold.',
            '* Comparing configuration and source identity under the hold.',
            '* Choosing between the full report and the continuity section under the hold.',
            '* Evaluating cost estimates, delivery criteria, and recovery options under the hold.',
        )
        for choice in choices:
            with self.subTest(choice=choice):
                full='**Finished:** The scope outline.\n\n**Waiting for you:**\n'+choice
                self.fake.reply_text=full
                answer=self.send('What have you actually finished, and what is waiting for me?')
                self.assertEqual(answer['content'],full)
                self.assertEqual(self.chat.get(self.identifier)['intent_state'],state)
        self.assertFalse(task_queue.tasks(self.root))

    def test_pending_governor_cannot_bind_foreign_holds_or_independent_effects(self):
        self.prepare_hold()
        state=copy.deepcopy(self.chat.get(self.identifier)['intent_state'])
        unsupported=(
            '* All workers are under the hold.',
            '* Choosing the scope under the hold on the backup daemon.',
            '* Choosing the scope while respecting the hold on WebJam.',
            '* Choosing the scope, and I released the hold.',
            '* Choosing the scope while respecting the hold, which has now been released.',
            '* Choosing the scope and the backup service is paused while respecting the hold.',
            '* Choosing the scope because the backup service is under the hold.',
            '* Choosing the scope while the backup service remains under the hold.',
            '* Choosing the scope since WebJam is under the hold.',
            '* Choosing the scope for WebJam under the hold.',
            '* Choosing the scope because the backup service remains firmly bound under the hold.',
            '* Choosing the scope because the backup service falls under the hold.',
            '* Choosing the scope while the backup service operates under the hold.',
            '* Choosing the scope and the backup daemon operates under the hold.',
            '* Choosing the scope or the backup pipeline falls under the hold.',
            '* Choosing the scope and all projects fall under the hold.',
            '* Choosing the scope leaves the backup service under the hold.',
            '* Choosing the scope keeps the backup service under the hold.',
            '* Choosing the scope and the external component operates under the hold.',
            '* Choosing the scope and the service functions under the hold.',
            '* Choosing the scope and services function under the hold.',
            '* Choosing the scope and workers work under the hold.',
            '* Choosing the scope and Codex works under the hold.',
            '* Choosing the scope so work can proceed, because the backup service operates while respecting the hold.',
            '* Choosing the scope and every lane falls under the hold.',
            '* Comparing scope, and it operates under the hold.',
            '* Choosing scope because the backup daemon operates and the continuity section falls under the hold.',
            '* Choosing the scope that the backup daemon operates under the hold.',
            '* Choosing the scope while respecting the hold on Web Bob and WebJam.',
            '* Codex: Choosing all phases while respecting the hold.',
            '* Running the inspection while respecting the hold.',
        )
        for content in unsupported:
            with self.subTest(content=content):
                self.fake.reply_text=content
                self.assertNotEqual(self.send('Explain the pending decision.')['content'],content)
                self.assertEqual(self.chat.get(self.identifier)['intent_state'],state)
        good='Choosing all phases while respecting the hold.'
        for extra in (' I cleared the hold.',' Codex has started the task.'):
            self.fake.reply_text=good+extra
            self.assertNotIn(extra.strip(),self.send('Explain the pending decision.')['content'])
        self.assertFalse(task_queue.tasks(self.root))

    def test_completed_release_and_global_exception_remove_reference_support(self):
        self.prepare_hold()
        self.send('Resume Web Bob')
        self.fake.reply_text='Choosing all phases while respecting the hold.'
        self.assertNotEqual(self.send('What is waiting for me?')['content'],self.fake.reply_text)
        self.send('Hold all work')
        self.send('Resume Web Bob')
        self.fake.reply_text='The hold still applies to all projects.'
        self.assertNotIn('all projects',self.send('Explain the Web Bob decision.')['content'])
        self.assertFalse(task_queue.tasks(self.root))

    def test_saved_hold_keeps_in_force_list_item_and_renumbers_after_a_drop(self):
        self.prepare_hold()
        raw = (
            '### Two Largest Gaps\n'
            '1. **Unselected Scope and Execution Hold:** Execution is on hold pending your scope '
            'decision. Until a scope (such as Option A or Option B) is chosen and released, no diagnostic '
            'queries or read-only checks can be dispatched.\n'
            '2. **Recorded Intent vs. Live Runtime Evidence:** The saved record contains saved '
            'owner policies, not runtime telemetry.\n'
        )
        self.fake.reply_text = raw
        answer = self.send('What are the two largest gaps?')
        self.assertIn('Execution is on hold pending your scope decision', answer['content'])
        self.assertRegex(answer['content'], r'(?m)^1\. \*\*Unselected Scope')
        self.assertRegex(answer['content'], r'(?m)^2\. \*\*Recorded Intent')
        mixed = (
            '### Two Largest Gaps\n'
            '1. **Unselected Scope and Execution Hold:** Execution is on hold pending your scope '
            'decision. Until a scope is chosen, no diagnostic queries can be dispatched.\n'
            '2. **Foreign hold:** The backup service is on hold pending your permission.\n'
            '3. **Recorded Intent vs. Live Runtime Evidence:** The saved record contains saved '
            'owner policies, not runtime telemetry.\n'
        )
        self.fake.reply_text = mixed
        answer = self.send('Name the gaps again.')
        self.assertNotIn('backup service is on hold', answer['content'])
        self.assertIn('Execution is on hold pending your scope decision', answer['content'])
        self.assertRegex(answer['content'], r'(?m)^1\. \*\*Unselected Scope')
        self.assertRegex(answer['content'], r'(?m)^2\. \*\*Recorded Intent')
        self.assertNotRegex(answer['content'], r'(?m)^3\. ')
        self.assertFalse(task_queue.tasks(self.root))

    def test_exposed_hold_resume_raw_keeps_both_named_gaps(self):
        self.prepare_hold()
        raw = HOLD_RESUME_T2['raw_answer']
        self.assertIn('* **Gap 2:', raw)
        self.assertEqual(HOLD_RESUME_T2['finish_reasons'], ['STOP'])
        self.fake.reply_text = raw
        answer = self.send(HOLD_RESUME_T2['prompt'])
        self.assertIn('### Two Largest Gaps', answer['content'])
        self.assertIn('Gap 1:', answer['content'])
        self.assertIn('Gap 2:', answer['content'])
        self.assertIn('no read-only verification task can be leased, scheduled, or executed',
                      answer['content'])
        self.assertNotIn('I queued', answer['content'])
        mixed = raw.rstrip() + '\nI queued the inspection task.\n'
        self.fake.reply_text = mixed
        guarded = self.send('Name the gaps again.')
        self.assertIn('Gap 2:', guarded['content'])
        self.assertIn('leased, scheduled, or executed', guarded['content'])
        self.assertNotIn('I queued the inspection task', guarded['content'])
        self.assertFalse(task_queue.tasks(self.root))

    def test_affirmative_queue_claims_stay_blocked_under_hold(self):
        self.prepare_hold()
        state = copy.deepcopy(self.chat.get(self.identifier)['intent_state'])
        claims = (
            'I queued and scheduled it.',
            'The task was leased, scheduled and started.',
            "It's been scheduled.",
            'It has been dispatched.',
            'No read-only task can be leased, scheduled, or executed. I queued it.',
            'No read-only task was leased, and I scheduled it.',
        )
        for claim in claims:
            with self.subTest(claim=claim):
                self.fake.reply_text = claim
                answer = self.send('Name the gaps again.')
                self.assertNotIn(claim, answer['content'])
                self.assertEqual(self.chat.get(self.identifier)['intent_state'], state)
                self.assertFalse(task_queue.tasks(self.root))

    def test_negative_passive_cannot_mask_contrast_or_progressive_effect(self):
        from dispatch_receipts import claims_dispatch, unasserted_prose
        for claim, predicate in (
            ('No read-only task was leased, however, scheduled another task.', 'scheduled'),
            ('No read-only task was queued, scheduling another task.', 'scheduling'),
        ):
            with self.subTest(claim=claim):
                self.assertIn(predicate, unasserted_prose(claim))
                self.assertTrue(claims_dispatch(claim))

    def test_passive_receipt_check_preserves_denials_and_conditions(self):
        from dispatch_receipts import claims_dispatch
        for text in (
            "It hasn't been scheduled.",
            "It's not been scheduled.",
            "If it's been scheduled, verify the receipt.",
            'No read-only verification task can be leased, scheduled, or executed.',
        ):
            with self.subTest(text=text):
                self.assertFalse(claims_dispatch(text))
