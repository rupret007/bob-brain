#!/usr/bin/env python3
"""Isolated handback drill fixture — never mutates production handback/state."""
from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from pathlib import Path

from handback import append_turn, refresh_summary

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FIXTURES = HERE / "drill-fixtures"

HANDBACK_FILES = ("BOB-STATE.md", "HANDBACK-LOG.md", "HANDBACK-SUMMARY.md", ".bob-last-seen")
STATE_FILES = ("STATE.json", "BOB-CATCHUP.md", "NOW.md", "events.jsonl", "INBOX.md")
DRILL_COMMIT_SHA = "drill0001"
SYNTHETIC_COMMIT_LABEL = f"synthetic:{DRILL_COMMIT_SHA}"


def prod_fingerprint(root: Path) -> dict[str, str]:
    """SHA256 of production handback + state files (detect drill leakage into prod)."""
    out: dict[str, str] = {}
    for rel in (
        *(f"conductor/handback/{name}" for name in HANDBACK_FILES),
        *(f"conductor/state/{name}" for name in STATE_FILES),
    ):
        path = root / rel
        if path.is_file():
            out[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def assert_prod_unchanged(before: dict[str, str], root: Path) -> None:
    after = prod_fingerprint(root)
    if before != after:
        changed = [k for k in sorted(set(before) | set(after)) if before.get(k) != after.get(k)]
        raise RuntimeError("Production handback changed during drill: " + ", ".join(changed[:8]))
    if str(ROOT / "conductor/state") not in __import__("sys").path:
        import sys

        sys.path.insert(0, str(ROOT / "conductor/state"))
    import ledger as state_ledger

    for ask in state_ledger.load_state(root).get("open_asks") or []:
        body = ask.get("body") or ""
        if ask.get("status") in ("new", "in_progress") and state_ledger._DRILL_NOISE_RE.search(body):
            raise RuntimeError("Drill noise reappeared in production open asks: " + body[:80])


def _assert_isolated(fixture_root: Path) -> None:
    resolved = fixture_root.resolve()
    if resolved == ROOT.resolve():
        raise RuntimeError("Refusing drill ledger on production ROOT")
    if "drill-fixtures" not in resolved.parts:
        raise RuntimeError("Fixture must live under a drill-fixtures/ directory")


def new_fixture_root(base: Path | None = None) -> Path:
    fixtures_dir = (base or HERE) / "drill-fixtures"
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    path = fixtures_dir / str(uuid.uuid4())
    path.mkdir(parents=True)
    (path / "conductor/handback").mkdir(parents=True)
    (path / "conductor/state").mkdir(parents=True)
    return path


def try_bob_state_running_line(fixture_root: Path, text: str) -> str | None:
    """Answer handback takeover asks from fixture BOB-STATE without a model."""
    import re

    if not re.search(r"bob-state|handback only", text or "", re.I):
        return None
    path = fixture_root / "conductor/handback/BOB-STATE.md"
    if not path.is_file():
        return None
    for line in path.read_text(errors="replace").splitlines():
        if "running" in line.lower():
            return line.strip()[:600]
    return None


def publish_fixture(fixture_root: Path) -> str:
    """Ensure fixture id is stable for server overlay bind (already under drill-fixtures/)."""
    _assert_isolated(fixture_root)
    return fixture_root.name


def ledger_round(fixture_root: Path, tag: str) -> dict:
    _assert_isolated(fixture_root)
    folder = fixture_root / "conductor/handback"
    folder.mkdir(parents=True, exist_ok=True)
    if str(ROOT / "conductor/state") not in __import__("sys").path:
        import sys

        sys.path.insert(0, str(ROOT / "conductor/state"))
    import ledger as state_ledger

    state = folder / "BOB-STATE.md"
    state.write_text(
        f"# BOB-STATE ({tag})\n\nRunning: handback drill screen `drill-{tag}`\n"
        "Waiting on Jeff: approve demo sketch\n"
    )
    state_ledger.add_open_ask(fixture_root, f"drill open item ({tag})")
    append_turn(
        fixture_root,
        ask=f"handback drill {tag}: status check",
        provider="gemini",
        jobs=[],
        files=[],
        commits=[],
        confirmations=[],
        refusals=[],
        open_items=[f"drill open item ({tag})"],
    )
    append_turn(
        fixture_root,
        ask=f"handback drill {tag}: queued review",
        provider="gemini",
        jobs=[f"drill-{tag}"],
        files=[],
        commits=[SYNTHETIC_COMMIT_LABEL],
        confirmations=[],
        refusals=[],
        open_items=[],
    )
    refresh_summary(fixture_root)
    state_ledger.write_now(fixture_root, f"Handback drill {tag}: running screen drill-{tag}", sha=DRILL_COMMIT_SHA)
    state_ledger.write_catchup(fixture_root)
    summary_path = folder / "HANDBACK-SUMMARY.md"
    log_path = folder / "HANDBACK-LOG.md"
    text = summary_path.read_text(errors="replace") if summary_path.exists() else ""
    log_text = log_path.read_text(errors="replace") if log_path.exists() else ""
    combined = text + "\n" + log_text
    ledger_ok = all(
        token in combined
        for token in (
            f"handback drill {tag}",
            "Running: handback drill",
            f"drill-{tag}",
            DRILL_COMMIT_SHA,
            "drill open item",
        )
    )
    bob_pickup_ok = (
        DRILL_COMMIT_SHA in combined
        and "drill open item" in combined
        and f"drill-{tag}" in combined
        and ("Open ask" in text or f"drill open item ({tag})" in combined)
    )
    return {
        "tag": tag,
        "fixture_id": publish_fixture(fixture_root),
        "ledger_ok": ledger_ok,
        "bob_pickup_ok": bob_pickup_ok,
        "summary_chars": len(text),
    }


def reverse_handback_ok(fixture_root: Path, tag: str) -> bool:
    log_path = fixture_root / "conductor/handback/HANDBACK-LOG.md"
    log_text = log_path.read_text(errors="replace").lower() if log_path.exists() else ""
    catchup_path = fixture_root / "conductor/state/BOB-CATCHUP.md"
    catchup = catchup_path.read_text(errors="replace").lower() if catchup_path.exists() else ""
    open_item = f"drill open item ({tag})"
    return (
        f"handback drill {tag}" in log_text
        and DRILL_COMMIT_SHA in log_text
        and open_item in catchup
    )


def events_ok(fixture_root: Path, tag: str) -> bool:
    if str(ROOT / "conductor/state") not in __import__("sys").path:
        import sys

        sys.path.insert(0, str(ROOT / "conductor/state"))
    try:
        import alignment_events
    except ImportError:
        return False
    rows = alignment_events.read_events(fixture_root, since_seq=max(0, alignment_events.latest_seq(fixture_root) - 30))
    return any(
        f"handback drill {tag}" in (r.get("summary") or "").lower() and r.get("kind") == "handback-turn"
        for r in rows
    )
