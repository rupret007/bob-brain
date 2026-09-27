#!/usr/bin/env python3
"""Opt-in curl drills against svc-webchat; real success paths, scoped faults.

Start the service with BOB_WEBCHAT_DRILLS=1 first. Credentials stay in private
files/stdin and are never printed or included in evidence. No server restarts.
"""
import argparse
import fcntl
import json
import os
import subprocess
import tempfile
import time
import uuid
from contextlib import ExitStack
from pathlib import Path
from urllib.parse import urlencode

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


class Curl:
    def __init__(self, url):
        self.url = url.rstrip("/")
        self.temp = tempfile.TemporaryDirectory(prefix="bob-curl-")
        self.folder = Path(self.temp.name)
        self.jar = self.folder / "cookies"
        self.headers = self.folder / "headers"
        self.csrf = ""
        code, _, _ = self.request("/login", urlencode({"password": (HERE / ".password").read_text().strip()}), form=True)
        assert code == 303, "Login did not return 303"
        self.csrf = self.json("/api/session")["csrf"]

    def request(self, path, data=None, form=False):
        headers = ["Origin: " + self.url]
        if data is not None:
            headers += ["Content-Type: " + ("application/x-www-form-urlencoded" if form else "application/json"), "X-CSRF-Token: " + self.csrf]
        self.headers.write_text("\n".join(headers) + "\n")
        self.headers.chmod(0o600)
        response = self.folder / "response"
        argv = ["/usr/bin/curl", "--noproxy", "*", "-sS", "--max-time", "15", "-b", str(self.jar), "-c", str(self.jar), "-H", "@" + str(self.headers), "-o", str(response), "-w", "%{http_code}", self.url + path]
        payload = None
        if data is not None:
            argv += ["--data-binary", "@-"]
            payload = data if form else json.dumps(data)
        started = time.monotonic()
        result = subprocess.run(argv, input=payload, text=True, capture_output=True, timeout=20)
        if result.returncode:
            raise RuntimeError("curl transport failed: " + str(result.returncode))
        return int(result.stdout), response.read_text(), time.monotonic() - started

    def json(self, path, data=None):
        code, body, _ = self.request(path, data)
        assert code in (200, 201, 202), (path, code, body[:200])
        return json.loads(body)

    def new(self):
        return self.json("/api/conversations", {})["id"]

    def submit(self, cid, message, request_id=None):
        return self.json("/api/messages", {"conversation_id": cid, "message": message, "request_id": request_id or str(uuid.uuid4())})

    def wait(self, cid, status=("done", "waiting", "error", "cancelled"), timeout=240):
        started = time.monotonic()
        while time.monotonic() - started < timeout:
            value = self.json("/api/conversations/" + cid)
            if value["messages"] and value["messages"][-1]["status"] in status:
                return value
            time.sleep(.25)
        raise RuntimeError("Timed out waiting for saved reply")

    def close(self):
        self.temp.cleanup()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8787")
    parser.add_argument("--output", type=Path, default=HERE / "evidence/failover-live.json")
    args = parser.parse_args()
    os.umask(0o077)
    client = Curl(args.url)
    ids, evidence = [], {"url": args.url, "started_at": time.time(), "checks": []}
    drill_path = HERE / ".drill.json"
    assert not drill_path.exists(), "Existing drill configuration must be handled by its owner"

    def configure(forced=None, hang=None, cooldown=3):
        value = {"conversation_ids": ids, "force_fail": forced or {}, "hang": hang or [], "cooldown_seconds": cooldown}
        temporary = drill_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(value))
        temporary.replace(drill_path)

    def new():
        cid = client.new()
        ids.append(cid)
        configure()
        return cid

    def record(name, value, started, **extra):
        message = value["messages"][-1]
        row = {"check": name, "conversation_id": value["id"], "status": message["status"], "provider": message.get("provider"), "content": message["content"], "attempts": message.get("attempts", []), "elapsed_seconds": round(time.monotonic() - started, 3), **extra}
        evidence["checks"].append(row)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, indent=2) + "\n")
        print(json.dumps({k: row[k] for k in ("check", "status", "provider", "elapsed_seconds")}), flush=True)

    try:
        cid = new()
        started = time.monotonic()
        client.submit(cid, "Remember this phrase for this conversation: violet kite.")
        value = client.wait(cid)
        assert value["messages"][-1]["status"] == "done", value["messages"][-1]
        client.submit(cid, "What phrase did I just ask you to remember? Reply with the phrase only.")
        value = client.wait(cid)
        assert "violet kite" in value["messages"][-1]["content"].lower()
        record("memory", value, started)

        for name, forced, expected in (
            ("codex_to_cursor", {"codex": "rate_limit"}, "cursor"),
            ("codex_cursor_to_gemini", {"codex": "rate_limit", "cursor": "network"}, "gemini"),
            ("three_failures_to_minimax", {"codex": "rate_limit", "cursor": "network", "gemini": "nonzero_exit"}, "minimax"),
        ):
            time.sleep(3.2)
            cid = new()
            configure(forced)
            started = time.monotonic()
            client.submit(cid, "Debug this chat connection only. Reply exactly: " + name + " verified.")
            value = client.wait(cid)
            record(name, value, started)
            assert value["messages"][-1]["status"] == "done" and value["messages"][-1]["provider"] == expected, value["messages"][-1]

        time.sleep(3.2)
        cid = new()
        configure({n: "network" for n in ("codex", "cursor", "gemini", "minimax")}, cooldown=5)
        started = time.monotonic()
        client.submit(cid, "Debug this chat connection only. Reply exactly: recovered on Codex.")
        value = client.wait(cid)
        assert value["messages"][-1]["status"] == "waiting"
        assert "queued" in value["messages"][-1]["content"] and len(value["messages"][-1]["attempts"]) == 4
        assert "retry_prompt" not in value
        evidence["all_down_health"] = client.json("/api/lanes?conversation_id=" + cid)
        record("all_down_queued", value, started)
        configure()
        value = client.wait(cid, status=("done", "error", "cancelled"))
        record("cooldown_automatic_recovery", value, started)
        assert value["messages"][-1]["provider"] == "codex" and len(value["messages"]) == 2

        marker = HERE / "sessions/drill-child.json"
        marker.unlink(missing_ok=True)
        cid = new()
        configure(hang=["codex"])
        started = time.monotonic()
        client.submit(cid, "Debug Stop: wait for my Stop button.")
        deadline = time.monotonic() + 15
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(.1)
        assert marker.exists(), "Stop drill did not launch a child"
        pids = json.loads(marker.read_text())
        client.json("/api/cancel", {"conversation_id": cid})
        value = client.wait(cid)
        assert value["messages"][-1]["status"] == "cancelled"
        for pid in [pids["parent"], *pids["children"]]:
            result = subprocess.run(["/bin/ps", "-p", str(pid), "-o", "stat="], capture_output=True, text=True)
            assert not result.stdout.strip() or result.stdout.strip().startswith("Z"), (pid, result.stdout)
        record("stop_kills_process_tree", value, started, pids=pids)
        configure()

        held = []
        with ExitStack() as stack:
            for name in ("codex", "cursor", "gemini", "minimax"):
                handle = stack.enter_context((ROOT / "conductor/locks" / ("lane-" + name + ".lock")).open("a+"))
                try:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    held.append(name + ": drill holds background lock")
                except BlockingIOError:
                    held.append(name + ": real background job holds lock")
            pair = [new(), new()]
            started = time.monotonic()
            for i, target in enumerate(pair):
                client.submit(target, "Reply exactly: interactive chat " + str(i + 1) + " works.")
            for target in pair:
                value = client.wait(target)
                assert value["messages"][-1]["status"] == "done"
                assert not any("another job" in a.get("error", "") for a in value["messages"][-1]["attempts"])
                record("background_locks_held", value, started, locks=held)

        cid = new()
        started = time.monotonic()
        request_id = str(uuid.uuid4())
        client.submit(cid, "merge #158", request_id)
        value = client.submit(cid, "merge #158", request_id)
        assert len(value["messages"]) == 2 and value["messages"][-1]["action_card"]["state"] == "refused"
        assert not value["messages"][-1]["action_card"]["executable"]
        record("merge_refusal_once_only", value, started)
        evidence["health"] = client.json("/api/lanes")
        evidence["finished_at"] = time.time()
        evidence["result"] = "PASS"
    except BaseException as exc:
        evidence["result"] = "FAIL"
        evidence["error"] = type(exc).__name__ + ": " + str(exc)[:1000]
        raise
    finally:
        for cid in ids:
            try:
                client.json("/api/cancel", {"conversation_id": cid})
            except Exception:
                pass
        drill_path.unlink(missing_ok=True)
        args.output.write_text(json.dumps(evidence, indent=2) + "\n")
        client.close()


if __name__ == "__main__":
    main()
