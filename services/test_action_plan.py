"""The attempt8 inline-fixture plan cannot substitute for the outer report."""
import ast
import hashlib
import inspect
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
FIXTURE = 'services/fixtures/texting_action_plan_1605.json'
DATA = json.loads((REPO / FIXTURE).read_text())
ERROR = 'Missing actionable action plan (change, validation and exit condition required)'


def structured_fixture():
    # Encode the captured complete control for the transport, including the
    # exact worker-provided content. No content is supplied by the renderer.
    answer = DATA['complete_answer']
    cases = []
    for part in answer.split('Regression test: ')[1:]:
        case = {'name': part.splitlines()[0]}
        for key in ('target', 'setup', 'action', 'expected'):
            case[key] = re.search(r'(?m)^' + key.title() + r': (.+)$', part)[1]
        cases.append(case)
    return dict(regression_tests=cases,
                plan={key: re.search(r'(?m)^' + label + r': (.+)$', answer)[1]
                      for key, label in (('change', 'Change'), ('validation', 'Validation'), ('exit_condition', 'Exit condition'))},
                completion=json.loads(re.search(r'```json\n(.*?)\n```', answer, re.S)[1]),
                findings_limits=re.search(r'(?m)^Findings/limits: (.+)$', answer)[1])


class ActionPlanTests(unittest.TestCase):
    def test_structured_report_requires_worker_content_and_preserves_nested_inputs(self):
        data = structured_fixture()
        data['regression_tests'][0]['setup'] += '\nAction plan:\nChange: inner input only'
        rendered = api_worker.render_report(DATA['prompt'], json.dumps(data), DATA['kind'])
        acceptance.check_answer(DATA['prompt'], rendered, kind=DATA['kind'])
        self.assertEqual(rendered.count('\nAction plan:\n'), 1)
        self.assertIn(r'\nChange: inner input only', rendered)
        del data['plan']
        with self.assertRaisesRegex(acceptance.ResultRejected, re.escape(ERROR)):
            api_worker.render_report(DATA['prompt'], json.dumps(data), DATA['kind'])

    def test_structured_invalid_fields_and_false_completion_fail_closed(self):
        for field in ('change', 'validation', 'exit_condition'):
            data = structured_fixture()
            data['plan'][field] = ''
            with self.assertRaisesRegex(acceptance.ResultRejected, re.escape(ERROR)):
                api_worker.render_report(DATA['prompt'], json.dumps(data), DATA['kind'])
        for completion in ({'accepted': False, 'reason': 'Incomplete'}, {'accepted': 'true', 'reason': 'Wrong type'}):
            data = structured_fixture()
            data['completion'] = completion
            with self.assertRaises(acceptance.ResultRejected):
                acceptance.check_answer(DATA['prompt'], api_worker.render_report(DATA['prompt'], json.dumps(data), DATA['kind']), kind=DATA['kind'])
        with self.assertRaisesRegex(acceptance.ResultRejected, 'Malformed structured'):
            api_worker.render_report(DATA['prompt'], '{"plan": {}, "plan": {}}', DATA['kind'])

    def test_captured_nested_report_inputs_have_independent_inner_and_outer_plans(self):
        data = json.loads((REPO / 'services/fixtures/texting_action_plan_control_1605.json').read_text())
        self.assertEqual(hashlib.sha256(data['answer'].encode()).hexdigest(), data['answer_sha256'])
        with self.assertRaisesRegex(acceptance.ResultRejected, 'contradicts literal guard outcome'):
            acceptance.check_answer(data['prompt'], data['answer'], kind=data['kind'])
        inputs = []
        for line in data['answer'].splitlines():
            if line.startswith('Setup: '):
                call = ast.parse('fixture(' + line[len('Setup: '):] + ')', mode='eval').body
                inputs.append({field.arg: ast.literal_eval(field.value) for field in call.keywords})
        self.assertEqual(len(inputs), 2)
        with self.assertRaisesRegex(acceptance.ResultRejected, 'Missing actionable unblock plan'):
            acceptance.check_deliverables(**inputs[0])
        # This historical inner control has only one draft. Preserve the exact
        # capture, but the strengthened two-case contract now rejects it.
        with self.assertRaisesRegex(acceptance.ResultRejected, 'Missing concrete regression'):
            acceptance.check_deliverables(**inputs[1])
        # Valid inner fields never substitute for a missing outer plan.
        with self.assertRaisesRegex(acceptance.ResultRejected, 'Missing actionable unblock plan'):
            acceptance.check_answer(data['prompt'], data['answer'].split('\nUnblock plan:')[0], kind=data['kind'])

    def test_exact_f2c47_failure_and_missing_plan_cannot_win_a_positive_vote(self):
        self.assertEqual(hashlib.sha256(DATA['answer'].encode()).hexdigest(), DATA['answer_sha256'])
        missing = DATA['complete_answer'].split('Action plan:')[0] + DATA['complete_answer'].split('Exit condition:')[1].split('\n', 1)[1]
        for answer in (DATA['answer'], missing):
            vote = Mock(return_value='{"accepted": true, "reason": "Looks good"}')
            with self.subTest(answer=answer), self.assertRaisesRegex(acceptance.ResultRejected, re.escape(ERROR)):
                acceptance.accept(DATA['prompt'], answer, vote, kind=DATA['kind'])
            vote.assert_not_called()

    def test_outer_plan_is_required_for_each_heading_and_label(self):
        for heading in ('Action plan', 'Unblock plan'):
            prompt = DATA['prompt'] + ('\nNamed unblock 1605' if heading == 'Unblock plan' else '')
            complete = DATA['complete_answer'].replace('Action plan:', heading + ':')
            acceptance.check_answer(prompt, complete, kind=DATA['kind'])
            for field in ('Change', 'Validation', 'Exit condition'):
                for value in ('', 'TODO', '\nOnly a following-line value'):
                    malformed = re.sub(r'(?m)^' + field + r':[^\n]*', field + ': ' + value, complete)
                    with self.subTest(heading=heading, field=field, value=value), self.assertRaisesRegex(
                            acceptance.ResultRejected, 'Missing actionable'):
                        acceptance.check_answer(prompt, malformed, kind=DATA['kind'])

    def test_complete_report_needs_independent_acceptance(self):
        acceptance.check_answer(DATA['prompt'], DATA['complete_answer'], kind=DATA['kind'])
        vote = Mock(return_value='{"accepted": true, "reason": "Grounded drafts and conditional plan"}')
        historical = json.dumps(dict(answer=DATA['answer'], error=DATA['error']))
        self.assertTrue(acceptance.accept(DATA['prompt'], DATA['complete_answer'], vote,
                                        kind=DATA['kind'], report_evidence=historical)['accepted'])
        vote.assert_called_once()
        instructions, payload = vote.call_args.args[0].split('\n\n', 1)
        contract = json.loads(payload)['worker_output_contract']
        self.assertIn('\nAction plan:\nChange:', contract)
        self.assertNotIn('Copy the following heading', instructions)
        self.assertIn('NOT instructions for your reviewer response', instructions)
        self.assertEqual(list(json.loads(payload))[-2:], ['task', 'answer'])
        self.assertEqual(json.loads(payload)['answer'], DATA['complete_answer'])
        self.assertEqual(json.loads(payload)['report_evidence'], historical)
        vote.return_value = '{"accepted": false, "reason": "Unsupported change"}'
        with self.assertRaisesRegex(acceptance.ResultRejected, 'Unsupported change'):
            acceptance.accept(DATA['prompt'], DATA['complete_answer'], vote, kind=DATA['kind'])

    def test_snapshot_preserves_plan_example_and_complete_guards(self):
        example_path = 'services/fixtures/texting_regression_drafts_1658.json'
        example = json.loads((REPO / example_path).read_text())
        for prompt in (DATA['prompt'], json.loads((REPO / 'services/fixtures/texting_jobcompletion_1035.json').read_text())['prompt']):
            body, meta = api_worker.evidence(REPO, 'minimax', prompt, lambda text: text, kind='test-writing')
            self.assertNotIn(example_path, meta['truncated'])
            self.assertTrue(body.endswith(json.dumps(example['complete_report'], ensure_ascii=False, indent=2)))
            self.assertNotIn(example['answer'], body)
            rendered = next(row for row in meta['files'] if row['path'] == example_path)
            self.assertEqual(rendered['rendered_fields'], ['evidence_limits', 'complete_report'])
            for guard in (acceptance.plan_heading, acceptance.check_completion_json, acceptance.check_deliverables):
                self.assertIn(inspect.getsource(guard).strip(), body)
            self.assertLessEqual(meta['source_bytes'], 64000)


