# Strict LIVE MiniMax RE-REVIEW draft/webbob-integrate-2057 @ab50533
full: ab5053331d128372607194a0756b893d3872c7a0

SCOPE: status_observation / apiworkers / lane awareness ONLY.
Prior MiniMax FAIL claimed undefined `payload`, undefined `snap`, missing `redact_snapshot`. Those were based on truncated hunks. Below is the COMPLETE status_observation.py — triage those claims as TRUE bugs or FALSE POSITIVES against this full source.
Gemini LIVE @ ab50533 = PASS. Offline: 319 webchat + 129 services + 56 evals READY (INTEGRATE-FIXED-2143.md).
Do NOT fail for voice/media/texting. List only REAL CRITICAL/HIGH that exist in the full source.
End with exactly: VERDICT: PASS or VERDICT: FAIL

## COMPLETE webchat/status_observation.py
```python
"""Evidence saved atomically with each operational reply, never supplied by a model."""
import hashlib
import json
import math
from datetime import datetime


def snapshot_digest(snapshot):
    payload = json.dumps(snapshot, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def redact_snapshot(value, redact):
    """Redact values before rendering and hashing without changing JSON structure."""
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, list):
        return [redact_snapshot(item, redact) for item in value]
    if isinstance(value, dict):
        return {key: redact_snapshot(item, redact) for key, item in value.items()}
    return value


def bind_observation(observation, conversation):
    message = conversation["messages"][-1]
    return dict(observation, conversation_id=conversation["id"], request_id=message["request_id"],
                message_id=message["id"])


def observation_errors(answer, question, conversation_id, started, finished):
    """Fail closed on absent/stale evidence or prose that differs from its sample.

    Independent before/after samples remain diagnostics, not alternate values a
    reply may choose between. Worker and queue assertions use the saved sample.
    """
    from reply_authority import format_operational_reply
    from worker_activity import WORKER_NAMES

    observation = answer.get("status_observation")
    if not isinstance(observation, dict):
        return ["status reply has no saved observation"]
    errors = []
    try:
        if observation["schema_version"] != 1:
            errors.append("unsupported status observation version")
        if (observation["conversation_id"] != conversation_id or
                observation["request_id"] != answer["request_id"] or
                observation["message_id"] != answer["id"] or observation["question"] != question):
            errors.append("status observation belongs to another reply")
        snap = observation["snapshot"]
        if observation["snapshot_sha256"] != snapshot_digest(snap):
            errors.append("status observation digest mismatch")
        first, last = observation["observed_from"], observation["observed_until"]
        captured = datetime.fromisoformat(snap["captured_at"])
        if (captured.tzinfo is None or not all(math.isfinite(t) for t in (first, last, started, finished)) or
                not started <= answer["created_at"] <= first <= last <= finished or
                abs(captured.timestamp() - first) > 0.000001):
            errors.append("status observation is outside its reply interval")
        if observation["renderer_provider"] not in ("server", answer.get("provider")):
            errors.append("status observation renderer does not match reply")
        if answer["content"] != format_operational_reply(snap, observation["renderer_provider"], question):
            errors.append("status reply differs from its saved observation")
        work, inspection = snap["work"], snap["inspection"]
        states = ("running", "paused", "claimed", "unverified")
        if snap["work_counts"] != {state: sum(row["state"] == state for row in work) for state in states}:
            errors.append("status observation worker counts disagree with its rows")
        if any(type(inspection[key]) is not bool for key in
               ("screens_available", "processes_available", "queue_available")):
            errors.append("status observation has invalid inspection evidence")
        for row in work:
            if row["state"] not in states:
                errors.append("status observation has an invalid worker state")
            if row["state"] in ("running", "paused") and (
                    not inspection["processes_available"] or row.get("source") != "process" or
                    type(row.get("pid")) is not int or row["pid"] <= 0 or
                    row.get("worker") not in WORKER_NAMES or row.get("assignment_recorded") is False):
                errors.append("status observation claims execution without a confirmed worker")
        for bucket in ("queued", "claimed", "done", "failed"):
            rows, count = snap["queue_jobs"][bucket], snap["queue_counts"][bucket]
            if type(count) is not int or count < len(rows) or (bucket in ("queued", "claimed") and count != len(rows)):
                errors.append("status observation queue counts disagree with its rows")
            if any(row["bucket"] != bucket for row in rows):
                errors.append("status observation queue row is in the wrong state")
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
        errors.append("malformed status observation")
    return errors
```

## reply_authority imports / observation build (grep)
315:    from status_observation import redact_snapshot, snapshot_digest
317:    snap = redact_snapshot(build_live_status_snapshot(root, now=started), redact)
323:                           snapshot=snap, snapshot_sha256=snapshot_digest(snap))

