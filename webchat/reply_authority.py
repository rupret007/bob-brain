"""Server-owned operational statements; model prose cannot acknowledge effects."""
import re
import time

from live_status_snapshot import build_live_status_snapshot
from chat_intent import PROJECT, blocked_scopes, hold_reply, projects, state_for
from worker_activity import WORKER_NAMES, task_label
from worker_evidence import clean

DIRECT_QUEUE_CLAIM = re.compile(
    r"\b(?:i|we)(?:['’]ve| have)?\s+(?:(?:just|already|now)\s+)?(?:queued|scheduled|launched|started|created|dispatched|added|submitted|assigned|delegated|asked|kicked off)\b"
    r".{0,160}\b(?:job|task|work|review|fix|council|inbox|queue|it|this|that|codex|claude|cursor|gemini|minimax)\b|"
    r"^\s*(?:queued|scheduled|launched|started|submitted|assigned)\b|"
    r"\b(?:codex|claude|cursor|gemini|minimax)(?:['’]s|\s+(?:is|has started))\s+(?:working|running|reviewing|fixing|on it)\b|"
    r"\b(?:codex|claude|cursor|gemini|minimax)\s+has\s+(?:your|the|this)\s+(?:[\w-]+\s+){0,6}(?:job|task|work|review)\b|"
    r"\b(?:i|we)(?:['’]ve| have)?\s+(?:(?:just|already|now)\s+)?(?:marked|completed|finished)\b"
    r".{0,80}\b(?:complete|done|finished|task|work|it|this|that)\b", re.I)
QUEUE_CLAIM = re.compile(DIRECT_QUEUE_CLAIM.pattern + r"|"
    r"\b(?:job|task|council)\b[^:.;!?\n]{0,120}\b(?:created|queued|scheduled|launched|started|assigned|builder inbox|picked up|in progress|running)\b"
    r"(?!\s+(?:when|if|until)\b)|"
    r"\bwork\s+(?:is|was|has been|is now)\s+(?:created|queued|scheduled|launched|started|assigned|picked up|in progress|running)\b"
    r"(?!\s+(?:when|if|until)\b)", re.I)
NO_JOB_NOTICE = re.compile(
    r"\bno (?:server[- ]confirmed )?(?:jobs?|tasks?)\s+(?:(?:was|were|has been|are)\s+)?(?:created|queued|started|running)\b|"
    r"\b(?:nothing|no work) (?:was |is |has been )?(?:queued|started|running)\b|"
    r"\bstart a job\s*:", re.I)
REFERENCE_PROGRESS_CLAIM = re.compile(
    DIRECT_QUEUE_CLAIM.pattern + r"|"
    r"\b(?:jobs?|tasks?|work|council)(?:\s+(?:you|that|which)\b[^.;!?\n]{0,60})?"
    r"(?:['’]s|\s+(?:is|are|was|were|has|have)|\s*[:–—-]|\s+(?=now|already|currently))\s*"
    r"(?:(?:now|already|currently|been)\s+)*(?:running|in progress|picked up)\b", re.I)
STATUS_QUESTION = re.compile(
    # Resource-use instructions must reach dispatch/model handling. Only an
    # explicit resource observation belongs in the server-owned status route.
    r"\b(?:status|resources? (?:usage|utilization|availability|health)|"
    r"(?:check|show(?: me)?) (?:the )?resources?|"
    r"(?:what|which) resources? (?:are|do we have)|how are (?:the |our )?resources?(?: doing)?|"
    r"(?:are we|we) using (?:all (?:of )?(?:the |our )?|any )?resources?|"
    r"workers? doing|each (?:worker|model)|all (?:workers|models|LLMs)|"
    r"work being performed|what about (?:Gemini|MiniMax|Codex|Claude|Cursor)|"
    r"(?:what(?:['’]s| is) (?:working on what|going on)|what are you working on|each llm)|"
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
    r"\b(?:daemons?|services?|workers?|reviewers?|process(?:es)?|servers?|systems?|agents?)\s+"
    r"(?:is|are|was|were)\s+(?:(?:now|still|currently)\s+)?(?:held|paused)\b|"
    r"\b(?:" + PROJECT.pattern + r"|work|coding|jobs?|tasks?)\s+(?:is|are|has been|have been)\s+(?:paused|held)\b|"
    r"\b(?:awaiting|pending)\s+(?:your\s+)?(?:permission|approval|go[- ]ahead)\b|"
    r"\b(?:until you (?:say (?:go|resume)|resume|give (?:the )?go[- ]ahead)|waiting for (?:your|permission)|"
    r"(?:need|require) (?:your |fresh |renewed |explicit )*(?:permission|approval|go[- ]ahead))\b", re.I)
HOLD_QUESTION = re.compile(r"^(?:(?:are|is|am|do|does|why)\b[^.!]*\b(?:on hold|holds? (?:still )?active|paused|need.{0,20}permission)\b[^.!]*|what holds? are active)\??$", re.I)
STATE_ADVERB = r'(?:already|now|just|still|yet|[a-z]+ly)'
MODAL_PERFECT = r'must\s+(?:'+STATE_ADVERB+r'\s+){0,3}have\s+(?:'+STATE_ADVERB+r'\s+){0,3}been'
PERMISSION_CHANGE = re.compile(
    r'\b(?:hold|permission|approval)\b[^,;!?]{0,30}'
    r'\b(?:is|was|has been|'+MODAL_PERFECT+r'|now|already)\s+(?:'+STATE_ADVERB+r'\s+){0,3}(?:lifted|cleared|released|granted)\b|'
    r'\b(?:I|we|you)(?:[’\']ve|\s+have)?\s+(?:(?:already|now)\s+)?'
    r'(?:lifted|cleared|released|granted)\s+(?:(?:the|your|our|my|real|actual|current|existing)\s+){0,3}'
    r'(?:hold|permission|approval)\b', re.I)
