#!/usr/bin/env python3
"""Isolated HTTP status proof plus a read-only observation of the live host.

Replays the reported four-lane situation with deterministic process evidence.
No external model, worker, live conversation, or live service is started/changed.
"""
import argparse
import hashlib
import http.cookiejar
import json
import tempfile
import threading
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from app import Chat, Server, private_write
from live_clean_proof import live_listener, service_screens
from live_status_snapshot import build_live_status_snapshot
from test_worker_activity import PS, SCREENS
from worker_activity import parse_processes

CODE_ROOT = Path(__file__).resolve().parents[1]
RELEASE = ("The hold is lifted. Bob already started WebJam #161, AdoptIQ #26, StoryBoard #47, and Shelf #10 on Claude, "
           "so don't start duplicates. For anything new, use start a job: plus the task. When I ask for status, give it in plain words from the real queue.")


class NoModel:
    def __init__(self):
        self.calls = 0

    def health(self, conversation_id=None):
        return dict(providers={}, order=[], fast_order=[])

    def reply(self, *args):
        self.calls += 1
        raise AssertionError("Status must use local evidence without generating a model answer")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-root", type=Path, required=True, help="Read-only host data root")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(tempfile.mkdtemp(prefix="webbob-status-proof-"))
    model = NoModel()
    chat = Chat(root / "conductor/webchat", root, model)
    (root / "conductor/lanes.json").write_text(json.dumps({name: dict(state="ready") for name in ("codex", "claude", "cursor", "gemini", "minimax")}))
    (root / "conductor/jobs.jsonl").write_text(json.dumps(dict(job_id="shelf-load-1659", state="harvested", worker=None)) + "\n")
    server = Server(("127.0.0.1", 0), chat)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = "http://127.0.0.1:" + str(server.server_address[1])
    receipt = dict(started_at=datetime.now(timezone.utc).isoformat(), root=str(root), url=url,
                   live_listener_before=live_listener(), service_screens_before=service_screens(),
                   source_sha256={name: hashlib.sha256((CODE_ROOT / name).read_bytes()).hexdigest() for name in (
                       "webchat/app.py", "webchat/reply_authority.py", "webchat/live_status_snapshot.py", "webchat/providers.py",
                       "webchat/worker_activity.py", "webchat/ops_panel.py", "webchat/test_worker_activity.py", "webchat/isolated_status_proof.py")},
                   evidence_kind="Four-lane screen/ps fixtures and actual read-only host observation; no model calls or worker execution.",
                   examples=[], result="INCOMPLETE")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    csrf = None

    def call(route, payload=None):
        headers = {"Origin": url}
        if payload is not None:
            headers.update({"Content-Type": "application/json", "X-CSRF-Token": csrf})
        request = urllib.request.Request(url + route, data=json.dumps(payload).encode() if payload is not None else None, headers=headers)
        with opener.open(request, timeout=10) as response:
            return json.load(response)

    def submit(message, *, evidence="fixture"):
        request_id = str(uuid.uuid4())
        value = call("/api/messages", dict(conversation_id=identifier, message=message, request_id=request_id))
        answer = value["messages"][-1]
        assert answer["status"] == "done", answer
        receipt["examples"].append(dict(message=message, reply=answer["content"], evidence=evidence))
        print(answer["content"], flush=True)
        return answer["content"]

    try:
        request = urllib.request.Request(url + "/login", data=urllib.parse.urlencode({"password": chat.password}).encode(), headers={"Origin": url})
        with opener.open(request, timeout=10) as response:
            response.read()
        csrf = call("/api/session")["csrf"]
        identifier = call("/api/conversations", {})["id"]
        with patch("live_status_snapshot._screen_sessions", return_value=SCREENS), \
                patch("live_status_snapshot.process_table", return_value=parse_processes(PS)), \
                patch("ops_panel.load_live_ops", return_value={}):
            receipt["fixture"] = dict(screens=SCREENS, ps=PS, snapshot=build_live_status_snapshot(root))
            assert submit(RELEASE) == "Ready when you are."
            for message in ("Ok great is it moving along now?", "status"):
                answer = submit(message)
                assert "4 workers are running" in answer
                for fragment in ("Projects push — Claude (opus) — running for 24 min", "Web Bob clean — Codex (gpt-fixture) — running for 18 min",
                                 "Web Bob clean 2 — Codex — running for 12 min", "Web Bob MiniMax — Codex — running for 8 min"):
                    assert fragment in answer
                for hidden in ("None", "History:", "Answering provider:", "lane-", "shelf-load-1659", "start a job:"):
                    assert hidden not in answer
            detailed = submit("Status with screen names, job IDs and PIDs")
            assert "lane-projects-push, 103" in detailed and "shelf-load-1659" in detailed
            assert "None" not in detailed
        # The same HTTP handler also formats a fresh observation of the actual
        # host. Only the sanitized snapshot is retained, never process commands.
        live = build_live_status_snapshot(args.live_root.resolve())
        receipt["live_observation"] = {key: live[key] for key in ("captured_at", "work", "work_counts", "inspection", "queue_counts")}
        with patch("reply_authority.build_live_status_snapshot", return_value=live):
            submit("Is it moving along now?", evidence="read-only live observation")
        receipt["isolated_queue_rows"] = call("/api/jobs")["dispatch"]
        receipt["provider_calls"] = model.calls
        assert receipt["isolated_queue_rows"] == [] and model.calls == 0
        assert not (root / "conductor/state/queue.jsonl").exists()
        receipt["checks_passed"] = True
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
        chat.close()
        receipt["live_listener_after"] = live_listener()
        receipt["service_screens_after"] = service_screens()
        receipt["finished_at"] = datetime.now(timezone.utc).isoformat()
        if (receipt.get("checks_passed") and receipt["live_listener_before"] == receipt["live_listener_after"]
                and receipt["service_screens_before"] == receipt["service_screens_after"]):
            receipt["result"] = "PASS"
        payload = chat.redact(json.dumps(receipt, ensure_ascii=False, indent=2)) + "\n"
        private_write(root / "proof.json", payload)
        private_write(args.output, payload)
    assert receipt["result"] == "PASS"
    print("PASS — evidence: " + str(args.output), flush=True)


if __name__ == "__main__":
    main()
