"""Server-owned operational statements; model prose cannot acknowledge effects."""
import re

from live_status_snapshot import build_live_status_snapshot
from chat_intent import PROJECT, blocked_scopes, hold_reply, projects, state_for
from worker_activity import WORKER_NAMES, task_label

QUEUE_CLAIM = re.compile(
    r"\b(?:i|we)(?:['’]ve| have)?\s+(?:(?:just|already|now)\s+)?(?:queued|scheduled|launched|started|created|dispatched|added|submitted|assigned|delegated|asked|kicked off)\b"
    r".{0,160}\b(?:job|task|work|review|fix|council|inbox|queue|it|this|that|codex|claude|cursor|gemini|minimax)\b|"
    r"^\s*(?:queued|scheduled|launched|started|submitted|assigned)\b|"
    r"\b(?:job|task|council|work)\b.{0,120}\b(?:created|queued|scheduled|launched|started|assigned|builder inbox|picked up|in progress|running)\b"
    r"(?!\s+(?:when|if|until)\b)|"
    r"\b(?:codex|claude|cursor|gemini|minimax)(?:['’]s|\s+(?:is|has started))\s+(?:working|running|reviewing|fixing|on it)\b|"
    r"\b(?:codex|claude|cursor|gemini|minimax)\s+has\s+(?:your|the|this)\s+(?:job|task|work|review)\b", re.I)
NO_JOB_NOTICE = re.compile(
    r"\bno (?:server[- ]confirmed )?(?:jobs?|tasks?)\s+(?:(?:was|were|has been|are)\s+)?(?:created|queued|started|running)\b|"
    r"\b(?:nothing|no work) (?:was |is |has been )?(?:queued|started|running)\b|"
    r"\bstart a job\s*:", re.I)
STATUS_QUESTION = re.compile(
    r"\b(?:status|resources?|workers? doing|each (?:worker|model)|all (?:workers|models)|"
    r"everything (?:going|running)|how(?:['’]s| is| we)? (?:everything|it going|we doing)|"
    r"(?:is|are) (?:it|anything|everything|things|the (?:work|jobs?|workers?)) "
    r"(?:going(?: now)?|moving(?: along)?|running|making progress)|(?:any|making) progress|"
    r"what(?:['’]s| is| are) (?:running|moving|happening)|(?:job|task|screen|process) (?:ids?|names?)|"
    r"(?:service|disk|storage) status|diagnostics?|"
    r"who(?:['’]s| is) (?:answering|responding)|(?:gemini|minimax|providers?).{0,45}(?:healthy|failing|errors?|working))\b", re.I)
PROVIDER_CLAIM = re.compile(
    r"\b(?:codex|cursor|gemini|minimax|claude)\b.{0,90}\b(?:handling (?:the|our) chat|answering|cooldown|failing|still.*errors?)\b", re.I)
HOLD_CLAIM = re.compile(
    r"\b(?:your|the|earlier|previous)\s+(?:(?:earlier|previous|existing|current)\s+)?hold\b|"
    r"\b(?:on hold|still (?:paused|held)|remain(?:s)? (?:paused|held))\b|"
    r"\b(?:" + PROJECT.pattern + r"|work|coding|jobs?|tasks?)\s+(?:is|are|has been|have been)\s+(?:paused|held)\b|"
    r"\b(?:awaiting|pending)\s+(?:your\s+)?(?:permission|approval|go[- ]ahead)\b|"
    r"\b(?:until you (?:say (?:go|resume)|resume|give (?:the )?go[- ]ahead)|waiting for (?:your|permission)|"
    r"(?:need|require) (?:your |fresh |renewed |explicit )*(?:permission|approval|go[- ]ahead))\b", re.I)
HOLD_QUESTION = re.compile(r"^(?:(?:are|is|am|do|does|why)\b[^.!]*\b(?:on hold|holds? (?:still )?active|paused|need.{0,20}permission)\b[^.!]*|what holds? are active)\??$", re.I)


DETAILS = re.compile(r"\b(?:raw|diagnostic(?:s)?|internal (?:ids?|details)|(?:job|task|screen|process) (?:ids?|names?)|pids?)\b", re.I)
HIDE_DETAILS = re.compile(r"\b(?:no|without|hide|omit|skip|don['’]t show|do not show|leave out)\b.{0,45}"
                          r"\b(?:raw|internal|ids?|names?|pids?|diagnostics?)\b", re.I)
IDENTITY = re.compile(r"\bwho(?:['’]s| is) (?:answering|responding)\b", re.I)
HEALTH = re.compile(r"\b(?:health|healthy|failing|errors?|providers?|resources?)\b", re.I)


def _duration(seconds):
    if seconds is None:
        return "elapsed time unavailable"
    seconds = max(0, int(seconds))
    if seconds < 60:
        return "less than a minute"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} hr" + (f" {minutes} min" if minutes else "")


