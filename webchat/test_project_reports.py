"""Real product admission, saved holds and report-source integrity; no models."""
import hashlib
import time
from unittest.mock import patch

from app import Chat
from test_webchat import Fixture
import project_reports
import project_context
import report_artifacts
import task_queue


class ProjectReportTests(Fixture):
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
