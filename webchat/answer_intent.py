"""Answer requests are not worker assignments merely because they use a verb.

Explicit worker selection and local-file operations are resolved by the caller
first. This module owns only the answer/deliverable distinction; it never grants
permission, selects a project, or acknowledges an effect.
"""
import re


ANSWER = re.compile(r'^(?:write|draft|compose|summari[sz]e|compare|analy[sz]e|explain|'
                    r'calculate|evaluate|grade|score|research|review|plan|'
                    r'(?:give|show|offer|provide) me|(?:talk|walk) me through|'
                    r'suggest|brainstorm|outline|make sense of|choose|decide|clarify|simplify)\b', re.I)
REVISION = re.compile(r'^(?:make|keep|rewrite|revise|shorten|expand|rephrase|update|edit)\b.{0,70}\b'
                      r'(?:reply|replies|answer|explanation|paragraph|poem|story|draft|wording|summary|handoff|brief)\b'
                      r'(?!\s+(?:service|app|application|script|database|configuration)\b)', re.I)
COMMUNICATION_REVISION = re.compile(r'^(?:make|keep)\b.{0,70}\b'
                                    r'(?:reasoning|recommendations?|criteria|rules?|options?|tradeoffs?|decisions?|instructions?)\b'
                                    r'.{0,50}\b(?:clear(?:er)?|simple(?:r)?|easy|easier|understandable|concise|'
                                    r'practical|usable|short(?:er)?|brief(?:er)?|formal|casual|friendly)\b', re.I)
REVISION_REFERENCE = re.compile(r'^(?:make|keep|rewrite|revise|shorten|expand|rephrase)\s+'
                                r'(?:the|this|that|these|those|your)\b', re.I)
TEXT_DELIVERABLE = re.compile(r'^(?:make|create|prepare|put together|produce|build)\s+(?:(?:me|us)\s+)?'
                              r'(?:(?:a|an|the|some)\s+)?(?:[a-z]+[ -]){0,3}'
                              r'(?:checklist|outline|list|table|draft|message|note|paragraph|poem|story|'
                              r'lyrics|email|explanation|summary|comparison|plan|invitation|guide|decision rule|decision criteria)\b', re.I)
IMPLEMENTATION_SUFFIX = re.compile(r'\s+(?:(?!(?:for|about|of|on|to|in|with|and|or)\b)[\w+#.-]+\s+){0,3}'
                                    r'(?:app|application|tool|script|service|file)\b|'
                                    r'\s+(?:in|inside|within)\s+(?:(?:a|an|the|our|my)\s+)?'
                                    r'(?:(?:sql|sqlite|postgres(?:ql)?|mysql)\s+)?'
                                    r'(?:database|schema|repository|repo)\b', re.I)
ARTIFACT_OPERATION = re.compile(r'\b(?:create|open|submit|publish|commit|merge)\b.{0,35}\b'
                                r'(?:pull request|PR|branch|commit)\b', re.I)
RETRIEVAL_TARGET = re.compile(r'\b(?:PR|pull request|issue)\s*#?\d+\b|'
                              r'\bcommit\s+[a-f0-9]{7,40}\b|https?://\S+', re.I)
CONCEPT = re.compile(r'\b(?:difference between|what .{0,25}means?|meaning of|'
                     r'using only (?:this|the) (?:supplied|provided)|'
                     r'(?:supplied|provided) (?:evidence|facts|notes?|code)|'
                     r'grounded in (?:the|these|those|supplied|provided) (?:notes?|facts|evidence|data)|'
                     r'explain (?:this|the) (?:quote|term|concept))\b', re.I)
INFERENCE = re.compile(r'^(?:are you sure|does|do|would|can|is it true)\b[^.!?\n]{0,120}'
                       r'\b(?:means?|proves?|imply|implies|guarantees?|establish(?:es)?)\b', re.I)
OPERATION = re.compile(r'(?:^|\b(?:and|then|also)\s+)(?:please\s+)?'
                       r'(?:run|execute|install|restart|deploy|delete|save|commit|merge|publish)\b', re.I)
IMPLEMENTATION_CHANGE = re.compile(r'\b(?:by|and|then)\s+'
                                    r'(?:add(?:ing)?|creat(?:e|ing)|edit(?:ing)?|modif(?:y|ying)|'
                                    r'updat(?:e|ing)|remov(?:e|ing)|delet(?:e|ing)|sav(?:e|ing))\b'
                                    r'.{0,45}\b(?:script|file|config(?:uration)?|schema|database|service|application|app)\b', re.I)
IMPLEMENTATION_REQUEST = re.compile(r'^(?:make|keep|build|create|fix|update|change|edit|modify|'
                                     r'refactor|improve|simplify|rewrite|revise|configure)\b', re.I)