PURE_GREETING = re.compile(r"(?:hi|hey|hello|good (?:morning|afternoon|evening))"
                           r"(?:[, ]+(?:bob|there))?[.!? ]*", re.I)
GREETING_OPERATIONS = re.compile(
    r"\b(?:codex|claude|cursor|gemini|minimax|workers?|jobs?|tasks?|queue|services?|lanes?|llms?)\b"
    r"[^.!?]{0,200}\b(?:running|working|ready|idle|busy|queued|claimed|paused|cooldown|available|waiting|active|started|failed|healthy)\b|"
    r"\b(?:running|queued|active|idle|busy)\b[^.!?]{0,80}\b(?:workers?|jobs?|tasks?|services?|lanes?)\b|"
    r"\bready for (?:new )?work\b", re.I)


STICKY_REPLY = re.compile(r"(?:(?:ready when you are|(?:hi|hey|hello)(?:[, ]+Jeff)?|"
                         r"(?:I(?:['’]m| am) )?ready to help)[.!,\s]*)+", re.I)


def sticky_reply(text, content):
    # A literal-output request is content, not an accidental greeting.
    literal = (re.search(r"\b(?:say|reply|return|write|print|output)\s+(?:with\s+)?"
                         r"(?:exactly|verbatim|the (?:exact|literal) (?:text|words|string))\b", text, re.I)
               and not re.search(r"\b(?:never|not|don[’']t)\b", text, re.I))
    if literal and re.search(r"\b(?:ready when you are|ready to help|hi|hey|hello)\b", text, re.I):
        return False
    return bool(not PURE_GREETING.fullmatch(text.strip()) and STICKY_REPLY.fullmatch(content.strip()))


def dispatch_block(conversation):
    messages = (conversation or {}).get('messages', [])
    return messages[-1].get('dispatch_blocked') if messages else None


def greeting_content(content):
    """A plain greeting does not request the operational context sent to models."""
    parts = re.split(r"(?<=[.!?])(?=\s)|(?<=\n)", content)
    kept = []
    for part in parts:
        # Keep natural conversational offers; they are not claims about live
        # utilization. The ordinary effect/permission guards still run below.
        offer = re.match(r"\s*(?:I can\b|Would you like\b|Want (?:me )?to\b|Shall we\b)", part, re.I)
        if offer or not GREETING_OPERATIONS.search(part):
            kept.append(part)
    return "".join(kept).strip() or "Hi Jeff!"


DETAILS = re.compile(r"\b(?:raw|diagnostic(?:s)?|internal (?:ids?|details)|(?:job|task|screen|process) (?:ids?|names?)|pids?)\b", re.I)
HIDE_DETAILS = re.compile(r"\b(?:no|without|hide|omit|skip|don['’]t show|do not show|leave out)\b.{0,45}"
                          r"\b(?:raw|internal|ids?|names?|pids?|diagnostics?)\b", re.I)
IDENTITY = re.compile(r"\bwho(?:['’]s| is) (?:answering|responding)\b", re.I)
HEALTH = re.compile(r"\b(?:health|healthy|failing|errors?|providers?)\b", re.I)


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


def _lane_line(row, detailed=False):
    label = row.get("screen") or "lane"
    llm = row.get("llm_label") or WORKER_NAMES.get(row.get("llm")) or row.get("llm") or "worker unconfirmed"
    if row.get("model"):
        llm += " (" + row["model"] + ")"
    project = row.get("project")
    task = row.get("task") or row.get("screen", "").removeprefix("lane-").replace("-", " ")
    body = (project + ": " if project else "") + task
    duration = _duration(row.get("elapsed_seconds"))
    state = row.get("state") or "running"
    if state == 'not_observed':
        line = f"{label} — {llm}, not currently observed; last activity {duration} ago — {body}; outcome unverified"
    elif state == "finished":
        line = f"{label} — {llm}, finished {duration} ago — {body}"
    else:
        prefix = {"running": "running ", "paused": "paused ", "unverified": "session open ", "claimed": "claimed "}.get(state, "")
        line = f"{label} — {llm}, {prefix}{duration} — {body}"
    if row.get("result_path"):
        line += " — " + row["result_path"]
    elif row.get("log_path") and (not row.get("prompt_path") or not row.get("task")):
        line += "; " + row["log_path"]
        if row.get("last_log_line"):
            line += "; last: " + row["last_log_line"]
    if detailed:
        ids = [str(row[key]) for key in ("screen", "pid") if row.get(key)]
        if ids:
            line += " (" + ", ".join(ids) + ")"
        for key in ("prompt_path", "log_path"):
            if row.get(key):
                line += f"; {row[key]}"
    return line


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
    label = row.get("task") or row.get("title") or (row.get("prompt") or "").split("\n")[0] or task_label(screen=row.get("screen"))
    label = clean(label, 95).strip(" .;:") or "a CLI session"
    project = row.get("project")
    if project and project.lower() not in label.lower():
        label = project + ": " + label
    elif project:
        label = re.sub(re.escape(project), lambda _: project, label, flags=re.I)
    return label


