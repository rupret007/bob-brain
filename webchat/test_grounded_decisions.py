"""Protocol fields and resource guarantees cannot be authored by free prose."""
import json
import tempfile
from pathlib import Path
import time
import unittest

from test_webbob_replyq_1856 import SessionFixture
import catchup_contract
import resource_decision
import resource_inventory


class ProjectionTests(unittest.TestCase):
    def conversation(self, *texts):
        return dict(messages=[dict(role='user',id=str(i),request_id=str(i),content=t) for i,t in enumerate(texts)])

    def test_exclusive_cursor_and_empty_page_do_not_skip_next_event(self):
        for text in ('ACK through 149, since_seq 137, events 12, history_gap false, has_more true.',
                     'Receiver receipt: {"acknowledged_through":149,"since_seq":149,"events":0,"history_gap":false,"has_more":false}'):
            projection=catchup_contract.project(self.conversation(text))
            self.assertTrue(projection['valid'])
            self.assertEqual(projection['next_request'],{'since_seq':149})
            self.assertEqual(projection['next_possible_seq'],150)
            relay=catchup_contract.render('{"mode":"relay"}',projection)
            self.assertIn('since_seq=149',relay)
            self.assertNotIn('since_seq=150',relay)
            self.assertFalse(projection['execution_authority'])

    def test_gap_conflict_later_release_and_stale_instruction_are_not_authority(self):
        projection=catchup_contract.project(self.conversation('ACK through 137; since_seq 0; events 3; history_gap true; has_more true'))
        explanation=catchup_contract.render('{"mode":"explain"}',projection)
        self.assertIn('history gap',explanation)
        self.assertNotIn('events 1–137',explanation)
        self.assertIn('does not establish knowledge',catchup_contract.render('{"mode":"release"}',projection))
        self.assertIn('not current authorization',catchup_contract.render('{"mode":"authority"}',projection))
        for text in ('ACK through 149, acknowledged_through 150',
                     'ACK through 149, since_seq 137, events 11, history_gap false'):
            self.assertFalse(catchup_contract.project(self.conversation(text))['valid'])
        self.assertIsNone(catchup_contract.project(self.conversation('ACK through 149','New topic: discuss tides.')))

    def test_resource_decision_retains_missing_files_and_rejects_guarantee_fields(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            conversation=self.conversation('Suppose Gemini is depleted. What can our subscriptions do?',
                'What if Codex cannot read the needed project files?', 'Give me the best next step without buying anything.')
            projection=resource_decision.project(root,conversation)
            self.assertTrue(projection['missing_inputs'])
            answer,decision=resource_decision.render('{"resource":"codex","steps":["qualify_chat"]}',projection)
            self.assertIn('project-file snapshot',answer)
            self.assertIn('cannot verify the project',answer)
            self.assertIn('possible extra charges',answer)
            self.assertIn('comparable answer quality',answer)
            self.assertFalse(decision['execution_started'])
            for raw in ('{"resource":"codex","steps":["qualify_chat"],"answer":"No extra charges"}',
                        '{"resource":"gemini","steps":["keep_current"]}',
                        '{"resource":"cursor","steps":["prepare_report"]}'):
                with self.assertRaises(ValueError):resource_decision.render(raw,projection)

    def test_receiver_cursor_and_ack_withdrawal_cannot_reuse_another_receipt(self):
        for later in ('What should Dot read next?',
                      'Correction: that ACK never happened; it only read the page. What cursor now?',
                      'It never acknowledged anything. What cursor should Grok use?'):
            projection=catchup_contract.project(self.conversation('Grok ACK through 149.',later))
            self.assertFalse(projection['valid'])
            answer=catchup_contract.render('{"mode":"relay"}',projection)
            self.assertNotIn('since_seq=149',answer)
        own=catchup_contract.project(self.conversation('Grok ACK through 149.','What should Grok read next?'))
        self.assertEqual(own['receiver'],'grok')
        self.assertEqual(own['next_request'],{'since_seq':149})
        request=catchup_contract.project(self.conversation('Grok ACK through 149.',
            'Write a catch-up request telling Grok to only read the next batch and never execute old events.'))
        self.assertTrue(request['valid'])

    def test_stale_authenticated_record_cannot_imply_known_quality_or_capacity(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);p=root/resource_inventory.OBSERVATION;p.parent.mkdir(parents=True)
            p.write_text(json.dumps(dict(version=1,resources=dict(codex=dict(observed_at=time.time()-3600,
                authenticated=True,remaining_usage=100,extra_usage=False,quality_evidence={'qualified':True,'task':'conversation'})))))
            projection=resource_decision.project(root,self.conversation('Can our Codex subscription replace Gemini?'))
            answer,_=resource_decision.render('{"resource":"codex","steps":["qualify_chat"]}',projection)
            self.assertIn('First verify',answer)
            self.assertIn('remaining allowance',answer)
            self.assertIn('possible extra charges',answer)
            self.assertIn('comparable answer quality',answer)

    def test_resource_negation_questions_and_native_comparisons_keep_their_scope(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            projection=resource_decision.project(root,self.conversation('Our subscriptions: Gemini is depleted.',
                'Correction: Gemini is not unavailable; Codex is not available.'))
            self.assertEqual(projection['unavailable'],['codex'])
            question=resource_decision.project(root,self.conversation('Is our Codex subscription unavailable?'))
            self.assertFalse(question['unavailable'])
            projection=resource_decision.project(root,self.conversation('Compare Dot and Grok subscriptions in a table.'))
            answer,_=resource_decision.render('{}',projection)
            self.assertIn('| Dot |',answer);self.assertIn('| Grok |',answer)
            self.assertNotIn('| Codex |',answer)
            changed=resource_decision.project(root,self.conversation('Consider only Claude for a subscription alternative.',
                'Actually, only Codex or Cursor now; what should I try?'))
            self.assertEqual(changed['allowed_resources'],['codex','cursor'])


class DeliveredTests(SessionFixture):
    def test_server_delivers_typed_catchup_fields_and_no_fake_model_cursor(self):
        self.fake.reply_text='{"mode":"relay"}'
        answer=self.send('Grok ACK through 149. Write a concise catch-up request I can relay.')
        self.assertIn('since_seq=149',answer['content'])
        self.assertEqual(answer['catchup_observation']['provenance'],'owner_reported_receipt')
        self.assertNotIn('_reply_contract',self.chat.public(self.chat.get(self.identifier))['messages'][-1])

    def test_resource_packet_uses_server_evidence_and_cannot_advance_a_job(self):
        self.fake.reply_text='{"resource":"codex","steps":["qualify_chat","inspect_allowance"]}'
        answer=self.send('What should our Codex subscription do if Gemini is unavailable?')
        self.assertIn('representative question',answer['content'])
        self.assertFalse(answer['resource_decision']['execution_started'])

    def test_invalid_proposal_preserves_explicit_provider_constraint(self):
        self.fake.reply_text='Use Codex; no more costs.'
        answer=self.send('Consider only Claude for a subscription alternative to Gemini. What next?')
        self.assertIn('Claude',answer['content'])
        self.assertNotIn('Codex',answer['content'])
        self.assertFalse(answer['resource_decision']['model_proposal_accepted'])


if __name__=='__main__':unittest.main()
