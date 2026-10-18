"""Morning calendar routine: once per America/Chicago day, read-only today's events."""
from contextlib import contextmanager
from datetime import datetime, time, timedelta
from pathlib import Path
import sqlite3

from webbob.reminders import CHICAGO
from webbob.workspace import WorkspaceError

MORNING = time(7, 0)


class MorningCalendarError(ValueError):
    pass


class MorningCalendarRoutine:
    def __init__(self, path, clock=None, morning=MORNING):
        self.path = Path(path)
        self.clock = clock or (lambda: datetime.now(CHICAGO))
        self.morning = morning
        self._reject_symlink_path()
        if not self.path.parent.is_dir():
            raise MorningCalendarError("morning calendar routine unavailable")
        with self.db() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS morning_calendar_routine (
                state TEXT NOT NULL,
                last_fired_chicago_date TEXT)""")
            if db.execute("SELECT COUNT(*) FROM morning_calendar_routine").fetchone()[0] == 0:
                db.execute("INSERT INTO morning_calendar_routine VALUES ('active', NULL)")
        self.path.chmod(0o600)

    def _reject_symlink_path(self):
        for part in (self.path, *self.path.parents):
            if part.is_symlink():
                raise MorningCalendarError("morning calendar routine unavailable")

    @contextmanager
    def db(self):
        self._reject_symlink_path()
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

    def _row(self, db):
        row = db.execute("SELECT state, last_fired_chicago_date FROM morning_calendar_routine").fetchone()
        return row["state"], row["last_fired_chicago_date"]

    def _chicago_now(self):
        now = self.clock()
        if now.tzinfo is None:
            raise MorningCalendarError("timezone-aware clock required")
        return now.astimezone(CHICAGO)

    def _chicago_date(self, when):
        return when.date().isoformat()

    def _morning_reached(self, when):
        start = datetime.combine(when.date(), self.morning, tzinfo=CHICAGO)
        return when >= start

    def _day_bounds(self, when):
        start = datetime.combine(when.date(), time(0, 0), tzinfo=CHICAGO)
        end = start + timedelta(days=1)
        return start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds")

    def cancel(self):
        with self.db() as db:
            state, _ = self._row(db)
            if state == "cancelled":
                raise MorningCalendarError("morning calendar routine already cancelled")
            db.execute("UPDATE morning_calendar_routine SET state='cancelled'")

    def _mark_fired(self, chicago_date):
        with self.db() as db:
            db.execute("UPDATE morning_calendar_routine SET last_fired_chicago_date=?", (chicago_date,))

    async def run_due(self, workspace):
        when = self._chicago_now()
        with self.db() as db:
            state, last_fired = self._row(db)
        if state == "cancelled":
            return None
        chicago_date = self._chicago_date(when)
        if not self._morning_reached(when) or last_fired == chicago_date:
            return None
        time_min, time_max = self._day_bounds(when)
        try:
            calendar = await workspace.read(
                "get_events",
                {"calendar_id": "primary", "time_min": time_min, "time_max": time_max, "max_results": 20},
            )
        except WorkspaceError as exc:
            self._mark_fired(chicago_date)
            return {"chicago_date": chicago_date, "ok": False, "error": str(exc), "calendar": None}
        self._mark_fired(chicago_date)
        return {"chicago_date": chicago_date, "ok": True, "error": None, "calendar": calendar}
