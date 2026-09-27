#!/usr/bin/env python3
"""Private, single-owner Bob web chat. Python standard library only."""
from __future__ import annotations

import base64
import copy
import fcntl
import hashlib
import hmac
import json
import mimetypes
import os
import re
import secrets
import shlex
import signal
import stat
import subprocess
import sys
import threading
import time
import uuid
from collections import deque
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from providers import Cancelled, ProviderError, Providers, Redactor, UUID, clean_env, run
from failover import AllDown
from handback import append_turn, public_digest
from job_queue import (
    council_job_description,
    parse_council,
    parse_council_cancel,
    parse_council_confirm_proposal,
    parse_job_confirm,
    parse_do_more,
    parse_start,
)
from actions import queue_once
from music_notebook import get_project, list_projects, save_project, try_music_coach_reply
from reply_guard import repair_hollow_progress
from drill_fixture import try_bob_state_running_line
from music_demo import demo_receipt, generate_demo, music_budget_status, resolve_audio, store_upload
from ops_panel import conductor_snapshot, draft_head_sha, enrich_live_ops, load_live_ops, maybe_spawn_dashboard_refresh
from quiet_hours import in_quiet_hours
from task_dispatch import TaskDispatch, parse_work, task_queue

HERE = Path(os.environ.get("BOB_WEBCHAT_DIR", Path(__file__).resolve().parent)).resolve()
ROOT = Path(os.environ.get("BOB_ROOT", HERE.parent.parent)).resolve()
_STATE_LEDGER_DIR = ROOT / "conductor/state"
if str(_STATE_LEDGER_DIR) not in sys.path:
    sys.path.insert(0, str(_STATE_LEDGER_DIR))
import ledger as state_ledger  # noqa: E402
HOST, PORT = "127.0.0.1", 8787  # Deliberately no all-interface or port override.
COOKIE = "bob_session"
SESSION_SECONDS = 12 * 60 * 60
MAX_BODY = 32768
MAX_AUDIO_BODY = 35 * 1024 * 1024


def hard_rule_refusal(text):
    if re.search(r"\b(?:merge\s+(?:(?:pr|pull request)\s*)?#?\d+|undraft|force[ -]push|gh\s+pr\s+(?:merge|ready))\b", text, re.I):
        return "I can review the draft, but I won't merge, undraft, or force-push. Drafts only; no action was run."
    return None


class RequestError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


