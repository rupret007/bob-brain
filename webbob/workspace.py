"""Read-first community Workspace MCP facade and host-only consent adapter.

No OAuth code, raw Google client, or automatic credential discovery exists here.
The caller supplies a connected MCP session only after Jeff's consent/scopes.
"""
import asyncio
from contextlib import contextmanager
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import time
import uuid
from zoneinfo import ZoneInfo

NEEDS_JEFF = "needs Jeff: OAuth consent + scopes"
READ_TOOLS = {"search_gmail_messages", "get_gmail_message_content", "get_events", "search_drive_files", "get_drive_file_content"}
WRITE_TOOLS = {"email": "send_gmail_message", "event": "manage_event"}


class WorkspaceError(ValueError):
    pass


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class Workspace:
    def __init__(self, session=None, *, account, consent_verified=False):
        self.session, self.account, self.consent_verified = session, account, consent_verified

    async def read(self, tool, arguments):
        if tool not in READ_TOOLS:
            raise WorkspaceError("read-only tool boundary")
        if not self.consent_verified or self.session is None:
            raise WorkspaceError(NEEDS_JEFF)
        if "user_google_email" in arguments and arguments["user_google_email"] != self.account:
            raise WorkspaceError("account mismatch")
        arguments = dict(arguments, user_google_email=self.account)
        try:
            result = await asyncio.wait_for(self.session.call_tool(tool, arguments), 20)
        except Exception:
            raise WorkspaceError("Workspace read unavailable") from None
        if result.isError:
            raise WorkspaceError("Workspace read failed; check connection/scopes")
        text = "\n".join(c.text for c in result.content if c.type == "text")
        return {"source_tool": tool, "source_arguments": arguments, "retrieved_at": time.time(),
                "text": text[:16000], "truncated": len(text) > 16000,
                "private": True, "execution_authority": False}

    async def daily_brief(self, time_min, time_max):
        # This supplies source evidence for the existing conversational renderer.
        return [await self.read("search_gmail_messages", {"query": "newer_than:1d", "page_size": 10, "include_headers": True}),
                await self.read("get_events", {"calendar_id": "primary", "time_min": time_min, "time_max": time_max, "max_results": 20})]

    async def locate_document(self, query):
        return await self.read("search_drive_files", {"query": query, "page_size": 10})


class Drafts:
    """Private drafts and receipts. Wire to existing exact-consent card verifier.

    prepare/edit are safe local operations. execute is trusted-host only and
    requires both a verifier and an ownership context; never expose raw writes.
    """
    def __init__(self, path, account, conversation, *, verify_consent, ownership):
        if not callable(verify_consent) or not callable(ownership):
            raise WorkspaceError("existing consent and ownership adapters required")
        self.path, self.account, self.conversation = Path(path), account, conversation
        self.verify, self.ownership = verify_consent, ownership
        if not self.path.parent.is_dir() or self.path.is_symlink():
            raise WorkspaceError("private store unavailable")
        with self.db() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS drafts (
                id TEXT PRIMARY KEY, account TEXT, conversation TEXT, kind TEXT,
                payload TEXT, revision INTEGER, digest TEXT, state TEXT, receipt TEXT, expires REAL)""")
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

    def _payload(self, kind, payload):
        allowed = {"email": {"to", "subject", "body"}, "event": {"calendar_id", "summary", "start_time", "end_time", "timezone"}}
        if kind not in allowed or set(payload) != allowed[kind]:
            raise WorkspaceError("exact supported draft fields required")
        if any(not isinstance(v, str) or not v or len(v) > 10000 for v in payload.values()):
            raise WorkspaceError("invalid draft value")
        if kind == "email" and (not re.fullmatch(r"[^\s@,;<>]+@[^\s@,;<>]+\.[^\s@,;<>]+", payload["to"])
                                or "\n" in payload["subject"] or "\r" in payload["subject"]):
            raise WorkspaceError("single explicit recipient and plain subject required")
        if kind == "event":
            try:
                start, end = datetime.fromisoformat(payload["start_time"]), datetime.fromisoformat(payload["end_time"])
                ZoneInfo(payload["timezone"])
                if not start.tzinfo or not end.tzinfo or end <= start:
                    raise ValueError()
            except (ValueError, KeyError):
                raise WorkspaceError("explicit valid event times and timezone required") from None
            payload = dict(payload, action="create", visibility="private", send_updates="none", attendees=[], add_google_meet=False)
        else:
            payload = dict(payload, body_format="plain", include_signature=False, quote_original=False, reply_all=False)
        return dict(payload, user_google_email=self.account)

    def _owned(self, db, draft_id):
        row = db.execute("SELECT * FROM drafts WHERE id=?", (draft_id,)).fetchone()
        if not row or row["account"] != self.account or row["conversation"] != self.conversation:
            raise WorkspaceError("draft ownership mismatch")
        return row

    def prepare(self, kind, payload, draft_id=None):
        payload = self._payload(kind, payload)
        with self.db() as db:
            revision = 1
            if draft_id:
                old = self._owned(db, draft_id)
                if old["state"] != "draft":
                    raise WorkspaceError("attempted drafts cannot be edited or retried")
                revision = old["revision"] + 1
            draft_id = draft_id or uuid.uuid4().hex
            binding = {"id": draft_id, "account": self.account, "conversation": self.conversation,
                       "kind": kind, "payload": payload, "revision": revision}
            bound_digest = fingerprint(binding)
            db.execute("INSERT OR REPLACE INTO drafts VALUES (?,?,?,?,?,?,?,'draft',NULL,?)",
                       (draft_id, self.account, self.conversation, kind, json.dumps(payload), revision,
                        bound_digest, time.time() + 900))
        return dict(binding, digest=bound_digest, state="draft")

    def receipt(self, draft_id):
        with self.db() as db:
            row = self._owned(db, draft_id)
            return {"id": draft_id, "digest": row["digest"], "state": row["state"], "receipt": row["receipt"]}

    async def execute(self, draft_id, approved_digest, proof, session, *, writes_enabled=False):
        if not writes_enabled:
            raise WorkspaceError("writes disabled; separate scopes and exact consent required")
        # Ownership callback holds the actual shared lease across the effect.
        with self.ownership(draft_id):
            with self.db() as db:
                row = self._owned(db, draft_id)
                if row["state"] != "draft":
                    return {"id": draft_id, "state": row["state"], "receipt": row["receipt"]}
                if row["digest"] != approved_digest or row["expires"] <= time.time():
                    raise WorkspaceError("stale approval")
                if self.verify(approved_digest, proof) is not True:
                    raise WorkspaceError("exact consent missing or consumed")
                # Durable uncertainty precedes transport. No automatic retry even
                # if the process exits after dispatch and before response storage.
                db.execute("UPDATE drafts SET state='uncertain' WHERE id=?", (draft_id,))
                tool, payload = WRITE_TOOLS[row["kind"]], json.loads(row["payload"])
            try:
                result = await asyncio.wait_for(session.call_tool(tool, payload), 30)
                if result.isError:
                    return self.receipt(draft_id)
                # Keep only a digest of the transport receipt in this journal.
                receipt = fingerprint(result.model_dump(mode="json"))
            except Exception:
                return self.receipt(draft_id)
            with self.db() as db:
                db.execute("UPDATE drafts SET state='submitted',receipt=? WHERE id=?", (receipt, draft_id))
            return self.receipt(draft_id)
