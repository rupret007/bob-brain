"""Attempt10 controls must agree with the exact guard result before publication."""
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
import test_dispatch as dispatch_fixture
from test_regression_drafts import DATA as DRAFTS

REPO = Path(__file__).resolve().parents[1]
DATA = json.loads((REPO / 'services/fixtures/texting_guard_consistency_1803.json').read_text())


def report():
    value = copy.deepcopy(DRAFTS['complete_report'])
    value['regression_tests'] = api_worker.completion_guard_examples()
    return value


def draft(case):
    return '\n'.join(label + ': ' + case[key] for label, key in
                     (('Regression test', 'name'), ('Target', 'target'), ('Setup', 'setup'),
                      ('Action', 'action'), ('Expected', 'expected')))


class GuardConsistencyTests(unittest.TestCase):
    def test_exact_attempt10_capture_rejects_before_semantic_vote(self):
        for key in ('prompt', 'answer', 'rejected_control'):
            self.assertEqual(hashlib.sha256(DATA[key].encode()).hexdigest(), DATA[key + '_sha256'])
        vote = Mock(return_value='{"accepted":true,"reason":"Looks complete"}')
        with self.assertRaises(acceptance.ResultRejected) as raised:
            acceptance.accept(DATA['prompt'], DATA['answer'], vote, kind=DATA['kind'])
        self.assertEqual(str(raised.exception), DATA['error'])
        vote.assert_not_called()

    def test_missing_and_ambiguous_json_require_exact_rejection_text(self):
        for answer in ('Findings only.', '```json\n{}\n```\n```json\n{}\n```'):
            for expected in ('returns None', 'ResultRejected: Missing completion JSON',
                             "ResultRejected('Malformed required completion JSON output block')",
                             "ResultRejected('Missing or ambiguous required completion JSON output block!')",
                             'the guard rejects the report'):
                case = api_worker.completion_guard_examples()[0]
                case['setup'] = "prompt='Return JSON with accepted/reason fields.'; answer=" + repr(answer)
                case['expected'] = expected
                with self.subTest(answer=answer, expected=expected), self.assertRaisesRegex(
                        acceptance.ResultRejected, re.escape(DATA['error'])):
                    acceptance.check_literal_guard_drafts(draft(case))

    def test_exact_error_is_valid_draft_but_inner_answer_still_rejects(self):
        for inner in ('Findings only.', '```json\n{}\n```\n```json\n{}\n```'):
            case = api_worker.completion_guard_examples()[0]
            case['setup'] = "prompt='Return JSON with accepted/reason fields.'; answer=" + repr(inner)
            case['expected'] = "raises ResultRejected(" + repr(DATA['literal_guard_error']) + ")"
            acceptance.check_literal_guard_drafts(draft(case))
            with self.assertRaises(acceptance.ResultRejected) as raised:
                acceptance.check_completion_json('Return JSON with accepted/reason fields.', inner)
            self.assertEqual(str(raised.exception), DATA['literal_guard_error'])
        # The report's own completion JSON and semantic vote are separate gates.
        raw = report()
        raw['regression_tests'][0] = case
        rendered = api_worker.render_report(DRAFTS['prompt'], json.dumps(raw), DRAFTS['kind'])
        vote = Mock(return_value='{"accepted":true,"reason":"Exact unexecuted guard drafts"}')
        self.assertTrue(acceptance.accept(DRAFTS['prompt'], rendered, vote, kind=DRAFTS['kind'])['accepted'])
        vote.assert_called_once()

    def test_pass_path_and_other_guard_error_classes_are_checked(self):
        case = api_worker.completion_guard_examples()[1]
        acceptance.check_literal_guard_drafts(draft(case))
        case['expected'] = "ResultRejected('Missing or ambiguous required completion JSON output block')"
        with self.assertRaisesRegex(acceptance.ResultRejected, 'returned successfully'):
            acceptance.check_literal_guard_drafts(draft(case))
        case.update(action='acceptance.check_deliverables(prompt, answer, kind="analysis")',
                    setup="prompt='Return an actionable plan.'; answer='Findings only.'")
        actual = acceptance.guard_draft_expected('check_deliverables', 'Return an actionable plan.',
                                                'Findings only.', kind='analysis')
        with self.assertRaisesRegex(acceptance.ResultRejected, 'Missing actionable action plan'):
            acceptance.check_literal_guard_drafts(draft(case))
        case['expected'] = actual
        acceptance.check_literal_guard_drafts(draft(case))

    def test_formatted_outer_labels_cannot_bypass_audit(self):
        case = DATA['rejected_control']
        for body in (case, case.replace('Regression test:', '### Regression test:'),
                     '\n'.join('  ' + line for line in case.splitlines()),
                     re.sub(r'(?m)^(Target|Setup|Action|Expected):', r'**\1:**', case)):
            with self.subTest(body=body), self.assertRaisesRegex(acceptance.ResultRejected,
                                                              'contradicts literal guard outcome'):
                acceptance.check_literal_guard_drafts(body)

    def test_renderer_rejects_contradiction_without_repair(self):
        raw = report()
        raw['regression_tests'][0]['expected'] = 'returns None'
        before = copy.deepcopy(raw)
        with self.assertRaisesRegex(acceptance.ResultRejected, re.escape(DATA['error'])):
            api_worker.render_report(DRAFTS['prompt'], json.dumps(raw), DRAFTS['kind'])
        self.assertEqual(raw, before)

    def test_examples_follow_the_live_guard_and_keep_successful_control(self):
        cases = api_worker.completion_guard_examples()
        for case in cases:
            values = {s.targets[0].id: ast.literal_eval(s.value) for s in ast.parse(case['setup']).body}
            actual = acceptance.literal_guard_outcome('check_completion_json', **values)
            if actual is None:
                self.assertEqual(case['expected'], 'returns None')
            else:
                self.assertIn(actual, case['expected'])
            acceptance.check_literal_guard_drafts(draft(case))
        with patch.object(acceptance, 'check_completion_json', side_effect=acceptance.ResultRejected('changed guard text')):
            self.assertEqual(api_worker.completion_guard_examples()[0]['expected'],
                             "raises ResultRejected('changed guard text')")


