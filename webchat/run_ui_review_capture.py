#!/usr/bin/env python3
"""Start a private Web Bob listener and capture UI review screenshots."""
from __future__ import annotations

import json
import secrets
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch

from app import Chat, Server

CODE = Path(__file__).resolve().parent


class NoModels:
    def health(self, conversation_id=None):
        return dict(providers={}, order=[], fast_order=[])

    def reply(self, *args):
        raise AssertionError("UI capture must not call a model")


def main():
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else CODE.parent / "reviews/WEBBOB-UI-0927/before"
    out_dir.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="webbob-ui-capture-"))
    folder = root / "conductor/webchat"
    folder.mkdir(parents=True, exist_ok=True)
    password = secrets.token_urlsafe(24)
    (folder / ".password").write_text(password + "\n", encoding="utf-8")
    chat = Chat(folder, root, NoModels())
    server = Server(("127.0.0.1", 0), chat)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    url = f"http://{host}:{port}"
    config_path = root / "capture.json"
    config_path.write_text(json.dumps(dict(url=url, password=password, outDir=str(out_dir.resolve()))), encoding="utf-8")
    try:
        with patch("live_status_snapshot._screen_sessions", return_value={}), patch("live_status_snapshot.process_table", return_value={}):
            subprocess.run(
                ["node", str(CODE / "capture_ui_review.cjs"), str(config_path)],
                check=True,
                cwd=str(CODE),
            )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)
    print(json.dumps(dict(ok=True, out=str(out_dir))))


if __name__ == "__main__":
    main()
