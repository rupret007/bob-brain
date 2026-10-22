"""Andrea mentions -> Web Bob drafts -> fresh Jeff approval -> fenced Andrea send.

This is a runtime adapter, not an autonomous sender. Model tools get only
``on_message``. ``approve_and_send`` belongs exclusively to the authenticated
Bob UI, with an approval verifier and Andrea's existing fenced send adapter.
There is no Grok path, standing authorization, background dispatch or retry.
"""
from dataclasses import dataclass
import hashlib
import json
import math
import os
import re
import secrets
import sqlite3
import threading
import time


class ReplyBlocked(RuntimeError):
    pass


@dataclass(frozen=True)
class JeffApproval:
    """Returned by the trusted Bob session verifier, never parsed from model text."""
    event_id: str
    principal: str
    surface: str
    draft_id: str
    digest: str
    approved_at: float
    decision: str = 'send_once'


def _digest(chat_guid, text):
    return hashlib.sha256(json.dumps([chat_guid, text], ensure_ascii=True,
                                    separators=(',', ':')).encode()).hexdigest()


def _text(value, maximum):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= maximum


class AndreaReplies:
    def __init__(self, path, *, webbob_draft, verify_jeff_approval, andrea_send_once,
                 clock=time.time):
        """Callbacks are trusted host configuration, never model-selected tools.

        webbob_draft receives same-thread data and returns only reply text.
        verify_jeff_approval verifies a fresh, authenticated Bob UI event and
        returns JeffApproval; a bool or caller-supplied identity is insufficient.
        andrea_send_once uses Andrea's existing approve-before-send boundary,
        enforces the bound digest and idempotency key, and never retries.
        """
        self._draft = webbob_draft
        self._verify = verify_jeff_approval
        self._send = andrea_send_once
        self._clock = clock
        self._lock = threading.RLock()
        # The runtime owns a private directory; never follow a planted DB symlink.
        fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        os.fchmod(fd, 0o600)
        os.close(fd)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.executescript('''
            CREATE TABLE IF NOT EXISTS andrea_replies (
                id TEXT PRIMARY KEY, source_id TEXT NOT NULL, chat_guid TEXT NOT NULL,
                text TEXT NOT NULL, digest TEXT NOT NULL, created REAL NOT NULL,
                expires REAL NOT NULL, state TEXT NOT NULL,
                UNIQUE(source_id, chat_guid)
            );
            CREATE TABLE IF NOT EXISTS andrea_reply_approvals (
                event_id TEXT PRIMARY KEY, draft_id TEXT NOT NULL
            );
        ''')

    @property
    def model_tools(self):
        """The drafting model has no approval or send tool."""
        return {'on_message': self.on_message}

    def close(self):
        self._db.close()

    @staticmethod
    def _preview(row):
        return {key: row[key] for key in ('id', 'chat_guid', 'text', 'digest', 'expires', 'state')}

    def on_message(self, event):
        """Draft only. The host supplies authenticated same-thread ingress data.

        No approval flags from a thread, routine or model are honored. Unknown
        fields are rejected, including caller-supplied send/standing permissions.
        """
        if (not isinstance(event, dict) or set(event) != {'id', 'chat_guid', 'text', 'history'}
                or not _text(event['id'], 256) or not _text(event['chat_guid'], 512)
                or not _text(event['text'], 8000) or not isinstance(event['history'], list)
                or len(event['history']) > 20):
            raise ReplyBlocked('Invalid Andrea mention')
        if not re.search(r'(?<!\w)@andrea\b', event['text'], re.I):
            return None
        history = []
        for message in event['history']:
            if (not isinstance(message, dict) or set(message) != {'chat_guid', 'text'}
                    or message['chat_guid'] != event['chat_guid']
                    or not _text(message['text'], 8000)):
                raise ReplyBlocked('Only same-thread context is permitted')
            history.append({'chat_guid': message['chat_guid'], 'text': message['text']})
        with self._lock:
            existing = self._db.execute('SELECT * FROM andrea_replies WHERE source_id=? AND chat_guid=?',
                                        (event['id'], event['chat_guid'])).fetchone()
            if existing:
                return self._preview(existing)
            try:
                body = self._draft({'chat_guid': event['chat_guid'], 'mention': event['text'],
                                    'history': history, 'mode': 'draft_only'})
            except Exception:
                raise ReplyBlocked('Web Bob unavailable; draft held, no fallback or send') from None
            if not _text(body, 3500):
                raise ReplyBlocked('Web Bob returned no usable draft')
            # The exact wrapper appears in Jeff's preview and is covered by approval.
            text = 'NanoBot: ' + body.strip() + '\n— NanoBot via Bob'
            draft_id = secrets.token_hex(24)
            now = self._clock()
            with self._db:
                # A new mention supersedes unsent drafts for that same thread.
                self._db.execute("UPDATE andrea_replies SET state='superseded' WHERE chat_guid=? AND state='pending'",
                                 (event['chat_guid'],))
                self._db.execute('INSERT INTO andrea_replies VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                                 (draft_id, event['id'], event['chat_guid'], text,
                                  _digest(event['chat_guid'], text), now, now + 300, 'pending'))
            row = self._db.execute('SELECT * FROM andrea_replies WHERE id=?', (draft_id,)).fetchone()
            return self._preview(row)

    def approve_and_send(self, authenticated_ui_event):
        """Host-only handler: exact preview + fresh Jeff event + one send attempt.

        The durable claim happens before calling Andrea. A crash or ambiguous
        delivery consumes the approval; Jeff must review a new draft to retry.
        The adapter has no background worker that can send later.
        """
        try:
            approval = self._verify(authenticated_ui_event)
        except Exception:
            raise ReplyBlocked('Jeff approval could not be verified') from None
        if (not isinstance(approval, JeffApproval) or approval.principal != 'jeff'
                or approval.surface != 'bob_chat' or approval.decision != 'send_once'
                or not _text(approval.event_id, 256)
                or type(approval.approved_at) not in (int, float)
                or not math.isfinite(approval.approved_at)):
            raise ReplyBlocked('Fresh separate Jeff approval in Bob chat is required')
        with self._lock:
            # BEGIN IMMEDIATE serializes claims across processes, not just threads.
            self._db.execute('BEGIN IMMEDIATE')
            try:
                row = self._db.execute('SELECT * FROM andrea_replies WHERE id=?', (approval.draft_id,)).fetchone()
                now = self._clock()
                if (not row or row['state'] != 'pending' or approval.digest != row['digest']
                        or row['digest'] != _digest(row['chat_guid'], row['text'])
                        or not row['created'] <= approval.approved_at <= now < row['expires']
                        or now - approval.approved_at > 60):
                    raise ReplyBlocked('Approval is stale or does not match the current exact draft')
                self._db.execute('INSERT INTO andrea_reply_approvals VALUES (?, ?)',
                                 (approval.event_id, row['id']))
                self._db.execute("UPDATE andrea_replies SET state='attempted' WHERE id=?", (row['id'],))
                self._db.commit()
            except sqlite3.IntegrityError:
                self._db.rollback()
                raise ReplyBlocked('Approval already consumed') from None
            except Exception:
                self._db.rollback()
                raise
            try:
                self._send(chat_guid=row['chat_guid'], text=row['text'],
                           approval=approval, idempotency_key=row['id'])
            except Exception:
                raise ReplyBlocked('Andrea delivery unconfirmed; approval consumed, no automatic retry') from None
            # Do not claim delivered without Andrea's independently verified receipt.
            return {'id': row['id'], 'state': 'submitted', 'automatic_retry': False}


def build_router(path, *, webbob_draft, verify_jeff_approval, andrea_send_once, clock=time.time):
    """Runtime binding point. The shipped route cannot select Grok or auto-send."""
    from pathlib import Path
    config = json.loads((Path(__file__).parents[1] / 'config/andrea-routing.json').read_text())
    if (config.get('brain') != 'webbob' or config.get('fallback') is not None
            or config.get('standing_permission') is not False
            or config.get('automatic_retry') is not False
            or config.get('model_surface') != ['on_message']):
        raise ReplyBlocked('Andrea route must use Web Bob and fresh per-send approval')
    return AndreaReplies(path, webbob_draft=webbob_draft,
                         verify_jeff_approval=verify_jeff_approval,
                         andrea_send_once=andrea_send_once, clock=clock)
