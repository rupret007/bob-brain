"""Complete pending decisions and contrary claims through actual Chat delivery."""
import copy

from test_webbob_replyq_1856 import SessionFixture
import task_queue


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
