"""Private HTTP/browser proof for stop completion and restart admission."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import threading

from app import Handler, Server
from instinct_fixture import InstinctFixture
from task_dispatch import task_queue


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for engine in ('chromium', 'webkit'):
        with InstinctFixture() as fixture:
            released = threading.Event()
            callbacks = []
            def reply(conversation, cancel, progress):
                callbacks.append('started')
                if not cancel.wait(20):
                    raise RuntimeError('Fixture was not stopped')
                progress('gemini', [])  # A provider that reports after Stop.
                callbacks.append('late_progress')
                if not released.wait(20):
                    raise RuntimeError('Fixture was not released')
                return dict(content='Late answer must not appear.', provider='gemini', attempts=[])
            fixture.providers.reply = reply

            class FixtureHandler(Handler):
                # These controls exist only on this temporary fixture server.
                # The inherited dispatch applies owner auth and Origin/CSRF.
                def post(self, session):
                    if self.path_only == '/api/fixture/release':
                        self.body()
                        released.set()
                        return self.send(200, {'ok': True})
                    if self.path_only == '/api/fixture/close':
                        self.body()
                        fixture.chat.close()
                        return self.send(200, {'ok': True})
                    return super().post(session)

            server = Server(('127.0.0.1', 0), fixture.chat)
            server.RequestHandlerClass = FixtureHandler
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                result = subprocess.run(['node', str(Path(__file__).with_name('browser_reply_lifecycle.cjs'))],
                    input=json.dumps(dict(url=f'http://127.0.0.1:{server.server_port}', password=fixture.chat.password,
                        output=str(args.output_dir.resolve()), engine=engine)), text=True, capture_output=True, timeout=70)
                if result.returncode:
                    raise RuntimeError(result.stderr)
                evidence = json.loads(result.stdout)
                assert evidence['passed'] and callbacks == ['started', 'late_progress']
                assert not fixture.chat.workers
                assert not fixture.mock.sends and not fixture.mock.unexpected_writes
                assert not task_queue.tasks(fixture.root)
                results.append(evidence)
            finally:
                released.set()
                server.shutdown()
                server.server_close()
                thread.join(3)
    evidence = dict(all_pass=True, browsers=results, real_texts_sent=0, model_calls=0, queued_workers=0,
                    scope='Private synthetic provider with actual HTTP and Chromium/WebKit phone UI')
    (args.output_dir / 'evidence.json').write_text(json.dumps(evidence, indent=2) + '\n')
    print(json.dumps(evidence))


if __name__ == '__main__':
    main()
