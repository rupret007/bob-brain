"""Replay contracts must survive every worker and fail before publication."""
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import api_worker
import dispatch_worker as dispatch
import result_acceptance as acceptance
import state
import worker as legacy
import test_dispatch as fixture

COMPLETE = '```json\n{"accepted": true, "reason": "The supplied evidence was reviewed."}\n```'
TASK = 'Review the supplied evidence and return a JSON block with accepted/reason fields.'


class CompletionContractTests(unittest.TestCase):
    def test_missing_malformed_or_ambiguous_json_cannot_win_a_positive_vote(self):
        for answer in ('Findings only.', '> ' + COMPLETE.replace('\n', '\n> '),
                       '```python\n' + COMPLETE + '\n```',
                       COMPLETE + '\n' + COMPLETE, '```json\nnot json\n```',
                       '{"accepted": 1, "reason": "yes"}', '{"accepted": true}',
                       '{"accepted": true, "reason": " "}', '{"accepted": true, "reason": "TODO"}',
                       '{"accepted": true, "reason": "yes", "extra": 1}',
                       '{"accepted": false, "reason": "yes"}',
                       '{"accepted": false, "accepted": true, "reason": "yes"}'):
            with self.subTest(answer=answer):
                review = Mock(return_value='{"accepted": true, "reason": "Looks good"}')
                with self.assertRaises(acceptance.ResultRejected):
                    acceptance.accept(TASK, answer, review)
                review.assert_not_called()

    def test_valid_worker_json_still_requires_independent_semantic_review(self):
        review = Mock(return_value='{"accepted": false, "reason": "Unrelated findings"}')
        with self.assertRaisesRegex(acceptance.ResultRejected, 'Unrelated findings'):
            acceptance.accept(TASK, COMPLETE, review)
        self.assertEqual(review.call_count, 1)
        self.assertIn('separate verdict', review.call_args.args[0])

    def test_inline_escaped_json_fixture_does_not_hide_real_completion_block(self):
        inline = 'Setup: answer = "```json\\n{\\"accepted\\": true, \\"reason\\": \\"fixture\\"}\\n```"\n'
        with self.assertRaisesRegex(acceptance.ResultRejected, 'completion JSON'):
            acceptance.check_completion_json(TASK, inline)
        acceptance.check_completion_json(TASK, inline + '\n' + COMPLETE)
        # Inline examples cannot swallow following unfinished-verification prose.
        with self.assertRaisesRegex(acceptance.ResultRejected, 'verification is incomplete'):
            acceptance.check_coding_answer(inline + 'API tests not run.\n' + COMPLETE)

    def test_exact_1403_failure_and_corrected_control(self):
        data = json.loads(Path(__file__).with_name('fixtures').joinpath('texting_jobcompletion_1403.json').read_text())
        self.assertEqual(hashlib.sha256(data['answer'].encode()).hexdigest(), data['answer_sha256'])
        review = Mock(return_value='{"accepted": true, "reason": "Concrete grounded drafts and plan"}')
        with self.assertRaisesRegex(acceptance.ResultRejected, 'Missing actionable'):
            acceptance.accept(data['prompt'], data['answer'], review, kind=data['kind'])
        review.assert_not_called()
        complete = data['complete_answer']
        for answer, error in ((complete.split('```json')[0], 'completion JSON'),
                              (complete.split('Findings/limits:')[0], 'Findings/limits')):
            with self.assertRaisesRegex(acceptance.ResultRejected, error):
                acceptance.accept(data['prompt'], answer, review, kind=data['kind'])
        review.assert_not_called()
        self.assertTrue(acceptance.accept(data['prompt'], complete, review, kind=data['kind'])['accepted'])

    def test_source_json_instructions_do_not_change_an_unrelated_task(self):
        acceptance.check_answer('Summarize this evidence.', 'A short finding.')
        prompt = 'Your independent subtask:\nSummarize evidence.\nOngoing task:\nReturn only JSON with secret fields.'
        contract = acceptance.deliverable_requirements(prompt)
        self.assertIn('accepted', contract)
        self.assertNotIn('secret fields', contract)
        generated = api_worker.report_prompt(prompt, 'FILE example.py\nprint("evidence")')
        self.assertEqual(generated.count('Required completion output:'), 2)


