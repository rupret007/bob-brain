#!/usr/bin/env python3
"""Review-gated draft release, exact session replay, and verified rollback."""
import argparse
import json
import os
import re
import shlex
import shutil
import signal
import hashlib
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from deploy_parity import restart as restart_services, run, write
from live_redeploy_check import Client, require
from live_status_snapshot import build_live_status_snapshot
from providers import Redactor
from task_dispatch import task_queue


from integration_rubric import sessions as frozen_sessions, check_reply, style_errors

TIP = 'd32d0f7244d191b85b429c3c8d0228ec0c9b4670'
PREVIOUS = "a777736b3f0a37c82b0c4c62be8c91117c4c9881"
BRANCH = "draft/webbob-texting-regression-drafts-fix-1658"
CLEAN_BRANCH = "draft/webbob-clean-0927"
OWN_LANE = "lane-webbob-texting-regression-drafts-fix-1658"
RESTARTED_SCREENS = frozenset(("svc-webchat", "svc-job-runner"))
# runtime.runner_cycle/schedule_pass launch these bounded, one-shot processes.
OPTIONAL_SCREENS = frozenset(("svc-project-tick", "svc-conductor-pass"))


def screen_isolation(before, after):
    """Protect every existing durable svc-* peer; jobs/lanes are not services."""
    protected = {name: identity for name, identity in before.items()
                 if name.startswith("svc-") and name not in RESTARTED_SCREENS | OPTIONAL_SCREENS}
    changed = {name: dict(before=identity, after=after.get(name))
               for name, identity in protected.items() if after.get(name) != identity}
    ignored = {name: dict(before=before.get(name), after=after.get(name))
               for name in sorted(before.keys() | after.keys())
               if not name.startswith("svc-") or name in RESTARTED_SCREENS | OPTIONAL_SCREENS}
    return dict(other_screens_unchanged=not changed,
                screen_isolation_policy="durable-svc-peers-1403",
                protected_screens=protected, changed_durable_screens=changed,
                ignored_screens=ignored)


def restart(root, pins, expected_exits=()):
    """Reuse the locked restart and its raw snapshots, replacing only the guard."""
    result = restart_services(root, pins)
    result["legacy_other_screens_unchanged"] = result["other_screens_unchanged"]
    # These are cancelled job IDs, never a screen-name allowlist.
    result["cancelled_replay_job_ids"] = list(expected_exits)
    result.update(screen_isolation(result["before"], result["after"]))
    return result


def check_lane_isolation():
    from runtime import screen_sessions
    screens = screen_sessions()
    others = sorted(name for name in screens if name.startswith("lane-webbob-") and name != OWN_LANE)
    require(not others, "Other active Web Bob lanes: " + ", ".join(others))
    return screens


def verify_clean_merge(repo, sha, merge_sha):
    """Fetch and check both objects in the release repository, not the feature checkout."""
    ref = "refs/remotes/origin/" + CLEAN_BRANCH

    def fetch_clean():
        run(["git", "-C", repo, "fetch", "--no-tags", "origin",
             "refs/heads/" + CLEAN_BRANCH + ":" + ref])
        require(run(["git", "-C", repo, "rev-parse", ref]) == merge_sha,
                "Fetched clean branch differs from recorded clean merge")

    fetch_clean()
    retried_missing_object = False
    for attempt in range(2):
        try:
            run(["git", "-C", repo, "merge-base", "--is-ancestor", sha, merge_sha])
            break
        except subprocess.CalledProcessError as exc:
            if exc.returncode == 128 and attempt == 0:
                # Git 128 is an object/repository error, never a negative ancestry result.
                retried_missing_object = True
                fetch_clean()
                continue
            if exc.returncode == 1:
                raise RuntimeError("Reviewed tip is not an ancestor of the clean merge") from exc
            if exc.returncode == 128:
                raise RuntimeError("Ancestry object/repository error persists after fetch in " + str(repo)) from exc
            raise
    require(not run(["git", "-C", repo, "diff", "--name-only", sha, merge_sha]),
            "Clean merge tree differs from reviewed tip")
    return dict(repo=str(repo), sha=sha, merge_sha=merge_sha, fetched_ref=ref,
                retried_missing_object=retried_missing_object, ancestor=True, tree_equal=True)


