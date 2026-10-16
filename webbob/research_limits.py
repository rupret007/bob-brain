"""Hard daily caps for paid research tools (fail closed)."""
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo

DEFAULT_BRAVE_DAILY_QUERY_CAP = 50
BRAVE_QUERY_COST_MICRODOLLARS = 5000  # Brave Search API public list price ~$5 / 1k queries.
BRAVE_SPEND_MODEL = "brave_search"


class DailyQueryCap:
    def __init__(self, path, limit=DEFAULT_BRAVE_DAILY_QUERY_CAP, clock=None):
        if type(limit) is not int or not 1 <= limit <= 10_000:
            raise ValueError("explicit positive daily query cap required")
        self.path = Path(path)
        self.limit = limit
        self.clock = clock or (lambda: datetime.now(ZoneInfo("America/Chicago")))
        if not self.path.parent.is_dir() or self.path.is_symlink():
            raise ValueError("query cap store unavailable")
        with self.db() as db:
            db.execute("CREATE TABLE IF NOT EXISTS daily(day TEXT PRIMARY KEY, count INTEGER NOT NULL)")
        self.path.chmod(0o600)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=5)
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _day(self):
        now = self.clock()
        if now.tzinfo is None:
            raise ValueError("timezone-aware clock required")
        return now.astimezone(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d")

    def admit(self):
        day = self._day()
        with self.db() as db:
            count = db.execute("SELECT count FROM daily WHERE day=?", (day,)).fetchone()
            used = count[0] if count else 0
            if used >= self.limit:
                return False
            if count:
                db.execute("UPDATE daily SET count=count+1 WHERE day=?", (day,))
            else:
                db.execute("INSERT INTO daily VALUES (?,1)", (day,))
        return True
