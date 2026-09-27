#!/usr/bin/env python3
"""Worker execution journal, durable blockers, and legacy queue migration."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import shlex
import sys
import time
import uuid
from pathlib import Path

from command import run
from state import CONDUCTOR, ROOT, alert, atomic_write, job_event, jobs, lock, log, read_json, write_json
import lanes
from workspaces import git, prepare

PROJECTS = ("WebJam", "StoryBoard", "AdoptIQ", "shelf")
MAX_ATTEMPTS = 3


def load_helper(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), ROOT / "bin" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def closeout(job_dir):
    for name in ("RESULT.txt", "RESULT.md"):
        path = Path(job_dir) / name
        if path.is_file() and path.stat().st_size:
            return path
    return None


def blocked(record, reason):
    attempt = record.get("attempts", 0)
    job_event(record["job_id"], "blocked", outcome="blocked", recovery=reason,
              retry_at=time.time() + min(3600, 60 * 2 ** attempt),
              escalated=attempt >= record.get("max_attempts", MAX_ATTEMPTS))
    if attempt >= record.get("max_attempts", MAX_ATTEMPTS) or record.get("legacy"):
        alert("job-" + record["job_id"], record["job_id"] + " blocked: " + reason)


def import_legacy(refill=None, screens=None):
    """Recover already misclassified BLOCKERs even after the old import marker."""
    records = jobs()
    for record in records.values():
        if record.get("outcome") == "blocked" and record["state"] == "harvested":
            blocked(record, "legacy BLOCKER retained; explicit retry or escalation required")
    if (CONDUCTOR / "jobs-imported-v2.json").exists():
        return
    old = read_json(ROOT / "local-cursor-job-watch-state.json", {}).get("jobs", {})
    for job, record in old.items():
        if job in records or not record.get("running"):
            continue
        folder = ROOT / job
        job_event(job, "blocked", legacy=True, job_dir=str(folder), outcome="blocked",
                  recovery="orphaned legacy running record", escalated=True)
        folder.mkdir(parents=True, exist_ok=True)
        atomic_write(folder / "ORPHAN_WARNING.txt", "No durable active worker was found; job retained as blocked.\n")
    write_json(CONDUCTOR / "jobs-imported-v2.json", {"at": time.time()})


def update_index(record, status):
    if not record.get("file"):
        return
    index = ROOT / "next-prompts/INDEX.md"
    if not index.exists():
        return
    lines = index.read_text().splitlines()
    for i, line in enumerate(lines):
        parts = line.split("|")
        if len(parts) >= 8 and parts[2].strip().strip("`") == record["file"]:
            parts[5] = " " + status + " "
            parts[6] = " " + record["job_id"] + "; " + record.get("recovery", "managed by services") + " "
            lines[i] = "|".join(parts)
    atomic_write(index, "\n".join(lines) + "\n")


def harvest(record, result):
    digest = hashlib.sha256(result.read_bytes()).hexdigest()
    # Persist deliverables/promotions before terminal journal state.
    atomic_write(ROOT / "next-prompts/_inbox" / (record["job_id"] + "-" + result.name), result.read_text())
    if (Path(record["job_dir"]) / "queue-ready").exists() or (Path(record["job_dir"]) / "PROMOTE.json").exists():
        helper = load_helper("auto_harvest")
        helper.promote_from_queue_ready(Path(record["job_dir"]), record["job_id"])
    update_index(record, "DONE")
    job_event(record["job_id"], "harvested", outcome="result", result_path=str(result),
              result_sha256=digest, recovery="deliverables persisted")
    alert("job-" + record["job_id"])


def recover(refill=None):
    from runtime import screen_sessions
    sessions = screen_sessions()
    import_legacy()
    unresolved = []
    for record in jobs().values():
        folder = Path(record.get("job_dir", ROOT / record["job_id"]))
        result = closeout(folder)
        live = record["job_id"] in sessions
        if record.get("queue_id") and record["state"] in ("launched", "running"):
            from scheduler import recover_worker
            if recover_worker(record, live):
                continue
        if live:
            if record["state"] in ("queued", "launched"):
                job_event(record["job_id"], "running", recovery="live worker adopted after restart")
            continue  # do not harvest files an active writer may still be changing
        if result:
            if record.get("queue_id") and record.get("verified") and hashlib.sha256(result.read_bytes()).hexdigest() != record.get("verified_sha256"):
                job_event(record["job_id"], "blocked", invalidate_result=True, verified=False,
                          outcome="blocked", recovery="result changed after worker verification", retry_at=time.time() + 300)
                continue
            if record.get("managed") and re.search(r"(?im)^\s*(?:\*\*)?BLOCKER\s*:", result.read_text()):
                if record["state"] != "blocked" or record.get("verified"):
                    job_event(record["job_id"], "blocked", invalidate_result=True, verified=False,
                              outcome="blocked", recovery="final response is a BLOCKER; completion invalidated",
                              retry_at=time.time() + 300)
                update_index(record, "BLOCKED")
                unresolved.append(record["job_id"])
                continue
            digest = hashlib.sha256(result.read_bytes()).hexdigest()
            if record["state"] != "harvested" or record.get("result_sha256") != digest:
                # Managed jobs must pass worker verification before RESULT is terminal.
                if not record.get("managed") or record.get("verified"):
                    harvest(record, result)
                    continue
        if record["state"] == "harvested":
            continue
        if record["state"] in ("running", "launched"):
            blocked(record, "worker exited without a verified result")
        elif (folder / "BLOCKER.txt").exists() and record["state"] != "blocked":
            blocked(record, "BLOCKER.txt requires retry")
        if record.get("legacy") and record["state"] != "blocked":
            blocked(record, "legacy job needs a private worktree specification")
        if record.get("legacy") and record.get("file"):
            # Requeue its prompt through the new scheduler; never replay old run.sh.
            update_index(record, "READY")
        unresolved.append(record["job_id"])
    alert("jobs", str(len(unresolved)) + " unfinished/blocked jobs retained in jobs.jsonl" if unresolved else None)
    return unresolved


def queue_specs():
    configured = read_json(CONDUCTOR / "services/backlog.json", [])
    index = ROOT / "next-prompts/INDEX.md"
    rows = []
    if index.exists():
        for line in index.read_text().splitlines():
            parts = [p.strip().strip("`") for p in line.split("|")]
            if len(parts) < 8 or not parts[1].isdigit() or parts[5] != "READY":
                continue
            project = next((p for p in PROJECTS if parts[3].lower().startswith(p.lower())), parts[3])
            # Dedicated per-PR jobs supersede the old shared-worktree CI prompt.
            if parts[2] == "20-webjam-ci-fix-choice-helper.md":
                continue
            prompt = ROOT / "next-prompts" / parts[2]
            if not prompt.is_file():
                continue
            sidecar = read_json(prompt.with_suffix(".json"), {})
            rows.append(dict(id="queue-" + prompt.stem, file=parts[2], project=project,
                             kind="non-coding" if "non-coding" in parts[4] else "coding",
                             priority=int(parts[1]) + 20, prompt=prompt.read_text(), **sidecar))
    # Unknown legacy work is retained for escalation, not silently relaunched.
    return sorted(configured + rows, key=lambda r: (PROJECTS.index(r["project"]) if r["project"] in PROJECTS else len(PROJECTS), r.get("priority", 99), r["id"]))


def evidence(spec, repo):
    sections = []
    for field, root in (("evidence", repo), ("conductor_evidence", CONDUCTOR)):
        for name in spec.get(field, []):
            path = (root / name).resolve()
            if root.resolve() not in path.parents or path.name == "keys.env":
                raise RuntimeError("evidence path outside approved root")
            if path.is_file():
                sections.append("FILE " + name + "\n" + path.read_text(errors="replace")[:20000])
            else:
                sections.append("FILE " + name + ": missing; do not infer contents")
    return "\n\n".join(sections)[:80000]


def create_record(spec, lane):
    projects = read_json(CONDUCTOR / "services/projects.json", {})
    project = projects.get(spec.get("project"), {})
    job_id = lane + "-" + spec["id"][:48] + "-" + uuid.uuid4().hex[:8]
    folder = ROOT / "jobs" / job_id
    folder.mkdir(parents=True)
    repo = str(Path(spec.get("repo") or project.get("repo") or CONDUCTOR).expanduser().resolve())
    record = dict(spec, job_id=job_id, spec_id=spec["id"], job_dir=str(folder), repo=repo,
                  remote=spec.get("remote", project.get("remote")), engine=lane, worktree=str(ROOT / "workspaces" / job_id),
                  branch="draft/" + job_id, managed=True, attempts=0, legacy=False)
    atomic_write(folder / "PROMPT.txt", spec["prompt"])
    atomic_write(folder / "run.sh", "#!/bin/bash\nexec " + shlex.quote(sys.executable) + " " +
                 shlex.quote(str(CONDUCTOR / "bootstrap.py")) + " worker " + shlex.quote(job_id) +
                 ' "${1:-}" < /dev/null\n')
    (folder / "run.sh").chmod(0o755)
    return job_event(job_id, "queued", **{k: v for k, v in record.items() if k != "job_id"})


def setup_record(record):
    if record.get("pr"):
        pr = json.loads(run(["gh", "pr", "view", str(record["pr"]), "-R", record["remote"],
                             "--json", "isDraft,state,headRefName,headRefOid,url"],
                            capture_output=True, text=True, timeout=30, check=True).stdout)
        if not pr["isDraft"] or pr["state"] != "OPEN":
            raise RuntimeError("target PR is not an open draft")
        record.update(fetch_ref=pr["headRefName"], publish_branch=record["branch"] if record.get("publish_new_draft") else pr["headRefName"], pr_url=pr["url"])
        job_event(record["job_id"], **{k: record[k] for k in ("fetch_ref", "publish_branch", "pr_url")})
    workspace = prepare(record)
    if record.get("queue_id") and not record.get("base_sha"):
        record["base_sha"] = git(workspace, "rev-parse", "HEAD")
        job_event(record["job_id"], base_sha=record["base_sha"])
    body = evidence(record, workspace)
    if body:
        atomic_write(Path(record["job_dir"]) / "EVIDENCE.txt", body)
    return workspace


def launch_record(record):
    folder = Path(record["job_dir"])
    attempt = record.get("attempts", 0) + 1
    lane_attempts = dict(record.get("lane_attempts", {}))
    lane_attempts[record["engine"]] = lane_attempts.get(record["engine"], 0) + 1
    token = uuid.uuid4().hex
    job_event(record["job_id"], "launched", attempts=attempt, lane_attempts=lane_attempts,
              attempt_token=token, started_at=time.time(), heartbeat=time.time(), worker_pid=None,
              verified=False, recovery="launch intent")
    if record.get("queue_id"):
        import queue_store
        queue_store.update(record["queue_id"], status="running", execution_id=record["job_id"],
                           owner=record["engine"], heartbeat=time.time(), started_at=time.time(),
                           attempt_token=token, attempts=attempt)
    try:
        for name in ("BLOCKER.txt", "RESULT.txt", "RESULT.md"):
            path = folder / name
            if path.exists():
                path.rename(folder / (name + ".attempt-" + str(attempt - 1)))
        launch(record["job_id"], folder)
    except Exception as exc:
        reason = str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__
        atomic_write(folder / "BLOCKER.txt", "BLOCKER: " + reason + "\n")
        blocked(jobs()[record["job_id"]], reason)


def launch(job_name, job_dir):
    record = jobs()[job_name]
    run(["screen", "-dmS", job_name, "/bin/bash", str(job_dir / "run.sh"), record.get("attempt_token", "")],
        capture_output=True, text=True, timeout=15, check=True, detach=True)
    # The child can finish or block before screen returns. Never overwrite it.
    if jobs()[job_name]["state"] == "launched":
        job_event(job_name, "running", expected_token=record.get("attempt_token"),
                  expected_states=("launched",), recovery="worker launched")
    update_index(jobs()[job_name], "RUNNING")


def can_assign(spec, lane, active, health):
    if health.get(lane, {}).get("state") != "ready" or any(r.get("engine") == lane for r in active):
        return False
    if lane == "mini" and spec.get("role") != "test":
        return False
    if spec.get("role") == "test" and lane != "mini":
        return False
    if spec["kind"] == "coding" and lane not in ("cursor", "codex"):
        return False
    if lane == "claude" and (spec["kind"] == "coding" or not (spec.get("small_review") or spec.get("role") in ("review", "critique", "council"))):
        return False
    if spec["kind"] == "coding":
        from queue_store import overlaps
        from scheduler import repo_key
        if any(r.get("kind") == "coding" and repo_key(r) == repo_key(spec) and
               overlaps(spec.get("scope"), r.get("scope")) for r in active):
            return False
    return len(active) < len(lanes.SCHEDULER_LANES)


def external_webjam_lease(sessions):
    """Honor the separately requested local test build without taking its worktree."""
    notice = CONDUCTOR / "reviews/WEBJAM-TEST-BUILD-SCHEDULER.md"
    if "svc-webjam-test" in sessions:
        return True
    return notice.exists() and bool(re.search(r"(?m)^Status:\s*ACTIVE\b", notice.read_text()))


def tick():
    from scheduler import tick as schedule
    return schedule()
