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
import traceback
from datetime import datetime, timezone
from pathlib import Path

# Import the reviewed checkout regardless of cwd or an inherited relative PYTHONPATH.
CANDIDATE_CODE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(CANDIDATE_CODE / name) for name in ("webchat", "services", "state")]

from texting_deploy_record import (atomic_json, atomic_text, claim_record, compact_evidence,
    disk_space, require_disk_space, reserve_recovery, release_recovery, failure_publish)
from deploy_parity import restart as restart_services, run, write
from live_redeploy_check import Client, require
from live_status_snapshot import build_live_status_snapshot
from providers import Redactor
from task_dispatch import task_queue


from integration_rubric import sessions as frozen_sessions, check_reply, style_errors

PREVIOUS = "a777736b3f0a37c82b0c4c62be8c91117c4c9881"
BRANCH = "draft/webbob-texting-minimax-probe-fix-2256"
CLEAN_BRANCH = "draft/webbob-clean-0927"
OWN_LANE = "lane-webbob-texting-minimax-probe-fix-2256"
RESTARTED_SCREENS = frozenset(("svc-webchat", "svc-job-runner"))
# runtime.runner_cycle/schedule_pass launch these bounded, one-shot processes.
OPTIONAL_SCREENS = frozenset(("svc-project-tick", "svc-conductor-pass"))
REQUIRED_SCRIPTS = frozenset(('deploy_texting_2256.py', 'record_texting_deploy_2256.py',
    'texting_deploy_record.py', 'test_deploy_texting_2256.py', 'test_deploy_screens_2256.py',
    'test_deploy_ancestry_2256.py', 'test_record_texting_deploy_2256.py', 'test_disk_evidence_2256.py',
    'isolated_replay_2256.py', 'test_isolated_replay_2256.py', 'test_deploy_scope_2256.py',
    'probe_texting_worker_2256.py', 'audit_texting_probes_2256.py', 'run_texting_checks_2256.py',
    'run_texting_reviews_2256.py', 'test_audit_texting_probes_2256.py'))


def activation_budget(root):
    """Count this release series' actual activations, including failed restarts."""
    attempts = []
    for path in (root / 'conductor/reviews').glob('WEBBOB-TEXTING-DEPLOYMENT-0927-attempt*.json'):
        row = json.loads(path.read_text())
        if row.get('release_series') in ('2055', '2256') and row.get('activated'):
            attempts.append(dict(path=str(path), attempt=row['attempt'], sha=row['sha']))
    require(len(attempts) < 5, 'The five 2055/2256 deployment activations are exhausted')
    return dict(maximum=5, prior_activations=attempts, next_activation=len(attempts) + 1)


def scoped_sessions(root, candidate):
    """Keep exact assertions for all frozen turns, with explicit execution scopes."""
    from isolated_replay_2256 import verify_proof
    sources = latest_sessions(root)
    live = [source for source in sources if source['source_id'].startswith('b33fac')]
    private = [source for source in sources if source not in live]
    require(len(live) == 1 and len(live[0]['exchanges']) == 9,
            'The original nine Web Bob production turns changed')
    require(sum(len(source['exchanges']) for source in private) == 10,
            'The original ten cross-project turns changed')
    proof = verify_proof(root / 'conductor/reviews/TEXTING-2256-isolated-replay.json', candidate, private)
    require(proof['all_pass'] and proof['captured_turns'] == proof['passed_turns'] == 10,
            'Same-SHA isolated cross-project replay did not pass all ten turns')
    for source in live:
        source['scope'] = 'production-webbob'
    return live, proof


def rollback_journal(evidence):
    keys = ('sha', 'attempt', 'release_series', 'draft_pr', 'record_owner', 'activated', 'rollback', 'previous_version',
            'previous_pins', 'snapshots', 'recovery_reserve', 'emergency_marker', 'child_log', 'before')
    result = {k: evidence[k] for k in keys if k in evidence}
    result['sessions'] = [dict(replay_id=cid) for cid in sorted(replay_conversations(evidence))]
    return result


