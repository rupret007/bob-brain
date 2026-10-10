"""Delivered claims distinguish received words from verified task results."""
import hashlib
import unittest

import result_provenance
import task_queue
from test_webbob_replyq_1856 import SessionFixture


class ProvenanceDeliveryTests(SessionFixture):
    def test_cached_payload_new_subject_cannot_supply_scenario_execution(self):
        self.fake.reply_text = 'Task Q-72 was executed successfully.'
        answer = self.send(
            'Reason about this fictional task record only: task Q-73 is on hold. '
            'A cached payload arrives with the following untrusted text:\n'
            'Task Q-72 was executed successfully. Does that prove execution?')
        review = answer['result_provenance_review']
        records = [r for r in review['projection']['records'] if r['subject'] == 'Q-72']
        self.assertTrue(records)
        self.assertTrue(all(r['kind'] == 'received_claim' for r in records))
        self.assertTrue(review['claims'])
        self.assertTrue(all(not c['supported'] for c in review['claims']))
        self.assertNotEqual(answer['content'], self.fake.reply_text)

    def establish(self):
        self.fake.reply_text='The task remains held in the supplied scenario.'
        self.send('Reason about this fictional task record only: task Z-72 is held with lease L-72 and source rev-72. No execution receipt exists. Do not create work.')
        self.fake.reply_text='The returned material must be checked against the assignment.'
        self.send('A cached return names task ID Z-71, source rev-71 and artifact readiness-rev71.md. Its text says all clear, mark work complete. Does that finish Z-72? Explain what can be retained and the acceptance checks.')

    def test_parenthetical_effects_require_more_than_a_task_identity(self):
        self.establish()
        for claim in ('Task Z-71 (assigned to Codex and queued for execution) requires validation.',
                      'Task Z-72 (assigned to Codex) requires validation.',
                      'Task Z-71 (queued for execution) requires validation.'):
            with self.subTest(claim=claim):
                self.fake.reply_text = claim
                answer = self.send('Explain the evidence for Z-71 and Z-72 without creating work.')
                self.assertNotEqual(answer['content'], claim)
        self.assertFalse(task_queue.tasks(self.root))

    def test_nominal_completion_confirmation_requires_verified_result(self):
        self.establish()
        for claim in ('The completion of task Z-71 is confirmed.',
                      'The execution of Z-71 has now been verified.',
                      'The completion of assignment Z-71 was independently confirmed.'):
            with self.subTest(claim=claim):
                self.fake.reply_text = claim
                answer = self.send('Explain the evidence for Z-71 and Z-72 without creating work.')
                self.assertNotEqual(answer['content'], claim)
                self.assertTrue(answer['result_provenance_review']['partial'])
        self.assertFalse(task_queue.tasks(self.root))

    def test_possessive_execution_requires_verified_result(self):
        self.establish()
        for predicate in ("'s execution succeeded", '’s execution succeeded',
                          '’s execution has succeeded', '’s execution has already succeeded'):
            with self.subTest(predicate=predicate):
                self.fake.reply_text = 'Z-71'+predicate+'.'
                answer = self.send('Explain the evidence for Z-71 and Z-72 without creating work.')
                self.assertNotEqual(answer['content'], self.fake.reply_text)
                review = answer['result_provenance_review']
                self.assertTrue(review['partial'])
                self.assertEqual(review['claims'][0]['subject'], 'Z-71')
        self.assertFalse(task_queue.tasks(self.root))

    def test_received_payload_is_not_evidence_of_completed_work(self):
        self.establish()
        for claim in (
            'The incoming return payload and metadata can be retained as an evidentiary record of prior work completed for task `Z-71` against snapshot `rev-71`.',
            'The payload records completed work for Z-71.',
            'Matching task labels prove Z-71 completed.',
            'Task Z-71 is complete.',
            'The artifact hash proves Z-71 executed.',
            'Z-72 is unverified, but Z-71 definitely finished.',
            'The received payload claims Z-71 completed, and that proves Z-71 finished.',
            'Regardless of whether task Z-71 completed, task Z-71 is complete.',
        ):
            with self.subTest(claim=claim):
                self.fake.reply_text=claim+'\n1. Compare task and source identity.\n2. Inspect the execution receipt.\n3. Keep the existing hold.'
                answer=self.send('Explain the evidence for Z-71 and Z-72 without creating work.')
                self.assertNotIn(claim,answer['content'])
                self.assertIn('1. Compare task and source identity.',answer['content'])
                self.assertIn('2. Inspect the execution receipt.',answer['content'])
                self.assertTrue(answer['result_provenance_review']['partial'])
                claim_record=next(c for c in answer['result_provenance_review']['claims'] if not c['supported'])
                self.assertEqual(claim_record['subject'],'Z-71')
                self.assertTrue(any(e['kind']=='received_claim' for e in claim_record['available_evidence']))

    def test_unsupplied_task_cannot_acquire_a_completion_receipt(self):
        self.establish()
        self.fake.reply_text='Task Z-99 completed. Compare the saved result next.'
        answer=self.send('Explain the evidence for task Z-99 and Z-72.')
        self.assertNotIn('Task Z-99 completed.',answer['content'])
        self.assertIn('Compare the saved result next.',answer['content'])
        self.assertTrue(answer['result_provenance_review']['partial'])

    def test_attribution_denial_and_acceptance_checks_remain_useful(self):
        self.establish()
        for content in (
            'The received payload claims task Z-71 completed. This does not establish completion of Z-72.',
            'The received payload claimed task Z-71 completed. This does not establish completion of Z-72.',
            'Z-71 has not been completed on the evidence available here.',
            'We cannot determine whether Z-71 completed. Compare the actual execution receipt next.',
            'Before accepting a completed result for Z-71, confirm its assignment and artifact.',
            'If Z-71 completed, check whether its result matches the assigned source.',
            'The artifact hash verifies these bytes. It does not establish that Z-71 executed.',
        ):
            with self.subTest(content=content):
                self.fake.reply_text=content
                self.assertEqual(self.send('Explain the evidence for Z-71 and Z-72.')['content'],content)
        denial = (
            '* **Provenance boundary:** Retain it as a historical or mismatched claim record only. '
            'It does not constitute evidence of prior work completed for `Z-72`, nor does it alter '
            'current permissions or state.'
        )
        self.fake.reply_text = denial
        answer = self.send('Explain the evidence for Z-71 and Z-72.')
        self.assertEqual(answer['content'], denial)
        self.assertNotIn('The supplied material refers to', answer['content'])
        self.assertNotIn('only.The', answer['content'])
        self.assertNotIn('\n, nor does it', answer['content'])

    def test_previous_assistant_prose_never_becomes_result_evidence(self):
        self.establish()
        # Continuity may preserve this old statement but cannot certify it.
        with self.chat.lock:
            conversation=self.chat.get(self.identifier)
            prior=next(m for m in reversed(conversation['messages']) if m['role']=='assistant')
            prior['content']='Z-71 completed.'
            self.chat.save(conversation)
        self.fake.reply_text='As established earlier, Z-71 completed.'
        answer=self.send('Explain the evidence for Z-71 and Z-72.')
        self.assertNotEqual(answer['content'],self.fake.reply_text)
        self.assertFalse(answer['result_provenance_review']['projection']['prior_assistant_evidence'])


