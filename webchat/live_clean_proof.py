#!/usr/bin/env python3
"""Six authenticated chat examples on a private server, with real model replies.

Creates a fresh data root and an ephemeral localhost listener. No worker runner
is started: this proves chat wording and durable submission, not job execution.
"""
import argparse
import hashlib
import http.cookiejar
import json
import os
import re
import subprocess
import tempfile
import threading
import time
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app import Chat, Server, private_write
from task_dispatch import task_queue

CODE_ROOT = Path(__file__).resolve().parents[1]


def service_screens():
    result = subprocess.run(["screen", "-ls"], capture_output=True, text=True, timeout=10)
    return sorted(re.findall(r"\b\d+\.svc-[\w-]+", result.stdout))


def live_listener():
    result = subprocess.run(["lsof", "-tiTCP:8787", "-sTCP:LISTEN"], capture_output=True, text=True, timeout=10)
    pids = sorted(set(result.stdout.split()))
    if not pids:
        return []
    result = subprocess.run(["ps", "-p", ",".join(pids), "-o", "pid=,lstart=,comm="],
                            capture_output=True, text=True, timeout=10, check=True)
    return sorted(line.strip() for line in result.stdout.splitlines())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("claude", "codex", "cursor"), default="claude")
    parser.add_argument("--output", type=Path, help="Also save the redacted proof receipt at this path")
    args = parser.parse_args()
    os.umask(0o077)
    root = Path(tempfile.mkdtemp(prefix="webbob-clean-proof-"))
    before = service_screens()
    listener_before = live_listener()
    chat = Chat(root / "conductor/webchat", root)
    server = Server(("127.0.0.1", 0), chat)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = "http://127.0.0.1:" + str(server.server_address[1])
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    csrf = None
    receipt = dict(root=str(root), url=url, started_at=datetime.now(timezone.utc).isoformat(),
                   service_screens_before=before, live_listener_before=listener_before,
                   provider=args.provider, examples=[], setup=[], replays=0, code_root=str(CODE_ROOT),
                   source_sha256={name: hashlib.sha256((CODE_ROOT / name).read_bytes()).hexdigest() for name in (
                       "webchat/app.py", "webchat/providers.py", "webchat/reply_authority.py", "webchat/reply_guard.py",
                       "webchat/task_dispatch.py", "state/task_queue.py", "webchat/live_clean_proof.py")})
    path = root / "proof.json"

    def save():
        payload = chat.redact(json.dumps(receipt, ensure_ascii=False, indent=2)) + "\n"
        private_write(path, payload)
        if args.output:
            private_write(args.output, payload)

    def call(route, payload=None):
        headers = {"Origin": url}
        if payload is not None:
            headers.update({"Content-Type": "application/json", "X-CSRF-Token": csrf})
        request = urllib.request.Request(url + route, data=json.dumps(payload).encode() if payload is not None else None, headers=headers)
        with opener.open(request, timeout=15) as response:
            return json.load(response)

    def example(message, *, conversation=None, queued=False, setup=False, worker="auto"):
        identifier = conversation or call("/api/conversations", {})["id"]
        request_id = str(uuid.uuid4())
        payload = dict(conversation_id=identifier, request_id=request_id, message=message, provider=args.provider)
        started = time.monotonic()
        value = call("/api/messages", payload)
        while True:
            answer = next(m for m in value["messages"] if m.get("request_id") == request_id and m["role"] == "assistant")
            if answer["status"] not in ("queued", "running"):
                break
            if time.monotonic() - started > 240:
                raise RuntimeError("Timed out waiting for the isolated chat reply")
            time.sleep(.2)
            value = call("/api/conversations/" + identifier)
        entry = dict(message=message, reply=answer["content"], conversation_id=identifier,
                     request_id=request_id, provider=answer["provider"], status=answer["status"],
                     elapsed_seconds=round(time.monotonic() - started, 3), task_id=answer.get("task_id"))
        receipt["setup" if setup else "examples"].append(entry)
        save()
        assert answer["status"] == "done", entry
        assert "No server-confirmed" not in entry["reply"] and "start a job:" not in entry["reply"], entry
        assert "\n" not in entry["reply"] and len(entry["reply"]) < 240, entry
        rows = task_queue.tasks(root)
        entry["queue_rows_for_request"] = sum(row["request_id"] == request_id for row in rows.values())
        if queued:
            row = rows[entry["task_id"]]
            assert (row["conversation_id"], row["request_id"], row["status"], row["requested_worker"]) == (identifier, request_id, "queued", worker)
            assert row["id"] in entry["reply"] and entry["reply"].startswith("Queued"), entry
            # An actual HTTP retransmission must preserve one durable task.
            replay = call("/api/messages", payload)["messages"][-1]
            assert replay["task_id"] == row["id"] and len(task_queue.tasks(root)) == len(rows)
            receipt["replays"] += 1
        else:
            assert not entry["task_id"] and not any(row["request_id"] == request_id for row in rows.values()), entry
        print(json.dumps(entry, ensure_ascii=False), flush=True)
        return identifier, entry

    try:
        login = urllib.request.Request(url + "/login", data=urllib.parse.urlencode({"password": chat.password}).encode(), headers={"Origin": url})
        with opener.open(login, timeout=15) as response:
            response.read()
        csrf = call("/api/session")["csrf"]
        _, plain = example("Keep replies short and friendly.")
        assert plain["provider"] == args.provider, plain
        assert not re.search(r"\b(?:jobs?|queue|ledger|server)\b", plain["reply"], re.I), plain
        example("fix the login button", queued=True)
        example("review PR #161", queued=True)
        example("have Claude review PR #161", queued=True, worker="claude")
        _, ambiguous = example("go")
        assert ambiguous["reply"] == "What would you like me to work on?", ambiguous
        conversation, proposal = example("Can you offer to review PR #162 in one short sentence?", setup=True)
        assert proposal["provider"] == args.provider, proposal
        example("go", conversation=conversation, queued=True)
        rows = task_queue.tasks(root)
        assert len(rows) == 4 and all(row["status"] == "queued" and row["attempts"] == 0 and row["worker"] is None for row in rows.values())
        api_rows = call("/api/jobs")["dispatch"]
        assert {row["id"] for row in api_rows} == set(rows)
        receipt.update(queue_rows=api_rows, queue_sha256=hashlib.sha256((root / "conductor/state/queue.jsonl").read_bytes()).hexdigest())
        receipt["queue_events"] = [json.loads(line) for line in (root / "conductor/state/queue.jsonl").read_text().splitlines()]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
        chat.close()
        receipt["service_screens_after"] = service_screens()
        receipt["live_listener_after"] = live_listener()
        save()
    assert receipt["service_screens_after"] == before, "Live service identities changed during proof"
    assert receipt["live_listener_after"] == listener_before, "Live listener identity changed during proof"
    receipt["finished_at"] = datetime.now(timezone.utc).isoformat()
    receipt["result"] = "PASS"
    save()
    print("PASS — receipt: " + str(path), flush=True)


if __name__ == "__main__":
    main()
