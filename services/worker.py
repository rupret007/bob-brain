#!/usr/bin/env python3
"""Execute one explicit job in its private worktree with a persistent blocker."""
from __future__ import annotations

import contextlib
import hashlib
import sys
import re
import json
import os
import threading
import time
from pathlib import Path

from command import run
from jobs import blocked, setup_record, external_webjam_lease
from lanes import ask
from state import CONDUCTOR, atomic_write, job_event, jobs, lock
from workspaces import git, prepare
import queue_store
from scheduler import HEARTBEAT_SECONDS


@contextlib.contextmanager
def heartbeat(record):
    stopped = threading.Event()
    token = record.get("attempt_token")
    def pulse():
        now = time.time()
        job_event(record["job_id"], expected_token=token, heartbeat=now, worker_pid=os.getpid())
        if record.get("queue_id"):
            queue_store.update(record["queue_id"], expected_token=token, heartbeat=now)
    def loop():
        while not stopped.wait(HEARTBEAT_SECONDS):
            pulse()
    pulse()
    thread = threading.Thread(target=loop, daemon=True)
    thread.start()
    try:
        yield
    finally:
        stopped.set()
        thread.join(timeout=5)


def run_tests(record, cwd):
    from lanes import clean_env
    from workspaces import sandbox_command
    commands = record.get("test_commands", [])
    if not commands:
        raise RuntimeError("explicit test_commands are required for build/test jobs")
    receipts = []
    folder = Path(record["job_dir"])
    head = git(cwd, "rev-parse", "HEAD")
    for index, argv in enumerate(commands, 1):
        result = run(sandbox_command(argv, cwd), cwd=str(cwd), env=clean_env(), capture_output=True,
                     text=True, timeout=min(900, max(1, record.get("test_timeout", 300))))
        output = folder / ("test-" + str(index) + ".log")
        atomic_write(output, result.stdout + result.stderr)
        receipts.append(dict(argv=argv, returncode=result.returncode, log=str(output), sha=head))
        atomic_write(folder / "tests.json", json.dumps(receipts, indent=2) + "\n")
        if result.returncode:
            raise RuntimeError("branch test failed; see " + str(output))
    if git(cwd, "rev-parse", "HEAD") != head:
        raise RuntimeError("tests modified the branch")
    clean_worktree(cwd)
    job_event(record["job_id"], tests_passed=True, tests_sha=head, test_receipts=receipts)
    return receipts


def clean_worktree(cwd):
    untracked = [p for p in git(cwd, "ls-files", "--others", "--exclude-standard", "-z").split("\0")
                 if p and p != "STATUS-NOTE.md"]
    if git(cwd, "status", "--porcelain", "--untracked-files=no") or untracked:
        raise RuntimeError("tracked or untracked changes remain uncommitted")


def verify_scope(record, cwd):
    changed = [p for p in git(cwd, "diff", "--name-only", "-z", "--no-renames", record["base_sha"], "HEAD").split("\0") if p]
    outside = [p for p in changed if not queue_store.contains(record.get("scope"), p)]
    if outside:
        raise RuntimeError("changes outside assigned scope: " + ", ".join(outside))
    atomic_write(Path(record["job_dir"]) / "change.diff", git(cwd, "diff", record["base_sha"], "HEAD") + "\n")
    return changed


