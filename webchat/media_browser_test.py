#!/usr/bin/env python3
"""Run real WebKit/Chromium media flows against a disposable localhost fixture.

No production data, provider requests, jobs, deployment, or service restarts.
"""
import argparse
import json
import os
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

from app import Chat, Server
from live_media_proof import StubProviders
from test_chat_media import png_fixture, pdf_fixture


class EchoProviders(StubProviders):
    def reply(self, conversation, cancel, progress):
        user = next(m for m in reversed(conversation['messages']) if m['role'] == 'user')
        markers = ''.join('<bob-webchat-attachment media_id="' + a['media_id'] + '" />' for a in user.get('attachments', []))
        return {'content': 'These are the attachments from your message. ' + markers, 'provider': 'gemini', 'attempts': []}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--screenshots', type=Path)
    args = parser.parse_args()
    code = Path(__file__).resolve().parents[1]
    module = os.environ.get('BOB_PLAYWRIGHT_MODULE')
    for parent in (code, *code.parents):
        candidate = parent / 'conductor/webchat/node_modules/playwright'
        if not module and candidate.is_dir():
            module = str(candidate)
    if not module:
        raise RuntimeError('Set BOB_PLAYWRIGHT_MODULE to the installed Playwright package.')
    if not shutil.which('ffmpeg'):
        raise RuntimeError('ffmpeg is required for the local video fixture.')
    with tempfile.TemporaryDirectory(prefix='webbob-media-browser-') as directory:
        root = Path(directory)
        (root / 'photo.png').write_bytes(png_fixture())
        (root / 'notes.pdf').write_bytes(pdf_fixture())
        (root / 'notes.txt').write_text('A file for the offline browser fixture.')
        # Local fixture creation, no external media or model requests.
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i', 'color=c=red:s=64x64:d=2',
                        '-an', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(root / 'clip.mp4')], check=True, timeout=15)
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-i', str(root / 'clip.mp4'),
                        '-c', 'copy', str(root / 'clip.mov')], check=True, timeout=15)
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-i', str(root / 'clip.mp4'),
                        '-c:v', 'libvpx', '-b:v', '50k', str(root / 'clip.webm')], check=True, timeout=15)
        if shutil.which('sips'):
            subprocess.run(['sips', '-s', 'format', 'heic', str(root / 'photo.png'), '--out', str(root / 'photo.heic')],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        chat = Chat(root / 'conductor/webchat', root, EchoProviders())
        server = Server(('127.0.0.1', 0), chat)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            env = dict(os.environ, BOB_PLAYWRIGHT_MODULE=module)
            command = ['node', str(code / 'webchat/test_media_browser.cjs'),
                       '--url', 'http://127.0.0.1:' + str(server.server_address[1]), '--fixtures', str(root)]
            if args.screenshots:
                args.screenshots.mkdir(parents=True, exist_ok=True)
                command += ['--screenshots', str(args.screenshots.resolve())]
            subprocess.run(command, env=env, check=True, timeout=180)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(2)
            chat.close()
    print(json.dumps({'ok': True, 'isolation': 'temporary root, loopback port, stub provider'}))


if __name__ == '__main__':
    main()
