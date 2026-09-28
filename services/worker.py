#!/usr/bin/env python3
"""Execute one explicit job in its private worktree with a persistent blocker."""
from __future__ import annotations

import contextlib
import hashlib
import os
import sys
import re
import json
import time
from pathlib import Path

from command import run
from jobs import blocked, setup_record, external_webjam_lease
from lanes import ask, slot
from state import CONDUCTOR, atomic_write, job_event, jobs, lock
from workspaces import git, prepare
import api_worker
from api_tasks import MODELS as WORKER_MODELS, report_kind


def execute(job):
    record = jobs()[job]
    folder = Path(record["job_dir"])
    if record["state"] == "harvested":
        return 0
    coding = record.get("kind") == "coding"
    try:
        with contextlib.ExitStack() as stack:
            stack.enter_context(lock("worker-" + job, blocking=False))
            if record["engine"] in WORKER_MODELS:
                from dispatch_worker import redact
                from result_acceptance import check_answer, accept
                if coding:
                    raise RuntimeError("API workers cannot edit project files, deploy or resolve conflicts")
                stack.enter_context(slot(record["engine"]))
                job_event(job, "running", model=WORKER_MODELS[record["engine"]], pid=os.getpid(),
                          started_at=time.time(), recovery="API report executing")
                task = (folder / "PROMPT.txt").read_text()
                body, metadata = api_worker.evidence(Path(record["repo"]), record["engine"], task, redact, kind=record.get("kind"))
                purpose = "api-worker-research" if record["engine"] == "gemini" and report_kind(task) == "research" else "api-worker"
                answer = redact(ask(record["engine"], api_worker.report_prompt(task, body, record.get("kind")),
                                    purpose=purpose, locked=True))
                answer = api_worker.render_report(task, answer, record.get("kind"))
                check_answer(task, answer, kind=record.get("kind"))
                acceptance = accept(task, answer, lambda instructions: ask(record["engine"], instructions,
                                      purpose="result-acceptance", locked=True), report_evidence=body, kind=record.get("kind"))
                report = api_worker.save_report(CONDUCTOR, job, str(record.get("attempts", 0)), record["engine"], answer, redact)
                atomic_write(folder / "RESULT.txt", answer + "\n")
                job_event(job, verified=True, report_path=str(report), evidence=metadata,
                          acceptance=json.loads(redact(json.dumps(acceptance))), recovery="API report verified; pending harvest")
                return 0
            stack.enter_context(lock("lane-" + record["engine"], blocking=False))
            stack.enter_context(lock("worktree-" + hashlib.sha256(record["worktree"].encode()).hexdigest(), blocking=False))
            if coding and record["project"] == "WebJam":
                stack.enter_context(lock("webjam-coder", blocking=False))
                from runtime import screen_sessions
                if external_webjam_lease(screen_sessions()):
                    raise BlockingIOError("external WebJam coding lease")
            cwd = setup_record(record)
            job_event(job, "running", recovery="worker executing")
            from result_acceptance import check_answer, deliverable_requirements
            task = (folder / "PROMPT.txt").read_text()
            prompt = task + "\n" + deliverable_requirements(task, record.get("kind"))
            prompt += api_worker.report_serialization(task, record.get("kind"))
            prompt = ("ASSIGNED WORKTREE: " + str(cwd) + "\nBRANCH: " + record["branch"] +
                      "\nThis job specification replaces every legacy shared-worktree instruction in the task. "
                      "Do not switch branches or use other checkout paths. "
                      "Write status notes to STATUS-NOTE.md inside this worktree.\n" +
                      ("Approved draft PR push target: origin HEAD:refs/heads/" + record["publish_branch"] + "\n" if record.get("publish_branch") else "") +
                      "Return an honest final result with tests, SHA and links, or begin BLOCKER: if unfinished.\n\nTASK:\n" + prompt)
            evidence = folder / "EVIDENCE.txt"
            if evidence.exists():
                prompt += "\nSUPPLIED EVIDENCE:\n" + evidence.read_text()
            answer = ask(record["engine"], prompt, cwd=cwd, coding=coding, timeout=5400 if coding else 300,
                         purpose="small-review" if record["engine"] == "claude" else "job-" + job, locked=True)
            answer = api_worker.render_report(task, answer, record.get("kind"))
            atomic_write(folder / (record["engine"] + ".log"), answer + "\n")
            if re.search(r"(?im)^\s*(?:\*\*)?BLOCKER\s*:", answer):
                raise RuntimeError(answer[:1000])
            check_answer(task, answer, kind=record.get("kind"))
            if coding:
                if git(cwd, "status", "--porcelain", "--untracked-files=no"):
                    raise RuntimeError("tracked changes remain uncommitted")
                if git(cwd, "branch", "--show-current") != record["branch"]:
                    raise RuntimeError("worker changed its assigned draft branch")
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
            job_event(job, verified=True, recovery="result verified; pending harvest")
            note = cwd / "STATUS-NOTE.md"
            if note.exists():
                atomic_write(CONDUCTOR / "status" / ("notes-" + record["engine"] + ".md"), note.read_text()[:12000])
            return 0
    except BlockingIOError:
        job_event(job, "queued", attempts=max(0, record.get("attempts", 1) - 1),
                  retry_at=time.time() + 30, recovery="waiting for lane/worktree lease")
        return 0
    except Exception as exc:
        from dispatch_worker import redact
        reason = redact(str(exc)) if isinstance(exc, RuntimeError) else type(exc).__name__
        atomic_write(folder / "BLOCKER.txt", "BLOCKER: " + reason + "\n")
        blocked(jobs()[job], reason)
        return 1


if __name__ == "__main__":
    raise SystemExit(execute(sys.argv[1]))
