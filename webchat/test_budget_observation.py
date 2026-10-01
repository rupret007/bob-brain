"""Routing observes the checked budget without loading the legacy dashboard API."""
import json
import os
import sys
import types
from unittest.mock import patch

from providers import Providers
from failover import classify
from voice import create_token, VoiceError
from test_webbob_replyq_1856 import SessionFixture


class BudgetObservationTests(SessionFixture):
    def test_known_refill_stops_new_voice_credentials_without_provider_contact(self):
        self.ledger('gemini', 20)
        (self.root / 'conductor/gemini-funding.json').write_text(json.dumps({'refill_required': True}))
        with patch('voice.urlopen') as transport, patch('voice.api_key') as key:
            with self.assertRaises(VoiceError) as error:
                create_token(self.root, {}, 1)
            self.assertIn('refill', error.exception.message)
            transport.assert_not_called()
            key.assert_not_called()

    def test_known_refill_skips_gemini_and_preserves_ordinary_fallback(self):
        self.ledger('gemini', 20)
        self.ledger('minimax', 8)
        (self.root / 'conductor/gemini-funding.json').write_text(json.dumps({'refill_required': True}))
        provider = Providers(self.root, self.chat.redact)
        self.addCleanup(provider.close)
        self.chat.providers = provider
        with patch.object(provider, 'route_order', return_value=('gemini', 'minimax')), \
                patch.object(provider, 'snapshot', return_value=[]), \
                patch.object(provider, 'call', return_value=('A snow-covered lighthouse guards the shore.', None)) as call:
            answer = self.send('Write one sentence about a lighthouse in snow.')
        self.assertEqual(answer['provider'], 'minimax')
        self.assertEqual(call.call_count, 1)
        self.assertEqual(call.call_args.args[0], 'minimax')
        self.assertEqual(answer['attempts'][0]['kind'], 'refill_required')

    def test_refill_remains_visible_after_restart_and_successful_configuration_probe(self):
        self.ledger('gemini', 20)
        funding = self.root / 'conductor/gemini-funding.json'
        funding.write_text(json.dumps({'refill_required': True}))
        for _ in range(2):
            provider = Providers(self.root, self.chat.redact)
            self.addCleanup(provider.close)
            with patch.object(provider, 'run', return_value=(0, 'configured', '')):
                provider.probe_once()
            health = provider.health()['providers']['gemini']
            self.assertEqual(health['reason'], 'refill_required')
            self.assertEqual(health['state'], 'open')
            self.assertIsNone(health['retry_at'])
            self.assertEqual(health['spend']['committed_usd'], 20)
            self.assertEqual(health['spend']['tier'], 'stop')
        self.assertEqual(classify(1, 'RefillRequired: Gemini prepaid credits require refill'), 'refill_required')
        self.assertEqual(classify(1, 'HTTP 429 RESOURCE_EXHAUSTED'), 'rate_limit')

    def ledger(self, name, committed):
        path = self.root / ('conductor/ledger/' + name + '.jsonl')
        path.parent.mkdir(parents=True, exist_ok=True)
        lock = self.root / ('conductor/locks/ledger-' + name + '.lock')
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.touch()
        path.write_text(json.dumps(dict(call_id='settled', cost_usd=committed-1)) + '\n' +
                        json.dumps(dict(call_id='unresolved', cost_usd=None, reserved_usd=1)) + '\n')
        return path

    def test_resource_reply_survives_preloaded_legacy_budget_and_import_path(self):
        files = [self.ledger('gemini', 46), self.ledger('minimax', 8)]
        before = [f.read_bytes() for f in files]
        legacy = types.ModuleType('budget')
        legacy.CAP_USD = 59  # Old display module has no cap() and is not authority.
        legacy.totals = lambda *_: self.fail('Observation must not repair a ledger')
        shadow = self.root / 'legacy-services'
        shadow.mkdir()
        (shadow / 'budget.py').write_text("raise AssertionError('Do not import the legacy budget')\n")
        provider = Providers(self.root, self.chat.redact)
        self.chat.providers = provider
        answer_text = 'The next useful step is to choose the task these resources should support.'
        with patch.dict(sys.modules, {'budget': legacy}), patch.object(sys, 'path', [str(shadow), *sys.path]), \
                patch.object(provider, 'snapshot', return_value=[]), \
                patch.object(provider, 'call', return_value=(answer_text, None)) as call:
            paths = list(sys.path)
            usage = provider.spend('gemini')
            self.assertEqual(sys.path, paths)
            self.assertEqual((usage['cap_usd'], usage['committed_usd'], usage['reserved_usd']), (None, 46, 1))
            self.assertFalse(usage['provider_balance_known'])
            answer = self.send('top priority use any and all resources')
            self.assertEqual(answer['status'], 'done')
            # With Gemini's former local ceiling removed, both lanes are
            # normal tier; the ordinary fast route prefers Gemini.
            self.assertEqual(answer['provider'], 'gemini')
            self.assertEqual(answer['content'], answer_text)
            self.assertEqual(call.call_count, 1)
            self.assertIs(sys.modules['budget'], legacy)
            self.assertFalse(hasattr(legacy, 'cap'))
        self.assertEqual([f.read_bytes() for f in files], before)

    def test_observation_keeps_boundary_and_torn_ledger_without_repair(self):
        path = self.ledger('gemini', 47.5)
        provider = Providers(self.root, self.chat.redact)
        legacy = types.ModuleType('budget')
        with patch.dict(sys.modules, {'budget': legacy}), patch.dict(os.environ, {'BOB_GEMINI_CAP_USD': '50'}):
            self.assertEqual(provider.spend('gemini')['tier'], 'stop')
            path.write_bytes(path.read_bytes() + b'{torn')
            before = path.read_bytes()
            self.assertFalse(provider.spend('gemini')['quota_known'])
            self.assertEqual(path.read_bytes(), before)
            self.assertFalse(path.with_name(path.name + '.interrupted-tail').exists())

    def test_unreadable_cap_is_unknown_and_never_legacy_display_capacity(self):
        provider = Providers(self.root, self.chat.redact)
        for error in (OSError('missing'), ValueError('invalid constant'), SyntaxError('invalid source')):
            with patch('providers.observed_api_cap', side_effect=error):
                value = provider.spend('gemini')
                self.assertFalse(value['quota_known'])
                self.assertIsNone(value['cap_usd'])
