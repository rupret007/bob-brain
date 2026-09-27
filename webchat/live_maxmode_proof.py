#!/usr/bin/env python3
"""One authenticated max request, timestamped API overlap and durable answer proof.

Credentials and cookies stay in memory. Raw receipts stay in ignored runtime
state. No forced delays, provider failures, quota resets, or fake model calls.
"""
import argparse
import hashlib
import http.cookiejar
import json
import time
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

MODELS = {"codex", "claude", "cursor", "gemini", "minimax"}
URL = "http://127.0.0.1:8787"
PROMPT = """Max mode: Review Web Bob's new parallel task dispatcher. Produce one combined answer covering independent implementation, testing, design, capacity, and failure analyses, with actual local test evidence. Work read-only; do not edit files, push, or open PRs.

Shared evidence: A request saves a durable dispatch intent, expands into independent queue rows with a shared group_id and expected group_size, and starts nothing until every group row exists. Each claim has a unique token and a 90-second renewable lease. CLI capacity is 1 each; Gemini and MiniMax capacity is 3 each. A provider error records the failed worker and retries an untried compatible worker; coding stays on Codex/Cursor. Budgets include outstanding worst-case reservations; tiers warn at 70%, reduce API concurrency at 85%, and refuse new reservations crossing 95%. Queue results are saved before the single deterministic group answer is saved; delivery acknowledgements follow that chat write. Mini runs a named local test suite without a model call. Analysis outputs and local commits from code packages remain attributable to their worker.

[codex] Read state/task_queue.py and services/web_dispatch.py in the assigned checkout. Audit atomic claims, partial group enqueue recovery, retries, capacity and routing. Cite specific code locations, trace two concrete races, and list the three highest-priority correctness risks. Use 500-700 words and distinguish proven facts from recommendations.
[cursor] Read webchat/task_dispatch.py, webchat/max_mode.py and webchat/test_dispatch.py in the assigned checkout. Audit the group result outbox, duplicate request handling and restart delivery. Cite code locations and propose a concrete regression matrix with at least eight crash/failure cases. Use 500-700 words; do not modify anything.
[claude] Using only the shared evidence, independently critique the design assumptions, separation of responsibilities and acceptance criteria. Evaluate five invariants and specify an observable falsification test for each. Rank the three most consequential risks. Use a focused 400-500 word critique and clearly label unknown implementation details.
[gemini] Using only the shared evidence, calculate maximum concurrency and a capacity model. Assume mean CLI durations Codex 50s, Cursor 40s, Claude 20s; API durations Gemini 12s, MiniMax 30s; Mini tests 5s. Compute per-lane and aggregate hourly throughput at normal capacity and at the 85% API throttle, explain why this is only an upper bound, and analyze five scheduling/starvation scenarios. Give formulas, tables and a detailed 600-800 word analysis.
[minimax] Using only the shared evidence, build a failure/recovery matrix of at least twelve cases spanning lost claims, crashed workers, timed-out provider calls, cap exhaustion, partial enqueue, stale tokens, chat save failure and lost delivery acknowledgements. For each give expected durable state, next action and evidence needed. Finish with the three most useful operational alerts. Use 600-800 words; do not invent observations.
[mini] Run services/test_services.py on the local CPU and return its real test output.
"""


def stamp(value=None):
    return datetime.fromtimestamp(time.time() if value is None else value, timezone.utc).isoformat(timespec="milliseconds")


class Client:
    def __init__(self, root):
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        body = urllib.parse.urlencode({"password": (root / "conductor/webchat/.password").read_text().strip()}).encode()
        with self.opener.open(urllib.request.Request(URL + "/login", data=body, headers={"Origin": URL}), timeout=15) as response:
            response.read()
        self.csrf = self.call("/api/session")["csrf"]

    def call(self, path, data=None):
        headers = {"Origin": URL}
        if data is not None:
            headers.update({"Content-Type": "application/json", "X-CSRF-Token": self.csrf})
        request = urllib.request.Request(URL + path, data=json.dumps(data).encode() if data is not None else None, headers=headers)
        with self.opener.open(request, timeout=20) as response:
            return json.load(response)


