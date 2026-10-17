"""Durable outbound chat reply journal: idempotent IDs, bounded retry, no duplicate send."""
import asyncio
from contextlib import contextmanager
import hashlib
import re
import sqlite3
import time

MAX_ATTEMPTS = 3
BACKOFF_BASE_SECONDS = 1.0
REPLY_ID = re.compile(r"[a-zA-Z0-9_.:-]{1,100}")


class ChatReplyError(ValueError):
    pass


def body_digest(body):
    if not isinstance(body, str) or not body or len(body) > 32_000:
        raise ChatReplyError("invalid reply body")
    return hashlib.sha256(body.encode()).hexdigest()


def retry_delay(attempt):
    return min(30.0, BACKOFF_BASE_SECONDS * (2 ** max(0, attempt - 1)))


class ChatReplyJournal:
    """Per-conversation store for one visible assistant reply per stable message id."""

    def __init__(self, path, conversation):
        if not isinstance(conversation, str) or not conversation:
            raise ChatReplyError("conversation required")
        self.path, self.conversation = path, conversation
        if not self.path.parent.is_dir() or self.path.is_symlink():
            raise ChatReplyError("private reply store unavailable")
        with self.db() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS replies (
                id TEXT PRIMARY KEY, conversation TEXT NOT NULL, body_digest TEXT NOT NULL,
                state TEXT NOT NULL, receipt TEXT, attempts INTEGER NOT NULL,
                next_retry_at REAL, updated_at REAL NOT NULL)""")
        self.path.chmod(0o600)

    @contextmanager
    def db(self):
        conn = sqlite3.connect(self.path, timeout=5)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _row(self, db, reply_id):
        row = db.execute("SELECT * FROM replies WHERE id=?", (reply_id,)).fetchone()
        if not row:
            return None
        if row["conversation"] != self.conversation:
            raise ChatReplyError("reply ownership mismatch")
        return row

    def _snapshot(self, row):
        return {"id": row["id"], "state": row["state"], "receipt": row["receipt"],
                "attempts": row["attempts"], "next_retry_at": row["next_retry_at"]}

    def prepare(self, reply_id, body):
        if not REPLY_ID.fullmatch(reply_id):
            raise ChatReplyError("invalid reply id")
        digest = body_digest(body)
        now = time.time()
        with self.db() as db:
            prior = self._row(db, reply_id)
            if prior:
                if prior["body_digest"] != digest:
                    raise ChatReplyError("reply id reused with different body")
                return self._snapshot(prior)
            db.execute("""INSERT INTO replies(id,conversation,body_digest,state,receipt,attempts,next_retry_at,updated_at)
                VALUES (?,?,?,?,NULL,0,NULL,?)""",
                       (reply_id, self.conversation, digest, "queued", now))
            row = self._row(db, reply_id)
        return self._snapshot(row)

    def status(self, reply_id):
        with self.db() as db:
            row = self._row(db, reply_id)
            if not row:
                raise ChatReplyError("unknown reply")
            return self._snapshot(row)

    async def deliver(self, reply_id, body, send, *, now=None):
        if not callable(send):
            raise ChatReplyError("transport adapter required")
        now = time.time() if now is None else now
        digest = body_digest(body)
        self.prepare(reply_id, body)
        with self.db() as db:
            row = self._row(db, reply_id)
            if row["state"] == "delivered":
                return self._snapshot(row)
            if row["state"] == "in_flight":
                return self._snapshot(row)
            if row["state"] == "failed":
                return self._snapshot(row)
            if row["state"] == "failed_retry" and row["next_retry_at"] is not None and now < row["next_retry_at"]:
                return self._snapshot(row)
            if row["attempts"] >= MAX_ATTEMPTS:
                db.execute("UPDATE replies SET state='failed', updated_at=? WHERE id=?", (now, reply_id))
                row = self._row(db, reply_id)
                return self._snapshot(row)
            attempts = row["attempts"] + 1
            db.execute("UPDATE replies SET state='in_flight', attempts=?, updated_at=? WHERE id=?",
                       (attempts, now, reply_id))
        try:
            receipt = await asyncio.wait_for(send(body), 30)
            if not isinstance(receipt, str) or not receipt:
                raise ChatReplyError("transport receipt required")
        except Exception:
            delay = retry_delay(attempts)
            next_at = now + delay
            terminal = attempts >= MAX_ATTEMPTS
            state = "failed" if terminal else "failed_retry"
            with self.db() as db:
                db.execute("""UPDATE replies SET state=?, receipt=NULL, next_retry_at=?, updated_at=? WHERE id=?""",
                           (state, None if terminal else next_at, now, reply_id))
                row = self._row(db, reply_id)
            return self._snapshot(row)
        with self.db() as db:
            db.execute("UPDATE replies SET state='delivered', receipt=?, next_retry_at=NULL, updated_at=? WHERE id=?",
                       (receipt, now, reply_id))
            row = self._row(db, reply_id)
        return self._snapshot(row)
