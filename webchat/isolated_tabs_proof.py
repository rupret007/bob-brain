#!/usr/bin/env python3
"""Capture and test all tabs on a private listener/data root; never launch models."""
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
from live_clean_proof import live_listener, service_screens
from providers import Providers


class NoGeneration(Providers):
    calls = 0

    def reply(self, *args, **kwargs):
        self.calls += 1
        raise AssertionError("The tab proof must not call a model")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("reviews"))
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(timezone.utc).isoformat()
    before = dict(listener=live_listener(), services=service_screens())
    with tempfile.TemporaryDirectory(prefix="webbob-tabs-") as temporary:
        root = Path(temporary)
        provider = NoGeneration(root, lambda text: text)
        chat = Chat(root / "conductor/webchat", root, provider)
        server = Server(("127.0.0.1", 0), chat)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        env = dict(os.environ, WEBBOB_TEST_URL=f"http://127.0.0.1:{server.server_address[1]}",
                   WEBBOB_TEST_PASSWORD_FILE=str(chat.folder / ".password"), WEBBOB_TEST_OUTPUT=str(output))
        try:
            result = subprocess.run(["node", str(Path(__file__).with_name("browser_tabs.cjs"))],
                                    env=env, timeout=180, check=False)
            if result.returncode:
                raise SystemExit(result.returncode)
            assert provider.calls == 0, "The proof called a model"
            assert not (root / "conductor/state/queue.jsonl").exists(), "The proof created a job"
        finally:
            server.shutdown()
            server.server_close()
            thread.join(3)
            chat.close()
    after = dict(listener=live_listener(), services=service_screens())
    evidence = output / "WEBBOB-CLEAN-0927.tabs-evidence.json"
    value = json.loads(evidence.read_text())
    value.update(live_before=before, live_after=after, started_at=started_at, finished_at=datetime.now(timezone.utc).isoformat(),
                 live_services_unchanged=before == after,
                 provider_calls=provider.calls, jobs_created=0,
                 isolation="Temporary data root and ephemeral loopback listener; no model calls, probes or workers started.")
    code = Path(__file__).resolve().parents[1]
    value["source_sha256"] = {name: hashlib.sha256((code / name).read_bytes()).hexdigest() for name in (
        "webchat/static/index.html", "webchat/static/app.js", "webchat/static/style.css", "webchat/tab_status.py",
        "webchat/app.py", "webchat/jobs_view.py", "webchat/worker_activity.py", "webchat/live_status_snapshot.py", "webchat/browser_tabs.cjs", "webchat/isolated_tabs_proof.py")}
    value["screenshot_sha256"] = {name: hashlib.sha256((output / name).read_bytes()).hexdigest() for name in value["screenshots"]}
    if before != after:
        value["result"] = "UI PASS; live service observation changed"
    evidence.write_text(json.dumps(value, indent=2) + "\n")
    assert before == after, "Live service identities changed during the proof; comparison saved in evidence"
    print("PASS: tab screenshots, browser checks, and unchanged live service identities")


if __name__ == "__main__":
    main()
