#!/usr/bin/env python3
"""Review-gated draft release, exact session replay, and verified rollback."""
import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from deploy_parity import restart, run, write
from live_redeploy_check import Client, require
from live_status_snapshot import build_live_status_snapshot
from providers import Redactor
from task_dispatch import task_queue


from integration_rubric import sessions as frozen_sessions, check_reply, style_errors


def latest_sessions(root):
    rows = frozen_sessions()
    for source in rows:
        saved = json.loads((root / "conductor/webchat/sessions" / (source["source_id"] + ".json")).read_text())
        asks = [m["content"] for m in saved["messages"] if m.get("role") == "user"]
        require(asks == [e["message"] for e in source["exchanges"]], "Original Jeff session changed since regression capture")
    return rows


def submit(client, cid, text):
    request = str(uuid.uuid4())
    value = client.call("/api/messages", dict(conversation_id=cid, message=text, request_id=request))
    deadline = time.monotonic() + 120
    while True:
        answer = next(m for m in value["messages"] if m.get("role") == "assistant" and m.get("request_id") == request)
        if answer["status"] == "done":
            return answer
        require(answer["status"] not in ("error", "cancelled", "waiting"), "Reply failed or providers unavailable")
        require(time.monotonic() < deadline, "Reply timed out")
        time.sleep(.5)
        value = client.call("/api/conversations/" + cid)


