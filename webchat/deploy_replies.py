#!/usr/bin/env python3
"""Draft-only replies release: fresh rollback, two restarts, exact live replay."""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from deploy_parity import run, write, restart
from live_redeploy_check import Client, require, verify_four, follow_through
from live_replies_check import verify_replies
from providers import Redactor
from task_dispatch import task_queue


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
    sha = run(["git", "-C", candidate, "rev-parse", "HEAD"])
    require(run(["git", "-C", candidate, "branch", "--show-current"]) == "draft/webbob-replies-1720", "Wrong candidate branch")
    require(not run(["git", "-C", candidate, "status", "--porcelain"]), "Candidate is not clean")
    run(["git", "-C", candidate, "merge-base", "--is-ancestor", "dcc2c8e", sha])
    pr = json.loads(run(["gh", "pr", "view", args.draft_pr, "--json", "isDraft,headRefOid,baseRefName"]))
    require(pr["isDraft"] and pr["headRefOid"] == sha and pr["baseRefName"] == "draft/webbob-clean-0927", "Draft PR mismatch")
    client = Client("http://127.0.0.1:8787", root / "conductor/webchat/.password")
    client.login()
    session = client.call("/api/session")
    require(not session.get("active_conversations") and not session.get("active_conversation"), "A chat reply is in flight")
    redact = Redactor(root, client.password_file.read_text().strip())
    rollback = root / "rollbacks" / ("webbob-replies-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    rollback.mkdir(mode=0o700)
    previous, snapshots = {}, {}
    for name in ("webchat", "dispatch"):
        pin = root / "conductor/state" / (name + "-code-root")
        previous[name] = Path(pin.read_text().strip()).resolve() if pin.exists() else root / "conductor"
        copy = rollback / ("previous-" + name)
        shutil.copytree(previous[name], copy, ignore=shutil.ignore_patterns(
            ".git", ".password", ".session-secret", "keys.env", "sessions", "node_modules", "__pycache__", "uploads", "evidence", "task-runs"))
        snapshots[name] = copy
    reviews = root / "conductor/reviews"
    evidence = dict(sha=sha, draft_pr=args.draft_pr, rollback=str(rollback), previous_pins={k:str(v) for k,v in previous.items()}, all_pass=False)
    record = reviews / "WEBBOB-REPLIES-DEPLOYMENT-0927.json"
    def save():
        write(record, redact(json.dumps(evidence, indent=2, ensure_ascii=False)) + "\n")
    write(rollback / "release.json", json.dumps(evidence, indent=2) + "\n")
    save()
    activated = False
    try:
        write(candidate / "webbob-build.json", json.dumps(dict(sha=sha, built_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))) + "\n")
        activated = True
        evidence["deployment"] = restart(root, dict(webchat=candidate, dispatch=candidate))
        save()
        print("Deployed " + sha[:7] + "; fresh rollback " + str(rollback), flush=True)
        client = Client(client.url, client.password_file)
        replies = verify_replies(client, root, reviews / "WEBBOB-REPLIES-LIVE-0927.json")
        evidence["replies"] = replies
        save()
        require(replies["all_pass"], replies.get("failure", "Exact session replay failed"))
        print("Four real project jobs started. Running existing parity checks.", flush=True)
        parity_path = reviews / "WEBBOB-REPLIES-PARITY-0927.json"
        parity = verify_four(client, root, parity_path)
        parity = follow_through(client, root, parity_path, parity, sha)
        evidence["parity"] = parity
        save()
        require(parity["all_pass"], parity.get("failure", "Existing parity checks failed"))
        origin = (root / "conductor/webchat/.public-origin").read_text().strip()
        browser = subprocess.run(["node", str(candidate / "webchat/capture_parity.cjs"), str(root), origin, sha,
                                  str(reviews / "WEBBOB-REPLIES-JOBS-0927.png"), str(reviews / "WEBBOB-REPLIES-BROWSER-0927.json")],
                                 capture_output=True, text=True, timeout=120,
                                 env=dict(os.environ, BOB_PLAYWRIGHT_MODULE=str(root / "conductor/webchat/node_modules/playwright")))
        require(browser.returncode == 0, "Public Jobs/assets: " + browser.stderr[-1000:])
        rows = task_queue.tasks(root)
        stress = [rows[job] for job in replies["task_ids"]]
        for row in stress:
            require(row["status"] not in ("failed", "cancelled"), "Stress job failed: " + row["id"] + " " + str(row.get("error")))
            if row["status"] == "succeeded":
                require(row.get("publication", {}).get("pr_url"), "Completed stress job lacks a draft PR")
        evidence["stress_final"] = [{key: row.get(key) for key in ("id", "title", "worker", "status", "publication")} for row in stress]
        evidence.update(all_pass=True, finished_at=time.time())
        save()
        lines = ["PASS", "SHA: " + sha, "Draft PR: " + args.draft_pr, "Rollback: " + str(rollback),
                 "Tests: full webchat/services discovery + JavaScript; reviews/WEBBOB-REPLIES-TESTS-0927.txt",
                 "Live: exact session messages, four actual executions, existing parity completion, public assets/Jobs.",
                 "Only webchat and job-runner were restarted.", "", "Started project jobs:"]
        lines += [row["project"] + " — " + row["llm"] + " — " + row["job_id"] for row in replies["started_jobs"]]
        for exchange in replies["exchanges"]:
            lines += ["", "User: " + exchange["message"], "Before: " + exchange["before"],
                      "After: " + exchange.get("after_started", exchange["after"])]
        write(root / "conductor/LOOP-REPLIES-PASS-0927.txt", redact("\n".join(lines)) + "\n")
        print("PASS " + sha[:7] + " " + args.draft_pr, flush=True)
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
        write(reviews / "WEBBOB-REPLIES-FAIL-0927.md", "# Web Bob replies — FAIL\n\nCandidate: `" + sha + "`\n\nDraft PR: " +
              args.draft_pr + "\n\nExact failure: " + evidence["failure"] + "\n\nRollback: `" + str(rollback) +
              "`. Restored: " + str(evidence.get("rolled_back", False)) + "\n\nEvidence: WEBBOB-REPLIES-DEPLOYMENT-0927.json.\n")
        print("FAIL " + evidence["failure"] + "; rolled back=" + str(evidence.get("rolled_back", False)), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
