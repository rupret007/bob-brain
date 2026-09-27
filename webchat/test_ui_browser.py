#!/usr/bin/env python3
"""Playwright layout smoke for chat + jobs shell (optional dependency)."""
from __future__ import annotations

import json
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

CODE = Path(__file__).resolve().parent


class NoModels:
    def health(self, conversation_id=None):
        return dict(providers={}, order=[], fast_order=[])

    def reply(self, *args):
        raise AssertionError("UI browser test must not call a model")


@unittest.skipUnless(shutil.which("node"), "node required")
class UiBrowserTests(unittest.TestCase):
    def test_phone_chat_and_jobs_render_without_console_errors(self):
        if not (CODE / "node_modules" / "playwright").is_dir():
            self.skipTest("playwright not installed in webchat/node_modules")
        root = Path(tempfile.mkdtemp(prefix="webbob-ui-browser-"))
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        folder = root / "conductor/webchat"
        folder.mkdir(parents=True, exist_ok=True)
        password = secrets.token_urlsafe(24)
        (folder / ".password").write_text(password + "\n", encoding="utf-8")
        chat = Chat(folder, root, NoModels())
        server = Server(("127.0.0.1", 0), chat)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address
        config = root / "ui-browser.json"
        config.write_text(json.dumps(dict(url=f"http://{host}:{port}", password=password)), encoding="utf-8")
        script = CODE / "browser_ui_shell.cjs"
        try:
            with patch("live_status_snapshot._screen_sessions", return_value={}), patch("live_status_snapshot.process_table", return_value={}):
                subprocess.run(["node", str(script), str(config)], check=True, cwd=str(CODE))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(2)


if __name__ == "__main__":
    unittest.main()
