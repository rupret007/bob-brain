#!/usr/bin/env python3
"""Queue recovery and launch hooks. The existing queue remains the scheduler."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import time
from pathlib import Path

from state import CONDUCTOR, ROOT, alert, atomic_write, job_event, jobs, lock, log, read_json, write_json


def load_helper(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), ROOT / "bin" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def closeout(job_dir):
    for name in ("RESULT.txt", "RESULT.md", "BLOCKER.txt"):
        path = job_dir / name
        if path.is_file() and path.stat().st_size:
            return path
    return None


def import_legacy(refill, screens):
    if (CONDUCTOR / "jobs-imported.json").exists():
        return
    known = jobs()
    legacy = read_json(ROOT / "local-cursor-job-watch-state.json", {})
    running_rows = {r["job"]: r for r in refill.parse_running_rows() if r.get("job")}
    candidates = set(legacy.get("jobs", {})) | set(running_rows)
    for path in ROOT.iterdir():
        if path.is_dir() and re.match(r"^(codex|cursor|claude|webjam|storyboard|adoptiq|shelf)-", path.name):
            if closeout(path) or (path / "run.sh").is_file():
                candidates.add(path.name)
    for job in sorted(candidates):
        if job in known:
            continue
        folder = ROOT / job
        result = closeout(folder)
        active = job in running_rows or refill.screen_alive(job, screens)
        old = legacy.get("jobs", {}).get(job, {})
        if not result and not active and not old.get("running"):
            continue
        row = running_rows.get(job, {})
        job_event(job, "running" if active else "launched", job_dir=str(folder),
                  legacy=True, pri=row.get("pri"), file=row.get("file"), recovery="imported")
        if not result and not active:
            # Stale historical metadata is not authority to relaunch a cancelled job.
            # Preserve an explicit closeout and let the queue decide follow-on work.
            folder.mkdir(parents=True, exist_ok=True)
            atomic_write(folder / "BLOCKER.txt", "BLOCKER: legacy running record has no live screen, current RUNNING row, or closeout.\n"
                         "Recovered by service migration; retained for review, not silently treated as completed work.\n")
    write_json(CONDUCTOR / "jobs-imported.json", {"at": time.time(), "candidates": len(candidates)})


def launch(job_name, job_dir):
    """Called only after the intent is fsynced. No zombie interactive shell."""
    result = subprocess.run(["screen", "-dmS", job_name, "/bin/bash", str(job_dir / "run.sh")],
                            capture_output=True, text=True, timeout=15)
    if result.returncode:
        job_event(job_name, recovery="launch_failed", launch_error=result.returncode)
        raise RuntimeError("screen launch failed rc=" + str(result.returncode))
    job_event(job_name, "running", recovery="screen_started")


def recover(refill):
    screens = refill.screen_ls()
    if "screen_error:" in screens or ("Sockets in" not in screens and "No Sockets found" not in screens):
        raise RuntimeError("cannot inspect screens; refusing duplicate job launches")
    import_legacy(refill, screens)
    # Also adopt a job created immediately before a crash at the journal boundary.
    known = jobs()
    for row in refill.parse_running_rows():
        job = row.get("job")
        if job and job not in known:
            job_event(job, "running", job_dir=str(ROOT / job), pri=row["pri"], file=row["file"], legacy=True)
    unresolved = []
    for job, record in jobs().items():
        folder = Path(record.get("job_dir", ROOT / job))
        result = closeout(folder)
        # Re-harvest changed results, including RESULT arriving after a BLOCKER.
        digest = hashlib.sha256(result.read_bytes()).hexdigest() if result else None
        if record["state"] == "harvested" and digest == record.get("result_sha256"):
            continue
        if folder.is_dir():
            refill.copy_tmp_closeout(job, folder)
            result = closeout(folder)
        if result:
            for action in refill.harvest_on_reap(job):
                log(action)
            current = jobs()[job]
            expected = hashlib.sha256(result.read_bytes()).hexdigest()
            if current["state"] != "harvested" or current.get("result_sha256") != expected:
                unresolved.append(job + ": harvest pending")
            continue
        if record["state"] == "harvested":
            unresolved.append(job + ": harvested source missing (journal retained)")
            continue
        if refill.screen_alive(job, screens):
            job_event(job, "running", recovery="live")
            continue
        if record.get("legacy"):
            # Do not replay old shell scripts that may reset worktrees. Resume via
            # the common worker with the existing prompt and an explicit resume contract.
            if (folder / "PROMPT.txt").exists():
                atomic_write(folder / "resume.sh", '#!/bin/bash\nexec python3 ' +
                             __import__("shlex").quote(str(CONDUCTOR / "services" / "worker.py")) +
                             ' ' + __import__("shlex").quote(job) + ' --resume\n')
            else:
                unresolved.append(job + ": prompt missing")
                job_event(job, recovery="prompt_missing")
                continue
        if record.get("resume_count", 0) >= 3:
            unresolved.append(job + ": three job resume attempts exhausted")
            job_event(job, recovery="resume_limit")
            continue
        # Reuse the existing coding lease guard, never bypass another coder.
        if "webjam" in job.lower() and refill.job_dir_looks_coding(folder):
            if refill.webjam_coding_screens_alive(screens):
                job_event(job, recovery="waiting_for_coding_lease")
                continue
            reason = refill.webjam_coding_lease_blocked(ci_unblock="ci" in job.lower())
            if reason:
                job_event(job, recovery="lease_blocked", recovery_detail=reason)
                unresolved.append(job + ": coding lease blocked")
                continue
        script = folder / ("resume.sh" if record.get("legacy") else "run.sh")
        if not script.exists() and not record.get("legacy") and record.get("prompt_path"):
            source = Path(record["prompt_path"])
            if source.is_file():
                refill.write_job(job, source, record.get("kind", "non-coding"))
        if not script.exists():
            unresolved.append(job + ": launch script missing")
            job_event(job, recovery="script_missing")
            continue
        job_event(job, resume_count=record.get("resume_count", 0) + 1, recovery="resuming")
        result = subprocess.run(["screen", "-dmS", job, "/bin/bash", str(script)], capture_output=True, timeout=15)
        if result.returncode:
            unresolved.append(job + ": resume screen failed")
        else:
            job_event(job, "running", recovery="resumed")
        screens = refill.screen_ls()
    alert("jobs", (str(len(unresolved)) + " job recovery issues; see conductor/jobs.jsonl: " + "; ".join(unresolved[:3])) if unresolved else None)
    return unresolved


def tick():
    with lock("queue", blocking=False):
        refill = load_helper("ops-queue-refill")
        recover(refill)
        # Existing reaping logic preserves BLOCKED vs DONE and the coding lease.
        result = subprocess.run([sys.executable, str(ROOT / "bin/job-watch-tick.py")], cwd=str(ROOT), timeout=300)
        recover(refill)
        if result.returncode not in (0, 2):
            raise RuntimeError("queue tick failed rc=" + str(result.returncode))
        log("tick complete rc=%s (2 means queue safely held)" % result.returncode)
        return result.returncode
