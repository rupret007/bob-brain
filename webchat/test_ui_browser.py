#!/usr/bin/env python3
"""Required real-browser layout check for the integrated UI."""
from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from app import Chat, Server
from music_notebook import save_project

CODE = Path(__file__).resolve().parent


def playwright_module(code):
    override = os.environ.get('BOB_PLAYWRIGHT_MODULE')
    candidates = [Path(override)] if override else [
        code / 'node_modules/playwright',
        *(parent / 'conductor/webchat/node_modules/playwright' for parent in code.parents),
    ]
    for module in candidates:
        if module.is_dir():
            return str(module.resolve())
    raise AssertionError('Set BOB_PLAYWRIGHT_MODULE to the installed Playwright package')


class NoModels:
    def health(self, conversation_id=None):
        return dict(providers={}, order=[], fast_order=[])

    def reply(self, *args):
        raise AssertionError("UI browser test must not call a model")


class PlaywrightModuleTests(unittest.TestCase):
    def test_worktree_finds_shared_runtime(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            root = Path(directory).resolve()
            code = root / "workspaces/review/webchat"
            code.mkdir(parents=True)
            shared = root / "conductor/webchat/node_modules/playwright"
            shared.mkdir(parents=True)
            self.assertEqual(playwright_module(code), str(shared))

    def test_local_runtime_and_explicit_override_take_precedence(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            root = Path(directory).resolve()
            code = root / "workspaces/review/webchat"
            local = code / "node_modules/playwright"
            local.mkdir(parents=True)
            shared = root / "conductor/webchat/node_modules/playwright"
            shared.mkdir(parents=True)
            self.assertEqual(playwright_module(code), str(local))
            os.environ['BOB_PLAYWRIGHT_MODULE'] = str(shared)
            self.assertEqual(playwright_module(code), str(shared))
            os.environ['BOB_PLAYWRIGHT_MODULE'] = str(root / "missing")
            with self.assertRaisesRegex(AssertionError, 'BOB_PLAYWRIGHT_MODULE'):
                playwright_module(code)

    def test_missing_runtime_still_fails(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(Path, 'is_dir', return_value=False):
            with self.assertRaisesRegex(AssertionError, 'BOB_PLAYWRIGHT_MODULE'):
                playwright_module(CODE)


class UiBrowserTests(unittest.TestCase):
    def test_phone_chat_and_jobs_render_without_console_errors(self):
        if not shutil.which('node'):
            self.fail('Node is required for the UI release proof')
        module = playwright_module(CODE)
        root = Path(tempfile.mkdtemp(prefix="webbob-ui-browser-"))
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        folder = root / "conductor/webchat"
        folder.mkdir(parents=True, exist_ok=True)
        password = secrets.token_urlsafe(24)
        (folder / ".password").write_text(password + "\n", encoding="utf-8")
        chat = Chat(folder, root, NoModels())
        saved = save_project(root, {"title": "Preserved private song", "lyrics": "Keep this existing draft"})
        song_path = root / "conductor/webchat/song-projects" / (saved["id"] + ".json")
        song_bytes = song_path.read_bytes()
        server = Server(("127.0.0.1", 0), chat)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address
        config = root / "ui-browser.json"
        config.write_text(json.dumps(dict(url=f"http://{host}:{port}", password=password)), encoding="utf-8")
        script = CODE / "browser_ui_shell.cjs"
        try:
            with patch("live_status_snapshot._screen_sessions", return_value={}), patch("live_status_snapshot.process_table", return_value={}):
                subprocess.run(["node", str(script), str(config)], check=True, cwd=str(CODE), timeout=120,
                               env=dict(os.environ, BOB_PLAYWRIGHT_MODULE=module))
            self.assertEqual(song_bytes, song_path.read_bytes(), "Shell navigation must preserve saved songs")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(2)
            chat.close()


if __name__ == "__main__":
    unittest.main()
