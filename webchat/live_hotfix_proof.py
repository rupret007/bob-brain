#!/usr/bin/env python3
"""Real API-to-worker proof. Never prints or persists authentication material."""
import argparse
import hashlib
import http.cookiejar
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "state"))
import task_queue
from providers import Redactor


class Client:
    def __init__(self, root, url="http://127.0.0.1:8787"):
        self.url = url
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        password = (root / "conductor/webchat/.password").read_text().strip()
        self.redact = Redactor(root, password)
        request = urllib.request.Request(url + "/login", data=urllib.parse.urlencode({"password": password}).encode(),
                                         headers={"Origin": url})
        with self.opener.open(request, timeout=15) as response:
            response.read()
        self.csrf = self.call("/api/session")["csrf"]

    def call(self, path, data=None):
        headers = {"Origin": self.url}
        if data is not None:
            headers.update({"Content-Type": "application/json", "X-CSRF-Token": self.csrf})
        request = urllib.request.Request(self.url + path, data=json.dumps(data).encode() if data is not None else None,
                                         headers=headers)
        with self.opener.open(request, timeout=20) as response:
            return json.load(response)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--workers", nargs="+", default=["codex", "cursor", "claude"])
    args = parser.parse_args()
    root = args.root.resolve()
    client = Client(root)
    evidence = root / "conductor/state/webbob-hotfix-proof-0927.json"
    data = json.loads(evidence.read_text()) if evidence.exists() else {"tasks": [], "health": []}

    def save():
        temporary = evidence.with_suffix(".tmp")
        with open(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as handle:
            handle.write(client.redact(json.dumps(data, indent=2)) + "\n")
        temporary.replace(evidence)

    for worker in args.workers:
        if any(r["worker"] == worker and r.get("verified") for r in data["tasks"]):
            continue
        conversation = client.call("/api/conversations", {})["id"]
        entry = dict(worker=worker, conversation_id=conversation, request_id=str(uuid.uuid4()), submitted_at=time.time(),
                     request="start a job: write hello to /tmp/wb-proof.txt")
        accepted = client.call("/api/messages", dict(conversation_id=conversation, request_id=entry["request_id"],
                                                     message=entry["request"], worker=worker))
        receipt = accepted["messages"][-1]
        entry.update(task_id=receipt.get("task_id"), receipt=receipt["content"])
        data["tasks"].append(entry)
        save()
        assert entry["task_id"] and entry["task_id"] in receipt["content"], "No visible durable queue receipt"
        print("Created", worker, entry["task_id"], flush=True)
        observed = None
        while time.time() - entry["submitted_at"] < 120:
            row = task_queue.tasks(root)[entry["task_id"]]
            if row["status"] != observed:
                observed = row["status"]
                print(worker, entry["task_id"], observed, flush=True)
            history = client.call("/api/conversations/" + conversation)
            answers = [m for m in history["messages"] if m.get("task_id") == row["id"] and m.get("task_status")]
            if answers:
                row = task_queue.tasks(root)[entry["task_id"]]
                assert len(answers) == 1 and row["status"] == "succeeded", "Task failed or duplicate answer"
                answer = answers[0]
                assert row["worker"] == answer["provider"] == worker, "Unexpected worker substitution"
                assert row["result"] in answer["content"] and row["id"] in answer["content"]
                assert Path("/tmp/wb-proof.txt").read_text().rstrip("\n") == "hello"
                events = [json.loads(line) for line in (root / "conductor/state/queue.jsonl").read_text().splitlines()]
                events = [r for r in events if r["id"] == row["id"]]
                assert {"enqueued", "claimed", "running", "succeeded"} <= {r["event"] for r in events}
                elapsed = answer["created_at"] - entry["submitted_at"]
                assert elapsed < 120
                entry.update(verified=True, elapsed_seconds=elapsed, answer=answer["content"], message_id=answer["id"],
                             claimed_at=row["claimed_at"], started_at=row["started_at"], finished_at=row["finished_at"],
                             answered_at=answer["created_at"], events=[{k:r.get(k) for k in ("event", "updated_at", "worker")} for r in events],
                             file_sha256=hashlib.sha256(Path("/tmp/wb-proof.txt").read_bytes()).hexdigest())
                save()
                print("Answered", worker, row["id"], round(elapsed, 3), "seconds", flush=True)
                break
            time.sleep(1)
        else:
            raise RuntimeError("Two-minute proof deadline exceeded for " + worker)
    for provider in ("gemini", "minimax"):
        conversation = client.call("/api/conversations", {})["id"]
        request_id = str(uuid.uuid4())
        client.call("/api/messages", dict(conversation_id=conversation, request_id=request_id, provider=provider,
                    message="Who is answering this reply, and are Gemini and MiniMax healthy right now?"))
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            answer = client.call("/api/conversations/" + conversation)["messages"][-1]
            if answer["status"] == "done":
                assert answer["provider"] == provider
                assert "Answering provider: " + provider in answer["content"]
                assert "gemini=ready" in answer["content"] and "minimax=ready" in answer["content"]
                data["health"].append(dict(conversation_id=conversation, request_id=request_id, provider=provider,
                                           answer=answer["content"], at=time.time()))
                save()
                print("Health and actual answering provider verified:", provider, flush=True)
                break
            time.sleep(1)
        else:
            raise RuntimeError("Provider health proof deadline exceeded")


if __name__ == "__main__":
    main()
