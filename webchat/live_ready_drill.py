#!/usr/bin/env python3
"""WEBCHAT-READY 10-message drill: 2 conversations, background lane locks held."""
from __future__ import annotations

import fcntl
import json
import statistics
import sys
import time
import uuid
from contextlib import ExitStack
from pathlib import Path
from urllib.parse import urlsplit

from live_failover import Curl, HERE, ROOT


def origin_url() -> str:
    path = HERE / ".public-origin"
    if path.exists():
        value = path.read_text().strip()
        if value:
            return value.rstrip("/")
    return "http://127.0.0.1:8787"


def main():
    url = origin_url()
    parsed = urlsplit(url)
    host = parsed.netloc or "127.0.0.1:8787"
    client = Curl(url if parsed.scheme else "http://" + host)
    latencies = []
    convs = [client.new(), client.new()]
    messages = [
        (0, "Reply with exactly: drill A1"),
        (1, "Reply with exactly: drill B1"),
        (0, "Reply with exactly: drill A2"),
        (1, "Reply with exactly: drill B2"),
        (0, "Reply with exactly: drill A3"),
        (1, "Reply with exactly: drill B3"),
        (0, "Reply with exactly: drill A4"),
        (1, "Reply with exactly: drill B4"),
        (0, "Reply with exactly: drill A5"),
        (1, "Reply with exactly: drill B5"),
    ]
    evidence = {"url": url, "host": host, "messages": [], "started_at": time.time()}
    with ExitStack() as stack:
        held = []
        for name in ("codex", "cursor", "gemini", "minimax"):
            handle = stack.enter_context((ROOT / "conductor/locks" / ("lane-" + name + ".lock")).open("a+"))
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                held.append(name + ": drill holds background lock")
            except BlockingIOError:
                held.append(name + ": background job holds lock")
        for conv, text in messages:
            started = time.monotonic()
            client.submit(convs[conv], text, str(uuid.uuid4()))
            value = client.wait(convs[conv])
            elapsed = time.monotonic() - started
            latencies.append(elapsed)
            msg = value["messages"][-1]
            busy = any("another job" in a.get("error", "") for a in msg.get("attempts", []))
            evidence["messages"].append({
                "conversation": conv, "text": text, "status": msg["status"], "provider": msg.get("provider"),
                "elapsed_seconds": round(elapsed, 3), "busy_in_attempts": busy,
            })
            if msg["status"] != "done" or busy:
                evidence["result"] = "FAIL"
                out = HERE / "evidence/ready-drill.json"
                out.write_text(json.dumps(evidence, indent=2) + "\n")
                print(json.dumps(evidence, indent=2))
                return 1
    evidence["locks"] = held
    evidence["p50_seconds"] = round(statistics.median(latencies), 3)
    evidence["via_tsnet"] = host.endswith(".ts.net")
    merge_rid = str(uuid.uuid4())
    merge_cid = client.new()
    client.submit(merge_cid, "merge #158", merge_rid)
    merge_value = client.submit(merge_cid, "merge #158", merge_rid)
    merge_msg = merge_value["messages"][-1]
    card = merge_msg.get("action_card") or {}
    merge_ok = (
        len(merge_value["messages"]) == 2
        and card.get("state") == "refused"
        and not card.get("executable")
    )
    evidence["merge_refusal"] = {
        "ok": merge_ok,
        "request": "merge #158",
        "state": card.get("state"),
        "executable": card.get("executable"),
        "duplicate_messages": len(merge_value["messages"]),
        "idempotent_refusal": len(merge_value["messages"]) == 2,
    }
    if not merge_ok:
        evidence["result"] = "FAIL"
        out = HERE / "evidence/ready-drill.json"
        out.write_text(json.dumps(evidence, indent=2) + "\n")
        print(json.dumps(evidence, indent=2))
        client.close()
        return 1
    evidence["finished_at"] = time.time()
    evidence["result"] = "PASS"
    out = HERE / "evidence/ready-drill.json"
    out.write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps({
        "result": "PASS",
        "p50_seconds": evidence["p50_seconds"],
        "count": len(latencies),
        "via_tsnet": evidence["via_tsnet"],
        "merge_refusal": merge_ok,
    }, indent=2))
    client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