def private_write(path, value):
    temporary = path.with_name("." + path.name + "." + secrets.token_hex(6))
    try:
        with open(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        temporary.unlink(missing_ok=True)


def password_at(folder):
    path = folder / ".password"
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor) as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                raise RuntimeError("Password path must be a regular file")
            os.fchmod(handle.fileno(), 0o600)
            password = handle.read().strip()
        if len(password) < 24:
            raise RuntimeError("Password file must contain at least 24 characters")
        return password
    with os.fdopen(descriptor, "w") as handle:
        password = secrets.token_urlsafe(24)
        handle.write(password + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return password


class Chat(TaskDispatch):
    def __init__(self, folder=HERE, root=ROOT, providers=None):
        self.folder, self.root = folder, root
        folder.mkdir(parents=True, exist_ok=True)
        self.password = password_at(folder)
        self.redact = Redactor(root, self.password)
        self.state = folder / "sessions"
        self.state.mkdir(mode=0o700, exist_ok=True)
        self.state.chmod(0o700)
        try:
            state_ledger.purge_drill_open_asks(self.root)
        except OSError:
            pass
        self.lock = threading.RLock()
        self.sessions, self.conversations = {}, {}
        self.overlay_roots: dict[str, Path] = {}
        self.overlay_pins: dict[str, Path] = {}
        self.failures = deque()
        self.workers = {}
        self.closing, self.queue_thread = threading.Event(), None
        self.providers = providers or Providers(
            root, self.redact, overlay_roots=self.overlay_roots, overlay_pins=self.overlay_pins,
        )
        for path in self.state.glob("*.json"):
            if not UUID.fullmatch(path.stem):
                continue
            # Corrupt state fails startup visibly; never silently discard history.
            value = json.loads(path.read_text())
            if value.get("id") != path.stem or not isinstance(value.get("messages"), list):
                raise RuntimeError("Invalid conversation file: " + path.name)
            path.chmod(0o600)
            self.conversations[value["id"]] = value
            interrupted = False
            for message in value["messages"]:
                if message.get("status") in ("queued", "running"):
                    message.update(status="error", content="The server restarted before this reply finished. Send your message again to retry.")
                    interrupted = True
            if interrupted:
                value["codex_thread_id"] = None
                self.save(value)
        if not self.conversations:
            self.new_conversation()
        self.migrate_legacy_tasks()
        self.reconcile_tasks()

    def save(self, conversation):
        conversation["updated_at"] = time.time()
        private_write(self.state / (conversation["id"] + ".json"), json.dumps(conversation, ensure_ascii=False, indent=2) + "\n")

    def ledger_root(self, conversation_id: str | None = None) -> Path:
        if conversation_id:
            if conversation_id in self.overlay_pins:
                return self.overlay_pins[conversation_id]
            if conversation_id in self.overlay_roots:
                return self.overlay_roots[conversation_id]
        return self.root

    def bind_drill_overlay(self, conversation_id: str, fixture_id: str) -> dict:
        if os.environ.get("BOB_WEBCHAT_DRILLS") != "1":
            raise RequestError(403, "Drill overlay is disabled.")
        if not isinstance(fixture_id, str) or not re.fullmatch(r"[0-9a-f-]{36}", fixture_id):
            raise RequestError(400, "Invalid fixture id.")
        base = (HERE / "drill-fixtures").resolve()
        path = (base / fixture_id).resolve()
        if not str(path).startswith(str(base)) or not path.is_dir():
            raise RequestError(404, "Fixture not found.")
        self.get(conversation_id)
        with self.lock:
            self.overlay_roots[conversation_id] = path
        return {"ok": True, "fixture_id": fixture_id}

    def clear_drill_overlay(self, conversation_id: str) -> dict:
        with self.lock:
            self.overlay_roots.pop(conversation_id, None)
        return {"ok": True}

    def record_turn(self, conversation_id=None, **data):
        # The optional handback ledger cannot turn a completed provider reply or
        # a persisted action receipt into a failed/replayed request.
        ask = (data.get("ask") or "").strip()
        if self.ledger_root(conversation_id) == self.root and state_ledger._DRILL_NOISE_RE.search(ask):
            return
        try:
            append_turn(self.ledger_root(conversation_id), **data)
        except OSError:
            if hasattr(self.providers, "circuit"):
                try:
                    self.providers.circuit.log("handback_error", reason="handback write unavailable")
                except OSError:
                    pass

    def new_conversation(self):
        with self.lock:
            value = {"id": str(uuid.uuid4()), "title": "New conversation", "created_at": time.time(),
                     "messages": [], "codex_thread_id": None}
            self.save(value)
            self.conversations[value["id"]] = value
            return self.public(value)

    def public(self, value):
        return {k: copy.deepcopy(v) for k, v in value.items() if k not in ("codex_thread_id", "retry_prompt", "pending_job", "pending_job_id")}

    def get(self, identifier):
        if not isinstance(identifier, str) or not UUID.fullmatch(identifier) or identifier not in self.conversations:
            raise RequestError(404, "Conversation not found.")
        return self.conversations[identifier]

    def history(self, identifier):
        with self.lock:
            self.reconcile_tasks()
            return self.public(self.get(identifier))

    def worker_info(self, identifier):
        return self.workers.get(identifier)

    def reply_deadline(self):
        timeouts = getattr(self.providers, "timeouts", {})
        values = list(timeouts.values()) or [180]
        return sum(values[:4]) + 60

    def sweep_stuck(self):
        now = time.time()
        limit = self.reply_deadline()
        with self.lock:
            for identifier, info in list(self.workers.items()):
                if now - info["started_at"] <= limit:
                    continue
                info["cancel"].set()
                value = self.get(identifier)
                if value["messages"] and value["messages"][-1]["status"] in ("queued", "running"):
                    value["messages"][-1].update(status="error",
                        content="This reply timed out. Tap Stop if it is still running, then send again.")
                    value.pop("retry_prompt", None)
                    self.save(value)

    def conversation_list(self):
        with self.lock:
            return {"conversations": [{k: c[k] for k in ("id", "title", "updated_at")}
                                      for c in sorted(self.conversations.values(), key=lambda c: c["updated_at"], reverse=True)],
                    "active_conversation": next(iter(self.workers), None),
                    "active_conversations": list(self.workers)}

    def authenticate(self, cookie):
        try:
            parsed = SimpleCookie(cookie or "")
            token = parsed[COOKIE].value
        except (CookieError, KeyError, ValueError):
            return None
        digest = hashlib.sha256(token.encode()).hexdigest()
        with self.lock:
            session = self.sessions.get(digest)
            if session and session["expires"] > time.time():
                return session
            self.sessions.pop(digest, None)
        return None

    def login(self, password):
        with self.lock:
            now = time.time()
            while self.failures and self.failures[0] < now - 60:
                self.failures.popleft()
            if len(self.failures) >= 10:
                raise RequestError(429, "Too many login attempts. Wait one minute and try again.")
            if not isinstance(password, str) or not hmac.compare_digest(password.encode(), self.password.encode()):
                self.failures.append(now)
                raise RequestError(401, "That password did not match. Try again.")
            token = secrets.token_urlsafe(32)
            digest = hashlib.sha256(token.encode()).hexdigest()
            self.sessions = {k: v for k, v in self.sessions.items() if v["expires"] > now}
            if len(self.sessions) >= 64:
                self.sessions.pop(next(iter(self.sessions)))
            self.sessions[digest] = {"expires": now + SESSION_SECONDS, "csrf": secrets.token_urlsafe(32), "digest": digest}
            return token

    def submit(self, identifier, text, request_id, provider="auto", worker=None):
        if provider not in ("auto", "minimax", "gemini", "codex", "claude", "cursor"):
            raise RequestError(400, "Choose auto, minimax, gemini, codex, claude, or cursor.")
        if not isinstance(text, str) or not text.strip() or len(text) > 6000:
            raise RequestError(400, "Write a message between 1 and 6,000 characters.")
        if not isinstance(request_id, str) or not UUID.fullmatch(request_id):
            raise RequestError(400, "A valid request ID is required.")
        text = text.strip()
        try:
            text.encode("utf-8")
        except UnicodeError:
            raise RequestError(400, "The message contains invalid text.") from None
        if self.redact(text) != text:
            raise RequestError(400, "This message appears to contain a secret. Remove it before sending; it was not saved or sent to a model.")
        with self.lock:
            conversation = copy.deepcopy(self.get(identifier))
            for message in conversation["messages"]:
                if message.get("request_id") == request_id:
                    if (message["content"] != text or message.get("preferred_provider", "auto") != provider
                            or message.get("requested_worker") != worker):
                        raise RequestError(409, "That request ID was already used for a different message.")
                    return self.public(conversation)
            self.sweep_stuck()
            if identifier in self.workers:
                raise RequestError(409, "Bob is finishing another reply in this conversation. Stop it or wait, then try again.")
            if conversation["messages"] and conversation["messages"][-1]["status"] == "waiting":
                raise RequestError(409, "This conversation has a queued request. Stop it before sending another message.")
            conversation["preferred_provider"] = provider
            conversation["messages"] += [
                {"id": str(uuid.uuid4()), "request_id": request_id, "preferred_provider": provider, "role": "user", "content": text,
                 "status": "done", "created_at": time.time(), "requested_worker": worker},
                {"id": str(uuid.uuid4()), "request_id": request_id, "role": "assistant", "content": "", "status": "queued",
                 "provider": None, "attempts": [], "created_at": time.time()},
            ]
            if conversation["title"] == "New conversation":
                conversation["title"] = text[:65]
            work, route = parse_work(text)
            started = parse_start(text)
            if started or work or worker is not None:
                conversation.pop("pending_job", None)
                conversation.pop("pending_job_id", None)
                return self.submit_task(conversation, started or work or text, request_id, worker or route)
            pending = conversation.get("pending_job")
            pending_council = conversation.get("pending_council")
            council_confirm, council_proposal = parse_council_confirm_proposal(text)
            if council_confirm and pending_council:
                expected_council = conversation.get("pending_council_id")
                if council_proposal and (not expected_council or council_proposal != expected_council):
                    conversation["messages"][-1].update(
                        status="done",
                        content="That council button is stale. Use the latest card or ask again.",
                        action_card={
                            "id": request_id,
                            "proposal_id": council_proposal,
                            "state": "refused",
                            "executable": False,
                            "reason": "Stale council proposal",
                        },
                    )
                    self.save(conversation)
                    self.conversations[identifier] = conversation
                    return self.public(conversation)
                conversation.pop("pending_council", None)
                blocked = hard_rule_refusal(pending_council) or hard_rule_refusal(text)
                if blocked:
                    conversation["messages"][-1].update(status="done", content=blocked,
                        action_card={"id": request_id, "state": "refused", "executable": False, "reason": "Council blocked by standing rules"})
                    self.save(conversation)
                    self.conversations[identifier] = conversation
                    self.record_turn(ask=text, provider=None, jobs=[], files=[], commits=[], confirmations=[],
                                refusals=[blocked], open_items=[])
                    return self.public(conversation)
                action_id = conversation.pop("pending_council_id", None) or str(uuid.uuid5(uuid.NAMESPACE_URL, identifier + pending_council))
                description = council_job_description(pending_council)
                result = queue_once(self.root, action_id, description)
                if result["ok"]:
                    reply = (
                        f"Queued a **draft** council run on the mini (`{result['file']}`). "
                        "Gemini, MiniMax, and Claude will critique; transcript lands under `conductor/reviews/`."
                    )
                    conversation["messages"][-1].update(status="done", content=reply,
                        action_card={"id": request_id, "state": "queued", "executable": False, "reason": "Council queued (draft)", "queue_id": result.get("file")})
                else:
                    conversation["messages"][-1].update(status="done", content=result["error"],
                        action_card={"id": request_id, "state": "blocked", "executable": False, "reason": "Duplicate or blocked"})
                self.save(conversation)
                self.conversations[identifier] = conversation
                self.record_turn(ask=text, provider=None, jobs=[result.get("file", "")] if result.get("ok") else [],
                            files=[result.get("path", "")] if result.get("ok") else [], commits=[],
                            confirmations=[text[:200]] if result.get("ok") else [],
                            refusals=[result.get("error", "blocked")] if not result.get("ok") else [], open_items=[])
                return self.public(conversation)
            job_confirm, job_proposal = parse_job_confirm(text)
            if job_confirm and pending:
                expected_job = conversation.get("pending_job_id")
                if job_proposal and (not expected_job or job_proposal != expected_job):
                    conversation["messages"][-1].update(
                        status="done",
                        content="That approve button is stale. Use the latest card or ask again.",
                        action_card={
                            "id": request_id,
                            "proposal_id": job_proposal,
                            "state": "refused",
                            "executable": False,
                            "reason": "Stale job proposal",
                        },
                    )
                    self.save(conversation)
                    self.conversations[identifier] = conversation
                    return self.public(conversation)
                conversation.pop("pending_job", None)
                blocked = hard_rule_refusal(pending) or hard_rule_refusal(text)
                if blocked:
                    conversation["messages"][-1].update(status="done", content=blocked,
                        action_card={"id": request_id, "state": "refused", "executable": False, "reason": "Job blocked by standing rules"})
                    self.save(conversation)
                    self.conversations[identifier] = conversation
                    self.record_turn(ask=text, provider=None, jobs=[], files=[], commits=[], confirmations=[],
                                refusals=[blocked], open_items=[])
                    return self.public(conversation)
                action_id = conversation.pop("pending_job_id", None) or str(uuid.uuid5(uuid.NAMESPACE_URL, identifier + pending))
                return self.submit_task(conversation, pending, action_id)
            if pending and not job_confirm:
                conversation.pop("pending_job", None)
            if parse_council_cancel(text) and pending_council:
                conversation.pop("pending_council", None)
                conversation.pop("pending_council_id", None)
                conversation["messages"][-1].update(status="done", content="Council request cancelled.",
                    action_card={"id": request_id, "state": "cancelled", "executable": False, "reason": "Council dismissed"})
                self.save(conversation)
                self.conversations[identifier] = conversation
                return self.public(conversation)
            if pending_council and not council_confirm and not parse_council_cancel(text):
                conversation.pop("pending_council", None)
            council_text = parse_council(text)
            if council_text:
                if hard_rule_refusal(council_text):
                    refusal = hard_rule_refusal(council_text)
                    conversation["messages"][-1].update(status="done", content=refusal,
                        action_card={"id": request_id, "state": "refused", "executable": False, "reason": "Standing rule: drafts only"})
                    self.save(conversation)
                    self.conversations[identifier] = conversation
                    self.record_turn(ask=text, provider=None, jobs=[], files=[], commits=[], confirmations=[],
                                refusals=[refusal], open_items=[])
                    return self.public(conversation)
                conversation["pending_council"] = council_text
                conversation["pending_council_id"] = request_id
                conversation["messages"][-1].update(status="done",
                    content="I can queue a **draft** council critique on the mini (Gemini + MiniMax + Claude; no Grok). Reply `yes, run council` to confirm.",
                    action_card={"id": request_id, "proposal_id": request_id, "state": "confirm", "executable": True,
                                 "reason": "Council: " + council_text[:120]})
                self.save(conversation)
                self.conversations[identifier] = conversation
                return self.public(conversation)
            started = parse_start(text)
            do_more_goal = parse_do_more(text) if not started else None
            job_text = started or do_more_goal
            do_more = bool(do_more_goal)
            if job_text:
                if hard_rule_refusal(job_text):
                    refusal = hard_rule_refusal(job_text)
                    conversation["messages"][-1].update(status="done", content=refusal,
                        action_card={"id": request_id, "state": "refused", "executable": False, "reason": "Standing rule: drafts only"})
                    self.save(conversation)
                    self.conversations[identifier] = conversation
                    self.record_turn(ask=text, provider=None, jobs=[], files=[], commits=[], confirmations=[],
                                refusals=[refusal], open_items=[])
                    return self.public(conversation)
                conversation["pending_job"] = job_text
                conversation["pending_job_id"] = request_id
                confirm_body = (
                    "I can queue a **draft** screen job for the conductor scheduler — I am not read-only here. "
                    "Reply `yes, start job` to confirm, or say `start a job: …` with your exact goal."
                    if do_more
                    else "I can queue a **draft** screen job for the conductor scheduler. Reply `yes, start job` to confirm, or edit your request."
                )
                conversation["messages"][-1].update(status="done",
                    content=confirm_body,
                    action_card={"id": request_id, "proposal_id": request_id, "state": "confirm", "executable": True,
                                 "reason": "Queue job: " + job_text[:120]})
                self.save(conversation)
                self.conversations[identifier] = conversation
                return self.public(conversation)
            refusal = hard_rule_refusal(text)
            if refusal:
                conversation["messages"][-1].update(status="done", content=refusal,
                    action_card={"id": request_id, "state": "refused", "executable": False,
                                 "reason": "Standing rule: drafts only"})
            self.save(conversation)
            self.conversations[identifier] = conversation
            if refusal:
                if hasattr(self.providers, "circuit"):
                    self.providers.circuit.log("action_refused", request_id=request_id, reason="drafts_only")
                self.record_turn(ask=text, provider=None, jobs=[], files=[], commits=[], confirmations=[],
                            refusals=[refusal], open_items=[])
                return self.public(conversation)
            inbox_body = state_ledger.parse_inbox_message(text)
            ledger = self.ledger_root(identifier)
            if inbox_body:
                if ledger != self.root:
                    conversation["messages"][-1].update(
                        status="done",
                        content="Builder inbox is disabled during a drill overlay — use a normal chat to reach the mini.",
                        provider="state",
                    )
                    self.save(conversation)
                    self.conversations[identifier] = conversation
                    return self.public(conversation)
                state_ledger.append_inbox(self.root, inbox_body, source="web-bob", request_id=request_id)
                reply = (
                    "Got it — I added that to the builder inbox on the mini. "
                    "The next round will re-read INBOX.md before continuing."
                )
                conversation["messages"][-1].update(status="done", content=reply, provider="inbox")
                self.save(conversation)
                self.conversations[identifier] = conversation
                self.record_turn(conversation_id=identifier, ask=text, provider="inbox", jobs=[], files=["conductor/state/INBOX.md"],
                            commits=[], confirmations=[], refusals=[], open_items=[inbox_body[:200]],
                            request_id=request_id)
                if not state_ledger._DRILL_NOISE_RE.search(text):
                    state_ledger.record_webchat_turn(ledger, ask=text, provider="inbox", request_id=request_id)
                return self.public(conversation)
            if ledger == self.root:
                try:
                    state_ledger.sync_from_live_ops(
                        self.root, load_live_ops(self.root).get("live_ops") or {},
                        head_sha=draft_head_sha(self.root),
                        webchat_round=(load_live_ops(self.root).get("live_ops") or {}).get("webchat_round"),
                    )
                except OSError:
                    pass
            music_tip = try_music_coach_reply(text) if provider == "auto" else None
            if music_tip:
                conversation["messages"][-1].update(status="done", content=music_tip, provider="state")
                self.save(conversation)
                self.conversations[identifier] = conversation
                self.record_turn(conversation_id=identifier, ask=text, provider="state", jobs=[], files=["conductor/webchat/song-projects"],
                            commits=[], confirmations=[], refusals=[], open_items=[], request_id=request_id)
                state_ledger.record_webchat_turn(ledger, ask=text, provider="state", request_id=request_id)
                return self.public(conversation)
            bob_line = try_bob_state_running_line(ledger, text) if provider == "auto" else None
            if bob_line:
                conversation["messages"][-1].update(status="done", content=bob_line, provider="state")
                self.save(conversation)
                self.conversations[identifier] = conversation
                self.record_turn(conversation_id=identifier, ask=text, provider="state", jobs=[], files=["conductor/handback/BOB-STATE.md"],
                            commits=[], confirmations=[], refusals=[], open_items=[], request_id=request_id)
                state_ledger.record_webchat_turn(ledger, ask=text, provider="state", request_id=request_id)
                return self.public(conversation)
            local_status = state_ledger.try_status_reply(ledger, text) if provider == "auto" else None
            if local_status:
                conversation["messages"][-1].update(status="done", content=local_status, provider="state")
                self.save(conversation)
                self.conversations[identifier] = conversation
                head = draft_head_sha(self.root)
                self.record_turn(conversation_id=identifier, ask=text, provider="state", jobs=[], files=["conductor/state/STATE.json"],
                            commits=[head] if head else [], confirmations=[], refusals=[], open_items=[],
                            request_id=request_id)
                state_ledger.record_webchat_turn(ledger, ask=text, provider="state", request_id=request_id)
                return self.public(conversation)
            self.launch(identifier)
            return self.public(conversation)

    def launch(self, identifier):
        # Caller holds self.lock; the same saved assistant message is reused.
        if not self.closing.is_set():
            cancel = threading.Event()
            if identifier in self.overlay_roots:
                self.overlay_pins[identifier] = self.overlay_roots[identifier]
            worker = threading.Thread(target=self.complete, args=(identifier, cancel), daemon=True)
            self.workers[identifier] = {"thread": worker, "cancel": cancel, "started_at": time.time()}
            worker.start()

    def complete(self, identifier, cancel):
        with self.lock:
            conversation = copy.deepcopy(self.get(identifier))
            value = self.get(identifier)
            if value["messages"] and value["messages"][-1]["status"] == "queued":
                value["messages"][-1].update(status="running", provider=None, attempts=[])
                self.save(value)
        def progress(provider, attempts):
            with self.lock:
                value = self.get(identifier)
                value["messages"][-1].update(status="running", provider=provider, attempts=attempts)
                self.save(value)
        try:
            answer = self.providers.reply(conversation, cancel, progress)
            if cancel.is_set():
                raise Cancelled("Reply stopped.")
            with self.lock:
                value = self.get(identifier)
                value["codex_thread_id"] = answer.pop("codex_thread_id", None)
                value.pop("retry_prompt", None)
                answer["content"] = repair_hollow_progress(self.redact(answer["content"]))
                user_msg = next((m for m in reversed(value["messages"]) if m["role"] == "user"), {})
                rid = user_msg.get("request_id")
                value["messages"][-1].update(answer, status="done")
                if rid:
                    value["messages"][-1]["request_id"] = rid
                value["messages"][-1].pop("retry_at", None)
                self.save(value)
                user = user_msg.get("content", "")
                head = draft_head_sha(self.root)
                commits = [head] if head else []
                self.record_turn(conversation_id=identifier, ask=user, provider=answer.get("provider"),
                            jobs=[], files=[], commits=commits, confirmations=[], refusals=[],
                            open_items=[user[:200]] if user else [],
                            request_id=user_msg.get("request_id"))
                try:
                    ledger = self.ledger_root(identifier)
                    if not (ledger == self.root and state_ledger._DRILL_NOISE_RE.search(user or "")):
                        state_ledger.record_webchat_turn(
                            ledger, ask=user, provider=answer.get("provider"), request_id=user_msg.get("request_id"),
                        )
                except OSError:
                    pass
        except AllDown as exc:
            with self.lock:
                value = self.get(identifier)
                value["codex_thread_id"] = None
                value["retry_prompt"] = exc.prompt
                value["messages"][-1].update(status="cancelled" if cancel.is_set() else "waiting",
                    provider=None, content="Reply stopped." if cancel.is_set() else str(exc),
                    attempts=exc.attempts, retry_at=exc.retry_at)
                self.save(value)
        except Exception as exc:
            with self.lock:
                value = self.get(identifier)
                value["codex_thread_id"] = None
                value.pop("retry_prompt", None)
                message = str(exc) if isinstance(exc, ProviderError) else "The reply failed unexpectedly. Your message is saved; please try again."
                value["messages"][-1].update(status="cancelled" if isinstance(exc, Cancelled) else "error", content=self.redact(message))
                self.save(value)
        finally:
            with self.lock:
                self.workers.pop(identifier, None)
                self.overlay_pins.pop(identifier, None)

    def stop(self, identifier):
        with self.lock:
            value = self.get(identifier)
            info = self.workers.get(identifier)
            if info:
                info["cancel"].set()
            elif value["messages"] and value["messages"][-1]["status"] == "waiting":
                value["messages"][-1].update(status="cancelled", content="Queued request stopped.")
                value.pop("retry_prompt", None)
                self.save(value)
                if hasattr(self.providers, "circuit"):
                    self.providers.circuit.log("queue_cancelled", conversation_id=identifier)

    def retry_queued(self):
        with self.lock:
            self.sweep_stuck()
            queued = sorted((c for c in self.conversations.values() if c["messages"] and c["messages"][-1]["status"] == "waiting"), key=lambda c: c["messages"][-1]["created_at"])
            for value in queued:
                if value["id"] in self.workers:
                    continue
                message = value["messages"][-1]
                if message.get("retry_at", 0) <= time.time():
                    message.update(status="queued", content="", provider=None)
                    self.save(value)
                    if hasattr(self.providers, "circuit"):
                        self.providers.circuit.log("queue_retry", conversation_id=value["id"])
                    self.launch(value["id"])
                    return

    def start_background(self):
        self.providers.start_probes()
        def loop():
            while not self.closing.wait(1):
                try:
                    if not self.closing.is_set():
                        self.migrate_legacy_tasks()
                        self.reconcile_tasks()
                        self.retry_queued()
                        self.sweep_stuck()
                except Exception:
                    self.providers.circuit.log("queue_error", reason="queued retry could not start")
        self.queue_thread = threading.Thread(target=loop, daemon=True)
        self.queue_thread.start()

    def close(self):
        self.closing.set()
        with self.lock:
            for info in self.workers.values():
                info["cancel"].set()
        if self.queue_thread:
            self.queue_thread.join(timeout=3)
        for info in list(self.workers.values()):
            info["thread"].join(timeout=10)
        if hasattr(self.providers, "close"):
            self.providers.close()

    def report(self, relative):
        path = self.root / relative
        try:
            with path.open() as handle:
                value = handle.read(200_001)
                modified = os.fstat(handle.fileno()).st_mtime
        except OSError:
            raise RequestError(404, "This report is not available yet.") from None
        return {"text": self.redact(value[:200_000]), "truncated": len(value) > 200_000,
                "modified_at": modified, "read_at": time.time()}

    def handback(self):
        return public_digest(self.root, self.redact)

    @staticmethod
    def _launchd_job_loaded(label: str) -> bool | None:
        if sys.platform != "darwin":
            return None
        try:
            proc = subprocess.run(
                ["/bin/launchctl", "print", f"gui/{os.getuid()}/{label}"],
                capture_output=True,
                timeout=3,
                check=False,
            )
            return proc.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return None

    def _cached_launchd_loaded(self, label: str) -> bool | None:
        cache = getattr(self, "_launchd_probe_cache", {})
        now = time.time()
        hit = cache.get(label)
        if hit and now - hit[1] < 60:
            return hit[0]
        value = self._launchd_job_loaded(label)
        cache[label] = (value, now)
        self._launchd_probe_cache = cache
        return value

    def _self_improve_schedule_hint(self, plist: Path) -> str | None:
        if not plist.is_file():
            return None
        try:
            text = plist.read_text(errors="replace")
        except OSError:
            return None
        hour = minute = None
        for key, var in (("Hour", "hour"), ("Minute", "minute")):
            match = re.search(rf"<key>{key}</key>\s*<integer>(\d+)</integer>", text)
            if match:
                if var == "hour":
                    hour = int(match.group(1))
                else:
                    minute = int(match.group(1))
        if hour is None:
            return None
        minute = minute if minute is not None else 0
        return f"Scheduled daily ~{hour:02d}:{minute:02d} CT on the mini (launchd)."

    def self_improve_status(self):
        root = self.root
        plist = root / "conductor/launchd/com.jeff.bob-webchat-self-improve.plist"
        tick = root / "conductor/webchat/self_improve_tick.sh"
        log_path = root / "logs/webchat-self-improve.log"
        label = "com.jeff.bob-webchat-self-improve"
        schedule_hint = self._self_improve_schedule_hint(plist)
        last_tick = None
        last_tick_outcome = None
        handback = root / "conductor/handback/HANDBACK-LOG.md"
        if handback.exists():
            try:
                text = handback.read_text(errors="replace")
            except OSError:
                text = ""
            for block in reversed(text.split("\n## ")):
                lower = block.lower()
                if "self-improve tick" in lower or "webchat self-improve tick" in lower:
                    last_tick = block.split("\n", 1)[0].strip() or None
                    break
        files_ok = plist.exists() and tick.exists()
        launchd_loaded = self._cached_launchd_loaded(label) if files_ok else False
        recent_ok = False
        recent_age_seconds = None
        if log_path.exists():
            try:
                tail = log_path.read_text(errors="replace")[-4000:]
                tail_lower = tail.lower()
                recent_ok = False
                for line in reversed(tail.splitlines()):
                    if "self-improve tick" not in line.lower():
                        continue
                    last_tick_outcome = line.strip()[:200]
                    low = line.lower()
                    if re.search(r"self-improve tick ok\b|tick ok\b", low) and "failed" not in low:
                        recent_ok = True
                    elif "tick skipped" in low:
                        recent_ok = True
                    break
                if "tests failed" in tail_lower[-800:]:
                    recent_ok = False
                recent_age_seconds = max(0, time.time() - log_path.stat().st_mtime)
                if recent_age_seconds > 48 * 3600:
                    recent_ok = False
            except OSError:
                recent_ok = False
        summary = "Self-improve runs on the mini (launchd, draft branch only)."
        if last_tick:
            summary = f"Last tick logged {last_tick}. {summary}"
        if launchd_loaded is True:
            summary = "Launchd job loaded. " + summary
        elif launchd_loaded is False and files_ok:
            summary = (
                "Launchd job not loaded — run conductor/webchat/bootstrap_self_improve_launchd.sh on the mini. "
                + summary
            )
        elif launchd_loaded is None and files_ok:
            summary = "Launchd probe unavailable on this host. " + summary
        elif not files_ok:
            summary = "Install self-improve launchd plist + tick script. " + summary
        healthy = bool(files_ok and (launchd_loaded is True or recent_ok))
        tick_ok_streak = 0
        if log_path.exists():
            try:
                for line in reversed(log_path.read_text(errors="replace").splitlines()[-40:]):
                    low = line.lower()
                    if "self-improve tick" not in low:
                        continue
                    if re.search(r"self-improve tick ok\b|tick ok\b", low) and "failed" not in low:
                        tick_ok_streak += 1
                    elif "skipped" in low:
                        continue
                    else:
                        break
            except OSError:
                tick_ok_streak = 0
        loop_ready = bool(
            files_ok
            and recent_ok
            and tick_ok_streak >= 1
            and recent_age_seconds is not None
            and recent_age_seconds < 48 * 3600
        )
        if schedule_hint:
            summary = schedule_hint + " " + summary
        if loop_ready:
            summary = f"Loop ready ({tick_ok_streak} recent OK tick{'s' if tick_ok_streak != 1 else ''}). " + summary
        if loop_ready:
            plain_status = f"Loop ready — {tick_ok_streak} OK tick{'s' if tick_ok_streak != 1 else ''} on the mini."
        elif launchd_loaded is True and recent_ok:
            plain_status = "Launchd loaded and the last tick passed tests."
        elif launchd_loaded is False and files_ok:
            plain_status = "Copy the install command below and run it once on the mini."
        elif not files_ok:
            plain_status = "Self-improve files missing in the repo — pull latest draft branch."
        elif recent_ok:
            plain_status = "Last tick OK — load launchd on the mini to stay on schedule."
        else:
            plain_status = "Waiting for a successful tick (webchat + failover + services tests)."
        if last_tick_outcome:
            plain_status = f"{plain_status} Latest: {last_tick_outcome[:120]}."
        bootstrap = root / "conductor/webchat/bootstrap_self_improve_launchd.sh"
        install_ready = bool(files_ok and bootstrap.is_file())
        if bootstrap.is_file():
            rel = bootstrap.relative_to(root)
            bootstrap_command = f"cd {shlex.quote(str(root))} && bash {shlex.quote(str(rel))}"
        else:
            bootstrap_command = None
        return {
            "launchd_plist": plist.exists(),
            "tick_script": tick.exists(),
            "bootstrap_script": str(bootstrap.relative_to(root)) if bootstrap.exists() else None,
            "launchd_files_ok": files_ok,
            "launchd_loaded": launchd_loaded,
            "healthy": healthy,
            "recent_tick_ok": recent_ok,
            "last_logged": last_tick,
            "last_tick_log_line": last_tick_outcome,
            "recent_log_ok": recent_ok,
            "log_age_seconds": recent_age_seconds,
            "schedule_hint": schedule_hint,
            "tick_ok_streak": tick_ok_streak,
            "loop_ready": loop_ready,
            "install_ready": install_ready,
            "bootstrap_command": bootstrap_command,
            "plain_status": plain_status,
            "summary": summary,
        }

    def round_changelog(self) -> dict:
        import re

        def round_num(path: Path) -> int:
            match = re.search(r"R(\d+)", path.name)
            return int(match.group(1)) if match else 0

        paths = sorted(
            self.root.glob("conductor/reviews/WEBCHAT-READY-R*-RESULT.md"),
            key=round_num,
            reverse=True,
        )
        if not paths:
            return {}
        path = paths[0]
        name = path.name
        round_no = round_num(path) or None
        line = ""
        try:
            text = path.read_text(errors="replace")
            section = re.search(r"^## Changelog\s*\n+(.+?)(?:\n## |\Z)", text, re.M | re.S)
            if section:
                for row in section.group(1).splitlines():
                    cleaned = row.strip()
                    if cleaned and not cleaned.startswith("#"):
                        line = cleaned[:220]
                        break
            if not line:
                explicit = re.search(r"^\*\*Changelog:\*\*\s*(.+)$", text, re.M)
                if explicit:
                    line = explicit.group(1).strip()[:220]
            if not line:
                for row in text.splitlines():
                    if "Time-to-value" in row or "visible improvement" in row.lower():
                        line = row.strip().lstrip("|").rstrip("|").strip()[:220]
                        break
            if not line:
                for row in text.splitlines():
                    if row.startswith("|") and "iPhone" in row:
                        line = row.strip().lstrip("|").rstrip("|").strip()[:220]
                        break
        except OSError:
            pass
        return {"round": round_no, "file": name, "line": line or "See latest round result on the mini."}

    def panel(self):
        lanes = self.providers.health()
        jobs = self.jobs()
        results = []
        for path in sorted(self.root.glob("conductor/reviews/*RESULT*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:5]:
            try:
                results.append({"name": path.name, "modified_at": path.stat().st_mtime})
            except OSError:
                continue
        loaded = load_live_ops(self.root)
        live_ops = loaded.get("live_ops") or {}
        meta = loaded.get("meta") or {}
        alignment: dict = {}
        try:
            state_ledger.sync_from_live_ops(
                self.root, live_ops, head_sha=draft_head_sha(self.root), webchat_round=live_ops.get("webchat_round"),
            )
            alignment = state_ledger.public_slice(self.root)
            now_line = alignment.get("now_line")
            if now_line and not live_ops.get("now_line"):
                live_ops = {**live_ops, "now_line": now_line}
        except OSError:
            alignment = state_ledger.public_slice(self.root)
        dashboard_age = meta.get("dashboard_modified_at")
        if dashboard_age is None:
            status_path = self.root / "conductor/STATUS.md"
            dashboard_age = status_path.stat().st_mtime if status_path.exists() else None
        alignment_events: dict = {}
        try:
            import alignment_events as align_ev  # noqa: WPS433

            alignment_events = {
                "latest_seq": align_ev.latest_seq(self.root),
                "recent": align_ev.read_events(self.root, since_seq=max(0, align_ev.latest_seq(self.root) - 20)),
            }
        except (ImportError, OSError):
            alignment_events = {}
        if live_ops.get("dashboard_freshness_seconds") is None and dashboard_age is not None:
            live_ops = {**live_ops, "dashboard_freshness_seconds": round(max(0, time.time() - dashboard_age))}
        live_ops = enrich_live_ops(live_ops)
        changelog = self.round_changelog()
        qh = in_quiet_hours()
        return {"lanes": lanes, "jobs": jobs, "recent_results": results, "round_changelog": changelog,
                "dashboard_modified_at": dashboard_age,
                "live_ops": live_ops, "live_ops_meta": meta, "conductor": conductor_snapshot(self.root),
                "handback": self.handback(), "self_improve": self.self_improve_status(),
                "alignment": alignment, "alignment_events": alignment_events,
                "quiet_hours": {
                    "active": qh,
                    "window": "11 PM–7 AM CT",
                    "read_aloud_blocked": qh,
                },
                "read_at": time.time()}

    def jobs(self):
        try:
            code, out, _ = run(["/usr/bin/screen", "-ls"], cwd=self.root, env=clean_env(),
                                cancel=threading.Event(), timeout=5)
            screens = out.strip() if code in (0, 1) and out.strip() else "Screen listing unavailable."
        except (OSError, ProviderError):
            screens = "Screen listing unavailable."
        try:
            queue = self.report("next-prompts/INDEX.md")
        except RequestError:
            queue = {"text": "Queue not available yet.", "modified_at": None}
        maintenance = self.root / "conductor/MAINTENANCE"
        return {"screens": self.redact(screens), "queue": queue, "read_at": time.time(),
                "dispatch": [{k: row.get(k) for k in ("id", "conversation_id", "status", "worker", "requested_worker",
                             "created_at", "claimed_at", "started_at", "finished_at", "delivered_at", "attempts", "error")}
                             for row in task_queue.tasks(self.root).values()],
                "maintenance": self.redact(maintenance.read_text()[:1000]) if maintenance.exists() else None}


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, chat, public_origin=""):
        if address[0] != HOST:
            raise ValueError("Bob web chat must bind to 127.0.0.1")
        self.chat = chat
        super().__init__(address, Handler)
        port = self.server_address[1]
        self.origins = {f"127.0.0.1:{port}": f"http://127.0.0.1:{port}", f"localhost:{port}": f"http://localhost:{port}"}
        if public_origin:
            parsed = urlsplit(public_origin)
            if (parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith(".ts.net")
                    or parsed.path not in ("", "/") or parsed.query or parsed.fragment or parsed.username or parsed.password):
                self.server_close()
                raise ValueError(".public-origin must be an exact https:// device.ts.net origin")
            self.origins[parsed.netloc.lower()] = public_origin.rstrip("/")


class Handler(BaseHTTPRequestHandler):
    server_version = "BobWebchat/1"

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, *_args):
        pass  # No URLs, cookies, prompts, passwords or provider output in HTTP logs.

    def send(self, status, data, content_type="application/json; charset=utf-8", headers=None):
        if isinstance(data, (dict, list)):
            data = json.dumps(data, ensure_ascii=False)
        if isinstance(data, str):
            data = data.encode()
        self.send_response(status)
        extra = {"X-Bob-Webchat-Drills": "1"} if os.environ.get("BOB_WEBCHAT_DRILLS") == "1" else {}
        for key, value in {
            "Content-Type": content_type, "Content-Length": str(len(data)), "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; media-src 'self'; connect-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'",
            "X-Bob-Webchat": "1", **extra, **(headers or {}),
        }.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def body(self, form=False, limit=None):
        if self.headers.get("Transfer-Encoding"):
            raise RequestError(400, "Transfer encoding is not supported.")
        cap = limit or MAX_BODY
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise RequestError(400, "Invalid content length.") from None
        if not 0 < size <= cap:
            raise RequestError(413, "Request is empty or too large.")
        mime = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if mime != ("application/x-www-form-urlencoded" if form else "application/json"):
            raise RequestError(415, "Unsupported content type.")
        try:
            raw = self.rfile.read(size).decode("utf-8")
            data = {k: v[0] for k, v in parse_qs(raw).items()} if form else json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError()
            return data
        except (UnicodeError, ValueError):
            raise RequestError(400, "Invalid request body.") from None

    def cookie(self, token, clear=False):
        secure = self.origin.startswith("https://")
        return f"{COOKIE}={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={0 if clear else SESSION_SECONDS}" + ("; Secure" if secure else "")

    def dispatch(self):
        try:
            hosts = self.headers.get_all("Host", [])
            if len(hosts) != 1 or hosts[0].lower() not in self.server.origins:
                raise RequestError(403, "Unrecognized host.")
            self.origin = self.server.origins[hosts[0].lower()]
            self.path_only = urlsplit(self.path).path
            session = self.server.chat.authenticate(self.headers.get("Cookie"))
            if self.path_only == "/api" or self.path_only.startswith("/api/"):
                if not session:
                    raise RequestError(401, "Please log in.")
            if self.command == "POST":
                origins = self.headers.get_all("Origin", [])
                if (origins and origins != [self.origin]) or self.headers.get("Sec-Fetch-Site") in ("cross-site", "same-site"):
                    raise RequestError(403, "Cross-site requests are not allowed.")
                if self.path_only.startswith("/api/"):
                    csrf = self.headers.get("X-CSRF-Token", "")
                    if not hmac.compare_digest(csrf.encode(), session["csrf"].encode()):
                        raise RequestError(403, "Invalid request token. Reload the page.")
                self.post(session)
            elif self.command == "GET":
                self.get(session)
            else:
                raise RequestError(405, "Method not allowed.")
        except RequestError as exc:
            self.send(exc.status, {"error": exc.message})
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass
        except Exception:
            self.send(500, {"error": "The request failed. Please try again."})

    do_GET = dispatch
    do_POST = dispatch
    do_OPTIONS = dispatch
    do_PUT = dispatch
    do_DELETE = dispatch
    do_PATCH = dispatch

    def stream_alignment(self, chat):
        try:
            import alignment_events as align_ev  # noqa: WPS433
        except ImportError:
            raise RequestError(503, "Alignment stream unavailable.") from None
        query = parse_qs(urlsplit(self.path).query)
        try:
            since = int(query.get("since", ["0"])[0] or 0)
        except ValueError:
            raise RequestError(400, "Invalid since parameter.") from None
        self.connection.settimeout(45.0)
        self.send_response(200)
        for key, value in {
            "Content-Type": "text/event-stream; charset=utf-8",
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "X-Bob-Webchat": "1",
        }.items():
            self.send_header(key, value)
        self.end_headers()
        deadline = time.time() + 40
        cursor = since
        try:
            while time.time() < deadline:
                batch = align_ev.read_events(chat.root, since_seq=cursor)
                for row in batch:
                    cursor = max(cursor, int(row.get("seq") or 0))
                    payload = json.dumps(row, ensure_ascii=False).encode()
                    self.wfile.write(b"data: " + payload + b"\n\n")
                self.wfile.flush()
                if batch:
                    self.wfile.write(f"event: ping\ndata: {{\"latest_seq\":{cursor}}}\n\n".encode())
                    self.wfile.flush()
                time.sleep(2)
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass

    def get(self, session):
        route, chat = self.path_only, self.server.chat
        assets = {"/style.css": ("style.css", "text/css; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                  "/manifest.webmanifest": ("manifest.webmanifest", "application/manifest+json")}
        if route in assets:
            name, mime = assets[route]
            return self.send(200, (HERE / "static" / name).read_bytes(), mime)
        if route == "/login":
            return self.send(200, (HERE / "static/login.html").read_bytes(), "text/html; charset=utf-8")
        if route == "/":
            if not session:
                return self.send(303, "", headers={"Location": "/login"})
            return self.send(200, (HERE / "static/index.html").read_bytes(), "text/html; charset=utf-8")
        if route in ("/api", "/api/session"):
            return self.send(200, {"csrf": session["csrf"], "active_conversation": next(iter(chat.workers), None),
                                   "active_conversations": list(chat.workers)})
        if route == "/api/conversations":
            return self.send(200, chat.conversation_list())
        if route.startswith("/api/conversations/"):
            return self.send(200, chat.history(route.removeprefix("/api/conversations/")))
        if route in ("/api/status", "/api/review"):
            return self.send(200, chat.report("conductor/STATUS.md" if route.endswith("status") else "conductor/reviews/LATEST.md"))
        if route == "/api/jobs":
            return self.send(200, chat.jobs())
        if route == "/api/handback":
            return self.send(200, chat.handback())
        if route == "/api/panel":
            return self.send(200, chat.panel())
        if route == "/api/panel/refresh":
            return self.send(405, {"error": "Use POST to refresh dashboard."})
        if route == "/api/conductor":
            return self.send(200, conductor_snapshot(chat.root))
        if route == "/api/music/eligibility":
            try:
                status = music_budget_status(chat.root)
            except Exception as exc:
                raise RequestError(503, str(exc)) from exc
            return self.send(200, {"ok": True, **status})
        if route == "/api/song-projects":
            return self.send(200, {"projects": list_projects(chat.root)})
        if route.startswith("/api/song-projects/"):
            project_id = route.removeprefix("/api/song-projects/").strip("/")
            try:
                return self.send(200, get_project(chat.root, project_id))
            except FileNotFoundError:
                raise RequestError(404, "Song project not found.") from None
        if route.startswith("/api/audio/"):
            audio_id = route.removeprefix("/api/audio/").strip("/")
            try:
                path = resolve_audio(chat.root, audio_id)
            except (ValueError, FileNotFoundError):
                raise RequestError(404, "Audio not found.") from None
            mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            return self.send(200, path.read_bytes(), mime)
        if route == "/api/lanes":
            identifier = parse_qs(urlsplit(self.path).query).get("conversation_id", [None])[0]
            if identifier:
                chat.get(identifier)
            return self.send(200, chat.providers.health(identifier))
        if route == "/api/alignment/events":
            try:
                import alignment_events as align_ev  # noqa: WPS433

                since = int(parse_qs(urlsplit(self.path).query).get("since", ["0"])[0] or 0)
            except ValueError:
                raise RequestError(400, "Invalid since parameter.") from None
            return self.send(200, {"events": align_ev.read_events(chat.root, since_seq=since), "latest_seq": align_ev.latest_seq(chat.root)})
        if route == "/api/alignment/stream":
            return self.stream_alignment(chat)
        raise RequestError(404, "Not found.")

    def post(self, session):
        route, chat = self.path_only, self.server.chat
        if route == "/login":
            token = chat.login(self.body(form=True).get("password"))
            return self.send(303, "", headers={"Location": "/", "Set-Cookie": self.cookie(token)})
        if route == "/api/logout":
            self.body()
            with chat.lock:
                chat.sessions.pop(session["digest"], None)
            return self.send(200, {"ok": True}, headers={"Set-Cookie": self.cookie("", clear=True)})
        if route == "/api/conversations":
            self.body()
            return self.send(201, chat.new_conversation())
        if route == "/api/panel/refresh":
            self.body()
            spawned = maybe_spawn_dashboard_refresh(chat.root)
            return self.send(202, {"ok": True, "spawned": spawned})
        if route == "/api/messages":
            data = self.body()
            return self.send(202, chat.submit(data.get("conversation_id"), data.get("message"), data.get("request_id"), data.get("provider", "auto"), worker=data.get("worker")))
        if route == "/api/cancel":
            chat.stop(self.body().get("conversation_id"))
            return self.send(202, {"ok": True})
        if route == "/api/song-projects":
            data = self.body()
            try:
                project = save_project(chat.root, data)
            except (TypeError, json.JSONDecodeError, OSError) as exc:
                raise RequestError(400, "Could not save song project.") from exc
            chat.record_turn(ask="song notebook save: " + project.get("title", ""), provider=None, jobs=[], files=[project["id"]],
                            commits=[], confirmations=[], refusals=[], open_items=[])
            return self.send(200, project)
        if route == "/api/music/demo":
            data = self.body()
            lyrics = data.get("lyrics") or ""
            style = data.get("style") or ""
            receipt = demo_receipt(lyrics, style)
            if not data.get("confirm"):
                return self.send(200, {"ok": False, "needs_confirm": True, "receipt": receipt,
                                       "estimate_usd": 0.0, "engine": "local-sketch",
                                       "can_afford_demo": True,
                                       "message": "Generate a free local chord sketch from your lyrics? Confirm to render ($0)."})
            if data.get("receipt") != receipt:
                raise RequestError(400, "Demo confirmation does not match current lyrics/style. Save and try again.")
            try:
                result = generate_demo(chat.root, lyrics=lyrics, style=style, dry_run=bool(data.get("dry_run")))
            except Exception as exc:
                raise RequestError(400, str(exc)) from exc
            result["receipt"] = receipt
            return self.send(200, result)
        if route == "/api/drill/overlay":
            if os.environ.get("BOB_WEBCHAT_DRILLS") != "1":
                raise RequestError(403, "Drill overlay is disabled.")
            data = self.body()
            return self.send(200, chat.bind_drill_overlay(data.get("conversation_id"), data.get("fixture_id")))
        if route == "/api/drill/overlay/clear":
            if os.environ.get("BOB_WEBCHAT_DRILLS") != "1":
                raise RequestError(403, "Drill overlay is disabled.")
            data = self.body()
            chat.get(data.get("conversation_id"))
            return self.send(200, chat.clear_drill_overlay(data.get("conversation_id")))
        if route == "/api/audio/upload":
            data = self.body(limit=MAX_AUDIO_BODY)
            name = data.get("filename") or "upload.mp3"
            raw = data.get("data_base64")
            if not isinstance(raw, str):
                raise RequestError(400, "Audio payload required.")
            try:
                blob = base64.b64decode(raw, validate=True)
            except ValueError:
                raise RequestError(400, "Invalid audio encoding.") from None
            suffix = Path(name).suffix or ".mp3"
            try:
                stored = store_upload(chat.root, blob, suffix)
            except ValueError as exc:
                raise RequestError(400, str(exc)) from exc
            chat.record_turn(ask=f"audio upload {name}", provider=None, jobs=[], files=[stored["path"]],
                            commits=[], confirmations=[], refusals=[], open_items=[])
            return self.send(201, stored)
        raise RequestError(404, "Not found.")


def main():
    os.umask(0o077)
    with (HERE / ".server.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("Bob web chat is already running.")
        chat = Chat()
        origin_path = HERE / ".public-origin"
        origin = origin_path.read_text().strip() if origin_path.exists() else ""
        server = Server((HOST, PORT), chat, origin)
        chat.start_background()
        def shutdown(_signum, _frame):
            with chat.lock:
                for info in chat.workers.values():
                    info["cancel"].set()
            threading.Thread(target=server.shutdown, daemon=True).start()
        for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            signal.signal(signum, shutdown)
        print(f"Bob web chat listening on http://{HOST}:{PORT} (auth via local session file; secret never logged)", flush=True)
        try:
            server.serve_forever(poll_interval=0.25)
        finally:
            server.server_close()
            chat.close()


if __name__ == "__main__":
    main()
