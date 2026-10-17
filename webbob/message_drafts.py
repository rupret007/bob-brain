"""Text and email outbound drafts with explicit human approval only.

Web Bob presents the exact draft; transport runs only after consent bound to the
current digest. Routines, timers, and background jobs must never call execute().
"""
import asyncio
from contextlib import contextmanager
import json
from pathlib import Path
import re
import sqlite3
import time
import uuid

from webbob.workspace import fingerprint

ALLOWED_SEND_TRIGGERS = frozenset({"explicit_approval"})


class MessageDraftError(ValueError):
    pass


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
    return {
        "id": binding["id"],
        "channel": channel,
        "digest": binding["digest"],
        "revision": binding["revision"],
        "state": binding["state"],
        "preview": preview,
        "send_authorized": False,
    }


class MessageDraftGate:
    def __init__(self, path, account, conversation, *, verify_consent, ownership, dispatch):
        if not all(callable(f) for f in (verify_consent, ownership, dispatch)):
            raise MessageDraftError("consent verifier, ownership and dispatch adapters required")
        self.path, self.account, self.conversation = Path(path), account, conversation
        self.verify, self.ownership, self.dispatch = verify_consent, ownership, dispatch
        if not self.path.parent.is_dir() or self.path.is_symlink():
            raise MessageDraftError("private store unavailable")
        with self.db() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS message_drafts (
                id TEXT PRIMARY KEY, account TEXT, conversation TEXT, channel TEXT,
                payload TEXT, revision INTEGER, digest TEXT, state TEXT, receipt TEXT, expires REAL)"""
            )
        self.path.chmod(0o600)

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
        else:
            if not re.fullmatch(r"[^\s@,;<>]+@[^\s@,;<>]+\.[^\s@,;<>]+", payload["to"]):
                raise MessageDraftError("single explicit recipient required")
            if "\n" in payload["subject"] or "\r" in payload["subject"]:
                raise MessageDraftError("plain single-line subject required")
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
                    time.time() + 900,
                ),
            )
        return dict(binding, digest=bound_digest, state="draft")

    def receipt(self, draft_id):
        with self.db() as db:
            row = self._owned(db, draft_id)
            return {"id": draft_id, "digest": row["digest"], "state": row["state"], "receipt": row["receipt"]}

    async def execute(self, draft_id, approved_digest, proof, *, writes_enabled=False, trigger="explicit_approval"):
        if trigger not in ALLOWED_SEND_TRIGGERS:
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
                if self.verify(approved_digest, proof) is not True:
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
