"""Pure recovery wording from the existing status snapshot, never an executor.

Journal projections omit error/result/delivery details. Absence in a projection
is unknown, not proof that no result exists. Recovery strings are matched only
against exact server markers; arbitrary prose is never rendered or interpreted.
Freshness is relative to captured_at so saved observations reproduce verbatim.
"""
import math
import re
from datetime import datetime

from chat_intent import blocked_scopes


MAX_AGE_SECONDS = 24 * 60 * 60
LIVE_LANE_STATES = frozenset(("running", "paused", "claimed", "unverified"))
STAGES = frozenset(("queued", "claimed", "launched", "running", "failed",
                    "blocked", "succeeded", "harvested", "paused",
                    "unverified", "not_observed", "finished"))
RESULT_MARKERS = frozenset(("deliverables persisted", "harvest_complete",
                            "result verified; pending harvest",
                            "API report verified; pending harvest"))
JOURNALS = frozenset(("conductor/jobs.jsonl", "conductor/queue.jsonl",
                     "conductor/state/queue.jsonl"))


def _stamp(value):
    try:
        if isinstance(value, str):
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.timestamp() if parsed.tzinfo is not None else None
        if type(value) in (int, float) and math.isfinite(value):
            return value
    except (ValueError, OverflowError):
        pass
    return None


def _identifier(value):
    return value if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,95}", value) else None


def _result_path(value):
    # Only an already observed, local review artifact. Never open it, accept a
    # URL, or echo arbitrary exception/source text disguised as a path.
    if not isinstance(value, str) or len(value) > 240:
        return None
    if re.fullmatch(r"(?:conductor/)?reviews/[A-Za-z0-9_./-]+\.(?:md|txt|json)", value):
        if all(part not in ("", ".", "..") for part in value.split("/")):
            return value
    return None


def _evidence_age(row, captured_at, available):
    """Age of usable evidence, shared by wording and selection; None if unknown."""
    lane = _identifier(row.get("screen")) if row.get("source") == "lane_collector" else None
    journal = row.get("journal")
    if (available is not True or not (_identifier(row.get("job_id")) or lane)
            or not (lane or isinstance(journal, str) and journal in JOURNALS)):
        return None
    captured = _stamp(captured_at)
    updated = _stamp(row.get("last_activity_at") if lane else row.get("updated_at"))
    # Live lane paths were inspected at capture; historical lanes use the
    # recorded activity timestamp. Never treat an old report as fresh work.
    if lane and row.get("state") in LIVE_LANE_STATES:
        updated = captured
    if captured is not None and updated is not None:
        age = captured - updated
        if 0 <= age <= MAX_AGE_SECONDS:
            return age
    return None


def _qualifies_result_marker(row):
    marker = row.get("recovery")
    stage = row.get("state")
    return (isinstance(marker, str) and marker in RESULT_MARKERS
            and stage in ("running", "harvested", "succeeded")
            and row.get("bucket") != "failed")


def _row_hold_active(state, row):
    holds = (state or {}).get("holds") or {}
    if not holds:
        return False
    project = row.get("project")
    if isinstance(project, str) and project:
        return bool(blocked_scopes(state, [project]))
    if "all" in holds:
        return True
    return False


def _dedupe_keys(row):
    keys = []
    job_id = _identifier(row.get("job_id"))
    if job_id:
        keys.append(("job", job_id))
    if row.get("source") == "lane_collector":
        lane = _identifier(row.get("screen"))
        if lane:
            keys.append(("lane", lane))
    return keys


