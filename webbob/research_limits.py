"""Hard daily caps for paid research tools (fail closed)."""
import json
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo

from webbob.spend_cap import SpendCap
from webbob.ai_capacity import AiCapacity

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


_RESEARCH_BILLING = Path(__file__).resolve().parent.parent / "config" / "research-billing.json"
_RESEARCH_CAP_STORE = Path.home() / "Documents/bob-overnight-inject/conductor/research-caps"


def _billing():
    data = json.loads(_RESEARCH_BILLING.read_text(encoding="utf-8"))
    if data.get("brave_spend_model") != BRAVE_SPEND_MODEL:
        raise ValueError("research billing config must name brave_search model")
    daily = data.get("default_daily_query_cap", DEFAULT_BRAVE_DAILY_QUERY_CAP)
    cost = data.get("cost_per_query_microdollars", BRAVE_QUERY_COST_MICRODOLLARS)
    if type(daily) is not int or not 1 <= daily <= 10_000:
        raise ValueError("explicit daily query cap required")
    if type(cost) is not int or not 0 < cost < 10**12:
        raise ValueError("explicit per-query microdollar cost required")
    monthly = data.get("default_monthly_spend_cap_microdollars")
    if monthly is None:
        monthly = daily * cost * 31
    if type(monthly) is not int or not 0 < monthly < 10**12:
        raise ValueError("explicit monthly spend cap required")
    return daily, cost, monthly


def research_spend_and_daily_caps():
    """Durable Brave spend and daily query caps for the live research host."""
    billing = _billing()
    daily_limit, cost, monthly = billing
    _RESEARCH_CAP_STORE.mkdir(parents=True, exist_ok=True)
    spend = SpendCap(_RESEARCH_CAP_STORE / "spend.sqlite", {BRAVE_SPEND_MODEL: monthly},
                     capacity_snapshot=AiCapacity().snapshot)
    daily = DailyQueryCap(_RESEARCH_CAP_STORE / "daily.sqlite", limit=daily_limit)
    return spend, daily, cost
