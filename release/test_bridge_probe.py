"""Protocol-2 release probe regressions; all transport is synthetic."""
import copy
import unittest
from unittest.mock import Mock, patch

import bridge_probe as probe
from texting import Andrea, TextingError


class BridgeProbeTests(unittest.TestCase):
    def test_protocol1_health_is_refused_and_protocol2_is_accepted(self):
        client, health, draft, receipt = probe.offline_contract_fixture()
        with patch.object(client, 'call', return_value={**health, 'protocol': 1}) as call:
            with self.assertRaises(TextingError):
                client.status()
            self.assertIsNone(client.prepare(draft))
            self.assertTrue(all(c.args[0] == 'health' for c in call.call_args_list))
        prepared = {k: draft['bridge'][k] for k in ('draftId', 'digest', 'actionId', 'requestDigest')}
        prepared.update(ok=True, expiresAt=(probe.time.time()+299)*1000)
        with patch.object(client, 'call', side_effect=[health, prepared]):
            accepted = client.prepare(draft)
        self.assertEqual(accepted['protocol'], 2)
        self.assertEqual(accepted['requestDigest'], Andrea.scope_digest(Andrea.scope(draft)))
        self.assertEqual(client.delivery_receipt(draft, receipt), 'delivered')
        self.assertIsNone(client.delivery_receipt(draft, {**receipt, 'protocol': 1}))

    def test_negative_matrix_exercises_integer_protocol1_and_request_binding(self):
        client, health, draft, receipt = probe.offline_contract_fixture()
        observed = []
        original = client.expected
        def expected(protocol):
            observed.append(protocol)
            return original(protocol)
        with patch.object(client, 'expected', side_effect=expected):
            probe.negative_contract(client, health, draft, receipt)
        self.assertIn(1, [p for p in observed if type(p) is int])

    def test_failed_owner_delivery_uses_original_request_digest(self):
        draft = probe.sample_draft()
        owner = {'summary': {'bridgeDraftId': 'b'*64}, 'approvalToken': 'wbtxt-'+'c'*64}
        expected = {'bridgeDraftId': 'b'*64, 'requestDigest': Andrea.scope_digest(Andrea.scope(draft))}
        def call(route, payload):
            self.assertEqual({k:v for k,v in payload.items() if k != 'approvalToken'}, expected)
            if route == 'confirm':
                self.assertEqual(payload['approvalToken'], owner['approvalToken'])
                raise TextingError('Synthetic refusal', status=409)
            self.assertEqual(route, 'status')
            return {'state': 'approval_unavailable'}
        bridge = Mock(call=Mock(side_effect=call))
        probe.failed_owner_delivery_contract(bridge, draft, owner)
        self.assertEqual(bridge.call.call_count, 2)

    def test_request_digest_matches_andrea_unicode_golden_vector(self):
        draft = probe.sample_draft()
        draft.update(revision=7, body='  Café 🎸 "quoted" \\ back\ttab\nline\x01ctl\u2028sep  ')
        draft['recipient'] = {'guid': 'iMessage;-;+12025550102', 'addresses': ['+12025550102']}
        self.assertEqual(Andrea.scope_digest(Andrea.scope(draft)),
                         '8e6a5e561b5fe14760b7127f1e6e16c380994e4d4692d1ef65377e030df4617e')

    def test_request_digest_required_on_every_receipt(self):
        client, health, draft, receipt = probe.offline_contract_fixture()
        for bad_digest in (None, '', '0'*64, draft['bridge']['digest']):
            with self.subTest(digest=bad_digest):
                bad = {**receipt, 'requestDigest': bad_digest}
                self.assertIsNone(client.delivery_receipt(draft, bad))
        bad = copy.deepcopy(receipt)
        del bad['requestDigest']
        self.assertIsNone(client.delivery_receipt(draft, bad))


if __name__ == '__main__':
    unittest.main()