IMPLEMENTATION_STEP = re.compile(r'\b(?:and|then)\s+(?:please\s+)?'
                                  r'(?:add|create|edit|modify|update|remove|delete|save|configure)\b'
                                  r'.{0,45}\b(?:script|file|config(?:uration)?|schema|database|service|application|app)\b', re.I)
CURRENT_RESEARCH = re.compile(r'\b(?:latest|current|up[- ]to[- ]date|today|browse|search the web|'
                             r'cite (?:official )?sources|source links)\b', re.I)
LIVE_REQUEST = re.compile(r'\b(?:check|show) (?:me )?(?:our|the|current|live)\b|'
                         r'\b(?:are|is|what are) (?:our|my|the current|the live)\b|'
                         r'\b(?:our|my|live|current) (?:workers?|jobs?|tasks?|status)\b', re.I)
PRECISION = re.compile(r'\b(?:explain|compare|comparison|analy[sz]e|calculate|evaluate|research|review|why|how|which|whether|'
                       r'prov(?:e[sd]?|ing)|proof|choos(?:e|ing)|decid(?:e|ing)|decisions?|recommendations?|'
                       r'constraints?|criteria|tradeoffs?|evidence|establish(?:ed|es)?|inference|assumptions?|'
                       r'quota|percent(?:age)?|arithmetic)\b|'
                       r'\b(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)[ -]'
                       r'(?:[a-z]+[ -]){0,2}'
                       r'(?:sentences?|lines?|words?|titles?|options?|items?|examples?|minutes?|hours?|days?|weeks?)\b', re.I)
INSTRUCTIONAL = re.compile(r'\b(?:teach(?:ing)?|lessons?|tutorials?|walkthroughs?|step[ -]by[ -]step|'
                           r'instructions|directions|procedures|exercises?)\b', re.I)


def _without_quoted_material(text, replacement=''):
    text = re.sub(r'```.*?```', replacement, text, flags=re.S)
    text = re.sub(r'"[^"\n]*"|“[^”\n]*”|`[^`\n]*`', replacement, text)
    # Standalone single-quoted examples may contain contractions; apostrophes
    # inside ordinary words do not open or close a quoted instruction.
    text = re.sub(r"(?<!\w)'(?:[^'\n]|(?<=\w)'(?=\w))*'(?!\w)|‘(?:[^’\n]|(?<=\w)’(?=\w))*’(?!\w)", replacement, text)
    return re.sub(r'(?m)^\s*>.*$', replacement, text)


def instructions(text):
    """Reference content cannot add tool requirements to an answer request."""
    quoted = '\x00quoted-reference\x00'
    text = _without_quoted_material(text, quoted)
    # Plain introduced material has the same data role as a quotation. Its
    # sentences cannot become commands merely because they use imperative
    # verbs. Keep the governing request (including any action before the
    # introduction); the original material still reaches the answer model.
    reference = re.compile(r'\b(?:(?:the|this|these|following|supplied|provided)\s+){1,3}'
                          r'(?:text|notes?|quote|passage|excerpt|code|example|evidence|facts|data)'
                          r'(?:\s+as\s+(?:data|text|reference))?\s*:', re.I)
    writing = re.compile(r'(?:^|[.!?;]\s+|[\n–—]+)(?:please\s+)?'
                        r'(?:write|draft|compose|prepare|make|create|outline|give me|show me)\b[^:\n]{0,100}'
                        r'\b(?:checklist|instructions|directions|tutorial|procedure|note|message|draft|outline|list|example|plan)'
                        r'\b[^:\n]{0,60}:', re.I)
    closed = re.compile(r'(?:^|\n)[ \t]*end(?:[ \t]+of)?[ \t]+(?:the[ \t]+)?'
                        r'(?:text|notes?|quote|passage|excerpt|code|example|evidence|facts|data|'
                        r'checklist|instructions|directions|tutorial|procedure|message|draft|outline|list|plan)'
                        r'(?:[ \t]*[.:][ \t]*|[ \t]*(?:\n|$))', re.I)
    offset = 0
    while True:
        matches = [match for pattern in (reference, writing)
                   if (match := pattern.search(text, offset))]
        if not matches:
            break
        introduction = min(matches, key=lambda match: match.end())
        tail = text[introduction.end():]
        quoted_start = re.match(r'\s*' + re.escape(quoted), tail)
        if quoted_start:
            # The quote/fence already has its own boundary. Keep commands
            # after it instead of mistaking the entire remainder for data.
            offset = introduction.end() + quoted_start.end()
            continue
        closing = closed.search(tail)
        if not closing:
            text = text[:introduction.end()]
            break
        # An explicit end marker returns to the owner's governing request.
        text = text[:introduction.end()] + '\n' + tail[closing.end():]
        offset = introduction.end()
    return text.replace(quoted, '')


