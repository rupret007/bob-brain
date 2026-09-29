#!/usr/bin/env python3
"""Isolated Web Bob media proof: upload, chat bubble, and screenshots.

Starts a private server on an ephemeral port. Does not touch the live :8787 listener.
"""
import argparse
import base64
import hashlib
import http.cookiejar
import json
import os
import subprocess
import tempfile
import threading
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app import Chat, Server, private_write

CODE_ROOT = Path(__file__).resolve().parents[1]


class StubProviders:
    """Deterministic replies for isolated media proof (no live model calls)."""

    def start_probes(self):
        return None

    def close(self):
        return None

    def health(self, conversation_id=None):
        return {"providers": {}, "order": [], "fast_order": []}

    def reply(self, conversation, cancel, progress):
        progress("gemini", [])
        user = next(m for m in reversed(conversation["messages"]) if m["role"] == "user")
        attachments = user.get("attachments") or []
        if attachments:
            mid = attachments[0]["media_id"]
            content = (
                "I can see your image attachment in this isolated proof. "
                f'<bob-webchat-attachment media_id="{mid}" label="echo" />'
            )
        else:
            content = "Media proof server is up."
        return {"content": content, "provider": "gemini", "codex_thread_id": None, "attempts": []}
PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAIAAABLbSncAAAAEklEQVR4nGP4z8CAFWEXHbQSACj/P8Fu7N9hAAAAAElFTkSuQmCC"
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=CODE_ROOT / "reviews" / "WEBBOB-MEDIA-0927.evidence.json")
    parser.add_argument("--screenshots", type=Path, default=CODE_ROOT / "reviews")
    args = parser.parse_args()
    os.umask(0o077)
    root = Path(tempfile.mkdtemp(prefix="webbob-media-proof-"))
    chat = Chat(root / "conductor/webchat", root, StubProviders())
    server = Server(("127.0.0.1", 0), chat)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = "http://127.0.0.1:" + str(server.server_address[1])
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def call(route, payload=None, headers=None):
        hdrs = {"Origin": url}
        if payload is not None:
            hdrs.update({"Content-Type": "application/json"})
        hdrs.update(headers or {})
        request = urllib.request.Request(url + route, data=json.dumps(payload).encode() if payload is not None else None, headers=hdrs)
        with opener.open(request, timeout=30) as response:
            return json.load(response)

    login = urllib.request.Request(
        url + "/login",
        data=("password=" + chat.password).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded", "Origin": url},
    )
    opener.open(login, timeout=15).read()
    csrf = call("/api/session")["csrf"]
    conv = call("/api/conversations", {}, {"X-CSRF-Token": csrf})
    uploaded = call(
        "/api/media/upload",
        {"conversation_id": conv["id"], "filename": "parity-dot.png", "data_base64": base64.b64encode(PNG_1PX).decode()},
        {"X-CSRF-Token": csrf},
    )
    request_id = str(uuid.uuid4())
    call(
        "/api/messages",
        {
            "conversation_id": conv["id"],
            "message": "Media parity check — I attached a 1×1 PNG.",
            "request_id": request_id,
            "attachments": [uploaded["media_id"]],
            "provider": "auto",
        },
        {"X-CSRF-Token": csrf},
    )
    started = time.monotonic()
    while time.monotonic() - started < 120:
        history = call("/api/conversations/" + conv["id"], headers={"X-CSRF-Token": csrf})
        assistant = next(m for m in history["messages"] if m.get("request_id") == request_id and m["role"] == "assistant")
        if assistant["status"] not in ("queued", "running"):
            break
        time.sleep(0.25)
    else:
        raise RuntimeError("Timed out waiting for isolated media reply")

    args.screenshots.mkdir(parents=True, exist_ok=True)
    shot_login = args.screenshots / "WEBBOB-MEDIA-0927-login.png"
    shot_chat = args.screenshots / "WEBBOB-MEDIA-0927-chat.png"
    shot_attach = args.screenshots / "WEBBOB-MEDIA-0927-attach-preview.png"
    node_script = CODE_ROOT / "webchat" / "media_proof_capture.cjs"
    playwright_module = ""
    for base in [CODE_ROOT, *CODE_ROOT.parents]:
        candidate = base / "conductor/webchat/node_modules/playwright"
        if candidate.is_dir():
            playwright_module = str(candidate)
            break
    env = os.environ.copy()
    if playwright_module:
        env["BOB_PLAYWRIGHT_MODULE"] = playwright_module
    subprocess.run(
        [
            "node",
            str(node_script),
            "--url",
            url,
            "--password-file",
            str(root / "conductor/webchat/.password"),
            "--conversation",
            conv["id"],
            "--out-login",
            str(shot_login),
            "--out-chat",
            str(shot_chat),
            "--out-attach",
            str(shot_attach),
        ],
        check=True,
        timeout=180,
        env=env,
    )

    receipt = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "isolated_url": url,
        "media_id": uploaded["media_id"],
        "conversation_id": conv["id"],
        "assistant_status": assistant["status"],
        "user_attachments": next(m for m in history["messages"] if m["role"] == "user")["attachments"],
        "screenshots": [str(shot_login), str(shot_chat), str(shot_attach)],
        "source_sha256": {
            "webchat/chat_media.py": hashlib.sha256((CODE_ROOT / "webchat/chat_media.py").read_bytes()).hexdigest(),
            "webchat/app.py": hashlib.sha256((CODE_ROOT / "webchat/app.py").read_bytes()).hexdigest(),
        },
    }
    private_write(args.output, json.dumps(receipt, indent=2) + "\n")
    server.shutdown()
    server.server_close()
    thread.join(timeout=3)
    chat.close()
    print(json.dumps({"ok": True, "evidence": str(args.output), "screenshots": receipt["screenshots"]}))


if __name__ == "__main__":
    main()
