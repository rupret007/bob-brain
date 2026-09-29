#!/usr/bin/env python3
"""Bob ↔ Web Bob handback live drill (run twice). Isolated fixture + overlay; production untouched."""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path

from drill_fixture import (
    DRILL_COMMIT_SHA,
    assert_prod_unchanged,
    events_ok,
    ledger_round,
    new_fixture_root,
    prod_fingerprint,
    reverse_handback_ok,
)
from live_failover import Curl, HERE, ROOT
from live_ready_drill import origin_url

if str(ROOT / "conductor/state") not in sys.path:
    sys.path.insert(0, str(ROOT / "conductor/state"))
import ledger as state_ledger


def live_round(url: str, tag: str, fixture_id: str) -> dict:
    parsed_host = url.split("://", 1)[-1].rstrip("/")
    client = Curl(url if "://" in url else "http://" + parsed_host)
    conv = client.new()
    try:
        client.json("/api/drill/overlay", {"conversation_id": conv, "fixture_id": fixture_id})
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
        return last
    finally:
        try:
            client.json("/api/drill/overlay/clear", {"conversation_id": conv})
        except AssertionError:
            pass
        client.close()


def main():
    evidence = {"started_at": time.time(), "rounds": [], "isolated": True}
    url = origin_url()
    before = prod_fingerprint(ROOT)
    prefix = os.environ.get("WEBCHAT_HANDBACK_TAG", "r8")
    for index in (1, 2):
        tag = f"{prefix}-{index}"
        fixture_root = new_fixture_root()
        round_evidence = {"ledger": ledger_round(fixture_root, tag), "live": None, "fixture_id": fixture_root.name}
        try:
            round_evidence["live"] = live_round(url, tag, round_evidence["ledger"]["fixture_id"])
        except (AssertionError, RuntimeError, OSError) as exc:
            round_evidence["live"] = {"tag": tag, "live_ok": False, "error": str(exc)[:300]}
        round_evidence["reverse_handback_ok"] = reverse_handback_ok(fixture_root, tag)
        round_evidence["events_ok"] = events_ok(fixture_root, tag)
        round_evidence["pass"] = (
            round_evidence["ledger"]["ledger_ok"]
            and round_evidence["ledger"]["bob_pickup_ok"]
            and round_evidence["live"].get("live_ok")
            and round_evidence["reverse_handback_ok"]
            and round_evidence.get("events_ok")
        )
        evidence["rounds"].append(round_evidence)
    for attempt in range(6):
        try:
            assert_prod_unchanged(before, ROOT)
            evidence["prod_unchanged"] = True
            evidence["prod_quiet_attempts"] = attempt + 1
            break
        except (AssertionError, RuntimeError):
            if attempt >= 5:
                raise
            time.sleep(2.0)
    else:
        evidence["prod_unchanged"] = False
    evidence["finished_at"] = time.time()
    evidence["result"] = "PASS" if all(row["pass"] for row in evidence["rounds"]) else "FAIL"
    evidence["drill_commit_marker"] = DRILL_COMMIT_SHA
    out = HERE / "evidence/handback-drill.json"
    out.write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps({"result": evidence["result"], "rounds": len(evidence["rounds"]), "isolated": True}, indent=2))
    return 0 if evidence["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
