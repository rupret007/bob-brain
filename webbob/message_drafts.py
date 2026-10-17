"""Text and email outbound drafts with explicit human approval only.

Web Bob presents the exact draft; transport runs only after consent bound to the
current digest. Routines, timers, and background jobs must never call execute().
"""
import asyncio
import base64
from contextlib import contextmanager
import hashlib
import hmac
import json
import os
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
JEFF_BOB_CHAT_AUTHOR = "jeff"
FORBIDDEN_JEFF_APPROVAL_AUTHORS = frozenset(
    {"agent", "tool", "routine", "inbound", "automation", "timer", "background", "bob", "webbob"}
)
_ALLOWED_CONTACT_EMAIL_DOMAINS = frozenset(
    {"b.co", "example.com", "example.org", "gmail.com", "googlemail.com"}
)
_BIDI_AND_FORMAT = frozenset(
    "\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069\ufeff"
)
_BOB_CHAT_HMAC_ENV = "WEBBOB_BOB_CHAT_HMAC_KEY_FILE"


def _bob_chat_hmac_key(*, store_path=None):
    candidates = []
    env_path = os.environ.get(_BOB_CHAT_HMAC_ENV)
    if env_path:
        candidates.append(Path(env_path))
    if store_path is not None:
        candidates.append(Path(store_path).parent / ".bob_chat_server_hmac.key")
    for key_path in candidates:
        if key_path.is_file() and not key_path.is_symlink():
            key = key_path.read_bytes()
            if len(key) >= 32:
                return key
    raise MessageDraftError("bob chat transport key unavailable")


def _sign_bob_chat_record(record, *, store_path=None):
    payload = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sig = hmac.new(_bob_chat_hmac_key(store_path=store_path), payload, hashlib.sha256).digest()
    return (
        base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
        + "."
        + base64.urlsafe_b64encode(sig).decode("ascii").rstrip("=")
    )