def execute(job, token=None):
    record = jobs()[job]
    folder = Path(record["job_dir"])
    if record["state"] == "harvested" or (token and record.get("attempt_token") != token):
        return 0
    coding = record.get("kind") == "coding"
    try:
        with contextlib.ExitStack() as stack:
            stack.enter_context(lock("worker-" + job, blocking=False))
            stack.enter_context(lock("lane-" + record["engine"], blocking=False))
            stack.enter_context(lock("worktree-" + hashlib.sha256(record["worktree"].encode()).hexdigest(), blocking=False))
            if coding and record.get("project") == "WebJam":
                from runtime import screen_sessions
                if external_webjam_lease(screen_sessions()):
                    raise BlockingIOError("external WebJam coding lease")
            stack.enter_context(heartbeat(record))
            cwd = setup_record(record)
            job_event(job, "running", recovery="worker executing")
            if record.get("queue_id") and (coding or record.get("role") == "test") and not record.get("test_commands"):
                raise RuntimeError("explicit test_commands required before assigning build/test work")
            prompt = (folder / "PROMPT.txt").read_text()
            prompt = ("ASSIGNED WORKTREE: " + str(cwd) + "\nBRANCH: " + record["branch"] +
                      "\nThis job specification replaces every legacy shared-worktree instruction in the task. "
                      "Do not switch branches or use other checkout paths. "
                      "ASSIGNED FILE/AREA SCOPE: " + json.dumps(record.get("scope", ["."])) + ". "
                      "Write status notes to STATUS-NOTE.md inside this worktree.\n" +
                      ("Approved draft PR push target: origin HEAD:refs/heads/" + record["publish_branch"] + "\n" if record.get("publish_branch") else "") +
                      "Return an honest final result with tests, SHA and links, or begin BLOCKER: if unfinished.\n\nTASK:\n" + prompt)
            evidence = folder / "EVIDENCE.txt"
            if evidence.exists():
                prompt += "\nSUPPLIED EVIDENCE:\n" + evidence.read_text()
            for name in record.get("result_evidence", []):
                path = Path(name)
                prompt += "\nRESULT EVIDENCE " + path.name + ":\n" + path.read_text()[:24000]
            if record.get("role") == "test":
                receipts = run_tests(record, cwd)
                answer = "Local branch tests passed.\n" + json.dumps(receipts, indent=2)
            else:
                answer = ask(record["engine"], prompt, cwd=cwd, coding=coding, timeout=5400 if coding else 300,
                             purpose="small-review" if record["engine"] == "claude" else "job-" + job, locked=True)
            atomic_write(folder / (record["engine"] + ".log"), answer + "\n")
            if re.search(r"(?im)^\s*(?:\*\*)?BLOCKER\s*:", answer):
                raise RuntimeError(answer[:1000])
            if record.get("stage") in ("review", "council"):
                verdicts = re.findall(r"(?im)^VERDICT:\s*(PASS|FAIL)\s*$", answer)
                if len(verdicts) != 1:
                    raise RuntimeError("review/council did not return a single explicit VERDICT: PASS or FAIL")
                # A rejection is a completed assessment, not a transport failure to shop around.
                job_event(job, verdict=verdicts[0])
            if coding:
                clean_worktree(cwd)
                if git(cwd, "branch", "--show-current") != record["branch"]:
                    raise RuntimeError("worker changed its assigned draft branch")
                if record.get("queue_id"):
                    changed = verify_scope(record, cwd)
                    run_tests(record, cwd)
                    job_event(job, head_sha=git(cwd, "rev-parse", "HEAD"), changed_paths=changed)
                target = record.get("publish_branch", record["branch"])
                remote = git(cwd, "ls-remote", "origin", "refs/heads/" + target).split()
                if not remote or remote[0] != git(cwd, "rev-parse", "HEAD"):
                    raise RuntimeError("HEAD is not pushed to the approved draft branch")
                if record.get("publish_new_draft"):
                    pr = json.loads(run(["gh", "pr", "view", target, "-R", record["remote"],
                                         "--json", "isDraft,state,url"], capture_output=True, text=True,
                                        timeout=30, check=True).stdout)
                    if not pr["isDraft"] or pr["state"] != "OPEN":
                        raise RuntimeError("replacement PR is not an open draft")
                    job_event(job, replacement_pr_url=pr["url"])
            atomic_write(folder / "RESULT.txt", answer + "\n")
            job_event(job, verified=True, verified_sha256=hashlib.sha256((folder / "RESULT.txt").read_bytes()).hexdigest(),
                      recovery="result verified; pending harvest")
            note = cwd / "STATUS-NOTE.md"
            if note.exists():
                atomic_write(CONDUCTOR / "status" / ("notes-" + record["engine"] + ".md"), note.read_text()[:12000])
            return 0
    except BlockingIOError:
        attempts = dict(record.get("lane_attempts", {}))
        attempts[record["engine"]] = max(0, attempts.get(record["engine"], 1) - 1)
        job_event(job, "queued", attempts=max(0, record.get("attempts", 1) - 1),
                  lane_attempts=attempts, expected_token=token,
                  retry_at=time.time() + 30, recovery="waiting for lane/worktree lease")
        return 0
    except Exception as exc:
        reason = str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__
        atomic_write(folder / "BLOCKER.txt", "BLOCKER: " + reason + "\n")
        blocked(jobs()[job], reason)
        return 1


if __name__ == "__main__":
    raise SystemExit(execute(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None))