## Relevant reply_authority excerpt around observation creation
315:    from status_observation import redact_snapshot, snapshot_digest
316-    started = time.time()
317:    snap = redact_snapshot(build_live_status_snapshot(root, now=started), redact)
318-    finished = time.time()
319-    content = format_operational_reply(snap, provider, text)
320-    if observation is not None:
321-        observation.update(schema_version=1, observed_from=started, observed_until=finished,
322-                           question=text, renderer_provider=provider,
323:                           snapshot=snap, snapshot_sha256=snapshot_digest(snap))
324-    return content
325-
326-
327-def enforce(root, text, answer, conversation=None, *, observation=None, redact=lambda value: value):
328-    content = answer["content"]
329-    from worker_assignment import requested_workers
330-    if requested_workers(text, conversation):
331-        # Model prose is never an assignment receipt, even if it sounds ready.
332-        return "I haven't assigned a worker from this reply. No new job was queued."
333-    state = state_for(conversation if conversation is not None else {})
334-    scopes = blocked_scopes(state, projects(text))
335-    if HOLD_QUESTION.match(text.strip()):
336-        return hold_reply(scopes) if scopes else "Ready when you are."
337-    from task_dispatch import CHAT_STYLE, PREAMBLE
338-    # A style preference calls for a simple acknowledgement, never a status
339-    # report from operational snapshots included in the model context.
340-    if CHAT_STYLE.match(PREAMBLE.sub("", text.strip())):
341-        return "Got it."
342-    if STATUS_QUESTION.search(text) or correcting_status(text, conversation):
343-        return operational_reply(root, answer["provider"], text, observation=observation, redact=redact)
344-    else:
345-        from dispatch_receipts import claims_dispatch, NO_DISPATCH
346-        sentences = re.split(r"(?<=[.!?])(?=\s)|(?<=\n)", content)
347-        content = "".join(part for part in sentences if not NO_JOB_NOTICE.search(part)).strip() or NO_DISPATCH
348-        if claims_dispatch(content) or QUEUE_CLAIM.search(content):

## FIXED-2143 head
# INTEGRATE-FIXED-2143 — READY (offline code repair)

Recorded: 2026-09-28T02:57:30+00:00.

- Tip SHA: `ab5053331d128372607194a0756b893d3872c7a0`.
- Branch: `draft/webbob-integrate-2057`.
- Regular push to `brain`: verified remote tip matches the SHA above.
- Draft PR: https://github.com/rupret007/bob-brain/pull/17 — OPEN, still draft, matching head SHA; description updated.
- Worktree: `/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-integrate-2057` — clean, with upstream set to `brain/draft/webbob-integrate-2057`.
- Result: **READY** for review of the code repair. **Not LIVE PASS.**

## Repair

Each status/worker reply now persists a versioned `status_observation` containing
the exact redacted snapshot used for rendering, observation start/end times,
a microsecond UTC capture timestamp, a SHA-256 digest, rendering inputs and
conversation/request/message IDs. Reply and observation use the existing
private, fsynced atomic conversation write and authenticated history response.
Retries and restart preserve both; legacy messages are not given invented
observations. Status corrections and provider fallback replies also capture
and bind their own evidence, and model metadata cannot forge it.

Worker rows and lane details share one worker/journal sample, including failed
inspections. Active queue assignments are fully preserved. The integration gate
validates identity, time bounds, digest, exact rendered text, counts, task/model
coverage and confirmed process evidence against that saved observation. It
retains timestamped before/after diagnostics and the reply observation, then
checks that history still contains the same message and observation after work
finishes. Receipt ownership and actual worker execution/completion checks remain
strict.

Attempt 1's bounded lane prompt handling and honest unattributed CLI reporting,
and attempt 2's concise completion summaries with authenticated full-report
links, are already implemented and remain covered by passing regressions.

## Validation

| Check | Result |
| --- | --- |
| Full webchat suite | 319 passed, 0 failed |
| Full services suite | 129 passed, 0 failed |
| Offline eval suite | 56/56 passed |
| JavaScript quiet-hours checks | Passed |
| JavaScript result renderer/dialog checks | Passed |
| JavaScript syntax | Passed |
| Python compilation | Passed |
| Git whitespace check | Passed |

New regressions exercise running counts **1 before / 3 in the saved reply
observation / 5 after**, queued→claimed→running transitions, reused PIDs,

## Prior MiniMax FAIL dispositions to reconsider
1. payload undefined in snapshot_digest — check full file above
2. snap undefined in observation_errors — check full file above
3. redact_snapshot missing — check full file above
4. null observation crash — check isinstance guard
