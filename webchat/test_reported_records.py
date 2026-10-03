"""Delivered record explanations retain meaning without acquiring authority."""
import hashlib
import unittest

from reported_records import units
from test_webbob_replyq_1856 import SessionFixture
import task_queue


class LayoutTests(unittest.TestCase):
    def test_identity_correction_invalidates_inherited_topic_but_cached_evidence_does_not(self):
        from reported_records import topic_record, source_bindings
        def record(text):
            return dict(user_excerpts=[dict(message_id='1',request_id='1',content='Fictional task V-57 is proposed.'),
                                      dict(message_id='2',request_id='2',content=text)])
        old=record('The cached artifact names task W-58, not V-57.')
        self.assertEqual(topic_record(old,source_bindings(old)),'V-57')
        corrected=record('Correction: the card is for task W-58, not V-57.')
        self.assertIsNone(topic_record(corrected,source_bindings(corrected)))

    def test_numbered_item_and_continuation_remain_one_unit(self):
        text = 'Checks:\n1. Confirm identity.\n2. Verify the permission record.\n   Keep the original attempt ID.\n3. Inspect the artifact.\n'
        parts = list(units(text))
        self.assertEqual(''.join(parts), text)
        self.assertIn('2. Verify the permission record.\n   Keep the original attempt ID.\n', parts)
        self.assertNotIn('2.', parts)