def verify_executions(root, identifiers):
    rows = [task_queue.tasks(root)[identifier] for identifier in identifiers]
    for row in rows:
        require(row["status"] not in ("failed", "cancelled"), "Replay job failed: " + row["id"] + " " + str(row.get("error")))
    started = [r for r in rows if r.get("execution_started_at") and r["status"] in ("running", "succeeded")]
    return rows, started


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--draft-pr", default="")
    parser.add_argument("--expected-live", default="dff84e3")
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--rollback", type=Path)
    parser.add_argument("--attempt", type=int, choices=(1, 2, 3), default=1)
    args = parser.parse_args()
    root, candidate = args.root.resolve(), args.candidate.resolve()
    os.umask(0o077)
    os.environ["BOB_ROOT"] = str(root)
    sys.path.insert(0, str(candidate / "services"))
    password_file = root / "conductor/webchat/.password"
    redact = Redactor(root, password_file.read_text().strip())
    client = Client("http://127.0.0.1:8787", password_file)
    if args.rollback:
        release = json.loads((args.rollback / "release.json").read_text())
        cancelled = task_queue.cancel_replay(root, {s["replay_id"] for s in release.get("sessions", []) if s.get("replay_id")},
                                            "Integration live replay cancelled for release rollback.")
        expected = set(release.get("cancelled_replay_jobs", [])) | {r["id"] for r in cancelled}
        restored = restart(root, {key: Path(path) for key, path in release["snapshots"].items()}, expected_exits=expected)
        client.login()
        require(client.call("/api/version")["sha"] == release["previous_version"]["sha"], "Rollback version mismatch")
        require(restored["other_screens_unchanged"], "Unrelated screens changed during rollback")
        origin = root / "conductor/webchat/.public-origin"
        if origin.exists():
            public = Client(origin.read_text().strip(), password_file)
            public.login()
            require(public.call("/api/version")["sha"] == release["previous_version"]["sha"], "Public rollback version mismatch")
        print("Rollback verified: " + release["previous_version"]["sha"])
        return 0
    evidence = dict(all_pass=False, sessions=[], task_ids=[], started_jobs=[])
    record = root / ("conductor/reviews/WEBBOB-INTEGRATE-DEPLOYMENT-0927-attempt" + str(args.attempt) + ".json")
    def save():
        write(record, redact(json.dumps(evidence, indent=2, ensure_ascii=False)) + "\n")
        if rollback:
            write(rollback / "release.json", redact(json.dumps(evidence, indent=2, ensure_ascii=False)) + "\n")
    activated = False
    rollback = None
    try:
        sha = run(["git", "-C", candidate, "rev-parse", "HEAD"])
        require(bool(args.draft_pr), "A draft PR is required for deployment")
        evidence.update(sha=sha, draft_pr=args.draft_pr)
        require(run(["git", "-C", candidate, "branch", "--show-current"]) == "draft/webbob-integrate-2057", "Wrong branch")
        require(not run(["git", "-C", candidate, "status", "--porcelain"]), "Candidate has uncommitted changes")
        pr = json.loads(run(["gh", "pr", "view", args.draft_pr, "--json", "isDraft,headRefOid,state,baseRefName"]))
        require(pr["isDraft"] and pr["state"] == "OPEN" and pr["headRefOid"] == sha and pr["baseRefName"] == "draft/webbob-clean-0927", "Draft PR does not match tested candidate")
        tests = json.loads((candidate / "webchat/evidence/integrate-tests.json").read_text())
        require(tests["sha"] == sha and tests["suite_exit"] == tests["eval_exit"] == 0 and
                tests["eval"]["passed"] == tests["eval"]["total"], "Full suite/eval gate is not green for this SHA")
        evidence["tests"] = tests
        client.login()
        previous_version = client.call("/api/version")
        require(previous_version["sha"].startswith(args.expected_live), "Live changed since review")
        session = client.call("/api/session")
        require(not session.get("active_conversations") and not session.get("active_conversation"), "A chat reply is in flight")
        # Freeze the source before creating any replay conversations.
        evidence["sessions"] = latest_sessions(root)
        evidence["previous_version"] = previous_version
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        rollback = root / "rollbacks" / ("webbob-integrate-" + stamp)
        rollback.mkdir(mode=0o700)
        evidence["rollback"] = str(rollback)
        previous, snapshots, copied = {}, {}, {}
        for name in ("webchat", "dispatch"):
            pin = root / "conductor/state" / (name + "-code-root")
            previous[name] = str(Path(pin.read_text().strip()).resolve())
            if previous[name] not in copied:
                target = rollback / ("previous-" + name)
                shutil.copytree(previous[name], target, ignore=shutil.ignore_patterns(
                    ".git", ".password", ".session-secret", "keys.env", ".env", ".env.*", "sessions",
                    "node_modules", "__pycache__", "uploads", "evidence", "task-runs"))
                copied[previous[name]] = str(target)
            snapshots[name] = copied[previous[name]]
        evidence.update(previous_pins=previous, snapshots=snapshots)
        write(rollback / "release.json", redact(json.dumps(evidence, indent=2, ensure_ascii=False)) + "\n")
        write(rollback / "rollback.sh", "#!/bin/bash\nset -euo pipefail\n" + shlex.join([
            sys.executable, str(candidate / "webchat/deploy_integrate.py"), "--root", str(root),
            "--candidate", str(candidate), "--rollback", str(rollback)]) + "\n")
        save()
        write(candidate / "webbob-build.json", json.dumps(dict(sha=sha, built_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))) + "\n")
        activated = True
        evidence["restart"] = restart(root, dict(webchat=candidate, dispatch=candidate))
        require(evidence["restart"]["other_screens_unchanged"], "Unrelated screens changed during restart")
        client = Client(client.url, password_file)
        client.login()
        evidence["version"] = client.call("/api/version")
        require(evidence["version"]["sha"] == sha, "Live /api/version differs from candidate")
        origin = root / "conductor/webchat/.public-origin"
        if origin.exists():
            public = Client(origin.read_text().strip(), password_file)
            public.login()
            evidence["public_version"] = public.call("/api/version")
            require(evidence["public_version"]["sha"] == sha, "Public /api/version differs from candidate")
        save()
        print("Deployed " + sha[:7] + "; rollback ready at " + str(rollback), flush=True)
        for source in evidence["sessions"]:
            cid = client.new()
            source["replay_id"] = cid
            save()
            for index, exchange in enumerate(source["exchanges"]):
                before = build_live_status_snapshot(root)
                turn_started = time.time()
                answer = submit(client, cid, exchange["message"])
                after = build_live_status_snapshot(root)
                ids = answer.get("task_ids", [answer["task_id"]] if answer.get("task_id") else [])
                evidence["task_ids"].extend(ids)
                errors = check_reply(answer, exchange, cid, turn_started, before, after, task_queue.tasks(root))
                api_jobs = {r["id"]: r for r in client.call("/api/jobs")["dispatch"]}
                require(all(i in api_jobs for i in ids), "Receipt jobs missing from authenticated Jobs API")
                exchange.update(after=answer["content"], provider=answer["provider"], request_id=answer["request_id"],
                                message_id=answer["id"],
                                task_ids=ids, errors=errors, pass_check=not errors, turn_started_at=turn_started,
                                receipts=[task_queue.tasks(root)[i] for i in ids],
                                observations={"reply": answer.get("status_observation"),
                                              "before": {k: before[k] for k in ("captured_at", "work", "work_counts", "queue_counts", "queue_jobs", "inspection")},
                                              "after": {k: after[k] for k in ("captured_at", "work", "work_counts", "queue_counts", "queue_jobs", "inspection")}})
                save()
                require(not errors, source["source_id"] + " turn " + str(index + 1) + ": " + "; ".join(errors))
                verify_executions(root, evidence["task_ids"])
                print(source["source_id"][:8] + " turn " + str(index + 1) + ": PASS — " + answer["content"], flush=True)
        deadline, last_progress = time.monotonic() + args.timeout, 0
        while True:
            rows, started = verify_executions(root, evidence["task_ids"])
            evidence["jobs"] = [{k: row.get(k) for k in ("id", "title", "worker", "status", "execution_started_at", "worktree", "branch", "publication", "result_path", "result_sha256", "kind", "model", "evidence", "error")} for row in rows]
            evidence["started_jobs"] = [row["id"] for row in started]
            save()
            if len(started) == len(rows) and all(r["status"] == "succeeded" for r in rows):
                break
            require(time.monotonic() < deadline, "Timed out waiting for every replay job to finish")
            if time.monotonic() - last_progress > 20:
                print("Replay executions: " + str(len(started)) + "/" + str(len(rows)) + "; " +
                      ", ".join((row.get("title") or row["id"]) + "=" + row["status"] for row in rows), flush=True)
                last_progress = time.monotonic()
            time.sleep(2)
        coding = [r for r in rows if r["kind"] == "coding"]
        require(len({r["worktree"] for r in coding}) == len(coding), "Coding jobs share a worktree")
        for row in coding:
            require(row["worker"] in ("codex", "cursor", "claude"), "Coding job has no file worker")
            require(run(["git", "-C", row["worktree"], "branch", "--show-current"]) == row["branch"] == "draft/" + row["id"], "Job left assigned draft branch")
        for row in rows:
            if row["worker"] in ("gemini", "minimax"):
                require(row.get("model") in ("gemini-2.5-pro", "MiniMax-M2.7"), "API execution model not recorded")
                require(not row.get("worktree"), "API report worker gained a code worktree")
                require(row["status"] == "succeeded" and Path(row.get("result_path") or "").is_file(), "API report did not complete")
        # Verify all replay jobs completed before accepting their replies.
        # Queue entries and an executing timestamp alone cannot pass.
        # Reconciliation must not rewrite the historical dispatch receipts.
        for source in evidence["sessions"]:
            messages = client.call("/api/conversations/" + source["replay_id"])["messages"]
            source["completions"] = []
            for exchange in source["exchanges"]:
                receipt = next(m for m in messages if m.get("request_id") == exchange["request_id"] and m.get("role") == "assistant")
                require(receipt["content"] == exchange["after"], "Original reply was rewritten after dispatch")
                require(receipt["id"] == exchange["message_id"] and
                        receipt.get("status_observation") == exchange["observations"]["reply"],
                        "Original status observation was rewritten or lost")
            for message in messages:
                if message.get("task_status"):
                    errors = style_errors(message["content"], 1 + len(message.get("task_ids", [])))
                    source["completions"].append(dict(content=message["content"], status=message["task_status"], errors=errors))
                    require(not errors, "Completion reply: " + "; ".join(errors))
        require(client.call("/api/version")["sha"] == sha, "Live version changed during replay")
        evidence.update(all_pass=True, finished_at=time.time())
        save()
        # The cross-vendor reviewer inspects this evidence before writing PASS.
        print("LIVE GATE GREEN: " + str(sum(len(s["exchanges"]) for s in evidence["sessions"])) +
              " replies; " + str(len(started)) + " actual executions. Evidence: " + str(record), flush=True)
        return 0
    except BaseException as exc:
        evidence["failure"] = redact(str(exc))
        if activated:
            try:
                evidence["cancelled_replay_jobs"] = [row["id"] for row in task_queue.cancel_replay(
                    root, {s["replay_id"] for s in evidence["sessions"] if s.get("replay_id")},
                    "Integration live replay failed; claim revoked before release rollback.")]
                evidence["rollback_result"] = restart(root, {key: Path(path) for key, path in evidence["snapshots"].items()},
                                                     expected_exits=evidence["cancelled_replay_jobs"])
                client = Client(client.url, password_file)
                client.login()
                evidence["restored_version"] = client.call("/api/version")
                require(evidence["restored_version"]["sha"] == evidence["previous_version"]["sha"], "Rollback version mismatch")
                require(evidence["rollback_result"]["other_screens_unchanged"], "Unrelated screens changed during rollback")
                origin = root / "conductor/webchat/.public-origin"
                if origin.exists():
                    public = Client(origin.read_text().strip(), password_file)
                    public.login()
                    evidence["restored_public_version"] = public.call("/api/version")
                    require(evidence["restored_public_version"]["sha"] == evidence["previous_version"]["sha"], "Public rollback version mismatch")
                evidence["rolled_back"] = True
            except BaseException as rollback_error:
                evidence["rollback_error"] = redact(str(rollback_error))
        save()
        report = ("# Web Bob integration deployment — FAIL\n\nCandidate: `" + evidence.get("sha", "unresolved") +
                  "`\n\nDraft PR: " + args.draft_pr + "\n\nFailing check: " + evidence["failure"] +
                  "\n\nRollback: `" + str(rollback) + "`; verified: " + str(evidence.get("rolled_back", False)) +
                  "\n\nEvidence: `" + str(record) + "`.\n")
        for directory in (root / "conductor/reviews",):
            write(directory / "WEBBOB-INTEGRATE-FAIL-0927.md", report)
        print("FAIL: " + evidence["failure"] + "; rollback verified=" + str(evidence.get("rolled_back", False)), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
