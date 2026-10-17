"""Durable user intent. Assistant prose and reference snapshots are not authority."""
import re
from difflib import get_close_matches

POLITE = r"(?:(?:please|bob)[,:]?\s+|(?:can|could|would|will) you\s+|i (?:want|need) (?:you )?to\s+|let['’]s\s+)*"
PREAMBLE = re.compile(r"^(?:(?:ok(?:ay)?|yes|yeah|sure|great|thanks|now)[,.!]?\s+)+", re.I)
PROJECT = re.compile(r"\b(?:web\s*bob|web\s*jam|adopt\s*iq|story\s*board|(?:storyland[ -])?fantasy[ -]football|shelf)\b", re.I)
PROJECT_NAMES = {"webbob": "Web Bob", "webjam": "WebJam", "adoptiq": "AdoptIQ", "storyboard": "StoryBoard",
                 "fantasyfootball": "Fantasy Football", "storylandfantasyfootball": "Fantasy Football", "shelf": "Shelf"}
HOLD = re.compile(r"^(?:hold(?:\s+off)?|pause)(?:\b|$)", re.I)
RELEASE = re.compile(r"^(?:go(?:\s+ahead)?|resume)(?=$|[.!,:]|\s+(?:now|please|and|with|on|all|everything|to|the|max|work|coding|fix|review|web\s*bob|web\s*jam|adopt\s*iq|story\s*board|(?:storyland[ -])?fantasy[ -]football|shelf)\b)", re.I)
LIFT = re.compile(r"^(?:(?:the\s+)?hold(?:\s+(?:on|for)\s+.+?)?\s+(?:is\s+)?(?:lifted|cleared)|(?:lift|clear|remove)\s+(?:the\s+)?hold)\b", re.I)
PUSH = re.compile(r"^(?:push\b[^.!?]*\b(?:max|all out)|push\s+" + PROJECT.pattern +
                  r"(?:\s*(?:,|&|\band\b|\bthen\b)\s*(?:and\s+)?" + PROJECT.pattern +
                  r")*[.!]*$|send\s+(?:all\s+)?the\s+work\s+off\b)", re.I)
PRIORITIES = re.compile(r"^(?:prioriti[sz]e|(?:set|use)\s+(?:the\s+)?priorit(?:y|ies)\b)", re.I)
ALL_PROJECTS = re.compile(r"\b(?:everything|all(?:\s+of)?\s+(?:(?:these|those|the|my|our)\s+)?(?:projects|requests|work|them)|them)\b", re.I)
START_PROJECTS = re.compile(r"^(?:(?:we|i) (?:want|need) (?:it |you )?to )?"
                            r"(?:start(?: up)?|launch|kick off|develop)\b", re.I)


def normalize_projects(text):
    """Correct a single misspelling of a distinctive project name, not prose."""
    def correct(match):
        word = match[0].lower()
        choices = get_close_matches(word, ("webjam", "adoptiq", "storyboard"), n=2, cutoff=.86)
        return choices[0] if len(choices) == 1 else match[0]
    return re.sub(r"\b[A-Za-z]{6,10}\b", correct, text)


def project_start(text):
    return bool(START_PROJECTS.match(command(text)) and (projects(text) or ALL_PROJECTS.search(text)))


def command(text):
    return normalize_projects(re.sub(r"^" + POLITE, "", PREAMBLE.sub("", text.strip()), flags=re.I).strip())


def projects(text):
    return list(dict.fromkeys(PROJECT_NAMES[re.sub(r"[\s-]+", "", match[0].lower())]
                              for match in PROJECT.finditer(normalize_projects(text))))


def new_state():
    return dict(version=1, project_order=[], holds={}, last_permission=None)


