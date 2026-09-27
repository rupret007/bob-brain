#!/usr/bin/env python3
"""Bob ↔ Web Bob handback live drill (run twice). Offline ledger checks + live takeover ask."""
from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path

from handback import append_turn, refresh_summary
from live_failover import Curl, HERE, ROOT
from live_ready_drill import origin_url


def ledger_round(root: Path, tag: str) -> dict:
    folder = root / "conductor/handback"
    folder.mkdir(parents=True, exist_ok=True)
    state = folder / "BOB-STATE.md"
    state.write_text(
        f"# BOB-STATE ({tag})\n\nRunning: handback drill screen `drill-{tag}`\n"
        "Waiting on Jeff: approve demo sketch\n"
    )
    append_turn(root, ask=f"handback drill {tag}: status check", provider="gemini", jobs=[], files=[],
                commits=[], confirmations=[], refusals=[], open_items=["drill open item"])
    append_turn(root, ask=f"handback drill {tag}: queued review", provider="gemini", jobs=[f"drill-{tag}"],
                files=[], commits=["abc1234"], confirmations=[], refusals=[], open_items=[])
    refresh_summary(root)
    summary_path = folder / "HANDBACK-SUMMARY.md"
    log_path = folder / "HANDBACK-LOG.md"
    text = summary_path.read_text(errors="replace") if summary_path.exists() else ""
    log_text = log_path.read_text(errors="replace") if log_path.exists() else ""
    combined = text + "\n" + log_text
    ok = all(token in combined for token in (f"handback drill {tag}", "Running: handback drill", f"drill-{tag}"))
    return {"tag": tag, "ledger_ok": ok, "summary_chars": len(text)}


def live_round(url: str, tag: str) -> dict:
    parsed_host = url.split("://", 1)[-1].rstrip("/")
    client = Curl(url if "://" in url else "http://" + parsed_host)
    conv = client.new()
    started = time.monotonic()
    client.submit(conv, "From BOB-STATE and handback only: what's running right now? One short paragraph.", str(uuid.uuid4()))
    value = client.wait(conv)
    elapsed = time.monotonic() - started
    msg = value["messages"][-1]
    body = (msg.get("content") or "").lower()
    mentions_running = "drill" in body or "running" in body or "handback" in body
    client.close()
    return {
        "tag": tag,
        "status": msg.get("status"),
        "provider": msg.get("provider"),
        "elapsed_seconds": round(elapsed, 3),
        "mentions_running": mentions_running,
        "live_ok": msg.get("status") == "done" and mentions_running,
    }


def main():
    evidence = {"started_at": time.time(), "rounds": []}
    url = origin_url()
    for index in (1, 2):
        tag = f"r4-{index}"
        round_evidence = {"ledger": ledger_round(ROOT, tag), "live": None}
        try:
            round_evidence["live"] = live_round(url, tag)
        except (AssertionError, RuntimeError, OSError) as exc:
            round_evidence["live"] = {"tag": tag, "live_ok": False, "error": str(exc)[:300]}
        round_evidence["pass"] = round_evidence["ledger"]["ledger_ok"] and round_evidence["live"].get("live_ok")
        evidence["rounds"].append(round_evidence)
    evidence["finished_at"] = time.time()
    evidence["result"] = "PASS" if all(row["pass"] for row in evidence["rounds"]) else "FAIL"
    out = HERE / "evidence/handback-drill.json"
    out.write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps({"result": evidence["result"], "rounds": len(evidence["rounds"])}, indent=2))
    return 0 if evidence["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
