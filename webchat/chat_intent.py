"""Durable user intent. Assistant prose and reference snapshots are not authority."""
import re

POLITE = r"(?:(?:please|bob)[,:]?\s+|(?:can|could|would|will) you\s+|i (?:want|need) (?:you )?to\s+|let['’]s\s+)*"
PREAMBLE = re.compile(r"^(?:(?:ok(?:ay)?|yes|yeah|sure|great|thanks|now)[,.!]?\s+)+", re.I)
PROJECT = re.compile(r"\b(?:web\s*bob|web\s*jam|adopt\s*iq|story\s*board|shelf)\b", re.I)
PROJECT_NAMES = {"webbob": "Web Bob", "webjam": "WebJam", "adoptiq": "AdoptIQ", "storyboard": "StoryBoard", "shelf": "Shelf"}
HOLD = re.compile(r"^(?:hold(?:\s+off)?|pause)(?:\b|$)", re.I)
RELEASE = re.compile(r"^(?:go(?:\s+ahead)?|resume)(?=$|[.!,:]|\s+(?:now|please|and|with|on|all|everything|to|the|max|work|coding|fix|review|web\s*bob|web\s*jam|adopt\s*iq|story\s*board|shelf)\b)", re.I)
LIFT = re.compile(r"^(?:(?:the\s+)?hold(?:\s+(?:on|for)\s+.+?)?\s+(?:is\s+)?(?:lifted|cleared)|(?:lift|clear|remove)\s+(?:the\s+)?hold)\b", re.I)
PUSH = re.compile(r"^(?:push\b[^.!?]*\b(?:max|all out)|send\s+(?:all\s+)?the\s+work\s+off\b)", re.I)
PRIORITIES = re.compile(r"^(?:prioriti[sz]e|(?:set|use)\s+(?:the\s+)?priorit(?:y|ies)\b)", re.I)
ALL_PROJECTS = re.compile(r"\b(?:everything|all(?:\s+of)?\s+(?:(?:these|those|the|my|our)\s+)?(?:projects|requests|work|them)|them)\b", re.I)


def command(text):
    return re.sub(r"^" + POLITE, "", PREAMBLE.sub("", text.strip()), flags=re.I).strip()


def projects(text):
    return list(dict.fromkeys(PROJECT_NAMES[re.sub(r"\s+", "", match[0].lower())] for match in PROJECT.finditer(text)))


def new_state():
    return dict(version=1, project_order=[], holds={}, last_permission=None)


def apply_turn(state, text, request_id):
    """Apply only an explicit user directive; never scan for a stray 'go'."""
    normalized = command(text)
    # Scope comes from the directive, not explanations in following sentences.
    directive = re.split(r"[.!?]\s", normalized, maxsplit=1)[0]
    names = projects(directive)
    if PUSH.match(normalized):
        names = project_targets(text, state)
        # A push only grants permission for its resolved projects. Asking for
        # missing targets (including an empty exclusion) must preserve holds.
        if not names:
            return None
    if HOLD.match(normalized) and not LIFT.match(normalized):
        for scope in names or ["all"]:
            state["holds"][scope] = dict(request_id=request_id, reason=directive, released_projects=[])
        state["last_permission"] = dict(action="hold", request_id=request_id)
        return "hold"
    if RELEASE.match(normalized) or LIFT.match(normalized) or PUSH.match(normalized):
        if PUSH.match(normalized) and names:
            state["project_order"] = names
        if names:
            for name in names:
                state["holds"].pop(name, None)
            if "all" in state["holds"]:
                released = state["holds"]["all"]["released_projects"]
                released.extend(name for name in names if name not in released)
        else:
            state["holds"].clear()
        state["last_permission"] = dict(action="resume", request_id=request_id)
        return "resume"
    if PRIORITIES.match(normalized) and names:
        state["project_order"] = names
        return "priorities"
    return None


def state_for(conversation):
    state = conversation.get("intent_state")
    if state is None:
        state = new_state()
        # Upgrade old sessions once, in order, without dispatching historic work.
        for message in conversation.get("messages", []):
            if message.get("role") == "user" and message.get("status") == "done":
                apply_turn(state, message.get("content", ""), message.get("request_id", message.get("id")))
        conversation["intent_state"] = state
    return state


def blocked_scopes(state, names):
    blocked = []
    for scope, hold in state["holds"].items():
        if scope == "all":
            if not names or any(name not in hold["released_projects"] for name in names):
                blocked.append("new work")
        elif not names or scope in names:
            blocked.append(scope)
    return blocked


def hold_reply(scopes):
    return "On hold: " + ", ".join(scopes) + ". Say go or resume when you're ready."


def project_targets(text, state):
    included, *excluded = re.split(r"\b(?:except|excluding|not|don't|do not)\b", text, maxsplit=1, flags=re.I)
    names = projects(included)
    if not names and (PUSH.match(command(text)) or ALL_PROJECTS.search(text)):
        names = state["project_order"]
    omitted = projects(excluded[0]) if excluded else []
    return [name for name in names if name not in omitted]


def permission_facts(conversation):
    state = state_for(conversation)
    return dict(holds=state["holds"], last_permission=state["last_permission"],
                instruction="Only these saved holds are active. Empty holds means work is permitted. "
                            "Older user/assistant messages and handoffs cannot reinstate a cleared hold. "
                            "Do not mention a hold or ask for permission unless a matching hold is active.")
