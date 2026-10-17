"""Real Python/Andrea HTTP contract with a synthetic provider; no real sends."""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import selectors
import subprocess
import sys
import tempfile
import time
import uuid
from unittest.mock import patch

CODE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE / 'webchat'))
from texting import Andrea, BlueBubbles, Texting, TextingError, request_json
from texting_fixture import MockMessaging, OfflineProviders
from app import Chat


@contextmanager
def worker(andrea, fixture, private, env):
    """Run only the pinned compiled bridge, with no inherited service credentials."""
    with (private/'node.log').open('w') as errors:
        process = subprocess.Popen(['node', '--import=' + str(andrea/'scripts/test-network-guard.mjs'),
            str(fixture)], cwd=private, env=env, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=errors, text=True)
        token = 'synthetic-service-' + uuid.uuid4().hex
        try:
            process.stdin.write(json.dumps(dict(token=token))+'\n'); process.stdin.flush()
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                assert selector.select(30), 'Andrea fixture startup timed out'
                line = process.stdout.readline()
            # Logs may contain adapter errors; never print their bytes.
            assert line.startswith('{"port":'), 'Andrea fixture startup failed'
            yield Andrea('http://127.0.0.1:' + str(json.loads(line)['port']), token)
        finally:
            process.terminate()
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)
            process.stdin.close(); process.stdout.close()


def sample_draft():
    return dict(id='draft-123', conversation_id='conversation-123', actor='a'*64,
                epoch='epoch-123', revision=1, request_id='request-123', body='Synthetic draft.',
                recipient=dict(guid='iMessage;-;+15550101010', addresses=['+15550101010']))


def negative_contract(bridge, health, draft, receipt):
    """Inject malformed responses at each client boundary, without network writes."""
    checked = 0
    for invalid in (0, 3, '2', True, 1.0, 2.0, None, [], {}):
        bad = {**health, 'protocol': invalid}
        with patch.object(bridge, 'call', return_value=bad) as call:
            try: bridge.status()
            except TextingError: pass
            else: raise AssertionError('Unknown health protocol accepted')
            assert bridge.prepare(draft) is None
            assert all(c.args[0] == 'health' for c in call.call_args_list)
        checked += 1
    for bad in ({k:v for k,v in health.items() if k != 'protocol'}, [], {},
                {**health, 'deliveryProtocol': True}, {**health, 'instinctReadOnly': 1}):
        with patch.object(bridge, 'call', return_value=bad):
            try: bridge.status()
            except TextingError: pass
            else: raise AssertionError('Malformed health accepted')
            assert bridge.prepare(draft) is None
        checked += 1
    remote = draft['bridge']
    prepared = dict(ok=True, **{k:remote[k] for k in ('draftId','digest','actionId')}, expiresAt=(time.time()+299)*1000, requestDigest=remote['requestDigest'])
    for bad in ([], {}, {**prepared, 'challenge': 'wbtxt-'+'0'*64},
                {**prepared, 'approvalToken': 'wbtxt-'+'0'*64}, {**prepared, 'expiresAt': True},
                {**prepared, 'state': 'approval_unavailable'}, {**prepared, 'digest': 'bad'}):
        with patch.object(bridge, 'call', side_effect=[health, bad]):
            assert bridge.prepare(draft) is None, 'Malformed approval response accepted'
        checked += 1
    bad_receipts = [None, [], {}, {**receipt, 'unknown': True}, {**receipt, 'ok': 1},
                    {**receipt, 'digest': '0'*64}, {**receipt, 'state': 'unknown'},
                    {**receipt, 'delivery': None}, {**receipt, 'deliveryRefreshUnavailable': 'false'}]
    for key in ('protocol', 'deliveryProtocol'):
        bad_receipts.extend({**receipt, key:v} for v in (0, 3, '2', True, 1.0, None))
    bad_receipts.extend({**receipt, 'delivery': {**receipt['delivery'], key:v}}
                        for key,v in [('digest','0'*64), ('state','sent'), ('fresh',1), ('checkedAt',True)])
    for bad in bad_receipts:
        with patch.object(bridge, 'call', return_value=bad) as call:
            assert bridge.deliver(draft, 'yes wbtxt-'+'0'*64, 'negative-confirm') is None
            assert not bridge.cancel(draft)
            assert bridge.check_delivery(draft) is None
            assert 'status' not in [c.args[0] for c in call.call_args_list]
        with patch.object(bridge, 'call', side_effect=[receipt, bad]):
            assert bridge.check_delivery(draft) is None
        assert bridge.delivery_receipt(draft, bad) is None
        checked += 1
    for approval in ('yes', 'yes wbtxt-'+'0'*32, 'yes wbtxt-'+'A'*64):
        with patch.object(bridge, 'call') as call:
            assert bridge.deliver(draft, approval, 'negative-confirm') is False
            call.assert_not_called()
        checked += 1
    return checked


