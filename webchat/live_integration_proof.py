#!/usr/bin/env python3
"""Real authenticated five-provider proof; credentials remain only in memory."""
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
from datetime import datetime, timezone
from pathlib import Path

from live_status_snapshot import build_live_status_snapshot
from providers import Redactor

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "state"))
import task_queue

PROVIDERS = ("minimax", "gemini", "codex", "claude", "cursor")
QUESTION = "what are the workers doing right now"


def stamp(value=None):
    return datetime.fromtimestamp(time.time() if value is None else value, timezone.utc).isoformat(timespec="milliseconds")


class Proof:
    def __init__(self, root, url):
        self.root, self.url = root, url
        self.path = root / "conductor/state/webbob-integration-proof-0927.json"
        self.data = json.loads(self.path.read_text()) if self.path.exists() else {"providers": [], "verifications": []}
        password = (root / "conductor/webchat/.password").read_text().strip()
        self.redact = Redactor(root, password)
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        request = urllib.request.Request(url + "/login", data=urllib.parse.urlencode({"password": password}).encode(), headers={"Origin": url})
        with self.opener.open(request, timeout=15) as response:
            response.read()
        self.csrf = self.call("/api/session")["csrf"]

    def call(self, path, data=None):
        headers = {"Origin": self.url}
        if data is not None:
            headers.update({"Content-Type": "application/json", "X-CSRF-Token": self.csrf})
        request = urllib.request.Request(self.url + path, data=json.dumps(data).encode() if data is not None else None, headers=headers)
        with self.opener.open(request, timeout=20) as response:
            return json.load(response)

    def save(self):
        temporary = self.path.with_suffix(".tmp")
        with open(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as handle:
            handle.write(self.redact(json.dumps(self.data, indent=2)) + "\n")
        temporary.replace(self.path)

    def history(self, entry):
        return self.call("/api/conversations/" + entry["conversation_id"])

    def status(self, entry, question=QUESTION):
        before = build_live_status_snapshot(self.root)
        request_id = str(uuid.uuid4())
        case = dict(request_id=request_id, question=question, submitted_at=stamp(), before=before)
        entry.setdefault("status_turns", []).append(case)
        self.save()
        self.call("/api/messages", dict(conversation_id=entry["conversation_id"], message=question,
                                       request_id=request_id, provider=entry["provider"]))
        print(stamp(), "Status submitted", entry["provider"], request_id, flush=True)
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            history = self.history(entry)
            answer = next(m for m in history["messages"] if m.get("request_id") == request_id and m["role"] == "assistant")
            if answer["status"] in ("done", "error", "cancelled"):
                after = build_live_status_snapshot(self.root)
                jobs = {row["job_id"] for snap in (before, after) for rows in snap["queue_jobs"].values() for row in rows}
                screens = {row["screen"] for snap in (before, after) for row in snap["screen_lanes"]}
                case.update(after=after, completed_at=stamp(), message_id=answer["id"], answer=answer["content"],
                            actual_provider=answer.get("provider"), attempts=answer.get("attempts", []),
                            cited_jobs=sorted(job for job in jobs if job in answer["content"]),
                            cited_screens=sorted(screen for screen in screens if screen in answer["content"]),
                            cited_lanes=[lane for lane in PROVIDERS if lane in answer["content"].lower()])
                self.save()
                assert answer["status"] == "done" and answer["provider"] == entry["provider"], "Requested provider did not answer"
                print(stamp(), "Status answered", entry["provider"], "jobs", len(case["cited_jobs"]),
                      "screens", len(case["cited_screens"]), "lanes", len(case["cited_lanes"]), flush=True)
                return case
            time.sleep(2)
        case["error"] = "Status deadline expired"
        self.save()
        raise RuntimeError(case["error"])

    def task(self, entry):
        if entry["provider"] in ("codex", "cursor"):
            prompt = ("Review webchat/live_status_snapshot.py in your assigned checkout. Read the file and report "
                      "the three queue journal paths it reads, how succeeded tasks and harvested result jobs are "
                      "classified, and how prompt encoding avoids cutting JSON. Cite at least two line numbers. "
                      "Do not modify files. Return a concrete review under 180 words.")
        else:
            prompt = ("Review this actual Web Bob dispatch timing measurement from task "
                      "webchat-c96d2c7fba4452dc8ad2cbb5fc65e875 on 2026-09-27 UTC: queued 15:26:31.279, "
                      "claimed 15:26:32.215, execution started 15:26:32.324, finished 15:26:49.414, "
                      "chat answer saved 15:26:49.507. Calculate queue wait, execution time, delivery delay, "
                      "and end-to-end time in seconds to three decimals. Identify which stage dominates. "
                      "Return a compact table and one conclusion under 140 words.")
        case = entry.get("task")
        if not case:
            case = dict(request=prompt, request_id=str(uuid.uuid4()), submitted_at=stamp())
            entry["task"] = case
            self.save()
        if not case.get("task_id"):
            accepted = self.call("/api/messages", dict(conversation_id=entry["conversation_id"], message=case["request"],
                                                       request_id=case["request_id"], provider=entry["provider"], worker=entry["provider"]))
            case["task_id"] = accepted["messages"][-1].get("task_id")
            self.save()
        assert case["task_id"], "Chat did not return a durable task ID"
        print(stamp(), "Task queued", entry["provider"], case["task_id"], flush=True)
        deadline, seen = time.monotonic() + 600, None
        while time.monotonic() < deadline:
            row = task_queue.tasks(self.root)[case["task_id"]]
            state = (row["status"], row["attempts"])
            if state != seen:
                print(stamp(), entry["provider"], state, flush=True)
                seen = state
            results = [m for m in self.history(entry)["messages"] if m.get("task_id") == row["id"] and m.get("task_status")]
            if results:
                assert len(results) == 1, "Duplicate terminal answer"
                # Delivery can finish between the journal read and HTTP poll.
                # Refresh the durable record before using terminal timestamps.
                row = task_queue.tasks(self.root)[case["task_id"]]
                answer = results[0]
                case.update(status=row["status"], actual_worker=row["worker"], attempts=row["attempts"],
                            queued_at=stamp(row["created_at"]), claimed_at=stamp(row["claimed_at"]),
                            started_at=stamp(row["started_at"]), finished_at=stamp(row["finished_at"]),
                            chat_at=stamp(answer["created_at"]), answer=answer["content"],
                            result_message_id=answer["id"], result_sha256=row.get("result_sha256"))
                case["journal_events"] = [dict(event=event["event"], status=event["status"], at=stamp(event["updated_at"]))
                    for line in (self.root / "conductor/state/queue.jsonl").read_text().splitlines()
                    if (event := json.loads(line)).get("id") == row["id"]]
                self.save()
                assert row["status"] == "succeeded", "Task failed; see saved chat answer"
                assert row["worker"] == answer["provider"] == entry["provider"]
                assert row["result"] in answer["content"]
                assert hashlib.sha256(row["result"].encode()).hexdigest() == row["result_sha256"]
                assert {"claimed", "running", "succeeded"} <= {event["event"] for event in case["journal_events"]}
                print(stamp(), "Task answered in chat", entry["provider"], case["task_id"], flush=True)
                return case
            time.sleep(2)
        raise RuntimeError("Task deadline expired; inspect durable queue")

    def run(self, provider):
        entry = dict(provider=provider, conversation_id=self.call("/api/conversations", {})["id"], started_at=stamp())
        self.data["providers"].append(entry)
        self.save()
        status = self.status(entry)
        if not (status["cited_jobs"] and status["cited_screens"] and status["cited_lanes"]):
            status = self.status(entry, "Which specific worker lanes, screen names, and full job IDs support that status? "
                                 "Use the current live_status_snapshot. If nothing is claimed, label recent finished jobs as history.")
        assert status["cited_jobs"] and status["cited_screens"] and status["cited_lanes"], "Status needs real lane, screen and job citations"
        self.task(entry)
        entry["completed_at"] = stamp()
        self.save()

    def resume(self, provider):
        entry = next((e for e in reversed(self.data["providers"]) if e["provider"] == provider), None)
        if entry and entry.get("completed_at"):
            print("Already completed", provider, flush=True)
        elif entry and entry.get("task"):
            self.task(entry)
            entry["completed_at"] = stamp()
            self.save()
        else:
            self.run(provider)

    def verify(self):
        for entry in self.data["providers"]:
            history = self.history(entry)
            for turn in entry.get("status_turns", []):
                matches = [m for m in history["messages"] if m["id"] == turn["message_id"]]
                assert len(matches) == 1 and matches[0]["content"] == turn["answer"]
                assert matches[0]["provider"] == entry["provider"]
            case = entry["task"]
            matches = [m for m in history["messages"] if m.get("task_id") == case["task_id"] and m.get("task_status")]
            assert len(matches) == 1 and matches[0]["content"] == case["answer"]
            assert matches[0]["id"] == case["result_message_id"]
            print("Verified saved status and task answer", entry["provider"], flush=True)
        self.data["verifications"].append(dict(at=stamp(), providers=len(self.data["providers"]), result="all saved answers present exactly once"))
        self.save()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("run", "resume", "verify"))
    parser.add_argument("--provider", choices=PROVIDERS)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--url", default="http://127.0.0.1:8787")
    args = parser.parse_args()
    proof = Proof(args.root.resolve(), args.url)
    if args.mode == "verify":
        proof.verify()
    else:
        for provider in (args.provider,) if args.provider else PROVIDERS:
            (proof.resume if args.mode == "resume" else proof.run)(provider)


if __name__ == "__main__":
    main()