def restore_release(root, evidence):
    """Recovery must run even if cancellation, reserve release, or evidence I/O fails."""
    errors = []
    try:
        release_recovery(evidence)
    except BaseException as error:
        errors.append('reserve: ' + str(error))
    try:
        evidence['cancelled_replay_jobs'] = [row['id'] for row in task_queue.cancel_replay(
            root, replay_conversations(evidence),
            'Texting deployment failed; claim revoked before release rollback.')]
    except BaseException as error:
        errors.append('cancel: ' + str(error))
    try:
        require(evidence['previous_version']['sha'] == PREVIOUS, 'Unexpected rollback baseline')
        evidence['rollback_result'] = restart(root, {k: Path(v) for k, v in evidence['snapshots'].items()},
                                             expected_exits=evidence.get('cancelled_replay_jobs', []))
        evidence['restored_pins'] = verify_pins(root, evidence['snapshots'])
        pair = version_pair(root, PREVIOUS)
        evidence.update(restored_version=pair['local'], restored_public_version=pair['public'], after=pair)
        require(evidence['rollback_result']['other_screens_unchanged'], 'Unrelated screens changed during rollback')
        evidence['rollback_version_verified'] = True
    except BaseException as error:
        errors.append('restore: ' + str(error))
    evidence['rolled_back'] = not errors
    if errors:
        evidence['rollback_error'] = '; '.join(errors)
    return evidence['rolled_back']


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


def version_pair(root, expected):
    """A required authenticated local/public assertion, never an optional public check."""
    password = root / 'conductor/webchat/.password'
    origin = (root / 'conductor/webchat/.public-origin').read_text().strip()
    require(bool(origin), 'Public origin is missing')
    versions = {}
    for name, url in (('local', 'http://127.0.0.1:8787'), ('public', origin)):
        client = Client(url, password)
        client.login()
        versions[name] = client.call('/api/version')
    require(all(value.get('sha') == expected for value in versions.values()),
            'Local/public version mismatch: ' + json.dumps(versions))
    return versions


def verify_pins(root, pins):
    observed = {name: str(Path((root / 'conductor/state' / (name + '-code-root')).read_text().strip()).resolve())
                for name in pins}
    require(observed == {name: str(Path(path).resolve()) for name, path in pins.items()},
            'Service code pins differ from requested release: ' + json.dumps(observed))
    return observed


def record_accepted_regression(evidence, key, row, fixture, worker="minimax"):
    """A named replay gate needs the exact task and its accepted saved answer."""
    from result_acceptance import check_answer
    require(row["prompt"] == fixture["prompt"] and row["kind"] == fixture["kind"],
            key + " assignment changed")
    require(row["worker"] == worker and row.get("model") == {"minimax": "MiniMax-M2.7", "gemini": "gemini-2.5-pro"}[worker] and
            row["status"] == "succeeded" and row.get("execution_started_at"),
            key + " did not execute successfully on " + worker)
    check_answer(row["prompt"], row["result"], kind=row["kind"])
    require(row.get("acceptance", {}).get("accepted") is True, key + " lacks semantic acceptance")
    require(row.get("result_sha256") == hashlib.sha256(row["result"].encode()).hexdigest(),
            key + " answer hash mismatch")
    path = Path(row.get("result_path") or "")
    require(path.is_file() and path.read_text().strip() == row["result"].strip(),
            key + " accepted deliverable is not saved")
    evidence[key].update(pass_check=True, worker=row["worker"], model=row["model"],
                         result_path=str(path), result_sha256=row["result_sha256"],
                         saved_report_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                         result=row["result"], acceptance=row["acceptance"])


