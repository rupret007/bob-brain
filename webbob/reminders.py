"""Persisted one-time reminders with due evaluation in America/Chicago."""
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import uuid
from zoneinfo import ZoneInfo

CHICAGO = ZoneInfo("America/Chicago")
class ReminderError(ValueError):
    pass


class ReminderStore:
    def __init__(self, path, clock=None):
        self.path = Path(path)
        self.clock = clock or (lambda: datetime.now(CHICAGO))
        if not self.path.parent.is_dir() or self.path.is_symlink():
            raise ReminderError("reminder store unavailable")
        with self.db() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS reminders (
                id TEXT PRIMARY KEY,
                body TEXT NOT NULL,
                due_utc REAL NOT NULL,
                state TEXT NOT NULL)""")
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

    def _now_utc(self):
        now = self.clock()
        if now.tzinfo is None:
            raise ReminderError("timezone-aware clock required")
        return now.astimezone(timezone.utc)

    @staticmethod
    def _parse_due(due_at):
        if isinstance(due_at, str):
            due_at = datetime.fromisoformat(due_at)
        if not isinstance(due_at, datetime):
            raise ReminderError("explicit due time required")
        if due_at.tzinfo is None:
            due_at = due_at.replace(tzinfo=CHICAGO)
        else:
            due_at = due_at.astimezone(CHICAGO)
        return due_at.astimezone(timezone.utc)

    @staticmethod
    def _validate_body(body):
        if not isinstance(body, str) or not 1 <= len(body) <= 2000:
            raise ReminderError("reminder body must be 1..2000 characters")

    @staticmethod
    def _row(row):
        due = datetime.fromtimestamp(row["due_utc"], tz=timezone.utc).astimezone(CHICAGO)
        return {"id": row["id"], "body": row["body"], "state": row["state"],
                "due_chicago": due.isoformat(timespec="seconds")}

    def create(self, body, due_at):
        self._validate_body(body)
        due_utc = self._parse_due(due_at).timestamp()
        reminder_id = str(uuid.uuid4())
        with self.db() as db:
            db.execute("INSERT INTO reminders VALUES (?,?,?,?)",
                       (reminder_id, body, due_utc, "pending"))
        return self.get(reminder_id)

    def list(self):
        with self.db() as db:
            rows = db.execute("SELECT * FROM reminders WHERE state='pending' ORDER BY due_utc").fetchall()
        return [self._row(row) for row in rows]

    def get(self, reminder_id):
        with self.db() as db:
            row = db.execute("SELECT * FROM reminders WHERE id=?", (reminder_id,)).fetchone()
        if row is None:
            raise ReminderError("unknown reminder")
        return self._row(row)

    def cancel(self, reminder_id):
        with self.db() as db:
            row = db.execute("SELECT state FROM reminders WHERE id=?", (reminder_id,)).fetchone()
            if row is None:
                raise ReminderError("unknown reminder")
            if row["state"] != "pending":
                raise ReminderError("only pending reminders may be cancelled")
            db.execute("UPDATE reminders SET state='cancelled' WHERE id=?", (reminder_id,))
        return self.get(reminder_id)

    def collect_due(self):
        now_utc = self._now_utc().timestamp()
        with self.db() as db:
            rows = db.execute(
                "SELECT * FROM reminders WHERE state='pending' AND due_utc <= ? ORDER BY due_utc",
                (now_utc,)).fetchall()
            fired = [self._row(row) for row in rows]
            for row in rows:
                db.execute("UPDATE reminders SET state='fired' WHERE id=?", (row["id"],))
        return fired
