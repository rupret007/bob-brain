"""Authenticated Jobs result recovery using private journals and real browsers."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import threading
import time
from unittest.mock import patch

from app import Server
from instinct_fixture import InstinctFixture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with InstinctFixture() as fixture:
        journal = fixture.root / 'conductor/state/queue.jsonl'
        journal.parent.mkdir(parents=True, exist_ok=True)
        rows = [dict(id='webchat-' + ('a' if name == 'first' else 'b') * 32,
                     conversation_id='private-fixture-history',
                     status='succeeded', project='Web Bob', title=title,
                     finished_at=time.time() - index, result=body)
                for index, (name, title, body) in enumerate((
                    ('first', 'Earlier job', 'First saved result'),
                    ('second', 'Selected job', 'Selected saved result <img src=x onerror=alert(1)>'),
                ))]
        journal.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        conversation = fixture.chat.get(fixture.identifier)
        conversation['messages'].append(dict(
            id='fixture-result-link', role='assistant', status='done', provider='fixture',
            content='[Saved result](/api/jobs/result?id=webchat-' + 'b' * 32 + ')'))
        fixture.chat.save(conversation)
        original = journal.read_bytes()
        server = Server(('127.0.0.1', 0), fixture.chat)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch('live_status_snapshot._screen_sessions', return_value={}), \
                    patch('live_status_snapshot.process_table', return_value={}):
                result = subprocess.run(['node', str(Path(__file__).with_name('browser_jobs_results.cjs'))],
                    input=json.dumps(dict(url=f'http://127.0.0.1:{server.server_port}', password=fixture.chat.password,
                                          output=str(args.output_dir.resolve()))),
                    text=True, capture_output=True, timeout=180)
            if result.returncode:
                raise RuntimeError(result.stderr)
            evidence = json.loads(result.stdout)
            assert evidence['all_pass'] and len(evidence['browsers']) == 2
            assert not fixture.mock.sends and not fixture.mock.unexpected_writes
            assert not fixture.providers.calls and journal.read_bytes() == original
            evidence.update(scope='private saved job results; authenticated HTTP and Chromium/WebKit; no live data',
                            real_texts_sent=0, model_calls=0, workers_dispatched=0, journal_unchanged=True)
            (args.output_dir / 'evidence.json').write_text(json.dumps(evidence, indent=2) + '\n')
            print(json.dumps(evidence))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(3)


if __name__ == '__main__':
    main()
