"""Offline real Chat/client regressions for the protocol-2 review blockers."""
import copy
import io
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
import uuid
from unittest.mock import Mock, patch

from app import Chat
from texting import Andrea, Texting, TextingError, request_json
from texting_fixture import CHATS, OfflineProviders
from test_andrea_bridge import draft


def health(protocol=2):
    return dict(ok=True, protocol=protocol, service='andrea-web-bob', connected=True,
                paused=False, instinctReadOnly=True, sha=None, deliveryProtocol=1)


def prepared(value):
    return dict(ok=True, draftId=uuid.uuid4().hex * 2, digest='d'*64,
                actionId=uuid.uuid4().hex, expiresAt=(time.time()+299)*1000)


class Protocol2SecurityTests(unittest.TestCase):
    def test_prepare_without_remote_request_binding_refuses_replayed_response(self):
        client = Andrea('http://127.0.0.1:4316', 'synthetic')
        old = draft()
        response = prepared(old)
        for change in ({}, {'conversation_id': 'other'}, {'request_id': 'other'},
                       {'body': 'Different text'}, {'recipient': dict(guid='SMS;-;+15550101011', addresses=['+15550101011'])}):
            with self.subTest(change=change), patch.object(client, 'call', side_effect=[health(), response]):
                self.assertIsNone(client.prepare({**old, **change}))

    def test_remote_request_digest_scope_replay_and_reused_ids_fail_closed(self):
        value = draft()
        response = prepared(value)
        response['requestDigest'] = Andrea.scope_digest(Andrea.scope(value))
        with tempfile.TemporaryDirectory() as folder:
            client = Andrea('http://127.0.0.1:4316', 'synthetic')
            client.bind_state(folder)
            with patch.object(client, 'call', side_effect=[health(), response]):
                remote = client.prepare(value)
            self.assertIsNotNone(remote)
            value['bridge'] = remote
            changes = dict(body='Different text', actor='other', epoch='other', id='other', revision=2,
                           conversation_id='other', request_id='other',
                           recipient=dict(guid='SMS;-;+15550101011', addresses=['+15550101011']))
            for key, changed in changes.items():
                other = {**value, key: changed}
                # Fresh clients exclude the duplicate-ID guard as the reason for refusal.
                fresh = Andrea('http://127.0.0.1:4316', 'synthetic')
                with self.subTest(key=key), patch.object(fresh, 'call', side_effect=[health(), response]):
                    self.assertIsNone(fresh.prepare(other))
                with patch.object(fresh, 'call') as call:
                    self.assertFalse(fresh.deliver(other, 'yes wbtxt-'+'c'*64, 'confirm'))
                    call.assert_not_called()
            # Even a response claiming the new request binding may not reuse an ID.
            for restarted in (False, True):
                if restarted:
                    client = Andrea('http://127.0.0.1:4316', 'synthetic')
                    client.bind_state(folder)
                other = {**value, 'conversation_id': 'new'}
                reused = {**response, 'requestDigest': Andrea.scope_digest(Andrea.scope(other))}
                with patch.object(client, 'call', side_effect=[health(), reused]):
                    self.assertIsNone(client.prepare(other))

    def test_old_receipt_cannot_attest_another_draft_or_old_unbound_record(self):
        value = draft()
        binding = Andrea.scope_digest(Andrea.scope(value))
        remote = dict(protocol=2, draftId='b'*64, digest='d'*64, actionId='action',
                      localDigest=binding, requestDigest=binding)
        value['bridge'] = remote
        result = dict(ok=True, state='submitted', messageGuid='message', deliveryProtocol=1,
                      **{k: remote[k] for k in ('draftId', 'digest', 'actionId', 'requestDigest')})
        result['delivery'] = dict(state='submitted', error=None, checkedAt=None, deliveredAt=None,
                                 fresh=True, **{k: result[k] for k in ('messageGuid', 'actionId', 'digest')})
        self.assertEqual(Andrea.delivery_receipt(value, result), 'submitted')
        other = {**value, 'body': 'Different body'}
        other_digest = Andrea.scope_digest(Andrea.scope(other))
        other['bridge'] = {**remote, 'localDigest': other_digest, 'requestDigest': other_digest}
        self.assertIsNone(Andrea.delivery_receipt(other, result))
        old = copy.deepcopy(value); del old['bridge']['requestDigest']
        client = Andrea('http://127.0.0.1:4316', 'synthetic')
        with patch.object(client, 'call') as call:
            self.assertFalse(client.deliver(old, 'yes wbtxt-'+'c'*64, 'confirm'))
            self.assertIsNone(client.check_delivery(old))
            call.assert_not_called()
        for raw in (json.dumps(result).replace('"ok": true', '"ok": false, "ok": true'),
                    json.dumps(result).replace('"state": "submitted"', '"state": "delivered", "state": "submitted"'),
                    json.dumps(result)[:-1]+', "protocol": 1, "protocol": 2}'):
            with patch('texting.urllib.request.build_opener') as opener:
                opener.return_value.open.side_effect = lambda *a, **kw: io.BytesIO(raw.encode())
                self.assertIsNone(client.deliver(value, 'yes wbtxt-'+'c'*64, 'confirm'))
                self.assertIsNone(client.check_delivery(value))

    def test_protocol_policy_config_and_legacy_records_require_explicit_opt_in(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'config.json'
            path.touch(mode=0o600)
            for policy in (1, 2, True, '1', 1.0, 3, None):
                path.write_text(json.dumps(dict(url='http://127.0.0.1:4316', token='s'*64, protocol=policy)))
                with patch.dict(os.environ, BOB_ANDREA_WEBBOB_CONFIG=str(path)):
                    client = Andrea()
                with patch.object(client, 'call', return_value=health(1)):
                    if type(policy) is int and policy == 1:
                        self.assertIn('connected', client.status())
                    else:
                        with self.assertRaises(TextingError):
                            client.status()
        value = draft()
        value['bridge'] = dict(draftId='b'*64, digest=Andrea.scope_digest(Andrea.scope(value)), actionId='action')
        client = Andrea('http://127.0.0.1:4316', 'synthetic')
        with patch.object(client, 'call') as call:
            self.assertFalse(client.deliver(value, 'yes wbtxt-'+'c'*32, 'confirm'))
            self.assertIsNone(client.check_delivery(value))
            call.assert_not_called()
        legacy = prepared(value)
        legacy.update(protocol=1, digest=value['bridge']['digest'], challenge='wbtxt-'+'c'*32)
        with patch.object(client, 'call', side_effect=[health(), legacy]):
            self.assertIsNone(client.prepare(value))

    def test_release_protocol_rejects_legacy_health_even_after_protocol2(self):
        client = Andrea('http://127.0.0.1:4316', 'synthetic')
        with patch.object(client, 'call', return_value=health()):
            self.assertIn('connected', client.status())
        with patch.object(client, 'call', return_value=health(1)) as call:
            with self.assertRaises(TextingError):
                client.status()
            self.assertIsNone(client.prepare(draft()))
            self.assertTrue(all(c.args[0] == 'health' for c in call.call_args_list))

    def test_raw_duplicate_json_keys_rejected_at_every_depth(self):
        for raw in (b'{"protocol":1,"protocol":2}', b'{"ok":false,"ok":true}',
                    b'{"delivery":{"state":"failed","state":"delivered"}}',
                    b'{"rows":[{"ok":false,"ok":true}]}', b'{"ok":true,"\\u006fk":true}'):
            with self.subTest(raw=raw), patch('texting.urllib.request.build_opener') as opener:
                opener.return_value.open.return_value = io.BytesIO(raw)
                with self.assertRaises(TextingError):
                    request_json('http://127.0.0.1:4316', '/web-bob/v1/confirm')

    def test_chat_protocol2_exact_whitespace_unicode_and_draft_only(self):
        with tempfile.TemporaryDirectory() as folder:
            client = Andrea('http://127.0.0.1:4316', 'synthetic')
            bb = Mock(); bb.chats.return_value = copy.deepcopy(CHATS)
            providers = OfflineProviders()
            chat = Chat(Path(folder)/'webchat', Path(folder), providers, texting=Texting(bb, client))
            self.addCleanup(chat.close)
            sends = []
            rows = {}
            def transport(route, payload=None):
                if route == 'health':
                    return health()
                if route == 'draft':
                    response = prepared(payload)
                    response['requestDigest'] = Andrea.scope_digest(payload)
                    rows[response['draftId']] = response
                    return response
                remote = rows[payload['bridgeDraftId']]
                self.assertEqual(payload['requestDigest'], remote['requestDigest'])
                if route == 'confirm':
                    sends.append(payload)
                result = {k: remote[k] for k in ('draftId', 'digest', 'actionId')}
                result['requestDigest'] = remote['requestDigest']
                result.update(ok=True, state='submitted', messageGuid='synthetic-message', deliveryProtocol=1)
                result['delivery'] = dict(state='submitted', error=None, checkedAt=None, deliveredAt=None,
                                          fresh=True, **{k: result[k] for k in ('messageGuid','actionId','digest')})
                return result
            exact = 'yes wbtxt-'+'c'*64
            variants = [' '+exact+' ', '\u00a0'+exact+'\u00a0', exact+'\n', '\t'+exact,
                        exact+'\r\n', exact+'\u2003', exact+'\u202f', exact+'\u200b',
                        exact.replace('yes ', 'yes\t'), exact.upper(), 'codex: '+exact, exact+' please']
            with patch.object(client, 'call', side_effect=transport):
                for text in variants + [exact]:
                    with self.subTest(text=text):
                        cid = chat.new_conversation()['id']
                        def say(message):
                            return chat.submit(cid, message, str(uuid.uuid4()), actor='owner')['messages'][-1]
                        card = say('draft reply to Alex Morgan: Exact café text.')['text_draft']
                        self.assertIsNone(card['confirm_message'])
                        before = len(sends)
                        answer = say(text)
                        self.assertEqual(len(sends)-before, int(text == exact))
                        if text != exact:
                            self.assertNotIn('Submitted to Messages', answer['content'])
                for hold in ('draft only', 'provided I agree', 'let me see it first', 'after I give the green light'):
                    cid = chat.new_conversation()['id']
                    before = len(sends)
                    answer = say('send a text to Alex Morgan: Bring the charts, '+hold)
                    self.assertEqual(answer['text_draft']['state'], 'pending')
                    self.assertEqual(len(sends), before)
                    self.assertFalse(chat.conversations[cid]['_texting']['audit'])
                # A genuine response for A is substituted for a different recipient/body in B.
                replay = copy.deepcopy(next(iter(rows.values())))
                original_transport = transport
                def substituted(route, payload=None):
                    return replay if route == 'draft' else original_transport(route, payload)
                cid = chat.new_conversation()['id']
                before = len(sends)
                with patch.object(client, 'call', side_effect=substituted):
                    card = say('send a text to Alex Taylor: Different request B.')['text_draft']
                    self.assertFalse(card['delivery_available'])
                    answer = say(exact)
                    self.assertNotIn('Submitted to Messages', answer['content'])
                    self.assertEqual(len(sends), before)
            self.assertFalse(providers.calls)
