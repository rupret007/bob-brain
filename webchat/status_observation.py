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
