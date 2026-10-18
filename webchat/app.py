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
import sqlite3
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
from urllib.error import URLError
from urllib.parse import parse_qs, quote, unquote, urlsplit

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
from chat_media import (
    MAX_VIDEO_BYTES,
    MAX_ATTACHMENTS_PER_MESSAGE,
    PROCESS_SLOTS,
    load_meta,
    media_limit,
    prompt_image_bytes,
    public_attachment,
    resolve_media,
    store_media,
    strip_assistant_attachment_markers,
    validate_attachment_ids,
)
from ops_panel import conductor_snapshot, draft_head_sha, enrich_live_ops, load_live_ops, maybe_spawn_dashboard_refresh
from quiet_hours import in_quiet_hours
from task_dispatch import FOLLOW_UP, PREAMBLE, TaskDispatch, followup_work, needs_task_detail, parse_work, task_queue
from voice import VoiceCalls, VoiceError
import chat_intent
from jobs_view import build_jobs_view, result_text
from build_info import BUILD, STATIC, VERSION_QUESTION, render_page
from texting import Texting
from local_tasks import LocalTasks, SEARCH as LOCAL_SEARCH
from bob_gaps import (
    append_profile_memory,
    capture_reply,
    capture_screenshot,
    format_web_search_reply,
    memory_confirm_prompt,
    needs_web_search,
    parse_memory_confirm,
    parse_remember,
    parse_screenshot,
    resolve_capture_path,
    web_search,
)
from bob_gaps import MEMORY_CANCEL as MEMORY_DISMISS

