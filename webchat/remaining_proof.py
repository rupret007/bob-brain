#!/usr/bin/env python3
"""Real due reminders and teammate UI over isolated HTTP with synthetic messaging."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import threading

from app import Server
from instinct_fixture import InstinctFixture
from task_dispatch import task_queue


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with InstinctFixture() as fixture:
        config = fixture.root / 'bin/band_messages_watch_run.py'
        config.parent.mkdir()
        config.write_text("CHATS = [{'name': 'Stalemate', 'chat_guid': 'fixture-band'}]\n")
        fixture.mock.chats.append(dict(guid='fixture-band', displayName='Stalemate', participants=[]))
        qa = fixture.root / 'wt-webjam-polish/PRE_KAREN_QA.md'
        qa.parent.mkdir()
        qa.write_text('Karen remains pending.')
        fixture.providers.start_probes = lambda: None
        from unittest.mock import Mock
        fixture.providers.circuit = Mock()
        fixture.chat.start_background()
        server = Server(('127.0.0.1', 0), fixture.chat)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = subprocess.run(['node', str(Path(__file__).with_name('browser_remaining.cjs'))],
                input=json.dumps(dict(url=f'http://127.0.0.1:{server.server_port}', password=fixture.chat.password,
                                     output=str(args.output_dir.resolve()))), text=True, capture_output=True, timeout=100)
            if result.returncode:
                raise RuntimeError(result.stderr)
            evidence = json.loads(result.stdout)
            assert evidence['all_pass'] and len(evidence['browsers']) == 2
            assert not fixture.mock.sends and not fixture.mock.unexpected_writes
            assert ('POST', '/web-bob/v1/confirm') not in fixture.mock.calls
            assert not fixture.providers.calls and not task_queue.tasks(fixture.root)
            assert not any(c.get('_texting', {}).get('audit') for c in fixture.chat.conversations.values())
            utility = subprocess.run(['node', str(Path(__file__).with_name('browser_utility_controls.cjs'))],
                input=json.dumps(dict(url=f'http://127.0.0.1:{server.server_port}', password=fixture.chat.password)),
                text=True, capture_output=True, timeout=100)
            if utility.returncode:
                raise RuntimeError(utility.stderr)
            evidence['utility_controls'] = json.loads(utility.stdout)
            assert evidence['utility_controls']['all_pass'] and len(evidence['utility_controls']['browsers']) == 2
            assert not fixture.mock.sends and not fixture.providers.calls and not task_queue.tasks(fixture.root)
            fixture.mock.drop_send_response = True
            delivery = subprocess.run(['node', str(Path(__file__).with_name('browser_delivery.cjs'))],
                input=json.dumps(dict(url=f'http://127.0.0.1:{server.server_port}', password=fixture.chat.password,
                                     output=str(args.output_dir.resolve()))), text=True, capture_output=True, timeout=100)
            if delivery.returncode:
                raise RuntimeError(delivery.stderr)
            recovered = json.loads(delivery.stdout)
            assert recovered['all_pass'] and len(recovered['browsers']) == 2
            assert len(fixture.mock.sends) == fixture.mock.calls.count(('POST', '/web-bob/v1/confirm')) == 2
            assert fixture.mock.calls.count(('POST', '/web-bob/v1/status')) == 4
            assert not fixture.mock.unexpected_writes and not fixture.providers.calls and not task_queue.tasks(fixture.root)
            audits = [a for c in fixture.chat.conversations.values()
                      for a in c.get('_texting', {}).get('audit', [])]
            assert len(audits) == 2
            assert all(a['event'] == 'owner_confirmed_delivery_unconfirmed' and
                       [check['state'] for check in a.get('delivery_checks', [])] == ['sent', 'sent']
                       for a in audits)
            evidence['delivery_recovery'] = recovered
            evidence.update(scope='isolated synthetic messaging; real HTTP/browser', real_texts_sent=0,
                            synthetic_provider_posts=2, model_calls=0, queued_workers=0)
            (args.output_dir / 'evidence.json').write_text(json.dumps(evidence, indent=2) + '\n')
            print(json.dumps(evidence))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(3)


if __name__ == '__main__':
    main()