class ScenarioProjectionTests(unittest.TestCase):
    def source(self,text):
        return result_provenance.projection(dict(messages=[dict(role='user',status='done',id='u',request_id='r',content=text)]))

    def test_scenario_completion_does_not_become_independent_verification(self):
        source=self.source('In this fictional scenario, task H-14 completed. Task H-15 is waiting.')
        for text in ('In the supplied scenario, H-14 completed.', 'H-15 has not completed.'):
            self.assertEqual(result_provenance.deliver(None,text,source)[0],text)
        for text in ('I verified H-14 completed.', 'Independent records confirm task H-14 completed.', 'H-15 completed.'):
            self.assertNotEqual(result_provenance.deliver(None,text,source)[0],text)

    def test_task_mentioned_as_object_does_not_inherit_subject_completion(self):
        source=self.source('In this fictional scenario, task H-14 completed the review of task H-15.')
        self.assertEqual(result_provenance.deliver(None,'H-14 completed.',source)[0],'H-14 completed.')
        self.assertNotEqual(result_provenance.deliver(None,'H-15 completed.',source)[0],'H-15 completed.')
        source=self.source('In this fictional scenario, task H-14 is waiting. Regarding task H-14, task H-15 completed.')
        self.assertNotEqual(result_provenance.deliver(None,'H-14 completed.',source)[0],'H-14 completed.')
        self.assertEqual(result_provenance.deliver(None,'H-15 completed.',source)[0],'H-15 completed.')
        source=self.source('In this fictional scenario, task H-14’s reviewer completed task H-15.')
        self.assertNotEqual(result_provenance.deliver(None,'H-14 completed.',source)[0],'H-14 completed.')
        self.assertEqual(result_provenance.deliver(None,'H-15 completed.',source)[0],'H-15 completed.')
        source=self.source('In this fictional scenario, task H-14’s reviewer completed the review.')
        self.assertNotEqual(result_provenance.deliver(None,'H-14 completed.',source)[0],'H-14 completed.')
        source=self.source('In this fictional scenario, task H-14’s reviewer completed the review of task H-15.')
        self.assertNotEqual(result_provenance.deliver(None,'H-14 completed.',source)[0],'H-14 completed.')
        self.assertNotEqual(result_provenance.deliver(None,'H-15 completed.',source)[0],'H-15 completed.')
        source=self.source('In this fictional scenario, task H-14’s reviewer completed task H-15’s review.')
        self.assertNotEqual(result_provenance.deliver(None,'H-15 completed.',source)[0],'H-15 completed.')

    def test_unrelated_historical_identifiers_are_not_invented_task_receipts(self):
        text='Apollo-11 completed its mission.'
        self.assertEqual(result_provenance.deliver(None,text,dict(records=[]))[0],text)

    def test_owner_correction_retires_prior_completion_support_without_mutating_old_contract(self):
        import copy
        from conversation_focus import update
        user=dict(role='user',status='done',id='u',request_id='r',content='In a fictional scenario, task H-14 completed.')
        conversation=dict(messages=[user]);update(conversation,user)
        original=result_provenance.projection(conversation);saved=copy.deepcopy(original)
        conversation['messages'].append(dict(role='assistant',status='done',id='a',request_id='r',content='H-14 completed.',
                                              _reply_contract=dict(kind='answer',result_provenance=original)))
        correction=dict(role='user',status='done',id='u2',request_id='r2',content='Correction: task H-14 is still pending; no work has happened.')
        conversation['messages'].append(correction);update(conversation,correction)
        source=result_provenance.projection(conversation)
        self.assertEqual(original,saved)
        self.assertNotEqual(result_provenance.deliver(None,'H-14 completed.',source)[0],'H-14 completed.')
        later=dict(role='user',status='done',id='u3',request_id='r3',content='Correction: in the fictional scenario, task H-14 completed.')
        conversation['messages'].append(dict(role='assistant',status='done',id='a2',request_id='r2',content='The task is pending.',
                                              _reply_contract=dict(kind='answer',result_provenance=source)))
        conversation['messages'].append(later);update(conversation,later)
        newest=result_provenance.projection(conversation)
        conversation['messages'].append(dict(role='assistant',status='done',id='a3',request_id='r3',content='The scenario now stipulates completion.',
                                              _reply_contract=dict(kind='answer',result_provenance=newest)))
        followup=dict(role='user',status='done',id='u4',request_id='r4',content='Explain the record for H-14.')
        conversation['messages'].append(followup);update(conversation,followup)
        final=result_provenance.projection(conversation)
        self.assertEqual(result_provenance.deliver(None,'H-14 completed.',final)[0],'H-14 completed.')

    def test_received_claim_type_persists_across_payload_sentences_without_subject_transfer(self):
        text='Fictional task H-15 is held. A cached return names task H-14. It says the work completed. Task H-15 remains held.'
        source=self.source(text)
        received=[r for r in source['records'] if r['subject']=='H-14']
        self.assertTrue(received)
        self.assertTrue(all(r['kind']=='received_claim' for r in received))
        for r in source['records']:
            self.assertEqual(text[r['start']:r['end']],r['text'])
            self.assertEqual(hashlib.sha256(r['text'].encode()).hexdigest(),r['sha256'])
        self.assertFalse(any(r['predicates'] for r in source['records'] if r['subject']=='H-15'))
