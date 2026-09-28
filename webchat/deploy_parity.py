#!/usr/bin/env python3
"""Pinned draft deploy; snapshot first, restart two services, verify or roll back."""
import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def run(argv, **kwargs):
    return subprocess.run([str(a) for a in argv], capture_output=True, text=True, check=True, timeout=60, **kwargs).stdout.strip()


def write(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value)
    temporary.replace(path)


def restart(root, pins, expected_exits=()):
    # Use the same supervisor lock as watchdog; no competing automatic restart.
    from state import lock
    from runtime import screen_sessions, stop_service_process, service_lock_held
    with lock("supervisor"):
        before = screen_sessions()
        listener = subprocess.run(["lsof", "-t", "-iTCP:8787", "-sTCP:LISTEN"], capture_output=True, text=True, timeout=10)
        pids = set(listener.stdout.split())
        if len(pids) > 1 or listener.returncode not in (0, 1):
            raise RuntimeError("restart: cannot identify webchat listener")
        pid = int(next(iter(pids))) if pids else None
        if pid:
            command = run(["ps", "-p", pid, "-o", "command="])
            if str(root) not in command or "/webchat/app.py" not in command:
                raise RuntimeError("restart: listener ownership mismatch")
        for name, code in pins.items():
            write(root / "conductor/state" / (name + "-code-root"), str(code) + "\n")
        for name in ("svc-webchat", "svc-job-runner"):
            if name in before:
                run(["screen", "-S", before[name], "-X", "quit"])
        stop_service_process("job-runner")
        if pid:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        for _ in range(60):
            if not pid:
                break
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            time.sleep(.25)
        else:
            raise RuntimeError("restart: old webchat did not exit")
        env = dict(os.environ, BOB_ROOT=str(root), BOB_WEBCHAT_DISPATCH="1", BOB_WEBCHAT_DRILLS="0")
        run(["screen", "-dmS", "svc-webchat", "/bin/bash", root / "conductor/webchat/run.sh"], env=env)
        run(["screen", "-dmS", "svc-job-runner", "/bin/bash", root / "conductor/services/job-runner.sh"], env=env)
        for _ in range(80):
            try:
                with urllib.request.urlopen("http://127.0.0.1:8787/login", timeout=1) as response:
                    healthy = response.status == 200 and response.headers.get("X-Bob-Webchat") == "1"
                if healthy and service_lock_held("job-runner"):
                    break
            except OSError:
                pass
            time.sleep(.25)
        else:
            raise RuntimeError("restart: webchat or job-runner did not become healthy")
        after = screen_sessions()
    unrelated = {name: identity for name, identity in before.items()
                 if name not in ("svc-webchat", "svc-job-runner") and name not in expected_exits}
    return dict(before=before, after=after, restarted_services=["webchat", "job-runner"],
                permitted_replay_exits=list(expected_exits),
                other_screens_unchanged=all(after.get(name) == identity for name, identity in unrelated.items()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--draft-pr", required=True)
    args = parser.parse_args()
    root, candidate = args.root.resolve(), args.candidate.resolve()
    os.umask(0o077)
    os.environ["BOB_ROOT"] = str(root)
    sys.path.insert(0, str(candidate / "services"))
    from live_redeploy_check import Client, verify_four, follow_through, require
    from providers import Redactor
    from task_dispatch import task_queue
    reviews = root / "conductor/reviews"
    sha = run(["git", "-C", candidate, "rev-parse", "HEAD"])
    require(run(["git", "-C", candidate, "branch", "--show-current"]) == "draft/webbob-parity-1633", "Wrong candidate branch")
    require(not run(["git", "-C", candidate, "status", "--porcelain"]), "Candidate is not clean")
    run(["git", "-C", candidate, "merge-base", "--is-ancestor", "7c9ed94", sha])
    pr = json.loads(run(["gh", "pr", "view", args.draft_pr, "--json", "isDraft,headRefOid,baseRefName"]))
    require(pr["isDraft"] and pr["headRefOid"] == sha and pr["baseRefName"] == "draft/webbob-clean-0927", "Draft PR does not match candidate/base")
    client = Client("http://127.0.0.1:8787", root / "conductor/webchat/.password")
    client.login()
    session = client.call("/api/session")
    require(not session.get("active_conversations") and not session.get("active_conversation"), "A chat reply is in flight; retry after it finishes")
    redact = Redactor(root, client.password_file.read_text().strip())
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    rollback = root / "rollbacks" / ("webbob-parity-" + stamp)
    rollback.mkdir(mode=0o700)
    previous, snapshots = {}, {}
    for name in ("webchat", "dispatch"):
        pin = root / "conductor/state" / (name + "-code-root")
        previous[name] = Path(pin.read_text().strip()).resolve() if pin.exists() else root / "conductor"
        copy = rollback / ("previous-" + name)
        shutil.copytree(previous[name], copy, ignore=shutil.ignore_patterns(
            ".git", ".password", ".session-secret", "keys.env", "sessions", "node_modules", "__pycache__", "uploads", "evidence", "task-runs"))
        snapshots[name] = copy
    evidence = dict(sha=sha, draft_pr=args.draft_pr, rollback=str(rollback), previous_pins={k:str(v) for k,v in previous.items()},
                    snapshots={k:str(v) for k,v in snapshots.items()}, all_pass=False)
    record = reviews / "WEBBOB-PARITY-DEPLOYMENT-0927.json"
    write(rollback / "release.json", json.dumps(evidence, indent=2) + "\n")
    def save():
        write(record, redact(json.dumps(evidence, indent=2)) + "\n")
    save()
    activated = False
    try:
        write(candidate / "webbob-build.json", json.dumps(dict(sha=sha, built_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))) + "\n")
        activated = True
        evidence["deployment"] = restart(root, dict(webchat=candidate, dispatch=candidate))
        save()
        print("Deployed " + sha[:7] + "; rollback " + str(rollback), flush=True)
        client = Client(client.url, client.password_file)
        checks_path = reviews / "WEBBOB-PARITY-LIVE-0927.json"
        checks = verify_four(client, root, checks_path)
        checks = follow_through(client, root, checks_path, checks, sha)
        evidence["live_checks"] = checks
        require(checks["all_pass"], checks.get("failure", "Live checks failed"))
        print("Review finished; both project drafts pushed and verified. Checking public Jobs UI.", flush=True)
        screenshot = reviews / "WEBBOB-PARITY-JOBS-0927.png"
        origin = (root / "conductor/webchat/.public-origin").read_text().strip()
        env = dict(os.environ, BOB_PLAYWRIGHT_MODULE=str(root / "conductor/webchat/node_modules/playwright"))
        browser = subprocess.run(["node", str(candidate / "webchat/capture_parity.cjs"), str(root), origin, sha,
                                  str(screenshot), str(reviews / "WEBBOB-PARITY-BROWSER-0927.json")],
                                 capture_output=True, text=True, timeout=120, env=env)
        require(browser.returncode == 0, "public Jobs/assets: " + browser.stderr[-1500:])
        for name in ("claude161", "push2"):
            for job in checks["checks"][name]["jobs"]:
                row = task_queue.tasks(root)[job["id"]]
                require(row["status"] != "failed", name + ": job failed during browser check: " + str(row.get("error")))
        evidence.update(all_pass=True, jobs_screenshot=str(screenshot), finished_at=time.time())
        save()
        write(root / "conductor/LOOP-TIME-TO-TEST-0927.txt",
              "PASS\nSHA: " + sha + "\nDraft PR: " + args.draft_pr + "\nJobs screenshot: " + str(screenshot) +
              "\nRollback: " + str(rollback) + "\nPR #161 actual reviewer: " + checks["checks"]["claude161"]["actual_worker"] +
              "\nTests: full webchat/services discovery + JavaScript; see reviews/WEBBOB-PARITY-TESTS-0927.txt\n" +
              "Live checks: status, PR review completion, two verified project draft pushes, hold off/go, own build SHA, public assets and Jobs.\n")
        print("PASS " + sha[:7] + " " + args.draft_pr + " " + str(screenshot), flush=True)
        return 0
    except Exception as exc:
        evidence["failure"] = redact(str(exc))
        if activated:
            try:
                evidence["rollback_result"] = restart(root, snapshots)
                evidence["rolled_back"] = True
            except Exception as rollback_error:
                evidence["rollback_error"] = redact(str(rollback_error))
        save()
        write(reviews / "WEBBOB-REDEPLOY-FAIL-0927-b.md", "# Web Bob parity redeploy — FAIL\n\n" +
              "Candidate: `" + sha + "`\n\nDraft PR: " + args.draft_pr + "\n\nExact failing check: " + evidence["failure"] +
              "\n\nRollback: `" + str(rollback) + "`. Restored: " + str(evidence.get("rolled_back", False)) +
              "\n\nEvidence: WEBBOB-PARITY-DEPLOYMENT-0927.json and WEBBOB-PARITY-LIVE-0927.json.\n")
        print("FAIL " + evidence["failure"] + "; rolled back=" + str(evidence.get("rolled_back", False)), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
