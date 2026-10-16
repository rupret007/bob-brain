"""Transactional per-model monthly caps, supplementary to existing global caps."""
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
import sqlite3
from typing import Optional
from zoneinfo import ZoneInfo

LOW_QUOTA_REMAINING_PCT = 5

# Model ids map to provider labels in ai-capacity rows (substring match, case-insensitive).
MODEL_PROVIDER_HINTS = {
    "codex": ("codex",),
    "claude": ("claude",),
    "minimax": ("minimax",),
    "gemini": ("gemini",),
    "grok": ("grok", "xai"),
    "xai": ("grok", "xai"),
    "cursor": ("cursor",),
}


def _model_hint(model: str) -> Optional[str]:
    lower = model.lower()
    for hint, needles in MODEL_PROVIDER_HINTS.items():
        if hint in lower or any(n in lower for n in needles):
            return hint
    return None


def match_capacity_row(model: str, rows: list) -> Optional[dict]:
    hint = _model_hint(model)
    if not hint or not isinstance(rows, list):
        return None
    needles = MODEL_PROVIDER_HINTS.get(hint, ())
    for row in rows:
        if not isinstance(row, dict):
            continue
        provider = str(row.get("provider") or "").lower()
        if any(n in provider for n in needles):
            return row
    return None


def provider_quota_check(model: str, capacity_doc: Optional[dict]) -> dict:
    """Fail closed when remaining_pct is known and below threshold; unknown is not low."""
    if not isinstance(capacity_doc, dict):
        return {"low_quota": False, "unknown_quota": True, "flagged": True, "reason": "no_capacity_snapshot"}
    row = match_capacity_row(model, capacity_doc.get("rows") or [])
    if row is None:
        return {"low_quota": False, "unknown_quota": True, "flagged": True, "reason": "provider_unmatched"}
    remaining = row.get("remaining_pct")
    if remaining is None:
        return {"low_quota": False, "unknown_quota": True, "flagged": True, "reason": "remaining_unknown",
                "provider": row.get("provider")}
    if remaining < LOW_QUOTA_REMAINING_PCT:
        return {"low_quota": True, "unknown_quota": False, "flagged": False, "reason": "provider_quota_low",
                "provider": row.get("provider"), "remaining_pct": remaining}
    return {"low_quota": False, "unknown_quota": False, "flagged": False, "reason": "ok",
            "provider": row.get("provider"), "remaining_pct": remaining}


class SpendCap:
    def __init__(self, path, caps, clock=None, capacity_snapshot=None):
        if not caps or any(not isinstance(k, str) or type(v) is not int or not 0 <= v < 10**12 for k, v in caps.items()):
            raise ValueError("explicit model caps in integer microdollars required")
        self.path, self.caps = Path(path), dict(caps)
        self.clock = clock or (lambda: datetime.now(ZoneInfo("America/Chicago")))
        self._capacity_snapshot = capacity_snapshot
        if not self.path.parent.is_dir() or self.path.is_symlink():
            raise ValueError("budget store unavailable")
        with self.db() as db:
            db.execute("CREATE TABLE IF NOT EXISTS spend(id TEXT PRIMARY KEY, model TEXT, month TEXT, reserved INTEGER, actual INTEGER)")
            db.execute("CREATE TABLE IF NOT EXISTS alerts(model TEXT, month TEXT, level TEXT, PRIMARY KEY(model,month,level))")
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

    def _month(self):
        now = self.clock()
        if now.tzinfo is None:
            raise ValueError("timezone-aware billing clock required")
        return now.astimezone(ZoneInfo("America/Chicago")).strftime("%Y-%m")

    def _total(self, db, model, month):
        return db.execute("SELECT COALESCE(SUM(COALESCE(actual,reserved)),0) FROM spend WHERE model=? AND month=?", (model, month)).fetchone()[0]

    def _alerts(self, db, model, month, total):
        cap = self.caps[model]
        for threshold in (80, 95, 100):
            if total * 100 >= cap * threshold:
                db.execute("INSERT OR IGNORE INTO alerts VALUES (?,?,?)", (model, month, str(threshold)))

    def capacity_snapshot(self):
        if callable(self._capacity_snapshot):
            return self._capacity_snapshot()
        return self._capacity_snapshot

    def reserve(self, call_id, model, maximum_cost):
        if model not in self.caps or not isinstance(call_id, str) or not 1 <= len(call_id) <= 100:
            raise ValueError("known model and stable call ID required")
        if type(maximum_cost) is not int or not 0 < maximum_cost < 10**12:
            raise ValueError("positive worst-case cost in microdollars required")
        quota = provider_quota_check(model, self.capacity_snapshot())
        if quota.get("low_quota"):
            month = self._month()
            with self.db() as db:
                db.execute("INSERT OR IGNORE INTO alerts VALUES (?,?,'quota_low')", (model, month))
            return {"admitted": False, "reason": "provider_quota_low", "quota": quota}
        month = self._month()
        with self.db() as db:
            prior = db.execute("SELECT model,month,reserved,actual FROM spend WHERE id=?", (call_id,)).fetchone()
            if prior:
                if prior[:3] != (model, month, maximum_cost):
                    raise ValueError("call ID reused with changed identity")
                return {"admitted": False, "reason": "already_reserved_or_settled"}
            total = self._total(db, model, month)
            if total + maximum_cost > self.caps[model]:
                db.execute("INSERT OR IGNORE INTO alerts VALUES (?,?,'blocked')", (model, month))
                return {"admitted": False, "reason": "monthly_cap", "used_or_reserved": total}
            db.execute("INSERT INTO spend VALUES (?,?,?,?,NULL)", (call_id, model, month, maximum_cost))
            self._alerts(db, model, month, total + maximum_cost)
            return {"admitted": True, "month": month, "used_or_reserved": total + maximum_cost}

    def settle(self, call_id, actual_cost):
        if type(actual_cost) is not int or not 0 <= actual_cost < 10**12:
            raise ValueError("nonnegative actual cost required")
        overrun = False
        with self.db() as db:
            row = db.execute("SELECT model,month,reserved,actual FROM spend WHERE id=?", (call_id,)).fetchone()
            if not row or row[0] not in self.caps:
                raise ValueError("unknown reservation")
            if row[3] is not None and row[3] != actual_cost:
                raise ValueError("settled receipt cannot be rewritten")
            if actual_cost > row[2]:
                db.execute("INSERT OR IGNORE INTO alerts VALUES (?,?,?)", (row[0], row[1], "overrun"))
                overrun = True
            else:
                db.execute("UPDATE spend SET actual=? WHERE id=?", (actual_cost, call_id))
                self._alerts(db, row[0], row[1], self._total(db, row[0], row[1]))
        if overrun:
            raise ValueError("actual cost exceeds reservation")

    def alerts(self):
        with self.db() as db:
            return [{"model": model, "month": month, "level": level} for model, month, level in
                    db.execute("SELECT model,month,level FROM alerts ORDER BY month,model,level")]
