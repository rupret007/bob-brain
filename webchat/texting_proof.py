#!/usr/bin/env python3
"""Run the actual Web Bob UI on a spare port using synthetic messaging only."""
import hashlib
import json
import os
import subprocess
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

from app import Chat, Server
from task_dispatch import task_queue
from texting import Andrea, BlueBubbles, Texting
from texting_fixture import MockMessaging, OfflineProviders

CODE = Path(__file__).resolve().parents[1]


def listeners():
    result = subprocess.run(["lsof", "-nP", "-iTCP:8787", "-iTCP:1234", "-iTCP:4315", "-sTCP:LISTEN"],
                            capture_output=True, text=True, timeout=10)
    return sorted(result.stdout.splitlines()[1:])


def main():
    os.umask(0o077)
    output = CODE / "reviews"
    before = listeners()
    started = datetime.now(timezone.utc).isoformat()
    with tempfile.TemporaryDirectory(prefix=".texting-proof-", dir=output) as temporary:
        root = Path(temporary)
        mock = MockMessaging(root)
        mock.enable_web_bob_send = True
        providers = OfflineProviders()
        texting = Texting(BlueBubbles(mock.config_db), Andrea(mock.base, mock.token))
        chat = Chat(root / "conductor/webchat", root, providers, texting=texting)
        server = Server(("127.0.0.1", 0), chat)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_port}"
        try:
            result = subprocess.run(["node", str(CODE / "webchat/browser_texting.cjs")],
                input=json.dumps({"url": url, "password": chat.password, "output": str(output)}),
                capture_output=True, text=True, timeout=90, cwd=CODE)
            if result.returncode:
                raise RuntimeError(result.stderr)
            browser = json.loads(result.stdout)
            audits = [a for c in chat.conversations.values() for a in c.get("_texting", {}).get("audit", [])]
            assert len(audits) == 1 and audits[0]["body"] == "I’ll bring the charts at 7."
            assert audits[0]["event"] == "owner_sent_via_andrea"
            assert len(mock.sends) == 1 and mock.sends[0]["text"] == "I’ll bring the charts at 7."
            assert ("POST", "/web-bob/send") in mock.calls
            assert not mock.unexpected_writes
            assert not providers.calls
            assert not task_queue.tasks(root)
            after = listeners()
            assert before == after, "Live listener identities changed during proof"
            evidence = {"ok": True, "scope": "mock messaging, real isolated HTTP server and browser",
                "delivery": "mock_andrea_bluebubbles_send",
                "started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(),
                "webchat_url": url, "mock_messaging_url": mock.base,
                "browser": browser, "mock_requests": mock.calls, "unexpected_writes": mock.unexpected_writes,
                "model_calls": len(providers.calls), "queued_jobs": 0,
                "confirmation_audit": [{k: v for k, v in a.items() if k != "actor"} for a in audits],
                "live_listeners_before": before, "live_listeners_after": after,
                "source_sha256": {p: hashlib.sha256((CODE / p).read_bytes()).hexdigest() for p in (
                    "webchat/texting.py", "webchat/app.py", "webchat/providers.py", "webchat/static/app.js",
                    "webchat/static/index.html", "webchat/static/style.css", "webchat/texting_fixture.py",
                    "webchat/texting_proof.py", "webchat/browser_texting.cjs", "webchat/test_texting.py")}}
            (output / "WEBBOB-TEXTING-0927.evidence.json").write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n")
            print(json.dumps({"ok": True, "url": url, "screenshots": browser["screenshots"],
                              "real_texts_sent": 0, "delivery": "mock_andrea", "mock_sends": len(mock.sends)}))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(3)
            chat.close()
            mock.close()


if __name__ == "__main__":
    main()