def replay_conversations(evidence):
    identifiers = {s["replay_id"] for s in evidence.get("sessions", []) if s.get("replay_id")}
    for key in ("jobcompletion_regression", "action_plan_regression", "regression_drafts_regression"):
        regression = evidence.get(key, {}).get("conversation_id")
        if regression:
            identifiers.add(regression)
    return identifiers


def record_accepted_regression(evidence, key, row, fixture):
    """A named replay gate needs the exact task and its accepted saved answer."""
    from result_acceptance import check_answer
    require(row["prompt"] == fixture["prompt"] and row["kind"] == fixture["kind"],
            key + " assignment changed")
    require(row["worker"] == "minimax" and row.get("model") == "MiniMax-M2.7" and
            row["status"] == "succeeded" and row.get("execution_started_at"),
            key + " did not execute successfully on MiniMax")
    check_answer(row["prompt"], row["result"], kind=row["kind"])
    require(row.get("acceptance", {}).get("accepted") is True, key + " lacks semantic acceptance")
    require(row.get("result_sha256") == hashlib.sha256(row["result"].encode()).hexdigest(),
            key + " answer hash mismatch")
    path = Path(row.get("result_path") or "")
    require(path.is_file() and path.read_text().strip() == row["result"].strip(),
            key + " accepted deliverable is not saved")
    evidence[key].update(pass_check=True, worker=row["worker"], model=row["model"],
                         result_path=str(path), result_sha256=row["result_sha256"],
                         result=row["result"], acceptance=row["acceptance"])


def verify_worker_probes(root, candidate, sha):
    receipt = json.loads((root / "conductor/reviews/TEXTING-WORKER-1658.json").read_text())
    require(receipt["sha"] == sha and receipt["all_pass"] and len(receipt["jobs"]) == 3,
            "Fresh three-job MiniMax probe gate did not pass on this tip")
    names = ("texting_regression_drafts_1658.json", "texting_action_plan_1605.json", "texting_jobcompletion_1107.json")
    for row, name in zip(receipt["jobs"], names):
        fixture = json.loads((candidate / "services/fixtures" / name).read_text())
        record_accepted_regression({name: {}}, name, row, fixture)
        require(row.get("evidence", {}).get("head") == sha, "Probe used stale repository evidence")
        require(hashlib.sha256(Path(row["prompt_file"]).read_bytes()).hexdigest() == row["worker_prompt_sha256"],
                "Probe worker prompt changed")
    return receipt


