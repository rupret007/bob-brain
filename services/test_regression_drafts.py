"""Attempt9 regression drafts must be outer deliverables before publication."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import re
import unittest
from unittest.mock import Mock, patch

import api_worker
import dispatch_worker as dispatch
import result_acceptance as acceptance
import state
import worker as legacy
import test_dispatch as dispatch_fixture

REPO = Path(__file__).resolve().parents[1]
DATA = json.loads((REPO / 'services/fixtures/texting_regression_drafts_1658.json').read_text())
ERROR = 'Missing concrete regression test drafts (setup, action and expected assertion required)'


class RegressionDraftTests(unittest.TestCase):
    def test_historical_probe_control_cannot_claim_success_for_incomplete_inner_report(self):
        data = json.loads((REPO / 'services/fixtures/texting_regression_control_1658.json').read_text())
        self.assertEqual(hashlib.sha256(data['answer'].encode()).hexdigest(), data['answer_sha256'])
        setup = [line[7:] for line in data['answer'].splitlines() if line.startswith('Setup: ')][1]
        values = {statement.targets[0].id: ast.literal_eval(statement.value)
                  for statement in ast.parse(setup).body}
        with self.assertRaisesRegex(acceptance.ResultRejected, re.escape(data['expected_inner_error'])):
            acceptance.check_deliverables(**values)
        # The current concrete example instead calls a narrow guard. Its literal
        # failure and successful control have the actual stated outcomes.
        inputs = [{s.targets[0].id: ast.literal_eval(s.value)
                   for s in ast.parse(case['setup']).body} for case in DATA['complete_report']['regression_tests']]
        with self.assertRaisesRegex(acceptance.ResultRejected, 'Missing or ambiguous required completion JSON'):
            acceptance.check_completion_json(**inputs[0])
        acceptance.check_completion_json(**inputs[1])

    def test_known_false_literal_controls_cannot_win_a_positive_vote(self):
        data = json.loads((REPO / 'services/fixtures/texting_regression_control_1658.json').read_text())
        for fixture in (data, data['envelope_confusion']):
            self.assertEqual(hashlib.sha256(fixture['answer'].encode()).hexdigest(), fixture['answer_sha256'])
            vote = Mock(return_value='{"accepted": true, "reason": "Looks good"}')
            with self.assertRaisesRegex(acceptance.ResultRejected, 'contradicts literal guard outcome'):
                acceptance.accept(fixture['prompt'], fixture['answer'], vote, kind=fixture['kind'])
            vote.assert_not_called()

    def test_literal_guard_audit_never_runs_model_expressions(self):
        malicious = DATA['complete_answer'].replace("prompt='Return JSON with accepted/reason fields.'",
                    "prompt=__import__('os').system('touch /must-never-run')")
        with patch('os.system') as system, self.assertRaisesRegex(acceptance.ResultRejected, 'Unverifiable literal guard draft'):
            acceptance.check_literal_guard_drafts(malicious)
        system.assert_not_called()

    def test_captured_missing_json_separator_is_not_repaired_into_success(self):
        data = json.loads((REPO / 'services/fixtures/texting_regression_control_1658.json').read_text())['malformed_transport']
        self.assertEqual(hashlib.sha256(data['answer'].encode()).hexdigest(), data['answer_sha256'])
        with self.assertRaisesRegex(acceptance.ResultRejected, data['error']):
            api_worker.render_report(data['prompt'], data['answer'], data['kind'])

    def test_exact_capture_cannot_win_a_positive_vote(self):
        for key in ('prompt', 'answer'):
            self.assertEqual(hashlib.sha256(DATA[key].encode()).hexdigest(), DATA[key + '_sha256'])
        self.assertEqual(DATA['error'], ERROR)
        vote = Mock(return_value='{"accepted": true, "reason": "Looks complete"}')
        with self.assertRaisesRegex(acceptance.ResultRejected, re.escape(ERROR)):
            acceptance.accept(DATA['prompt'], DATA['answer'], vote, kind=DATA['kind'])
        vote.assert_not_called()

    def test_complete_transport_and_markdown_reach_independent_review(self):
        answer = api_worker.render_report(DATA['prompt'], json.dumps(DATA['complete_report']), DATA['kind'])
        self.assertEqual(answer, DATA['complete_answer'])
        for value in (answer, DATA['complete_answer']):
            vote = Mock(return_value='{"accepted": true, "reason": "Grounded two-case draft and conditional plan"}')
            self.assertTrue(acceptance.accept(DATA['prompt'], value, vote, kind=DATA['kind'])['accepted'])
            vote.assert_called_once()

    def test_every_outer_field_and_two_cases_are_required(self):
        for index in (0, 1):
            for field in ('name', 'target', 'setup', 'action', 'expected'):
                for value in ('', None, {}, []):
                    report = copy.deepcopy(DATA['complete_report'])
                    report['regression_tests'][index][field] = value
                    with self.subTest(index=index, field=field, value=value), self.assertRaisesRegex(
                            acceptance.ResultRejected, re.escape(ERROR)):
                        api_worker.render_report(DATA['prompt'], json.dumps(report), DATA['kind'])
        for cases in ([], DATA['complete_report']['regression_tests'][:1], DATA['complete_report']['regression_tests'] * 2):
            report = dict(DATA['complete_report'], regression_tests=cases)
            with self.assertRaisesRegex(acceptance.ResultRejected, re.escape(ERROR)):
                api_worker.render_report(DATA['prompt'], json.dumps(report), DATA['kind'])
        for field in ('Target', 'Setup', 'Action', 'Expected'):
            # One valid case cannot cover for its malformed partner.
            for index in (0, 1):
                parts = DATA['complete_answer'].split('Regression test: ')
                parts[index + 1] = re.sub(r'(?m)^' + field + r': .*$', field + ':\nOnly a following-line value', parts[index + 1])
                with self.assertRaisesRegex(acceptance.ResultRejected, re.escape(ERROR)):
                    acceptance.check_answer(DATA['prompt'], 'Regression test: '.join(parts), kind=DATA['kind'])

    def test_nested_and_historical_labels_never_supply_outer_drafts(self):
        plan = DATA['complete_answer'].split('Unblock plan:')[1]
        history = DATA['complete_answer'].split('Unblock plan:')[0]
        for nested in ('```text\n' + history + '```\n',
                       '\n'.join('> ' + line for line in history.splitlines()) + '\n',
                       '\n'.join('    ' + line for line in history.splitlines()) + '\n',
                       'Setup: answer=' + json.dumps(history) + '\n'):
            with self.assertRaisesRegex(acceptance.ResultRejected, re.escape(ERROR)):
                acceptance.check_answer(DATA['prompt'], nested + 'Unblock plan:' + plan, kind=DATA['kind'])
        report = copy.deepcopy(DATA['complete_report'])
        report['regression_tests'][0]['setup'] += '\n' + history
        report['regression_tests'][0]['action'] = ''
        with self.assertRaisesRegex(acceptance.ResultRejected, re.escape(ERROR)):
            api_worker.render_report(DATA['prompt'], json.dumps(report), DATA['kind'])

    def test_plain_test_writing_uses_transport_without_inventing_a_plan(self):
        report = dict(DATA['complete_report'], plan=None)
        prompt = 'Draft regression tests for source selection.'
        answer = api_worker.render_report(prompt, json.dumps(report), 'test-writing')
        acceptance.check_answer(prompt, answer, kind='test-writing')
        self.assertNotIn('Unblock plan:', answer)

    def test_worker_gets_one_consistent_output_contract(self):
        prompt = api_worker.report_prompt(DATA['prompt'], 'FILE example.py\npass', DATA['kind'])
        self.assertIn('REPORT SERIALIZATION:', prompt)
        self.assertIn('"regression_tests":', prompt)
        self.assertNotIn('Required behavioral-draft layout', prompt)
        self.assertNotIn('exactly one fenced json block', prompt)


class WorkerRegressionDraftTests(unittest.TestCase):
    setUp = dispatch_fixture.DispatchTests.setUp
    tearDown = dispatch_fixture.DispatchTests.tearDown

    def test_all_dispatch_workers_reject_missing_drafts_and_save_complete_reports(self):
        self.acceptance.stop()
        for engine in ('gemini', 'minimax', 'claude', 'codex', 'cursor'):
            for valid in (False, True):
                kind = DATA['kind'] if engine in dispatch.task_queue.API_WORKERS else 'analysis'
                job = dispatch.task_queue.enqueue(self.root, '1658', engine + str(valid), DATA['prompt'], worker=engine, kind=kind)
                claim = dispatch.task_queue.claim(self.root, engine, identifier=job['id'])
                raw = json.dumps(DATA['complete_report']) if valid else DATA['answer']
                with patch.object(dispatch, 'prepare_task', return_value=self.root), \
                     patch.object(api_worker, 'evidence', return_value=('Captured evidence', {})), \
                     patch.object(dispatch, 'ask', side_effect=[raw, '{"accepted": true, "reason": "Grounded report"}']) as ask:
                    self.assertEqual(dispatch.execute(job['id'], claim['claim_token']), 0 if valid else 1)
                self.assertIn('REPORT SERIALIZATION:', ask.call_args_list[0].args[1])
                self.assertEqual(ask.call_count, 2 if valid else 1)
                row = dispatch.task_queue.tasks(self.root)[job['id']]
                saved = self.core / 'state/task-runs' / job['id'] / 'RESULT.md'
                if valid:
                    self.assertTrue(row['acceptance']['accepted'])
                    self.assertEqual(row['result'], DATA['complete_answer'])
                    self.assertEqual(row['result_sha256'], hashlib.sha256(row['result'].encode()).hexdigest())
                    self.assertEqual(saved.read_text().strip(), row['result'])
                    if engine in dispatch.task_queue.API_WORKERS:
                        self.assertEqual(Path(row['result_path']).read_text().strip(), row['result'])
                else:
                    self.assertEqual(row['error'], ERROR)
                    self.assertFalse(saved.exists())
                    self.assertNotIn('result_path', row)

    def test_legacy_workers_cannot_verify_or_save_nested_only_drafts(self):
        for engine in ('gemini', 'minimax', 'claude', 'codex', 'cursor'):
            folder = self.root / engine
            folder.mkdir()
            (folder / 'PROMPT.txt').write_text(DATA['prompt'])
            state.job_event(engine, 'launched', job_dir=str(folder), repo=str(self.root), worktree=str(folder),
                            branch='draft/test', engine=engine, kind='non-coding')
            with patch.object(legacy, 'CONDUCTOR', self.core), \
                 patch.object(legacy, 'setup_record', return_value=folder), \
                 patch.object(api_worker, 'evidence', return_value=('Captured evidence', {})), \
                 patch.object(legacy, 'ask', return_value=DATA['answer']) as ask, \
                 patch.object(api_worker, 'save_report') as save:
                self.assertEqual(legacy.execute(engine), 1)
            self.assertEqual(ask.call_count, 1)
            save.assert_not_called()
            self.assertFalse(state.jobs()[engine].get('verified'))
            self.assertFalse((folder / 'RESULT.txt').exists())
