"""Prove chat refresh and safe recovery from lost responses in real browsers."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from unittest.mock import Mock

from app import Server
from instinct_fixture import InstinctFixture
from proof_runtime import playwright_environment
from task_dispatch import task_queue


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path,
                        help='Save screenshots and evidence here (default: a unique private temporary directory).')
    args = parser.parse_args()
    os.umask(0o077)
    if args.output_dir is None:
        args.output_dir = Path(tempfile.mkdtemp(prefix='webbob-cold-start-proof-'))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    print('Proof output: ' + str(args.output_dir.resolve()), file=sys.stderr)
    environment = playwright_environment(Path(__file__).resolve().parent)
    with InstinctFixture() as fixture:
        fixture.providers.start_probes = lambda: None
        fixture.providers.circuit = Mock()
        fixture.chat.start_background()
        server = Server(('127.0.0.1', 0), fixture.chat)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = subprocess.run(['node', str(Path(__file__).with_name('browser_cold_start.cjs'))],
                input=json.dumps(dict(url=f'http://127.0.0.1:{server.server_port}', password=fixture.chat.password,
                                     output=str(args.output_dir.resolve()))), text=True, capture_output=True, timeout=60,
                env=environment)
            if result.returncode:
                raise RuntimeError(result.stderr)
            evidence = json.loads(result.stdout)
            assert evidence['all_pass'] and len(evidence['browsers']) == 2
            assert not fixture.mock.sends and not fixture.mock.unexpected_writes
            assert not fixture.providers.calls and not task_queue.tasks(fixture.root)
            assert ('POST', '/web-bob/v1/confirm') not in fixture.mock.calls
            evidence.update(scope='isolated synthetic reminders; real HTTP/browser; delayed overview and lost POST acknowledgment',
                            real_texts_sent=0, model_calls=0, queued_workers=0)
            (args.output_dir / 'evidence.json').write_text(json.dumps(evidence, indent=2) + '\n')
            print(json.dumps(evidence))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(3)


if __name__ == '__main__':
    main()