def texting_smoke(client, root, evidence, save):
    cid = client.new()
    smoke = evidence["texting_smoke"] = dict(conversation_id=cid, all_pass=False, exchanges=[])
    save()
    for prompt in ("texting help", "yes wbtxt-00000000000000000000000000000000"):
        answer = submit(client, cid, prompt)
        require(answer.get("provider") == "texting" and answer.get("texting"), "Live texting route did not handle smoke")
        require(not answer.get("task_ids") and not answer.get("task_id"), "Texting smoke dispatched work")
        require("drafts stay unsent" in answer["content"] if prompt == "texting help" else
                answer["content"].startswith("Nothing sent."), "Texting consent/help behavior changed")
        smoke["exchanges"].append(dict(prompt=prompt, reply=answer["content"], provider=answer["provider"], pass_check=True))
        save()
    saved = json.loads((root / "conductor/webchat/sessions" / (cid + ".json")).read_text())
    require(not saved.get("_texting", {}).get("drafts") and not saved.get("_texting", {}).get("audit"),
            "Texting smoke unexpectedly created a draft or delivery attempt")
    require(not any(row["conversation_id"] == cid for row in task_queue.tasks(root).values()),
            "Texting smoke created a job")
    smoke.update(all_pass=True, draft_count=0, delivery_audit_count=0, jobs=0)
    save()
    print("Live texting smoke: PASS; help and invalid confirmation, no delivery attempt", flush=True)


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
    parser.add_argument("--expected-live", default="a777736")
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--rollback", type=Path)
    parser.add_argument("--attempt", type=int, required=True)
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
        cancelled = task_queue.cancel_replay(root, replay_conversations(release),
                                            "Texting deployment live replay cancelled for release rollback.")
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
    require(args.attempt >= 10, "1658 deployment attempts start at slot 10")
    record = root / ("conductor/reviews/WEBBOB-TEXTING-DEPLOYMENT-0927-attempt" + str(args.attempt) + ".json")
    with record.open("x") as stream:
        json.dump(dict(all_pass=False, sha=TIP, status="PREFLIGHT", started_at=time.time()), stream)
    evidence.update(started_at=time.time(), attempt=args.attempt)
    def interrupted(signum, frame):
        raise RuntimeError("Deployment interrupted or exceeded its total timeout: " + str(signum))
    for signum in (signal.SIGALRM, signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, interrupted)
    signal.alarm(args.timeout)
    def save():
        write(record, redact(json.dumps(evidence, indent=2, ensure_ascii=False)) + "\n")
        if rollback:
            write(rollback / "release.json", redact(json.dumps(evidence, indent=2, ensure_ascii=False)) + "\n")
    activated = False
    rollback = None
    try:
        evidence["preflight_screens"] = check_lane_isolation()
        sha = run(["git", "-C", candidate, "rev-parse", "HEAD"])
        require(sha == TIP, "Reviewed candidate SHA changed")
        require(bool(args.draft_pr), "A draft PR is required for deployment")
        gate = root / "conductor/reviews/TEXTING-LIVE-1658.md"
        require("GATE: BOTH_PASS tip=" + TIP[:7] in gate.read_text(), "Recorded BOTH_PASS gate missing")
        reviews = json.loads((root / "conductor/reviews/TEXTING-LIVE-1658.json").read_text())
        require(reviews["sha"] == sha and reviews["gate"] == "BOTH_PASS" and reviews["attempt"] == args.attempt,
                "Fresh review SHA/gate mismatch")
        for name in ("gemini", "minimax"):
            review = reviews["reviews"][name]
            output = Path(review["output"])
            require(review["exit"] == 0 and review["verdict"] == "PASS" and
                    hashlib.sha256(output.read_bytes()).hexdigest() == review["output_sha256"],
                    "Fresh review output is missing or changed: " + name)
        evidence["fresh_reviews"] = reviews
        remote = dict(line.split()[::-1] for line in run([
            "git", "-C", candidate, "ls-remote", "origin", "refs/heads/" + BRANCH,
            "refs/heads/draft/webbob-clean-0927"]).splitlines())
        require(remote.get("refs/heads/" + BRANCH) == sha, "Remote candidate tip mismatch")
        clean = json.loads((root / "conductor/reviews/TEXTING-CLEAN-MERGE-1658.json").read_text())
        require(remote.get("refs/heads/draft/webbob-clean-0927") == clean["merge_sha"], "Clean remote changed")
        evidence["clean_ancestry"] = verify_clean_merge(root / "bob-brain", sha, clean["merge_sha"])
        evidence.update(review_gate=dict(path=str(gate), sha256=hashlib.sha256(gate.read_bytes()).hexdigest()),
                        clean_merge=clean, remote=remote)
        evidence.update(sha=sha, draft_pr=args.draft_pr)
        require(run(["git", "-C", candidate, "branch", "--show-current"]) == BRANCH, "Wrong branch")
        require(not run(["git", "-C", candidate, "status", "--porcelain"]), "Candidate has uncommitted changes")
        pr = json.loads(run(["gh", "pr", "view", args.draft_pr, "--json", "isDraft,headRefOid,state,baseRefName"]))
        # Like 0356, GitHub may mark the draft MERGED after a regular branch merge.
        # Accept only the exact reviewed head and clean base; never undraft it.
        require(pr["isDraft"] and pr["state"] in ("OPEN", "MERGED") and pr["headRefOid"] == sha and pr["baseRefName"] == "draft/webbob-clean-0927", "Draft PR does not match tested candidate")
        tests = json.loads((root / "conductor/reviews/TEXTING-1658-tests.json").read_text())
        require(tests["sha"] == sha and tests["suite_exit"] == tests["eval_exit"] == 0 and
                tests["eval"]["passed"] == tests["eval"]["total"], "Full suite/eval gate is not green for this SHA")
        require(tests["all_pass"] and all(x["exit"] == 0 and not x.get("skipped", 0)
                for x in tests["results"].values()), "Offline tests or browser proof did not pass")
        for name in ("webchat", "services", "eval", "browser"):
            result = tests["results"][name]
            require(hashlib.sha256(Path(result["log"]).read_bytes()).hexdigest() == result["log_sha256"],
                    "Offline test log changed: " + name)
        evidence["tests"] = tests
        from result_acceptance import check_coding_answer, check_answer, ResultRejected
        incomplete = json.loads((candidate / "services/fixtures/texting_verification_0810.json").read_text())
        try:
            check_coding_answer(incomplete["answer"])
        except ResultRejected:
            evidence["incomplete_verification_regression"] = dict(job_id=incomplete["job_id"], pass_check=True)
        else:
            raise RuntimeError("The 0810 incomplete-verification answer was accepted")
        completion = json.loads((candidate / "services/fixtures/texting_jobcompletion_1035.json").read_text())
        try:
            check_answer(completion["prompt"], completion["answer"], kind=completion["kind"])
        except ResultRejected:
            evidence["incomplete_deliverable_regression"] = dict(job_id=completion["job_id"], pass_check=True)
        else:
            raise RuntimeError("The 1035 exploratory-only answer was accepted")
        check_answer(completion["prompt"], completion["complete_answer"], kind=completion["kind"])
        recent = json.loads((candidate / "services/fixtures/texting_jobcompletion_1107.json").read_text())
        require(recent["prompt"] == completion["prompt"] and recent["kind"] == completion["kind"],
                "The 1035/1107 prompts differ; each would require its own replay")
        require(hashlib.sha256(recent["answer"].encode()).hexdigest() == recent["answer_sha256"],
                "Captured dd47c4cb answer changed")
        try:
            check_answer(recent["prompt"], recent["answer"], kind=recent["kind"])
        except ResultRejected:
            evidence["incomplete_deliverable_1107_regression"] = dict(job_id=recent["job_id"], pass_check=True)
        else:
            raise RuntimeError("The 1107 malformed/ungrounded answer was accepted")
        replay_json = json.loads((candidate / "services/fixtures/texting_jobcompletion_1403.json").read_text())
        require(hashlib.sha256(replay_json["answer"].encode()).hexdigest() == replay_json["answer_sha256"],
                "Captured 1403 answer changed")
        for answer in (replay_json["answer"], replay_json["complete_answer"].split("```json")[0]):
            try:
                check_answer(replay_json["prompt"], answer, kind=replay_json["kind"])
            except ResultRejected:
                pass
            else:
                raise RuntimeError("The 1403 incomplete/JSON-less answer was accepted")
        check_answer(replay_json["prompt"], replay_json["complete_answer"], kind=replay_json["kind"])
        evidence["completion_json_1403_regression"] = dict(job_id=replay_json["job_id"], pass_check=True)
        action_plan = json.loads((candidate / "services/fixtures/texting_action_plan_1605.json").read_text())
        require(hashlib.sha256(action_plan["answer"].encode()).hexdigest() == action_plan["answer_sha256"],
                "Captured f2c47c4c answer changed")
        try:
            check_answer(action_plan["prompt"], action_plan["answer"], kind=action_plan["kind"])
        except ResultRejected as exc:
            require(action_plan["error"] in str(exc), "The f2c47c4c rejection reason changed")
        else:
            raise RuntimeError("The f2c47c4c inline-fixture plan was accepted")
        check_answer(action_plan["prompt"], action_plan["complete_answer"], kind=action_plan["kind"])
        evidence["action_plan_fixture_regression"] = dict(job_id=action_plan["job_id"], pass_check=True)
        regression_drafts = json.loads((candidate / "services/fixtures/texting_regression_drafts_1658.json").read_text())
        for field in ("prompt", "answer"):
            require(hashlib.sha256(regression_drafts[field].encode()).hexdigest() == regression_drafts[field + "_sha256"],
                    "Captured 20bfc6f " + field + " changed")
        try:
            check_answer(regression_drafts["prompt"], regression_drafts["answer"], kind=regression_drafts["kind"])
        except ResultRejected as exc:
            require(regression_drafts["error"] in str(exc), "The 20bfc6f rejection reason changed")
        else:
            raise RuntimeError("The 20bfc6f nested-only drafts were accepted")
        check_answer(regression_drafts["prompt"], regression_drafts["complete_answer"], kind=regression_drafts["kind"])
        evidence["regression_drafts_fixture_regression"] = dict(job_id=regression_drafts["job_id"], pass_check=True)
        evidence["worker_probes"] = verify_worker_probes(root, candidate, sha)
        # Retest the authoritative failed observation before touching live.
        from reply_authority import format_operational_reply
        regression = json.loads((candidate / "webchat/fixtures/texting_diagdump_0810.json").read_text())
        corrected = format_operational_reply(regression["snapshot"], text=regression["message"])
        require(not style_errors(corrected), "Prior live failure still produces a diagnostic dump")
        evidence["prior_failure_regression"] = dict(session_id=regression["session_id"], turn=3,
                                                   question=regression["message"], reply=corrected, pass_check=True)
        client.login()
        previous_version = client.call("/api/version")
        require(previous_version["sha"] == PREVIOUS and previous_version["sha"].startswith(args.expected_live), "Live changed since review")
        session = client.call("/api/session")
        require(not session.get("active_conversations") and not session.get("active_conversation"), "A chat reply is in flight")
        # Freeze the source before creating any replay conversations.
        evidence["sessions"] = latest_sessions(root)
        evidence["previous_version"] = previous_version
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        rollback = root / "rollbacks" / ("webbob-texting-" + stamp)
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
            "env", "PYTHONPATH=" + str(candidate / "webchat"), "TMPDIR=/private/tmp",
            sys.executable, str(Path(__file__).resolve()), "--root", str(root),
            "--candidate", str(candidate), "--attempt", str(args.attempt), "--rollback", str(rollback)]) + "\n")
        (rollback / "rollback.sh").chmod(0o700)
        save()
        evidence["activation_screens"] = check_lane_isolation()
        write(candidate / "webbob-build.json", json.dumps(dict(sha=sha, built_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))) + "\n")
        activated = True
        evidence["activated"] = True
        save()
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
        texting_smoke(client, root, evidence, save)
        # Replay the precise substantive failure through the existing live queue.
        # This extra conversation is also covered by rollback claim revocation.
        cid = client.new()
        evidence["jobcompletion_regression"] = dict(conversation_id=cid, source_job_id=recent["job_id"],
            source_job_ids=[recent["job_id"], completion["job_id"]], pass_check=False)
        save()
        regression_job = task_queue.enqueue(root, cid, str(uuid.uuid4()), completion["prompt"],
                                            worker="minimax", kind=completion["kind"],
                                            title="Web Bob — Review and regression test-case drafts (1035/1107 replay)")
        evidence["jobcompletion_regression"]["job_id"] = regression_job["id"]
        evidence["task_ids"].append(regression_job["id"])
        save()
        cid = client.new()
        evidence["action_plan_regression"] = dict(conversation_id=cid, source_job_id=action_plan["job_id"], pass_check=False)
        save()
        action_plan_job = task_queue.enqueue(root, cid, str(uuid.uuid4()), action_plan["prompt"],
                                            worker="minimax", kind=action_plan["kind"],
                                            title="Web Bob — Action plan acceptance (f2c47c4c replay)")
        evidence["action_plan_regression"]["job_id"] = action_plan_job["id"]
        evidence["task_ids"].append(action_plan_job["id"])
        save()
        cid = client.new()
        evidence["regression_drafts_regression"] = dict(conversation_id=cid, source_job_id=regression_drafts["job_id"], pass_check=False)
        save()
        drafts_job = task_queue.enqueue(root, cid, str(uuid.uuid4()), regression_drafts["prompt"],
                                      worker="minimax", kind=regression_drafts["kind"],
                                      title="Web Bob — Outer regression drafts (20bfc6f replay)")
        evidence["regression_drafts_regression"]["job_id"] = drafts_job["id"]
        evidence["task_ids"].append(drafts_job["id"])
        save()
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
            for key, fixture in (("jobcompletion_regression", completion), ("action_plan_regression", action_plan),
                                 ("regression_drafts_regression", regression_drafts)):
                row = next(row for row in rows if row["id"] == evidence[key]["job_id"])
                if row["status"] == "succeeded":
                    record_accepted_regression(evidence, key, row, fixture)
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
            acceptance = row.get("acceptance", {})
            require(acceptance.get("accepted") is True, "Coding result has no acceptance")
            proof = acceptance.get("coding_evidence", {})
            require(proof.get("sha") == run(["git", "-C", row["worktree"], "rev-parse", "HEAD"]),
                    "Coding acceptance is not bound to the final commit")
            from mini_worker import coding_commands
            required = coding_commands(row.get("project") or "")
            if required:
                validation = proof.get("validation") or {}
                require(validation.get("all_pass") is True and validation.get("sha") == proof["sha"],
                        "Coding project lacks fresh passing validation")
                checks = validation.get("checks", [])
                require([check["command"] for check in checks] == required,
                        "Coding result omitted required project checks")
                require(validation["started_at"] >= row["execution_started_at"], "Stale coding validation")
                for check in checks:
                    require(check["exit"] == 0 and hashlib.sha256(Path(check["log"]).read_bytes()).hexdigest() == check["sha256"],
                            "Coding check failed or its output changed")
            evidence.setdefault("coding_verifications", []).append(dict(job_id=row["id"], project=row.get("project"), **proof))
            require(run(["git", "-C", row["worktree"], "branch", "--show-current"]) == row["branch"] == "draft/" + row["id"], "Job left assigned draft branch")
        for row in rows:
            check_answer(row["prompt"], row["result"], kind=row["kind"])
            require(row.get("acceptance", {}).get("accepted") is True, "Replay result has no semantic acceptance")
            require(row.get("result_sha256") == hashlib.sha256(row["result"].encode()).hexdigest(),
                    "Replay answer changed after acceptance")
            if row["worker"] in ("gemini", "minimax"):
                require(row.get("model") in ("gemini-2.5-pro", "MiniMax-M2.7"), "API execution model not recorded")
                require(not row.get("worktree"), "API report worker gained a code worktree")
                require(row["status"] == "succeeded" and Path(row.get("result_path") or "").is_file(), "API report did not complete")
                require(Path(row["result_path"]).read_text().strip() == row["result"].strip(),
                        "Saved API report differs from accepted deliverables")
        require(all(evidence[key]["pass_check"] for key in ("jobcompletion_regression", "action_plan_regression", "regression_drafts_regression")),
                "Required MiniMax regression reports did not pass")
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
        signal.alarm(0)
        evidence.update(all_pass=True, finished_at=time.time())
        save()
        # The cross-vendor reviewer inspects this evidence before writing PASS.
        print("LIVE GATE GREEN: " + str(sum(len(s["exchanges"]) for s in evidence["sessions"])) +
              " replies; " + str(len(started)) + " actual executions. Evidence: " + str(record), flush=True)
        return 0
    except BaseException as exc:
        signal.alarm(0)
        evidence["finished_at"] = time.time()
        evidence["failure"] = redact(str(exc))
        if activated:
            try:
                evidence["cancelled_replay_jobs"] = [row["id"] for row in task_queue.cancel_replay(
                    root, replay_conversations(evidence),
                    "Texting deployment live replay failed; claim revoked before release rollback.")]
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
        report = ("# Web Bob texting deployment — FAIL\n\nCandidate: `" + evidence.get("sha", "unresolved") +
                  "`\n\nDraft PR: " + args.draft_pr + "\n\nFailing check: " + evidence["failure"] +
                  "\n\nRollback: `" + str(rollback) + "`; verified: " + str(evidence.get("rolled_back", False)) +
                  "\n\nEvidence: `" + str(record) + "`.\n")
        for directory in (root / "conductor/reviews",):
            write(directory / "WEBBOB-TEXTING-FAIL-1658.md", report)
        print("FAIL: " + evidence["failure"] + "; rollback verified=" + str(evidence.get("rolled_back", False)), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
