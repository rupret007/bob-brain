#!/usr/bin/env python3
"""Prove blocked sends and delivery-state UI using isolated synthetic messaging."""
import argparse
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=CODE / "reviews")
    args = parser.parse_args()
    os.umask(0o077)
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    before = listeners()
    started = datetime.now(timezone.utc).isoformat()
    with tempfile.TemporaryDirectory(prefix=".texting-proof-", dir=output) as temporary:
        root = Path(temporary)
        mock = MockMessaging(root)
        mock.enable_web_bob_send = False
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
            assert audits[0]["event"] == "owner_confirmed_not_sent"
            assert not mock.sends
            assert ("POST", "/web-bob/v1/draft") in mock.calls
            assert ("POST", "/web-bob/v1/confirm") not in mock.calls
            assert ("POST", "/api/v1/message/text") not in mock.calls
            assert not mock.unexpected_writes
            assert not providers.calls
            assert not task_queue.tasks(root)
            mock.enable_web_bob_send = True
            mock.initial_delivery_state = 'submitted'
            mock.delivery_states = ['delivery_failed', 'delivered']
            delivery_result = subprocess.run(['node', str(CODE/'webchat/browser_texting.cjs')],
                input=json.dumps(dict(url=url,password=chat.password,output=str(output),delivery_flow=True)),
                capture_output=True,text=True,timeout=90,cwd=CODE)
            if delivery_result.returncode:
                raise RuntimeError(delivery_result.stderr)
            delivery_browser = json.loads(delivery_result.stdout)
            assert mock.sends == [dict(chatGuid='iMessage;-;+15550101010',text='Synthetic delivery state test.')]
            assert not mock.delivery_states and not providers.calls and not task_queue.tasks(root)
            assert not mock.unexpected_writes
            assert sum(route == '/web-bob/v1/confirm' for method,route in mock.calls) == 1
            assert sum(route == '/web-bob/v1/status' for method,route in mock.calls) == 2
            browser['screenshots'] += delivery_browser['screenshots']
            after = listeners()
            assert before == after, "Live listener identities changed during proof"
            evidence = {"ok": True, "scope": "mock messaging, real isolated HTTP server and browser",
                "delivery": "blocked_then_synthetic_submission_failure_delivery", "mock_sends": 1, "real_texts_sent": 0,
                "started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(),
                "webchat_url": url, "mock_messaging_url": mock.base,
                "browser": browser, "delivery_browser": delivery_browser, "mock_requests": mock.calls, "unexpected_writes": mock.unexpected_writes,
                "model_calls": len(providers.calls), "queued_jobs": 0,
                "confirmation_audit": [{k: v for k, v in a.items() if k != "actor"} for a in audits],
                "live_listeners_before": before, "live_listeners_after": after,
                "source_sha256": {p: hashlib.sha256((CODE / p).read_bytes()).hexdigest() for p in (
                    "webchat/texting.py", "webchat/app.py", "webchat/providers.py", "webchat/static/app.js",
                    "webchat/static/index.html", "webchat/static/style.css", "webchat/texting_fixture.py",
                    "webchat/texting_proof.py", "webchat/browser_texting.cjs", "webchat/test_texting.py",
                    "webchat/test_texting_e2e.py")},
                "screenshot_sha256": {name: hashlib.sha256((output / name).read_bytes()).hexdigest()
                                      for name in browser["screenshots"]}}
            (output / "WEBBOB-TEXTING-0927.evidence.json").write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n")
            print(json.dumps({"ok": True, "url": url, "screenshots": browser["screenshots"],
                              "real_texts_sent": 0, "delivery": evidence["delivery"], "mock_sends": len(mock.sends)}))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(3)
            chat.close()
            mock.close()


if __name__ == "__main__":
    main()
