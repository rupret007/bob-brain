#!/usr/bin/env python3
"""Assign durable requests to lanes and gate draft promotion on recorded evidence."""
from __future__ import annotations

import json
import os
import signal
import time
from pathlib import Path

import jobs as execution
import lanes
import queue_store as queue
import state
from command import run
from workspaces import git

HEARTBEAT_SECONDS = 15
STALE_SECONDS = 90
LAUNCH_GRACE = 30
ROLE_LANES = {
    "build": ("cursor", "codex"),
    "review": ("claude", "codex", "cursor"),
    "research": ("gemini", "minimax", "codex", "cursor"),
    "critique": ("minimax", "gemini", "claude", "codex"),
    "test": ("mini",),
    "council": ("gemini", "minimax", "codex", "cursor"),
}


def repo_key(spec):
    repo = spec.get("repo")
    if not repo:
        return spec.get("project", "unknown")
    try:
        return git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
    except Exception:
        return str(Path(repo).expanduser().resolve())


def lease_held(name):
    try:
        with state.lock(name, blocking=False):
            return False
    except BlockingIOError:
        return True


def stop_stale_worker(record, live):
    """Only signal the recorded worker after checking its command and job identity."""
    pid = record.get("worker_pid")
    if lease_held("worker-" + record["job_id"]):
        if not pid:
            return False
        command = run(["ps", "-o", "command=", "-p", str(pid)], capture_output=True,
                      text=True, timeout=5).stdout
        if "worker.py" not in command or record["job_id"] not in command or record.get("attempt_token", "") not in command:
            return False
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        for _ in range(20):
            if not lease_held("worker-" + record["job_id"]):
                break
            time.sleep(.1)
        if lease_held("worker-" + record["job_id"]):
            return False
    if live:
        result = run(["screen", "-S", record["job_id"], "-X", "quit"], capture_output=True, timeout=5)
        if result.returncode:
            return False
    return True


def recover_worker(record, live):
    age = time.time() - (record.get("heartbeat") or record.get("started_at") or 0)
    held = lease_held("worker-" + record["job_id"])
    if age <= STALE_SECONDS and (live or held):
        return True
    if not record.get("verified") and age < LAUNCH_GRACE:
        return True
    if live or held:
        if not stop_stale_worker(record, live):
            state.alert("stale-" + record["job_id"], "Stale worker identity/exit unverified; lane remains reserved: " + record["job_id"])
            return True
        execution.blocked(record, "worker heartbeat expired; verified worker stopped")
        state.alert("stale-" + record["job_id"])
        return True
    return False


def lane_order(request, record=None, requests=None):
    """One retry on the assigned provider, then advance; never cycle back."""
    order = list(ROLE_LANES[request["role"]])
    preferred = request.get("preferred_lane")
    if preferred in order:
        order.remove(preferred)
        order.insert(0, preferred)
    record = record or {}
    attempts = record.get("lane_attempts", {})
    engine = record.get("engine")
    if engine in order and attempts.get(engine, 0):
        index = order.index(engine)
        order = order[index:] if attempts[engine] < 2 else order[index + 1:]
    if request.get("stage") == "council":
        other_owners = {r.get("owner") for r in (requests or {}).values()
                        if r.get("source_id") == request.get("source_id") and
                        r.get("stage") == "council" and r["id"] != request["id"] and
                        r.get("status") in ("running", "completed")}
        order = [lane for lane in order if lane not in other_owners]
    return order


