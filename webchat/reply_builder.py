"""Offline reply construction through the same server paths as interactive chat."""
from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import patch

from app import Chat
from task_dispatch import task_queue

from test_worker_activity import PS, SCREENS


@dataclass
class ReplyOutcome:
    prompt: str
    content: str
    provider: str | None
    task_ids: list[str] = field(default_factory=list)
    action_card: dict[str, Any] | None = None
    jobs_created: int = 0
    action_queued: bool = False
    meta: dict[str, Any] = field(default_factory=dict)

    def as_meta(self) -> dict[str, Any]:
        return dict(
            task_ids=self.task_ids,
            jobs_created=self.jobs_created,
            action_queued=self.action_queued,
            provider=self.provider,
            **self.meta,
        )


class StubProviders:
    def __init__(self, content: str = "Stub model answer with a concrete fact: lane board is synced."):
        self.content = content
        self.calls = 0

    def health(self, conversation_id=None):
        return dict(providers={}, order=[], fast_order=[])

    def reply(self, conversation, cancel, progress):
        self.calls += 1
        progress("gemini", [])
        return dict(content=self.content, provider="gemini", attempts=[])


def _seed_eval_root(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "conductor").mkdir(exist_ok=True)
    lanes = {lane: dict(state="ready", active=0) for lane in task_queue.WORKERS}
    (root / "conductor/lanes.json").write_text(json.dumps(lanes))
    (root / "logs").mkdir(exist_ok=True)
    (root / "conductor/plan-usage.json").write_text(json.dumps({
        "codex": {"used_percent": 40, "reset_at": 1790563200},
        "claude": {"used_percent": 88, "reset_at": 1790551200},
    }))


def build_reply(
    prompt: str,
    *,
    code_root: Path,
    fixture: str | None = None,
    stub_model: str | None = None,
    conversation_id: str | None = None,
) -> ReplyOutcome:
    """Run one user turn through Chat.submit without live models."""
    eval_root = code_root / ".reply-eval-runtime"
    _seed_eval_root(eval_root)
    webchat_dir = code_root / "webchat"
    if not webchat_dir.is_dir():
        webchat_dir = code_root / "conductor/webchat"
    stub = StubProviders(stub_model or "Here is a direct answer: WebJam draft #161 is still open.")
    chat = Chat(webchat_dir, eval_root, stub)
    identifier = conversation_id or chat.conversation_list()["conversations"][0]["id"]
    before = len(task_queue.tasks(eval_root))

    patches = []
    if fixture == "busy_workers":
        patches.append(patch("live_status_snapshot._screen_sessions", return_value=SCREENS))
        from worker_activity import parse_processes

        patches.append(patch("live_status_snapshot.process_table", return_value=parse_processes(PS)))
    else:
        patches.append(patch("live_status_snapshot._screen_sessions", return_value={}))
        patches.append(patch("live_status_snapshot.process_table", return_value={}))

    for item in patches:
        item.start()
    try:
        request_id = str(uuid.uuid4())
        chat.submit(identifier, prompt, request_id)
        info = chat.workers.get(identifier)
        if info:
            info["thread"].join(30)
        value = chat.history(identifier)
        answer = next(
            (m for m in value["messages"] if m["role"] == "assistant" and m.get("request_id") == request_id),
            value["messages"][-1],
        )
        after = len(task_queue.tasks(eval_root))
        task_ids = answer.get("task_ids") or (
            [answer["task_id"]] if answer.get("task_id") else []
        )
        card = answer.get("action_card")
        return ReplyOutcome(
            prompt=prompt,
            content=answer.get("content") or "",
            provider=answer.get("provider"),
            task_ids=[tid for tid in task_ids if tid],
            action_card=card,
            jobs_created=max(0, after - before),
            action_queued=bool(card and card.get("state") in ("queued", "confirm")),
        )
    finally:
        for item in reversed(patches):
            item.stop()
        chat.close()


def wait_for_reply(chat: Chat, identifier: str, request_id: str, timeout: float = 30) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = chat.history(identifier)
        answer = next(
            (m for m in value["messages"] if m.get("request_id") == request_id and m["role"] == "assistant"),
            None,
        )
        if answer and answer.get("status") == "done":
            return answer
        if identifier not in chat.workers:
            break
        time.sleep(0.05)
    raise TimeoutError("reply did not complete")