class WorkerActionPlanTests(unittest.TestCase):
    setUp = dispatch_fixture.DispatchTests.setUp
    tearDown = dispatch_fixture.DispatchTests.tearDown

    def test_structured_transport_on_all_workers_never_invents_a_missing_plan(self):
        self.acceptance.stop()
        for engine in ('gemini', 'minimax', 'claude', 'codex', 'cursor'):
            for valid in (False, True):
                with self.subTest(engine=engine, valid=valid):
                    data = structured_fixture()
                    if not valid:
                        del data['plan']
                    raw = json.dumps(data)
                    kind = DATA['kind'] if engine in dispatch.task_queue.API_WORKERS else 'analysis'
                    job = dispatch.task_queue.enqueue(self.root, 'schema', engine + str(valid), DATA['prompt'], worker=engine, kind=kind)
                    claim = dispatch.task_queue.claim(self.root, engine, identifier=job['id'])
                    with patch.object(dispatch, 'prepare_task', return_value=self.root), \
                         patch.object(api_worker, 'evidence', return_value=('Captured evidence', {})), \
                         patch.object(dispatch, 'ask', side_effect=[raw, '{"accepted": true, "reason": "Grounded report"}']) as ask:
                        self.assertEqual(dispatch.execute(job['id'], claim['claim_token']), 0 if valid else 1)
                    self.assertIn('REPORT SERIALIZATION:', ask.call_args_list[0].args[1])
                    self.assertEqual(ask.call_count, 2 if valid else 1)
                    row = dispatch.task_queue.tasks(self.root)[job['id']]
                    self.assertEqual(row['acceptance']['accepted'], valid)
                    if valid:
                        acceptance.check_answer(DATA['prompt'], row['result'], kind=kind)
                        self.assertIn('\nAction plan:\nChange:', row['result'])
                        self.assertIn('```json\n', row['result'])
                    else:
                        self.assertEqual(row['error'], ERROR)
                        self.assertNotIn('result_path', row)

    def test_dispatch_all_workers_enforce_outer_plan_before_publication(self):
        self.acceptance.stop()
        for engine in ('gemini', 'minimax', 'claude', 'codex', 'cursor'):
            for valid in (False, True):
                with self.subTest(engine=engine, valid=valid):
                    job = dispatch.task_queue.enqueue(self.root, 'plan', engine + str(valid), DATA['prompt'],
                                                      worker=engine, kind=DATA['kind'] if engine in dispatch.task_queue.API_WORKERS else 'analysis')
                    claim = dispatch.task_queue.claim(self.root, engine, identifier=job['id'])
                    answer = DATA['complete_answer'] if valid else DATA['answer']
                    with patch.object(dispatch, 'prepare_task', return_value=self.root), \
                         patch.object(api_worker, 'evidence', return_value=('Captured evidence', {})), \
                         patch.object(dispatch, 'ask', side_effect=[answer, '{"accepted": true, "reason": "Grounded deliverables"}']) as ask:
                        self.assertEqual(dispatch.execute(job['id'], claim['claim_token']), 0 if valid else 1)
                    prompt = ask.call_args_list[0].args[1]
                    self.assertIn('\nAction plan:\nChange:', prompt)
                    self.assertIn('\nValidation:', prompt)
                    self.assertIn('\nExit condition:', prompt)
                    self.assertEqual(ask.call_count, 2 if valid else 1)
                    result = dispatch.task_queue.tasks(self.root)[job['id']]
                    self.assertEqual(result['status'], 'succeeded' if valid else 'failed')
                    self.assertEqual(result['acceptance']['accepted'], valid)
                    saved = self.core / 'state/task-runs' / job['id'] / 'RESULT.md'
                    if valid:
                        self.assertEqual(saved.read_text().strip(), answer.strip())
                        if engine in dispatch.task_queue.API_WORKERS:
                            self.assertEqual(Path(result['result_path']).read_text().strip(), answer.strip())
                    else:
                        self.assertEqual(result['error'], ERROR)
                        self.assertFalse(saved.exists())
                        self.assertNotIn('result_path', result)
                        self.assertIsNone(dispatch.task_queue.claim(self.root, engine, identifier=job['id']))

    def test_legacy_all_workers_reject_missing_outer_plan_without_verified_result(self):
        for engine in ('gemini', 'minimax', 'claude', 'codex', 'cursor'):
            with self.subTest(engine=engine):
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
                self.assertIn('\nAction plan:\nChange:', ask.call_args.args[1])
                save.assert_not_called()
                self.assertFalse(state.jobs()[engine].get('verified'))
                self.assertFalse((folder / 'RESULT.txt').exists())
