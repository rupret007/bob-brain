#!/usr/bin/env python3
"""Real authenticated HTTP/provider checks. Faults use an isolated server only."""
import argparse
import json
import os
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from app import Chat, Server
from failover import ORDER, atomic_json
from live_failover import Curl

HERE = Path(__file__).resolve().parent


def check(client, evidence, name, prompt, primary="auto", expected=None, cid=None):
    cid = cid or client.new()
    started = time.monotonic()
    client.submit(cid, prompt, provider=primary)
    value = client.wait(cid, timeout=660)
    message = value["messages"][-1]
    row = {"check": name, "conversation_id": cid, "status": message["status"],
           "provider": message.get("provider"), "reply": message["content"],
           "attempts": message.get("attempts", []), "seconds": round(time.monotonic()-started, 2)}
    evidence.append(row)
    print(json.dumps({k: row[k] for k in ("check", "provider", "status", "seconds")}), flush=True)
    assert message["status"] == "done", row
    assert message.get("provider") in ORDER, "A local shortcut is not provider evidence"
    if expected:
        assert message["provider"] == expected, row
    assert len(message["content"]) > 35, row
    return cid, message


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="https://jeffs-mac-mini.tail758ab4.ts.net")
    parser.add_argument("--isolated", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    evidence = {"started_at": time.time(), "checks": [], "isolated": args.isolated}
    temp = server = chat = client = None
    try:
        if args.isolated:
            temp = tempfile.TemporaryDirectory(prefix="webbob-live-drill-")
            root = Path(temp.name)
            folder = root / "conductor/webchat"
            folder.mkdir(parents=True, exist_ok=True)
            prod_pw = HERE / ".password"
            if prod_pw.is_file():
                (folder / ".password").write_text(prod_pw.read_text(errors="replace"))
            os.environ["BOB_WEBCHAT_DRILLS"] = "1"
            # API transport still uses its installed shared budget/credentials.
            # Only chat state, injected faults, CLI cwd and audit logs are isolated.
            os.environ.pop("BOB_ROOT", None)
            chat = Chat(folder, root)
            server = Server(("127.0.0.1", 0), chat)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            client = Curl("http://127.0.0.1:" + str(server.server_port))
            evidence["url"] = client.url
            drill_file = folder / ".drill.json"
            def configure(cid, forced):
                atomic_json(drill_file, {"conversation_ids": [cid], "force_fail": forced, "cooldown_seconds": 1})
                # Each scenario owns an independent breaker; never resets real health.
                chat.providers.drill_circuit = None
            # Every provider must finish an actual substantive reply.
            for name in ORDER:
                check(client, evidence["checks"], "real_" + name,
                      "Explain in two sentences why a checksum is useful when checking whether a file changed. Include one limitation.",
                      primary=name, expected=name)
            # Each provider fails as the selected primary, with real successor output.
            for name in ORDER:
                cid = client.new()
                configure(cid, {name: "network"})
                drill_order = (name,) + tuple(n for n in ORDER if n != name)
                successor = drill_order[1]
                _, message = check(client, evidence["checks"], "failed_primary_" + name,
                      "Give two practical steps for checking a saved chat after a server restart, and explain why they help.",
                      primary=name, expected=successor, cid=cid)
                assert message["attempts"][0]["provider"] == name
                assert message["attempts"][0]["kind"] == "network"
            for target in ORDER[2:]:
                cid = client.new()
                failed = ORDER[:ORDER.index(target)]
                configure(cid, {name: "network" for name in failed})
                _, message = check(client, evidence["checks"], "chain_to_" + target,
                      "Give two practical checks for detecting whether a saved chat has missing messages. Explain each briefly.",
                      primary="codex", expected=target, cid=cid)
                assert [a["provider"] for a in message["attempts"]] == list(failed)
            cid = client.new()
            configure(cid, {name: "network" for name in ORDER})
            client.submit(cid, "Explain one benefit of retrying after a temporary network outage.", provider="gemini")
            queued = client.wait(cid)["messages"][-1]
            assert queued["status"] == "waiting" and len(queued["attempts"]) == len(ORDER)
            evidence["checks"].append({"check": "all_down_waiting", "status": "waiting", "attempts": queued["attempts"]})
            atomic_json(drill_file, {"conversation_ids": [cid], "force_fail": {}})
            time.sleep(1.1)
            chat.retry_queued()
            value = client.wait(cid)
            assert value["messages"][-1]["status"] == "done" and len(value["messages"]) == 2
            evidence["checks"].append({"check": "all_down_recovery_once", "provider": value["messages"][-1]["provider"], "status": "done"})
        else:
            client = Curl(args.url)
            evidence["url"] = client.url
            for name in ORDER:
                check(client, evidence["checks"], "public_" + name,
                      "Give a useful two-sentence explanation of how to verify that conversation history survived a restart.", primary=name, expected=name)
        cid, _ = check(client, evidence["checks"], "memory_store",
                       "Remember that my imaginary boat is named Copper Heron. Suggest one short motto that fits the name.")
        _, message = check(client, evidence["checks"], "memory_recall",
                       "What is my imaginary boat called, and why does your motto suit that name?", cid=cid)
        assert "copper heron" in message["content"].lower()
        evidence["result"] = "PASS"
    except BaseException as exc:
        evidence["result"] = "FAIL"
        evidence["error"] = str(exc)[:3000]
        raise
    finally:
        evidence["finished_at"] = time.time()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, indent=2) + "\n")
        if client:
            client.close()
        if server:
            server.shutdown()
            server.server_close()
        if chat:
            chat.close()
        if temp:
            temp.cleanup()


if __name__ == "__main__":
    main()