def import_requests():
    projects = state.read_json(state.CONDUCTOR / "services/projects.json", {})
    records = state.jobs()
    known = {r.get("spec_id"): r for r in records.values()}
    pending = queue.snapshot()
    specs = execution.queue_specs()
    configured = {s["id"] for s in specs}
    # Existing queued/blocked jobs may no longer have a READY row. Retain them too.
    # Leave already-running legacy workers on their original closeout protocol.
    for record in records.values():
        identifier = record.get("spec_id", record["job_id"])
        if record.get("managed") and not record.get("queue_id") and record["state"] in ("queued", "blocked") and identifier not in configured:
            specs.append(dict(record, id=identifier))
            known[identifier] = record
            configured.add(identifier)
    for spec in specs:
        if spec["id"] in pending:
            continue
        old = known.get(spec["id"])
        if old and old["state"] == "harvested":
            continue  # importing configuration must never replay completed legacy jobs
        project = projects.get(spec.get("project"), {})
        request = queue.enqueue(dict(spec, repo=spec.get("repo") or project.get("repo") or str(state.CONDUCTOR),
                                     role=spec.get("role") or ("build" if spec.get("kind") == "coding" else
                                                              "review" if spec.get("small_review") else "research")))
        if old:
            state.job_event(old["job_id"], queue_id=request["id"], role=request["role"], scope=request["scope"],
                            max_attempts=2 * len(ROLE_LANES[request["role"]]),
                            lane_attempts=old.get("lane_attempts", {old["engine"]: old.get("attempts", 0)}))
            queue.update(request["id"], execution_id=old["job_id"])


def execution_for(request, records):
    return records.get(request.get("execution_id")) or next(
        (r for r in records.values() if r.get("queue_id") == request["id"]), None)


def promotion_child(source, suffix, role, goal, *, lane=None, evidence=None):
    spec = {"id": queue.child_id(source["id"], suffix), "source_id": source["id"],
            "stage": role, "role": role, "goal": goal, "repo": source["repo"],
            "priority": source["priority"], "scope": source["scope"],
            "result_evidence": evidence or [source["result_path"]]}
    if source.get("head_sha"):
        spec["base_ref"] = source["head_sha"]
    if lane:
        spec["preferred_lane"] = lane
    return queue.enqueue(spec)["id"]


def conflict_checks(request, record, requests, records):
    if request["role"] != "build":
        return []
    if not record.get("tests_passed") or record.get("tests_sha") != record.get("head_sha"):
        raise RuntimeError("branch lacks passing tests for its exact result SHA")
    if git(record["worktree"], "rev-parse", "HEAD") != record["head_sha"]:
        raise RuntimeError("branch changed after tests")
    siblings = [r for r in requests.values() if request.get("parent_id") and
                r.get("parent_id") == request["parent_id"] and r["id"] != request["id"] and
                r["role"] == "build" and repo_key(r) == repo_key(request)]
    checks = []
    for sibling in siblings:
        other = execution_for(sibling, records)
        if not other or other["state"] != "harvested":
            return None
        if not other.get("tests_passed") or other.get("tests_sha") != other.get("head_sha"):
            raise RuntimeError("sibling lacks passing branch tests: " + sibling["id"])
        if git(other["worktree"], "rev-parse", "HEAD") != other["head_sha"]:
            raise RuntimeError("sibling branch changed after tests: " + sibling["id"])
        # Computes a merge tree in the object DB only; changes no branch/index/worktree.
        result = run(["git", "-C", request["repo"], "merge-tree", "--write-tree",
                      record["head_sha"], other["head_sha"]], capture_output=True, text=True, timeout=60)
        check = {"sibling": sibling["id"], "head": record["head_sha"], "other_head": other["head_sha"],
                 "returncode": result.returncode, "output": result.stdout + result.stderr}
        checks.append(check)
        state.atomic_write(Path(record["job_dir"]) / ("conflict-" + sibling["id"] + ".json"), json.dumps(check, indent=2) + "\n")
        if result.returncode:
            raise RuntimeError("sibling draft conflict: " + sibling["id"])
    return checks