class ReportedRecordDeliveryTests(SessionFixture):
    def establish(self):
        self.fake.reply_text = 'The supplied record is held.'
        self.send('Reason about this fictional task record only: V-57 is on hold, with lease L-57 and source rev-57. No execution or worker-stop receipt exists. Do not create work.')

    def delivered(self, text):
        self.fake.reply_text = text
        return self.send('Explain the state and next check for V-57.')

    def test_bound_reduced_relative_does_not_become_dispatch_receipt(self):
        self.establish()
        valid = ('The task identity remains **V-57** (bound to lease `L-57` and assigned to `ReviewWorker`), '
                 'as re-submitting the request after a browser reload targets the existing task rather than creating a new one.\n\n'
                 'Its current status is **on hold** (accepted, but paused prior to execution). '
                 'Because the hold was recorded before any execution-start receipt and remains active, '
                 'the re-submission cannot dispatch or run the task.')
        self.assertEqual(self.delivered(valid)['content'], valid)
        for effect in (' I assigned Codex another task.', ' I queued your repair.',
                       ' Assigned your task to Claude.', ' Gemini has started your work.'):
            with self.subTest(effect=effect):
                self.assertNotIn(effect.strip(), self.delivered(valid+effect)['content'])
        for invalid in ('Unknown-58 (bound to L-58 and assigned to ReviewWorker).',
                        'V-57 (I assigned Codex the review).',
                        'V-57 (bound to L-57 and I assigned the task).',
                        'V-57 (bound to L-57 and assigned your task to Codex).',
                        'V-57 (bound to L-57 and queued your repair).',
                        'V-57 (bound to L-57 and queued in your live queue).'):
            self.assertNotEqual(self.delivered(invalid)['content'], invalid)
        from dispatch_receipts import claims_dispatch
        self.assertTrue(claims_dispatch(valid, reference='A generic explanation, with no source bindings.'))
        self.assertFalse(task_queue.tasks(self.root))

    def test_hold_prerequisite_retains_complete_list_and_topic_after_foreign_subject(self):
        self.establish()
        self.fake.reply_text='The older artifact does not establish the current task result.'
        self.send('A cached return names task ID V-56, not V-57. Explain the evidence checks.')
        valid = ('1. Check the identity against V-57.\n'
                 '2. **Hold and Authorization State:** The hold on `V-57` must be explicitly cleared, '
                 'and budget admission and execution authorization must be confirmed before any run can be considered valid.\n'
                 '3. Compare the actual artifact with the assigned source.')
        self.assertEqual(self.delivered(valid)['content'], valid)
        self.assertEqual(self.delivered('ReviewWorker may still be active. Maintain the hold and reject immediate reassignment.')['content'],
                         'ReviewWorker may still be active. Maintain the hold and reject immediate reassignment.')
        for invalid in ('The hold on V-57 must be cleared, and the hold is now cleared.',
                        'The hold on V-57 must have been cleared.',
                        'The hold must have been cleared.',
                        'The hold on V-57 must have already been cleared.',
                        'The hold on V-57 must surely have already been explicitly cleared.',
                        'ReviewWorker is offline. Its status is on hold.',
                        'The backup daemon is now held.',
                        'Maintain the hold on the backup daemon.'):
            self.assertNotEqual(self.delivered(invalid)['content'], invalid)
        self.assertFalse(self.chat.get(self.identifier)['intent_state']['holds'])

    def test_neutral_headings_do_not_delete_bound_facts_or_prerequisites(self):
        self.establish()
        for heading in ('Task Status', 'What actually exists in the record', 'Current disposition', 'Decision context'):
            text = '**'+heading+':** Task V-57 is recorded as on hold.\n\n* **What remains uncertain:** It is unverified whether ReviewWorker stopped after its lease expired.\n* **Next safe step:** Keep the hold in place and confirm worker termination before considering reassignment.'
            with self.subTest(heading=heading):
                answer = self.delivered(text)
                self.assertEqual(answer['content'], text)
                self.assertFalse(answer['authority_review']['partial'])
                bound = [r for r in answer['authority_review']['units'] if r['referenced_record'] == 'V-57']
                self.assertTrue(bound)
                self.assertTrue(all(r['source_bindings'] for r in bound))
        checklist = ('Before accepting the result for V-57, check:\n'
            '1. **Binding and Identity:** Match task V-57 and source rev-57.\n'
            '2. **Execution Validity:** The work must reflect an authorized execution that occurred after lifting the hold, rather than a replay.\n'
            '3. **Acceptance Criteria:** Check the actual artifact against the assigned scope.')
        self.assertEqual(self.delivered(checklist)['content'], checklist)
        self.assertFalse(task_queue.tasks(self.root))
        self.assertFalse(self.chat.get(self.identifier)['intent_state']['holds'])

    def test_foreign_heading_breaks_anaphora_but_explicit_task_body_restores_it(self):
        self.establish()
        for heading in ('External reviewer for V-57', 'Backup daemon', 'Web Bob', 'Codex'):
            bad = '**'+heading+':** Its status is on hold.'
            with self.subTest(heading=heading):
                self.assertNotEqual(self.delivered(bad)['content'], bad)
                good = '**'+heading+':** No worker-stop receipt is available.\n\n**Record status:** Task V-57 remains on hold.\n**Next action:** Keep the hold in force.'
                self.assertEqual(self.delivered(good)['content'], good)

    def test_state_modifier_never_binds_an_external_target(self):
        self.establish()
        for tail in ('in place', 'in force', 'in effect'):
            text = 'Keep the hold '+tail+' until the task evidence is reconciled.'
            self.assertEqual(self.delivered(text)['content'], text)
        for tail in ('on the backup service', 'in the external worker', 'in place for the backup service'):
            text = 'Keep the hold '+tail+'.'
            self.assertNotEqual(self.delivered(text)['content'], text)
        for tail in ("on task V-57's reviewer", 'on task V-57 reviewer', 'for task V-57’s service'):
            text = 'Keep the hold '+tail+'.'
            self.assertNotEqual(self.delivered(text)['content'], text)
        for tail in ('on task V-57', 'on task V-57 until the evidence is reconciled'):
            text = 'Keep the hold '+tail+'.'
            self.assertEqual(self.delivered(text)['content'], text)

    def test_atomic_item_removal_keeps_neighbors_and_reason(self):
        self.establish()
        bad = '2. **External reviewer:** Its status is on hold.\n'
        text = '1. Inspect the cached artifact identity.\n'+bad+'3. Task V-57 remains on hold.\n'
        answer = self.delivered(text)
        self.assertNotIn('2.', answer['content'])
        self.assertIn('1. Inspect the cached artifact identity.', answer['content'])
        self.assertIn('3. Task V-57 remains on hold.', answer['content'])
        removed = [r for r in answer['authority_review']['units'] if not r['accepted']]
        self.assertEqual(len(removed), 1)
        self.assertEqual(removed[0]['sha256'], hashlib.sha256(bad.encode()).hexdigest())
        self.assertEqual(removed[0]['reason'], 'unbound_hold_claim')

    def test_requirement_does_not_hide_completed_permission_change(self):
        self.establish()
        valid = '2. **Evidence to obtain:** The work must occur after lifting the hold.'
        self.assertEqual(self.delivered(valid)['content'], valid)
        for invalid in (' I cleared your real hold.', ' The permission is now granted.',
                        ' Verification that the hold was lifted has been received.'):
            answer = self.delivered(valid+invalid)
            self.assertNotIn(invalid.strip(), answer['content'])
        self.assertFalse(self.chat.get(self.identifier)['intent_state']['holds'])
        self.assertFalse(task_queue.tasks(self.root))

    def test_task_role_excludes_associated_lease_and_source_identifiers(self):
        self.fake.reply_text = 'The supplied task is held.'
        self.send('Reason about this fictional record: source rev-62 belongs to task P-62, which is on hold with lease L-62. Do not create work.')
        self.fake.reply_text = 'Its status is on hold.'
        answer = self.send('Explain the state for P-62.')
        self.assertEqual(answer['content'], self.fake.reply_text)
        self.assertEqual(answer['authority_review']['units'][0]['referenced_record'], 'P-62')
        for other in ('rev-62', 'L-62'):
            self.fake.reply_text = other+' remains on hold.'
            self.assertNotEqual(self.send('Explain the state for P-62.')['content'], self.fake.reply_text)

    def test_foreign_body_subject_and_completed_subordinate_change_are_rejected(self):
        self.establish()
        for text in ('The backup daemon is offline. It remains on hold.',
                     'ReviewWorker is offline. Its status is on hold.',
                     "Task V-57's reviewer is offline. It remains on hold.",
                     'The reviewer for task V-57 is offline. It remains on hold.',
                     'The work must be rechecked after the supervisor already lifted the hold.',
                     'The work must proceed after someone cleared the hold.'):
            self.assertNotEqual(self.delivered(text)['content'], text)
        text = 'The record does not prove the reviewer has stopped. Keep the hold in place.'
        self.assertEqual(self.delivered(text)['content'], text)


if __name__ == '__main__':
    unittest.main()