def format_operational_reply(snap, provider="server", text=""):
    """A conversational view of evidence; raw identifiers are opt-in."""
    counts = snap["queue_counts"]
    work = snap["work"]
    running = snap["work_counts"]["running"]
    inspection = snap["inspection"]
    detailed = bool(DETAILS.search(text) and not HIDE_DETAILS.search(text))
    if running:
        lines = [f"Yes — {running} worker{'s are' if running != 1 else ' is'} running."]
    elif snap["work_counts"]["paused"]:
        lines = ["The worker processes are paused."]
    elif work:
        lines = ["There is work listed, but I can't confirm a live worker is running."]
    elif not all(inspection.values()):
        lines = ["I couldn't check all the live workers, so I can't confirm whether work is running."]
    elif any(row["state"] == "busy" for row in snap["lane_locks"].values()):
        lines = ["The saved lane status reports busy workers, but their current work isn't identified."]
    else:
        lines = ["I don't see active work on the mini right now."]
    items = []
    for row in work:
        label = row["title"]
        if row.get("worker") in WORKER_NAMES:
            label += " — " + WORKER_NAMES[row["worker"]]
        if row.get("model"):
            label += " (" + row["model"] + ")"
        duration = _duration(row.get("elapsed_seconds"))
        if row["state"] == "running":
            detail = "running for " + duration if row.get("elapsed_seconds") is not None else "running; " + duration
        elif row["state"] == "paused":
            detail = "paused; process age " + duration
        elif row["state"] == "claimed":
            detail = "tracked as running; live activity unconfirmed"
            if row.get("elapsed_seconds") is not None:
                detail += "; claimed " + duration + " ago"
        else:
            detail = "session open; worker activity unconfirmed"
        if detailed:
            identifiers = [str(row[key]) for key in ("screen", "pid", "job_id") if row.get(key)]
            if identifiers:
                detail += " (" + ", ".join(identifiers) + ")"
        items.append("- " + label + " — " + detail + ".")
    if items:
        lines.append("\n".join(items))
    if counts["queued"]:
        lines.append(f"{counts['queued']} " + ("more " if work else "") +
                     f"job{'s are' if counts['queued'] != 1 else ' is'} waiting in the queue.")
    elif running:
        lines.append("Nothing else is waiting in the queue.")
    else:
        lines.append("No jobs are waiting in the queue.")
    if running and not all(inspection.values()):
        lines.append("Some live worker checks were unavailable; this list may be incomplete.")
    if IDENTITY.search(text):
        lines.append((WORKER_NAMES[provider] + " answered this message." if provider in WORKER_NAMES
                      else "This status comes directly from the live checks."))
    if detailed or HEALTH.search(text):
        labels = {"ready": "last reply succeeded", "unchecked": "no recent reply verified",
                  "cooldown": "temporarily unavailable", "recovery_due": "needs a retry"}
        lines.append("Chat health: " + "; ".join(WORKER_NAMES[name] + " — " + labels[row["state"]]
                     for name, row in snap["provider_health"].items()) + ".")
    if detailed:
        services = [row["screen"] for row in snap["screen_lanes"] if row["role"] == "service"]
        if services:
            lines.append("Service sessions: " + ", ".join(services) + ".")
    if re.search(r"\b(?:services?|resources?)\b", text, re.I):
        healthy = sum(row["healthy"] for row in snap["service_health"].values())
        lines.append(f"{healthy} of {len(snap['service_health'])} monitored services are healthy.")
    if re.search(r"\b(?:disk|storage|resources?)\b", text, re.I) and snap["disk"].get("available"):
        lines.append(f"Disk space: {snap['disk']['avail_gb']} GB free.")
    if detailed or re.search(r"\b(?:history|finished|completed|done)\b", text, re.I):
        for state in ("queued", "done", "failed"):
            rows = snap["queue_jobs"][state][:3]
            if rows:
                entries = [row["job_id"] if detailed else task_label(row) for row in rows]
                lines.append({"queued": "Waiting", "done": "Recently finished", "failed": "Recently failed"}[state]
                             + ": " + ", ".join(entries) + ".")
    return "\n\n".join(lines)


def operational_reply(root, provider, text=""):
    return format_operational_reply(build_live_status_snapshot(root), provider, text)


def enforce(root, text, answer, conversation=None):
    content = answer["content"]
    state = state_for(conversation if conversation is not None else {})
    scopes = blocked_scopes(state, projects(text))
    if HOLD_QUESTION.match(text.strip()):
        return hold_reply(scopes) if scopes else "Ready when you are."
    from task_dispatch import CHAT_STYLE, PREAMBLE
    # A style preference calls for a simple acknowledgement, never a status
    # report from operational snapshots included in the model context.
    if CHAT_STYLE.match(PREAMBLE.sub("", text.strip())):
        return "Got it."
    if STATUS_QUESTION.search(text):
        content = operational_reply(root, answer["provider"], text)
    else:
        # Keep the useful answer; remove unsupported effects and boilerplate
        # without adding a system notice to ordinary chat.
        # Keep original whitespace so removing a footer doesn't flatten the
        # useful answer's paragraphs, lists, or code formatting.
        sentences = re.split(r"(?<=[.!?])(?=\s)|(?<=\n)", content)
        kept = [part for part in sentences if not QUEUE_CLAIM.search(part)
                and not NO_JOB_NOTICE.search(part) and not PROVIDER_CLAIM.search(part)]
        if len(kept) != len(sentences):
            content = "".join(kept).strip() or "What would you like me to work on?"
    sentences = re.split(r"(?<=[.!?])(?=\s)|(?<=\n)", content)
    kept = [part for part in sentences if not HOLD_CLAIM.search(part)]
    if len(kept) != len(sentences):
        content = "".join(kept).strip()
        # Only the saved state may explain an operational hold.
        if scopes:
            content = (content + "\n\n" if content else "") + hold_reply(scopes)
        elif not content:
            content = "Ready when you are."
    return content