HERE = Path(os.environ.get("BOB_WEBCHAT_DIR", Path(__file__).resolve().parent)).resolve()
ROOT = Path(os.environ.get("BOB_ROOT", HERE.parent.parent)).resolve()
_STATE_LEDGER_DIR = Path(__file__).resolve().parents[1] / "state"
# Data roots never select executable code; prioritize this release even if its
# state directory already appears later in an inherited PYTHONPATH.
sys.path.insert(0, str(_STATE_LEDGER_DIR))
import ledger as state_ledger  # noqa: E402
HOST, PORT = "127.0.0.1", 8787  # Deliberately no all-interface or port override.
COOKIE = "bob_session"
SESSION_SECONDS = 12 * 60 * 60
MAX_BODY = 32768
MAX_AUDIO_BODY = 35 * 1024 * 1024
# Base64 expands 3 bytes to 4 characters: ceil(video_limit * 4 / 3) + JSON overhead
MAX_MEDIA_BODY = 4 * ((MAX_VIDEO_BYTES + 2) // 3) + MAX_BODY


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
    def __init__(self, folder=HERE, root=ROOT, providers=None, texting=None, *, reminder_notifier=None, calendar=None, local_tasks=None, shared_context=None, skills=None, storypool_actions=None):
        self.folder, self.root = folder, root
        self.shared_context = shared_context
        from storypool_actions import StoryPoolActions, guarded_executor
        self.storypool_actions = storypool_actions if storypool_actions is not None else StoryPoolActions(
            folder, execute=guarded_executor(root))
        from skill_runtime import SkillRuntime
        self.skills = skills if skills is not None else SkillRuntime()
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
        # Session checks also gate static assets and independent read endpoints.
        # Keep them independent of chat I/O such as a bridge receipt wait.
        self.auth_lock = threading.RLock()
        self.sessions, self.conversations = {}, {}
        self.overlay_roots: dict[str, Path] = {}
        self.overlay_pins: dict[str, Path] = {}
        self.failures = deque()
        self.workers = {}
        self.closing, self.queue_thread = threading.Event(), None
        self.providers = providers or Providers(
            root, self.redact, overlay_roots=self.overlay_roots, overlay_pins=self.overlay_pins,
        )
        self.texting = texting or Texting()
        self.texting.instinct.bind_state(folder)
        self.texting.andrea.bind_state(folder)
        self.voice = VoiceCalls(self)
        from reminders import Reminders
        self.reminders = Reminders(folder)
        # Tests, staging, and restored pending reminders must never implicitly
        # gain permission to display OS alerts. The server entry point opts in.
        self.reminder_notifier = reminder_notifier if reminder_notifier is not None else lambda body: False
        from calendar_actions import CalendarActions
        self.calendar = calendar if calendar is not None else CalendarActions(folder)
        # Keep direct lookups and routines on the established search adapter,
        # including its offline release/test injection boundary.
        self.local_tasks = local_tasks if local_tasks is not None else LocalTasks(
            folder, root=root, search=lambda query: format_web_search_reply(web_search(query)),
            read_calendar=lambda: self.calendar.read('today'))
        for path in self.state.glob("*.json"):
            if not UUID.fullmatch(path.stem):
                continue
            # Corrupt state fails startup visibly; never silently discard history.
            value = json.loads(path.read_text())
            if value.get("id") != path.stem or not isinstance(value.get("messages"), list):
                raise RuntimeError("Invalid conversation file: " + path.name)
            path.chmod(0o600)
            self.conversations[value["id"]] = value
            migrated_intent = "intent_state" not in value
            chat_intent.state_for(value)
            from project_context import recover as recover_project_context
            recovered_context = recover_project_context(self.ledger_root(value['id']), value)
            interrupted = False
            for message in value["messages"]:
                if message.get("status") in ("queued", "running"):
                    message.update(status="error", content="The server restarted before this reply finished. Send your message again to retry.")
                    interrupted = True
            if interrupted:
                value["codex_thread_id"] = None
                from self_improvement import recover_research
                recover_research(value)
            if interrupted or migrated_intent or recovered_context or value.get("_coordination_outbox"):
                self.save(value)
        if not self.conversations:
            self.new_conversation()
        self.migrate_legacy_tasks()
        self.reconcile_tasks()

    def save(self, conversation):
        messages = conversation.get('messages', [])
        from personal_drafts import private_requests as private_draft_requests
        private_drafts = private_draft_requests(conversation)
        for message in messages:
            if message.get('request_id') in private_drafts:
                message['private_draft'] = True
        # Product receipts, capability answers, resource/outage facts and private
        # memory own their exact source wording. Preserve reviewed evidence after
        # authority, provenance, and planning-condition checks too.
        if (messages and messages[-1].get('role') == 'assistant' and messages[-1].get('status') == 'done'
                and not messages[-1].get('texting')
                and not messages[-1].get('private_memory')
                and not messages[-1].get('private_draft')
                and messages[-1].get('provider') not in ('drafts', 'calendar', 'reminders', 'project-context', 'capabilities', 'skills')
                and not messages[-1].get('authority_review')
                and not messages[-1].get('result_provenance_review')
                and not messages[-1].get('artifact')
                and not messages[-1].get('resource_decision')
                and not messages[-1].get('decision_context_review')):
            from reply_quality import check
            ask = next((m.get('content', '') for m in reversed(messages) if m.get('role') == 'user'
                        and m.get('request_id') == messages[-1].get('request_id')), '')
            previous_answer = next((m.get('content', '') for m in reversed(messages[:-1])
                                    if m.get('role') == 'assistant' and m.get('status') == 'done'), '')
            messages[-1]['content'] = check(ask, messages[-1].get('content', ''),
                                           previous_answer=previous_answer)
        conversation["updated_at"] = time.time()
        if self.ledger_root(conversation['id']) != self.root:
            # Fixture context must remain excluded after its in-memory overlay
            # is cleared or the process restarts.
            conversation['_coordination_excluded'] = True
        pending = conversation.setdefault('_coordination_outbox', {})
        private_requests = {m.get('request_id') for m in conversation.get('messages', [])
                            if m.get('private_memory') or m.get('texting') or m.get('private_draft')}
        for event_id, record in list(pending.items()):
            if record.get('kind') == 'answer-delivered' and record.get('request_id') in private_requests:
                pending.pop(event_id)
        for record in self.coordination_records(conversation):
            pending.setdefault(record['event_id'], record)
        # Operational evidence owns an immutable, atomically saved public reply.
        # Bind its rendering identity in that same write; adding it only during
        # history projection made the returned status differ from saved evidence.
        # This is identity metadata, never a delivery acknowledgement or action.
        from reply_delivery import rendering
        for message in messages:
            if "status_observation" in message:
                message.pop("reply_delivery", None)
                delivery = rendering(message)
                if delivery is not None:
                    message["reply_delivery"] = delivery[0]
        path = self.state / (conversation["id"] + ".json")
        private_write(path, json.dumps(conversation, ensure_ascii=False, indent=2) + "\n")
        if conversation.get('_coordination_excluded'):
            return
        # Publish only saved turns. Shared observations never enter the action
        # dispatcher, and an unavailable journal cannot replay a completed turn.
        if self.shared_context is not None:
            from shared_chat import SharedChatError
            last = messages[-1] if messages else {}
            rid = last.get('request_id')
            if (rid and conversation.get('_shared_handoff_done') != rid
                    and last.get('role') == 'assistant' and last.get('status') in ('done', 'error')):
                try:
                    from personal_drafts import pending as pending_drafts
                    self.shared_context.record_conversation(conversation, redact=self.redact,
                        pending_count=len(pending_drafts(self, conversation)))
                    conversation['_shared_handoff_done'] = rid
                    conversation['_shared_context_status'] = 'available'
                    private_write(path, json.dumps(conversation, ensure_ascii=False, indent=2) + '\n')
                except (OSError, SharedChatError):
                    conversation['_shared_context_status'] = 'unavailable'
                    self.coordination_error()
        # The event payload and authoritative conversation commit together. If
        # publication fails, another turn or startup retries this same outbox.
        import alignment_events
        changed = False
        for event_id, record in list(pending.items()):
            try:
                alignment_events.append_event(self.root, **record)
            except OSError:
                self.coordination_error()
                break
            pending.pop(event_id)
            changed = True
        if changed:
            try:
                private_write(path, json.dumps(conversation, ensure_ascii=False, indent=2) + "\n")
            except OSError:
                # A crash can replay already published events, whose stable
                # identities make the publication idempotent, never execution.
                self.coordination_error()

    def coordination_error(self):
        if hasattr(self.providers, 'circuit'):
            try:
                self.providers.circuit.log('coordination_error', reason='Shared record publication unavailable')
            except OSError:
                pass

    def coordination_records(self, conversation):
        """Project saved work only; private texting never enters the handoff."""
        if (conversation.get('_coordination_excluded') or
                self.ledger_root(conversation['id']) != self.root):
            return []
        messages = conversation.get('messages', [])
        if not messages:
            return []
        last = messages[-1]
        # Historical entries and direct voice transcription can precede a
        # dispatched request. Missing IDs must not bind unrelated turns (or an
        # empty permission record) merely because both values are None.
        if not last.get('request_id'):
            return []
        user = next((m for m in reversed(messages) if m.get('role') == 'user'
                     and m.get('request_id') == last.get('request_id')), {})
        if (not user or last.get('texting') or user.get('texting') or
                last.get('private_memory') or user.get('private_memory') or
                last.get('private_draft') or user.get('private_draft')):
            return []
        records = []
        permission = conversation.get('intent_state', {}).get('last_permission') or {}
        if permission and permission.get('request_id') == user.get('request_id'):
            state = conversation['intent_state']
            scope = json.loads(self.redact(json.dumps({key:state[key] for key in ('holds', 'last_permission')})))
            records.append(dict(actor='web-bob', kind='scope-change',
                event_id=conversation['id'] + ':permission:' + user['request_id'],
                summary='Saved ' + permission['action'] + ' in one conversation.',
                conversation_id=conversation['id'], request_id=user['request_id'], saved_scope=scope,
                authority='Applies to this saved conversation; does not grant the receiver new work.'))
        if (last.get('role') == 'assistant' and last.get('status') == 'done'
                and not last.get('task_id') and not last.get('task_ids')):
            import hashlib
            content = self.redact(last.get('content', ''))
            digest = hashlib.sha256(content.encode()).hexdigest()
            records.append(dict(actor='web-bob', kind='answer-delivered',
                event_id=conversation['id'] + ':answer:' + last['id'] + ':' + digest,
                summary='Delivered a chat answer; this is not a verified external action.',
                conversation_id=conversation['id'], request_id=user['request_id'], message_id=last['id'],
                answer_excerpt=content[:1000], answer_sha256=digest))
            if last.get('project_dependencies') or last.get('project_dependency'):
                records[-1].pop('answer_excerpt')
                records[-1]['project_dependencies'] = last.get('project_dependencies', [last.get('project_dependency')])
        return records

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
                     "messages": [], "codex_thread_id": None, "intent_state": chat_intent.new_state()}
            if self.shared_context is not None:
                value['_shared_context_snapshot'] = self.shared_context.snapshot(include_engines=False)
            self.save(value)
            self.conversations[value["id"]] = value
            return self.public(value)

    def public(self, value):
        excluded = {"_shared_context_snapshot", "_shared_handoff_done", "_personal_action", "_coordination_outbox", "_coordination_excluded", "_coordination_prepared_batches", "codex_thread_id", "retry_prompt", "pending_job", "pending_job_id", "held_job",
                    "pending_memory", "pending_memory_id", "pending_memory_removal", "_project_edit", "_project_removal", "_project_intent", "_report_inputs",
                    "_project_handoffs", "_project_returns"}
        # Extensions never see core-private state or mutable conversation objects.
        filtered = {k: copy.deepcopy(v) for k, v in value.items() if k not in excluded}
        public = {k: v for k, v in self.texting.public(filtered).items() if k not in excluded}
        for message in public.get('messages', []):
            message.pop('_generation', None)
            message.pop('_reply_contract', None)
            message.pop('_reminder_extraction', None)
            message.pop('reply_delivery', None)
            from reply_delivery import rendering
            delivery = rendering(message)
            if delivery is not None:
                message['reply_delivery'] = delivery[0]
        info = self.workers.get(value["id"])
        public["reply_stopping"] = bool(info and info["cancel"].is_set())
        return public

    def bob_gaps_memory_turn(self, conversation, text, request_id, provider="auto"):
        if provider != "auto":
            return None
        identifier = conversation["id"]
        ledger = self.ledger_root(identifier)
        if ledger != self.root:
            return None
        pending_memory = conversation.get("pending_memory")
        memory_confirm, memory_proposal = parse_memory_confirm(text)
        if memory_confirm and not pending_memory:
            return self.intent_reply(conversation, "No memory is waiting for confirmation. Ask me to remember it again.", provider="state")
        if memory_confirm and pending_memory:
            expected = conversation.get("pending_memory_id")
            if memory_proposal and (not expected or memory_proposal != expected):
                conversation["messages"][-1].update(
                    status="done",
                    content="That memory button is stale. Use the latest card or ask again.",
                    provider="state",
                    action_card={"id": request_id, "state": "refused", "executable": False, "reason": "Stale memory proposal"},
                )
                self.save(conversation)
                self.conversations[identifier] = conversation
                return self.public(conversation)
            conversation.pop("pending_memory", None)
            conversation.pop("pending_memory_id", None)
            try:
                saved = append_profile_memory(self.root, pending_memory)
            except OSError:
                conversation["pending_memory"] = pending_memory
                conversation["pending_memory_id"] = expected or request_id
                conversation["messages"][-1].update(
                    status="done",
                    content="I could not save memory reliably. Your proposal is still available to review.",
                    provider="state",
                    action_card={"id": request_id, "state": "refused", "executable": False, "reason": "Save failed"},
                )
                self.save(conversation)
                self.conversations[identifier] = conversation
                return self.public(conversation)
            conversation["messages"][-1].update(
                status="done",
                content=f"Saved to durable memory:\n\n`{saved}`",
                provider="state",
                action_card={"id": request_id, "state": "done", "executable": False, "reason": "Memory saved"},
            )
            self.save(conversation)
            self.conversations[identifier] = conversation
            invalidate = getattr(self.providers, "invalidate_snapshot", None)
            if invalidate:
                invalidate()
            self.record_turn(conversation_id=identifier, ask=text, provider="state", jobs=[], files=["conductor/webchat/memory/profile.md"],
                        commits=[], confirmations=[pending_memory[:200]], refusals=[], open_items=[], request_id=request_id)
            state_ledger.record_webchat_turn(ledger, ask=text, provider="state", request_id=request_id)
            return self.public(conversation)
        if MEMORY_DISMISS.match(text) and pending_memory:
            conversation.pop("pending_memory", None)
            conversation.pop("pending_memory_id", None)
            conversation["messages"][-1].update(status="done", content="Memory save cancelled.", provider="state",
                action_card={"id": request_id, "state": "cancelled", "executable": False, "reason": "Memory dismissed"})
            self.save(conversation)
            self.conversations[identifier] = conversation
            return self.public(conversation)
        if pending_memory and not memory_confirm:
            conversation.pop("pending_memory", None)
        fact = parse_remember(text)
        if fact:
            conversation["pending_memory"] = fact
            conversation["pending_memory_id"] = request_id
            conversation["messages"][-1].update(
                status="done",
                content=memory_confirm_prompt(fact),
                provider="state",
                action_card={"id": request_id, "proposal_id": request_id, "kind": "memory", "state": "confirm",
                             "executable": True, "reason": "Memory: " + fact[:120]},
            )
            self.save(conversation)
            self.conversations[identifier] = conversation
            return self.public(conversation)
        return None

    def try_bob_gaps(self, conversation, text, request_id, provider="auto"):
        """Local parity tools before provider dispatch."""
        if provider != "auto":
            return None
        identifier = conversation["id"]
        ledger = self.ledger_root(identifier)
        if ledger != self.root:
            return None
        shot_target = parse_screenshot(text)
        if shot_target is not None:
            try:
                capture_id, _path = capture_screenshot(self.root, shot_target or None)
                conversation["messages"][-1].update(
                    status="done", content=capture_reply(capture_id, shot_target or None), provider="state")
            except (OSError, subprocess.CalledProcessError, RuntimeError) as exc:
                conversation["messages"][-1].update(status="done", content=str(exc), provider="state")
            self.save(conversation)
            self.conversations[identifier] = conversation
            self.record_turn(conversation_id=identifier, ask=text, provider="state", jobs=[], files=["conductor/webchat/captures"],
                        commits=[], confirmations=[], refusals=[], open_items=[], request_id=request_id)
            state_ledger.record_webchat_turn(ledger, ask=text, provider="state", request_id=request_id)
            return self.public(conversation)
        if needs_web_search(text):
            try:
                result = web_search(text)
                reply = format_web_search_reply(result)
            except (OSError, URLError, ValueError, TimeoutError) as exc:
                reply = f"I could not complete a web search right now ({exc})."
            conversation["messages"][-1].update(status="done", content=reply, provider="state")
            self.save(conversation)
            self.conversations[identifier] = conversation
            self.record_turn(conversation_id=identifier, ask=text, provider="state", jobs=[], files=[], commits=[],
                        confirmations=[], refusals=[], open_items=[], request_id=request_id)
            state_ledger.record_webchat_turn(ledger, ask=text, provider="state", request_id=request_id)
            return self.public(conversation)
        return None

    def intent_reply(self, conversation, content, provider="dispatcher", *, reconcile=False):
        conversation["messages"][-1].update(status="done", provider=provider, content=content)
        self.save(conversation)
        self.conversations[conversation["id"]] = conversation
        if reconcile:
            # An explicit resume owns recovery after its permission is durable;
            # it must not rely on the next browser history read to queue work.
            self.reconcile_tasks()
            return self.public(self.get(conversation["id"]))
        return self.public(conversation)

    def status_reply(self, conversation, text):
        from reply_authority import operational_reply
        from status_observation import bind_observation
        conversation = copy.deepcopy(conversation)
        observation = {}
        content = operational_reply(self.ledger_root(conversation["id"]), "server", text,
                                    observation=observation, redact=self.redact)
        conversation["messages"][-1]["status_observation"] = bind_observation(observation, conversation)
        # The reply and its exact rendering input share the existing private,
        # fsynced atomic conversation write. Retries/restarts keep both intact.
        return self.intent_reply(conversation, self.redact(content), provider="state")

    def get(self, identifier):
        if not isinstance(identifier, str) or not UUID.fullmatch(identifier) or identifier not in self.conversations:
            raise RequestError(404, "Conversation not found.")
        return self.conversations[identifier]

    def history(self, identifier):
        with self.lock:
            # Recovery belongs to startup and the background loop. A page read
            # must not enqueue a saved intent or acknowledge an outbox result.
            return self.public(self.get(identifier))

    def acknowledge_replies(self, identifier, receipts):
        from reply_delivery import acknowledge
        from webbob.chat_reply import ChatReplyError
        if (not isinstance(receipts, list) or not 1 <= len(receipts) <= 32
                or any(not isinstance(row, dict) or set(row) != {'message_id', 'id', 'sha256'}
                       or any(not isinstance(value, str) for value in row.values()) for row in receipts)):
            raise RequestError(400, 'Invalid reply receipts.')
        with self.lock:
            conversation = self.public(self.get(identifier))
            by_id = {m['id']: m for m in conversation['messages']}
            # Validate the entire batch before writing any observation. Private
            # text/voice and stale/foreign identities cannot become receipts.
            for row in receipts:
                message = by_id.get(row['message_id'], {})
                if message.get('reply_delivery') != {key: row[key] for key in ('id', 'sha256')}:
                    raise RequestError(409, 'Reply rendering changed or is unavailable.')
            try:
                return {'replies': [acknowledge(self.state, identifier, by_id[row['message_id']],
                    {key: row[key] for key in ('id', 'sha256')}) for row in receipts]}
            except (OSError, ChatReplyError, sqlite3.Error):
                raise RequestError(503, 'Reply observation could not be saved; the saved reply is unchanged.') from None

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
                pending = next((m for m in value["messages"] if m["id"] == info.get("reply_id")), None)
                if pending is None and value["messages"]:
                    pending = value["messages"][-1]
                if pending and pending["status"] in ("queued", "running"):
                    pending.update(status="error",
                        content="This reply timed out. Wait for it to finish stopping before sending another message.")
                    value["codex_thread_id"] = None
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
        with self.auth_lock:
            session = self.sessions.get(digest)
            if session and session["expires"] > time.time():
                return session
            self.sessions.pop(digest, None)
        return None

    def login(self, password):
        with self.auth_lock:
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

    def submit(self, identifier, text, request_id, provider="auto", worker=None, actor=None, attachments=None, source_voice=None, provider_mode='fallback'):
        if provider not in ("auto", "minimax", "gemini", "codex", "claude", "cursor"):
            raise RequestError(400, "Choose auto, minimax, gemini, codex, claude, or cursor.")
        if provider_mode not in ('fallback', 'only') or provider_mode == 'only' and provider == 'auto':
            raise RequestError(400, 'Choose one provider for provider-only mode.')
        if not isinstance(text, str):
            raise RequestError(400, "Write a message between 1 and 6,000 characters.")
        # Consent handlers must see the submitted message exactly, including
        # padding that ordinary chat input otherwise trims away.
        raw_text = text
        text = text.strip()
        raw_attachments = attachments if attachments is not None else []
        try:
            attachment_metas = validate_attachment_ids(self.root, raw_attachments, conversation_id=identifier)
        except ValueError as exc:
            raise RequestError(400, str(exc)) from exc
        except FileNotFoundError:
            raise RequestError(404, "One or more attachments were not found.") from None
        if not text and not attachment_metas:
            raise RequestError(400, "Write a message or attach a file.")
        if text and len(text) > 6000:
            raise RequestError(400, "Write a message between 1 and 6,000 characters.")
        if not isinstance(request_id, str) or not UUID.fullmatch(request_id):
            raise RequestError(400, "A valid request ID is required.")
        try:
            text.encode("utf-8")
        except UnicodeError:
            raise RequestError(400, "The message contains invalid text.") from None
        if text and self.redact(text) != text:
            raise RequestError(400, "This message appears to contain a secret. Remove it before sending; it was not saved or sent to a model.")
        public_attachments = [public_attachment(meta) for meta in attachment_metas]
        with self.lock:
            conversation = copy.deepcopy(self.get(identifier))
            if source_voice is None and self.voice.busy(identifier):
                if not self.voice.active(identifier):
                    raise RequestError(409, "Voice is still finishing startup. Wait a moment and try again.")
                raise RequestError(409, "End the voice call before typing in this conversation.")
            for message in conversation["messages"]:
                if message.get("request_id") == request_id:
                    if (message["content"] != text or message.get("preferred_provider", "auto") != provider
                            or message.get('provider_mode', 'fallback') != provider_mode
                            or message.get("requested_worker") != worker
                            or message.get("attachments", []) != public_attachments):
                        raise RequestError(409, "That request ID was already used for a different message.")
                    return self.public(conversation)
            if self.closing.is_set():
                raise RequestError(503, "Web Bob is restarting. Your new message was not saved; try again shortly.")
            self.sweep_stuck()
            if identifier in self.workers:
                raise RequestError(409, "Bob is finishing another reply in this conversation. Stop it or wait, then try again.")
            if any(m.get("status") == "waiting" for m in conversation["messages"]):
                raise RequestError(409, "This conversation has a queued request. Stop it before sending another message.")
            intent_state = chat_intent.state_for(conversation)
            was_held = bool(intent_state["holds"])
            conversation["preferred_provider"] = provider
            conversation['provider_mode'] = provider_mode
            import generation_budget
            try:
                admitted = generation_budget.binding(self.root, request_id, actor, text, require_active=False)
            except generation_budget.AdmissionDenied:
                # Broken or expired generation settings cannot block hold,
                # cancel, context removal or other deterministic controls.
                # Generation/dispatch boundaries revalidate before effects.
                admitted = None
            user_message = {"id": str(uuid.uuid4()), "request_id": request_id, "preferred_provider": provider,
                            "role": "user", "content": text, "status": "done", "created_at": time.time(),
                            "requested_worker": worker}
            user_message['provider_mode'] = provider_mode
            if admitted:
                user_message['_generation'] = admitted
            if public_attachments:
                user_message["attachments"] = public_attachments
            reply_message = {"id": str(uuid.uuid4()), "request_id": request_id, "role": "assistant", "content": "",
                             "status": "queued", "provider": None, "attempts": [], "created_at": time.time()}
            if source_voice:
                source = next((m for m in conversation["messages"] if m["id"] == source_voice
                               and m["role"] == "user" and m.get("voice_call_id") and m["content"] == text), None)
                if not source:
                    raise RequestError(400, "Request could not be processed. Please try again.")
                source.update({k: v for k, v in user_message.items() if k != "id"})
                reply_message.update(voice_call_id=source["voice_call_id"],
                    voice_turn_id=source.get("voice_turn_id"), voice_order=source.get("voice_order", 0) + 1)
            else:
                conversation["messages"].append(user_message)
            # Voice reuses its saved user row; every path creates an explicit
            # reply without indexing a possibly empty message list.
            conversation["messages"].append(reply_message)
            from conversation_focus import update as update_focus
            update_focus(conversation, source if source_voice else user_message)
            from self_improvement import observe_turn as observe_improvement_turn
            observe_improvement_turn(conversation, text, request_id)
            if conversation["title"] == "New conversation":
                conversation["title"] = (text or (public_attachments[0].get("filename") if public_attachments else "") or "Attachment")[:65]
            if not parse_memory_confirm(text)[0] and not parse_remember(text) and not MEMORY_DISMISS.match(text):
                conversation.pop("pending_memory", None)
                conversation.pop("pending_memory_id", None)
            storypool = self.storypool_actions.handle(raw_text, identifier, request_id, actor=actor,
                allow_effects=not public_attachments and worker is None and source_voice is None
                    and self.ledger_root(identifier) == self.root, blocked=bool(intent_state.get("holds")))
            if storypool is not None:
                for message in conversation['messages']:
                    if message.get('request_id') == request_id:
                        message['private_draft'] = True
                return self.intent_reply(conversation, self.redact(storypool), provider='storypool-controls')
            from memory_removal import handle as memory_removal_turn
            removal = memory_removal_turn(self, conversation, text, request_id, source_voice=source_voice,
                                         provider=provider, worker=worker, attachments=public_attachments)
            if removal is not None:
                return removal
            from project_context import handle as project_context_turn
            from project_context import observe as observe_project
            observe_project(self.ledger_root(identifier), conversation, text)
            context_reply = project_context_turn(self, conversation, text, request_id, provider=provider,
                worker=worker, attachments=public_attachments, source_voice=source_voice)
            if context_reply is not None:
                return context_reply
            from skill_runtime import selected as selected_skill, definition as skill_definition, SkillUnavailable
            # Preserve the established sourced watcher-status and private
            # digest receipts. These exact commands remain in teammates.py;
            # explicit skill selection must not intercept a bound thread read.
            legacy_band = re.fullmatch(r'band desk (?:status|(?:digest|read)(?: for .+)?)',
                                       text.strip().rstrip('.?!'), re.I)
            skill = selected_skill(text) if legacy_band is None else None
            if skill is not None:
                try:
                    skill_definition(skill)
                    if worker is not None:
                        return self.intent_reply(conversation, 'This skill reads or drafts in chat. Choose it without a work-lane assignment.', provider='skills')
                    if skill == 'director':
                        self.save(conversation)
                        self.conversations[identifier] = conversation
                        self.launch(identifier)
                        return self.public(conversation)
                    content = self.skills.status(skill, shared_context=self.shared_context)
                except SkillUnavailable:
                    content = 'The reviewed skill is unavailable. No skill action ran.'
                return self.intent_reply(conversation, self.redact(content), provider='skills')
            if VERSION_QUESTION.search(text):
                self.texting.invalidate(conversation)
                return self.intent_reply(conversation, BUILD["short_sha"])
            from capabilities import reply as capability_reply
            capability = capability_reply(text, self.root) if not public_attachments and worker is None else None
            if capability is not None:
                self.texting.invalidate(conversation)
                for key in ('pending_job', 'pending_job_id', 'pending_council', 'pending_council_id'):
                    conversation.pop(key, None)
                return self.intent_reply(conversation, capability, provider='capabilities')
            from memory_view import matches as memory_view_matches, inspect as inspect_memory
            if not public_attachments and worker is None and memory_view_matches(text):
                self.texting.invalidate(conversation)
                for key in ('pending_job', 'pending_job_id', 'pending_council', 'pending_council_id'):
                    conversation.pop(key, None)
                for message in conversation['messages']:
                    if message.get('request_id') == request_id:
                        message['private_memory'] = True
                return self.intent_reply(conversation, inspect_memory(self.ledger_root(identifier), self.redact), provider='memory')
            from personal_drafts import handle as personal_draft_turn
            personal = personal_draft_turn(self, conversation, text, request_id)
            if personal is not None:
                return self.intent_reply(conversation, self.redact(personal), provider='drafts')
            # Text intent and confirmations never enter generic job/provider routing.
            def persist_texting(value):
                # Replace competing drafts before the texting handler's durable save.
                # Confirmation still saves consumed consent before its handoff.
                if value.get('_personal_action', {}).get('request_id') == request_id:
                    from personal_drafts import replace_pending
                    replace_pending(self, value, keep='personal')
                if value['messages'][-1].get('text_draft_id'):
                    from personal_drafts import replace_pending
                    replace_pending(self, value, keep='texting')
                for key in ("pending_job", "pending_job_id", "pending_council", "pending_council_id"):
                    value.pop(key, None)
                self.save(value)
                self.conversations[identifier] = copy.deepcopy(value)
            if self.texting.handle(conversation, raw_text, actor, request_id, persist_texting, self.redact):
                return self.public(conversation)
            calendar = self.calendar.handle(text, identifier, request_id, intent_state)
            if calendar is not None:
                from personal_drafts import calendar_unavailable
                calendar = calendar_unavailable(self, conversation, text, request_id, calendar)
                if 'Calendar draft (not created):' in calendar:
                    from personal_drafts import replace_pending
                    replace_pending(self, conversation, keep='calendar')
                for key in ('pending_job', 'pending_job_id', 'pending_council', 'pending_council_id'):
                    conversation.pop(key, None)
                return self.intent_reply(conversation, self.redact(calendar), provider='calendar')
            from reminders import ReminderError, ExtractionNeeded
            import actions_intent
            if (actions_intent.reminder_request(text) or actions_intent.routine_intent(text)
                    or actions_intent.routine_request(text) or re.match(r'^remind me\b', text, re.I)):
                scopes = chat_intent.blocked_scopes(intent_state, chat_intent.projects(text), action_text=text)
                if scopes:
                    return self.intent_reply(conversation, chat_intent.hold_reply(scopes))
            try:
                reminder = self.reminders.handle(raw_text, identifier, request_id, local_tasks=self.local_tasks,
                                                 intent_state=intent_state, actor=actor, allow_model=True)
            except ExtractionNeeded:
                conversation['messages'][-1]['_reminder_extraction'] = dict(text=text, actor=actor)
                self.save(conversation)
                self.conversations[identifier] = conversation
                self.launch(identifier)
                return self.public(conversation)
            except ReminderError as exc:
                reminder = str(exc)
            if reminder is not None:
                for key in ('pending_job', 'pending_job_id', 'pending_council', 'pending_council_id'):
                    conversation.pop(key, None)
                return self.intent_reply(conversation, self.redact(reminder), provider='reminders')
            from reply_quality import creative_request
            if creative_request(text) and worker is None:
                self.save(conversation)
                self.conversations[identifier] = conversation
                self.launch(identifier)
                return self.public(conversation)
            local = self.local_tasks.handle(raw_text, identifier, request_id, intent_state)
            if local is not None:
                for key in ('pending_job', 'pending_job_id', 'pending_council', 'pending_council_id'):
                    conversation.pop(key, None)
                return self.intent_reply(conversation, self.redact(local),
                                         provider='state' if LOCAL_SEARCH.fullmatch(text.strip()) else 'local-tasks')
            from teammates import handle as teammate_turn
            teammate = teammate_turn(self, conversation, text, request_id)
            if teammate is not None:
                for key in ('pending_job', 'pending_job_id', 'pending_council', 'pending_council_id'):
                    conversation.pop(key, None)
                return self.intent_reply(conversation, self.redact(teammate), provider='teammates')
            from recorded_brief import reply as recorded_brief
            brief = recorded_brief(self.ledger_root(identifier), text)
            if brief is not None:
                return self.intent_reply(conversation, self.redact(brief), provider='state')
            from reply_authority import correcting_status
            if correcting_status(text, conversation):
                return self.status_reply(conversation, text)
            memory_turn = self.bob_gaps_memory_turn(conversation, text, request_id, provider=provider)
            if memory_turn:
                return memory_turn
            # Permission changes and worker admission share the queue lock.
            # A hold is durable before a concurrent claim/execute can proceed.
            with task_queue.locked(self.root):
                transition = chat_intent.apply_turn(intent_state, text, request_id)
                if transition:
                    self.save(conversation)
                    self.conversations[identifier] = copy.deepcopy(conversation)
            if transition == "hold":
                held_work, held_worker = followup_work(conversation)
                if held_work:
                    held = conversation.get('held_job') or {}
                    if held.get('prompt') != held_work or held.get('worker') != held_worker:
                        conversation["held_job"] = dict(prompt=held_work, worker=held_worker)
                return self.intent_reply(conversation, chat_intent.hold_reply(chat_intent.blocked_scopes(intent_state, [])))
            if transition == "priorities":
                conversation["pending_job"] = "Improve " + ", ".join(intent_state["project_order"])
                conversation["pending_job_id"] = request_id
                return self.intent_reply(conversation, "Priority order: " + ", ".join(intent_state["project_order"]) + ".")
            if not public_attachments and worker is None:
                from capabilities import prepare_coordination
                prepared = prepare_coordination(self, conversation, text, request_id)
                if prepared is not None:
                    return prepared
                cancelled_task = self.cancel_task_turn(conversation, text)
                if cancelled_task is not None:
                    return cancelled_task
                from project_handoffs import handle as project_handoff_turn
                handoff_reply = project_handoff_turn(self, conversation, text, request_id)
                if handoff_reply is not None:
                    return handoff_reply
                from project_reports import handle as project_report_turn
                report_reply = project_report_turn(self, conversation, text, request_id)
                if report_reply is not None:
                    return report_reply
                from self_improvement import handle as improvement_turn
                improvement = improvement_turn(self, conversation, text, request_id)
                if improvement is not None:
                    return improvement
            from reply_quality import spreadsheet_proposal
            if spreadsheet_proposal(text):
                scopes = chat_intent.blocked_scopes(intent_state, chat_intent.projects(text), action_text=text)
                if scopes:
                    return self.intent_reply(conversation, chat_intent.hold_reply(scopes))
                from personal_drafts import replace_pending
                replace_pending(self, conversation)
                conversation['pending_job'] = text
                conversation['pending_job_id'] = request_id
                columns = text.partition(':')[2].strip().rstrip('.') or 'Please specify the columns.'
                return self.intent_reply(conversation,
                    f'Spreadsheet template:\n\n```csv\n{columns}\n```\n\n'
                    f'Reply `yes, start job proposal {request_id}` to create the file.')
            from worker_assignment import requested_workers
            assignments = requested_workers(text, conversation)
            if assignments:
                return self.submit_worker_assignment(conversation, text, request_id, assignments)
            from worker_assignment import issue_followup
            fix = issue_followup(self.root, conversation, text)
            if fix:
                return self.submit_task(conversation, fix, request_id)
            work, route = parse_work(text, conversation=conversation)
            if transition == "resume" and not work:
                work_text = re.sub(r"^(?:go(?:\s+ahead)?|resume)(?:\s+and)?[\s,:!]+", "", chat_intent.command(text), flags=re.I)
                work, route = parse_work(work_text)
            started = parse_start(text)
            inbox_task = state_ledger.parse_inbox_message(text)
            if inbox_task:
                inbox_work, inbox_route = parse_work(inbox_task)
                if parse_start(inbox_task) or inbox_work:
                    work, route = parse_start(inbox_task) or inbox_work, inbox_route
            followup = FOLLOW_UP.fullmatch(text) or FOLLOW_UP.fullmatch(PREAMBLE.sub("", text)) or parse_do_more(text)
            if followup:
                work, route = followup_work(conversation)
            task = started or work or (text if worker is not None and not followup else None)
            names = chat_intent.project_targets(task or text, intent_state)
            if task and len(names) >= 2:
                intent_state["project_order"] = names
            if (chat_intent.PUSH.match(chat_intent.command(text)) or chat_intent.project_start(text)) and not names:
                return self.intent_reply(conversation, "Which projects should I work on?")
            if route != "max":
                try:
                    task_queue.worker_name(worker or route)
                except ValueError:
                    return self.submit_task(conversation, task or text, request_id, worker or route)
            if ((followup and not task) or (route != "auto" and not task)
                    or (task and needs_task_detail(task))):
                return self.intent_reply(conversation, "Ready when you are." if was_held and transition == "resume" and not task
                                         else "What would you like me to work on?", reconcile=transition == "resume")
            if task:
                conversation.pop("pending_job", None)
                conversation.pop("pending_job_id", None)
                if route == "max":
                    return self.submit_max_task(conversation, task, request_id)
                return self.submit_task(conversation, task, request_id, worker or route)
            # A resume prefix grants permission; it does not consume the rest
            # of a user request. Unknown verbs (for example "restart") must
            # reach the model with the original text instead of becoming a
            # successful, acknowledgement-only reply. Bare follow-ups were
            # handled above; an explicit hold-lift remains a control turn.
            if transition == "resume" and chat_intent.LIFT.fullmatch(chat_intent.command(text).rstrip(".! ")):
                return self.intent_reply(conversation, "Ready when you are.", reconcile=True)
            pending = conversation.get("pending_job")
            pending_council = conversation.get("pending_council")
            council_confirm, council_proposal = parse_council_confirm_proposal(text)
            if council_confirm or parse_council(text) or inbox_task:
                scopes = chat_intent.blocked_scopes(intent_state, chat_intent.projects(pending_council or inbox_task or text))
                if scopes:
                    return self.intent_reply(conversation, chat_intent.hold_reply(scopes))
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
                conversation.pop("pending_council_id", None)
                return self.submit_council(conversation, pending_council, request_id)
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
                conversation.pop("pending_job_id", None)
                return self.submit_task(conversation, pending, request_id)
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
            from reply_authority import HOLD_QUESTION, live_status_question
            from answer_intent import conceptual
            from conversation_focus import reference_scope
            from resource_inventory import question as resource_question
            if HOLD_QUESTION.match(text) and not reference_scope(conversation,text):
                scopes = chat_intent.blocked_scopes(intent_state, chat_intent.projects(text))
                return self.intent_reply(conversation, chat_intent.hold_reply(scopes) if scopes else "There are no active conversation holds.")
            if ledger == self.root and live_status_question(text,conversation) and not resource_question(text):
                return self.status_reply(conversation, text)
            if ledger == self.root:
                try:
                    live_ops = load_live_ops(self.root).get("live_ops") or {}
                    state_ledger.sync_from_live_ops(
                        self.root, live_ops,
                        head_sha=draft_head_sha(self.root),
                        webchat_round=live_ops.get("webchat_round"),
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
            local_status = state_ledger.try_status_reply(ledger, text) if provider == "auto" and live_status_question(text,conversation) and not resource_question(text) else None
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
            gaps = self.try_bob_gaps(conversation, text, request_id, provider=provider)
            if gaps:
                return gaps
            self.launch(identifier)
            return self.public(conversation)

    def launch(self, identifier):
        # Caller holds self.lock; the same saved assistant message is reused.
        if not self.closing.is_set():
            cancel = threading.Event()
            if identifier in self.overlay_roots:
                self.overlay_pins[identifier] = self.overlay_roots[identifier]
            value = self.get(identifier)
            import reply_contract
            value['messages'][-1].setdefault('_reply_contract', reply_contract.derive(value, self.redact,self.ledger_root(identifier)))
            user = next((m for m in reversed(value['messages']) if m.get('role')=='user'), {})
            if '_generation' not in user:
                import generation_budget
                try:
                    binding = generation_budget.binding(self.root,user.get('request_id'),'saved-owner-request',user.get('content',''))
                except generation_budget.AdmissionDenied:
                    value['messages'][-1].update(status='error',content='The active generation allowance does not admit this reply.')
                    self.save(value)
                    return
                if binding:
                    user['_generation'] = binding
            self.save(value)
            snapshot = copy.deepcopy(value)
            worker = threading.Thread(target=self.complete, args=(identifier, cancel, snapshot), daemon=True)
            self.workers[identifier] = {"thread": worker, "cancel": cancel, "started_at": time.time(),
                                        "reply_id": self.get(identifier)["messages"][-1]["id"]}
            try:
                worker.start()
            except RuntimeError:
                self.workers.pop(identifier, None)
                self.overlay_pins.pop(identifier, None)
                value = self.get(identifier)
                value.pop("retry_prompt", None)
                value["messages"][-1].update(status="error", provider=None,
                    content="The reply could not start. Your message is saved; send it again to retry.")
                self.save(value)

    def complete(self, identifier, cancel, conversation):
        reply_id = conversation["messages"][-1]["id"]
        def reply(value):
            return next(m for m in value["messages"] if m["id"] == reply_id)
        def pending(value):
            info = self.workers.get(identifier)
            return (info is not None and info["cancel"] is cancel
                    and reply(value)["status"] in ("queued", "running"))
        def release_worker():
            # Caller holds self.lock. An older thread must never retire a
            # follow-up that acquired this conversation after publication.
            info = self.workers.get(identifier)
            if info is not None and info["cancel"] is cancel:
                self.workers.pop(identifier, None)
                self.overlay_pins.pop(identifier, None)
        def progress(provider, attempts):
            with self.lock:
                value = self.get(identifier)
                if cancel.is_set() or not pending(value):
                    return
                reply(value).update(status="running", provider=provider, attempts=attempts)
                self.save(value)
        try:
            with self.lock:
                value = self.get(identifier)
                if not pending(value):
                    return
                if cancel.is_set():
                    raise Cancelled("Reply stopped.")
                reply(value).update(status="running", provider=None, attempts=[])
                self.save(value)
            from project_context import model_view as project_model_view, projection as project_projection
            model_conversation = project_model_view(self.ledger_root(identifier), self.texting.provider_view(conversation))
            if self.shared_context is not None and self.ledger_root(identifier) == self.root:
                model_conversation['_shared_context_snapshot'] = self.shared_context.snapshot()
            else:
                model_conversation.pop('_shared_context_snapshot', None)
            project_prompt = next((m['content'] for m in reversed(model_conversation['messages']) if m['role']=='user'), '')
            project_snapshot = project_projection(self.ledger_root(identifier), model_conversation, project_prompt)
            model_conversation['_project_snapshot'] = project_snapshot
            extraction = conversation['messages'][-1].get('_reminder_extraction')
            if extraction:
                from reminders import extraction_prompt
                model_conversation = copy.deepcopy(model_conversation)
                for message in reversed(model_conversation['messages']):
                    if message['role'] == 'user':
                        message['content'] = extraction_prompt(extraction['text'])
                        break
            answer = self.providers.reply(model_conversation, cancel, progress)
            with self.lock:
                value = self.get(identifier)
                # Check after acquiring the lock: Stop/timeout may have won it
                # while the provider was returning. Terminal outcomes stay final.
                if not pending(value):
                    return
                if cancel.is_set():
                    raise Cancelled("Reply stopped.")
                if extraction:
                    content = self.reminders.extracted(answer.get('content', ''), extraction['text'], identifier,
                        reply(value)['request_id'], extraction['actor'], chat_intent.state_for(value))
                    reply(value).update(content=self.redact(content), status='done', provider='reminders')
                    self.save(value)
                    release_worker()
                    return
                value["codex_thread_id"] = answer.pop("codex_thread_id", None)
                value.pop("retry_prompt", None)
                # Provider metadata cannot mint receipts or dispatcher authority.
                answer = {key: answer[key] for key in ("content", "provider", "attempts") if key in answer}
                from project_context import inherited_dependencies
                deps = getattr(getattr(self.providers, 'current_call', None), 'project_dependencies', None)
                if deps is None:
                    deps = inherited_dependencies(model_conversation, project_snapshot)
                if deps:
                    answer['project_dependencies'] = deps
                answer["content"] = self.redact(answer["content"])
                user_msg = next((m for m in value["messages"] if m["role"] == "user" and m.get("request_id") == reply(value).get("request_id")), {})
                from reply_authority import enforce
                from status_observation import bind_observation
                observation = {}
                from reply_contract import deliver
                report_bindings=getattr(getattr(self.providers,'current_call',None),'report_sources',[]) or []
                delivered, artifact = deliver(self.ledger_root(identifier), user_msg.get('content',''), answer, value,
                                               observation=observation, redact=self.redact,report_bindings=report_bindings)
                from project_reports import render_citations
                report_sources=[]
                if report_bindings:
                    delivered,report_sources=render_citations(self.ledger_root(identifier),delivered,report_bindings)
                if report_sources:
                    answer['report_sources']=report_sources
                answer['content'] = self.redact(delivered)
                if artifact:
                    answer['artifact'] = artifact
                if observation:
                    answer["status_observation"] = bind_observation(observation, value)
                cleaned, outbound = strip_assistant_attachment_markers(answer["content"])
                answer.pop("attachments", None)  # Provider metadata cannot bypass ownership checks.
                from chat_media import requested_attachment_ids
                # An explicit return of this turn's unchanged upload is an
                # owned-file operation, not a model formatting obligation.
                outbound = ([dict(media_id=mid) for mid in requested_attachment_ids(user_msg)] + outbound)
                if outbound:
                    seen = set()
                    resolved = []
                    unavailable = False
                    for item in outbound:
                        mid = item.get("media_id")
                        if mid in seen:
                            continue
                        seen.add(mid)
                        try:
                            if len(resolved) >= MAX_ATTACHMENTS_PER_MESSAGE:
                                raise ValueError()
                            resolved.append(public_attachment(load_meta(self.root, mid, conversation_id=identifier)))
                        except (FileNotFoundError, OSError, ValueError):
                            unavailable = True
                    if resolved:
                        answer["attachments"] = resolved
                    if unavailable:
                        cleaned += "\n\nOne or more requested attachments could not be included. Please reattach the file in this conversation."
                answer["content"] = cleaned
                import decision_context
                contract=reply(value).get('_reply_contract') or {}
                answer['content'],context_review=decision_context.render(answer['content'],contract.get('decision_context'),value,self.redact)
                if context_review:
                    answer['decision_context_review']=context_review
                rid = user_msg.get("request_id")
                reply(value).update(answer, status="done")
                if rid:
                    reply(value)["request_id"] = rid
                reply(value).pop("retry_at", None)
                try:
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
                finally:
                    release_worker()
        except AllDown as exc:
            with self.lock:
                value = self.get(identifier)
                if not pending(value):
                    return
                import generation_budget
                user = next((m for m in reversed(value['messages']) if m['role']=='user'
                             and m.get('request_id')==reply(value).get('request_id')), {})
                try:
                    generation_budget.request_available(user.get('_generation'))
                except generation_budget.AdmissionDenied as exhausted:
                    value.pop('retry_prompt', None)
                    reply(value).update(status='error', provider=None, content=str(exhausted), attempts=exc.attempts)
                    reply(value).pop('retry_at', None)
                    self.save(value)
                    release_worker()
                    return
                value["codex_thread_id"] = None
                if cancel.is_set():
                    value.pop("retry_prompt", None)
                else:
                    value["retry_prompt"] = exc.prompt
                reply(value).update(status="cancelled" if cancel.is_set() else "waiting",
                    provider=None, content="Reply stopped." if cancel.is_set() else str(exc),
                    attempts=exc.attempts, retry_at=exc.retry_at)
                self.save(value)
                release_worker()
        except Exception as exc:
            with self.lock:
                value = self.get(identifier)
                if not pending(value):
                    return
                value["codex_thread_id"] = None
                value.pop("retry_prompt", None)
                cancelled = cancel.is_set() or isinstance(exc, Cancelled)
                message = ("Reply stopped." if cancelled else str(exc) if isinstance(exc, ProviderError)
                           else "The reply failed unexpectedly. Your message is saved; please try again.")
                reply(value).update(status="cancelled" if cancelled else "error", content=self.redact(message))
                self.save(value)
                release_worker()
        finally:
            with self.lock:
                release_worker()

    def stop(self, identifier, *, request_id=None):
        with self.lock:
            value = self.get(identifier)
            info = self.workers.get(identifier)
            if info:
                pending = next((m for m in value["messages"] if m["id"] == info["reply_id"]), None)
                if request_id is not None and (not pending or pending.get('request_id') != request_id):
                    return
                info["cancel"].set()
                if pending and pending["status"] in ("queued", "running", "waiting"):
                    pending.update(status="cancelled", content="Reply stopped.")
                    pending.pop("retry_at", None)
                    value.pop("retry_prompt", None)
                    value["codex_thread_id"] = None
                    self.save(value)
            else:
                waiting = next((m for m in reversed(value["messages"]) if m.get("status") == "waiting"
                                and (request_id is None or m.get('request_id') == request_id)), None)
                if waiting is None:
                    return
                waiting.update(status="cancelled", content="Queued request stopped.")
                value.pop("retry_prompt", None)
                self.save(value)
                if hasattr(self.providers, "circuit"):
                    self.providers.circuit.log("queue_cancelled", conversation_id=identifier)

    def retry_queued(self):
        with self.lock:
            if self.closing.is_set():
                return
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

    def deliver_reminders(self):
        with self.lock:
            if self.closing.is_set():
                return
            routine_ran = False
            def deliver(row, notice):
                nonlocal routine_ran
                conversation = self.conversations.get(row['conversation_id'])
                if not conversation:
                    return False
                if any(m.get('reminder_notice') == notice for m in conversation['messages']):
                    return True
                if row['conversation_id'] in self.workers or self.voice.busy(row['conversation_id']):
                    return False  # Never insert into an active model/voice turn.
                if any(m.get('status') in ('queued', 'running', 'waiting') for m in conversation['messages']):
                    return False
                value = copy.deepcopy(conversation)
                from reminders import stamp
                content = 'Reminder: ' + row['body'] + ' (due ' + stamp(row['due_at']) + ').'
                if row.get('action'):
                    if routine_ran:
                        return False  # One bounded lookup per tick; let owner hold/cancel turns in.
                    state = chat_intent.state_for(value)
                    scopes = chat_intent.blocked_scopes(state, chat_intent.projects(row['action']))
                    if scopes:
                        return False  # A scheduler tick never lifts a saved hold.
                    routine_ran = True
                    result = self.local_tasks.handle(row['action'], row['conversation_id'],
                                                     'routine:' + notice, state, routine=True)
                    content = 'Routine result (due ' + stamp(row['due_at']) + '):\n' + (result or 'Unsupported action; no action ran.')
                value['messages'].append(dict(id=str(uuid.uuid4()), role='assistant', status='done', provider='reminders',
                    content=self.redact(content),
                    created_at=time.time(), reminder_notice=notice, reminder_id=row['id']))
                self.save(value)
                self.conversations[value['id']] = value
                return True
            self.reminders.deliver_due(deliver, lambda body: self.reminder_notifier(self.redact(body)))

    def start_background(self):
        self.providers.start_probes()
        def loop():
            while not self.closing.wait(1):
                try:
                    if not self.closing.is_set():
                        self.deliver_reminders()
                        self.migrate_legacy_tasks()
                        self.reconcile_tasks()
                        self.retry_queued()
                        self.sweep_stuck()
                except Exception:
                    self.providers.circuit.log("queue_error", reason="queued retry could not start")
        self.queue_thread = threading.Thread(target=loop, daemon=True)
        self.queue_thread.start()

    def close(self):
        with self.lock:
            # Share submit/retry admission's lock so shutdown cannot strand a
            # saved turn between its acceptance and worker launch.
            self.closing.set()
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
                             "created_at", "claimed_at", "started_at", "finished_at", "delivered_at", "attempts", "error",
                             "group_id", "group_size", "group_index", "title", "kind", "tried_workers", "pid", "execution_started_at")}
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
            "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; media-src 'self'; manifest-src 'self'; connect-src 'self' wss://generativelanguage.googleapis.com; worker-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'",
            "Permissions-Policy": "microphone=(self), camera=()",
            "X-Bob-Webchat": "1", **extra, **(headers or {}),
        }.items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def send_media(self, path, meta):
        size = path.stat().st_size
        start, end, status = 0, size - 1, 200
        headers = {"Accept-Ranges": "bytes"}
        requested = self.headers.get("Range")
        if requested:
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", requested)
            try:
                if not match or not any(match.groups()):
                    raise ValueError()
                first, last = match.groups()
                if first:
                    start, end = int(first), min(int(last), size - 1) if last else size - 1
                else:
                    if int(last) <= 0:
                        raise ValueError()
                    start = max(0, size - int(last))
                if start > end or start >= size:
                    raise ValueError()
            except ValueError:
                return self.send(416, b"", headers={**headers, "Content-Range": f"bytes */{size}"})
            status = 206
            headers["Content-Range"] = f"bytes {start}-{end}/{size}"
        headers["Content-Length"] = str(end - start + 1)
        query = parse_qs(urlsplit(self.path).query)
        disposition = "attachment" if meta["kind"] == "file" or query.get("download") == ["1"] else "inline"
        headers["Content-Disposition"] = disposition + "; filename*=UTF-8''" + quote(meta["filename"], safe="")
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send(status, b"", mime, headers)
        if self.command != "HEAD":
            with path.open("rb") as handle:
                handle.seek(start)
                remaining = end - start + 1
                while remaining:
                    chunk = handle.read(min(64 * 1024, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)

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
            raw = self.read_content(size, cap).decode("utf-8")
            data = {k: v[0] for k, v in parse_qs(raw).items()} if form else json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError()
            return data
        except (UnicodeError, ValueError):
            raise RequestError(400, "Invalid request body.") from None

    def read_content(self, size: int, cap: int, *, incomplete: str = "Incomplete request body. Please retry.") -> bytes:
        """Read exactly size bytes without exceeding cap; fail closed on short reads."""
        if size > cap:
            raise RequestError(413, "Request is empty or too large.")
        chunks, remaining = [], size
        while remaining > 0:
            part = self.rfile.read(min(remaining, 64 * 1024))
            if not part:
                break
            chunks.append(part)
            remaining -= len(part)
        blob = b"".join(chunks)
        if len(blob) != size:
            raise RequestError(400, incomplete)
        return blob

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
                if not session and not (self.command == "GET" and self.path_only == "/api/version"):
                    raise RequestError(401, "Please log in.")
            if self.command == "POST":
                origins = self.headers.get_all("Origin", [])
                if (origins and origins != [self.origin]) or self.headers.get("Sec-Fetch-Site") in ("cross-site", "same-site"):
                    raise RequestError(403, "Cross-site requests are not allowed.")
                if self.path_only.startswith("/api/"):
                    # Shared by typed messages and every voice mutation,
                    # including transcript, token creation and lease renewal.
                    csrf = self.headers.get("X-CSRF-Token", "")
                    if not hmac.compare_digest(csrf.encode(), session["csrf"].encode()):
                        raise RequestError(403, "Invalid request token. Reload the page.")
                self.post(session)
            elif self.command in ("GET", "HEAD"):
                self.get(session)
            else:
                raise RequestError(405, "Method not allowed.")
        except (RequestError, VoiceError) as exc:
            self.send(exc.status, {"error": exc.message})
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass
        except Exception:
            self.send(500, {"error": "The request failed. Please try again."})

    do_GET = dispatch
    do_HEAD = dispatch
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
                batch = align_ev.read_events_page(chat.root, since_seq=cursor)['events']
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
        if route == "/api/version":
            return self.send(200, BUILD)
        assets = {"/style.css": ("style.css", "text/css; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                  "/voice.js": ("voice.js", "text/javascript; charset=utf-8"),
                  "/voice-capture.js": ("voice-capture.js", "text/javascript; charset=utf-8"),
                  "/manifest.webmanifest": ("manifest.webmanifest", "application/manifest+json")}
        if route in assets:
            name, mime = assets[route]
            return self.send(200, (STATIC / name).read_bytes(), mime)
        if route == "/login":
            return self.send(200, render_page("login.html"), "text/html; charset=utf-8",
                             headers={"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache", "Expires": "0"})
        if route == "/":
            if not session:
                return self.send(303, "", headers={"Location": "/login"})
            return self.send(200, render_page("index.html"), "text/html; charset=utf-8",
                             headers={"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache", "Expires": "0"})
        if route in ("/api", "/api/session"):
            return self.send(200, {"csrf": session["csrf"], "active_conversation": next(iter(chat.workers), None),
                                   "active_conversations": list(chat.workers)})
        if route == "/api/conversations":
            return self.send(200, chat.conversation_list())
        if route.startswith("/api/conversations/"):
            return self.send(200, chat.history(route.removeprefix("/api/conversations/")))
        if route in ("/api/status", "/api/review"):
            return self.send(200, chat.report("conductor/STATUS.md" if route.endswith("status") else "conductor/reviews/LATEST.md"))
        if route == "/api/reminders":
            return self.send(200, {"reminders": chat.reminders.listing(), "timezone": "America/Chicago", "read_at": time.time()})
        if route == "/api/jobs":
            return self.send(200, chat.jobs())
        if route == "/api/jobs/activity":
            data = build_jobs_view(chat.root)
            data['reminders'] = chat.reminders.listing()
            from teammates import status as teammate_status
            data['teammates'] = teammate_status(chat.root)['teammates']
            return self.send(200, json.loads(chat.redact(json.dumps(data))))
        if route == "/api/jobs/result":
            identifier = parse_qs(urlsplit(self.path).query).get("id", [""])[0]
            result = result_text(chat.root, identifier)
            if result is None:
                raise RequestError(404, "No saved result for this job.")
            return self.send(200, json.loads(chat.redact(json.dumps(result))))
        if route in ('/api/project-handoffs/export', '/api/project-handoffs/return'):
            import project_handoffs
            query = parse_qs(urlsplit(self.path).query)
            cid = query.get('conversation_id', [''])[0]
            hid = query.get('handoff_id', [''])[0]
            try:
                if route.endswith('/return'):
                    data = project_handoffs.returned(chat, cid, hid)
                else:
                    handoff = project_handoffs.export(chat, cid, hid)
                    data = dict(handoff=handoff, return_template=project_handoffs.return_template(handoff))
            except ValueError as exc:
                raise RequestError(404, str(exc)) from None
            return self.send(200, data, headers={'Cache-Control': 'no-store',
                                               'Content-Disposition': 'attachment; filename="webbob-handoff.json"'})
        if route == "/api/handback":
            return self.send(200, chat.handback())
        if route == "/api/panel":
            return self.send(200, chat.panel())
        if route == "/api/overview":
            from tab_status import overview

            identifier = parse_qs(urlsplit(self.path).query).get("conversation_id", [None])[0]
            if identifier:
                chat.get(identifier)
            return self.send(200, chat.redact(json.dumps(overview(chat, identifier))))
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
        if route.startswith("/api/captures/"):
            capture_id = route.removeprefix("/api/captures/").strip("/")
            path = resolve_capture_path(chat.root, capture_id)
            if not path:
                raise RequestError(404, "Capture not found.") from None
            return self.send(200, path.read_bytes(), "image/png")
        if route.startswith("/api/media/"):
            media_id = route.removeprefix("/api/media/").strip("/")
            query = parse_qs(urlsplit(self.path).query)
            conversation_id = query.get("conversation_id", [None])[0]
            try:
                chat.get(conversation_id)
                meta = load_meta(chat.root, media_id, conversation_id=conversation_id)
                path = resolve_media(chat.root, media_id, conversation_id=conversation_id)
            except (ValueError, FileNotFoundError):
                raise RequestError(404, "Attachment not found.") from None
            if query.get("preview") == ["1"] and path.suffix in (".heic", ".heif"):
                if not PROCESS_SLOTS.acquire(blocking=False):
                    raise RequestError(503, "Image preview is busy. Download the original or retry.")
                try:
                    blob, _ = prompt_image_bytes(path)
                    return self.send(200, blob, "image/jpeg")
                except (ValueError, OSError):
                    raise RequestError(422, "Image preview unavailable. Download the original.") from None
                finally:
                    PROCESS_SLOTS.release()
            return self.send_media(path, meta)
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
            page = align_ev.read_events_page(chat.root, since_seq=since)
            return self.send(200, dict(page, latest_seq=align_ev.latest_seq(chat.root)))
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
            with chat.auth_lock:
                chat.sessions.pop(session["digest"], None)
            chat.voice.logout(session["digest"])
            return self.send(200, {"ok": True}, headers={"Set-Cookie": self.cookie("", clear=True)})
        if route == "/api/conversations":
            self.body()
            return self.send(201, chat.new_conversation())
        if route == '/api/project-handoffs/import':
            import project_handoffs
            data = self.body(limit=project_handoffs.MAX_BYTES)
            try:
                value = project_handoffs.import_return(chat, data.get('conversation_id'), data.get('artifact'))
            except (TypeError, ValueError) as exc:
                raise RequestError(400, str(exc)) from None
            return self.send(200, value)
        if route.startswith("/api/voice/"):
            data = self.body(limit=128 * 1024)
            owner = session["digest"]
            if route == "/api/voice/start":
                return self.send(201, chat.voice.start(data.get("conversation_id"), owner, session=session))
            if route == "/api/voice/transcript":
                return self.send(200, chat.voice.transcript(data.get("call_id"), owner, data.get("entries")))
            if route == "/api/voice/tool":
                return self.send(200, chat.voice.tool(data.get("call_id"), owner, data.get("turn_id")))
            if route == "/api/voice/interrupt":
                return self.send(200, chat.voice.interrupt(data.get("call_id"), owner, data.get("turn_id")))
            if route == "/api/voice/end":
                return self.send(200, chat.voice.end(data.get("call_id"), owner))
            if route == "/api/voice/pulse":
                return self.send(200, chat.voice.pulse(data.get("call_id"), owner))
            raise RequestError(404, "Not found.")
        if route == "/api/panel/refresh":
            self.body()
            spawned = maybe_spawn_dashboard_refresh(chat.root)
            return self.send(202, {"ok": True, "spawned": spawned})
        if route == "/api/reply-receipts":
            data = self.body()
            return self.send(200, chat.acknowledge_replies(data.get('conversation_id'), data.get('receipts')))
        if route == "/api/messages":
            data = self.body()
            return self.send(202, chat.submit(
                data.get("conversation_id"), data.get("message", ""), data.get("request_id"),
                data.get("provider", "auto"), worker=data.get("worker"), actor=session["digest"], attachments=data.get("attachments"),
                provider_mode=data.get('provider_mode', 'fallback'),
            ))
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
        if route == "/api/media/upload":
            mime = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if mime == "application/octet-stream":
                name = unquote(self.headers.get("X-Filename", ""))
                conversation_id = self.headers.get("X-Conversation-Id")
                chat.get(conversation_id)
                try:
                    limit = media_limit(name)
                    size = int(self.headers.get("Content-Length", "0"))
                except ValueError as exc:
                    raise RequestError(400, "Invalid attachment name, type, or size.") from exc
                if self.headers.get("Transfer-Encoding"):
                    raise RequestError(400, "Transfer encoding is not supported.")
                if not 0 < size <= limit:
                    raise RequestError(413, "Attachment is empty or too large.")
                blob = self.read_content(
                    size, limit, incomplete="Incomplete attachment upload. Please retry.")
            else:
                # Compatibility for existing JSON clients, including base64 expansion.
                data = self.body(limit=MAX_MEDIA_BODY)
                name, conversation_id = data.get("filename"), data.get("conversation_id")
                chat.get(conversation_id)
                raw = data.get("data_base64")
                if not isinstance(raw, str):
                    raise RequestError(400, "Attachment payload required.")
                try:
                    blob = base64.b64decode(raw, validate=True)
                except ValueError:
                    raise RequestError(400, "Invalid attachment encoding.") from None
                try:
                    limit = media_limit(name)
                except ValueError as exc:
                    raise RequestError(400, str(exc)) from exc
                if len(blob) > limit:
                    raise RequestError(413, f"Attachment too large ({limit // (1024 * 1024)}MB max).")
            try:
                stored = store_media(chat.root, blob, name, conversation_id=conversation_id, redact=chat.redact)
            except ValueError as exc:
                raise RequestError(400, str(exc)) from exc
            return self.send(201, public_attachment(stored))
        raise RequestError(404, "Not found.")


def main():
    os.umask(0o077)
    with (HERE / ".server.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("Bob web chat is already running.")
        from reminders import notify_macos
        notifier = notify_macos if os.environ.get('BOB_REMINDER_MACOS_NOTIFICATIONS') == '1' else None
        from shared_chat import SharedChatContext
        chat = Chat(reminder_notifier=notifier, shared_context=SharedChatContext.configured())
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
