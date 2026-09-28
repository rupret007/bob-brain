"""Server-owned operational statements; model prose cannot acknowledge effects."""
import re

from live_status_snapshot import build_live_status_snapshot
from chat_intent import PROJECT, blocked_scopes, hold_reply, projects, state_for
from worker_activity import WORKER_NAMES, task_label
from worker_evidence import clean

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
    r"(?:what(?:['’]s| is) (?:working on what|going on)|each llm)|"
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


def _cooldown(snap, name):
    # Provider identity is the join key; reset text never floats between LLMs.
    lane = snap["lane_locks"].get(name, {})
    health = snap.get("provider_health", {}).get(name, {})
    if lane.get("cached_state", lane.get("state")) != "cooldown" and health.get("state") != "cooldown":
        return ""
    detail = lane.get("detail") or health.get("reason") or ""
    reset = re.search(r"resets?\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)(?:\s*\(([^)]+)\))?", detail, re.I)
    if reset:
        zone = " CT" if reset[4] in ("America/Chicago", "CT", "CDT", "CST") else " " + reset[4] if reset[4] else ""
        return "; resets " + reset[1] + ":" + (reset[2] or "00") + " " + reset[3].upper() + zone
    return "; cooling down"


def _work_line(row, detailed=False):
    project = row.get("project")
    repo = row.get("repo")
    label = project + (" (" + repo + ")" if repo else "") + ": " if project else (repo + ": " if repo else "")
    label += row.get("task") or row["title"]
    if detailed and not row.get("task") and "task" in row:
        label += " — " + (row.get("screen") or "process " + str(row.get("pid")))
        label += "; " + row["log_path"] + "; last: " + row["last_log_line"]
    if row.get("model"):
        label += " (" + row["model"] + ")"
    duration = _duration(row.get("elapsed_seconds"))
    state = {"running": "running for ", "paused": "paused; process age ",
             "claimed": "claimed; execution unconfirmed; age ",
             "unverified": "session open; worker activity unconfirmed; age "}[row["state"]]
    label += " — " + state + duration
    if detailed:
        ids = [str(row[key]) for key in ("screen", "pid", "job_id") if row.get(key)]
        if ids:
            label += " (" + ", ".join(ids) + ")"
        if row.get("prompt_path"):
            label += "; prompt " + row["prompt_path"]
        if row.get("log_path") and row.get("task"):
            label += "; " + row["log_path"] + "; last: " + row["last_log_line"]
    return label


def _join(items):
    return ", ".join(items[:-1]) + " and " + items[-1] if len(items) > 1 else items[0]


def _task_name(row):
    label = row.get("task") or row.get("title") or task_label(screen=row.get("screen"))
    label = clean(label, 95).strip(" .;:") or "a CLI session"
    project = row.get("project")
    if project and project.lower() not in label.lower():
        label = project + ": " + label
    elif project:
        label = re.sub(re.escape(project), lambda _: project, label, flags=re.I)
    return label


def _casual_status(snap):
    """Use full sentences; keep diagnostics and missing metadata out of task names."""
    work, inspection = snap["work"], snap["inspection"]
    active, idle, extra = [], [], []
    for name in WORKER_NAMES:
        rows = [row for row in work if row.get("worker") == name]
        if name == "mini" and not rows:
            continue
        display = WORKER_NAMES[name]
        if rows:
            tasks = []
            for row in rows:
                model = row.get("model") or "model not reported"
                duration = _duration(row.get("elapsed_seconds"))
                state = {"running": "running for ", "paused": "paused; process age ",
                         "claimed": "claimed, execution unconfirmed; age ",
                         "unverified": "open, worker unconfirmed; age "}[row["state"]]
                tasks.append("“" + _task_name(row) + "” (" + model + "; " + state + duration + ")")
            active.append(display + " is on " + _join(tasks) + _cooldown(snap, name))
        elif snap.get("lane_locks", {}).get(name, {}).get("state") == "busy":
            extra.append(display + "'s last lane check was busy, but its task isn't recorded")
        elif _cooldown(snap, name):
            extra.append(display + " has no confirmed active work" + _cooldown(snap, name))
        else:
            idle.append(display)
    sentences = []
    if active:
        # At most two sentences for actual workers, even when all five are busy.
        middle = (len(active) + 1) // 2
        sentences.append("; ".join(active[:middle]) + ".")
        if active[middle:]:
            sentences.append("; ".join(active[middle:]) + ".")
    elif work:
        sentences.append("Work sessions are open, but I can't confirm a running worker.")
    elif not all(inspection.values()):
        sentences.append("I can't confirm all workers because a live check failed.")
    elif snap["screen_lanes"]:
        sentences.append("There are live service sessions, but no task worker is confirmed.")
    else:
        sentences.append("I don't see active work on the mini right now.")
    other = [row for row in work if row.get("worker") not in WORKER_NAMES]
    if other:
        extra.append(_join([_task_name(row) for row in other]) +
                     (" has" if len(other) == 1 else " have") + " an open session with no confirmed worker")
    # A cached lock or a failed inspection cannot establish that a worker is idle.
    if idle:
        extra.append(_join(idle) + (" has" if len(idle) == 1 else " have") + " no confirmed active work")
    if not all(inspection.values()) and active:
        extra.append("a live check failed, so this list may be incomplete")
    if extra:
        sentences.append("; ".join(extra) + ".")
    counts = snap["queue_counts"]
    if inspection.get("queue_available", True):
        sentences.append(f"The job runner has {counts['claimed']} claimed and {counts['queued']} queued jobs.")
    else:
        sentences.append("I couldn't read the job queue.")
    return " ".join(sentences)


