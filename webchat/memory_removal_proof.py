"""Authenticated phone review/removal with synthetic notes; never touches owner memory."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import threading

from app import Handler, Server
from instinct_fixture import InstinctFixture
from memory_store import append_memory
from task_dispatch import task_queue
from texting import Texting


FIRST = '[2026-09-29] Synthetic copper-puffin note\n'
SECOND = '[2026-09-29] Keep café <img src=x onerror=alert(1)> literally\n'
ADDED = '[2026-09-29] Concurrent synthetic save\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for engine in ('chromium', 'webkit'):
        with InstinctFixture() as fixture:
            append_memory(fixture.root, FIRST + SECOND)
            class FixtureHandler(Handler):
                # Private fixture only; inherited dispatch enforces owner and CSRF.
                def post(self, session):
                    if self.path_only == '/api/fixture/change-memory':
                        self.body()
                        append_memory(fixture.root, ADDED)
                        return self.send(200, {'ok': True})
                    return super().post(session)
            server = Server(('127.0.0.1', 0), fixture.chat)
            server.RequestHandlerClass = FixtureHandler
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                result = subprocess.run(['node', str(Path(__file__).with_name('browser_memory_removal.cjs'))],
                    input=json.dumps(dict(url=f'http://127.0.0.1:{server.server_port}', password=fixture.chat.password,
                        output=str(args.output_dir.resolve()), engine=engine)), text=True, capture_output=True, timeout=100)
                if result.returncode:
                    raise RuntimeError(result.stderr)
                evidence = json.loads(result.stdout)
                assert evidence['passed']
                assert (fixture.root / 'conductor/webchat/memory/profile.md').read_text() == SECOND + ADDED
                for conversation in fixture.chat.conversations.values():
                    assert 'copper-puffin' not in json.dumps(Texting.provider_view(conversation))
                assert not fixture.providers.calls and not fixture.mock.sends and not fixture.mock.unexpected_writes
                assert not task_queue.tasks(fixture.root)
                results.append(evidence)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(3)
    evidence = dict(all_pass=True, browsers=results, real_texts_sent=0, model_calls=0, queued_workers=0,
                    real_notes_removed=0, scope='Private synthetic notes with actual HTTP and Chromium/WebKit phone UI')
    (args.output_dir / 'evidence.json').write_text(json.dumps(evidence, indent=2) + '\n')
    print(json.dumps(evidence))


if __name__ == '__main__':
    main()