def reconcile():
    records = state.jobs()
    for request in queue.snapshot().values():
        if request["status"] in ("completed", "jeff-draft", "cancelled", "split"):
            continue
        record = execution_for(request, records)
        if not record:
            continue
        fields = dict(execution_id=record["job_id"], owner=record["engine"],
                      heartbeat=record.get("heartbeat"), started_at=record.get("started_at"),
                      attempts=record.get("attempts", 0), retry_at=record.get("retry_at", 0),
                      reason=record.get("recovery", ""))
        if record["state"] in ("launched", "running"):
            queue.update(request["id"], status="running", **fields)
        elif record["state"] == "blocked":
            available = lane_order(request, record)
            queue.update(request["id"], status="retry" if available else "blocked", **fields)
        elif record["state"] == "queued":
            queue.update(request["id"], status="queued", **fields)
        elif record["state"] == "harvested" and record.get("verified"):
            fields.update(result_path=record["result_path"], result_sha256=record["result_sha256"],
                          head_sha=record.get("head_sha"), verdict=record.get("verdict"))
            queue.update(request["id"], **fields)
            if request["stage"] != "work":
                if record.get("verdict") == "PASS":
                    queue.update(request["id"], status="completed")
                else:
                    queue.update(request["id"], status="blocked", decision_rejected=True,
                                 reason="review/council rejected result; revision required")
                continue
            if request["status"] in ("review", "council"):
                continue
            try:
                checks = conflict_checks(request, record, queue.snapshot(), records)
                if checks is None:
                    queue.update(request["id"], status="waiting-siblings", reason="waiting for sibling branch tests")
                    continue
                request = queue.snapshot()[request["id"]]
                review = promotion_child(request, "review", "review",
                    "Review the completed result and its test/conflict receipts. Cite defects or missing evidence. "
                    "End with VERDICT: PASS only if ready for council, otherwise VERDICT: FAIL.",
                    evidence=[record["result_path"], *([str(Path(record["job_dir"]) / name) for name in ("tests.json", "change.diff")] if request["role"] == "build" else []),
                              *(str(p) for p in sorted(Path(record["job_dir"]).glob("conflict-*.json")))])
                queue.update(request["id"], status="review", review_id=review, conflict_checks=checks,
                             promotion_blocked=False, reason="verified result queued for review")
            except Exception as exc:
                queue.update(request["id"], status="blocked", promotion_blocked=True, reason=str(exc))

    requests = queue.snapshot()
    for request in requests.values():
        if request["status"] == "review":
            review = requests.get(request.get("review_id"), {})
            if review.get("status") != "completed":
                if review.get("status") == "blocked":
                    queue.update(request["id"], reason="review blocked: " + review.get("reason", "revision required"))
                continue
            members = [promotion_child(request, "council-" + lane, "council",
                "Independently assess this result and the review. Cite missing proof or conflicts. "
                "End with VERDICT: PASS only if ready for Jeff's draft review, otherwise VERDICT: FAIL.",
                lane=lane, evidence=list(dict.fromkeys([request["result_path"], review["result_path"],
                                                       *review.get("result_evidence", [])]))) for lane in ("gemini", "minimax")]
            queue.update(request["id"], status="council", council_ids=members, reason="review passed; council queued")
        elif request["status"] == "council":
            members = [requests.get(i, {}) for i in request.get("council_ids", [])]
            if any(m.get("status") == "blocked" for m in members):
                queue.update(request["id"], reason="council blocked; see independent assessment receipts")
            if len(members) == 2 and all(m.get("status") == "completed" and m.get("verdict") == "PASS" for m in members) and len({m["owner"] for m in members}) == 2:
                # Recheck branch evidence after reviewers finish, before the final gate.
                try:
                    checks = conflict_checks(request, execution_for(request, records), requests, records)
                    if checks is not None:
                        queue.update(request["id"], status="jeff-draft", promoted_at=time.time(),
                                     conflict_checks=checks, reason="review + two independent council PASS receipts; remains draft")
                except Exception as exc:
                    queue.update(request["id"], status="blocked", promotion_blocked=True, reason=str(exc))
        elif request["status"] == "split":
            children = [requests.get(i, {}) for i in request.get("children", [])]
            if children and all(c.get("status") == "jeff-draft" for c in children):
                queue.update(request["id"], status="jeff-draft", promoted_at=time.time(), reason="all parts passed promotion")


def paused():
    return any(p.exists() for p in (state.CONDUCTOR / "MAINTENANCE", state.CONDUCTOR / "STOP-WEBBOB", state.ROOT / "STOP-WEBBOB"))


