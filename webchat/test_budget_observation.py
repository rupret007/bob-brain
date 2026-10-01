"""Routing observes the checked budget without loading the legacy dashboard API."""
import json
import sys
import types
from unittest.mock import patch

from providers import Providers
from test_webbob_replyq_1856 import SessionFixture


class BudgetObservationTests(SessionFixture):
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
            self.assertEqual((usage['cap_usd'], usage['committed_usd'], usage['reserved_usd']), (50, 46, 1))
            answer = self.send('top priority use any and all resources')
            self.assertEqual(answer['status'], 'done')
            self.assertEqual(answer['provider'], 'minimax')
            self.assertEqual(answer['content'], answer_text)
            self.assertEqual(call.call_count, 1)
            self.assertIs(sys.modules['budget'], legacy)
            self.assertFalse(hasattr(legacy, 'cap'))
        self.assertEqual([f.read_bytes() for f in files], before)

    def test_observation_keeps_boundary_and_torn_ledger_without_repair(self):
        path = self.ledger('gemini', 47.5)
        provider = Providers(self.root, self.chat.redact)
        legacy = types.ModuleType('budget')
        with patch.dict(sys.modules, {'budget': legacy}):
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
