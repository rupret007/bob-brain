#!/usr/bin/env python3
"""Authenticated, isolated proof of project dispatch and durable permissions.

No model or worker process is launched. Deliberately stale provider responses
exercise the final reply guard; all dispatch and persistence are real server code.
"""
import argparse
import hashlib
import http.cookiejar
import json
import tempfile
import threading
import time
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app import Chat, Server, private_write
from live_clean_proof import live_listener, service_screens
from task_dispatch import task_queue

CODE_ROOT = Path(__file__).resolve().parents[1]
PROJECTS = ["Web Bob", "WebJam", "AdoptIQ", "StoryBoard"]
HOLD = ("Hold off on any coding jobs or service restarts for Web Bob. Bob has Codex fixing job pickup right now, "
        "and two fixes at once will clash. You can keep answering questions and reporting status, "
        "but don't queue, start, or restart anything for Web Bob until I say go.")
PRIORITY = "Ok prioritize making Web Bob better, then WebJam, then AdoptIQ, then Storyboard."
PUSH = "Now push everything to the max and fix anything you find along the way."


class StaleReplyFixture:
    def __init__(self):
        self.calls = 0
        self.content = ("Your earlier hold on Web Bob code and service restarts still applies. "
                        "I need your permission before continuing.")

    def health(self, conversation_id=None):
        return dict(providers={}, order=[], fast_order=[])

    def reply(self, conversation, cancel, progress):
        self.calls += 1
        progress("gemini", [])
        return dict(provider="gemini", attempts=[], content=self.content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(tempfile.mkdtemp(prefix="webbob-intent-proof-"))
    fixture = StaleReplyFixture()
    chat = Chat(root / "conductor/webchat", root, fixture)
    (root / "conductor/lanes.json").write_text(json.dumps({lane: dict(state="ready", active=0) for lane in task_queue.WORKERS}))
    server = Server(("127.0.0.1", 0), chat)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = "http://127.0.0.1:" + str(server.server_address[1])
    receipt = dict(root=str(root), url=url, started_at=datetime.now(timezone.utc).isoformat(),
                   live_listener_before=live_listener(), service_screens_before=service_screens(),
                   provider_fixture="Synthetic stale hold replies; no external model calls or worker execution.",
                   lane_fixture="All workers ready for the incident; Codex busy and Cursor ready for the inline push.",
                   provider_fixture_inputs=[],
                   examples=[], reloads=0, retransmissions=0,
                   source_sha256={name: hashlib.sha256((CODE_ROOT / name).read_bytes()).hexdigest() for name in (
                       "webchat/app.py", "webchat/chat_intent.py", "webchat/providers.py", "webchat/reply_authority.py",
                       "webchat/task_dispatch.py", "state/task_queue.py", "webchat/isolated_intent_proof.py",
                       "webchat/test_chat_intent.py", "webchat/test_reply_authority.py")})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    csrf = None

    def call(route, payload=None):
        headers = {"Origin": url}
        if payload is not None:
            headers.update({"Content-Type": "application/json", "X-CSRF-Token": csrf})
        request = urllib.request.Request(url + route, data=json.dumps(payload).encode() if payload is not None else None, headers=headers)
        with opener.open(request, timeout=10) as response:
            return json.load(response)

    def login():
        nonlocal csrf
        request = urllib.request.Request(url + "/login", data=urllib.parse.urlencode({"password": chat.password}).encode(), headers={"Origin": url})
        with opener.open(request, timeout=10) as response:
            response.read()
        csrf = call("/api/session")["csrf"]

    def submit(text, request_id=None):
        request_id = request_id or str(uuid.uuid4())
        value = call("/api/messages", dict(conversation_id=identifier, message=text, request_id=request_id))
        deadline = time.monotonic() + 5
        while True:
            answer = next(message for message in value["messages"] if message["role"] == "assistant" and message.get("request_id") == request_id)
            if answer["status"] == "done":
                break
            assert time.monotonic() < deadline, answer
            time.sleep(.01)
            value = call("/api/conversations/" + identifier)
        receipt["examples"].append(dict(conversation_id=identifier, message=text, request_id=request_id, reply=answer["content"],
                                         task_ids=answer.get("task_ids", [answer["task_id"]] if answer.get("task_id") else []),
                                         intent_state=value["intent_state"]))
        print(answer["content"], flush=True)
        return answer

    def reload_chat():
        nonlocal chat
        chat.close()
        chat = Chat(root / "conductor/webchat", root, fixture)
        server.chat = chat
        receipt["reloads"] += 1
        login()

    try:
        login()
        identifier = call("/api/conversations", {})["id"]
        receipt["conversation_id"] = identifier
        submit(HOLD)
        submit(PRIORITY)
        assert not task_queue.tasks(root)
        reload_chat()
        request_id = str(uuid.uuid4())
        answer = submit(PUSH, request_id)
        rows = list(task_queue.tasks(root).values())
        assert [row["title"] for row in rows] == PROJECTS
        assert [row["requested_worker"] for row in rows] == ["codex", "cursor", "codex", "cursor"]
        assert set(answer["task_ids"]) == {row["id"] for row in rows}
        assert all(row["status"] == "queued" and row["worker"] is None and row["attempts"] == 0 for row in rows)
        assert all(row["title"] in answer["content"] and row["id"] in answer["content"] for row in rows)
        assert "hold" not in answer["content"].lower()
        receipt["project_rows"] = rows
        submit(PUSH, request_id)
        receipt["retransmissions"] += 1
        reload_chat()
        submit(PUSH, request_id)
        receipt["retransmissions"] += 1
        assert len(task_queue.tasks(root)) == 4
        assert not call("/api/conversations/" + identifier)["intent_state"]["holds"]
        submit("go")
        assert len(task_queue.tasks(root)) == 4
        assert fixture.calls == 0
        for content in (fixture.content, "Web Bob is paused until you say resume.",
                        "I am holding Web Bob pending your approval."):
            fixture.content = content
            receipt["provider_fixture_inputs"].append(content)
            stale = submit("Any concerns?")
            assert stale["content"] == "Ready when you are."
        assert fixture.calls == 3
        submit("Hold off on Web Bob.")
        blocked = submit("Fix Web Bob login")
        assert "On hold: Web Bob" in blocked["content"] and len(task_queue.tasks(root)) == 4
        reload_chat()
        request_id = str(uuid.uuid4())
        resumed = submit("resume", request_id)
        assert resumed.get("task_id") and "hold" not in resumed["content"].lower()
        submit("resume", request_id)
        receipt["retransmissions"] += 1
        reload_chat()
        assert not call("/api/conversations/" + identifier)["intent_state"]["holds"]
        assert len(task_queue.tasks(root)) == 5

        # Missing/excluded targets ask for clarification without granting permission.
        identifier = call("/api/conversations", {})["id"]
        submit(HOLD)
        before = call("/api/conversations/" + identifier)["intent_state"]
        assert submit(PUSH)["content"] == "Which projects should I work on?"
        reload_chat()
        assert call("/api/conversations/" + identifier)["intent_state"] == before
        assert submit("go")["content"] == "Ready when you are."
        reload_chat()
        assert not call("/api/conversations/" + identifier)["intent_state"]["holds"]
        assert len(task_queue.tasks(root)) == 5
        submit(HOLD)
        submit("Prioritize Web Bob")
        before = call("/api/conversations/" + identifier)["intent_state"]
        assert submit("Push everything to the max except Web Bob")["content"] == "Which projects should I work on?"
        reload_chat()
        assert call("/api/conversations/" + identifier)["intent_state"] == before
        assert len(task_queue.tasks(root)) == 5

        # Inline projects use only the free compatible worker in this lane fixture.
        identifier = call("/api/conversations", {})["id"]
        (root / "conductor/lanes.json").write_text(json.dumps({
            "codex": dict(state="busy", active=1), "cursor": dict(state="ready", active=0)}))
        submit(HOLD)
        inline = "Push everything to the max: Web Bob, WebJam, AdoptIQ, StoryBoard."
        request_id = str(uuid.uuid4())
        answer = submit(inline, request_id)
        rows = [task_queue.tasks(root)[job] for job in answer["task_ids"]]
        assert [row["title"] for row in rows] == PROJECTS
        assert {row["requested_worker"] for row in rows} == {"cursor"}
        assert len(answer["content"].splitlines()) == 4
        assert all(row["title"] in answer["content"] and row["id"] in answer["content"] for row in rows)
        assert not call("/api/conversations/" + identifier)["intent_state"]["holds"]
        receipt["busy_lane_project_rows"] = rows
        reload_chat()
        assert submit(inline, request_id)["task_ids"] == answer["task_ids"]
        receipt["retransmissions"] += 1
        submit("go")
        assert len(task_queue.tasks(root)) == 9
        assert fixture.calls == 3

        # A named go accepts the saved project plan and cannot replay it later.
        identifier = call("/api/conversations", {})["id"]
        submit(HOLD)
        submit(PRIORITY)
        reload_chat()
        named_go = "Go ahead with Web Bob, WebJam, AdoptIQ and StoryBoard."
        request_id = str(uuid.uuid4())
        answer = submit(named_go, request_id)
        rows = [task_queue.tasks(root)[job] for job in answer["task_ids"]]
        assert [row["title"] for row in rows] == PROJECTS
        assert not call("/api/conversations/" + identifier)["intent_state"]["holds"]
        receipt["named_go_project_rows"] = rows
        reload_chat()
        assert submit(named_go, request_id)["task_ids"] == answer["task_ids"]
        receipt["retransmissions"] += 1
        assert not submit(named_go).get("task_ids")
        assert len(task_queue.tasks(root)) == 13
        assert fixture.calls == 3
        api_rows = call("/api/jobs")["dispatch"]
        assert {row["id"] for row in api_rows} == set(task_queue.tasks(root))
        receipt["queue_api_rows"] = api_rows
        journal = root / "conductor/state/queue.jsonl"
        receipt["queue_events"] = [json.loads(line) for line in journal.read_text().splitlines()]
        assert len(receipt["queue_events"]) == 13
        assert all(row["event"] == "enqueued" and row["status"] == "queued" and row["worker"] is None
                   and row["attempts"] == 0 for row in receipt["queue_events"])
        receipt["queue_sha256"] = hashlib.sha256(journal.read_bytes()).hexdigest()
        receipt["provider_fixture_calls"] = fixture.calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
        chat.close()
        receipt["live_listener_after"] = live_listener()
        receipt["service_screens_after"] = service_screens()
        receipt["finished_at"] = datetime.now(timezone.utc).isoformat()
        receipt["result"] = "INCOMPLETE"
        payload = chat.redact(json.dumps(receipt, ensure_ascii=False, indent=2)) + "\n"
        private_write(root / "proof.json", payload)
        private_write(args.output, payload)
    assert receipt["live_listener_before"] == receipt["live_listener_after"]
    assert receipt["service_screens_before"] == receipt["service_screens_after"]
    receipt["result"] = "PASS"
    payload = chat.redact(json.dumps(receipt, ensure_ascii=False, indent=2)) + "\n"
    private_write(root / "proof.json", payload)
    private_write(args.output, payload)
    print("PASS — evidence: " + str(args.output), flush=True)


if __name__ == "__main__":
    main()