def format_recovery_message(row, *, captured_at, available=True, hold_active=False):
    """Describe one projected journal/lane row and exactly one read-only step.

    Missing fields never imply failure, delivery, a result, or permission. A
    failed journal stage does not distinguish provider failure from acceptance
    failure, so the wording attributes failure to the record, not its cause.
    """
    row = row if isinstance(row, dict) else {}
    job_id = _identifier(row.get("job_id"))
    lane = _identifier(row.get("screen")) if row.get("source") == "lane_collector" else None
    identity = f"Job `{job_id}`" if job_id else f"Lane `{lane}` (job ID unknown)" if lane else "Job ID unknown"
    stage = row.get("state")
    stage = stage if isinstance(stage, str) and stage in STAGES else "unknown"
    journal = row.get("journal")
    source = journal if isinstance(journal, str) and journal in JOURNALS else "lane_collector" if lane else None
    prefix = f"{identity}; recorded stage: {stage}"
    prefix += f" (source: {source}). " if source else ". "
    fresh = _evidence_age(row, captured_at, available) is not None
    path = _result_path(row.get("result_path")) if lane else None
    marker = row.get("recovery")
    recorded_result = _qualifies_result_marker(row)
    next_step = "Inspect status for this job." if job_id else "Inspect status."
    if not fresh:
        explanation = "Current outcome is unknown; evidence is missing, stale, or unavailable."
    elif stage == "queued" and marker == "waiting for lane/worktree lease":
        explanation = "Deferred while waiting for lane/worktree capacity. Start time is unknown."
    elif stage == "queued":
        explanation = "Waiting in the queue; the reason and start time are unknown."
    elif path or recorded_result:
        explanation = "A saved result is recorded; completeness and chat delivery are unconfirmed."
        if path:
            next_step = f"Open the saved result `{path}`."
        else:
            next_step = "Inspect status for this job to locate the saved result."
    elif stage == "failed" or row.get("bucket") == "failed":
        explanation = "Failure is recorded; no result evidence is included in this snapshot. Whether a result exists is unknown."
    elif stage == "blocked":
        explanation = "A block is recorded; the cause and result are unknown."
    else:
        explanation = "The outcome and chat delivery are unknown."
    if hold_active is True or stage == "paused":
        explanation += " The saved hold remains in place." if hold_active is True else " The observed pause remains recorded."
        next_step = "Inspect status for this job." if job_id else "Inspect status."
    return prefix + explanation + " Next step: " + next_step


def recovery_messages(snapshot):
    """Bounded recovery notes using only fields already collected for status."""
    queue = snapshot.get("queue_jobs") or {}
    inspection = snapshot.get("inspection") or {}
    rows = [row for bucket in ("failed", "queued", "done", "claimed")
            for row in queue.get(bucket, []) if isinstance(row, dict)
            and (row.get("state") in ("failed", "blocked")
                 or row.get("bucket") == "failed" and row.get("state") == "harvested"
                 or row.get("state") == "queued" and row.get("recovery") == "waiting for lane/worktree lease"
                 or _qualifies_result_marker(row))]
    bob = snapshot.get("bob_lanes") or {}
    rows += [row for key in ("live", "finished_recent") for row in bob.get(key, [])
             if isinstance(row, dict) and row.get("source") == "lane_collector"
             and _result_path(row.get("result_path"))]

    def priority(row):
        age = _evidence_age(row, snapshot.get("captured_at"),
                            inspection.get("queue_available") if row.get("journal") else True)
        return (age is None, age if age is not None else 0)

    # Rank across buckets and lanes before deduplication and the note limit.
    # Freshest evidence wins; stable ties retain the existing snapshot order.
    rows.sort(key=priority)
    hold_state = snapshot.get("recovery_hold_state")
    legacy_hold = snapshot.get("recovery_hold_active") is True
    notes, seen = [], set()
    for row in rows:
        keys = _dedupe_keys(row)
        if keys and any(key in seen for key in keys):
            continue
        for key in keys:
            seen.add(key)
        hold_active = (_row_hold_active(hold_state, row) if hold_state is not None
                       else legacy_hold)
        notes.append(format_recovery_message(
            row, captured_at=snapshot.get("captured_at"),
            available=inspection.get("queue_available") if row.get("journal") else True,
            hold_active=hold_active))
        if len(notes) == 3:
            break
    return notes
