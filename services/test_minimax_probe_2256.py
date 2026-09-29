"""The exact 2055 MiniMax rejection stays rejected; outer drafts publish safely."""
import hashlib
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import Mock, patch

import api_worker
import dispatch_worker as dispatch
import result_acceptance as acceptance
import test_dispatch as dispatch_fixture
import workspaces

REPO = Path(__file__).resolve().parents[1]
FIXTURE = 'services/fixtures/texting_minimax_probe_2256.json'
DATA = json.loads((REPO / FIXTURE).read_text())
ERROR = 'Missing concrete regression test drafts (setup, action and expected assertion required)'


def complete_report():
    """Concrete current-source controls, distinct from the captured bad answer."""
    return dict(regression_tests=[
        dict(name='runtime review receipt is excluded from the source snapshot',
             target='services/api_worker.py::safe_source',
             action="Call safe_source(repo, 'reviews/TEXTING-RUNTIME.json').",
             expected='Assert the result is False.',
             setup='Create temporary directory repo containing regular file reviews/TEXTING-RUNTIME.json; no symlinks.'),
        dict(name='ordinary Python source is eligible for the snapshot',
             target='services/api_worker.py::safe_source',
             action="Call safe_source(repo, 'services/example.py').",
             expected='Assert the result is True.',
             setup='Create temporary directory repo containing regular file services/example.py; no symlinks.')],
        plan=dict(change='Validate existing source-isolation coverage for the observed Web Bob unblock 1035 lane; its original assignment is unavailable.',
                  validation="Run python3 -m unittest discover -s services -p 'test_*.py' and require zero failures; proposed, not executed.",
                  exit_condition='Keep Web Bob unblock 1035 on hold until its actual worker results and live gates pass; the report alone does not close it.'),
        completion=dict(accepted=True, reason='Delivered two current-source regression drafts and a conditional plan; drafts are unexecuted.'),
        findings_limits='safe_source excludes runtime review evidence while permitting ordinary Python source. Drafts are unexecuted; the original unblock 1035 assignment was not recorded.')