def save(path, data):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n")
    temporary.chmod(0o600)
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("run", "resume", "verify"))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--receipt", type=Path, help="Select a preserved private receipt without replacing the current run")
    args = parser.parse_args()
    path = args.receipt or args.root / "conductor/state/webbob-maxmode-proof-0927.json"
    client = Client(args.root)
    if args.mode == "run":
        if path.exists():
            raise RuntimeError("A proof receipt already exists; use resume or verify")
        conversation = client.call("/api/conversations", {})["id"]
        request = str(uuid.uuid4())
        value = client.call("/api/messages", dict(conversation_id=conversation, request_id=request, message=PROMPT))
        receipt = value["messages"][-1]
        if not receipt.get("group_id"):
            raise RuntimeError("Chat did not accept a max-mode group: " + receipt.get("content", ""))
        data = dict(conversation_id=conversation, request_id=request, group_id=receipt["group_id"],
                    task_ids=receipt["task_ids"], submitted_at=stamp(), prompt=PROMPT, snapshots=[])
        save(path, data)
        print("Accepted one request", data["group_id"], "subtasks", len(data["task_ids"]), data["submitted_at"], flush=True)
    else:
        data = json.loads(path.read_text())
    deadline = time.monotonic() + (20 if args.mode == "verify" else 600)
    seen = None
    while time.monotonic() < deadline:
        jobs = client.call("/api/jobs")
        rows = [row for row in jobs["dispatch"] if row.get("group_id") == data["group_id"]]
        snapshot = dict(at=stamp(), read_at=jobs["read_at"], rows=rows)
        running = {row["worker"] for row in rows if row["status"] == "running" and row.get("execution_started_at")}
        state = [(row["worker"] or row["requested_worker"], row["status"], row["attempts"]) for row in rows]
        if state != seen or (MODELS <= running and not data.get("all_five_running")):
            data["snapshots"].append(snapshot)
            seen = state
            print(snapshot["at"], state, flush=True)
        if MODELS <= running and not data.get("all_five_running"):
            data["all_five_running"] = snapshot
            print("ALL FIVE EXECUTING", snapshot["at"], flush=True)
        history = client.call("/api/conversations/" + data["conversation_id"])
        results = [m for m in history["messages"] if m.get("group_id") == data["group_id"] and m.get("task_status")]
        save(path, data)
        if results:
            assert len(results) == 1, "Expected exactly one group answer"
            result = results[0]
            rows = [row for row in client.call("/api/jobs")["dispatch"] if row.get("group_id") == data["group_id"]]
            data.update(answer=result, rows=rows, verified_at=stamp(), answer_sha256=hashlib.sha256(result["content"].encode()).hexdigest())
            model_rows = [row for row in rows if row["worker"] in MODELS]
            assert len(model_rows) == 5 and {r["worker"] for r in model_rows} == MODELS, "Every original model lane must complete"
            begin = max(row["execution_started_at"] for row in model_rows)
            end = min(row["finished_at"] for row in model_rows)
            data["overlap"] = dict(start=stamp(begin), end=stamp(end), seconds=round(end - begin, 3))
            save(path, data)
            assert result["task_status"] == "succeeded", "Group has a failed subtask"
            assert data.get("all_five_running") and end > begin, "No proven overlap of all five model calls"
            assert all(row["delivered_at"] for row in rows), "Delivery acknowledgements are still pending"
            print("Verified one saved answer", result["id"], "overlap_seconds", data["overlap"]["seconds"], "sha256", data["answer_sha256"], flush=True)
            return
        time.sleep(.5)
    raise RuntimeError("Group proof is pending; run resume after inspecting runtime state")


if __name__ == "__main__":
    main()