def format_operational_reply(snap, provider="server", text=""):
    """Live worker facts in casual sentences; diagnostics are opt-in."""
    counts, work, inspection = snap["queue_counts"], snap["work"], snap["inspection"]
    running = snap["work_counts"]["running"]
    detailed = bool(DETAILS.search(text) and not HIDE_DETAILS.search(text))
    if not detailed:
        answer = _casual_status(snap)
        if IDENTITY.search(text):
            answer += (" " + WORKER_NAMES[provider] + " answered this message." if provider in WORKER_NAMES
                       else " This answer comes from live checks.")
        if re.search(r"\b(?:disk|storage)\b", text, re.I) and snap["disk"].get("available"):
            answer += f" Disk space: {snap['disk']['avail_gb']} GB free."
        return answer
    if running:
        first = f"{running} worker{'s are' if running != 1 else ' is'} running."
    elif work:
        first = "Work is listed; I can't confirm a running worker."
    elif not all(inspection.values()):
        first = "I can't confirm all workers; a live check failed."
    elif snap["screen_lanes"]:
        first = "There are live service sessions; no task worker is confirmed."
    else:
        first = "I don't see active work on the mini right now."
    lines = [first]
    for name in ("codex", "claude", "cursor", "gemini", "minimax"):
        rows = [row for row in work if row.get("worker") == name]
        current = " | ".join(_work_line(row, detailed) for row in rows)
        if not current:
            current = "idle" if all(inspection.values()) else "activity unconfirmed"
        lines.append(WORKER_NAMES[name] + ": " + current + _cooldown(snap, name) + ".")
    other = [row for row in work if row.get("worker") not in ("codex", "claude", "cursor", "gemini", "minimax")]
    if other:
        lines.append("Other sessions: " + " | ".join(_work_line(row, detailed) for row in other) + ".")
    queue_line = f"Job runner: {counts['claimed']} claimed, {counts['queued']} queued."
    if running and not all(inspection.values()):
        queue_line += " Some live checks failed; this list may be incomplete."
    lines.append(queue_line)
    if IDENTITY.search(text):
        lines.append(WORKER_NAMES[provider] + " answered this message." if provider in WORKER_NAMES else "This answer comes from live checks.")
    if detailed or re.search(r"\b(?:health|healthy|services?|diagnostics?|logs?)\b", text, re.I):
        services = [row["screen"] for row in snap["screen_lanes"] if row["role"] == "service"]
        if services:
            lines.append("Service sessions: " + ", ".join(services) + ".")
        if detailed:
            lines.extend(row["path"] + ": " + " / ".join(row["lines"]) for row in snap.get("recent_logs", []) if row["lines"])
    if re.search(r"\b(?:disk|storage)\b", text, re.I) and snap["disk"].get("available"):
        lines.append(f"Disk space: {snap['disk']['avail_gb']} GB free.")
    return "\n".join(lines)


CRITICISM = re.compile(r"^(?:this|that|it|your (?:answer|reply|response|update)) (?:needs? to be (?:way |much )?better|"
                       r"(?:is|was|isn['’]t) (?:bad|wrong|not good|good enough|helpful))|"
                       r"^(?:do better|be more specific|try again|fix your (?:answer|reply))\b", re.I)


def correcting_status(text, conversation):
    if not CRITICISM.search(text.strip()):
        return False
    previous = [m["content"] for m in (conversation or {}).get("messages", []) if m["role"] == "user"]
    if previous and previous[-1] == text:
        previous.pop()
    previous = [ask for ask in previous if not CRITICISM.search(ask)]
    return bool(previous and STATUS_QUESTION.search(previous[-1]))


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
    if STATUS_QUESTION.search(text) or correcting_status(text, conversation):
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