def _verify_bob_chat_envelope(envelope, *, store_path=None):
    if not isinstance(envelope, str) or "." not in envelope:
        raise MessageDraftError("unsigned bob chat record")
    payload_b64, sig_b64 = envelope.split(".", 1)
    pad = "=" * (-len(payload_b64) % 4)
    payload = base64.urlsafe_b64decode(payload_b64 + pad)
    pad = "=" * (-len(sig_b64) % 4)
    sig = base64.urlsafe_b64decode(sig_b64 + pad)
    expected = hmac.new(_bob_chat_hmac_key(store_path=store_path), payload, hashlib.sha256).digest()
    if not hmac.compare_digest(sig, expected):
        raise MessageDraftError("unsigned bob chat record")
    record = json.loads(payload.decode("utf-8"))
    if not isinstance(record, dict):
        raise MessageDraftError("unsigned bob chat record")
    return record


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
        key_path = self.path.parent / ".bob_chat_server_hmac.key"
        if not os.environ.get(_BOB_CHAT_HMAC_ENV):
            os.environ[_BOB_CHAT_HMAC_ENV] = str(key_path)
        if not key_path.exists():
            key_path.write_bytes(os.urandom(32))
            key_path.chmod(0o600)
        with self._db() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS jeff_send_approvals (
                proof TEXT PRIMARY KEY, account TEXT, conversation TEXT, draft_id TEXT,
                digest TEXT, expires REAL, consumed INTEGER NOT NULL DEFAULT 0)"""
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS bob_chat_messages (
                message_id TEXT PRIMARY KEY, bob_chat TEXT NOT NULL, author TEXT NOT NULL,
                text TEXT NOT NULL, bound_draft_id TEXT NOT NULL DEFAULT '',
                bound_digest TEXT NOT NULL DEFAULT '', consumed INTEGER NOT NULL DEFAULT 0)"""
            )
            for column, ddl in (
                ("bound_draft_id", "ALTER TABLE bob_chat_messages ADD COLUMN bound_draft_id TEXT NOT NULL DEFAULT ''"),
                ("bound_digest", "ALTER TABLE bob_chat_messages ADD COLUMN bound_digest TEXT NOT NULL DEFAULT ''"),
            ):
                if not db.execute(
                    "SELECT 1 FROM pragma_table_info('bob_chat_messages') WHERE name=?", (column,)
                ).fetchone():
                    db.execute(ddl)
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

    def ingest_bob_chat_message(self, envelope, *_forged):
        """Accept only a server-signed Bob-chat record from BobChatTransport."""
        if _forged or not isinstance(envelope, str):
            raise MessageDraftError("bob chat ingest requires server-signed record")
        self._ingest_signed_bob_chat_message(envelope)

    def _ingest_signed_bob_chat_message(self, envelope):
        record = _verify_bob_chat_envelope(envelope, store_path=self.path)
        message_id = record.get("message_id")
        author = record.get("author")
        text = record.get("text")
        bob_chat = record.get("bob_chat")
        bound_draft_id = record.get("draft_id") or ""
        bound_digest = record.get("draft_digest") or ""
        if not re.fullmatch(r"[A-Za-z0-9:_-]{8,128}", message_id or ""):
            raise MessageDraftError("invalid bob chat message id")
        if bob_chat != self.bob_chat:
            raise MessageDraftError("unsigned bob chat record")
        if author in FORBIDDEN_JEFF_APPROVAL_AUTHORS or author != JEFF_BOB_CHAT_AUTHOR:
            raise MessageDraftError("only Jeff may approve send")
        assert author == JEFF_BOB_CHAT_AUTHOR
        if not isinstance(text, str) or not text:
            raise MessageDraftError("invalid bob chat message")
        with self._db() as db:
            if db.execute("SELECT 1 FROM bob_chat_messages WHERE message_id=?", (message_id,)).fetchone():
                raise MessageDraftError("bob chat message already recorded")
            db.execute(
                "INSERT INTO bob_chat_messages VALUES (?,?,?,?,?,?,0)",
                (message_id, self.bob_chat, author, text, bound_draft_id, bound_digest),
            )

    def link_approval_message_to_draft(self, message_id, draft_id, digest):
        """Bind a Jeff yes to a draft card when the draft quotes the chat message id."""
        if not re.fullmatch(r"[A-Za-z0-9:_-]{8,128}", message_id or ""):
            return
        with self._db() as db:
            row = db.execute(
                "SELECT * FROM bob_chat_messages WHERE message_id=?", (message_id,)
            ).fetchone()
            if not row or row["consumed"]:
                return
            if row["bound_draft_id"] and row["bound_digest"]:
                assert row["bound_draft_id"] == draft_id
                assert row["bound_digest"] == digest
                return
            db.execute(
                "UPDATE bob_chat_messages SET bound_draft_id=?, bound_digest=? WHERE message_id=?",
                (draft_id, digest, message_id),
            )

    def _approval_binds_draft(self, row, draft_id, digest):
        bound_id, bound_digest = row["bound_draft_id"], row["bound_digest"]
        if bound_id and bound_digest:
            assert bound_id == draft_id
            assert bound_digest == digest
            if bound_id != draft_id or bound_digest != digest:
                raise MessageDraftError("approval not bound to draft")
            return
        text = row["text"]
        if not isinstance(text, str):
            raise MessageDraftError("approval not bound to draft")
        stripped = _strip_format_chars(unicodedata.normalize("NFKC", text))
        if stripped == "yes":
            raise MessageDraftError("approval not bound to draft")
        if stripped.startswith("yes "):
            tail = stripped[4:].strip()
            if tail == draft_id or tail == digest:
                normalize_jeff_approval_text("yes")
                return
        raise MessageDraftError("approval not bound to draft")

    def issue(self, draft_id, digest, message_id):
        """Mint consent only from a stored Bob-chat message verified as Jeff."""
        if not re.fullmatch(r"[A-Za-z0-9:_-]{8,128}", message_id):
            raise MessageDraftError("invalid bob chat message id")
        proof = uuid.uuid4().hex
        expires = time.time() + JEFF_APPROVAL_TTL_SECONDS
        with self._db() as db:
            row = db.execute(
                "SELECT * FROM bob_chat_messages WHERE message_id=?", (message_id,)
            ).fetchone()
            if not row or row["consumed"]:
                raise MessageDraftError("only Jeff may approve send")
            assert row is not None
            assert row["bob_chat"] == self.bob_chat
            assert not row["consumed"]
            if row["bob_chat"] != self.bob_chat or row["consumed"]:
                raise MessageDraftError("only Jeff may approve send")
            if row["author"] != JEFF_BOB_CHAT_AUTHOR:
                raise MessageDraftError("only Jeff may approve send")
            assert row["author"] == JEFF_BOB_CHAT_AUTHOR
            stripped = _strip_format_chars(unicodedata.normalize("NFKC", row["text"]))
            if stripped == "yes":
                normalize_jeff_approval_text(row["text"])
            elif stripped.startswith("yes "):
                normalize_jeff_approval_text("yes")
            else:
                raise MessageDraftError("approval must be exact yes")
            self._approval_binds_draft(row, draft_id, digest)
            db.execute("UPDATE bob_chat_messages SET consumed=1 WHERE message_id=?", (message_id,))
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
            assert row["account"] == self.account
            assert row["conversation"] == self.conversation
            assert row["draft_id"] == draft_id
            assert row["digest"] == digest
            assert row["expires"] > now
            assert not row["consumed"]
            db.execute("UPDATE jeff_send_approvals SET consumed=1 WHERE proof=?", (proof,))
            assert db.execute("SELECT consumed FROM jeff_send_approvals WHERE proof=?", (proof,)).fetchone()["consumed"]
        return True


