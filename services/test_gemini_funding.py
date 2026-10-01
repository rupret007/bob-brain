"""Explicit credit exhaustion is terminal; ordinary rate limits remain distinct."""
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import api
import budget
import test_services


class GeminiFundingTests(unittest.TestCase):
    setUp = test_services.ServicesTest.setUp
    tearDown = test_services.ServicesTest.tearDown

    def transport(self, code, error):
        def run(argv, **kwargs):
            Path(argv[argv.index('-o') + 1]).write_text(json.dumps(error))
            return SimpleNamespace(returncode=0, stdout=str(code), stderr='')
        return run

    def test_explicit_credit_failure_is_terminal_durable_and_sanitized(self):
        for code, error in ((402, {}), (429, {'error': {'message':
                'Your prepayment credits are depleted. private-provider-detail'}}),
                (400, {'error': {'code': 'payment_required'}})):
            with self.subTest(code=code):
                budget.authorize_refill_retry('Fixture reset between independent responses')
                with patch.object(api, 'run', side_effect=self.transport(code, error)) as run, \
                        patch.object(api.time, 'sleep') as sleep, patch.object(api, 'log') as log:
                    before = budget.totals('gemini')['calls']
                    with self.assertRaises(budget.RefillRequired) as caught:
                        api.http_json('https://example.invalid', lane='gemini', prompt='test', max_tokens=10)
                    self.assertNotIn('private-provider-detail', str(caught.exception))
                    self.assertEqual(run.call_count, 1)
                    sleep.assert_not_called()
                    log.assert_not_called()
                    observed = budget.status('gemini')
                    self.assertEqual(observed['tier'], 'stop')
                    self.assertEqual(observed['calls'], before + 1)
                    self.assertGreater(observed['reserved_usd'], 0)
                    ledger = budget.path('gemini').read_bytes()
                    with self.assertRaises(budget.RefillRequired):
                        api.http_json('https://example.invalid', lane='gemini', prompt='again', max_tokens=10)
                    self.assertEqual(run.call_count, 1)
                    self.assertEqual(budget.path('gemini').read_bytes(), ledger)
                    marker = (self.core / 'gemini-funding.json').read_text()
                    self.assertNotIn('private-provider-detail', marker)

    def test_generic_quota_failure_retries_without_claiming_empty_credit(self):
        error = {'error': {'status': 'RESOURCE_EXHAUSTED', 'message': 'Quota exceeded; retry later'}}
        with patch.object(api, 'run', side_effect=self.transport(429, error)) as run, \
                patch.object(api.time, 'sleep'), patch.object(api, 'log'):
            with self.assertRaisesRegex(RuntimeError, 'HTTP 429'):
                api.http_json('https://example.invalid', lane='gemini', prompt='test', max_tokens=10)
            self.assertEqual(run.call_count, 3)
            self.assertFalse(budget.funding('gemini').get('refill_required'))
            self.assertEqual(budget.totals('gemini')['calls'], 3)

    def test_latch_write_failure_does_not_buy_more_attempts(self):
        with patch.object(api, 'run', side_effect=self.transport(402, {})) as run, \
                patch.object(budget, 'mark_refill_required', side_effect=OSError('private detail')), \
                patch.object(api.time, 'sleep') as sleep:
            with self.assertRaisesRegex(budget.BudgetExceeded, 'could not be saved') as error:
                api.http_json('https://example.invalid', lane='gemini', prompt='test', max_tokens=10)
            self.assertNotIn('private detail', str(error.exception))
            self.assertEqual(run.call_count, 1)
            sleep.assert_not_called()

    def test_parser_ignores_success_other_errors_and_oversized_or_invalid_bodies(self):
        response = self.root / 'response'
        for raw in ('not json', '[]', json.dumps({'error': {'message':
                    'x' * 32768 + ' prepayment credits are depleted'}}),
                    json.dumps({'error': {'message': 9}})):
            response.write_text(raw)
            self.assertFalse(api.depleted_gemini_credit(429, response))
        response.write_text(json.dumps({'error': {'message': 'Prepayment credits are depleted'}}))
        for code in (200, 401, 500):
            self.assertFalse(api.depleted_gemini_credit(code, response))

    def test_minimax_error_does_not_stop_gemini(self):
        with patch.object(api, 'run', side_effect=self.transport(402, {})), patch.object(api, 'log'):
            with self.assertRaisesRegex(RuntimeError, 'HTTP 402'):
                api.http_json('https://example.invalid', lane='minimax', prompt='test', max_tokens=10, attempts=1)
        self.assertFalse(budget.funding('gemini').get('refill_required'))
