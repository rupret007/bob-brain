"""Text and email outbound drafts with explicit human approval only.

Web Bob presents the exact draft; transport runs only after consent bound to the
current digest. Routines, timers, and background jobs must never call execute().
"""
import asyncio
from contextlib import contextmanager
import inspect
import json
from pathlib import Path
import re
import sqlite3
import time
import unicodedata
import uuid

from webbob.shared_context import _FACT_CONFUSABLES
from webbob.workspace import fingerprint

ALLOWED_SEND_TRIGGERS = frozenset({"explicit_approval"})
_TRIGGER_REQUIRED = object()
JEFF_APPROVAL_TTL_SECONDS = 900
ALLOWED_JEFF_APPROVAL_SOURCES = frozenset({"jeff_chat", "jeff_ui"})
FORBIDDEN_JEFF_APPROVAL_SOURCES = frozenset(
    {"agent", "tool", "routine", "inbound", "automation", "timer", "background"}
)
_BIDI_AND_FORMAT = frozenset(
    "\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069\ufeff"
)


class MessageDraftError(ValueError):
    pass


def _strip_format_chars(value):
    return "".join(c for c in value if unicodedata.category(c) != "Cf" and c not in _BIDI_AND_FORMAT)


def _normalize_visible(value):
    return unicodedata.normalize("NFKC", value).translate(_FACT_CONFUSABLES)


def _unicode_abuse(value):
    if not isinstance(value, str):
        return True
    for ch in value:
        if unicodedata.category(ch) == "Cf" or ch in _BIDI_AND_FORMAT:
            return True
        if unicodedata.bidirectional(ch) in {"R", "AL", "AN"}:
            return True
    normalized = _normalize_visible(_strip_format_chars(value))
    if normalized != _strip_format_chars(unicodedata.normalize("NFKC", value)):
        return True
    return False


def normalize_jeff_approval_text(text):
    """Return NFKC 'yes' or raise if disguised approval."""
    if not isinstance(text, str) or not text:
        raise MessageDraftError("approval must be exact yes")
    if _unicode_abuse(text):
        raise MessageDraftError("approval text contains forbidden unicode")
    stripped = _strip_format_chars(unicodedata.normalize("NFKC", text))
    if _normalize_visible(stripped) != stripped:
        raise MessageDraftError("approval text contains forbidden unicode")
    if stripped != "yes":
        raise MessageDraftError("approval must be exact yes")
    return stripped


def _hygiene_warnings(payload):
    warnings = []
    for field, value in payload.items():
        if isinstance(value, str) and _unicode_abuse(value):
            warnings.append(f"{field}:unicode_hygiene")
    return warnings


def present_draft(binding):
    """Surface a draft card for Web Bob without authorizing send."""
    if binding.get("state") != "draft":
        raise MessageDraftError("only draft state may be presented")
    channel = binding["channel"]
    payload = binding["payload"]
    preview = {"body": payload["body"]}
    if channel == "text":
        preview["chat_guid"] = payload["chat_guid"]
    else:
        preview["to"] = payload["to"]
        preview["subject"] = payload["subject"]
    warnings = _hygiene_warnings(payload)
    card = {
        "id": binding["id"],
        "channel": channel,
        "digest": binding["digest"],
        "revision": binding["revision"],
        "state": binding["state"],
        "preview": preview,
        "send_authorized": False,
    }
    if warnings:
        card["hygiene_warnings"] = warnings
    return card