class GuardPublicationTests(unittest.TestCase):
    setUp = dispatch_fixture.DispatchTests.setUp
    tearDown = dispatch_fixture.DispatchTests.tearDown

    def test_contradiction_never_saves_and_exact_drafts_save_verified_hashes(self):
        self.acceptance.stop()
        for engine in ('gemini', 'minimax', 'claude', 'codex', 'cursor'):
            for valid in (False, True):
                raw = report()
                if not valid:
                    raw['regression_tests'][0]['expected'] = "ResultRejected('Missing JSON output')"
                job = dispatch.task_queue.enqueue(self.root, '1803', engine + str(valid), DRAFTS['prompt'],
                        worker=engine, kind=DRAFTS['kind'] if engine in dispatch.task_queue.API_WORKERS else 'analysis')
                claim = dispatch.task_queue.claim(self.root, engine, identifier=job['id'])
                with patch.object(dispatch, 'prepare_task', return_value=self.root), \
                     patch.object(api_worker, 'evidence', return_value=('Captured evidence', {})), \
                     patch.object(dispatch, 'ask', side_effect=[json.dumps(raw),
                         '{"accepted":true,"reason":"Grounded report"}']) as ask:
                    self.assertEqual(dispatch.execute(job['id'], claim['claim_token']), 0 if valid else 1)
                row = dispatch.task_queue.tasks(self.root)[job['id']]
                saved = self.core / 'state/task-runs' / job['id'] / 'RESULT.md'
                if valid:
                    self.assertTrue(row['acceptance']['accepted'])
                    self.assertEqual(saved.read_text().strip(), row['result'])
                    self.assertEqual(row['result_sha256'], hashlib.sha256(row['result'].encode()).hexdigest())
                    self.assertEqual(ask.call_count, 2)
                else:
                    self.assertEqual(row['error'], DATA['error'])
                    self.assertFalse(saved.exists())
                    self.assertNotIn('result_path', row)
                    self.assertEqual(ask.call_count, 1)