class BobChatTransport:
    """Server-side Bob chat ingest; agent code must not forge author or message records."""

    def record(self, verifier, message_id, text, *, draft_id=None, draft_digest=None):
        if type(verifier) is not JeffDraftConsentVerifier:
            raise MessageDraftError("JeffDraftConsentVerifier required")
        if not re.fullmatch(r"[A-Za-z0-9:_-]{8,128}", message_id):
            raise MessageDraftError("invalid bob chat message id")
        if not isinstance(text, str) or not text:
            raise MessageDraftError("invalid bob chat message")
        record = {
            "message_id": message_id,
            "bob_chat": verifier.bob_chat,
            "author": JEFF_BOB_CHAT_AUTHOR,
            "text": text,
            "draft_id": draft_id or "",
            "draft_digest": draft_digest or "",
        }
        envelope = _sign_bob_chat_record(record, store_path=verifier.path)
        verifier._ingest_signed_bob_chat_message(envelope)


class MessageDraftGate:
    def __init__(self, path, account, conversation, *, jeff_consent, ownership, dispatch):
        if type(jeff_consent) is not JeffDraftConsentVerifier:
            raise MessageDraftError("JeffDraftConsentVerifier required")
        if not callable(ownership) or not callable(dispatch):
            raise MessageDraftError("ownership and dispatch adapters required")
        self.path, self.account, self.conversation = Path(path), account, conversation
        self.jeff_consent, self.ownership, self.dispatch = jeff_consent, ownership, dispatch
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
        if type(self.jeff_consent) is not JeffDraftConsentVerifier:
            raise MessageDraftError("JeffDraftConsentVerifier required")
        return JeffDraftConsentVerifier.verify(self.jeff_consent, draft_id, approved_digest, proof) is True

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
        if not domain.isascii() or _unicode_abuse(domain):
            raise MessageDraftError("single explicit recipient required")
        domain_lower = domain.lower()
        if any(label.startswith("xn--") for label in domain_lower.split(".")):
            raise MessageDraftError("single explicit recipient required")
        if domain_lower not in _ALLOWED_CONTACT_EMAIL_DOMAINS:
            raise MessageDraftError("single explicit recipient required")
        if not re.fullmatch(r"[A-Za-z0-9._%+-]+", local):
            raise MessageDraftError("single explicit recipient required")
        if not re.fullmatch(r"[A-Za-z0-9.-]+\.[A-Za-z0-9.-]+", domain_lower):
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
            if channel == "text":
                self.jeff_consent.link_approval_message_to_draft(payload["body"], draft_id, bound_digest)
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