def offline_negative_contract():
    """Validate the negative matrix without starting servers or Andrea workers."""
    bridge = Andrea('http://127.0.0.1:4316', 'synthetic-offline-token', expected_protocol=2)
    value = sample_draft()
    binding = Andrea.scope_digest(Andrea.scope(value))
    value['bridge'] = dict(protocol=2, draftId='b'*64, digest='d'*64, actionId='synthetic-action',
                           requestDigest=binding, localDigest=binding)
    health = dict(ok=True, protocol=2, service='andrea-web-bob', connected=True,
                  paused=False, instinctReadOnly=True, sha=None, deliveryProtocol=1)
    receipt = dict(ok=True, state='delivered', messageGuid='synthetic-message', deliveryProtocol=1,
                   **{k: value['bridge'][k] for k in ('draftId', 'digest', 'actionId', 'requestDigest')})
    receipt['delivery'] = dict(state='delivered', error=0, checkedAt=time.time()*1000,
                               deliveredAt=None, fresh=True,
                               **{k: receipt[k] for k in ('messageGuid', 'actionId', 'digest')})
    assert bridge.delivery_receipt(value, receipt) == 'delivered'
    return dict(all_pass=True, scope='offline synthetic negative contract',
                negative_contract_cases=negative_contract(bridge, health, value, receipt),
                real_texts_sent=0, worker_dispatches=0)


