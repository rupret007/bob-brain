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
    def test_provider_display_case_does_not_change_unavailable_routes(self):
        with tempfile.TemporaryDirectory() as temp:
            projection = resource_decision.project(Path(temp), self.conversation(
                'Suppose Gemini is depleted and Grok is unavailable. What can our subscriptions do?'))
            self.assertEqual(set(projection['unavailable']), {'gemini', 'grok'})
            self.assertIn('Gemini, Grok are unavailable', projection['facts']['availability'])
            with self.assertRaises(ValueError):
                resource_decision.validate_route('gemini', ['qualify_chat'], projection)

    def test_relay_returns_information_without_queue_ack_write(self):
        for request in ('Draft a read-only catch-up relay.', 'Draft a read-only catch-up relay and save the checkpoint.'):
            projection = catchup_contract.project(self.conversation('Grok ACK through 149.', request))
            answer = catchup_contract.render('{"mode":"relay"}', projection)
            self.assertIn('Return checkpoint/acknowledgment information only', answer)
            self.assertIn('if the user explicitly requested that save', answer)
            self.assertIn('Do not write a queue acknowledgment or change task state', answer)
            self.assertNotIn('then acknowledge', answer)
            self.assertIn('Preserve completed work and holds', answer)
            self.assertIn('do not execute tasks, deploy, send messages', answer)

    def conversation(self, *texts):
        return dict(messages=[dict(role='user',id=str(i),request_id=str(i),content=t) for i,t in enumerate(texts)])

    def test_json_page_limit_is_bounded_current_and_cannot_be_inherited_from_model(self):
        for limit in (1,8,80):
            value=catchup_contract.project(self.conversation('ACK through 60.',f'Draft a JSON page request with limit {limit}.'))
            answer=catchup_contract.render('{"mode":"authority"}',value)
            self.assertIn('"since_seq":60',answer)
            self.assertIn('"limit":'+str(limit),answer)
            self.assertIn('61–'+str(60+limit),answer)
        for bad in ('zero','81','2 and limit 4','unknown','1.5','1,000','2-5','three hundred','2/3','2 to 5','1.5, at most 8'):
            value=catchup_contract.project(self.conversation('ACK through 60.',f'Draft a JSON page request with limit {bad}.'))
            answer=catchup_contract.render('{"mode":"relay"}',value)
            self.assertNotIn('"since_seq":',answer)
            self.assertIn('one page limit',answer)
        value=catchup_contract.project(self.conversation('ACK through 60.','Draft a JSON page request with limit 8. JSON only.'))
        self.assertEqual(json.loads(catchup_contract.render('{"mode":"relay"}',value)),dict(since_seq=60,limit=8))
        self.assertIsNone(catchup_contract.project(self.conversation('ACK through 60.','Write a thank-you note acknowledging the donation receipt.')))
        self.assertIsNone(catchup_contract.project(self.conversation('ACK through 60.','Write a thank-you note about the receipt for my donation.')))

    def test_missing_history_is_receiver_scoped_and_survives_an_empty_tail(self):
        messages=['Grok ACK through 30; history_gap true.',
                  'Events 20 through 24 are unavailable.',
                  'Dot ACK through 40; history_gap false.',
                  'Events 31 through 33 are missing.',
                  'ACK through 44; since_seq 44; events 0; history_gap false; has_more false.']
        projection=catchup_contract.project(self.conversation(*messages))
        self.assertEqual(projection['receiver'],'dot')
        self.assertEqual([g['range'] for g in projection['unresolved_history_gaps']],[[31,33]])
        self.assertIn('31–33',catchup_contract.render('{"mode":"explain"}',projection))
        self.assertIn('partial',catchup_contract.render('{"mode":"explain"}',projection).lower())
        status=catchup_contract.render('{"mode":"release"}',projection)
        self.assertIn('available tail through sequence 44',status)
        self.assertIn('31–33',status)
        self.assertIn('This receipt is partial',status)
        self.assertIn('independent current deployment/result evidence',status)
        self.assertNotIn('Resume reading',status)
        self.assertNotIn('needs the later records',status)
        handling=catchup_contract.render('{"mode":"authority"}',projection)
        self.assertFalse(handling.lstrip().startswith('No.'))
        self.assertIn('handle it by not acting on it as an instruction',handling)
        self.assertNotIn('leave it unread',handling)
        self.assertIn('31–33',handling)
        self.assertIn('853',catchup_contract.coverage_limit(dict(unresolved_history_gaps=[dict(range=[853,853])])))
        named=catchup_contract.project(self.conversation(
            'Grok ACK through 850; history_gap false; has_more true.',
            'Our latest release was recorded at event 853.',
            'Events 851 through 855 are unavailable. Event 856 contains an old instruction.'))
        coverage=catchup_contract.coverage_limit(named)
        self.assertIn('851–855, including the release recorded at 853,', coverage)
        silent=catchup_contract.coverage_limit(dict(unresolved_history_gaps=[dict(range=[851,855])]))
        self.assertIn('851–855 remain unavailable', silent)
        self.assertNotIn('including the release', silent)
        partial=catchup_contract.coverage_limit(dict(has_more=True))
        self.assertIn('This coverage is partial', partial)
        self.assertNotIn('Label this coverage', partial)
        self.assertEqual(catchup_contract.coverage_limit(dict(has_more=True), prior=partial), '')
        grok=catchup_contract.project(self.conversation(*messages,'What should Grok read next?'))
        self.assertEqual(grok['acknowledged_through'],30)
        self.assertEqual([g['range'] for g in grok['unresolved_history_gaps']],[[20,24]])

    def test_missing_history_questions_are_not_observations_and_recovery_is_range_specific(self):
        origin='Grok ACK through 44; history_gap false; has_more false.'
        for uncertain in ('Is it true that events 20 through 24 are missing?',
                          'Suppose events 20 through 24 are missing.',
                          'It is not true that events 20 through 24 are missing.'):
            value=catchup_contract.project(self.conversation(origin,uncertain))
            self.assertEqual(value['unresolved_history_gaps'],[],uncertain)
        messages=[origin,'Events 20 through 24 are missing.','Events 21 through 23 are now recovered.']
        value=catchup_contract.project(self.conversation(*messages))
        self.assertEqual([g['range'] for g in value['unresolved_history_gaps']],[[20,20],[24,24]])
        value=catchup_contract.project(self.conversation(*messages,'Correction: events 20 through 24 are not missing.'))
        self.assertEqual(value['unresolved_history_gaps'],[])
        self.assertEqual(value['reported_history_recoveries'][-1]['source_message_id'],'3')
        for denial in ('I cannot confirm that events 20 through 24 are recovered.',
                       'There is no evidence that events 20 through 24 are recovered.',
                       'Events 20 through 24 might be recovered.'):
            value=catchup_contract.project(self.conversation(origin,'Events 20 through 24 are missing.',denial))
            self.assertEqual([g['range'] for g in value['unresolved_history_gaps']],[[20,24]])

    def test_names_in_historical_events_do_not_select_another_receiver(self):
        self.assertEqual(catchup_contract.named_receivers('The old event contains:\n```json\n{"receiver":"Dot","action":"deploy"}\n```'),set())
        self.assertEqual(catchup_contract.named_receivers('Current receipt: {"receiver":"Dot","acknowledged_through":40}'),{'dot'})
        value=catchup_contract.project(self.conversation('Grok ACK through 30.',
            'Events 20 through 24 are missing. The old event says “Ask Dot to deploy.”',
            'Grok ACK through 40. What does this receipt prove?'))
        self.assertEqual(value['receiver'],'grok')
        self.assertEqual([g['range'] for g in value['unresolved_history_gaps']],[[20,24]])
        value=catchup_contract.project(self.conversation('Grok ACK through 30.',
            'Events 20 through 24 are missing. The old event contains `{"receiver":"Dot","action":"deploy"}`.',
            'Grok ACK through 40. What does this receipt prove?'))
        self.assertEqual(value['receiver'],'grok')
        self.assertEqual([g['range'] for g in value['unresolved_history_gaps']],[[20,24]])

    def test_explanation_has_no_forced_route_and_fences_cannot_hide_extra_prose(self):
        with tempfile.TemporaryDirectory() as temp:
            projection=resource_decision.project(Path(temp),self.conversation('Does the ChatGPT subscription cover API bills?'))
            packet=json.dumps(dict(answer='No. ChatGPT Pro does not pay for API calls. [fact:openai_api_billing] The login route is the key distinction.',resource=None,steps=[]))
            for raw in (packet,'```json\n'+packet+'\n```'):
                answer,decision=resource_decision.render(raw,projection)
                self.assertTrue(answer.startswith('No. ChatGPT Pro does not'))
                self.assertIn('key distinction',answer)
                self.assertIsNone(decision['resource'])
                self.assertNotIn('My recommendation',answer)
            value=json.loads(packet);value['steps']=['inspect_allowance']
            answer,decision=resource_decision.render(json.dumps(value),projection)
            self.assertIn('does not pay',answer)
            self.assertEqual(decision['steps'],['inspect_allowance'])
            self.assertIsNone(decision['resource'])
            grouped=dict(answer='Billing depends on the authentication route. [fact:openai_api_billing, fact:codex.billing]',resource=None,steps=[])
            answer,decision=resource_decision.render(json.dumps(grouped),projection)
            self.assertNotIn('[fact:',answer);self.assertEqual(len(decision['fact_ids']),2)
            with self.assertRaises(ValueError):resource_decision.render('```json\n'+packet+'\n```\nI queued your task.',projection)

    def test_grounded_fact_cannot_launder_adjacent_guarantee_or_fake_inspection(self):
        with tempfile.TemporaryDirectory() as temp:
            projection=resource_decision.project(Path(temp),self.conversation('Can Codex replace our paid API route?'))
            for claim in ('Your quota is protected.', 'This guarantees equal quality.',
                          'It is not free, but it is unlimited.', 'There will be no additional charges.',
                          'Quota is unknown and this guarantees equal quality.',
                          'It is not free and it is unlimited.',
                          'I have not checked quota and I inspected your files.',
                          'This test guarantees equal quality.',
                          'Our comparison guarantees no extra charges.',
                          'Without a new subscription we guarantee the same quality.',
                          'We are not changing plans since this route is free.',
                          'Rather than wait this route provides equal quality.',
                          'Rather than being slow this route is free.',
                          'Treat it as bounded rather than unlimited, and it is free.',
                          'Rather than offering evidence this guarantees equal quality.',
                          'Conversation pacing prevents quota exhaustion.',
                          'This route is preserving quality.',
                          'This route protects quality.',
                          'This route maintains quality.',
                          'Pacing will reduce demand and preserve quality.',
                          'Pacing prevents rate limits.', 'I inspected your files.',
                          'We keep the configuration so quality and continuity remain protected.',
                          'If the subscription is active this route is free.',
                          'This route is proven to protect quality.',
                          'We can read your project files.', 'I queued your task.'):
                with self.subTest(claim=claim),self.assertRaises(ValueError):
                    resource_decision.render(json.dumps(dict(answer='[fact:codex.observation] '+claim,resource=None,steps=[])),projection)
            for clause in ('Login does not guarantee equal quality.', 'That is not free.',
                           'Pacing cannot prevent rate limits.', 'File access is unverified.',
                           'Paying for a subscription does not make API requests free.',
                           'Compare the outputs rather than assuming equal quality.',
                           'We cannot assume this provider produces equivalent answers.',
                           'Subscription access is not an unlimited pool.',
                           'Use a bounded allowance rather than being completely unlimited.',
                           'Use capped candidates rather than unlimited resources.',
                           'The route draws from an allowance rather than offering unlimited usage.',
                           'It consumes a capped allowance rather than providing free usage.',
                           'Check remaining quota rather than assuming login guarantees capacity.',
                           '**Preserving quality:** Compare the delivered outputs first.',
                           'Preserve quality by comparing outputs first.'):
                answer,_=resource_decision.render(json.dumps(dict(answer=clause+' [fact:codex.observation]',resource=None,steps=[])),projection)
                self.assertIn(clause,answer)

    def test_composed_facts_and_proposals_preserve_scope_and_rejection_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            projection=resource_decision.project(Path(temp),self.conversation('Can our Codex subscription replace the API route?'))
            for reasoning in ('Compare results to protect quality.',
                              'Wait until a representative comparison establishes the same quality bar.',
                              'An allowance does not mean usage is unlimited or free from incremental charges.'):
                blocks=[dict(fact='purchase_vs_usage'),dict(reasoning=reasoning)]
                answer,decision=resource_decision.render(json.dumps(dict(answer=blocks,resource=None,steps=['inspect_allowance'])),projection)
                self.assertIn(reasoning,answer);self.assertFalse(decision['partial'])
            for bad in ('Our comparison guarantees equal quality.',
                        'Check the limits to protect quality, and our allowance is protected.',
                        'It does not mean usage is unlimited, but this route is free.',
                        'I queued your task.'):
                blocks=[dict(fact='purchase_vs_usage'),dict(reasoning=bad)]
                answer,decision=resource_decision.render(json.dumps(dict(answer=blocks,resource=None,steps=[])),projection)
                self.assertNotIn(bad,answer);self.assertTrue(decision['partial'])
                self.assertFalse(decision['model_proposal_accepted']);self.assertEqual(decision['rejected_blocks'][0]['index'],1)
                self.assertNotIn("couldn't verify one proposed claim",answer)
                self.assertNotIn('answer is incomplete',answer)
            for blocks in ([dict(fact='invented')],[dict(fact='quality_bar',reasoning='Extra field')],
                           [dict(reasoning='Keep thinking.')]):
                with self.assertRaises(ValueError):
                    resource_decision.render(json.dumps(dict(answer=blocks,resource=None,steps=[])),projection)

    def test_invalid_explanation_keeps_only_independently_validated_preparation(self):
        with tempfile.TemporaryDirectory() as temp:
            projection=resource_decision.project(Path(temp),self.conversation('What should our paid subscription do when needed files are missing?'))
            for bad in ('Proceed without risking unexpected charges or degraded responses.',
                        'This lets us compare without purchasing a new service or triggering unintended charges.',
                        'The setup works without incurring extra costs.',
                        'Preparing inputs entails zero risk of overages.'):
                packet=dict(answer=[dict(fact='purchase_vs_usage'),dict(reasoning=bad)],resource=None,steps=['provide_inputs','inspect_allowance','preserve_standard'])
                answer,decision=resource_decision.render(json.dumps(packet),projection)
                self.assertNotIn(bad,answer);self.assertTrue(decision['partial'])
                self.assertFalse(decision['model_proposal_accepted']);self.assertFalse(decision['execution_started'])
                self.assertEqual(decision['steps'],[])
                self.assertEqual(decision['verified_preparation_steps'],packet['steps'])
                self.assertIn('Proposed preparation steps (not started)',answer)
                self.assertIn('multi-turn corrections',answer)
                self.assertIn('require budget admission',answer)
                for resource,steps in ((None,['qualify_chat']),('codex',['prepare_report']),(None,['invented'])):
                    with self.assertRaises(ValueError):resource_decision.render(json.dumps(dict(packet,resource=resource,steps=steps)),projection)
            self.assertTrue(resource_decision.safe_reasoning('Prepare the inputs without purchasing another subscription.'))
            self.assertTrue(resource_decision.safe_reasoning('We cannot promise a comparison without incurring extra costs.'))
            self.assertFalse(resource_decision.safe_reasoning('We cannot promise a comparison without incurring extra costs, but this route runs without extra charges.'))

    def test_unavailable_current_route_cannot_be_kept_by_any_packet_format(self):
        with tempfile.TemporaryDirectory() as temp:
            conversation=self.conversation('Suppose Gemini is depleted; what can our subscriptions do?')
            conversation['preferred_provider']='gemini'
            projection=resource_decision.project(Path(temp),conversation)
            self.assertTrue(projection['current_route']['unavailable'])
            self.assertNotIn('keep_current',projection['allowed_steps'])
            for value in (dict(resource='claude',steps=['keep_current']),
                          dict(answer='Preserve the standard. [fact:quality_bar]',resource=None,steps=['keep_current']),
                          dict(answer=[dict(fact='availability')],resource='claude',steps=['keep_current'])):
                with self.assertRaises(ValueError):resource_decision.render(json.dumps(value),projection)
            answer,decision=resource_decision.render(json.dumps(dict(answer=[dict(fact='availability'),
                dict(reasoning='Prepare the evidence and comparison criteria before any generation.')],
                resource=None,steps=['preserve_standard','provide_inputs'])),projection)
            self.assertIn('unavailable',answer);self.assertFalse(decision['execution_started'])
            packet=dict(answer=[dict(fact='availability'),dict(reasoning='Keep the current qualified route active.')],
                        resource=None,steps=['preserve_standard'])
            answer,decision=resource_decision.render(json.dumps(packet),projection)
            self.assertTrue(decision['partial']);self.assertNotIn('Keep the current qualified route active.',answer)
            for text in ('Use Gemini for the next reply.','Keep Gemini active.',
                         'Use Gemini after Codex is available.',
                         'Use Gemini now and plan the comparison after it is restored.',
                         'Use Gemini for the next reply and plan the comparison after it is restored.',
                         'Use Gemini once it is restored and keep Gemini active now.'):
                packet['answer'][1]['reasoning']=text
                answer,decision=resource_decision.render(json.dumps(packet),projection)
                self.assertTrue(decision['partial']);self.assertNotIn(text,answer)
            for text in ('Do not use Gemini for the next reply.', 'Use Gemini only after it is restored.',
                         'Once Gemini is restored, use Gemini for the next reply.'):
                packet['answer'][1]['reasoning']=text
                answer,decision=resource_decision.render(json.dumps(packet),projection)
                self.assertFalse(decision['partial']);self.assertIn(text,answer)
            comparison=dict(projection,requested_view='comparison')
            for value in (dict(resource='claude',steps=['keep_current']),dict(packet,extra=True)):
                with self.assertRaises(ValueError):resource_decision.render(json.dumps(value),comparison)

    def test_missing_input_cause_is_not_inferred_from_adapter_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            projection=resource_decision.project(Path(temp),self.conversation('Our Codex subscription cannot read the needed project files.'))
            packet=dict(answer=[dict(fact='missing_inputs'),
                dict(reasoning='The missing file access reflects the chat adapter boundary.'),
                dict(reasoning='Therefore we can conclude the cause is settled.')],resource=None,steps=['provide_inputs'])
            answer,decision=resource_decision.render(json.dumps(packet),projection)
            self.assertTrue(decision['partial']);self.assertNotIn('reflects',answer);self.assertNotIn('Therefore',answer)
            self.assertEqual(len(decision['rejected_blocks']),2)
            packet['answer'][1]['reasoning']='Which evidence should we inspect now that missing file access is caused by the sandbox?'
            answer,decision=resource_decision.render(json.dumps(packet),projection)
            self.assertTrue(decision['partial']);self.assertNotIn('now that',answer)
            packet['answer']=[dict(fact='missing_inputs'),dict(reasoning='File access might reflect a chat adapter limit; inspect the error before choosing a remedy.')]
            answer,decision=resource_decision.render(json.dumps(packet),projection)
            self.assertFalse(decision['partial']);self.assertIn('inspect the error',answer)

    def test_comparison_keeps_model_reasoning_and_missing_inputs_survive_explanation(self):
        with tempfile.TemporaryDirectory() as temp:
            projection=resource_decision.project(Path(temp),self.conversation('Compare Codex and Claude subscriptions.'))
            answer,_=resource_decision.render(json.dumps(dict(answer='For a bounded review, begin with the supported report interface. [fact:claude.reach]',resource=None,steps=[])),projection)
            self.assertIn('begin with',answer)
            projection=resource_decision.project(Path(temp),self.conversation('Our Codex subscription cannot read the needed project files.', 'What next?'))
            answer,_=resource_decision.render(json.dumps(dict(answer='[fact:codex.reach] Define a short evidence checklist first.',resource=None,steps=[])),projection)
            self.assertIn('inputs unavailable',answer)
            restored=resource_decision.project(Path(temp),self.conversation('Our Codex subscription cannot read the needed project files.',
                'Correction: the files are now available.'))
            self.assertNotIn('missing_inputs',restored['facts'])
            with self.assertRaises(ValueError):resource_decision.render(json.dumps(dict(answer='[fact:missing_inputs]',resource=None,steps=[])),restored)

    def test_comparison_cannot_skip_route_or_step_schema_constraints(self):
        with tempfile.TemporaryDirectory() as temp:
            projection=resource_decision.project(Path(temp),self.conversation('Compare Codex and Cursor subscriptions.'))
            for resource,steps in [('cursor',['prepare_report']),('grok',[]),('codex',None),('codex',False),('codex',0),('codex',''),('codex',{})]:
                with self.subTest(resource=resource,steps=steps),self.assertRaises(ValueError):
                    resource_decision.render(json.dumps(dict(answer='[fact:codex.reach]',resource=resource,steps=steps)),projection)

    def test_exclusive_cursor_and_empty_page_do_not_skip_next_event(self):
        for text in ('ACK through 149, since_seq 137, events 12, history_gap false, has_more true.',
                     'Acknowledgment through 149; since_seq 149; events 0; history_gap false; has_more false.',
                     'Acknowledgement through 149; since_seq 149; events 0; history_gap false; has_more false.',
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
    def test_drafted_page_request_fields_are_protocol_owned_even_with_bad_model_math(self):
        self.fake.reply_text='{"mode":"explain"}'
        self.send('Grok ACK through 72; since_seq 68; events 4; history_gap false; has_more true.')
        self.fake.reply_text=json.dumps(dict(artifact='{"since_seq":73,"limit":99}',commentary='I fetched it.'))
        answer=self.send('Draft the next read-only page request as JSON with since_seq and limit, at most seven events. Give the expected range.')
        self.assertEqual(self.chat.get(self.identifier)['messages'][-1]['_reply_contract']['kind'],'catchup')
        self.assertIn('{"since_seq":72,"limit":7}',answer['content'])
        self.assertIn('73–79',answer['content'])
        self.assertNotIn('I fetched',answer['content'])
        self.assertFalse(answer.get('artifact'))
        self.assertFalse(answer['catchup_observation']['execution_authority'])
        answer=self.send('Write a concise status I can relay: ACK through 79; since_seq 79; events 0; history_gap false; has_more false.')
        self.assertEqual(self.chat.get(self.identifier)['messages'][-1]['_reply_contract']['kind'],'catchup')
        self.assertIn('79',answer['content'])

    def test_owner_fact_namespace_is_current_attributed_and_revision_bound(self):
        self.send('For the Web Bob project, remember the priority: useful daily work.')
        self.send('Correction: reliable continuity comes first.')
        self.fake.reply_text=json.dumps(dict(answer=[dict(fact='owner.priority'),
            dict(reasoning='Prepare one representative question and its acceptance criteria.')],resource=None,steps=['provide_inputs']))
        answer=self.send('For Web Bob, how can our Codex subscription help?')
        self.assertIn('reliable continuity comes first',answer['content'])
        self.assertNotIn('useful daily work',answer['content'])
        self.assertIn('Owner statement',answer['content'])
        self.assertIn('saved project record revision 2',answer['content'])
        self.assertIn('not live-verified or execution authority',answer['content'])
        projection=self.chat.get(self.identifier)['messages'][-1]['_reply_contract']['resource_projection']
        self.assertEqual(projection['owner_context']['revision'],2)
        self.assertEqual(projection['owner_context']['facts']['owner.priority']['revision'],2)
        self.assertFalse(answer['resource_decision']['execution_started'])
        self.send('For the Web Bob project, remember the priority: useful completed work comes first.')
        with self.assertRaises(ValueError):
            resource_decision.render(self.fake.reply_text,projection,root=self.root)

    def test_direct_answer_preserved_and_bad_answer_never_selects_default_worker(self):
        self.fake.reply_text=json.dumps(dict(answer='No. ChatGPT Pro does not pay for API calls. [fact:openai_api_billing]',resource=None,steps=[]))
        answer=self.send('Does ChatGPT Pro pay for OpenAI API usage?')
        self.assertIn('does not pay',answer['content'])
        self.assertIsNone(answer['resource_decision']['resource'])
        self.fake.reply_text='malformed proposal'
        answer=self.send('Then what does our subscription cover?')
        self.assertIsNone(answer['resource_decision']['resource'])
        self.assertNotIn('qualify Codex',answer['content'])

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
