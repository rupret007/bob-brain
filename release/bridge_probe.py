"""Real Python/Andrea HTTP contract with a synthetic provider; no real sends."""
import argparse
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
        with (private/'node.log').open('w') as errors:
            process = subprocess.Popen(['node', '--import=' + str(andrea/'scripts/test-network-guard.mjs'),
                str(fixture)], cwd=private, env=env,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors, text=True)
            token = 'synthetic-service-' + uuid.uuid4().hex
            process.stdin.write(json.dumps(dict(token=token))+'\n'); process.stdin.flush()
            mock = chat = None
            try:
                selector = selectors.DefaultSelector(); selector.register(process.stdout, selectors.EVENT_READ)
                assert selector.select(30), 'Andrea fixture startup timed out'
                line = process.stdout.readline(); selector.close()
                assert line.startswith('{"port":'), 'Andrea fixture startup failed: ' + (private/'node.log').read_text()[-3000:]
                port = json.loads(line)['port']
                bridge = Andrea('http://127.0.0.1:' + str(port), token)
                assert 'confirm it separately' in bridge.status()
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
                assert not (private/'provider-count.json').exists()
                assert say('yes')['content'].startswith('Nothing sent')
                assert say('cancel text draft '+card['id'])['content'].startswith('Text draft cancelled')
                assert 'cancelled' in say(card['confirm_message'])['content']
                assert not (private/'provider-count.json').exists()
                card = say('draft reply to Alex Morgan: Approved synthetic fixture text.')['text_draft']
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
                    result = say(card['confirm_message'], request_id)
                assert 'delivery is unconfirmed' in result['content']
                assert say(card['confirm_message'], request_id) == result
                assert say('check text delivery ' + card['id'])['content'].startswith('Sent via Andrea')
                assert 'already verified sent' in say('check text delivery ' + card['id'])['content']
                say(card['confirm_message'])
                counts = json.loads((private/'provider-count.json').read_text())
                assert counts['sends'] == 1
                saved = json.loads((chat.state/(cid+'.json')).read_text())
                assert len(saved['_texting']['audit']) == 1
                assert saved['_texting']['audit'][0]['event'] == 'owner_sent_via_andrea'
                assert not mock.sends and not mock.unexpected_writes and not chat.providers.calls
                return dict(all_pass=True, scope='real Python Chat -> Andrea HTTP -> durable SQLite/core action -> synthetic provider',
                            synthetic_provider_posts=1, real_texts_sent=0, worker_dispatches=0,
                            lost_receipt_recovered_without_confirmation_retry=True,
                            andrea_sha=subprocess.check_output(['git','-C',str(andrea),'rev-parse','HEAD'],text=True).strip(),
                            andrea_artifact_sha256=manifest['artifactSha256'],
                            andrea_fixture_sha256=hashlib.sha256(fixture.read_bytes()).hexdigest())
            finally:
                if chat: chat.close()
                if mock: mock.close()
                process.terminate()
                try: process.wait(timeout=10)
                except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)
                process.stdin.close(); process.stdout.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--andrea', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = probe(args.andrea.resolve())
    result['at'] = time.time()
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))
