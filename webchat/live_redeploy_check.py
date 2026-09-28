#!/usr/bin/env python3
"""Authenticated release checks. Live mode creates three real, draft-only jobs."""
import argparse
import http.cookiejar
import json
import os
import re
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from live_status_snapshot import build_live_status_snapshot
from providers import Redactor
from task_dispatch import task_queue

CHECKS = ("going", "claude161", "push2", "go")


class CheckFailure(RuntimeError):
    pass


def require(condition, reason):
    if not condition:
        raise CheckFailure(reason)


class Client:
    def __init__(self, url, password_file):
        self.url = url.rstrip("/")
        self.password_file = password_file
        self.csrf = None
        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def login(self):
        # Neither credentials nor cookies enter command arguments or evidence.
        request = urllib.request.Request(self.url + "/login", headers={"Origin": self.url},
            data=urllib.parse.urlencode({"password": self.password_file.read_text().strip()}).encode())
        self.open(request, parse=False)
        self.csrf = self.call("/api/session").get("csrf")
        require(bool(self.csrf), "Authenticated session did not supply a CSRF token")

    def open(self, request, parse=True):
        try:
            with self.opener.open(request, timeout=15) as response:
                require(200 <= response.status < 300, "Non-success HTTP response")
                require(response.headers.get("X-Bob-Webchat") == "1", "Unexpected server identity")
                return json.load(response) if parse else response.read()
        except urllib.error.HTTPError as exc:
            # An error body is never treated as a Bob reply (including hold/go).
            raise CheckFailure(f"HTTP {exc.code} at {urllib.parse.urlsplit(request.full_url).path}") from None
        except (OSError, ValueError):
            raise CheckFailure("Transport or JSON failure at " + urllib.parse.urlsplit(request.full_url).path) from None

    def call(self, route, data=None):
        headers = {"Origin": self.url}
        if data is not None:
            headers.update({"Content-Type": "application/json", "X-CSRF-Token": self.csrf or ""})
        return self.open(urllib.request.Request(self.url + route, headers=headers,
            data=json.dumps(data).encode() if data is not None else None))

    def new(self):
        return self.call("/api/conversations", {})["id"]

    def submit(self, cid, text, request_id=None):
        request_id = request_id or str(uuid.uuid4())
        value = self.call("/api/messages", dict(conversation_id=cid, message=text, request_id=request_id))
        deadline = time.monotonic() + 25
        while True:
            answer = next((m for m in value["messages"]
                           if m.get("request_id") == request_id and m["role"] == "assistant"), None)
            require(answer is not None, "No saved assistant response for this request")
            if answer["status"] == "done":
                require(bool(answer["content"].strip()), "Empty reply")
                require("start a job:" not in answer["content"].lower(), "Reply requires special job syntax")
                return value, answer
            require(answer["status"] not in ("error", "cancelled", "waiting"), "Reply did not finish successfully")
            require(time.monotonic() < deadline, "Reply deadline expired")
            time.sleep(.1)
            value = self.call("/api/conversations/" + cid)


def observation(root):
    snap = build_live_status_snapshot(root)
    return {k: snap[k] for k in ("inspection", "work_counts", "work", "screen_lanes")}


