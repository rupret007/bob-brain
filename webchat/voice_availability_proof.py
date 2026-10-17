"""Deterministic phone recovery from provider credit and unknown close errors."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import threading
import time

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
        fixture.providers.snapshot = lambda **_: []
        minted = []
        def expired_token(*_):
            # Exercise actual HTTP/server rejection after token creation, using
            # only private fixture state and no external provider credential.
            with fixture.chat.lock:
                pending = [c for c in fixture.chat.voice.calls.values() if c.get('starting')]
                assert len(pending) == 1
                pending[0]['lease_expires'] = time.time() - 1
                minted.append(True)
            return 'auth_tokens/expired-private-fixture'
        fixture.chat.voice.token_factory = expired_token
        server = Server(('127.0.0.1', 0), fixture.chat)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = subprocess.run(['node', str(Path(__file__).with_name('browser_voice_availability.cjs'))],
                input=json.dumps(dict(url=f'http://127.0.0.1:{server.server_port}', password=fixture.chat.password,
                                     output=str(args.output_dir.resolve()))), text=True, capture_output=True, timeout=90)
            if result.returncode:
                raise RuntimeError(result.stderr)
            evidence = json.loads(result.stdout)
            assert evidence['all_pass'] and len(evidence['browsers']) == 2
            assert all(len(b['hangup']) == 5 and all(c['all_pass'] for c in b['hangup'])
                       for b in evidence['browsers'])
            assert not fixture.mock.sends and not fixture.mock.unexpected_writes
            assert not fixture.providers.calls and not task_queue.tasks(fixture.root)
            assert len(minted) == len(fixture.chat.voice.calls) == 2
            assert all(c['ended'] and not c['starting'] for c in fixture.chat.voice.calls.values())
            evidence.update(real_provider=False, real_texts_sent=0, model_calls=0, queued_workers=0)
            (args.output_dir / 'evidence.json').write_text(json.dumps(evidence, indent=2) + '\n')
            print(json.dumps(evidence))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(3)


if __name__ == '__main__':
    main()