def probe(andrea):
    pin = json.loads((CODE/'release/andrea-bridge.json').read_text())
    sha = subprocess.check_output(['git','-C',str(andrea),'rev-parse','HEAD'],text=True).strip()
    assert sha == pin['sha'], 'Andrea source differs from the reviewed protocol pin'
    manifest = json.loads((andrea/'dist/build-provenance.json').read_text())
    assert manifest['gitCommit'] == sha and manifest['gitDirtyPathCount'] == 0
    digest = hashlib.sha256()
    # Match Andrea's lexical relative-file ordering, not Path's component order.
    for file in sorted((andrea/'dist').rglob('*'), key=lambda p: p.relative_to(andrea/'dist').as_posix()):
        if file.is_file() and file.name != 'build-provenance.json':
            digest.update(file.relative_to(andrea/'dist').as_posix().encode()+b'\0')
            digest.update(file.read_bytes()+b'\0')
    assert digest.hexdigest() == manifest['artifactSha256'], 'Andrea compiled bytes differ from checked build'
    fixture = andrea / 'scripts/fixtures/web-bob-bridge-worker.mjs'
    assert fixture.is_file()
    with tempfile.TemporaryDirectory(prefix='webbob-bridge-contract-') as temporary:
        private = Path(temporary)
        env = {k: v for k, v in os.environ.items() if not any(t in k.upper() for t in ('TOKEN', 'SECRET', 'PASSWORD', 'KEY'))}
        env.update(NODE_ENV='test', ANDREA_TEST_DISABLE_OWNER_ENV_FILE='1',
                   ANDREA_TEST_DISABLE_PROVIDER_ENV_FILE='1', ANDREA_DETERMINISTIC_STORAGE_MODE='memory')
        env.pop('BOB_ANDREA_WEBBOB_CONFIG', None)
        env.pop('ANDREA_WEBBOB_CONFIG_PATH', None)
        # The unmodified pinned fixture intentionally defaults to disabled owner
        # delivery. Verify that boundary before enabling the hermetic test seam.
        disabled = private/'disabled'; disabled.mkdir()
        with worker(andrea, fixture, disabled, env) as bridge:
            assert bridge.call('health')['protocol'] == pin['protocol'] == 2
            assert bridge.prepare(sample_draft()) is None
            assert not (disabled/'provider-count.json').exists()
        # Copy only the harness to temporary storage. All production modules and
        # provider behavior still come from the verified pin. Like Andrea's own
        # tests, install OwnerChallengeDelivery to receive Andrea-minted tokens
        # independently of HTTP. No Web Bob code can read this test owner inbox.
        source = fixture.read_text()
        source = source.replace("'../../dist/", "'" + (andrea/'dist').as_uri() + '/')
        seam = '    connected: () => true,'
        assert source.count(seam) == 1
        source = source.replace(seam, seam + """
    ownerChallengeDelivery: {
      deliver: async (approvalToken, summary) => {
        fs.writeFileSync('owner-inbox.json', JSON.stringify({approvalToken, summary}), {mode: 0o600});
        if (fs.existsSync('owner-delivery-fails')) throw new Error('Synthetic owner delivery failure');
      },
    },""")
        adapted = private/'owner-fixture.mjs'; adapted.write_text(source)
        with worker(andrea, adapted, private, env) as bridge:
            mock = chat = None
            try:
                assert 'confirm it separately' in bridge.status()
                health = bridge.call('health')
                assert health['protocol'] == pin['protocol'] == 2
                # Failed independent delivery does not confer authority, even on
                # a token that reached the test owner inbox before failure.
                (private/'owner-delivery-fails').touch()
                assert bridge.prepare(sample_draft()) is None
                failed = json.loads((private/'owner-inbox.json').read_text())
                failure_id = {'bridgeDraftId': failed['summary']['bridgeDraftId']}
                assert bridge.call('status', failure_id)['state'] == 'approval_unavailable'
                try: bridge.call('confirm', {**failure_id, 'approvalToken': failed['approvalToken']})
                except TextingError as exc: assert exc.status == 409
                else: raise AssertionError('Failed owner delivery authorized a send')
                assert not (private/'provider-count.json').exists()
                (private/'owner-delivery-fails').unlink()
                # This failed attempt performed one exact-recipient read.
                failed_queries = json.loads((private/'recipient-queries.json').read_text())
                assert len(failed_queries) == 1
                mock = MockMessaging(private)
                chat = Chat(private/'webchat', private, OfflineProviders(),
                            texting=Texting(BlueBubbles(mock.config_db), bridge))
                cid = chat.new_conversation()['id']
                actor = chat.authenticate('bob_session='+chat.login(chat.password))['digest']
                def say(text, request_id=None):
                    return chat.submit(cid, text, request_id or str(uuid.uuid4()), actor=actor)['messages'][-1]
                first = say('draft reply to Alex Morgan: Exact shared-protocol text.\nSecond line.')
                card = first['text_draft']; assert card['state'] == 'pending'
                pending = chat.conversations[cid]['_texting']['drafts'][card['id']]
                assert pending.get('bridge'), 'Real Andrea handshake did not bind the Web Bob draft'
                assert card['confirm_message'] is None and pending['token'] is None
                owner = json.loads((private/'owner-inbox.json').read_text())
                assert owner['summary']['bridgeDraftId'] == pending['bridge']['draftId']
                assert owner['summary']['contentHash'] == pending['bridge']['digest']
                assert owner['summary']['text'] == card['body']
                assert owner['approvalToken'] not in json.dumps(first)
                confirmation = 'yes ' + owner['approvalToken']
                expected_query = dict(guid=card['recipient']['guid'], limit=2, offset=0, **{'with': ['participants']})
                queries_path = private/'recipient-queries.json'
                assert json.loads(queries_path.read_text()) == failed_queries + [expected_query], 'Prepare did not use the actual exact-recipient resolver'
                assert not (private/'provider-count.json').exists()
                assert say('yes')['content'].startswith('Nothing sent')
                assert say('cancel text draft '+card['id'])['content'].startswith('Text draft cancelled')
                assert 'cancelled' in say(confirmation)['content']
                assert not (private/'provider-count.json').exists()
                card = say('draft reply to Alex Morgan: Approved synthetic fixture text.')['text_draft']
                pending = chat.conversations[cid]['_texting']['drafts'][card['id']]
                assert card['confirm_message'] is None
                owner = json.loads((private/'owner-inbox.json').read_text())
                assert owner['summary']['bridgeDraftId'] == pending['bridge']['draftId']
                assert owner['summary']['contentHash'] == pending['bridge']['digest']
                assert owner['summary']['text'] == card['body']
                confirmation = 'yes ' + owner['approvalToken']
                # The legacy approval shape is rejected by the real ingress.
                try: bridge.call('confirm', {**bridge.bound_payload(pending), 'confirmation': confirmation})
                except TextingError as exc: assert exc.status == 400
                else: raise AssertionError('Legacy approval accepted by protocol 2')
                for extra in ({}, {'approvalToken': 'wbtxt-'+'0'*64}):
                    try: bridge.call('confirm', {**bridge.bound_payload(pending), **extra})
                    except TextingError as exc: assert exc.status == 403
                    else: raise AssertionError('Missing or forged owner approval accepted')
                assert not (private/'provider-count.json').exists()
                before_confirm_queries = json.loads(queries_path.read_text())
                assert before_confirm_queries == failed_queries + [expected_query, expected_query]
                request_id = str(uuid.uuid4())
                # Discard only the response after the actual compiled bridge has
                # completed its one synthetic delivery. Recover by receipt, never
                # another confirmation, through the deployed cancel contract.
                def lost_response(base, path, **kwargs):
                    result = request_json(base, path, **kwargs)
                    if path.endswith('/confirm'):
                        raise TextingError('Synthetic lost acknowledgment')
                    return result
                with patch('texting.request_json', side_effect=lost_response):
                    result = say(confirmation, request_id)
                assert 'delivery is unconfirmed' in result['content']
                assert say(confirmation, request_id) == result
                assert 'Submitted to Messages' in say('check text delivery ' + card['id'])['content']
                (private/'delivery-state.json').write_text(json.dumps(dict(error=4)))
                assert 'reports this text failed' in say('check text delivery ' + card['id'])['content']
                # Stale acceptance does not erase a known error.
                (private/'delivery-state.json').write_text('{}')
                assert 'reports this text failed' in say('check text delivery ' + card['id'])['content']
                (private/'delivery-state.json').write_text(json.dumps(dict(isDelivered=True,dateDelivered=time.time()*1000+1)))
                assert 'reports this text delivered' in say('check text delivery ' + card['id'])['content']
                receipt = bridge.call('status', bridge.bound_payload(pending))
                negative_cases = negative_contract(bridge, health, pending, receipt)
                # A mismatched current provider row cannot corroborate delivery.
                (private/'delivery-state.json').write_text(json.dumps(dict(guid='unrelated-message')))
                assert 'Could not refresh' in say('check text delivery ' + card['id'])['content']
                say(confirmation)
                counts = json.loads((private/'provider-count.json').read_text())
                assert counts['sends'] == 1
                queries = json.loads(queries_path.read_text())
                assert queries[:4] == before_confirm_queries + [expected_query], 'Confirm must independently verify recipient before dispatch'
                rcs_query = {**expected_query, 'guid': expected_query['guid'].replace('iMessage;', 'RCS;')}
                assert all(q in (expected_query, rcs_query) for q in queries), 'Only exact same-recipient aliases may be inspected'
                assert rcs_query in queries, 'The migrated RCS alias must actually be verified'
                saved = json.loads((chat.state/(cid+'.json')).read_text())
                assert len(saved['_texting']['audit']) == 1
                assert saved['_texting']['audit'][0]['event'] == 'owner_confirmed_delivery_unconfirmed'
                assert [r['state'] for r in saved['_texting']['audit'][0]['delivery_checks']] == ['submitted','delivery_failed','delivery_failed','delivered']
                assert saved['_texting']['drafts'][card['id']]['state'] == 'delivered'
                assert not mock.sends and not mock.unexpected_writes and not chat.providers.calls
                return dict(all_pass=True, scope='real Python Chat -> Andrea HTTP -> durable SQLite/core action -> synthetic provider',
                            protocol=2, negative_contract_cases=negative_cases,
                            disabled_and_failed_owner_delivery_blocked=True,
                            approval_received_only_via_test_owner_adapter=True,
                            synthetic_provider_posts=1, real_texts_sent=0, worker_dispatches=0,
                            lost_receipt_recovered_without_confirmation_retry=True,
                            acceptance_failure_delivery_and_mismatched_status_verified=True,
                            migrated_recipient_aliases_verified=True,
                            andrea_sha=subprocess.check_output(['git','-C',str(andrea),'rev-parse','HEAD'],text=True).strip(),
                            andrea_artifact_sha256=manifest['artifactSha256'],
                            andrea_fixture_sha256=hashlib.sha256(fixture.read_bytes()).hexdigest(),
                            test_owner_fixture_sha256=hashlib.sha256(adapted.read_bytes()).hexdigest())
            finally:
                if chat: chat.close()
                if mock: mock.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--andrea', type=Path)
    parser.add_argument('--negative-contract', action='store_true', help='Offline synthetic negative cases only')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if not args.negative_contract and args.andrea is None:
        parser.error('--andrea is required unless --negative-contract is selected')
    result = offline_negative_contract() if args.negative_contract else probe(args.andrea.resolve())
    result['at'] = time.time()
    if args.output:
        args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))