def verify_four(client, root, output):
    redact = Redactor(root, client.password_file.read_text().strip())
    evidence = dict(url=client.url, started_at=time.time(),
                    checks={name: dict(pass_check=False, error="Not completed") for name in CHECKS}, all_pass=False)

    def save():
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(".tmp")
        temporary.write_text(redact(json.dumps(evidence, indent=2)) + "\n")
        temporary.chmod(0o600)
        temporary.replace(output)

    def submit(case, cid, prompt, request_id=None):
        value, answer = client.submit(cid, prompt, request_id)
        case.setdefault("exchanges", []).append(dict(conversation_id=cid, prompt=prompt,
            request_id=answer["request_id"], answer=answer["content"], provider=answer.get("provider"),
            status=answer["status"], task_ids=answer.get("task_ids", [answer["task_id"]] if answer.get("task_id") else []),
            intent_state=value["intent_state"]))
        return value, answer

    def check_jobs(case, cid, answer, count):
        ids = answer.get("task_ids", [answer["task_id"]] if answer.get("task_id") else [])
        rows = [row for row in task_queue.tasks(root).values() if row["conversation_id"] == cid]
        case["jobs"] = [{k: row.get(k) for k in ("id", "conversation_id", "request_id", "requested_worker", "worker",
                         "status", "kind", "title", "attempts", "group_id", "group_index")} for row in rows]
        require(len(ids) == len(rows) == count and set(ids) == {r["id"] for r in rows},
                f"Expected {count} durable jobs matching the receipt")
        api_rows = {row["id"]: row for row in client.call("/api/jobs")["dispatch"]}
        for row in rows:
            require(row["id"] in ids and row["id"] in api_rows, "Receipt/API/journal disagree")
            require(row["id"] not in answer["content"], "Raw job ID leaked into casual receipt")
            require(row["status"] not in ("failed", "cancelled"), "Accepted job already failed; inspect queue")
            require(row["requested_worker"] not in ("grok", "xai"), "Forbidden worker selected")
        return rows

    try:
        client.login()
    except Exception as exc:
        for name in CHECKS:
            evidence["checks"][name]["error"] = "Authentication: " + str(exc)
        save()
        return evidence

    for name in CHECKS:
        case = evidence["checks"][name]
        try:
            cid = client.new()
            case["conversation_id"] = cid
            if name == "going":
                before = observation(root)
                _, answer = submit(case, cid, "is it going now?")
                after = observation(root)
                case.update(before=before, after=after)
                require(answer.get("provider") == "state", "Status was not generated from server observations")
                require(all(before["inspection"].values()) and all(after["inspection"].values()), "Live observation source unavailable")
                counts = {s["work_counts"]["running"] for s in (before, after)}
                if counts != {0}:
                    require(answer["content"].count("running for") in counts, "Running-worker count disagrees with process observations")
                stable = {r["pid"]: r for r in before["work"] if r.get("pid")}
                for row in after["work"]:
                    if row.get("pid") in stable:
                        from worker_evidence import clean
                        require(clean(row["title"], 95).strip(" .;:") in answer["content"], "Status omitted active work: " + row["title"])
                _, details = submit(case, cid, "status with screen names and PIDs")
                current = observation(root)
                common = {r["screen"] for r in after["screen_lanes"]} & {r["screen"] for r in current["screen_lanes"]}
                for screen in common:
                    require(screen in details["content"], "Detailed status omitted screen: " + screen)
                require(not [r for r in task_queue.tasks(root).values() if r["conversation_id"] == cid], "Status created a job")
            elif name in ("claude161", "push2"):
                prompt = "Claude review PR #161" if name == "claude161" else "push WebJam and AdoptIQ"
                request_id = str(uuid.uuid4())
                _, answer = submit(case, cid, prompt, request_id)
                rows = check_jobs(case, cid, answer, 1 if name == "claude161" else 2)
                if name == "claude161":
                    require(rows[0]["requested_worker"] == "claude", "Claude request routed elsewhere")
                else:
                    require({r["title"] for r in rows} == {"WebJam", "AdoptIQ"}, "Project jobs have wrong scope")
                _, repeated = submit(case, cid, prompt, request_id)
                check_jobs(case, cid, repeated, len(rows))
                case["replay_no_duplicates"] = True
            else:
                held, _ = submit(case, cid, "hold off")
                require(bool(held["intent_state"]["holds"]), "Hold was not persisted")
                resumed, answer = submit(case, cid, "go")
                require(not resumed["intent_state"]["holds"], "Go did not clear the saved hold")
                require("hold" not in answer["content"].lower(), "Go returned a stale hold claim")
                saved = json.loads((root / "conductor/webchat/sessions" / (cid + ".json")).read_text())
                require(not saved["intent_state"]["holds"], "Cleared hold was not saved to disk")
                _, answer = submit(case, cid, "Are we still on hold?")
                require(answer["content"] == "Ready when you are.", "Follow-up revived a stale hold")
                require(not [r for r in task_queue.tasks(root).values() if r["conversation_id"] == cid], "Hold/go replayed unwanted work")
            case.update(pass_check=True, error=None)
        except Exception as exc:
            case.update(pass_check=False, error=str(exc))
        save()
        print(name + ": " + ("PASS" if case["pass_check"] else "FAIL — " + redact(case["error"])), flush=True)
    evidence.update(all_pass=all(evidence["checks"][name]["pass_check"] for name in CHECKS), finished_at=time.time())
    save()
    return evidence