class JeffDraftConsentVerifier:
    """Jeff-only, single-use consent bound to Bob chat, draft id, and digest."""

    def __init__(self, path, account, conversation, *, bob_chat=None):
        self.path = Path(path)
        self.account = account
        self.conversation = conversation
        self.bob_chat = bob_chat or conversation
        if not self.path.parent.is_dir() or self.path.is_symlink():
            raise MessageDraftError("private store unavailable")
        with self._db() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS jeff_send_approvals (
                proof TEXT PRIMARY KEY, account TEXT, conversation TEXT, draft_id TEXT,
                digest TEXT, expires REAL, consumed INTEGER NOT NULL DEFAULT 0)"""
            )
        self.path.chmod(0o600)

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA secure_delete=ON")
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def issue(self, draft_id, digest, approval_text, *, source, bob_chat=None):
        if source in FORBIDDEN_JEFF_APPROVAL_SOURCES:
            raise MessageDraftError("agent or inbound approval forbidden")
        if source not in ALLOWED_JEFF_APPROVAL_SOURCES:
            raise MessageDraftError("only Jeff may approve send")
        chat = bob_chat or self.bob_chat
        if chat != self.bob_chat:
            raise MessageDraftError("approval must be bound to Bob chat")
        normalize_jeff_approval_text(approval_text)
        proof = uuid.uuid4().hex
        expires = time.time() + JEFF_APPROVAL_TTL_SECONDS
        with self._db() as db:
            db.execute(
                "INSERT INTO jeff_send_approvals VALUES (?,?,?,?,?,?,0)",
                (proof, self.account, self.conversation, draft_id, digest, expires),
            )
        return proof

    def verify(self, draft_id, digest, proof):
        if not proof:
            return False
        now = time.time()
        with self._db() as db:
            row = db.execute(
                "SELECT * FROM jeff_send_approvals WHERE proof=?", (proof,)
            ).fetchone()
            if not row or row["consumed"]:
                return False
            if (
                row["account"] != self.account
                or row["conversation"] != self.conversation
                or row["draft_id"] != draft_id
                or row["digest"] != digest
                or row["expires"] <= now
            ):
                return False
            db.execute("UPDATE jeff_send_approvals SET consumed=1 WHERE proof=?", (proof,))
        return True

    def verify_callback(self):
        def _callback(digest, proof, draft_id):
            return self.verify(draft_id, digest, proof)

        return _callback


class MessageDraftGate:
    def __init__(self, path, account, conversation, *, verify_consent, ownership, dispatch):
        if not all(callable(f) for f in (verify_consent, ownership, dispatch)):
            raise MessageDraftError("consent verifier, ownership and dispatch adapters required")
        self.path, self.account, self.conversation = Path(path), account, conversation
        self.verify, self.ownership, self.dispatch = verify_consent, ownership, dispatch
        self._verify_accepts_draft_id = len(inspect.signature(verify_consent).parameters) >= 3
        if not self.path.parent.is_dir() or self.path.is_symlink():
            raise MessageDraftError("private store unavailable")
        with self.db() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS message_drafts (
                id TEXT PRIMARY KEY, account TEXT, conversation TEXT, channel TEXT,
                payload TEXT, revision INTEGER, digest TEXT, state TEXT, receipt TEXT, expires REAL)"""
            )
        self.path.chmod(0o600)

    def _consent_ok(self, draft_id, approved_digest, proof):
        if self._verify_accepts_draft_id:
            return self.verify(approved_digest, proof, draft_id) is True
        return self.verify(approved_digest, proof) is True

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA secure_delete=ON")
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _validate_recipient(self, address):
        if _unicode_abuse(address):
            raise MessageDraftError("single explicit recipient required")
        visible = _strip_format_chars(unicodedata.normalize("NFKC", address))
        if _normalize_visible(visible) != visible:
            raise MessageDraftError("single explicit recipient required")
        if "@" not in visible:
            raise MessageDraftError("single explicit recipient required")
        local, domain = visible.rsplit("@", 1)
        if not local or not domain or not all(ord(c) < 128 for c in local):
            raise MessageDraftError("single explicit recipient required")
        try:
            domain_ascii = domain.encode("idna").decode("ascii")
        except UnicodeError:
            raise MessageDraftError("single explicit recipient required")
        if not re.fullmatch(r"[A-Za-z0-9._%+-]+", local):
            raise MessageDraftError("single explicit recipient required")
        if not re.fullmatch(r"[A-Za-z0-9.-]+\.[A-Za-z0-9.-]+", domain_ascii):
            raise MessageDraftError("single explicit recipient required")
        return visible

    def _payload(self, channel, payload):
        allowed = {
            "text": {"chat_guid", "body"},
            "email": {"to", "subject", "body"},
        }
        if channel not in allowed or set(payload) != allowed[channel]:
            raise MessageDraftError("exact supported draft fields required")
        if any(not isinstance(v, str) or not v or len(v) > 10000 for v in payload.values()):
            raise MessageDraftError("invalid draft value")
        if channel == "text":
            if not re.fullmatch(r"[A-Za-z0-9:_-]{8,128}", payload["chat_guid"]):
                raise MessageDraftError("explicit chat guid required")
            if _unicode_abuse(payload["body"]):
                raise MessageDraftError("invalid draft value")
        else:
            self._validate_recipient(payload["to"])
            if "\n" in payload["subject"] or "\r" in payload["subject"]:
                raise MessageDraftError("plain single-line subject required")
            if _unicode_abuse(payload["subject"]) or _unicode_abuse(payload["body"]):
                raise MessageDraftError("invalid draft value")
        normalized = dict(payload)
        if channel == "email":
            normalized = dict(normalized, user_google_email=self.account, body_format="plain")
        return normalized

    def _owned(self, db, draft_id):
        row = db.execute("SELECT * FROM message_drafts WHERE id=?", (draft_id,)).fetchone()
        if not row or row["account"] != self.account or row["conversation"] != self.conversation:
            raise MessageDraftError("draft ownership mismatch")
        return row

    def prepare(self, channel, payload, draft_id=None):
        payload = self._payload(channel, payload)
        with self.db() as db:
            revision = 1
            if draft_id:
                old = self._owned(db, draft_id)
                if old["state"] != "draft":
                    raise MessageDraftError("attempted drafts cannot be edited or retried")
                revision = old["revision"] + 1
            draft_id = draft_id or uuid.uuid4().hex
            binding = {
                "id": draft_id,
                "account": self.account,
                "conversation": self.conversation,
                "channel": channel,
                "payload": payload,
                "revision": revision,
            }
            bound_digest = fingerprint(binding)
            db.execute(
                "INSERT OR REPLACE INTO message_drafts VALUES (?,?,?,?,?,?,?,'draft',NULL,?)",
                (
                    draft_id,
                    self.account,
                    self.conversation,
                    channel,
                    json.dumps(payload),
                    revision,
                    bound_digest,
                    time.time() + JEFF_APPROVAL_TTL_SECONDS,
                ),
            )
        return dict(binding, digest=bound_digest, state="draft")

    def receipt(self, draft_id):
        with self.db() as db:
            row = self._owned(db, draft_id)
            return {"id": draft_id, "digest": row["digest"], "state": row["state"], "receipt": row["receipt"]}

    async def execute(self, draft_id, approved_digest, proof, *, writes_enabled=False, trigger=_TRIGGER_REQUIRED):
        if trigger is _TRIGGER_REQUIRED or trigger not in ALLOWED_SEND_TRIGGERS:
            raise MessageDraftError("automatic or routine send forbidden")
        if not writes_enabled:
            raise MessageDraftError("writes disabled; explicit consent and scopes required")
        with self.ownership(draft_id):
            with self.db() as db:
                row = self._owned(db, draft_id)
                if row["state"] != "draft":
                    return {"id": draft_id, "state": row["state"], "receipt": row["receipt"]}
                if row["digest"] != approved_digest or row["expires"] <= time.time():
                    raise MessageDraftError("stale approval")
                if self._consent_ok(draft_id, approved_digest, proof) is not True:
                    raise MessageDraftError("exact consent missing or consumed")
                db.execute("UPDATE message_drafts SET state='uncertain' WHERE id=?", (draft_id,))
                channel, payload = row["channel"], json.loads(row["payload"])
            try:
                result = await asyncio.wait_for(self.dispatch(channel, payload), 30)
                if getattr(result, "isError", False):
                    return self.receipt(draft_id)
                receipt = fingerprint(result.model_dump(mode="json"))
            except Exception:
                return self.receipt(draft_id)
            with self.db() as db:
                db.execute("UPDATE message_drafts SET state='submitted',receipt=? WHERE id=?", (receipt, draft_id))
            return self.receipt(draft_id)