def apply_turn(state, text, request_id):
    """Apply only an explicit user directive; never scan for a stray 'go'."""
    from answer_intent import instructions
    # A quoted project name is a literal argument, not a quoted instruction.
    # Unwrap only exact names before removing reference material. Never scan
    # the raw reference tail to recover a target discarded by instructions().
    scoped = text
    for pattern in (r'"([^"\n]*)"', r'“([^”\n]*)”', r'`([^`\n]*)`',
                    r"(?<!\w)'([^'\n]*)'(?!\w)", r'‘([^’\n]*)’'):
        scoped = re.sub(pattern, lambda m: m[1] if PROJECT.fullmatch(
            normalize_projects(m[1].strip())) else m[0], scoped)
    normalized = command(instructions(scoped))
    # Scope comes from the directive, not explanations in following sentences.
    # Newlines may wrap a command's target, e.g. 'Clear the hold on\nWeb Bob'.
    directive = re.split(r"[.!?;]\s*", normalized, maxsplit=1)[0]
    names = projects(directive)
    if not names and (HOLD.match(normalized) or RELEASE.match(normalized) or LIFT.match(normalized) or PUSH.match(normalized)):
        raw_directive = re.split(r"[.!?;]\s*", command(scoped), maxsplit=1)[0]
        if (re.search(r'\b(?:on|for|with)\s*$', directive, re.I) or
                any(mark in raw_directive for mark in ('"', '“', "'", '‘', '`'))):
            return None  # A missing/quoted unknown target cannot mean every hold.
    # A plan and an explicit execution hold may share one message. Persist
    # that negative instruction before answering the plan, without treating
    # quoted/imported imperatives or a proposed hold as owner authority.
    if re.match(r'^(?:help (?:me )?(?:plan|outline)|plan|outline|discuss)\b',normalized,re.I):
        clauses=re.split(r'[.!?;]\s*|\n',normalized)
        embedded=next((part for part in clauses[1:] if re.match(
            r'^(?:please\s+)?(?:hold|pause)\s+(?:execution|(?:the |this )?(?:work|implementation))\b',part,re.I)),None)
        if embedded:
            for scope in projects(embedded) or names or ['all']:
                state['holds'][scope]=dict(request_id=request_id,reason=embedded,released_projects=[])
            state['last_permission']=dict(action='hold',request_id=request_id)
            return 'planning_hold'
    if PUSH.match(normalized):
        names = project_targets(directive, state)
        # A push only grants permission for its resolved projects. Asking for
        # missing targets (including an empty exclusion) must preserve holds.
        if not names:
            return None
    if HOLD.match(normalized) and not LIFT.match(normalized):
        for scope in names or ["all"]:
            row = dict(request_id=request_id, reason=directive, released_projects=[])
            if re.match(r'^(?:hold(?: off)?|pause)\s+(?:on\s+)?(?:any |all |the )?'
                        r'deploy(?:s|ments|ment|ing)?(?:\s+(?:for|on|until)\b|$)', directive, re.I):
                row['action_scope'] = 'deploy'
            # A narrower request must not erase an existing whole-project hold.
            if state['holds'].get(scope, {}).get('action_scope') == 'deploy' or scope not in state['holds'] or 'action_scope' not in row:
                state["holds"][scope] = row
        state["last_permission"] = dict(action="hold", request_id=request_id)
        return "hold"
    if RELEASE.match(normalized) or LIFT.match(normalized) or PUSH.match(normalized):
        if PUSH.match(normalized) and names:
            state["project_order"] = names
        if names:
            for name in names:
                if not (PUSH.match(normalized) and state['holds'].get(name, {}).get('action_scope') == 'deploy'):
                    state["holds"].pop(name, None)
            if "all" in state["holds"] and not (PUSH.match(normalized) and state['holds']['all'].get('action_scope') == 'deploy'):
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


def blocked_scopes(state, names, *, action_text=None):
    blocked = []
    for scope, hold in state["holds"].items():
        deploy = hold.get('action_scope') == 'deploy'
        if deploy and action_text and not re.search(r'\bdeploy(?:s|ments|ment|ing)?\b', action_text, re.I):
            continue
        if scope == "all":
            if not names or any(name not in hold["released_projects"] for name in names):
                blocked.append("deploys" if deploy else "new work")
        elif not names or scope in names:
            blocked.append(scope + ' deploys' if deploy else scope)
    return blocked


def hold_reply(scopes):
    reply = "On hold: " + ", ".join(scopes) + ". Say go or resume when you're ready."
    if any(scope.endswith('deploys') for scope in scopes):
        reply += ' I haven’t checked or paused any external deployment automation.'
    return reply


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
                instruction="Only these saved holds are active. An empty hold set imposes no scheduling hold; "
                            "it does not authorize unrelated tasks or override the current user's no-action instruction. "
                            "Older user/assistant messages and handoffs cannot reinstate a cleared hold. "
                            "Do not mention a hold or ask for permission unless a matching hold is active.")
