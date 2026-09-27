"""Server-owned operational statements; model prose cannot acknowledge effects."""
import re

from live_status_snapshot import build_live_status_snapshot

QUEUE_CLAIM = re.compile(
    r"\b(?:i|we)(?:['’]ve| have)?\s+(?:(?:just|already|now)\s+)?(?:queued|scheduled|launched|started|added|submitted|assigned|delegated|created|dispatched)\b"
    r".{0,160}\b(?:job|task|work|review|fix|council|inbox|queue|it|this|that|codex|claude|cursor|gemini|minimax)\b|"
    r"\b(?:i|we)(?:['’]ve| have)?\s+(?:asked|told|sent|handed)\b.{0,120}\b(?:codex|claude|cursor|gemini|minimax|inbox)\b|"
    r"^\s*(?:queued|scheduled|launched|started|submitted|assigned)\b|"
    r"\b(?:the|your|our|this|that|my)\s+(?:job|task|council|work)\b.{0,120}\b(?:created|queued|scheduled|started|launched|builder inbox|picked up|in progress|running)\b|"
    r"\b(?:job|task)\s+(?:webchat-[a-f0-9]+|[a-f0-9]{6,})\b.{0,60}\b(?:created|queued|started|running)\b|"
    r"\b(?:codex|claude|cursor|gemini|minimax)(?:['’]s|\s+(?:is|has started))\s+(?:working|running|reviewing|fixing|on it)\b|"
    r"\b(?:codex|claude|cursor|gemini|minimax)\s+has\s+(?:your|the|this)\s+(?:job|task|work|review)\b", re.I)
NO_JOB_NOTICE = re.compile(
    r"\bno (?:server[- ]confirmed )?(?:jobs?|tasks?)\s+(?:(?:was|were|has been|are)\s+)?(?:created|queued|started|running)\b|"
    r"\b(?:nothing|no work) (?:was |is |has been )?(?:queued|started|running)\b|"
    r"\b(?:send|say|use)\s+[`\"']?start a job\s*:", re.I)
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
    from task_dispatch import CHAT_STYLE, PREAMBLE
    # A style preference calls for a simple acknowledgement, never a status
    # report from operational snapshots included in the model context.
    if CHAT_STYLE.match(PREAMBLE.sub("", text.strip())):
        return "Got it."
    if STATUS_QUESTION.search(text):
        content = operational_reply(root, answer["provider"])
    else:
        # Keep the useful answer; remove unsupported effects and boilerplate
        # without adding a system notice to ordinary chat.
        sentences = re.split(r"(?<=[.!?])(?=\s)|(?<=\n)", content)
        kept = [part for part in sentences if not any(pattern.search(part) for pattern in (QUEUE_CLAIM, NO_JOB_NOTICE, PROVIDER_CLAIM))]
        if len(kept) != len(sentences):
            content = "".join(kept).strip() or "What would you like me to work on?"
    return content
