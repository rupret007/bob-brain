#!/usr/bin/env python3
"""Bob ↔ Web Bob handback live drill (run twice). Offline ledger checks + live takeover ask."""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path

from handback import append_turn, refresh_summary
from live_failover import Curl, HERE, ROOT

import sys

if str(ROOT / "conductor/state") not in sys.path:
    sys.path.insert(0, str(ROOT / "conductor/state"))
import ledger as state_ledger
from live_ready_drill import origin_url

HANDBACK_FILES = ("BOB-STATE.md", "HANDBACK-LOG.md", "HANDBACK-SUMMARY.md", ".bob-last-seen")
STATE_FILES = ("STATE.json", "BOB-CATCHUP.md", "NOW.md")
DRILL_COMMIT_SHA = "drill0001"


def backup_handback(root: Path) -> dict[str, bytes]:
    folder = root / "conductor/handback"
    saved: dict[str, bytes] = {}
    for name in HANDBACK_FILES:
        path = folder / name
        if path.exists():
            saved[name] = path.read_bytes()
    return saved


def backup_state(root: Path) -> dict[str, bytes]:
    folder = root / "conductor/state"
    saved: dict[str, bytes] = {}
    for name in STATE_FILES:
        path = folder / name
        if path.exists():
            saved[name] = path.read_bytes()
    return saved


def restore_state(root: Path, saved: dict[str, bytes]) -> None:
    folder = root / "conductor/state"
    folder.mkdir(parents=True, exist_ok=True)
    for name in STATE_FILES:
        path = folder / name
        if name in saved:
            path.write_bytes(saved[name])
        elif path.exists():
            path.unlink()


def restore_handback(root: Path, saved: dict[str, bytes]) -> None:
    folder = root / "conductor/handback"
    folder.mkdir(parents=True, exist_ok=True)
    for name in HANDBACK_FILES:
        path = folder / name
        if name in saved:
            path.write_bytes(saved[name])
        elif path.exists():
            path.unlink()


def ledger_round(root: Path, tag: str) -> dict:
    folder = root / "conductor/handback"
    folder.mkdir(parents=True, exist_ok=True)
    state = folder / "BOB-STATE.md"
    state.write_text(
        f"# BOB-STATE ({tag})\n\nRunning: handback drill screen `drill-{tag}`\n"
        "Waiting on Jeff: approve demo sketch\n"
    )
    state_ledger.add_open_ask(root, f"drill open item ({tag})")
    append_turn(root, ask=f"handback drill {tag}: status check", provider="gemini", jobs=[], files=[],
                commits=[], confirmations=[], refusals=[], open_items=[f"drill open item ({tag})"])
    append_turn(root, ask=f"handback drill {tag}: queued review", provider="gemini", jobs=[f"drill-{tag}"],
                files=[], commits=[DRILL_COMMIT_SHA], confirmations=[], refusals=[], open_items=[])
    refresh_summary(root)
    state_ledger.write_now(root, f"Handback drill {tag}: running screen drill-{tag}", sha=DRILL_COMMIT_SHA)
    state_ledger.write_catchup(root)
    summary_path = folder / "HANDBACK-SUMMARY.md"
    log_path = folder / "HANDBACK-LOG.md"
    text = summary_path.read_text(errors="replace") if summary_path.exists() else ""
    log_text = log_path.read_text(errors="replace") if log_path.exists() else ""
    combined = text + "\n" + log_text
    ledger_ok = all(token in combined for token in (
        f"handback drill {tag}", "Running: handback drill", f"drill-{tag}", DRILL_COMMIT_SHA, "drill open item",
    ))
    bob_pickup_ok = (
        DRILL_COMMIT_SHA in combined
        and "drill open item" in combined
        and f"drill-{tag}" in combined
        and ("Open ask" in text or f"drill open item ({tag})" in combined)
    )
    return {
        "tag": tag,
        "ledger_ok": ledger_ok,
        "bob_pickup_ok": bob_pickup_ok,
        "summary_chars": len(text),
    }


def live_round(url: str, tag: str) -> dict:
    parsed_host = url.split("://", 1)[-1].rstrip("/")
    client = Curl(url if "://" in url else "http://" + parsed_host)
    conv = client.new()
    started = time.monotonic()
    prompts = [
        "From BOB-STATE and handback only: what's running right now? Include the exact screen/job id.",
        f"From BOB-STATE only: quote the Running line for handback drill `{tag}` in one sentence.",
    ]
    last = {}
    for prompt in prompts:
        client.submit(conv, prompt, str(uuid.uuid4()))
        value = client.wait(conv)
        msg = value["messages"][-1]
        body = (msg.get("content") or "").lower()
        tag_bits = tag.replace("-", " ").split()
        specific = f"drill-{tag}" in body or f"handback drill {tag}" in body or all(bit in body for bit in tag_bits)
        mentions_running = specific and any(word in body for word in ("running", "drill", "screen", "active"))
        last = {
            "tag": tag,
            "status": msg.get("status"),
            "provider": msg.get("provider"),
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "mentions_running": mentions_running,
            "snippet": (msg.get("content") or "")[:220],
            "live_ok": msg.get("status") == "done" and mentions_running,
        }
        if last["live_ok"]:
            break
    client.close()
    return last


def main():
    evidence = {"started_at": time.time(), "rounds": [], "restored_handback": False}
    url = origin_url()
    saved = backup_handback(ROOT)
    saved_state = backup_state(ROOT)
    try:
        prefix = os.environ.get("WEBCHAT_HANDBACK_TAG", "r6")
        for index in (1, 2):
            tag = f"{prefix}-{index}"
            round_evidence = {"ledger": ledger_round(ROOT, tag), "live": None}
            try:
                round_evidence["live"] = live_round(url, tag)
            except (AssertionError, RuntimeError, OSError) as exc:
                round_evidence["live"] = {"tag": tag, "live_ok": False, "error": str(exc)[:300]}
            log_path = ROOT / "conductor/handback/HANDBACK-LOG.md"
            log_text = log_path.read_text(errors="replace").lower() if log_path.exists() else ""
            reverse_ok = f"handback drill {tag}" in log_text and DRILL_COMMIT_SHA in log_text
            events_ok = False
            try:
                if str(ROOT / "conductor/state") not in sys.path:
                    sys.path.insert(0, str(ROOT / "conductor/state"))
                import alignment_events
                rows = alignment_events.read_events(ROOT, since_seq=max(0, alignment_events.latest_seq(ROOT) - 30))
                events_ok = any(
                    f"handback drill {tag}" in (r.get("summary") or "").lower() and r.get("kind") == "handback-turn"
                    for r in rows
                )
            except (ImportError, OSError):
                events_ok = False
            round_evidence["events_ok"] = events_ok
            round_evidence["reverse_handback_ok"] = reverse_ok
            round_evidence["pass"] = (
                round_evidence["ledger"]["ledger_ok"]
                and round_evidence["ledger"]["bob_pickup_ok"]
                and round_evidence["live"].get("live_ok")
                and reverse_ok
                and round_evidence.get("events_ok")
            )
            evidence["rounds"].append(round_evidence)
    finally:
        restore_handback(ROOT, saved)
        restore_state(ROOT, saved_state)
        evidence["restored_handback"] = True
        evidence["restored_state"] = True
    evidence["finished_at"] = time.time()
    evidence["result"] = "PASS" if all(row["pass"] for row in evidence["rounds"]) else "FAIL"
    out = HERE / "evidence/handback-drill.json"
    out.write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps({"result": evidence["result"], "rounds": len(evidence["rounds"])}, indent=2))
    return 0 if evidence["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