def verify_worker_probes(root, candidate, sha):
    receipt = json.loads((root / "conductor/reviews/TEXTING-WORKER-2256.json").read_text())
    require(receipt["sha"] == sha and receipt["all_pass"] and len(receipt["jobs"]) == 3,
            "Fresh three-job MiniMax probe gate did not pass on this tip")
    require(receipt.get("guard_contradiction_rejects") == 0, "Worker probe guard contradiction")
    names = ("texting_regression_drafts_1658.json", "texting_action_plan_1605.json", "texting_jobcompletion_1107.json")
    for row, name in zip(receipt["jobs"], names):
        fixture = json.loads((candidate / "services/fixtures" / name).read_text())
        record_accepted_regression({name: {}}, name, row, fixture)
        require(row.get("evidence", {}).get("head") == sha, "Probe used stale repository evidence")
        require(hashlib.sha256(Path(row["prompt_file"]).read_bytes()).hexdigest() == row["worker_prompt_sha256"],
                "Probe worker prompt changed")
        require(hashlib.sha256(Path(row["result_path"]).read_bytes()).hexdigest() == row["saved_report_sha256"],
                "Probe accepted saved report changed")
    fixture = json.loads((candidate / "services/fixtures/texting_guard_consistency_1803.json").read_text())
    row = receipt["guard_consistency_job"]
    record_accepted_regression({"guard_consistency": {}}, "guard_consistency", row, fixture, worker="gemini")
    require(row.get("evidence", {}).get("head") == sha, "Gemini guard probe used stale evidence")
    require(hashlib.sha256(Path(row["prompt_file"]).read_bytes()).hexdigest() == row["worker_prompt_sha256"],
            "Gemini guard probe worker prompt changed")
    require(hashlib.sha256(Path(row["result_path"]).read_bytes()).hexdigest() == row["saved_report_sha256"],
            "Gemini guard probe accepted saved report changed")
    audit_path = root / "conductor/reviews/TEXTING-2256-probe-assertion-audit.json"
    audit = json.loads(audit_path.read_text())
    require(audit.get("sha") == sha and audit.get("all_pass") is True and
            audit.get("guard_contradiction_rejects") == 0 and len(audit.get("jobs", [])) == 4,
            "Fresh probe assertion audit did not pass on this tip")
    from audit_texting_probes_2256 import audit_probe
    observed = audit_probe(receipt, sha)
    require({key: value for key, value in audit.items() if key != "at"} == observed,
            "Probe assertion audit differs from the accepted saved reports")
    receipt["assertion_audit"] = dict(path=str(audit_path), sha256=hashlib.sha256(audit_path.read_bytes()).hexdigest(),
        all_pass=True, jobs=4, complete_outer_drafts=observed["complete_outer_drafts"],
        literal_guard_count=observed["literal_guard_count"], semantic_reviewed_count=observed["semantic_reviewed_count"])
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
    parser.add_argument("--tip", required=True)
    parser.add_argument("--record-owner", default="")
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
        record = root / ('conductor/reviews/WEBBOB-TEXTING-DEPLOYMENT-0927-attempt' + str(args.attempt) + '.json')
        try:
            evidence = json.loads(record.read_text())
        except (OSError, ValueError):
            evidence = dict(release)
        # The small journal is published first and can contain newer conversation IDs.
        identifiers = replay_conversations(evidence) | replay_conversations(release)
        release['sessions'] = [dict(replay_id=cid) for cid in identifiers]
        restored = restore_release(root, release)
        evidence.update({k: v for k, v in release.items() if k not in ('sessions',)})
        evidence.update(all_pass=False, status='FAIL_OR_ROLLBACK')
        evidence.setdefault('failure', 'Emergency rollback requested')
        failure_publish(record, root / 'conductor/reviews/WEBBOB-TEXTING-FAIL-2256.md', evidence,
                        'RESULT: FAIL_OR_ROLLBACK\nrollback_verified: ' + str(restored) + '\n')
        print('Rollback verified: ' + str(restored) + ' ' + PREVIOUS, flush=True)
        return 0 if restored else 1
    evidence = dict(all_pass=False, sessions=[], task_ids=[], started_jobs=[], sha=args.tip, release_series='2256')
    require(args.attempt >= 14, "2256 deployment attempts start at slot 14")
    record = root / ("conductor/reviews/WEBBOB-TEXTING-DEPLOYMENT-0927-attempt" + str(args.attempt) + ".json")
    if args.record_owner:
        initial = json.loads(record.read_text())
        require(initial.get('record_owner') == args.record_owner and initial.get('sha') == args.tip
                and initial.get('attempt') == args.attempt and initial.get('status') == 'PREFLIGHT',
                'Attempt record does not belong to this launcher')
        evidence.update(initial)
    else:
        evidence.update(started_at=time.time(), attempt=args.attempt, status='PREFLIGHT')
        claim_record(record, evidence)
    def interrupted(signum, frame):
        raise RuntimeError("Deployment interrupted or exceeded its total timeout: " + str(signum))
    for signum in (signal.SIGALRM, signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, interrupted)
    signal.alarm(args.timeout)
    def save():
        if activated:
            evidence.setdefault('free_space', {})['checkpoint'] = require_disk_space(root, candidate, evidence['status'])
        payload = json.loads(redact(json.dumps(compact_evidence(evidence), ensure_ascii=False)))
        # Persist new replay IDs before any job can be enqueued. No context dumps in the journal.
        if rollback:
            atomic_json(rollback / 'release.json', rollback_journal(payload))
        atomic_json(record, payload)
    activated = False
    rollback = None
    try:
        evidence.setdefault('free_space', {})['preflight'] = require_disk_space(root, candidate, 'PREFLIGHT')
        if not args.record_owner:
            reserve_recovery(record, evidence)
        evidence['free_space']['reserved'] = require_disk_space(root, candidate, 'RECOVERY_RESERVED')
        evidence['status'] = 'RUNNER_PREFLIGHT'
        evidence['imports'] = {name: str(Path(sys.modules[name].__file__).resolve()) for name in
                               ('deploy_parity', 'live_redeploy_check', 'providers', 'task_dispatch')}
        save()
        require(re.fullmatch(r'[0-9a-f]{40}', args.tip), 'A full reviewed SHA is required')
        require(candidate == CANDIDATE_CODE, 'Runner is not from the candidate checkout')
        evidence["preflight_screens"] = check_lane_isolation()
        evidence['activation_budget'] = activation_budget(root)
        sha = run(["git", "-C", candidate, "rev-parse", "HEAD"])
        require(sha == args.tip, "Reviewed candidate SHA changed")
        require(bool(args.draft_pr), "A draft PR is required for deployment")
        gate = root / "conductor/reviews/TEXTING-LIVE-2256.md"
        require("GATE: BOTH_PASS tip=" + args.tip[:7] in gate.read_text(), "Recorded BOTH_PASS gate missing")
        reviews = json.loads((root / "conductor/reviews/TEXTING-LIVE-2256.json").read_text())
        require(reviews["sha"] == sha and reviews["gate"] == "BOTH_PASS" and reviews["attempt"] == args.attempt,
                "Fresh review SHA/gate mismatch")
        for name in ("gemini", "minimax"):
            review = reviews["reviews"][name]
            output = Path(review["output"])
            require(review["exit"] == 0 and review["verdict"] == "PASS" and
                    hashlib.sha256(output.read_bytes()).hexdigest() == review["output_sha256"],
                    "Fresh review output is missing or changed: " + name)
            require(review['sha'] == sha and review['attempt'] == args.attempt and
                    hashlib.sha256(Path(review['context']).read_bytes()).hexdigest() == review['context_sha256'] == reviews['context_sha256'],
                    'Fresh review context is missing or changed: ' + name)
        evidence["fresh_reviews"] = reviews
        remote = dict(line.split()[::-1] for line in run([
            "git", "-C", candidate, "ls-remote", "origin", "refs/heads/" + BRANCH,
            "refs/heads/draft/webbob-clean-0927"]).splitlines())
        require(remote.get("refs/heads/" + BRANCH) == sha, "Remote candidate tip mismatch")
        clean = json.loads((root / "conductor/reviews/TEXTING-CLEAN-MERGE-2256.json").read_text())
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
        tests = json.loads((root / "conductor/reviews/TEXTING-2256-tests.json").read_text())
        require(tests["sha"] == sha and tests["suite_exit"] == tests["eval_exit"] == 0 and
                tests["eval"]["passed"] == tests["eval"]["total"], "Full suite/eval gate is not green for this SHA")
        require(tests["all_pass"] and all(x["exit"] == 0 and not x.get("skipped", 0)
                for x in tests["results"].values()), "Offline tests or browser proof did not pass")
        for name in ("webchat", "services", "eval", "browser"):
            result = tests["results"][name]
            require(hashlib.sha256(Path(result["log"]).read_bytes()).hexdigest() == result["log_sha256"],
                    "Offline test log changed: " + name)
        evidence["tests"] = tests
        runner_checks = json.loads((root / 'conductor/reviews/TEXTING-2256-runner-checks.json').read_text())
        require(runner_checks['sha'] == sha and runner_checks['all_pass'] and
                hashlib.sha256(Path(runner_checks['log']).read_bytes()).hexdigest() == runner_checks['log_sha256'],
                'Deploy runner tests did not pass on this tip')
        require(REQUIRED_SCRIPTS <= runner_checks['scripts'].keys(), 'Required deploy script hashes missing')
        for name, digest in runner_checks['scripts'].items():
            require(hashlib.sha256((candidate / 'reviews' / name).read_bytes()).hexdigest() == digest,
                    'Reviewed release script changed: ' + name)
        evidence['runner_checks'] = runner_checks
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
        held_probe = json.loads((candidate / "services/fixtures/texting_minimax_probe_2256.json").read_text())
        for field in ("prompt", "answer"):
            require(hashlib.sha256(held_probe[field].encode()).hexdigest() == held_probe[field + "_sha256"],
                    "Captured c63dc2f probe " + field + " changed")
        require(held_probe["prompt"] == regression_drafts["prompt"] and
                held_probe["kind"] == regression_drafts["kind"],
                "The c63dc2f/20bfc6f assignments differ; each would require its own replay")
        require(held_probe["error"] == "Missing concrete regression test drafts (setup, action and expected assertion required)",
                "Captured c63dc2f probe rejection changed")
        try:
            check_answer(held_probe["prompt"], held_probe["answer"], kind=held_probe["kind"])
        except ResultRejected as exc:
            require(held_probe["error"] in str(exc), "The c63dc2f probe rejection reason changed")
        else:
            raise RuntimeError("The c63dc2f buried-in-setup drafts were accepted")
        evidence["minimax_probe_2256_fixture_regression"] = dict(job_id=held_probe["job_id"],
            answer_sha256=held_probe["answer_sha256"], error=held_probe["error"], pass_check=True)
        guard_consistency = json.loads((candidate / "services/fixtures/texting_guard_consistency_1803.json").read_text())
        for field in ("prompt", "answer", "rejected_control"):
            require(hashlib.sha256(guard_consistency[field].encode()).hexdigest() == guard_consistency[field + "_sha256"],
                    "Captured 8e7eee34 " + field + " changed")
        try:
            check_answer(guard_consistency["prompt"], guard_consistency["answer"], kind=guard_consistency["kind"])
        except ResultRejected as exc:
            require(str(exc) == guard_consistency["error"], "The 8e7eee34 contradiction rejection changed")
        else:
            raise RuntimeError("The 8e7eee34 contradictory control was accepted")
        evidence["guard_consistency_fixture_regression"] = dict(job_id=guard_consistency["job_id"], pass_check=True)
        evidence["worker_probes"] = verify_worker_probes(root, candidate, sha)
        # Retest the authoritative failed observation before touching live.
        from reply_authority import format_operational_reply
        regression = json.loads((candidate / "webchat/fixtures/texting_diagdump_0810.json").read_text())
        corrected = format_operational_reply(regression["snapshot"], text=regression["message"])
        require(not style_errors(corrected), "Prior live failure still produces a diagnostic dump")
        evidence["prior_failure_regression"] = dict(session_id=regression["session_id"], turn=3,
                                                   question=regression["message"], reply=corrected, pass_check=True)
        client.login()
        previous_pair = version_pair(root, PREVIOUS)
        previous_version = previous_pair['local']
        evidence['previous_public_version'] = previous_pair['public']
        require(previous_version["sha"] == PREVIOUS and previous_version["sha"].startswith(args.expected_live), "Live changed since review")
        session = client.call("/api/session")
        require(not session.get("active_conversations") and not session.get("active_conversation"), "A chat reply is in flight")
        # Freeze the source before creating any replay conversations.
        evidence['sessions'], evidence['isolated_replay'] = scoped_sessions(root, candidate)
        evidence["previous_version"] = previous_version
        evidence['status'] = 'SNAPSHOTTING'
        save()
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        rollback = Path(evidence.get("planned_rollback") or root / "rollbacks" / ("webbob-texting-" + stamp))
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
        for path in set(snapshots.values()):
            require(json.loads((Path(path) / 'webbob-build.json').read_text())['sha'] == PREVIOUS,
                    'Rollback snapshot is not the required a777736 release')
        atomic_json(rollback / 'release.json', rollback_journal(evidence))
        atomic_text(rollback / "rollback.sh", "#!/bin/bash\nset -euo pipefail\n" + shlex.join([
            "env", "BOB_ROOT=" + str(root), "PYTHONPATH=" + os.pathsep.join(
                str(candidate / name) for name in ('webchat', 'services', 'state', 'reviews')), "TMPDIR=/private/tmp",
            sys.executable, str(Path(__file__).resolve()), "--root", str(root),
            "--candidate", str(candidate), "--attempt", str(args.attempt), "--tip", args.tip,
            "--rollback", str(rollback)]) + "\n")
        (rollback / "rollback.sh").chmod(0o700)
        save()
        evidence["activation_screens"] = check_lane_isolation()
        evidence['activation_budget'] = activation_budget(root)
        atomic_text(candidate / "webbob-build.json", json.dumps(dict(sha=sha, built_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))) + "\n")
        evidence['free_space']['before_activation'] = require_disk_space(root, candidate, 'BEFORE_ACTIVATION')
        activated = True
        evidence["activated"] = True
        evidence['status'] = 'ACTIVATING'
        save()
        evidence["restart"] = restart(root, dict(webchat=candidate, dispatch=candidate))
        require(evidence["restart"]["other_screens_unchanged"], "Unrelated screens changed during restart")
        evidence['activation_pins'] = verify_pins(root, dict(webchat=candidate, dispatch=candidate))
        client = Client(client.url, password_file)
        client.login()
        pair = version_pair(root, sha)
        evidence.update(version=pair['local'], public_version=pair['public'],
                        activation_verified=True, status='SMOKE')
        save()
        print("Deployed " + sha[:7] + "; rollback ready at " + str(rollback), flush=True)
        texting_smoke(client, root, evidence, save)
        require(evidence.get('texting_smoke', {}).get('all_pass'), 'Texting smoke did not pass')
        evidence['status'] = 'LIVE_REPLAY'
        save()
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
            source["replay_session_path"] = str(root / "conductor/webchat/sessions" / (cid + ".json"))
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
                rows, started = verify_executions(root, evidence["task_ids"])
                evidence['started_jobs'] = [row['id'] for row in started]
                save()
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
        evidence['final_versions'] = version_pair(root, sha)
        evidence['free_space']['after'] = require_disk_space(root, candidate, 'FINAL_GATE')
        _, verified_private = scoped_sessions(root, candidate)
        require(verified_private == evidence['isolated_replay'], 'Isolated replay proof changed during deployment')
        live_turns = sum(bool(x.get('request_id')) for s in evidence['sessions'] for x in s['exchanges'])
        require(live_turns == 9 and live_turns + verified_private['captured_turns'] == 19,
                'All 19 frozen turns must pass: nine production Web Bob and ten isolated cross-project turns')
        signal.alarm(0)
        evidence.update(all_pass=True, status='LIVE_PASS', finished_at=time.time())
        save()
        # The cross-vendor reviewer inspects this evidence before writing PASS.
        print("LIVE GATE GREEN: 9 production Web Bob turns and 10 isolated cross-project turns; " +
              str(len(started)) + " production executions. Evidence: " + str(record), flush=True)
        return 0
    except BaseException as exc:
        signal.alarm(0)
        evidence["finished_at"] = time.time()
        evidence["failure"] = redact(str(exc))
        evidence.update(all_pass=False, failed_stage=evidence.get('status'), status='FAIL_OR_ROLLBACK',
                        traceback=redact(traceback.format_exc()))
        # No write, read, or log operation may gate rollback after an evidence failure.
        if activated:
            restore_release(root, evidence)
        else:
            try:
                release_recovery(evidence)
            except OSError:
                pass
        try:
            evidence.setdefault('free_space', {})['after'] = disk_space(root, candidate, 'AFTER_RECOVERY')
        except OSError:
            pass
        evidence = json.loads(redact(json.dumps(compact_evidence(evidence), ensure_ascii=False)))
        report = ('RESULT: FAIL_OR_ROLLBACK\ntip: ' + evidence.get('sha', 'unresolved') +
                  '\nFailure: ' + evidence['failure'] + '\nRollback: ' + str(rollback) +
                  '\nrollback_verified: ' + str(evidence.get('rolled_back', False)) +
                  '\nevidence: ' + str(record) + '\n')
        failure_publish(record, root / 'conductor/reviews/WEBBOB-TEXTING-FAIL-2256.md', evidence, report)
        print("FAIL: " + evidence["failure"] + "; rollback verified=" + str(evidence.get("rolled_back", False)), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