class MiniMaxProbeTests(unittest.TestCase):
    def test_exact_capture_with_buried_action_expected_fails_before_review(self):
        for key in ('prompt', 'answer'):
            self.assertEqual(hashlib.sha256(DATA[key].encode()).hexdigest(), DATA[key + '_sha256'])
        self.assertEqual(DATA['error'], ERROR)
        cases = json.loads(DATA['answer'])['regression_tests']
        self.assertEqual(set(cases[1]), {'name', 'target', 'setup'})
        self.assertIn('Action:', cases[1]['setup'])
        self.assertIn('Expected:', cases[1]['setup'])
        reviewer = Mock(return_value='{"accepted": true, "reason": "Looks complete"}')
        for operation in (
                lambda: api_worker.render_report(DATA['prompt'], DATA['answer'], DATA['kind']),
                lambda: acceptance.accept(DATA['prompt'], DATA['answer'], reviewer, kind=DATA['kind'])):
            with self.assertRaisesRegex(acceptance.ResultRejected, re.escape(ERROR)):
                operation()
        reviewer.assert_not_called()

    def test_complete_transport_has_two_outer_cases_and_accepted_saved_content(self):
        rendered = api_worker.render_report(DATA['prompt'], json.dumps(complete_report()), DATA['kind'])
        for label in ('Regression test', 'Target', 'Setup', 'Action', 'Expected'):
            self.assertEqual(len(re.findall(r'(?m)^' + label + r': \S.+$', rendered)), 2)
        reviewer = Mock(return_value='{"accepted": true, "reason": "Grounded current-source controls"}')
        self.assertTrue(acceptance.accept(DATA['prompt'], rendered, reviewer, kind=DATA['kind'])['accepted'])
        reviewer.assert_called_once()

    def test_each_case_requires_its_own_nonempty_sibling_fields(self):
        for index in (0, 1):
            for key in ('name', 'target', 'setup', 'action', 'expected'):
                for value in ('', ' \n ', None, False, 7, [], {}, 'TODO'):
                    report = complete_report()
                    report['regression_tests'][index][key] = value
                    with self.subTest(index=index, key=key, value=value), self.assertRaisesRegex(
                            acceptance.ResultRejected, re.escape(ERROR)):
                        api_worker.render_report(DATA['prompt'], json.dumps(report), DATA['kind'])

    def test_nested_and_historical_labels_cannot_supply_missing_outer_fields(self):
        rendered = api_worker.render_report(DATA['prompt'], json.dumps(complete_report()), DATA['kind'])
        history, closing = rendered.split('Unblock plan:', 1)
        for nested in ('```text\n' + history + '```\n', '~~~text\n' + history + '~~~\n',
                       '````text\n' + history + '````\n', '~~~~text\n' + history + '~~~~~\n',
                       '~~~~text\n```json\n' + history + '\n```\n~~~~\n',
                       '\n'.join('> ' + line for line in history.splitlines()) + '\n',
                       '\n'.join('    ' + line for line in history.splitlines()) + '\n',
                       'Setup: answer=' + json.dumps(history) + '\n'):
            with self.subTest(nested=nested[:30]), self.assertRaisesRegex(acceptance.ResultRejected, re.escape(ERROR)):
                acceptance.check_deliverables(DATA['prompt'], nested + 'Unblock plan:' + closing, DATA['kind'])
        report = complete_report()
        report['regression_tests'][1]['setup'] += '\n' + history
        del report['regression_tests'][1]['action']
        with self.assertRaisesRegex(acceptance.ResultRejected, re.escape(ERROR)):
            api_worker.render_report(DATA['prompt'], json.dumps(report), DATA['kind'])
        report['regression_tests'][1]['action'] = "Call safe_source(repo, 'services/example.py')."
        rendered = api_worker.render_report(DATA['prompt'], json.dumps(report), DATA['kind'])
        self.assertEqual(len(re.findall(r'(?m)^Regression test:', rendered)), 2)
        self.assertEqual(len(re.findall(r'(?m)^Action:', rendered)), 2)

    def test_review_assignment_requires_two_cases_without_kind_or_dispatch_prefix(self):
        rendered = api_worker.render_report(DATA['prompt'], json.dumps(complete_report()), DATA['kind'])
        first = rendered.split('\n\nRegression test:', 1)[0]
        prompt = 'Review and regression test-case drafts for current source selection.'
        with self.assertRaisesRegex(acceptance.ResultRejected, re.escape(ERROR)):
            acceptance.check_deliverables(prompt, first)
        acceptance.check_deliverables(prompt, rendered)

    def test_renderer_checks_completion_even_for_plain_test_writing(self):
        for completion in ({'accepted': False, 'reason': 'Incomplete'}, {'accepted': 'true', 'reason': 'Wrong type'},
                           {'accepted': True, 'reason': 'TODO'}, {'accepted': True, 'reason': 'Done', 'extra': 1}):
            report = complete_report()
            report.update(plan=None, completion=completion)
            with self.subTest(completion=completion), self.assertRaises(acceptance.ResultRejected):
                api_worker.render_report('Draft source-selection regression tests.', json.dumps(report), 'test-writing')
        historical = '~~~text\n```json\n{"accepted": true, "reason": "Historical"}\n```\n~~~'
        with self.assertRaisesRegex(acceptance.ResultRejected, 'Missing or ambiguous required completion JSON'):
            acceptance.check_completion_json('Return JSON with accepted/reason fields.', historical)
        for opening, closing in (('~~~~text', '~~~~'), ('````text', '`````')):
            with self.assertRaisesRegex(acceptance.ResultRejected, 'Missing or ambiguous required completion JSON'):
                acceptance.check_completion_json('Return JSON with accepted/reason fields.',
                    historical.replace('~~~text', opening).removesuffix('~~~') + closing)

    def test_contract_places_short_sibling_fields_before_setup_without_changing_task_scope(self):
        contract = api_worker.report_serialization(DATA['prompt'], DATA['kind'])
        schema = json.loads(contract[contract.rindex('\n{') + 1:])
        for case in schema['regression_tests']:
            self.assertEqual(list(case), ['name', 'target', 'action', 'expected', 'setup'])
        self.assertIn('count five sibling keys in EACH case', contract)
        self.assertIn('only name, target and setup is INVALID', contract)
        self.assertNotIn('Optional completion-JSON guard examples', contract)

    def test_snapshot_projects_or_omits_capture_without_leaking_rejected_answer(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            workspaces.git(repo, 'init', '-b', 'main')
            (repo / 'example.py').write_text('value = 1\n')
            workspaces.git(repo, 'add', 'example.py')
            workspaces.git(repo, '-c', 'user.name=Test', '-c', 'user.email=test@localhost',
                           'commit', '-m', 'Source snapshot fixture')
            path = repo / FIXTURE
            path.parent.mkdir(parents=True)
            for padding in ('', 'x' * 70000):
                fixture = dict(DATA, answer=DATA['answer'] + padding)
                path.write_text(json.dumps(fixture))
                workspaces.git(repo, 'add', FIXTURE)
                body, meta = api_worker.evidence(repo, 'minimax', 'Review Web Bob ' + FIXTURE,
                                                 str, kind='test-writing')
                if padding:
                    self.assertIn(FIXTURE, meta['omitted'])
                    self.assertNotIn(FIXTURE, meta['truncated'])
                else:
                    projected = next(row for row in meta['files'] if row['path'] == FIXTURE)
                    self.assertEqual(projected['rendered_fields'], ['prompt', 'kind', 'job_id', 'error'])
                self.assertNotIn('empty answer missing test drafts raises ResultRejected', body)
                self.assertNotIn('complete answer with two test cases and findings passes guard', body)


class MiniMaxProbePublicationTests(unittest.TestCase):
    setUp = dispatch_fixture.DispatchTests.setUp
    tearDown = dispatch_fixture.DispatchTests.tearDown

    def test_api_workers_only_save_complete_reviewed_reports_with_matching_hashes(self):
        self.acceptance.stop()
        for engine in ('gemini', 'minimax'):
            for valid in (False, True):
                job = dispatch.task_queue.enqueue(self.root, '2256', engine + str(valid), DATA['prompt'],
                                                  worker=engine, kind=DATA['kind'])
                claim = dispatch.task_queue.claim(self.root, engine, identifier=job['id'])
                raw = json.dumps(complete_report()) if valid else DATA['answer']
                with patch.object(api_worker, 'evidence', return_value=('Captured current source', {})), \
                     patch.object(dispatch, 'ask', side_effect=[raw, '{"accepted": true, "reason": "Grounded current-source controls"}']) as ask:
                    self.assertEqual(dispatch.execute(job['id'], claim['claim_token']), 0 if valid else 1)
                row = dispatch.task_queue.tasks(self.root)[job['id']]
                saved = self.core / 'state/task-runs' / job['id'] / 'RESULT.md'
                self.assertEqual(ask.call_count, 2 if valid else 1)
                if valid:
                    self.assertEqual(row['status'], 'succeeded')
                    self.assertTrue(row['acceptance']['accepted'])
                    self.assertEqual(hashlib.sha256(row['result'].encode()).hexdigest(), row['result_sha256'])
                    self.assertEqual(saved.read_text().strip(), row['result'])
                    self.assertEqual(Path(row['result_path']).read_text().strip(), row['result'])
                    acceptance.check_deliverables(DATA['prompt'], row['result'], DATA['kind'])
                else:
                    self.assertEqual(row['error'], ERROR)
                    self.assertFalse(saved.exists())
                    self.assertNotIn('result_path', row)


if __name__ == '__main__':
    unittest.main()
