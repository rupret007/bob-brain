"""Load ai-capacity/v1 snapshots; refresh when stale. Never logs secrets."""
from __future__ import annotations

import json
import math
import os
import subprocess
import time
from pathlib import Path
from typing import Callable, Optional

from webbob.shared_context import ContextError, safe_fact

SCHEMA = "ai-capacity/v1"
_DEFAULT_SYNC = Path.home() / "Documents" / "bob-overnight-inject" / "sync" / "ai-capacity.json"
_DEFAULT_SCRIPT = Path.home() / "Documents" / "bob-overnight-inject" / "bin" / "ai-capacity.sh"
DEFAULT_JSON = Path(os.environ.get("AI_CAPACITY_JSON", str(_DEFAULT_SYNC)))
DEFAULT_SCRIPT = Path(os.environ.get("AI_CAPACITY_SCRIPT", str(_DEFAULT_SCRIPT)))
MAX_AGE_SECONDS = 15 * 60
REFRESH_TIMEOUT = 180
REFRESH_COOLDOWN_SECONDS = 10 * 60

Runner = Callable[[list[str], float], subprocess.CompletedProcess]


def _default_runner(argv: list[str], timeout: float) -> subprocess.CompletedProcess:
    return subprocess.run(
        argv,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _row_keys() -> set[str]:
    return {
        "provider",
        "used_pct",
        "remaining_pct",
        "reset_ts",
        "reset_ct",
        "source",
        "observed_ts",
        "freshness",
        "status",
        "note",
    }


def validate_document(data: object) -> dict:
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise ValueError("invalid ai-capacity document")
    generated_ts = data.get("generated_ts")
    if type(generated_ts) not in (int, float) or not math.isfinite(generated_ts) or not (0 < generated_ts < 10**12):
        raise ValueError("invalid generated_ts")
    rows = data.get("rows")
    if not isinstance(rows, list):
        raise ValueError("rows must be a list")
    out_rows = []
    for item in rows:
        if not isinstance(item, dict) or "provider" not in item:
            raise ValueError("invalid capacity row")
        row = {k: item.get(k) for k in _row_keys()}
        if not isinstance(row["provider"], str) or not row["provider"]:
            raise ValueError("provider required")
        for pct_key in ("used_pct", "remaining_pct"):
            pct = row[pct_key]
            if pct is not None and (
                type(pct) not in (int, float)
                or not math.isfinite(pct)
                or pct < 0
                or pct > 100
            ):
                raise ValueError("invalid percent")
        out_rows.append(row)
    return {
        "schema": SCHEMA,
        "generated_ts": float(generated_ts),
        "generated_ct": data.get("generated_ct") if isinstance(data.get("generated_ct"), str) else None,
        "host": data.get("host") if isinstance(data.get("host"), str) else None,
        "rows": out_rows,
        "snapshot_stale": bool(data.get("snapshot_stale")),
        "snapshot_note": data.get("snapshot_note") if isinstance(data.get("snapshot_note"), str) else "",
    }


def _read_file(path: Path) -> Optional[dict]:
    try:
        raw = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    try:
        return validate_document(raw)
    except ValueError:
        return None


def _safe_capacity_string(value) -> str:
    if not isinstance(value, str) or not value:
        return ""
    try:
        safe_fact(value)
    except ContextError:
        return ""
    return value


def sanitize_capacity_snapshot(doc: dict) -> dict:
    """Drop credential-like strings from capacity fields exposed via MCP."""
    out = dict(doc)
    out["host"] = _safe_capacity_string(out.get("host"))
    out["snapshot_note"] = _safe_capacity_string(out.get("snapshot_note"))
    rows = []
    for row in doc.get("rows") or []:
        if not isinstance(row, dict):
            continue
        cleaned = dict(row)
        cleaned["source"] = _safe_capacity_string(cleaned.get("source"))
        cleaned["note"] = _safe_capacity_string(cleaned.get("note"))
        rows.append(cleaned)
    out["rows"] = rows
    return out


def _mark_stale(doc: dict, note: str) -> dict:
    out = dict(doc)
    out["snapshot_stale"] = True
    prior = out.get("snapshot_note") or ""
    out["snapshot_note"] = note if not prior else f"{prior}; {note}"
    return out


class AiCapacity:
    """Read-only capacity loader with optional refresh via ai-capacity.sh --json."""

    def __init__(
        self,
        path: Path | str | None = None,
        script: Path | str | None = None,
        *,
        clock: Callable[[], float] | None = None,
        runner: Runner | None = None,
        max_age_seconds: float = MAX_AGE_SECONDS,
        refresh_cooldown_seconds: float = REFRESH_COOLDOWN_SECONDS,
    ):
        self.path = Path(path or DEFAULT_JSON)
        self.script = Path(script or DEFAULT_SCRIPT)
        self.clock = clock or time.time
        self.runner = runner or _default_runner
        self.max_age_seconds = max_age_seconds
        self.refresh_cooldown_seconds = refresh_cooldown_seconds
        self._cache: Optional[dict] = None
        self._refresh_blocked_until = 0.0

    def _needs_refresh(self, doc: Optional[dict], now: float) -> bool:
        if doc is None:
            return True
        return now - doc["generated_ts"] > self.max_age_seconds

    def _refresh(self) -> Optional[dict]:
        if not self.script.is_file():
            return None
        try:
            proc = self.runner([str(self.script), "--json"], REFRESH_TIMEOUT)
        except (OSError, subprocess.TimeoutExpired):
            return None
        if proc.returncode != 0:
            return None
        try:
            parsed = json.loads(proc.stdout)
        except json.JSONDecodeError:
            return None
        try:
            return validate_document(parsed)
        except ValueError:
            return None

    def snapshot(self, *, refresh: bool = True) -> dict:
        now = self.clock()
        on_disk = _read_file(self.path)
        if on_disk is not None:
            self._cache = on_disk
        doc = on_disk or self._cache
        stale_reason = None
        if refresh and self._needs_refresh(doc, now):
            if now < self._refresh_blocked_until:
                if doc is not None:
                    stale_reason = "refresh cooldown; using last snapshot"
                else:
                    stale_reason = "no snapshot available"
            else:
                self._refresh_blocked_until = now + self.refresh_cooldown_seconds
                fresh = self._refresh()
                if fresh is not None:
                    self._refresh_blocked_until = 0.0
                    self._cache = fresh
                    doc = fresh
                elif doc is not None:
                    stale_reason = "refresh failed; using last snapshot"
                else:
                    stale_reason = "no snapshot available"
        if doc is None:
            return {
                "schema": SCHEMA,
                "generated_ts": now,
                "generated_ct": None,
                "host": None,
                "rows": [],
                "snapshot_stale": True,
                "snapshot_note": stale_reason or "missing capacity data",
            }
        if stale_reason:
            doc = _mark_stale(doc, stale_reason)
        elif self._needs_refresh(doc, now):
            doc = _mark_stale(doc, "snapshot older than refresh threshold")
        self._cache = doc
        return doc