def _casual_status(snap):
    """Summarize the existing observation; keep its inventory in diagnostics."""
    work, inspection = snap["work"], snap["inspection"]
    groups = {}

    def add(name, singular, plural, priority):
        groups.setdefault((priority, singular, plural), []).append(name)

    for name in WORKER_NAMES:
        rows = [row for row in work if row.get("worker") == name]
        pending = [row for row in snap.get("queue_jobs", {}).get("queued", []) if row.get("worker") == name]
        if name == "mini" and not rows and not pending:
            continue
        display = WORKER_NAMES[name]
        running = [row for row in rows if row.get("state") == "running" and row.get("assignment_recorded") is not False]
        if running:
            labels = []
            for row in running:
                label = clean(row.get("project") or _task_name(row), 60)
                # Prompt headings and fallback screen labels are evidence, not
                # readable assignments. Never echo machine labels into chat.
                if re.search(r"lane-|logs/|\bPID\b|queue_counts|model not reported|job runner", label, re.I):
                    label = "the current task"
                label = re.sub(r"[;.!?]+", ",", label).strip(" #,: ") or "the current task"
                if label not in labels:
                    labels.append(label)
            summary = _join(labels[:2]) + (" and other tasks" if len(labels) > 2 else "")
            tail = "working on " + summary
            if any(row.get("state") == "paused" for row in rows):
                tail += ", with some work paused"
            add(display, "is " + tail, "are " + tail, 0)
        elif rows and all(row.get("state") == "paused" for row in rows):
            add(display, "is paused", "are paused", 1)
        elif rows:
            add(display, "has activity I can't confirm yet", "have activity I can't confirm yet", 1)
        elif pending:
            add(display, "has work waiting to run", "have work waiting to run", 2)
        elif snap.get("lane_locks", {}).get(name, {}).get("state") == "busy":
            add(display, "has activity I can't confirm yet", "have activity I can't confirm yet", 1)
        elif _cooldown(snap, name):
            cooldown = _cooldown(snap, name).removeprefix("; ")
            tail = "cooling down" + (" until " + cooldown.removeprefix("resets ") if cooldown.startswith("resets ") else "")
            if not all(inspection.values()):
                tail += ", with current activity unconfirmed"
            add(display, "is " + tail, "are " + tail, 3)
        else:
            add(display, "is idle" if all(inspection.values()) else "has no confirmed active work",
                "are idle" if all(inspection.values()) else "have no confirmed active work", 4)
    sentences = [_join(names) + " " + (singular if len(names) == 1 else plural)
                 for (priority, singular, plural), names in sorted(groups.items(), key=lambda item: item[0][0])]
    other = [row for row in work if row.get("worker") not in WORKER_NAMES]
    if other:
        sentences.append("There are other open sessions whose work I can't confirm")
    if any(row.get("worker") not in WORKER_NAMES for row in snap.get("queue_jobs", {}).get("queued", [])):
        sentences.append("Some work is still waiting for a worker")
    if not all(inspection.values()):
        sentences.append("A live check failed, so I can't confirm the full picture")
    # Ordinary answers stay short even when all workers have different tasks.
    # Group adjacent clauses with ordinary conjunctions, never diagnostic chains.
    while len(sentences) > 4:
        sentences[0:2] = [sentences[0] + ", while " + sentences[1]]
    return ". ".join(sentences) + "."


def format_operational_reply(snap, provider="server", text=""):
    """Live worker facts in casual sentences; diagnostics are opt-in."""
    counts, work, inspection = snap["queue_counts"], snap["work"], snap["inspection"]
    bob = snap.get("bob_lanes") or {}
    live_lanes = bob.get("live") or []
    finished_lanes = bob.get("finished_recent") or []
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
    if live_lanes:
        running_count = sum(1 for row in live_lanes if row.get("state") == "running")
        first = f"{running_count or len(live_lanes)} Bob lane{'s' if len(live_lanes) != 1 else ''} on screen."
        lines = [first]
        lines.extend(_lane_line(row, detailed) for row in live_lanes)
        if finished_lanes and re.search(r"\b(?:finished|done|recent|last)\b", text, re.I):
            lines.append("Recent lane activity (last 12h; outcomes unverified): " + " | ".join(_lane_line(row, detailed) for row in finished_lanes[:6]))
        other = [row for row in work if row.get("state") == "running" and row.get("screen") not in {lane["screen"] for lane in live_lanes}]
        if other:
            lines.append("Other sessions: " + " | ".join(_work_line(row, detailed) for row in other))
        lines.append(f"Job runner: {counts['claimed']} claimed, {counts['queued']} queued.")
        for name in ("codex", "claude", "cursor", "gemini", "minimax"):
            rows = [row for row in work if row.get("worker") == name]
            if rows:
                continue
            state = "idle" if all(inspection.values()) else "activity unconfirmed"
            cooldown = _cooldown(snap, name)
            if cooldown or (snap.get("lane_locks", {}).get(name, {}).get("cached_state") == "cooldown"):
                lines.append(WORKER_NAMES[name] + ": " + state + cooldown + ".")
        if IDENTITY.search(text):
            lines.append(WORKER_NAMES[provider] + " answered this message." if provider in WORKER_NAMES else "This answer comes from live checks.")
        return "\n".join(lines)
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


