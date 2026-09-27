"""Server-owned operational statements; model prose cannot acknowledge effects."""
import re

from live_status_snapshot import build_live_status_snapshot

QUEUE_CLAIM = re.compile(
    r"\b(?:i|we)(?:['’]ve| have)?\s+(?:(?:just|already|now)\s+)?(?:queued|scheduled|launched|started|added|submitted)\b"
    r".{0,160}\b(?:job|task|work|council|inbox|queue)\b|"
    r"\b(?:job|task|council|work)\b.{0,120}\b(?:queued|builder inbox|picked up|in progress|still running)\b", re.I | re.S)
STATUS_QUESTION = re.compile(
    r"\b(?:status|resources?|workers? doing|each (?:worker|model)|all (?:workers|models)|"
    r"everything (?:going|running)|how(?:['’]s| is| we)? (?:everything|it going|we doing)|"
    r"who(?:['’]s| is) (?:answering|responding)|(?:gemini|minimax|providers?).{0,45}(?:healthy|failing|errors?|working))\b", re.I)
PROVIDER_CLAIM = re.compile(
    r"\b(?:codex|cursor|gemini|minimax|claude)\b.{0,90}\b(?:handling (?:the|our) chat|answering|cooldown|failing|still.*errors?)\b", re.I)


def operational_reply(root, provider):
    snap = build_live_status_snapshot(root)
    counts = snap["queue_counts"]
    lines = ["Answering provider: " + provider + ". Server status at " + snap["captured_at"] + ".",
             "Chat provider health: " + "; ".join(name + "=" + row["state"] +
                 (" (" + row["reason"] + ")" if row["reason"] else "") for name, row in snap["provider_health"].items()) + ".",
             "Queue: " + str(counts["queued"]) + " queued; " + str(counts["claimed"]) + " claimed/running.",
             "Worker lanes: " + "; ".join(name + "=" + str(row["state"] or "unknown") for name, row in snap["lane_locks"].items()) + "."]
    for state in ("claimed", "queued", "done"):
        for row in snap["queue_jobs"][state][:3]:
            lines.append(("History: " if state == "done" else "") + "`" + row["job_id"] + "` — " + state + " — " + str(row["worker"]))
    if snap["screen_lanes"]:
        lines.append("Screens: " + ", ".join(str(row.get("screen") or row.get("name")) for row in snap["screen_lanes"][:10]))
    lines.append("Health source: provider-health.json + webchat-failover.log. Ready reflects the last successful reply; probes alone do not prove generation health.")
    return "\n\n".join(lines)


def enforce(root, text, answer):
    content = answer["content"]
    if STATUS_QUESTION.search(text) or PROVIDER_CLAIM.search(content):
        content = operational_reply(root, answer["provider"])
    elif QUEUE_CLAIM.search(content):
        content = "No server-confirmed job was created by this reply. Send `start a job: <task>` to create a tracked job."
    return content