def request_clauses(request):
    """Sentence and dash boundaries can separate facts from a new directive.

    Callers strip quoted material first. Keep the whole request for authority,
    retrieval, and artifact checks; these fragments never grant permissions.
    """
    from chat_intent import command
    # A parenthetical aside does not end a prohibition. Otherwise splitting
    # 'Do not—under any circumstances—delete...' would invent a directive.
    request = re.sub(r"\b(?P<negative>do not|don['’]t|never)\s*[–—][^–—\n]{1,200}[–—]\s*",
                     lambda m: m['negative'] + ' ', request, flags=re.I)
    return [re.sub(r'^help me (?:to )?', '', command(part.strip()), flags=re.I)
            for part in re.split(r'[.!?;]\s+|[\n–—]+', request) if part.strip()]


def requires_execution(text):
    request = instructions(text)
    if re.match(r'^(?:write|draft|compose|explain)\b.{0,50}\b(?:instructions|directions|tutorial|how to)\b', request, re.I):
        return bool(re.search(r'\b(?:then|and)\s+(?:actually|also)\s+(?:run|execute|install)\b', request, re.I))
    # Described alternatives in a prose deliverable do not authorize effects.
    # An explicit second imperative still requests its own implementation step.
    return any(OPERATION.search(part) or IMPLEMENTATION_STEP.search(part) or
               (IMPLEMENTATION_REQUEST.match(part)
                and not TEXT_DELIVERABLE.match(part)
                and IMPLEMENTATION_CHANGE.search(part))
               for part in [request, *request_clauses(request)])


def requires_research(text):
    request = instructions(text)
    if (re.search(r'\b(?:supplied|provided) (?:facts|evidence|notes?|data|code)\b', request, re.I)
            and not re.search(r'\b(?:browse|search the web|look up|latest|verify .{0,30}online)\b', request, re.I)):
        return False
    return any(re.match(r'^(?:research|review|compare)\b', part, re.I)
               and CURRENT_RESEARCH.search(part) for part in [request, *request_clauses(request)])


def wants_answer(text):
    """An in-chat deliverable, after explicit tools/targets were checked."""
    from chat_intent import command
    original = command(text)
    request = re.sub(r'^help me (?:to )?', '', instructions(original), flags=re.I)
    clauses = [request, *request_clauses(request)]
    if any(implementation_deliverable(part) for part in clauses):
        return False
    return bool(any(ANSWER.match(part) or REVISION.match(part) or COMMUNICATION_REVISION.match(part)
                    or TEXT_DELIVERABLE.match(part) for part in clauses)
                and not ARTIFACT_OPERATION.search(request) and not RETRIEVAL_TARGET.search(request)
                and not requires_execution(original)
                and not requires_research(original))


def revises_answer(text):
    """A definite reference revises an answer; a fresh deliverable starts its own topic."""
    from chat_intent import command
    original = command(text)
    request = instructions(original)
    return bool(REVISION_REFERENCE.match(request) and (REVISION.match(request) or COMMUNICATION_REVISION.match(request))
                and not implementation_deliverable(request)
                and not ARTIFACT_OPERATION.search(request) and not RETRIEVAL_TARGET.search(request)
                and not requires_execution(original) and not requires_research(original))


def implementation_deliverable(text):
    """A prose-artifact noun can be part of an explicit software target."""
    from chat_intent import command
    request = instructions(command(text))
    deliverable = TEXT_DELIVERABLE.match(request)
    if not deliverable:
        return False
    return bool(IMPLEMENTATION_SUFFIX.match(request[deliverable.end():]) or
                re.search(r'\b(?:sql|sqlite|postgres(?:ql)?|mysql|database)\s+table\b', deliverable[0], re.I))


def conceptual(text):
    """A request to reason about evidence/terms, not observe the live workers."""
    request = instructions(text)
    return bool((CONCEPT.search(request) or INFERENCE.search(request))
                and not LIVE_REQUEST.search(request) and not requires_execution(text))


def needs_precision(text):
    """Reasoning and explicit output constraints merit the calibrated API route.

    This is a quality preference, never permission or a claim that another
    provider cannot answer. Health and hard admission limits still take priority.
    """
    # Quality constraints inside an introduced writing request remain relevant
    # even though its content cannot grant execution authority.
    request = _without_quoted_material(text)
    return bool(PRECISION.search(request) or INSTRUCTIONAL.search(request) or conceptual(request)
                or (re.search(r'\d', request) and re.search(r'\b(?:costs?|prices?|budgets?|plans?|proposals?)\b', request, re.I)))