def live_status_question(text, conversation=None):
    """Require a request to observe, not an operational noun in an instruction.

    Use the same classification before generation and before delivery. Quoted,
    conditional and prohibited observations cannot select a server reply.
    """
    from answer_intent import conceptual, instructions, request_clauses, live_observation
    from conversation_focus import reference_scope
    if conceptual(text) or reference_scope(conversation,text):return False
    target = r'(?:workers?|models?|LLMs?|jobs?|tasks?|services?|resources?|queue|system|status)'
    # A dash inside an antecedent does not turn its consequent into a new
    # unconditional request. Sentence boundaries can start a fresh request.
    parts=[]
    for sentence in re.split(r'[.!?;]\s+|\n+',instructions(text)):
        first=request_clauses(sentence)
        if not first:continue
        if re.match(r"^(?:if|unless|until|when|once|before|suppose|imagine|do not|don['’]t|never|without)\b",first[0],re.I):continue
        if re.search(r'\b(?:only if|unless|until|once|provided that)\b',sentence,re.I):continue
        head=re.split(r'\b(?:and|but|then)\b',sentence,maxsplit=1,flags=re.I)[0]
        if re.search(r'\b(?:if|when)\b|\bafter\s+(?:I|we|you|they|it|he|she)\b',head,re.I):continue
        parts.extend(first)
    for part in parts:
        part=re.sub(r'^no[, ]+((?:is|are|what|which|how)\b)',r'\1',part,flags=re.I)
        part=re.sub(r'^(?:I|we)\s+(?:want|need)\s+to\s+(?:also\s+)?(?:know|see)\s+', '',part,flags=re.I)
        if re.match(r"^(?:if|unless|until|when|once|before|suppose|imagine|do not|don['’]t|never|without)\b",part,re.I):
            continue
        from answer_intent import ANSWER
        observe = re.match(r'^(?:check|show|inspect|tell me)\b',part,re.I)
        separate_directive = ANSWER.match(part) and not re.search(r'\b(?:whether|if|how to)\b',part,re.I)
        if (observe or separate_directive) and live_observation(part):return True
        if not STATUS_QUESTION.search(part):continue
        # Short direct observations can carry presentation constraints, but
        # field lists and requested status-report prose are not observations.
        if re.fullmatch(r'(?:(?:current|live|brief|quick)\s+)*(?:(?:service|disk|storage)\s+status|'
                        r'status(?: update)?|diagnostics?|resources? (?:usage|utilization|availability|health))'
                        r'(?:\s+(?:with|without)\s+[^.!?]+)?(?:[, ]+please)?[.!? ]*',part,re.I):return True
        if re.fullmatch(r'(?:give|show|tell) me\s+(?:(?:a|the|brief|short|current|quick)\s+)*'
                        r'(?:status|update|status update)(?:\s+(?:please|now))?[.!?]*',part,re.I):return True
        if re.match(r'^what(?:[\'’]s| is)\s+(?:(?:the|our|my|current|live)\s+)*'
                    r'(?:[\w-]+\s+){0,3}status\b',part,re.I):return True
        if re.match(r'^(?:what(?:[\'’]s| is| are)|which|who(?:[\'’]s| is))\s+'
                    r'(?:(?:the|our|my|current|live)\s+)*(?:status|running|moving|happening|going on|'
                    r'working on what|answering|responding|'+target+r')\b',part,re.I):return True
        if re.match(r'^what are you working on\b',part,re.I):return True
        names=r'(?:Gemini|MiniMax|Codex|Claude|Cursor)'
        if re.fullmatch(r'what about '+names+r'(?:\s*(?:,|and|or|&)\s*'+names+r')*[.!? ]*',part,re.I):return True
        if re.match(r'^how(?:[\'’]s| is| are| we)?\s+(?:(?:the|our|my)\s+)?'
                    r'(?:everything|it going|we doing|'+target+r')\b',part,re.I):return True
        if re.match(r'^(?:is|are)\s+(?:(?:the|our|my|current|live)\s+)*'
                    r'(?:it|anything|everything|things|work|'+target+r'|Gemini|MiniMax|Codex|Claude|Cursor)\b'
                    r'.{0,60}\b(?:going|moving|running|making progress|being performed|healthy|failing|working)\b',part,re.I):return True
        if re.match(r'^(?:are we|we) using\b|^(?:any|making) progress\b|^works? on all (?:workers|models|LLMs)\b',part,re.I):return True
    return False


def correcting_status(text, conversation):
    if not CRITICISM.search(text.strip()):
        return False
    messages=(conversation or {}).get('messages',[])
    previous=next((m for m in reversed(messages) if m.get('role')=='user'
                   and m.get('content')!=text and not CRITICISM.search(m.get('content',''))),None)
    if not previous:return False
    # A valid receipt proves what was observed, not that the old routing was
    # appropriate. Do not perpetuate a wrongly classified owner request.
    if not live_status_question(previous.get('content','')):return False
    replies=[m for m in messages if m.get('role')=='assistant' and
             m.get('request_id')==previous.get('request_id')]
    if not replies:
        # Old callers without a completed answer have no mutable focus to trust.
        return live_status_question(previous['content'])
    answer=replies[-1];observed=answer.get('status_observation') or {}
    from status_observation import snapshot_digest
    return bool(observed.get('message_id')==answer.get('id') and
                observed.get('request_id')==previous.get('request_id') and
                observed.get('conversation_id')==(conversation or {}).get('id') and
                observed.get('snapshot') and observed.get('snapshot_sha256')==snapshot_digest(observed['snapshot']))


def operational_reply(root, provider, text="", *, observation=None, redact=lambda value: value):
    from status_observation import redact_snapshot, snapshot_digest
    started = time.time()
    snap = redact_snapshot(build_live_status_snapshot(root, now=started), redact)
    finished = time.time()
    content = format_operational_reply(snap, provider, text)
    if observation is not None:
        observation.update(schema_version=1, observed_from=started, observed_until=finished,
                           question=text, renderer_provider=provider,
                           snapshot=snap, snapshot_sha256=snapshot_digest(snap))
    return content


def unperformed_restart(root, text):
    """Preserve a restart request's explicit scope without inventing effects."""
    from pathlib import Path
    from chat_intent import command, project_targets
    from dispatch_receipts import NO_DISPATCH
    directive = command(text)
    if not re.match(r"^(?:(?:go(?:\s+ahead)?|resume)(?:\s+and)?[\s,:!]+)?restart\b", directive, re.I):
        return NO_DISPATCH
    targets = project_targets(directive, {'project_order': []})
    if not targets:
        return NO_DISPATCH
    content = "I haven't restarted " + _join(targets) + ". No new work was queued."
    names = r"(?:Gemini|MiniMax|Codex|Claude|Cursor)"
    restriction = re.search(r"\b(?:only\s+(?:use|using)|(?:use|using)\s+only)\s+(" + names +
                            r"(?:\s*(?:,|&|and)\s*(?:and\s+)?" + names + r")*)\b", directive, re.I)
    if restriction:
        labels = {name.lower(): name for name in ('Gemini', 'MiniMax', 'Codex', 'Claude', 'Cursor')}
        requested = list(dict.fromkeys(labels[name.lower()] for name in re.findall(names, restriction[1], re.I)))
        content += " Your " + _join(requested) + " restriction has not been applied to any job."
    if (Path(root) / 'conductor/SOLO-WORKER').exists():
        content += " Additional workers are paused in solo mode."
    return content + " I can help define the next task for each project here."