def follow_through(client, root, output, evidence, expected_sha, timeout=1200):
    """Queue acceptance alone is not a release pass; observe execution and delivery."""
    redact = Redactor(root, client.password_file.read_text().strip())
    evidence["initial_acceptance_all_pass"] = evidence["all_pass"]
    evidence["all_pass"] = False
    def save():
        output.write_text(redact(json.dumps(evidence, indent=2)) + "\n")
    save()
    try:
        require(evidence["initial_acceptance_all_pass"], "; ".join(
            name + ": " + str(case.get("error")) for name, case in evidence["checks"].items() if not case["pass_check"]))
        version = client.call("/api/version")
        require(version["sha"] == expected_sha and version["short_sha"] == expected_sha[:7], "version: deployed SHA mismatch")
        cid = client.new()
        _, answer = client.submit(cid, "what version/build are you")
        require(answer["content"] == expected_sha[:7], "version: chat did not return only its own SHA")
        evidence["version"] = dict(pass_check=True, **version, chat_answer=answer["content"])
        deadline = time.monotonic() + timeout
        while True:
            rows = task_queue.tasks(root)
            ready = True
            for name in ("claude161", "push2"):
                case = evidence["checks"][name]
                jobs = [rows[row["id"]] for row in case["jobs"]]
                case["execution"] = [{key: job.get(key) for key in
                    ("id", "requested_worker", "worker", "status", "attempts", "execution_started_at", "error", "acceptance", "review_source", "publication")}
                    for job in jobs]
                for job in jobs:
                    require(job["status"] not in ("failed", "cancelled"), name + ": " + job["id"] + " " + str(job.get("error")))
                if name == "claude161":
                    job = jobs[0]
                    if job["status"] != "succeeded":
                        ready = False
                    else:
                        require(job.get("acceptance", {}).get("accepted"), "claude161: review was not accepted")
                        require(job.get("review_source", {}).get("number") == 161, "claude161: no verified PR source")
                        saved = client.call("/api/conversations/" + case["conversation_id"])
                        delivered = [m for m in saved["messages"] if m.get("task_id") == job["id"] and m.get("task_status") == "succeeded"]
                        require(bool(delivered) and job["result"] in delivered[-1]["content"], "claude161: final review not delivered")
                        case["result"] = job["result"]
                        case["actual_worker"] = job["worker"]
                else:
                    for job in jobs:
                        if job["status"] != "succeeded":
                            ready = False
                        else:
                            require(job.get("publication", {}).get("sha"), "push2: no verified draft push for " + job["id"])
                            require(job["publication"]["branch"] == "draft/" + job["id"], "push2: wrong draft branch")
            save()
            if ready:
                break
            require(time.monotonic() < deadline, "execution: timed out waiting for PR review and both verified draft pushes")
            time.sleep(2)
        evidence["all_pass"] = True
    except Exception as exc:
        evidence["failure"] = str(exc)
    evidence["finished_at"] = time.time()
    save()
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--url", default="http://127.0.0.1:8787")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-sha", help="Required in live mode; full deployed git SHA")
    parser.add_argument("--isolated", action="store_true", help="Use a temporary listener/queue and forbid model calls")
    args = parser.parse_args()
    os.umask(0o077)
    if not args.isolated:
        if not args.expected_sha:
            parser.error("--expected-sha is required for live release verification")
        client = Client(args.url, args.root / "conductor/webchat/.password")
        result = verify_four(client, args.root, args.output)
        result = follow_through(client, args.root, args.output, result, args.expected_sha)
    else:
        from app import Chat, Server
        class NoModels:
            def health(self, conversation_id=None):
                return dict(providers={}, order=[], fast_order=[])
            def reply(self, *args):
                raise AssertionError("These checks must not need model generation")
        with tempfile.TemporaryDirectory(prefix="webbob-redeploy-rehearsal-") as temporary:
            root = Path(temporary)
            chat = Chat(root / "conductor/webchat", root, NoModels())
            server = Server(("127.0.0.1", 0), chat)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            try:
                result = verify_four(Client(f"http://127.0.0.1:{server.server_port}", chat.folder / ".password"), root, args.output)
            finally:
                server.shutdown()
                server.server_close()
                chat.close()
    return 0 if result["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
