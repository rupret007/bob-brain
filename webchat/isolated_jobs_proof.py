#!/usr/bin/env python3
"""Phone browser proof on a private listener; live Jobs sources are read-only."""
import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import app
import live_status_snapshot
from app import Chat, Server
from jobs_view import build_jobs_view, result_text
from live_clean_proof import live_listener, service_screens
from worker_activity import parse_processes

CODE = Path(__file__).resolve().parents[1]
SCREENS = {"lane-webbob-jobs": "200.lane-webbob-jobs", "lane-webjam-review": "300.lane-webjam-review"}
PS = """200 1 20:00 Ss SCREEN -dmS lane-webbob-jobs bash
201 200 20:00 S bash
202 201 18:00 S codex exec --model=test-model Fixture task
203 202 18:00 S codex exec --model=test-model Fixture child
300 1 10:00 Ss SCREEN -dmS lane-webjam-review bash
301 300 10:00 S claude --model=test-model -p Fixture task
"""


class NoModels:
    calls = 0

    def health(self, conversation_id=None):
        return dict(providers={}, order=[], fast_order=[])

    def reply(self, *args):
        self.calls += 1
        raise AssertionError("Browser proof must not call a model")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-root", type=Path, required=True)
    parser.add_argument("--screenshot", type=Path, default=CODE / "reviews/webbob-jobs-0927.png")
    parser.add_argument("--output", type=Path, default=CODE / "reviews/WEBBOB-CLEAN-0927.jobs-evidence.json")
    args = parser.parse_args()
    os.umask(0o077)
    root = Path(tempfile.mkdtemp(prefix="webbob-jobs-proof-"))
    model = NoModels()
    chat = Chat(root / "conductor/webchat", root, model)
    mode = root / "mode"
    mode.write_text("fixture")
    now = time.time()
    journal = root / "conductor/state/queue.jsonl"
    journal.parent.mkdir(parents=True, exist_ok=True)
    rows = [dict(id="jobs-active", status="running", project="Web Bob", title="Making the Jobs tab easier to read", pid=201, worker="codex", started_at=now - 1080),
            dict(id="drill-r10-2", status="succeeded", title="Handback drill r10-2 · abc1234", finished_at=now, result="fixture")]
    rows += [dict(id=f"finished-{i}", status="succeeded", project="WebJam", title=f"Review build checks {i}", finished_at=now - 60 * (i + 1),
                  result="Saved browser fixture result <img src=x onerror=alert(1)>", pr_url="https://github.com/example/repo/pull/12" if i == 0 else None)
             for i in range(7)]
    for row in rows:
        row["conversation_id"] = "private-fixture-conversation"
    journal.write_text("".join(json.dumps(row) + "\n" for row in rows))
    empty_root = root / "empty"
    empty_root.mkdir()
    health = root / "conductor/webchat/sessions/provider-health.json"
    health.write_text(json.dumps({"codex": dict(last_success=now, checked_at=now)}))
    poison = "Handback drill r10-2: running screen drill-r10-2 · abc1234 · Web Bob R38 · Builder scheduler · Tick not loaded — run bootstrap"
    (root / "conductor/dashboard.json").write_text(json.dumps(dict(live_ops=dict(now_line=poison, webchat_round=38, generated_at=datetime.now(timezone.utc).isoformat(), running_jobs=[]))))
    (journal.parent / "NOW.md").write_text(poison)
    source_screens, source_processes = live_status_snapshot._screen_sessions, live_status_snapshot.process_table

    def selected_root(default):
        value = mode.read_text().strip()
        return args.live_root.resolve() if value == "live" else empty_root if value == "empty" else default

    def screens(folder):
        value = mode.read_text().strip()
        return source_screens(folder) if value == "live" else {} if value == "empty" else None if value == "unavailable" else SCREENS

    def processes(folder):
        value = mode.read_text().strip()
        return source_processes(folder) if value == "live" else {} if value == "empty" else None if value == "unavailable" else parse_processes(PS)

    before = dict(listener=live_listener(), services=service_screens())
    evidence = dict(started_at=datetime.now(timezone.utc).isoformat(), live_before=before,
                    screenshot_kind="Actual read-only host observations through an isolated authenticated instance. Browser regressions use private journal/process fixtures.")
    server = Server(("127.0.0.1", 0), chat)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    config = root / "browser.json"
    config.write_text(json.dumps(dict(url=f"http://127.0.0.1:{server.server_port}", password=chat.password, mode=str(mode),
                                      screenshot=str(args.screenshot.resolve()), evidence=str(root / "browser-evidence.json"))))
    try:
        with patch("app.build_jobs_view", side_effect=lambda folder: build_jobs_view(selected_root(folder))), \
                patch("app.result_text", side_effect=lambda folder, key: result_text(selected_root(folder), key)), \
                patch("live_status_snapshot._screen_sessions", side_effect=screens), \
                patch("live_status_snapshot.process_table", side_effect=processes):
            thread.start()
            subprocess.run(["node", str(CODE / "webchat/browser_jobs.cjs"), str(config)], check=True, timeout=120)
        evidence["browser"] = json.loads((root / "browser-evidence.json").read_text())
        evidence["provider_calls"] = model.calls
        assert model.calls == 0
        assert journal.read_text() == "".join(json.dumps(row) + "\n" for row in rows)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
        chat.close()
    evidence["live_after"] = dict(listener=live_listener(), services=service_screens())
    assert before == evidence["live_after"], "Live listener/service identities changed during proof"
    evidence["finished_at"] = datetime.now(timezone.utc).isoformat()
    evidence["source_sha256"] = {str(path.relative_to(CODE)): hashlib.sha256(path.read_bytes()).hexdigest() for path in [
        CODE / "webchat" / name for name in ("app.py", "jobs_view.py", "live_status_snapshot.py", "worker_activity.py", "test_jobs_view.py",
                                             "isolated_jobs_proof.py", "browser_jobs.cjs", "static/app.js", "static/index.html", "static/style.css")]}
    evidence["screenshot_sha256"] = hashlib.sha256(args.screenshot.read_bytes()).hexdigest()
    evidence["result"] = "PASS"
    args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    print("PASS — " + str(args.screenshot), flush=True)


if __name__ == "__main__":
    main()
