#!/usr/bin/env python3
"""Authenticated live dispatch proof. Credentials stay in memory, outside output."""
import argparse
import hashlib
import http.cookiejar
import json
import sys
import time
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORE = HERE.parent
sys.path.insert(0, str(CORE / "state"))
import task_queue

URL = "http://127.0.0.1:8787"
PROOF = CORE / "state/dispatch-proof-0927.json"


def stamp(value=None):
    return datetime.fromtimestamp(time.time() if value is None else value, timezone.utc).isoformat(timespec="milliseconds")


class Client:
    def __init__(self):
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        body = urllib.parse.urlencode({"password": (HERE / ".password").read_text().strip()}).encode()
        request = urllib.request.Request(URL + "/login", data=body, headers={"Origin": URL})
        with self.opener.open(request, timeout=15) as response:
            response.read()
        self.csrf = self.call("/api/session")["csrf"]

    def call(self, path, data=None):
        headers = {"Origin": URL}
        if data is not None:
            headers.update({"Content-Type": "application/json", "X-CSRF-Token": self.csrf})
        request = urllib.request.Request(URL + path, data=json.dumps(data).encode() if data is not None else None, headers=headers)
        with self.opener.open(request, timeout=20) as response:
            return json.load(response)


def cases(refill=False):
    if refill:
        return [("gemini", "Calculate the pickup delay in seconds for a job queued at 15:02:03.250 UTC and claimed at 15:02:07.750 UTC. Show the subtraction and state whether it meets a five-second pickup objective. This is a fresh worker-refill task after a service restart.")]
    claim = (CORE / "state/task_queue.py").read_text().split("def claim(", 1)[1].split("def transition(", 1)[0]
    return [
        ("codex", "Review services/command.py in your assigned checkout. Read the file and explain how timeout and SIGTERM clean up child process groups. Cite two line numbers and identify one limit of this protection. Do not modify files; return a concrete review under 150 words."),
        ("gemini", "Review this actual claim implementation for duplicate-pickup races. Explain the one-worker/one-task invariant and identify one boundary that this function alone cannot guarantee. Return under 130 words.\n\n def claim(" + claim),
        ("minimax", "Analyze this Web Bob result-delivery protocol for crash recovery: (1) persist a terminal worker result in state/queue.jsonl under its claim token; (2) derive a deterministic assistant message ID from task ID; (3) save that message into the originating conversation; (4) mark the result delivered in the queue. On retry, check if that message ID already exists before appending. Explain the outcome of a crash between each adjacent pair of steps and whether it can duplicate a visible answer. Give a compact three-row table and one conclusion."),
    ]


def save(data):
    PROOF.parent.mkdir(parents=True, exist_ok=True)
    temporary = PROOF.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n")
    temporary.chmod(0o600)
    temporary.replace(PROOF)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("submit", "verify", "refill", "retry-codex", "latency-minimax"))
    args = parser.parse_args()
    client = Client()
    data = json.loads(PROOF.read_text()) if PROOF.exists() else {"tasks": [], "verifications": []}
    if args.mode != "verify":
        pending = []
        selected = cases(args.mode == "refill")
        if args.mode == "retry-codex":
            selected = [case for case in selected if case[0] == "codex"]
        if args.mode == "latency-minimax":
            selected = [("minimax", "Calculate dispatch latency from these actual UTC events on the same date: queued 14:56:00.758, claimed 14:56:04.652, execution started 14:56:04.714, finished 14:56:30.337, chat answer saved 14:56:30.348. Report four durations in seconds to three decimals: queue wait (claimed minus queued), execution (finished minus started), delivery (chat minus finished), and end-to-end (chat minus queued). Show a compact table with the subtraction for each. This is an actual service measurement task; do not review code or propose changes.")]
        for worker, message in selected:
            conversation = client.call("/api/conversations", {})["id"]
            request_id = str(uuid.uuid4())
            accepted = client.call("/api/messages", dict(conversation_id=conversation, message=message, request_id=request_id, worker=worker))
            task_id = accepted["messages"][-1].get("task_id")
            if not task_id:
                raise RuntimeError("Chat did not return a durable task ID")
            entry = dict(worker=worker, task_id=task_id, conversation_id=conversation, request_id=request_id,
                         submitted_at=stamp(), request=message, phase=args.mode)
            data["tasks"].append(entry)
            pending.append(entry)
            save(data)
            print("Submitted", worker, task_id, entry["submitted_at"], flush=True)
        deadline = time.monotonic() + 480
        seen = {}
        while pending and time.monotonic() < deadline:
            rows = task_queue.tasks(CORE.parent)
            for entry in pending[:]:
                row = rows[entry["task_id"]]
                state = (row["status"], row["attempts"])
                if seen.get(row["id"]) != state:
                    seen[row["id"]] = state
                    print(stamp(), entry["worker"], state, "claimed", stamp(row["claimed_at"]) if row.get("claimed_at") else "pending", flush=True)
                history = client.call("/api/conversations/" + entry["conversation_id"])
                results = [m for m in history["messages"] if m.get("task_id") == row["id"] and m.get("task_status")]
                if results:
                    assert len(results) == 1, "Duplicate visible result"
                    result = results[0]
                    entry.update(status=row["status"], claimed_at=stamp(row["claimed_at"]), started_at=stamp(row["started_at"]),
                                 finished_at=stamp(row["finished_at"]), chat_at=stamp(result["created_at"]), answer=result["content"],
                                 result_message_id=result["id"], attempts=row["attempts"], result_sha256=row.get("result_sha256"))
                    save(data)
                    assert row["status"] == "succeeded", "Worker task failed; inspect the saved failure result"
                    assert result["provider"] == entry["worker"]
                    assert row["result"] in result["content"]
                    assert hashlib.sha256(row["result"].encode()).hexdigest() == row["result_sha256"]
                    print("Answered", entry["worker"], row["id"], entry["chat_at"], flush=True)
                    pending.remove(entry)
            if pending:
                time.sleep(2)
        if pending:
            raise RuntimeError("Live proof deadline expired; tasks still pending")
    else:
        for entry in data["tasks"]:
            history = client.call("/api/conversations/" + entry["conversation_id"])
            results = [m for m in history["messages"] if m.get("id") == entry["result_message_id"]]
            assert len(results) == 1 and results[0]["content"] == entry["answer"]
            print("Verified after restart", entry["worker"], entry["task_id"], flush=True)
        data["verifications"].append(dict(at=stamp(), task_count=len(data["tasks"]), result="all original answers present exactly once"))
        save(data)


if __name__ == "__main__":
    main()
