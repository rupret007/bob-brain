"""Client regressions. Optional cross-repo proof is a separate release command."""
import copy
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from texting import Andrea, TextingError


def draft():
    return dict(id='draft-123', conversation_id='conversation-123', actor='a'*64,
                epoch='epoch-123', revision=1, request_id='request-123', body='Exact text.\nSecond line.',
                recipient=dict(guid='iMessage;-;+15550101010', addresses=['+15550101010']),
                approved_at=time.time())


class AndreaBridgeTests(unittest.TestCase):
    def setUp(self):
        self.client = Andrea('http://127.0.0.1:4316', 'fixture-only-dedicated-token', expected_protocol=1)

    def bound(self):
        value = draft()
        value['bridge'] = dict(draftId='b'*64, digest=Andrea.scope_digest(Andrea.scope(value)), actionId='action-123')
        return value

    def test_missing_prepared_remote_challenge_cannot_send(self):
        with patch('texting.request_json') as request:
            self.assertFalse(self.client.deliver(draft(), 'yes wbtxt-' + 'c'*32, 'confirm-123'))
        request.assert_not_called()

    def test_only_matching_action_recipient_body_digest_receipt_claims_sent(self):
        value = self.bound()
        receipt = dict(ok=True, state='sent', messageGuid='receipt-123', **value['bridge'])
        for key in ('draftId', 'digest', 'actionId', 'state', 'messageGuid', 'ok'):
            with self.subTest(key=key), patch('texting.request_json', return_value={**receipt, key: None}):
                self.assertIsNone(self.client.deliver(value, 'yes wbtxt-' + 'c'*32, 'confirm-123'))
        with patch('texting.request_json', return_value=receipt) as request:
            self.assertEqual(self.client.deliver(value, 'yes wbtxt-' + 'c'*32, 'confirm-123'), 'submitted')
        self.assertEqual(request.call_args.args[1], '/web-bob/v1/confirm')
        self.assertEqual(request.call_args.kwargs['data']['actor'], value['actor'])
        self.assertEqual(request.call_args.kwargs['data']['draftRequestId'], value['request_id'])

    def test_changed_local_scope_is_refused_before_transport(self):
        value = self.bound()
        for key in ('body', 'actor', 'epoch', 'conversation_id', 'request_id'):
            changed = copy.deepcopy(value); changed[key] += 'changed'
            with self.subTest(key=key), patch('texting.request_json') as request:
                self.assertFalse(self.client.deliver(changed, 'yes wbtxt-' + 'c'*32, 'confirm-123'))
                request.assert_not_called()

    def test_delivery_claim_requires_correlated_explicit_transport_evidence(self):
        value = self.bound()
        receipt = dict(ok=True, state='delivered', deliveryProtocol=1, messageGuid='receipt-123', **value['bridge'])
        self.assertIsNone(self.client.delivery_receipt(value, receipt))
        receipt['delivery'] = dict(state='delivered', error=0, checkedAt=time.time()*1000, fresh=True)
        self.assertEqual(self.client.delivery_receipt(value, receipt), 'delivered')
        for key, invalid in [('state','sent'),('error',4),('error',False),('checkedAt',float('nan'))]:
            with self.subTest(key=key, invalid=invalid):
                malformed={**receipt,'delivery':{**receipt['delivery'],key:invalid}}
                self.assertIsNone(self.client.delivery_receipt(value,malformed))

    def test_receipt_check_revokes_pending_then_reads_status_with_exact_binding(self):
        value = self.bound()
        receipt = dict(ok=True, state='sent', messageGuid='receipt-123', **value['bridge'])
        with patch('texting.request_json', return_value=receipt) as request:
            self.assertEqual(self.client.check_delivery(value), 'submitted')
        self.assertEqual([call.args[1] for call in request.call_args_list], ['/web-bob/v1/cancel', '/web-bob/v1/status'])
        self.assertNotIn('confirmation', request.call_args.kwargs['data'])
        for key in ('draftId', 'digest', 'actionId', 'state', 'messageGuid', 'ok'):
            with self.subTest(key=key), patch('texting.request_json', return_value={**receipt, key: None}):
                self.assertIsNone(self.client.check_delivery(value))
        with patch('texting.request_json', side_effect=TextingError('Unavailable', status=403)):
            self.assertIsNone(self.client.check_delivery(value))
        for key in ('body', 'actor', 'epoch', 'conversation_id', 'request_id'):
            changed = copy.deepcopy(value); changed[key] += 'changed'
            with self.subTest(key=key), patch('texting.request_json') as request:
                self.assertIsNone(self.client.check_delivery(changed)); request.assert_not_called()

    def test_only_bound_cancelled_receipt_proves_an_unsent_handoff_revoked(self):
        value = self.bound()
        receipt = dict(ok=True, state='cancelled', **value['bridge'])
        with patch('texting.request_json', return_value=receipt):
            self.assertFalse(self.client.check_delivery(value))
        for key in ('draftId', 'digest', 'actionId', 'state', 'ok'):
            with self.subTest(key=key), patch('texting.request_json', return_value={**receipt, key: None}):
                self.assertIsNone(self.client.check_delivery(value))

    def test_prepare_requires_matching_scope_challenge_and_fresh_expiry(self):
        value = draft()
        response = dict(ok=True, draftId='b'*64, digest=Andrea.scope_digest(Andrea.scope(value)),
                        actionId='action-123', challenge='wbtxt-' + 'c'*32, expiresAt=(time.time()+300)*1000)
        health = dict(ok=True, protocol=1, service='andrea-web-bob', connected=True, paused=False, instinctReadOnly=True)
        with patch('texting.request_json', side_effect=[health, response]):
            self.assertEqual(self.client.prepare(value), response)
        for key, bad in [('digest', '0'*64), ('challenge', 'no'), ('expiresAt', 0), ('expiresAt', float('nan')), ('expiresAt', time.time()*1000+99999999)]:
            with self.subTest(key=key), patch('texting.request_json', side_effect=[health, {**response, key: bad}]):
                self.assertIsNone(self.client.prepare(value))

    def test_control_token_cannot_enable_new_owner_surface(self):
        with patch.dict(os.environ, {'BOB_ANDREA_CONTROL_TOKEN': 'old-token', 'BOB_ANDREA_WEBBOB_CONFIG': ''}):
            self.assertFalse(Andrea().token)

    def test_config_requires_private_regular_local_file(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)/'config.json'
            p.write_text(json.dumps(dict(url='http://127.0.0.1:4316', token='a'*64)))
            with patch.dict(os.environ, {'BOB_ANDREA_WEBBOB_CONFIG': str(p)}):
                p.chmod(0o644); self.assertFalse(Andrea().token)
                p.chmod(0o600); self.assertTrue(Andrea().token)
                p.write_text(json.dumps(dict(url='https://example.invalid', token='a'*64)))
                self.assertFalse(Andrea().token)

    def test_pause_unknown_or_readonly_missing_never_advertises_ready(self):
        health = dict(ok=True, protocol=1, service='andrea-web-bob', connected=True, paused=False, instinctReadOnly=True)
        with patch('texting.request_json', return_value=health):
            self.assertIn('confirm it separately', self.client.status())
        for key in ('paused', 'connected'):
            with patch('texting.request_json', return_value={**health, key: None}):
                self.assertIn('blocked', self.client.status())
