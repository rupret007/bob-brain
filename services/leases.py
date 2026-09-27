"""Transactional integration authority; worktrees/process isolation belong to the runner."""
from __future__ import annotations

import contextlib
import json
import math
import re
import sqlite3
import time
import unicodedata
import uuid
from pathlib import Path, PurePosixPath


class LeaseConflict(ValueError):
    pass


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}", value):
        raise ValueError("invalid identifier")
    return value


def normalize(paths, repo=None):
    if not isinstance(paths, (list, tuple)) or not paths:
        raise ValueError("a nonempty list of relative paths is required")
    result = set()
    for path in paths:
        if (not isinstance(path, str) or not path or path.startswith(("/", "~"))
                or any(c in path for c in "\\*?[]:\x00\n\r") or ".." in path.split("/")):
            raise ValueError("lease paths must be literal repository-relative paths")
        clean = str(PurePosixPath(path))
        if any(part.casefold() == ".git" for part in PurePosixPath(clean).parts):
            raise ValueError("Git metadata cannot be leased")
        if repo is not None:
            target = Path(repo)
            for part in PurePosixPath(clean).parts:
                target /= part
                if target.is_symlink():
                    raise ValueError("symlink paths cannot be leased")
        result.add(unicodedata.normalize("NFC", clean).casefold())
    return sorted(result)


def overlaps(left, right):
    return left == "." or right == "." or left == right or left.startswith(right + "/") or right.startswith(left + "/")


def resources(values):
    if not isinstance(values, (list, tuple)):
        raise ValueError("resources must be a list of namespace identifiers")
    return sorted({identifier(value).casefold() for value in values})


class LeaseStore:
    def __init__(self, conductor, project, repo=None):
        self.project, self.repo = identifier(project), repo
        self.path = Path(conductor) / "leases" / (project + ".sqlite3")
        if self.path.with_suffix(".json").exists():
            raise ValueError("reconcile and archive legacy JSON leases before using SQLite")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._transaction() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise ValueError("unsupported lease schema")
            if version == 0:
                db.execute("""CREATE TABLE leases (
                    generation INTEGER PRIMARY KEY AUTOINCREMENT, owner TEXT NOT NULL,
                    token TEXT NOT NULL UNIQUE, paths TEXT NOT NULL, resources TEXT NOT NULL,
                    heartbeat REAL NOT NULL, expires REAL NOT NULL, deadline REAL NOT NULL,
                    state TEXT NOT NULL, recovery_receipt TEXT)""")
                db.execute("PRAGMA user_version=1")

    @contextlib.contextmanager
    def _transaction(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _row(row):
        value = dict(row)
        for field in ("paths", "resources"):
            value[field] = json.loads(value[field])
        return value

    @staticmethod
    def _ttl(ttl):
        if type(ttl) not in (int, float) or not math.isfinite(ttl) or not 0 < ttl <= 3600:
            raise ValueError("lease TTL must be positive and at most one hour")
        return ttl

    def list(self):
        with self._transaction() as db:
            return [self._row(row) for row in db.execute("SELECT * FROM leases WHERE state='held'")]

    def claim(self, owner, paths, *, shared_resources=(), ttl=300):
        owner, paths = identifier(owner), normalize(paths, self.repo)
        scopes, ttl = resources(shared_resources), self._ttl(ttl)
        with self._transaction() as db:
            for raw in db.execute("SELECT * FROM leases WHERE state='held'"):
                row = self._row(raw)
                # Expiry removes authority, but keeps ownership pending explicit recovery.
                if (row["owner"] == owner or set(scopes) & set(row["resources"])
                        or any(overlaps(a, b) for a in paths for b in row["paths"])):
                    raise LeaseConflict("scope held; renew or reconcile the existing grant")
            now = time.time()
            cursor = db.execute("""INSERT INTO leases
                (owner, token, paths, resources, heartbeat, expires, deadline, state)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'held')""",
                (owner, uuid.uuid4().hex, json.dumps(paths), json.dumps(scopes), now, now + ttl, now + 86400))
            return self._row(db.execute("SELECT * FROM leases WHERE generation=?", (cursor.lastrowid,)).fetchone())

    def _owned(self, db, owner, token):
        row = db.execute("SELECT * FROM leases WHERE owner=? AND token=? AND state='held'", (owner, token)).fetchone()
        if row is None or row["expires"] <= time.time():
            raise ValueError("stale or expired lease fence")
        return self._row(row)

    @contextlib.contextmanager
    def guard(self, owner, token):
        """Fence a short acceptance transaction; never hold this across agent/CI calls."""
        with self._transaction() as db:
            yield self._owned(db, owner, token)
            self._owned(db, owner, token)

    def renew(self, owner, token, *, ttl=300):
        ttl = self._ttl(ttl)
        with self._transaction() as db:
            row, now = self._owned(db, owner, token), time.time()
            db.execute("UPDATE leases SET heartbeat=?, expires=? WHERE token=?",
                       (now, min(now + ttl, row["deadline"]), token))

    def release(self, owner, token):
        with self._transaction() as db:
            self._owned(db, owner, token)
            db.execute("UPDATE leases SET state='released' WHERE token=?", (token,))

    def recover(self, owner, token, *, receipt):
        """Runner attests expired attempt is stopped/quarantined; retain its evidence."""
        if not isinstance(receipt, str) or not receipt.strip():
            raise ValueError("runner recovery receipt is required")
        with self._transaction() as db:
            row = db.execute("SELECT * FROM leases WHERE owner=? AND token=?", (owner, token)).fetchone()
            if row is not None and row["state"] == "recovered" and row["recovery_receipt"] == receipt:
                return  # Safe restart/retry after committing recovery.
            if row is None or row["state"] != "held" or row["expires"] > time.time():
                raise ValueError("only the observed expired grant can be recovered")
            db.execute("UPDATE leases SET state='recovered', recovery_receipt=? WHERE token=?", (receipt, token))