def tick(request_ids=None):
    from runtime import screen_sessions
    with state.lock("queue", blocking=False):
        if paused():
            state.log("scheduler paused by MAINTENANCE/STOP-WEBBOB")
            return 0
        health = lanes.refresh()
        execution.recover()
        if request_ids is None:
            import_requests()
        for request in queue.snapshot().values():
            if request.get("parts") and request["status"] in ("queued", "split"):
                queue.split(request["id"])
        reconcile()
        sessions = screen_sessions()
        records = state.jobs()
        active = [r for r in records.values() if r["state"] in ("launched", "running") or
                  (r["job_id"] in sessions and r["state"] != "harvested") or lease_held("worker-" + r["job_id"])]
        external = execution.external_webjam_lease(sessions)
        requests = queue.snapshot()
        candidates = sorted((r for r in requests.values() if r["status"] in ("queued", "retry") and
                             (request_ids is None or r["id"] in request_ids) and
                             r.get("retry_at", 0) <= time.time() and not r.get("parts")),
                            key=lambda r: (r["priority"], r["created_at"], r["id"]))
        for request in candidates:
            if paused():
                break
            if any(requests.get(dep, {}).get("status") not in ("completed", "jeff-draft") for dep in request.get("depends_on", [])):
                queue.update(request["id"], reason="waiting for dependencies")
                continue
            if external and request.get("project") == "WebJam" and request["role"] == "build":
                queue.update(request["id"], reason="external WebJam work has no declared scope; waiting")
                continue
            record = execution_for(request, records)
            order = lane_order(request, record, requests)
            if not order:
                queue.update(request["id"], status="blocked", reason="retry and fallback lanes exhausted")
                continue
            chosen = next((lane for lane in order if execution.can_assign(request, lane, active, health)), None)
            # A busy first provider retains its promised retry. Unavailable providers can fall back.
            if record and record.get("lane_attempts", {}).get(record["engine"], 0) == 1 and record["engine"] in order:
                if health.get(record["engine"], {}).get("state") in ("ready", "busy"):
                    chosen = record["engine"] if execution.can_assign(request, record["engine"], active, health) else None
            if chosen is None:
                queue.update(request["id"], reason="waiting for eligible lane or non-overlapping repo scope")
                continue
            if not record:
                record = execution.create_record(dict(request, queue_id=request["id"],
                    max_attempts=2 * len(ROLE_LANES[request["role"]])), chosen)
            if record["engine"] != chosen:
                record = state.job_event(record["job_id"], engine=chosen, recovery="fallback to " + chosen)
            queue.update(request["id"], execution_id=record["job_id"])
            execution.launch_record(record)
            current = state.jobs()[record["job_id"]]
            records[current["job_id"]] = current
            if current["state"] in ("launched", "running"):
                active.append(current)
            # Even a very fast child holds the lane for this tick's inventory.
            health[chosen]["state"] = "busy"
            requests = queue.snapshot()
        reconcile()
        state.log("scheduler: %d reserved workers across %d lanes" % (len(active), len(lanes.SCHEDULER_LANES)))
        return 0


def lane_board():
    requests = queue.snapshot()
    records = list(state.jobs().values())
    health = state.read_json(state.CONDUCTOR / "lanes.json", {})
    board = []
    for lane in lanes.SCHEDULER_LANES:
        owned = [r for r in records if r.get("engine") == lane]
        owned.sort(key=lambda r: (r["state"] in ("running", "launched"), r.get("started_at", 0)), reverse=True)
        record = owned[0] if owned else {}
        request = requests.get(record.get("queue_id"), {})
        board.append(dict(lane=lane, state=record.get("state", health.get(lane, {}).get("state", "idle")),
                          job=request.get("id", record.get("job_id", "—")), started=record.get("started_at"),
                          heartbeat=record.get("heartbeat"), result=request.get("status", record.get("recovery", "—")),
                          result_path=record.get("result_path"), reason=request.get("reason", "")))
    return board