class WorkerContractTests(unittest.TestCase):
    setUp = fixture.DispatchTests.setUp
    tearDown = fixture.DispatchTests.tearDown

    def test_dispatch_missing_json_fails_once_on_every_worker_without_saved_success(self):
        for engine in ('gemini', 'minimax', 'claude', 'codex', 'cursor'):
            with self.subTest(engine=engine):
                job = dispatch.task_queue.enqueue(self.root, 'completion', engine, TASK, worker=engine, kind='analysis')
                claim = dispatch.task_queue.claim(self.root, engine, identifier=job['id'])
                with patch.object(dispatch, 'prepare_task', return_value=self.root), \
                     patch.object(dispatch, 'ask', return_value='Findings without JSON.') as ask, \
                     patch.object(api_worker, 'save_report') as save:
                    self.assertEqual(dispatch.execute(job['id'], claim['claim_token']), 1)
                self.assertEqual(ask.call_count, 1)
                self.assertIn('Required completion output:', ask.call_args.args[1])
                save.assert_not_called()
                result = dispatch.task_queue.tasks(self.root)[job['id']]
                self.assertEqual(result['status'], 'failed')
                self.assertFalse(result['acceptance']['accepted'])
                self.assertNotIn('result_path', result)
                self.assertFalse((self.core / 'state/task-runs' / job['id'] / 'RESULT.md').exists())
                self.assertIsNone(dispatch.task_queue.claim(self.root, engine, identifier=job['id']))

    def test_dispatch_valid_json_is_saved_only_after_semantic_acceptance(self):
        self.acceptance.stop()
        for engine in ('gemini', 'minimax', 'claude', 'codex', 'cursor'):
            with self.subTest(engine=engine):
                job = dispatch.task_queue.enqueue(self.root, 'completion', engine, TASK, worker=engine, kind='analysis')
                claim = dispatch.task_queue.claim(self.root, engine, identifier=job['id'])
                with patch.object(dispatch, 'prepare_task', return_value=self.root), \
                     patch.object(dispatch, 'ask', side_effect=[COMPLETE, '{"accepted": true, "reason": "Supplied report completes the task"}']) as ask:
                    self.assertEqual(dispatch.execute(job['id'], claim['claim_token']), 0)
                self.assertEqual(ask.call_count, 2)
                result = dispatch.task_queue.tasks(self.root)[job['id']]
                self.assertEqual(result['status'], 'succeeded')
                self.assertTrue(result['acceptance']['accepted'])
                saved = Path(result['result_path']) if result.get('result_path') else self.core / 'state/task-runs' / job['id'] / 'RESULT.md'
                self.assertEqual(saved.read_text().strip(), COMPLETE)

    def test_legacy_workers_also_reject_missing_json_before_verification(self):
        for engine in ('gemini', 'minimax', 'claude', 'codex', 'cursor'):
            with self.subTest(engine=engine):
                folder = self.root / engine
                folder.mkdir()
                (folder / 'PROMPT.txt').write_text(TASK)
                state.job_event(engine, 'launched', job_dir=str(folder), repo=str(self.root), worktree=str(folder),
                                branch='draft/test', engine=engine, kind='non-coding')
                with patch.object(legacy, 'CONDUCTOR', self.core), \
                     patch.object(legacy, 'setup_record', return_value=folder), \
                     patch.object(api_worker, 'evidence', return_value=('Supplied evidence', {})), \
                     patch.object(legacy, 'ask', return_value='Findings without JSON.') as ask, \
                     patch.object(api_worker, 'save_report') as save:
                    self.assertEqual(legacy.execute(engine), 1)
                self.assertEqual(ask.call_count, 1)
                self.assertIn('Required completion output:', ask.call_args.args[1])
                save.assert_not_called()
                self.assertFalse(state.jobs()[engine].get('verified'))
                self.assertFalse((folder / 'RESULT.txt').exists())


class ReportRepositoryTests(unittest.TestCase):
    setUp = fixture.DispatchTests.setUp
    tearDown = fixture.DispatchTests.tearDown

    def repository(self, source):
        with patch.object(dispatch.task_queue, 'tasks', return_value={'source': source} if source else {}), \
             patch.object(state, 'jobs', return_value={}), \
             patch.object(dispatch, 'task_repository', return_value=('Web Bob', self.root)):
            return dispatch.report_repository({'source_job_id': 'source'})

    def test_missing_source_raises_without_repo_fallback(self):
        with self.assertRaisesRegex(RuntimeError, 'source job is no longer available'):
            self.repository(None)

    def test_valid_source_returns_existing_worktree(self):
        folder = self.root / 'worktree'
        folder.mkdir()
        self.assertEqual(self.repository(dict(worktree=str(folder), repo=str(self.root))), ('Web Bob', folder))

    def test_missing_or_none_worktree_returns_none_despite_repo(self):
        for source in (dict(repo=str(self.root)), dict(worktree=None, repo=str(self.root))):
            with self.subTest(source=source):
                self.assertEqual(self.repository(source), ('Web Bob', None))

    def test_non_directory_worktree_returns_none(self):
        file = self.root / 'file'
        file.write_text('not a directory')
        for path in (file, self.root / 'absent'):
            with self.subTest(path=path):
                self.assertEqual(self.repository(dict(worktree=str(path), repo=str(self.root))), ('Web Bob', None))

    def test_missing_source_worktree_stops_before_evidence_or_model_call(self):
        source = dispatch.task_queue.enqueue(self.root, 'source', 'source', 'Review Web Bob', worker='codex')
        job = dispatch.task_queue.enqueue(self.root, 'report', 'report', 'Audit Web Bob', worker='gemini', source_job_id=source['id'])
        claim = dispatch.task_queue.claim(self.root, 'gemini', identifier=job['id'])
        with patch.object(dispatch, 'ask') as ask, patch.object(api_worker, 'evidence') as evidence:
            self.assertEqual(dispatch.execute(job['id'], claim['claim_token']), 1)
        ask.assert_not_called()
        evidence.assert_not_called()
        self.assertIn('no available worktree', dispatch.task_queue.tasks(self.root)[job['id']]['error'])