def enforce(root, text, answer, conversation=None, *, observation=None, redact=lambda value: value):
    content = answer["content"]
    from answer_intent import conceptual, wants_answer, LIVE_REQUEST
    from conversation_focus import reference_scope
    reported=reference_scope(conversation,text)
    from conversation_focus import focus
    from reported_records import source_bindings, topic_record
    record=focus(conversation or {}) if reported else None
    bindings=source_bindings(record)
    reference = conceptual(text) or reported
    from worker_assignment import requested_workers
    blocked = dispatch_block(conversation)
    if requested_workers(text, conversation) and not blocked:
        # Model prose is never an assignment receipt, even if it sounds ready.
        return "I haven't assigned a worker from this reply. No new job was queued."
    state = state_for(conversation if conversation is not None else {})
    scopes = blocked_scopes(state, projects(text))
    if HOLD_QUESTION.match(text.strip()) and not reported:
        return hold_reply(scopes) if scopes else "There are no active conversation holds."
    from task_dispatch import CHAT_STYLE, PREAMBLE
    # A style preference calls for a simple acknowledgement, never a status
    # report from operational snapshots included in the model context.
    if CHAT_STYLE.match(PREAMBLE.sub("", text.strip())):
        return "Got it."
    if PURE_GREETING.fullmatch(text.strip()):
        content = greeting_content(content)
    from resource_inventory import question as resource_question
    if not reference and not resource_question(text) and (live_status_question(text,conversation) or correcting_status(text, conversation)):
        return operational_reply(root, answer["provider"], text, observation=observation, redact=redact)
    else:
        from dispatch_receipts import claims_dispatch, dispatch_prose, reference_context, NO_DISPATCH
        # Once operational routing is resolved, guides and other requested
        # text can discuss state without acknowledging effects. Live status
        # requests such as "show me resources" retain the branch above.
        reference = reference or (wants_answer(text) and not LIVE_REQUEST.search(text))
        sentences = re.split(r"(?<=[.!?])(?=\s)|(?<=\n)", content)
        if not reference:
            content = "".join(part for part in sentences if not NO_JOB_NOTICE.search(part)).strip() or NO_DISPATCH
        supplied = reference_context(text, conversation) if reference else ''
        # The broad legacy proximity pattern mistakes explanations such as
        # "once it picks up a task ... that's running" for an actual receipt.
        # Reference answers still reject direct effects, concrete IDs and
        # asserted progress; they do not need the proximity-only heuristic.
        progress_claim = REFERENCE_PROGRESS_CLAIM if reference else QUEUE_CLAIM
        def unsupported_effect(part):
            return bool(claims_dispatch(part,reference=supplied,bindings=bindings,context=content) or
                        progress_claim.search(dispatch_prose(part.strip(),reference=supplied)) or
                        PROVIDER_CLAIM.search(part))
    from reported_records import units, presentation, foreign_label, foreign_subject, source_bindings, receipt
    sentences = list(units(content))
    def asserted_permission_change(part):
        for change in PERMISSION_CHANGE.finditer(part):
            # A conditional governs its own predicate, not a subsequent
            # assertion across punctuation or a coordinating conjunction.
            prefix=part[:change.start()]
            conditional=re.search(r'\b(?:if|when|once|before|until)\b'
                                  r'(?:(?!\b(?:and|but|yet|however|now that)\b)[^,;:.!?\n])*$',prefix,re.I)
            # A requested verification is not a completed permission change.
            # Anchor its governing predicate locally so a subsequent actual
            # assertion cannot borrow a preceding check or conditional.
            local=re.split(r'[;:.!?\n]|\b(?:and|but|yet|however)\b',prefix,flags=re.I)[-1]
            local=re.sub(r'[*_`]', '', local).strip()
            verification=re.fullmatch(
                r'(?:(?:first\s+)?(?:verify|check|confirm)\s+(?:that|whether)|'
                r'(?:(?:obtain|require|seek)\s+)?(?:verification|confirmation|evidence)\s+that|'
                r'(?:we|you)\s+(?:must|should|need to)\s+(?:verify|check|confirm)\s+(?:that|whether))(?:\s+the)?\s*',
                local,re.I)
            if verification and re.match(r'^(?:verification|confirmation|evidence)\b',local,re.I):
                tail=part[change.end():].strip()
                # A bare checklist item can name evidence to obtain. A noun
                # phrase with a completed main predicate instead asserts that
                # evidence exists; it cannot masquerade as an instruction.
                for tail_clause in re.split(r'[,;]|\b(?:and|but|yet|however)\b',tail,flags=re.I):
                    required=re.match(r'^\s*(?:is required|must\b|should\b|needs? to\b)',tail_clause,re.I)
                    completed=re.search(r'\b(?:is|was|has|have|exists?|now|already|recorded|obtained|received|confirmed)\b',tail_clause,re.I)
                    if completed and not required:verification=None
            if not conditional and not verification:
                return True
        return False

    def held_scope_question(part):
        # A real hold may be discussed while choosing the remaining scope.
        # Preserve that question, not arbitrary model status or permission
        # claims; the ordinary effect guard has already run above.
        mentioned=projects(part)
        question=re.sub(r'^\s*(?:[-*+]\s+|\d+[.)]\s+)?', '', part).strip()
        # Normalize a bounded Markdown label for recognition only. Every
        # effect/permission check still sees the original, including its label.
        question=re.sub(r'^(?:\*\*[^*\n!?]{1,64}:\*\*|__[^_\n!?]{1,64}:__)\s*', '', question)
        asks_scope=re.fullmatch(r'(?:(?:when|if|before|once)\b[^,;!?]{0,180},\s*)?'
                               r'(?:which|what|should|could|would|can)\b[^;!?]*\?',question,re.I)
        return bool(scopes and asks_scope and not asserted_permission_change(part) and
                    (not mentioned or all(blocked_scopes(state,[name]) for name in mentioned)))
    def saved_hold_reference(part):
        part=re.sub(r'^\s*(?:[-*+]\s+|\d+[.)]\s+)', '', part)
        # Referencing a matching saved hold is not an acknowledgment of a new
        # permission change. Effect/dispatch checks still examine all prose.
        if not scopes or asserted_permission_change(part):return False
        from hold_scope import GLOBAL_REFERENCE, pending_reference
        mentioned=projects(part)
        if any(not blocked_scopes(state,[name]) for name in mentioned):return False
        if pending_reference(part,state,scopes,HOLD_CLAIM):return True
        if re.search(r'\b(?:'+ '|'.join(re.escape(n) for n in WORKER_NAMES)+r')\b',part,re.I):return False
        global_hold=state['holds'].get('all')
        if (not global_hold or global_hold.get('released_projects')) and GLOBAL_REFERENCE.search(part):return False
        qualifier=re.match(r'\s*For\s+([^,;:]+),',part,re.I)
        if qualifier and qualifier[1].strip() not in state['holds']:return False
        # A bare reference is allowed only within the current held project;
        # arbitrary external subjects cannot borrow that project's permission.
        for clause in re.split(r';|\b(?:and|but|yet|however)\b',part,flags=re.I):
            for match in HOLD_CLAIM.finditer(clause):
                prefix=clause[:match.start()];suffix=clause[match.end():]
                if re.search(r'\b(?:your|the|this|that|earlier|previous)\s+(?:(?:earlier|previous|existing|current)\s+)?hold\b',match[0],re.I):
                    # A labelled pending decision is a noun phrase, not an
                    # unsupported hold on an arbitrary external service.
                    label=re.fullmatch(r'\s*(?:\*\*)?releasing\s*',prefix,re.I) and re.match(r'\s*\*\*?:|\s*:\*\*',suffix)
                    simple=not prefix.strip(' *\n') and re.match(r'\s+(?:remains?\s+(?:active|in place)|still applies)[.!?\s]*$',suffix,re.I)
                    if label or simple:continue
                    # A dependent prepositional reference names the existing
                    # constraint; it does not assert a new hold or release.
                    incidental = re.search(r'\b(?:under|within|during|subject to)\s*$',prefix,re.I)
                    target = re.match(r'\s+(?:on|for|in)\s+(.+)',suffix,re.I)
                    tail = suffix
                    if target:
                        bound = next((re.match(re.escape(name)+r'\b',target[1],re.I)
                                      for name in mentioned if blocked_scopes(state,[name]) and
                                      re.match(re.escape(name)+r'\b',target[1],re.I)),None)
                        if not bound:return False
                        tail = target[1][bound.end():]
                    # A relative clause changes what is asserted about the
                    # hold. A declarative 'X remains under' asserts its subject
                    # is held; neither is just an incidental reference.
                    reference_tail = (not tail.strip(' .!?\n') or
                                      re.fullmatch(r'\s+before\s+\w+ing\b[^,;.!?]*[.!?\s]*',tail,re.I))
                    from claim_scope import DIRECTIVE, QUESTION, plain
                    preparing = DIRECTIVE.match(plain(prefix)) or QUESTION.match(plain(prefix))
                    # Coordination of objects may leave a relative noun phrase
                    # after "and" ("files and checks you want examined"). It
                    # retains its question/directive governor, not a new actor.
                    relative_object = (DIRECTIVE.match(plain(part)) or QUESTION.match(plain(part))) and re.match(
                        r'^\s*(?:[\w-]+\s+){1,4}(?:you|we)\s+(?:want|need|choose)\b',plain(prefix),re.I)
                    predicate_prefix=prefix[:incidental.start()] if incidental else ''
                    asserted_subject=re.search(r'\b(?:is|are|was|were|has|have|remains?|stays?|falls?)\b\s*'
                                               r'(?:[\w-]+\s+){0,3}$',predicate_prefix,re.I)
                    from assertion_scope import nonasserted
                    from claim_scope import CONNECTOR, ASSERTED_LINK
                    links=[m for m in CONNECTOR.finditer(predicate_prefix)
                           if ASSERTED_LINK.fullmatch(m[0].strip(' ,'))]
                    local_prefix=predicate_prefix[links[-1].end():] if links else predicate_prefix
                    uncertain = nonasserted(local_prefix,'held',sentence_start=True)
                    # An introductory bound PP may precede its actual check.
                    # Check that remaining instruction separately for effects.
                    introductory = incidental and not prefix[:incidental.start()].strip(' *\n')
                    following = re.match(r'\s*,\s*(.+)',tail,re.S)
                    preposed = introductory and following and DIRECTIVE.match(plain(following[1]))
                    if (incidental and (not asserted_subject or uncertain) and
                            ((reference_tail and (preparing or relative_object)) or preposed) and
                            not foreign_subject(clause,projects,WORKER_NAMES)):
                        continue
                    return False
                subject=re.split(r'[,;:]',prefix)[-1].strip(' *\n')
                named=projects(match[0]) or projects(subject)
                if named and all(blocked_scopes(state,[p]) for p in named):
                    # Bare operational status belongs to the saved-state
                    # renderer. Contextual discussion may reference that hold
                    # without replacing the rest of a useful answer.
                    standalone = not suffix.strip(' .!?\n') and (not subject or any(
                        re.fullmatch(re.escape(p)+r'(?:\s+(?:is|was))?',subject,re.I) for p in named))
                    if standalone:return False
                    if (projects(match[0]) and (not subject or re.fullmatch(r'While|As|Because',subject,re.I))) or any(re.fullmatch(r'(?:(?:While|As|Because)\s+)?'+re.escape(p)+r'(?:\s+(?:is|was))?',subject,re.I) for p in named):continue
                if re.fullmatch(r'You\s+(?:set|put|placed)\s+(?:the\s+)?(?:execution|work)',subject,re.I):continue
                return False
        return True
    record_ids=set(bindings)
    # The server-bound focus supplies the referent for "its status" and
    # "the hold" across corrections. It does not authorize any real effect.
    record_topic=topic_record(record,bindings)
    record_subject=record_topic
    def attributed_record_hold(part):
        nonlocal record_subject
        if not reported or not record_ids:return False
        label,plain=presentation(part)
        # Neutral presentation never erases a bound record. An actual actor
        # label breaks inheritance, but an explicit body subject may rebind it.
        # Every effect/permission check still examines the unmodified text.
        if label:
            if foreign_label(label,projects,WORKER_NAMES):record_subject=None
        identity='(?:'+'|'.join(re.escape(i) for i in sorted(record_ids))+')'
        subject=r'(?:(?:task|assignment|record)\s+)?'+identity
        nominal=r'(?:the|this|that)\s+(?:(?:supplied|reported|fictional|hypothetical)\s+)?(?:task|assignment|record)'
        predicate=r'(?:(?:is|was|remains?|stays?)\b\s*)?(?:(?:still|explicitly|currently)\b\s*)?(?:(?:recorded|reported|described|listed|marked)\s+as\s*)?'
        accepted=True
        for clause in re.split(r'[.!?;]\s*|\b(?:and|but|yet|however)\b',plain,flags=re.I):
            # A new named app/worker/real-world subject cannot inherit a
            # fictional record's state, including after a conjunction.
            if projects(clause) or re.search(r'\b(?:'+ '|'.join(re.escape(n) for n in WORKER_NAMES)+r'|your|our|my|actual|real|this chat|this conversation)\b',clause,re.I):
                record_subject=None
                if HOLD_CLAIM.search(clause):accepted=False
                continue
            clean_clause=re.sub(r'^\s*(?:In the (?:supplied|reported|fictional|hypothetical) (?:record|case|scenario),?\s*|(?:Because|While|Whereas)\s+)','',clause,flags=re.I).strip()
            for claim in HOLD_CLAIM.finditer(clean_clause):
                prefix=clean_clause[:claim.start()].strip()
                suffix=clean_clause[claim.end():].strip()
                identified=re.fullmatch(subject+r'\s*'+predicate,prefix,re.I)
                task_directive=re.fullmatch(r'(?:keep|maintain)\s+'+subject+r'\s*',prefix,re.I)
                described=bool(re.fullmatch(nominal+r'\s*'+predicate,prefix,re.I))
                anaphor=record_subject and bool(re.fullmatch(r'(?:it|(?:its|the|this|that)\s+(?:(?:task|assignment|record|current|recorded|reported)\s+)*(?:status|state))\s*'+predicate,prefix,re.I))
                inherited=record_subject and bool(re.fullmatch(predicate,prefix,re.I))
                # A supplied record may restate its own hold/status without an
                # actor performing a permission change.
                described_status=bool(record_subject and re.search(
                    r'\b(?:(?:its|the|this|that)\s+)?(?:(?:task|assignment|record|current|recorded|reported)\s+)*'
                    r'(?:status|state)\s+'+predicate+r'(?:on hold|held|paused)\b',clean_clause,re.I))
                # References/advice/checks about a hold have a bounded object;
                # "the hold on the backup service" cannot borrow this scope.
                noun=bool(re.fullmatch(r'(?:the|this|that|earlier|previous)(?:\s+(?:earlier|previous|existing|current|owner(?:-placed)?|recorded|reported))?\s+hold',claim[0],re.I))
                governing=bool(re.fullmatch(r'(?:(?:maintain|keep|preserve)\s*|(?:(?:obtain|require|seek)\s+)?(?:verification|confirmation|evidence)\s+that\s*|(?:first\s+)?(?:verify|check|confirm)\s+(?:that|whether)\s*)?',prefix,re.I))
                # Requirements describe evidence still needed; they do not
                # assert that a permission change actually occurred. The
                # separate change guard checks the entire original unit.
                prerequisite=bool(re.search(r'\b(?:must|should|needs? to|is required to)\b',prefix,re.I)
                    and re.search(r'\b(?:before|after)\s+(?:lifting|clearing|releasing)\s*$',prefix,re.I)
                    and not foreign_label(prefix,projects,WORKER_NAMES))
                explicit_object=bool(re.fullmatch(r'(?:on|for|in)\s+'+subject+
                    r'(?:\s*(?:[,;]|(?:until|while|before|after|must|should|needs? to|remains?|stays?|is|was|are|were)\b).*)?\s*[.!?]*',suffix,re.I))
                state_modifier=bool(re.match(r'(?:still\s+)?(?:applies|active)|in\s+(?:place|force|effect)\b(?!\s+(?:on|for|in)\b)',suffix,re.I))
                object_ok=not re.match(r'(?:on|for|in)\b',suffix,re.I) or explicit_object or state_modifier
                directive=bool(re.fullmatch(r'(?:maintain|keep|preserve)\s*',prefix,re.I))
                from reported_records import prospective_hold_check
                bound_target=re.match(r'(?:on|for|in)\s+'+subject+r'(?=\s|$)',suffix,re.I) if explicit_object else None
                prospective_tail=suffix[bound_target.end():] if bound_target else suffix
                prospective=bool(record_topic and prospective_hold_check(prefix,prospective_tail))
                noun_reference=(record_subject or explicit_object or (directive or prospective) and record_topic) and noun and (governing or prerequisite or prospective) and object_ok
                denied_lift=bool((record_subject or explicit_object) and noun and object_ok and re.search(
                    r"\b(?:do(?:es)? not|cannot|can['’]t|has no(?:\s+\w+){0,4}\s+authority to|will not|did not)\s+"
                    r'(?:override|clear|lift|release|revoke|cancel)\b|'
                    r'\bno authority to\s+(?:override|clear|lift|release)\b',prefix,re.I))
                remaining_hold=bool((record_subject or explicit_object) and noun and object_ok and re.search(
                    r'\b(?:still applies|'
                    r'remains?\s+(?:(?:explicitly|currently|still)\s+)*(?:active|recorded|in (?:force|place|effect)|on hold|held)|'
                    r'stays?\s+(?:(?:explicitly|currently|still)\s+)*(?:active|in (?:force|place|effect)|on hold|held)|'
                    r'is still\s+(?:active|in (?:force|place|effect)|on hold|held))\b',
                    prefix+' '+suffix,re.I))
                if not (identified or task_directive or described or anaphor or described_status or
                        inherited and not noun or noun_reference or denied_lift or remaining_hold):
                    accepted=False
                    record_subject=None
                elif identified or task_directive:
                    record_subject=next(i for i in bindings if re.search(r'\b'+re.escape(i)+r'\b',prefix,re.I))
                elif explicit_object:
                    record_subject=next(i for i in bindings if re.search(r'\b'+re.escape(i)+r'\b',suffix,re.I))
            if not HOLD_CLAIM.search(clean_clause):
                # Coordinated predicates may share an explicit preceding
                # record subject, but not a different service's subject.
                explicit=re.search(r'(?:^|\bwhereas\s+)'+subject+r'\s+(?:is|was|are|were|remains?|stays?|has|have|requires?|needs?|must|should|may|can|could|will)\b',clean_clause,re.I)
                if explicit:record_subject=next(i for i in bindings if re.search(r'\b'+re.escape(i)+r'\b',explicit[0],re.I))
                elif foreign_subject(clean_clause,projects,WORKER_NAMES):record_subject=None
        return accepted
    from answer_fragments import DependencyState, depends_on_rejected_unit, heading_unit, ACKNOWLEDGEMENT
    dependency=DependencyState()
    kept=[];pending_effect=False;pending_reference=False;rejected_effect=False
    decisions=[];offset=0
    for part in sentences:
        # Track intervening subjects even when a sentence has no hold claim.
        # Otherwise "a service is offline. It is on hold" could inherit the
        # fictional task's referent across the first sentence's short circuit.
        context_record=record_subject
        record_hold=attributed_record_hold(part)
        changed=asserted_permission_change(part)
        effect=unsupported_effect(part)
        valid=not effect and not changed and (not HOLD_CLAIM.search(part) or
                held_scope_question(part) or saved_hold_reference(part) or record_hold)
        _,governor=dependency.consider(part,valid,offset=offset,taint=bool(effect or changed))
        # Independent list items, headings and separate sentences are judged
        # on their own. Only a true continuation or "therefore/so/this means"
        # back-reference inherits a rejected unit.
        dependent=depends_on_rejected_unit(part, pending=pending_reference)
        accepted=valid and not dependent
        if accepted:
            kept.append(part)
        elif part.strip():
            # An unresolved reference is not evidence of a fabricated effect.
            # Preserve independently checked payload/proof/requirement prose;
            # its original referents and final provenance remain checked.
            if effect or changed:pending_effect=True
            pending_reference=True
            rejected_effect=rejected_effect or effect or dependent
        decisions.append(receipt(part,offset=offset,accepted=bool(accepted),
            reason='unsupported_effect' if effect else
                ('dependent_on_rejected_effect' if pending_effect else 'dependent_on_unresolved_reference') if dependent else
                'unsupported_permission_change' if changed else 'supported_reference_or_nonclaim' if accepted else 'unbound_hold_claim',
            subject=record_subject,bindings=bindings))
        decisions[-1].update(context_record=context_record,context_source_bindings=bindings.get(context_record,[]))
        decisions[-1]['prospective_governor_start']=governor
        offset+=len(part)
    # A heading whose body survived is not a rejected consequence.
    for index,part in enumerate(sentences):
        decision=decisions[index]
        if decision['accepted'] or decision['reason'] not in (
                'dependent_on_rejected_effect','dependent_on_unresolved_reference'):
            continue
        if not heading_unit(part):
            continue
        for follow,follow_decision in zip(sentences[index+1:],decisions[index+1:]):
            if heading_unit(follow):
                break
            if follow_decision['accepted'] and follow.strip():
                decision['accepted']=True
                decision['reason']='supported_reference_or_nonclaim'
                break
    kept=[part for part,decision in zip(sentences,decisions) if decision['accepted'] or not part.strip()]
    if conversation and (reported or len(kept)!=len(sentences)):
        message=conversation.get('messages',[])[-1:]
        if message and message[0].get('role')=='assistant':
            import hashlib
            message[0]['authority_review']=dict(partial=len(kept)!=len(sentences),units=decisions,
                evaluated_input_sha256=hashlib.sha256(content.encode()).hexdigest(),
                stage='original_units_effect_hold_and_permission',
                scope='Reported-record and permission delivery checks; no execution authority')
    if len(kept) != len(sentences):
        content = "".join(kept).strip()
        if rejected_effect and (not content or ACKNOWLEDGEMENT.fullmatch(content)):
            return blocked or unperformed_restart(root,text)
        # Only the saved state may explain an operational hold.
        if scopes:
            content = (content + "\n\n" if content else "") + hold_reply(scopes)
        elif not content:
            content = "I could not produce a useful answer to that request. Please retry."
    if sticky_reply(text, content):
        content = "I could not produce a useful answer to that request. Please retry."
    if blocked:
        content = blocked + "\n\n" + content
    # A real model can still omit part of a restart request. Keep the user's
    # exact project/provider scope in the answer without inventing execution.
    scope = unperformed_restart(root, text)
    if scope != NO_DISPATCH:
        labels = projects(scope) + [name for name in ('Gemini', 'MiniMax', 'Codex', 'Claude', 'Cursor')
                                    if re.search(r"\b" + name + r"\b", scope, re.I)]
        compact = re.sub(r'[^a-z]', '', content.lower())
        if any(re.sub(r'[^a-z]', '', name.lower()) not in compact for name in labels):
            content = scope + "\n\n" + content
    return content
