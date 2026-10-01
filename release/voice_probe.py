#!/usr/bin/env python3
"""Real product audio with synthetic speech, no council, workers or messages."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading

CODE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(CODE / d) for d in ('webchat', 'services', 'state')]


def fixture_failure(chat):
    """Only owned isolated fixture metadata; never copy transcripts or secrets."""
    def digest(value):
        return hashlib.sha256(str(value or '').encode()).hexdigest()

    def allowed(value, choices):
        return value if value in choices else 'other'

    with chat.lock:
        conversations = list(chat.conversations.values())
        records = []
        for conversation in conversations[:8]:
            messages = conversation.get('messages', [])
            records.append(dict(conversation_sha256=digest(conversation.get('id')),message_count=len(messages),
                messages=[dict(role=allowed(m.get('role'),('user','assistant','system')),
                    status=allowed(m.get('status'),('done','running','queued','error','waiting','cancelled')),
                    provider=allowed(m.get('provider'),('gemini','dispatcher','voice','system')),
                    request_sha256=digest(m.get('request_id')),content_sha256=digest(m.get('content')),
                    content_bytes=len(str(m.get('content','')).encode()),
                    voice_interrupted=m.get('voice_interrupted') is True,
                    has_task=bool(m.get('task_id') or m.get('task_ids'))) for m in messages[-100:]]))
        calls = list(chat.voice.calls.values())
        return dict(scope='owned isolated fixture only',conversation_count=len(conversations),conversations=records,
                    call_count=len(calls),calls=[dict(ended=c.get('ended') is True,
                        tool_count=len(c.get('tools',{})),conversation_sha256=digest(c.get('conversation_id')),
                        request_hashes=[digest(r) for r in list(c.get('tools',{}).values())[:64]]) for c in calls[:8]])


def probe(root, output, url=None, engines=('chromium', 'webkit')):
    from app import Chat, Server
    from build_info import BUILD
    from providers import Providers, run
    from voice import create_token
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='solo-voice-') as directory:
        private = Path(directory)
        phrases = {
            'question-short': 'What must Instinct never do? Please answer in one short sentence.',
            'story-complete': 'Tell me a complete story about a sailor who finds a lost compass. Use about one hundred and fifty words. Start with the story itself.',
            'story': 'Tell me a very long story about a sailor. Start right away and keep going for several paragraphs.',
            'interrupt': 'Stop. Just say okay Jeff.',
            'tool': 'Please use your tool to check what version are you running, then read the version number.',
        }
        for name, phrase in phrases.items():
            raw, wav = private / (name + '.aiff'), private / (name + '.wav')
            subprocess.run(['say', '-v', 'Samantha', '-r', '175', '-o', str(raw), phrase], check=True, timeout=30)
            subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-i', str(raw),
                            '-ar', '24000', '-ac', '1', str(wav)], check=True, timeout=15)
        chat = server = None
        if not url:
            def product_api(argv, **kwargs):
                # Actual Gemini writing with private fixture history. Credentials
                # stay at their configured path; no copies or CLI/model fallback.
                if argv != [sys.executable, str(CODE / 'webchat/api_call.py'), 'gemini']:
                    raise RuntimeError('Voice proof permits only the Gemini product API')
                kwargs['env'] = dict(kwargs['env'], BOB_ROOT=str(root))
                return run(argv, **kwargs)
            providers = Providers(private, lambda value: value, runner=product_api)
            providers.route_order = lambda _conversation: ('gemini',)
            providers.snapshot = lambda **_: [dict(path='proof-memory', text='Instinct must never send messages; it may only read and draft.')]
            chat = Chat(private / 'conductor/webchat', private, providers)
            chat.voice.token_factory = lambda _root, setup, expires: create_token(root, setup, expires)
            server = Server(('127.0.0.1', 0), chat)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            url = 'http://127.0.0.1:' + str(server.server_port)
        config = dict(url=url, password_file=str(chat.folder / '.password' if chat else root / 'conductor/webchat/.password'), sha=BUILD['sha'])
        (private / 'server.json').write_text(json.dumps(config))
        env = dict(os.environ, BOB_VOICE_PROOF_ROOT=str(private), BOB_VOICE_FIXTURES=str(private),
                   BOB_VOICE_PROOF_OUTPUT=str(output), BOB_PLAYWRIGHT_MODULE=str(root / 'conductor/webchat/node_modules/playwright'))
        try:
            for engine in engines:
                command = ['node', str(CODE / 'webchat/voice_browser_proof.cjs')]
                if engine == 'webkit':
                    command.append('--webkit')
                subprocess.run(command, cwd=CODE, env=env, check=True, timeout=300)
            from task_dispatch import task_queue
            if chat and task_queue.tasks(private):
                raise RuntimeError('Voice proof queued a worker')
        except BaseException:
            if chat:
                try:
                    metadata = fixture_failure(chat)
                    metadata['sha'] = BUILD['sha']
                    (output / 'fixture-failure.json').write_text(json.dumps(metadata,indent=2)+'\n')
                except Exception:
                    # Retain the original failed probe even if diagnostics cannot save.
                    print('Voice fixture failure metadata unavailable',file=sys.stderr)
            raise
        finally:
            if server:
                server.shutdown()
                server.server_close()
                chat.close()
    results = [json.loads((output / (engine + '-proof.json')).read_text()) for engine in engines]
    if not all(r.get('ok') and r.get('real_provider') for r in results):
        raise RuntimeError('Voice proof lacked a real-provider pass')
    return dict(all_pass=True, real_provider=True, real_product_writing=True, synthetic_microphone=True, engines=list(engines),
                real_texts_sent=0, queued_workers=0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--url')
    args = parser.parse_args()
    print(json.dumps(probe(args.root, args.output, args.url)))
