"""Initial connection failures recover through real read-only browser requests."""
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
        before = {p.name: p.read_bytes() for p in fixture.chat.state.glob('*.json')}
        server = Server(('127.0.0.1', 0), fixture.chat)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = subprocess.run(['node', str(Path(__file__).with_name('browser_startup_recovery.cjs'))],
                input=json.dumps(dict(url=f'http://127.0.0.1:{server.server_port}', password=fixture.chat.password,
                                     output=str(args.output_dir.resolve()))), text=True, capture_output=True, timeout=180)
            if result.returncode:
                raise RuntimeError(result.stderr)
            evidence = json.loads(result.stdout)
            assert evidence['all_pass'] and len(evidence['browsers']) == 2
            assert before == {p.name: p.read_bytes() for p in fixture.chat.state.glob('*.json')}
            assert not fixture.mock.sends and not fixture.mock.unexpected_writes
            assert not fixture.providers.calls and not task_queue.tasks(fixture.root)
            evidence.update(scope='Private HTTP/browser startup failures; no inference or message submission',
                            real_texts_sent=0, model_calls=0, queued_workers=0, history_unchanged=True)
            (args.output_dir / 'evidence.json').write_text(json.dumps(evidence, indent=2) + '\n')
            print(json.dumps(evidence))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(3)


if __name__ == '__main__':
    main()
