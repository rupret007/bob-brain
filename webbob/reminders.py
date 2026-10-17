"""Persisted one-time reminders with due evaluation in America/Chicago."""
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import uuid
from zoneinfo import ZoneInfo

CHICAGO = ZoneInfo("America/Chicago")
MAX_PENDING_PER_OWNER = 100
_LATEST_DUE_UTC = datetime(2099, 12, 31, 23, 59, 59, tzinfo=timezone.utc)


class ReminderError(ValueError):
    pass


class ReminderStore:
    def __init__(self, path, owner, clock=None):
        self.path = Path(path)
        self.owner = self._validate_owner(owner)
        self.clock = clock or (lambda: datetime.now(CHICAGO))
        if not self.path.parent.is_dir() or self.path.is_symlink():
            raise ReminderError("reminder store unavailable")
        with self.db() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS reminders (
                id TEXT PRIMARY KEY,
                owner TEXT NOT NULL,
                body TEXT NOT NULL,
                due_utc REAL NOT NULL,
                state TEXT NOT NULL)"""
            )
        self.path.chmod(0o600)
        self._now_utc()

    @staticmethod
    def _validate_owner(owner):
        if not isinstance(owner, str) or not owner.strip():
            raise ReminderError("owner required")
        return owner

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

    def _now_utc(self):
        now = self.clock()
        if now.tzinfo is None:
            raise ReminderError("timezone-aware clock required")
        return now.astimezone(timezone.utc)

    @staticmethod
    def _parse_due(due_at):
        if isinstance(due_at, str):
            try:
                due_at = datetime.fromisoformat(due_at.replace("Z", "+00:00"))
            except ValueError:
                raise ReminderError("explicit due time required")
        if not isinstance(due_at, datetime):
            raise ReminderError("explicit due time required")
        if due_at.tzinfo is None:
            fold0 = due_at.replace(tzinfo=CHICAGO, fold=0)
            fold1 = due_at.replace(tzinfo=CHICAGO, fold=1)
            if fold0.timestamp() != fold1.timestamp():
                raise ReminderError("ambiguous or nonexistent local time in Chicago")
            due_at = due_at.replace(tzinfo=CHICAGO)
        else:
            due_at = due_at.astimezone(CHICAGO)
        try:
            due_utc = due_at.astimezone(timezone.utc)
        except (OverflowError, OSError, ValueError) as exc:
            raise ReminderError("invalid due time") from exc
        if due_utc > _LATEST_DUE_UTC:
            raise ReminderError("due time too far in the future")
        return due_utc

    @staticmethod
    def _validate_body(body):
        if not isinstance(body, str) or not 1 <= len(body) <= 2000:
            raise ReminderError("reminder body must be 1..2000 characters")

    @staticmethod
    def _row(row):
        due = datetime.fromtimestamp(row["due_utc"], tz=timezone.utc).astimezone(CHICAGO)
        return {
            "id": row["id"],
            "owner": row["owner"],
            "body": row["body"],
            "state": row["state"],
            "due_chicago": due.isoformat(timespec="seconds"),
        }

    def _owned(self, rows):
        return [row for row in rows if row["owner"] == self.owner]

    def _fetch_owned(self, db, reminder_id):
        row = db.execute(
            "SELECT * FROM reminders WHERE id=? AND owner=?",
            (reminder_id, self.owner),
        ).fetchone()
        if row is None:
            raise ReminderError("unknown reminder")
        return row

    def create(self, body, due_at):
        self._validate_body(body)
        due_utc = self._parse_due(due_at)
        now_utc = self._now_utc()
        if due_utc.timestamp() < now_utc.timestamp():
            raise ReminderError("due time must be in the future")
        reminder_id = str(uuid.uuid4())
        with self.db() as db:
            pending = db.execute(
                "SELECT COUNT(*) AS n FROM reminders WHERE owner=? AND state='pending'",
                (self.owner,),
            ).fetchone()["n"]
            if pending >= MAX_PENDING_PER_OWNER:
                raise ReminderError("reminder limit reached")
            try:
                db.execute(
                    "INSERT INTO reminders VALUES (?,?,?,?,?)",
                    (reminder_id, self.owner, body, due_utc.timestamp(), "pending"),
                )
            except (OverflowError, ValueError) as exc:
                raise ReminderError("invalid due time") from exc
        return self.get(reminder_id)

    def list(self):
        with self.db() as db:
            rows = db.execute(
                "SELECT * FROM reminders WHERE state='pending' ORDER BY due_utc"
            ).fetchall()
        return [self._row(row) for row in self._owned(rows)]

    def get(self, reminder_id):
        with self.db() as db:
            row = self._fetch_owned(db, reminder_id)
        return self._row(row)

    def cancel(self, reminder_id):
        with self.db() as db:
            row = self._fetch_owned(db, reminder_id)
            if row["state"] != "pending":
                raise ReminderError("only pending reminders may be cancelled")
            db.execute(
                "UPDATE reminders SET state='cancelled' WHERE id=? AND owner=?",
                (reminder_id, self.owner),
            )
        return self.get(reminder_id)

    def collect_due(self):
        now_utc = self._now_utc().timestamp()
        with self.db() as db:
            rows = db.execute(
                "SELECT * FROM reminders WHERE state='pending' AND due_utc <= ? ORDER BY due_utc",
                (now_utc,),
            ).fetchall()
        return [self._row(row) for row in self._owned(rows)]

    def mark_fired(self, reminder_id):
        with self.db() as db:
            row = self._fetch_owned(db, reminder_id)
            if row["state"] in ("fired", "cancelled"):
                raise ReminderError("only pending reminders may be marked fired")
            db.execute("UPDATE reminders SET state='fired' WHERE id=?", (row["id"],))
        return self.get(reminder_id)
