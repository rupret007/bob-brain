"""Real product admission, saved holds and report-source integrity; no models."""
import hashlib
import copy
import json
import time
from unittest.mock import patch

from app import Chat
from test_webchat import Fixture
import project_reports
import project_context
import report_artifacts
import task_queue


class ProjectReportTests(Fixture):
    def test_completion_support_is_bound_to_verified_saved_report_not_another_task(self):
        import result_provenance
        row,_=self.report();self.finish_report(row,'Useful saved finding with evidence.')
        question='For Web Bob, what finished and what should happen next?'
        conversation=dict(project_id='web-bob')
        project=project_context.projection(self.root,conversation,question)
        _,bindings=project_reports.answer_evidence(self.root,conversation,project,question,self.chat.redact)
        source=dict(topic=None,records=[],prior_assistant_evidence=False)
        text='The report completed. [report:saved-report-1]'
        # A citation in a separate sentence is not a grammatical subject; a
        # bound alias in the same proposition identifies the actual report.
        text='The saved report [report:saved-report-1] completed.'
        self.assertEqual(result_provenance.deliver(self.root,text,source,bindings)[0],text)
        trailing='The report completed [report:saved-report-1].'
        self.assertEqual(result_provenance.deliver(self.root,trailing,source,bindings)[0],trailing)
        for unsupported in ('The recommendations in [report:saved-report-1] were executed.',
                            'The report’s recommendations in [report:saved-report-1] were executed.',
                            'The recommendations for '+row['id']+' were executed.'):
            self.assertNotEqual(result_provenance.deliver(self.root,unsupported,source,bindings)[0],unsupported)
        source['records']=[dict(subject='H-88',kind='received_claim',predicates=['completion'])]
        other='Task H-88 completed.'
        self.assertNotEqual(result_provenance.deliver(self.root,other,source,bindings)[0],other)
        (self.root/row['report_contract']['output_relative']).write_text('Altered result')
        # Retain the referenced identity even when fresh verification fails.
        source['records'].append(dict(subject=row['id'],kind='received_claim',predicates=[]))
        changed=row['id']+' completed.'
        self.assertNotEqual(result_provenance.deliver(self.root,changed,source,bindings)[0],changed)
        self.assertNotEqual(result_provenance.deliver(self.root,text,source,bindings)[0],text)

    def finish_report(self,row,answer):
        claimed=task_queue.claim(self.root,'claude',identifier=row['id'])
        digest=hashlib.sha256(answer.encode()).hexdigest()
        path=row['report_contract']['output_relative']
        report_artifacts.put_once(self.root,path,(answer+'\n').encode())
        task_queue.transition(self.root,row['id'],claimed['claim_token'],'succeeded',result=answer,
            result_sha256=digest,result_path=str(self.root/path),
            acceptance=dict(accepted=True,result_sha256=digest,contract_sha256=row['report_contract']['contract_sha256']))

    def test_later_conversation_loads_verified_findings_separately_and_cites_protected_results(self):
        from providers import Providers
        from reply_authority import enforce
        row,_=self.report();self.finish_report(row,'Saved finding: receipt transport deserves the next investigation.')
        question='For Web Bob, what finished and what should happen next?'
        conversation=dict(id=self.identifier,messages=[dict(role='user',status='done',content=question)])
        provider=Providers(self.root,self.chat.redact);provider.prompt(conversation,fast=True)
        context=provider.current_call.api_input['context']
        self.assertIn('receipt transport deserves',context)
        self.assertIn('reliable daily assistance',context)
        self.assertEqual(len(provider.current_call.report_sources),1)
        content='The saved finding recommends investigating receipt transport. [report:saved-report-1]'
        guarded=enforce(self.root,question,dict(content=content,provider='gemini'),conversation)
        linked,sources=project_reports.render_citations(self.root,guarded,provider.current_call.report_sources)
        self.assertIn('/api/jobs/result?id='+row['id'],linked);self.assertEqual(sources[0]['task_id'],row['id'])
        for extra in (' I queued your task.',' webchat-'+'a'*32):
            rejected=enforce(self.root,question,dict(content=content+extra,provider='gemini'),conversation)
            self.assertNotIn('[report:',rejected)
        with patch.object(project_reports,'verified_report',side_effect=AssertionError('unrelated report read')):
            provider.prompt(dict(messages=[dict(role='user',status='done',content='Different topic: what is a good lunch?')]),fast=True)
        self.assertEqual(provider.current_call.report_sources,[])
        project=project_context.projection(self.root,dict(project_id='web-bob'),'What next?')
        with patch.object(project_reports,'verified_report',side_effect=AssertionError('personal question read')):
            for query in ('What is a good book to read next?', 'Could you write a birthday note about next year?',
                          'What is an earnings report?', 'What did today’s weather report say?'):
                self.assertEqual(project_reports.answer_evidence(self.root,dict(project_id='web-bob'),project,query,self.chat.redact),(None,[]))

    def test_recall_rejects_file_and_contract_tampering_and_bounds_utf8(self):
        row,_=self.report();self.finish_report(row,'Useful finding with evidence.\n'+'🪴'*5000)
        conversation=dict(project_id='web-bob');question='What did the report find?'
        project=project_context.projection(self.root,conversation,question)
        value,bindings=project_reports.answer_evidence(self.root,conversation,project,question,self.chat.redact)
        self.assertLessEqual(len(json.dumps(value,ensure_ascii=False).encode()),16000)
        self.assertTrue(value['reports'][0]['truncated']);self.assertTrue(bindings)
        current=task_queue.tasks(self.root);tampered=copy.deepcopy(current)
        tampered[row['id']]['report_contract']['scope']='Different scope without a new contract hash'
        with patch.object(task_queue,'tasks',return_value=tampered):
            value,bad=project_reports.answer_evidence(self.root,conversation,project,question,self.chat.redact)
        self.assertFalse(bad);self.assertNotIn('excerpt',value['reports'][0])
        (self.root/row['report_contract']['output_relative']).write_text('Tampered findings')
        value,bad=project_reports.answer_evidence(self.root,conversation,project,question,self.chat.redact)
        self.assertFalse(bad);self.assertNotIn('excerpt',value['reports'][0])
        content,sources=project_reports.render_citations(self.root,'See [report:saved-report-1]',bindings)
        self.assertFalse(sources);self.assertIn('changed',content)
        content,sources=project_reports.render_citations(self.root,'The report recommends a new investigation.',bindings)
        self.assertFalse(sources);self.assertIn('changed',content)

    def test_removal_withholds_historical_body_but_correction_keeps_it_historical(self):
        row,_=self.report();self.finish_report(row,'Saved finding with an earlier priority.')
        self.submit('For the Web Bob project, remember the priority: answer quality first.')
        conversation=self.chat.get(self.identifier);question='What did the report find?'
        project=project_context.projection(self.root,conversation,question)
        value,bindings=project_reports.answer_evidence(self.root,conversation,project,question,self.chat.redact)
        self.assertTrue(bindings);self.assertFalse(value['reports'][0]['context_matches'])
        retained=bindings
        fact=next(f for f in project['facts'] if f['kind']=='priority')
        self.submit('Forget project fact web-bob '+fact['id']+' at revision '+str(project['revision']))
        proposal=self.chat.get(self.identifier)['_project_removal']['proposal_id']
        self.submit('yes, forget project fact proposal '+proposal)
        project=project_context.projection(self.root,self.chat.get(self.identifier),question)
        value,bindings=project_reports.answer_evidence(self.root,self.chat.get(self.identifier),project,question,self.chat.redact)
        self.assertFalse(bindings);self.assertNotIn('excerpt',value['reports'][0]);self.assertIn('removed',value['reports'][0]['reason'])
        answer,bound=project_reports.render_citations(self.root,'The older report recommended work.',retained)
        self.assertFalse(bound);self.assertIn('changed',answer)

    def submit(self, text):
        from uuid import uuid4
        self.chat.submit(self.identifier, text, str(uuid4()))
        self.wait()
        return self.chat.history(self.identifier)

    def project(self):
        return self.submit('For the Web Bob project, remember the priority: reliable daily assistance. Keep texting working.')

    def report(self, text='Create a read-only Web Bob readiness report'):
        self.project()
        result = self.submit(text)
        row = next(iter(task_queue.tasks(self.root).values()))
        return row, result

    def test_product_contract_and_exact_inputs_exist_before_first_queue_event(self):
        row, result = self.report()
        self.assertEqual((row['kind'], row['requested_worker'], row['attempts'], row['max_attempts']),
                         ('bounded-report', 'claude', 0, 1))
        sources = report_artifacts.load_inputs(self.root, row['report_contract'])
        self.assertIn('reliable daily assistance', sources[0]['text'])
        self.assertIn(row['id'], result['messages'][-1]['content'])
        self.assertTrue(all(item['sha256'] == hashlib.sha256(source['text'].encode()).hexdigest()
                            for item, source in zip(row['report_contract']['input_manifest'], sources)))

    def test_held_assignment_restart_and_repeated_resume_keep_original_identity(self):
        self.project()
        self.submit('Hold all work')
        result = self.submit('Have Claude create a read-only Web Bob readiness report')
        saved = self.chat.conversations[self.identifier]
        contract = saved['held_job']['report_contract']
        self.assertFalse(task_queue.tasks(self.root))
        self.chat.close()
        self.chat = Chat(self.folder, self.root, self.fake)
        self.assertFalse(task_queue.tasks(self.root))
        self.submit('Resume')
        rows = task_queue.tasks(self.root)
        self.assertEqual(list(rows), [contract['task_id']])
        self.assertEqual(rows[contract['task_id']]['report_contract'], contract)
        self.submit('Resume')
        self.assertEqual(len(task_queue.tasks(self.root)), 1)

    def test_correction_while_held_does_not_rewrite_assignment_or_create_second_job(self):
        self.project()
        self.submit('Hold all work')
        self.submit('Create a read-only Web Bob readiness report')
        original = self.chat.conversations[self.identifier]['held_job']['report_contract']
        self.submit('For the Web Bob project, remember the priority: delivery reliability comes first.')
        self.submit('Resume')
        row = next(iter(task_queue.tasks(self.root).values()))
        self.assertEqual(row['report_contract'], original)
        current = project_context.read(self.root)['projects']['web-bob']
        self.assertGreater(current['revision'], row['report_contract']['goal_revision'])

    def test_questions_quoted_requests_and_deferred_work_do_not_enqueue(self):
        self.project()
        for text in ('How would a read-only Web Bob readiness report work?',
                     'Explain this sentence: "Create a read-only Web Bob readiness report"',
                     'Create a read-only Web Bob readiness report later',
                     'Create a read-only Web Bob readiness report if Claude is free'):
            with self.subTest(text=text):
                self.submit(text)
                self.assertFalse(task_queue.tasks(self.root))

    def test_polite_action_request_keeps_the_bounded_route(self):
        row, _ = self.report('Could you create a read-only Web Bob readiness report?')
        self.assertEqual(row['kind'], 'bounded-report')
        self.assertEqual(row['max_attempts'], 1)

    def test_unsupported_worker_does_not_fall_back_to_generic_executor(self):
        self.project()
        result = self.submit('Have Codex create a read-only Web Bob readiness report')
        self.assertFalse(task_queue.tasks(self.root))
        self.assertIn('no job was created', result['messages'][-1]['content'])

    def test_duplicate_product_request_does_not_recollect_changing_snapshot(self):
        self.project()
        from uuid import uuid4
        request = str(uuid4())
        result = self.chat.submit(self.identifier, 'Create a read-only Web Bob readiness report', request_id=request)
        row = next(iter(task_queue.tasks(self.root).values()))
        with patch.object(project_reports, 'collect', side_effect=AssertionError('must not recollect')):
            replay = self.chat.submit(self.identifier, 'Create a read-only Web Bob readiness report', request_id=request)
        self.assertEqual(len(task_queue.tasks(self.root)), 1)
        self.assertEqual(row['report_contract'], next(iter(task_queue.tasks(self.root).values()))['report_contract'])

    def test_brief_uses_verified_report_and_latest_correction_not_old_objective(self):
        row, _ = self.report()
        claimed = task_queue.claim(self.root, 'claude', identifier=row['id'])
        answer = 'Prior readiness findings and limitations.'
        digest = hashlib.sha256(answer.encode()).hexdigest()
        path = row['report_contract']['output_relative']
        report_artifacts.put_once(self.root, path, (answer + '\n').encode())
        task_queue.transition(self.root, row['id'], claimed['claim_token'], 'succeeded',
            result=answer, result_sha256=digest, result_path=str(self.root/path),
            acceptance=dict(accepted=True, result_sha256=digest, contract_sha256=row['report_contract']['contract_sha256']))
        self.submit('For the Web Bob project, remember the priority: delivery reliability comes first.')
        self.submit('Create a read-only next-actions brief for Web Bob from report ' + row['id'])
        rows = list(task_queue.tasks(self.root).values())
        self.assertEqual(len(rows), 2)
        sources = report_artifacts.load_inputs(self.root, rows[-1]['report_contract'])
        self.assertIn('delivery reliability comes first', sources[0]['text'])
        self.assertNotIn('reliable daily assistance', sources[0]['text'])
        self.assertIn(answer, sources[1]['text'])
        (self.root/path).write_text('Tampered report')
        self.submit('Create a read-only next-actions brief for Web Bob from report ' + row['id'])
        self.assertEqual(len(task_queue.tasks(self.root)), 2)

    def test_cancel_then_resume_cannot_recreate_the_report(self):
        row, _ = self.report()
        self.submit('Cancel task ' + row['id'])
        self.submit('Resume')
        rows = task_queue.tasks(self.root)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[row['id']]['status'], 'failed')

    def test_cancel_held_before_queue_then_restart_resume_does_not_admit(self):
        self.project(); self.submit('Hold all work')
        self.submit('Create a read-only Web Bob readiness report')
        self.submit('Cancel task')
        self.chat.close(); self.chat=Chat(self.folder,self.root,self.fake)
        self.submit('Resume')
        self.assertFalse(task_queue.tasks(self.root))

    def test_crash_after_inputs_publish_recovers_original_snapshot_not_recollected_one(self):
        self.project()
        original=report_artifacts.save_inputs
        captured={}
        def interrupted(root,contract,sources):
            original(root,contract,sources)
            captured.update(contract=contract,sources=sources)
            raise OSError('Fixture crash after input publication')
        with patch.object(report_artifacts,'save_inputs',side_effect=interrupted),self.assertRaises(OSError):
            self.submit('Create a read-only Web Bob readiness report')
        self.assertFalse(task_queue.tasks(self.root))
        self.chat.close()
        with patch.object(project_reports,'collect',side_effect=AssertionError('Do not recollect')):
            self.chat=Chat(self.folder,self.root,self.fake)
        row=next(iter(task_queue.tasks(self.root).values()))
        self.assertEqual(row['report_contract'],captured['contract'])
        self.assertEqual(report_artifacts.load_inputs(self.root,row['report_contract']),captured['sources'])
        self.assertNotIn('_report_inputs', self.chat.public(self.chat.conversations[self.identifier]))
