"""Release audits distinguish literal checks from independently reviewed drafts."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import audit_texting_probes_2256 as audit
from result_acceptance import ResultRejected

WT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((WT / 'services/fixtures/texting_regression_drafts_1658.json').read_text())
NONLITERAL = """Regression test: renderer rejects the held probe's missing action
Target: services/test_api_workers.py; api_worker.render_report
Setup: report is a deep copy of services/fixtures/texting_regression_drafts_1658.json complete_report; delete cases[1].action; task is the fixture prompt.
Action: call api_worker.render_report(task, json.dumps(report), kind='test-writing').
Expected: raises ResultRejected for the incomplete second draft; no report is saved.

Regression test: renderer keeps complete outer draft fields
Target: services/test_api_workers.py; api_worker.render_report
Setup: report is a deep copy of services/fixtures/texting_regression_drafts_1658.json complete_report; task is the fixture prompt.
Action: call api_worker.render_report(task, json.dumps(report), kind='test-writing').
Expected: returned prose has two outer Regression test headings and two separate nonempty Target, Setup, Action and Expected lines.

Unblock plan:""" + FIXTURE['complete_answer'].split('Unblock plan:', 1)[1]


class ProbeAuditTests(unittest.TestCase):
    def row(self, folder, answer):
        path = Path(folder) / 'report.md'
        path.write_text(answer + '\n')
        return dict(id='synthetic-probe', worker='minimax', model='MiniMax-M2.7',
                    prompt=FIXTURE['prompt'], kind=FIXTURE['kind'], result=answer,
                    result_sha256=hashlib.sha256(answer.encode()).hexdigest(), result_path=str(path),
                    saved_report_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    acceptance=dict(accepted=True, method='task-answer-review',
                                    reason='Synthetic stored independent review for audit tests'))

    def test_non_guard_pair_is_semantic_reviewed_and_never_literal_verified(self):
        with tempfile.TemporaryDirectory() as folder:
            result = audit.audit_job(self.row(folder, NONLITERAL))
        self.assertEqual(result['complete_outer_drafts'], 2)
        self.assertEqual(result['literal_guard_count'], 0)
        self.assertEqual(result['semantic_reviewed_count'], 2)
        self.assertTrue(result['independent_semantic_review'])
        for case in result['cases']:
            self.assertEqual(case['classification'], 'semantic-reviewed')
            self.assertIs(case['literal_verified'], False)
            self.assertNotIn('actual_error', case)
            self.assertNotIn('consistent', case)

    def test_supported_direct_guards_are_all_checked(self):
        with tempfile.TemporaryDirectory() as folder:
            result = audit.audit_job(self.row(folder, FIXTURE['complete_answer']))
        self.assertEqual(result['literal_guard_count'], 2)
        self.assertEqual(result['semantic_reviewed_count'], 0)
        self.assertTrue(result['cases'][0]['actual_error'])
        self.assertIsNone(result['cases'][1]['actual_error'])
        self.assertTrue(all(case['consistent'] for case in result['cases']))

    def test_wrong_literal_expectation_still_rejects_before_audit(self):
        wrong = FIXTURE['complete_answer'].replace(
            "Expected: ResultRejected containing 'Missing or ambiguous required completion JSON output block'.",
            'Expected: returns None.', 1)
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ResultRejected, 'contradicts literal guard outcome'):
                audit.audit_job(self.row(folder, wrong))

    def test_non_guard_pair_requires_independent_review_not_self_report(self):
        with tempfile.TemporaryDirectory() as folder:
            row = self.row(folder, NONLITERAL)
            row['acceptance'] = dict(accepted=True)
            with self.assertRaisesRegex(RuntimeError, 'independent semantic acceptance'):
                audit.audit_job(row)

    def test_nested_or_missing_outer_fields_still_reject(self):
        with tempfile.TemporaryDirectory() as folder:
            for answer in (FIXTURE['answer'], NONLITERAL.replace('Action: call api_worker.render_report',
                                                               '    Action: call api_worker.render_report', 1)):
                with self.subTest(answer=answer[:40]), self.assertRaisesRegex(ResultRejected, 'Missing concrete regression'):
                    audit.audit_job(self.row(folder, answer))


if __name__ == '__main__':
    unittest.main()
