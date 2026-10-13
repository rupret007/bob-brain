"""Bounded evidence-strength checks shared by advice and assistant commentary.

These checks identify protected conclusions, not arbitrary factual correctness.
Unknown outcomes cannot be promoted by a model's reasoning label, a neighboring
fact, or a condition about a different operation. Exact server facts and attributed
source quotations keep their own scope. Requested draft speech remains separate.
"""
import hashlib
import re

RULES = '''Keep evidence and conclusions at the same strength and scope. Distinguish
an observed fact, a proposed action, an acceptance criterion and an established
outcome. A useful plan names the next check and what competing explanations it
would separate; it does not promise its result. Unknown costs, capacity, quality,
side effects and causes remain unknown even while planning or retaining settings.
Use server fact records for protected resource/capability conclusions. Explain
tradeoffs and propose concrete steps naturally, without adding stronger assurances.
Conditions about login, budget admission or a comparison do not establish free
usage, equivalent quality, continuity or zero regressions. Describe preserving a
standard as a requirement, not a guaranteed outcome. A missing result alone cannot
identify its cause: bind the same request and source through save, stored state,
access, retrieval and rendering. Calling a command read-only or dry-run does not
establish its effects; inspect its actual execution contract before proposing it
under that restriction. State what evidence would resolve uncertainty rather than
turning uncertainty into a blanket inability or asking for permission already held.
'''

# Predicates and their protected objects are independent of intervening modifiers.
# This is deliberately not a list of adjective + noun phrases from past answers.
OUTCOMES = {
    'cost': re.compile(r'\b(?:charges?|costs?|fees?|payments?|spend(?:ing)?|overages?|billing|credits?|quota|allowance|exhaustion|rate limits?)\b', re.I),
    'quality': re.compile(r'\b(?:quality|continuity|regressions?|degradation|degraded responses|equivalent answers)\b', re.I),
}
ASSURANCE = re.compile(r"\b(?:without|no|zero|free|risk[- ]free|guarantee\w*|ensure\w*|"
                       r"prevent\w*|eliminat\w*|protect\w*|preserv\w*|maintain\w*|avoid\w*|"
                       r"guard\w*|unchanged|equal|equivalent|(?:will|can|could|does|do) not|won['’]t|cannot|can['’]t)\b", re.I)
CLAUSE = re.compile(r'[^.!?;\n]+(?:[.!?;]|(?=\n)|$)')
CONTRAST = re.compile(r',|\b(?:and|but|however|yet|therefore|thus|so|because|since)\b', re.I)
TECHNICAL = re.compile(r'\b(?:Web Bob|Codex|Claude|Cursor|Gemini|MiniMax|API|generation|invocations?|'
                       r'test(?:ing|s)?|suites?|texting|deploy\w*|routing|providers?|models?|workers?)\b', re.I)
MODE = re.compile(r'\b(?:read[- ]only|dry[- ]run|side[- ]effect[- ]free)\b', re.I)
TEST = re.compile(r'\b(?:tests?|testing|suites?|commands?|executables?|scripts?)\b', re.I)
ABSENCE = re.compile(r'\b(?:empty|missing|404|not found|no (?:result|record|response|data)|never stored)\b', re.I)
CAUSE = re.compile(r'\b(?:proves?|establish\w*|confirm\w*|demonstrat\w*|means?|proof (?:of|that)|points? to)\b', re.I)
PERSISTENCE = re.compile(r'\b(?:persistence|persisted|backend|API failure|storage failure|never (?:saved|stored)|data loss)\b', re.I)
EVIDENCE_OBJECT = re.compile(r'\b(?:data|evidence|records?|settings?|configuration|information|documentation|'
                             r'controls?|criteria|changes?|questions?|decisions?|permissions?|approval|proof|measurements?)\b', re.I)
# Copular conclusions are assurances too: an outcome can be asserted intact
# without using a verb such as "preserve". Bind the outcome as subject, not as
# an attributive modifier in "quality records remain intact".
STATE = re.compile(r'\b(?P<link>is|are|was|were|be|been|being|remain(?:s|ed)?|stay(?:s|ed)?)\s+'
                   r'(?:(?:\w+ly|still|not)\s+)*(?P<state>intact|unaffected|unbroken|stable|'
                   r'unchanged|equal|equivalent|protected|preserved|maintained)\b',re.I)
STATE_BRIDGE = re.compile(r'^\s*(?:(?:\w+ly|still|not|never|am|is|are|was|were|be|been|being|'
    r'has|have|had|can|cannot|could|will|would|may|might|must|should|need|needs|to|'
    r'known|proven|shown|established|verified|required)\s+)*$',re.I)


def state_predicates(text, objects):
    for match in STATE.finditer(text):
        for subject in objects.finditer(text[:match.start()]):
            bridge = text[subject.end():match.start()]
            # Only grammatical links may follow the protected subject. Other
            # noun heads (records/criteria/etc.) describe a different object.
            if not STATE_BRIDGE.fullmatch(bridge):
                continue
            before = text[:subject.start()]
            if re.search(r'\b(?:records?|data|evidence|criteria|settings?|measurements?)\s+of\s*$',before,re.I):
                continue
            yield match
            break


def operation_mode(text, mode):
    """Bind a mode to an executable head, not any nearby test mention."""
    prefix, suffix = text[:mode.start()], text[mode.end():]
    bridge=re.compile(r'^\s*(?:(?:\w+ly|still|not|am|is|are|was|were|be|been|being|'
        r'remains?|stays?|has|have|had|can|cannot|could|will|would|may|might|must|should|'
        r'need|needs|to|known|proven|shown|established|verified|required|guaranteed|'
        r'described|considered|runs?|run|executed|operates?|in|as)\s+)+$',re.I)
    for subject in TEST.finditer(prefix):
        if bridge.fullmatch(prefix[subject.end():]):
            return True
    # Attributive mode: the last noun before a relation/predicate is its head.
    phrase = re.split(r'[.,;:!?()|]|\b(?:of|for|about|with|from|in|on|to|and|or|'
                      r'is|are|was|were|has|have|will|can|remains?)\b',suffix,maxsplit=1,flags=re.I)[0]
    words = re.findall(r'[\w-]+',phrase)
    if words and words[-1].lower() not in ('mode','operation','execution'):
        return bool(TEST.fullmatch(words[-1]))
    # Copular/adverbial mode: bind the predicate's subject or imperative object.
    return False
OBJECT_BOUNDARY = re.compile(r'\b(?:about|above|across|after|against|along|among|around|as|at|before|behind|below|'
    r'beneath|beside|between|beyond|by|despite|during|except|for|from|in|inside|into|near|of|off|on|onto|out|outside|'
    r'over|past|per|since|through|throughout|to|toward|under|until|upon|via|with|within|when|while|because|using|or|that|which|where|if)\b', re.I)
IMPERATIVE = re.compile(r'^\s*(?:[-*]\s*|\d+[.)]\s*)?(?:compare|check|inspect|prepare|require|preserve|protect|maintain|keep|record|verify)\b', re.I)
METHOD_OBJECT = re.compile(r'\b(?:bias|rushing|omission|drift|skew|overreach)\b', re.I)
REJECTED_NOMINAL = re.compile(
    r'\b(?:rejecting|denying|refusing|declining|withdraw(?:ing)?)\b[^.!?]{0,48}\b(?:guarantees?|promises?|assurances?)\b', re.I)
EPISTEMIC_WITHOUT = re.compile(
    r'^\s*(?:establishing|preserving|assuming|claiming|promising|proving|inventing|fabricating|introducing)\b',
    re.I)
QUALIFICATIONS = {
    'cost': 'The cost or capacity outcome is unverified from what’s available here. Check the actual route, allowance and billing controls before admitting generation.',
    'quality': 'The quality or continuity outcome is unverified from what’s available here.',
    'operation_mode': 'That execution mode is unverified from what’s available here. Inspect the exact command’s writes, network access and isolation contract before treating a test run as read-only.',
    'diagnostic_cause': 'A missing result does not identify its cause from what’s available here. Match the request and source across save, stored state, access, retrieval and rendering.',
    'operational_state': "I can’t confirm live queue, task, or process state from what’s available here.",
    'lifecycle_absence': 'External execution, inspection, verification and dispatch remain unverified without supporting evidence; missing receipts do not prove they never occurred.',
}
LIFECYCLE_ABSENCE = re.compile(
    r'\b(?:execution|inspection|verification|dispatch)\s+'
    r'(?:(?:is|was|remains?|still)\s+)*'
    r'(?P<predicate>unexecuted|not\s+(?:performed|completed)|has\s+not\s+started|was\s+not\s+issued)\b', re.I)
# Global inventory and process-status overclaims. Conversation-scoped denials
# such as "no task was started" are a different, permitted effect boundary.
QUEUE_INVENTORY = re.compile(
    r'\b(?:no|zero|without)\s+(?:active\s+)?(?:tasks?|jobs?)(?:\s+or\s+pending\s+assignments?)?\s+'
    r'(?:currently\s+)?(?:queued|in progress)\b|'
    r'\b(?:zero|no)\s+(?:pending assignments?|completed effects?)\b|'
    r'\b(?:active tasks?|pending assignments?|completed effects?)\s+'
    r'(?:remain(?:s|ed)?|are|is)\s+(?:at\s+)?zero\b',
    re.I)
CONVO_SCOPED = re.compile(
    r"\b(?:this conversation|this chat|this turn|this reply|I haven['’]t|no task was started)\b", re.I)
PROCESS_STATE = re.compile(
    r'\b(?:currently\s+)?not running\b|'
    r'\b(?:confirmed|confirms?|verified)\s+(?:the\s+)?(?:running\s+)?(?:source\s+)?(?:code\s+)?SHA\b|'
    r'\bthe SHA confirms\b',
    re.I)
MARKDOWN_LINK = re.compile(r'\[([^\]]+)\]\((https?://[^)\s]+)\)', re.I)
BARE_URL = re.compile(r'(?<!\()https?://[^\s)<>\]]+', re.I)
JOURNAL_CURSOR = re.compile(
    r'(?:,\s*)?(?:(?:the|its)\s+)?(?:coordination\s+)?'
    r'journal(?:[_\s]+)cursor\b(?:\s*(?:,|:|\bis\b|\bat\b|\bcurrently at\b)[^.!?\n]{0,48})?\s*\d+(?:\s*/\s*\d+)*|'
    r'\bjournal_cursor\s*[:=]\s*\d+\b|'
    r'\bcursor\s+\d+(?:\s*/\s*\d+)+\b',
    re.I)
PATH_THEN_OBSERVED_EPOCH = re.compile(
    r'`?(?:conductor/[\w./-]+\.(?:json|jsonl)|[\w./-]*projects\.json)`?'
    r'\s*\(?\s*(?:observed(?:\s+(?:timestamp|at)|[ _]?at)\s*[:=]?\s*)[`\'"]?\d{9,12}(?:\.\d+)?[`\'"]?\s*\)?',
    re.I)
OBSERVED_EPOCH_THEN_PATH = re.compile(
    r'(?:observed(?:\s+(?:timestamp|at)|[ _]?at)\s*[:=]?\s*)[`\'"]?\d{9,12}(?:\.\d+)?[`\'"]?'
    r'(?:\s+(?:for|in|of|at|from)\s+)'
    r'`?(?:conductor/[\w./-]+\.(?:json|jsonl)|[\w./-]*projects\.json)`?',
    re.I)
BARE_OBSERVED_EPOCH = re.compile(
    r'(?:observed(?:\s+(?:timestamp|at)|[ _]?at)\s*[:=]?\s*)[`\'"]?\d{9,12}(?:\.\d+)?[`\'"]?',
    re.I)
SAVED_RECORD_PHRASE = 'the saved project record loaded with this chat (as of the saved record)'
EMPTY_LABEL = re.compile(
    r'^(?:#{1,6}\s+)?(?:\d+[.)]\s+|[-*+]\s+)?(?:\*\*[^*\n]{1,80}\*\*|__[^_\n]{1,80}__):(?:\*\*|__)?\s*$')
HEADING_LABEL = re.compile(
    r'^(?:#{1,6}\s+)?(?:\d+[.)]\s+|[-*+]\s+)?(?P<label>[A-Z0-9][A-Za-z0-9/&\' ]{0,60}):(?:\*\*|__)?\s*$')
ITEM_START = re.compile(r'^(?:#{1,6}\s+|\d+[.)]\s+|[-*+]\s+)')
COUNT_WORDS = {
    'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
    'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
}
WORD_FOR = {value: word for word, value in COUNT_WORDS.items()}
COUNT_LEADIN = re.compile(
    r'\b(?P<verb>take|list|need|require|recommend|perform|complete|include)\s+'
    r'(?P<count>one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+'
    r'(?P<noun>(?:preparatory\s+)?(?:actions?|steps?|items?|checks?))\s*:'
    r'(?P<ws>\s*)(?P<body>(?:\d+[.)][^\n]*(?:\n|$))+)',
    re.I)
ALREADY_STATED = re.compile(
    r"\b(?:unverified|not verified|not evaluated|not established|not guaranteed|"
    r"cannot guarantee|can['’]t guarantee|unknown|"
    r"have not been (?:evaluated|verified|checked|established|measured))\b",
    re.I)


def is_empty_label(stripped):
    """True for orphan headings/list labels, not colon-ended intro sentences."""
    if not stripped:
        return False
    if EMPTY_LABEL.match(stripped):
        return True
    core = re.sub(r'[*_`]', '', stripped).strip()
    core = re.sub(r'^(?:#{1,6}\s+|\d+[.)]\s+|[-*+]\s+)', '', core).strip()
    match = re.fullmatch(r'([^:]{1,80}):\s*', core)
    if not match:
        return False
    label = match[1].strip()
    if not label or ',' in label or ';' in label:
        return False
    if re.search(r'\b(?:here|this|that|following|below)\b', label, re.I) and re.search(
            r'\b(?:is|are|was|were)\b', label, re.I):
        return False
    from claim_scope import FINITE
    return bool(re.match(r'^[A-Z0-9]', label)) and not FINITE.search(label)


def _plain(text):
    return re.sub(r'[*_`]', '', text)


def _criteria_label(label):
    text = _plain(label or '').strip()
    return bool(re.match(
        r'(?i)(?:\d+[.)]\s*)?(?:acceptance criteria|acceptance criterion|pass|fail)\s*$', text))


def _nonasserted(prefix, predicate, clause, *, sentence_start=False, label=''):
    from assertion_scope import nonasserted
    prefix = _plain(prefix)
    scoped_predicate = predicate + ' ' if predicate.lower() in ('preserve', 'protect', 'maintain') else predicate
    if nonasserted(prefix, scoped_predicate, sentence_start=sentence_start):
        return True
    if _criteria_label(label):
        return True
    if re.match(r'(?i)^\s*(?:acceptance criteria|acceptance criterion|pass|fail)\s*:', _plain(clause)):
        return True
    if (sentence_start and not prefix.strip() and predicate.lower() in ('preserving', 'protecting', 'maintaining')
            and re.match(r'^\w+\s+[^.!?;:]{1,60}:', _plain(clause).strip())):
        return True
    # A goal or check is not an assertion that its desired result is established.
    # An appended independent clause gets a new prefix in violations().
    if re.search(r'\b(?:require|aim for|target|acceptance criterion|acceptance criteria|goal|objective)\s*:?\s*$', prefix, re.I):
        return True
    if re.search(r'\b(?:pass|fail)\s*:\s*$', prefix, re.I):
        return True
    if re.search(r'\b(?:may|might|could)\s+(?:(?:help|partly|potentially)\s+)?$', prefix, re.I):
        return True
    if re.search(r'\b(?:should|must|need to)\s*$', prefix, re.I) and not re.search(r'\b(?:guarantee|ensure)\w*\b', prefix, re.I):
        return True
    if re.search(r"\b(?:not|never|cannot|can['’]t|does not|doesn['’]t)\s+(?:(?:assume|promise|establish|prove|mean|imply|guarantee)\s+)(?:that\s+)?[^,;.!?]{0,100}$", prefix, re.I):
        return True
    if clause.rstrip().endswith('?') and re.match(r'\s*(?:[-*]\s*)?(?:can|could|does|do|is|are|whether|how|what)\b', _plain(clause), re.I):
        return True
    return False


def _quoted_source(text, source):
    """Mask only the exact attributed source words, never adjacent assertions."""
    def mask(match):
        words = match[1]
        prefix = text[max(0,match.start()-90):match.start()]
        suffix = text[match.end():match.end()+70]
        attributed = re.search(r'\b(?:claim|phrase|statement|promise|quote|wording|said|wrote|claims|says)\s*:?\s*$', prefix, re.I)
        # A neutral-looking attribution does not negate an endorsement. Mask a
        # protected source quote only when this local statement disclaims it.
        denied_before = re.search(r"\b(?:cannot|can['’]t|do not)\s+(?:confirm|verify|substantiate|accept)\s+(?:the\s+)?(?:claim|statement|promise)\s*$", prefix, re.I)
        denied_after = re.match(r'\s*(?:(?:is|was|remains)\s+(?:unsupported|unverified|not (?:proven|verified|established|supported))\b|lacks?\s+(?:evidence|support)\b)', suffix, re.I)
        return ' ' * len(match[0]) if words and words in source and attributed and (denied_before or denied_after) else match[0]
    return re.sub(r'["“]([^"”\n]+)["”]', mask, text)


def _assurance_head(clause, predicate):
    tail = clause[predicate.end():]
    return re.split(r'\b(?:without|before|unless|until|while|if|when|once)\b|[,;]', tail, maxsplit=1, flags=re.I)[0]


def _assurance_governs_outcome(clause, predicate, objects):
    head = _assurance_head(clause, predicate)
    if objects.search(head):
        return True
    if re.search(r'\b(?:is|are|was|were|remains?|stays?|will be)\s*$', clause[:predicate.start()], re.I):
        return bool(objects.search(clause[predicate.end():]))
    return False


def _rejected_nominal_assurance(clause, predicate):
    if predicate[0].lower() not in ('guarantee', 'guarantees', 'promise', 'promises'):
        return False
    return bool(REJECTED_NOMINAL.search(clause[:predicate.end()]))


def contradictory_exclusions(content):
    """Withhold an exclusion list contradicting its adjacent alternative list.

    Exact cause names only: no inference that related causes are equivalent,
    and no propagation across diagnostic branch boundaries.
    """
    from reported_records import presentation
    pending = None
    offset = 0
    for line in content.splitlines(keepends=True):
        label, body = presentation(line)
        names = {re.sub(r'\s+', ' ', name).strip(' .').casefold()
                 for name in re.split(r'[,;]', body) if name.strip(' .\n')}
        if label.strip().casefold() == 'rules out':
            pending = (offset, offset+len(line), names)
        elif line.strip():
            if (pending and label.strip().casefold() == 'still-possible alternatives'
                    and pending[2] & names):
                start, end, _ = pending
                yield dict(start=start, end=end, categories=['diagnostic_exclusion'], claims=[],
                           sha256=hashlib.sha256(content[start:end].encode()).hexdigest(),
                           reason='contradictory_diagnostic_exclusion')
            pending = None
        offset += len(line)


def violations(content, *, source='', trusted_facts=(), artifact=False):
    from claim_scope import clauses, disposition, DIRECTIVE
    findings = list(contradictory_exclusions(content)) if not artifact else []
    trusted = {_plain(value).strip() for value in trusted_facts}
    quoted = _quoted_source(content, source)
    technical_artifact = bool(TECHNICAL.search(content + '\n' + source))
    for part in clauses(quoted):
        original = content[part.start:part.end]
        if _plain(original).strip() in trusted:
            continue
        text = part.text
        if artifact and not technical_artifact:
            continue
        categories = set()
        claims = []
        for clause in (text,):
            criteria_clause = _criteria_label(part.label) or re.match(
                r'(?i)^\s*(?:acceptance criteria|acceptance criterion|pass|fail)\s*:', _plain(clause))
            for kind, objects in OUTCOMES.items():
                if criteria_clause:
                    continue
                targets = list(objects.finditer(clause))
                labelled = bool(objects.search(part.label))
                if not targets and not labelled:
                    continue
                states = list(state_predicates(clause, objects))
                for predicate in states:
                    start, end = predicate.span('state')
                    if not disposition(part, start, end, predicate['state'], copular=True):
                        categories.add(kind)
                        claims.append(dict(start=part.start+start,end=part.start+end,
                                           category=kind,disposition='asserted_without_support'))
                for predicate in ASSURANCE.finditer(clause):
                    tail = clause[predicate.end():]
                    # Keeping a standard is a requirement, not a claim that
                    # the route meets it. Bind the noun head, not its modifier.
                    standard = re.match(r'\s+(?:(?:the|our|your|existing|current|answer)\s+)*'
                                        r'quality\s+(?:bar|standards?|requirements?)\b', tail, re.I)
                    proposed = DIRECTIVE.match(clause) or re.search(
                        r'\b(?:recommendation|next step|plan)\s+is\s+to\b', clause[:predicate.start()], re.I)
                    if (kind == 'quality' and proposed and standard
                            and re.fullmatch(r'(?:preserv(?:e|ing)|(?:maintain|protect)(?:ing)?)', predicate[0], re.I)
                            and not objects.search(tail[standard.end():])):
                        continue
                    # Acquisition is a different operation from metered use.
                    negative = predicate[0].lower() in ('no', 'cannot', "can't", 'can’t', 'does not', 'do not', 'will not', "won't", 'won’t')
                    if negative and re.match(r'\s+(?:evidence|proof|basis|mean|imply|establish|prove|guarantee|promise|assume|prevent|protect|preserve|maintain|avoid|guard|ensure|eliminate|rely|depend|count)\b', tail, re.I):
                        continue
                    if (predicate[0].lower() in ('prevent', 'prevents', 'avoid', 'avoids', 'preventing', 'avoiding')
                            and re.search(r'\b(?:set|ensure|check|inspect|verify|require|prepare)\b.{0,80}\bto\s+$',
                                          clause[:predicate.start()], re.I)):
                        continue
                    if (predicate[0].lower() == 'without'
                            and re.match(r'^\s*(?:[-*+]\s+|\d+[.)]\s+)?(?:(?:we|you)\s+(?:should|must|need to)\s+)?'
                                         r'(?:check|inspect|verify|confirm|prepare|require)\b', clause, re.I)
                            and re.search(r'\bto\s+(?:confirm|verify|check|ensure|establish)\b',
                                          clause[:predicate.start()], re.I)):
                        continue
                    if re.search(r'\b(?:not that|not because)\b', clause[:predicate.start()], re.I):
                        continue
                    if (predicate[0].lower() in ('preserving', 'protecting', 'maintaining', 'preserve', 'protect', 'maintain')
                            and kind in ('quality', 'cost')):
                        rest = clause[predicate.start():]
                        if re.search(r'\b(?:is|as)\s+(?:(?:a|an)\s+)?(?:testing|acceptance|quality)\s+requirement\b', rest, re.I):
                            continue
                        not_outcome = re.search(
                            r'\bnot (?:(?:an?)\s+)?(?:inherent|guaranteed|established)\s+outcomes?\b', rest, re.I)
                        if not_outcome:
                            continue
                        requirement = re.search(
                            r'\b(?:remain|remains|are)\s+(?:(?:a|an)\s+)?'
                            r'(?:(?:testing|acceptance|quality|planning)\s+)?requirements?\b', rest, re.I)
                        if requirement and re.search(r'\bnot (?:(?:an?)\s+)?guaranteed\b', rest, re.I):
                            continue
                    if predicate[0].lower() == 'without' and EPISTEMIC_WITHOUT.match(tail):
                        continue
                    if re.search(r'\bwithout\s+$', clause[:predicate.start()], re.I):
                        continue
                    if (predicate[0].lower() in ('prevent', 'prevents', 'avoid', 'avoids', 'preventing', 'avoiding')
                            and METHOD_OBJECT.search(_assurance_head(clause, predicate))
                            and not objects.search(_assurance_head(clause, predicate))):
                        continue
                    if _rejected_nominal_assurance(clause, predicate):
                        continue
                    if re.search(r'\bwithout\s+(?:establishing|preserving|assuming|claiming|promising)\s+', clause[:predicate.start()], re.I):
                        continue
                    if (predicate[0].lower() in ('equal', 'equivalent') and re.search(
                            r'\b(?:establishing|preserving|assuming|claiming|promising)\s+', clause[:predicate.start()], re.I)):
                        continue
                    if (predicate[0].lower() == 'without' and re.match(r'\s+(?:purchasing|buying)\b', tail, re.I)
                            and not re.search(r'\b(?:or|and)\b', tail, re.I)):
                        continue
                    object_head = OBJECT_BOUNDARY.split(tail, maxsplit=1)[0]
                    evidence_head = EVIDENCE_OBJECT.search(object_head)
                    if (predicate[0].lower() in ('without', 'no', 'zero') and evidence_head
                            and not objects.search(object_head[evidence_head.end():])):
                        # Configuration/evidence availability is a different
                        # object from charges or a guaranteed performance outcome.
                        continue
                    copular = any(p.span('state') == predicate.span() for p in states)
                    if disposition(part, predicate.start(), predicate.end(), predicate[0], copular=copular):
                        continue
                    # A rubric label such as "Reasoning Quality" is not itself an
                    # outcome assertion. The body must still govern a protected object
                    # or use a positive assurance verb.
                    positive = predicate[0].lower() in (
                        'guarantee', 'guarantees', 'ensure', 'ensures', 'preserve', 'preserves',
                        'protect', 'protects', 'maintain', 'maintains', 'equivalent', 'equal',
                        'unchanged', 'zero', 'free', 'no')
                    labelled_outcome = labelled and (objects.search(clause) or positive)
                    # A predicate must govern an outcome in this clause. A cost
                    # noun before "without buying" cannot change that operation.
                    if labelled_outcome or _assurance_governs_outcome(clause, predicate, objects) or re.search(
                            r'\b(?:is|are|stays?|remains?|will be)\s*$', clause[:predicate.start()], re.I):
                        categories.add(kind)
                        claims.append(dict(start=part.start+predicate.start(), end=part.start+predicate.end(),
                                           category=kind, disposition='asserted_without_support'))
            if TEST.search(clause):
                for mode in MODE.finditer(clause):
                    if operation_mode(clause,mode) and not disposition(part, mode.start(), mode.end(), mode[0]):
                        categories.add('operation_mode')
                        claims.append(dict(start=part.start+mode.start(), end=part.start+mode.end(),
                                           category='operation_mode', disposition='asserted_without_support'))
            if ABSENCE.search(text) and PERSISTENCE.search(clause):
                for predicate in CAUSE.finditer(clause):
                    if not disposition(part, predicate.start(), predicate.end(), predicate[0]):
                        categories.add('diagnostic_cause')
                        claims.append(dict(start=part.start+predicate.start(), end=part.start+predicate.end(),
                                           category='diagnostic_cause', disposition='asserted_without_support'))
            if not artifact:
                haystack = source + '\n' + '\n'.join(trusted)
                for predicate in LIFECYCLE_ABSENCE.finditer(clause):
                    start, end = predicate.span('predicate')
                    if (_established(predicate[0], haystack) or
                            disposition(part, start, end, predicate['predicate'])):
                        continue
                    categories.add('lifecycle_absence')
                    claims.append(dict(start=part.start+start, end=part.start+end,
                                       category='lifecycle_absence', disposition='asserted_without_support'))
                scoped = bool(CONVO_SCOPED.search(clause))
                for pattern, kind in ((QUEUE_INVENTORY, 'operational_state'), (PROCESS_STATE, 'operational_state')):
                    if kind == 'operational_state' and pattern is QUEUE_INVENTORY and scoped:
                        continue
                    for predicate in pattern.finditer(clause):
                        if _established(predicate[0], haystack) or disposition(part, predicate.start(), predicate.end(), predicate[0]):
                            continue
                        categories.add(kind)
                        claims.append(dict(start=part.start+predicate.start(), end=part.start+predicate.end(),
                                           category=kind, disposition='asserted_without_support'))
        if categories:
            findings.append(dict(start=part.start, end=part.end, categories=sorted(categories), claims=claims,
                sha256=hashlib.sha256(original.encode()).hexdigest(), reason='conclusion_exceeds_available_support'))
    return findings


def _established(phrase, haystack):
    return bool(phrase and haystack and re.search(re.escape(phrase.strip()), haystack, re.I))


def _allowed_urls(*texts):
    urls = []
    for text in texts:
        urls.extend(url.rstrip('.,;:!?') for _, url in MARKDOWN_LINK.findall(text or ''))
        urls.extend(url.rstrip('.,;:!?') for url in BARE_URL.findall(text or ''))
    return urls


def _user_asked_cursors(source):
    return bool(re.search(r'\b(?:journal\s+cursor|cursor\s+number|journal_cursor)\b', source or '', re.I))


def drop_empty_labels(text):
    """Drop orphan headings and empty list items; renumber only after a numbered drop."""
    lines = (text or '').split('\n')
    kept = []
    dropped_number = False
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        numbered = bool(re.match(r'^\d+[.)]\s+', stripped))
        if stripped and is_empty_label(stripped):
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            nxt = lines[j].strip() if j < len(lines) else ''
            next_heading = bool(nxt and (is_empty_label(nxt) or re.match(r'^#{1,6}\s+', nxt)
                                        or re.match(r'^(?:-{3,}|\*{3,}|_{3,})\s*$', nxt)))
            next_number = bool(nxt and re.match(r'^\d+[.)]\s+', nxt))
            cur_item = bool(re.match(r'^(?:\d+[.)]\s+|[-*+]\s+)', stripped))
            next_item = bool(nxt and re.match(r'^(?:\d+[.)]\s+|[-*+]\s+)', nxt))
            cur_indent = len(lines[i]) - len(lines[i].lstrip())
            next_indent = (len(lines[j]) - len(lines[j].lstrip())) if j < len(lines) else 0
            sibling_item = cur_item and next_item and next_indent <= cur_indent
            if not nxt or next_heading or (numbered and next_number) or sibling_item:
                dropped_number = dropped_number or numbered
                i += 1
                continue
        kept.append(lines[i])
        i += 1
    text = '\n'.join(kept)
    return _renumber_lists(text) if dropped_number else text


def _renumber_lists(text):
    """Compact a numbered run only when a guard left a gap; separate lists stay 1-based."""
    lines = text.split('\n')
    i = 0
    while i < len(lines):
        match = re.match(r'^(\s*)(\d+)([.)]\s+)', lines[i])
        if not match:
            i += 1
            continue
        indent, delim = match.group(1), match.group(3)
        run = []
        j = i
        while j < len(lines):
            numbered = re.match(r'^(\s*)(\d+)([.)]\s+)(.*)$', lines[j])
            if numbered and numbered.group(1) == indent and numbered.group(3) == delim:
                value = int(numbered.group(2))
                if run and value <= run[-1][1]:
                    break
                run.append((j, value, numbered.group(4)))
                j += 1
                continue
            if not lines[j].strip():
                k = j + 1
                while k < len(lines) and not lines[k].strip():
                    k += 1
                if k < len(lines) and re.match(r'^' + re.escape(indent) + r'\d+' + re.escape(delim), lines[k]):
                    next_num = re.match(r'^' + re.escape(indent) + r'(\d+)' + re.escape(delim), lines[k])
                    if next_num and run and int(next_num.group(1)) <= run[-1][1]:
                        break
                    j += 1
                    continue
                break
            if ITEM_START.match(lines[j].strip()) or EMPTY_LABEL.match(lines[j].strip()):
                break
            j += 1
        numbers = [item[1] for item in run]
        consecutive = list(range(numbers[0], numbers[0] + len(numbers))) if numbers else []
        if numbers and (numbers[0] != 1 or numbers != consecutive):
            for n, (line, _, body) in enumerate(run, 1):
                lines[line] = indent + str(n) + delim + body
        i = j if j > i else i + 1
    return '\n'.join(lines)


SUBORDINATE_ONLY = re.compile(
    r'^\s*(?:since|because|as|if|when|while|although|given that)\b', re.I)
DISCOURSE_AS = re.compile(
    r'^\s*as\s+(?:a\s+result|such|follows|usual|expected|of|for|to|with|per)\b', re.I)
LOWER_CONNECTOR = re.compile(
    r'^(?:and|or|but|yet|so|then|as|because|since|although|while)\b')


def _orphan_subordinate(body):
    """A leftover subordinate clause has no main clause of its own."""
    if not body:
        return False
    if body[0].islower() and LOWER_CONNECTOR.match(body) and not DISCOURSE_AS.match(body):
        return True
    if not SUBORDINATE_ONLY.match(body) or DISCOURSE_AS.match(body):
        return False
    return not (re.search(r',\s+\S', body) or re.search(r'\bthen\b', body, re.I))


def drop_orphan_fragments(text):
    """Drop sentences that are only a subordinate clause after a guard edit."""
    if not text:
        return text
    from reported_records import units
    kept = []
    for part in units(text):
        stripped = part.strip()
        if not stripped:
            kept.append(part)
            continue
        body = re.sub(r'^\s*(?:[-*+]\s+|\d+[.)]\s+|#{1,6}\s+)', '', stripped).strip()
        if _orphan_subordinate(body):
            continue
        if re.search(r'[,;]\s*$', body) or re.search(r'\b(?:and|or|but|yet|so)\s*$', body, re.I):
            body = re.sub(r'[,;]\s*$', '.', stripped.rstrip())
            if re.search(r'\b(?:and|or|but|yet|so)\s*$', body, re.I):
                continue
            kept.append(re.sub(r'[,;]\s*$', '.', part.rstrip()) + ('\n' if part.endswith('\n') else ''))
            continue
        kept.append(part)
    return ''.join(kept)


STEP_LABEL = re.compile(
    r'(?im)(?P<prefix>^\s*\|\s*|^\s*(?:#{1,6}\s+)?)(?P<label>Step\s+)(?P<n>\d+)\b')
STEP_REF = re.compile(
    r'\b(?:pass(?:es)?\s+)?steps?\s+\d+(?:\s*(?:,|and|&)\s*\d+)+', re.I)


def _drop_missing_step_refs(text, missing):
    if not missing:
        return text
    def scrub(match):
        nums = [int(n) for n in re.findall(r'\d+', match[0])]
        kept = [n for n in nums if n not in missing]
        if not kept:
            return ''
        if kept == nums:
            return match[0]
        head = match[0][:re.search(r'\d', match[0]).start()]
        if len(kept) == 1:
            head = re.sub(r'(?i)steps\s*$', 'step ', head)
            return head + str(kept[0])
        joined = ', '.join(str(n) for n in kept[:-1]) + ' and ' + str(kept[-1])
        return head + joined
    text = STEP_REF.sub(scrub, text)
    return re.sub(r' +([,.;:])', r'\1', re.sub(r' {2,}', ' ', text))


def _repair_step_lists(text):
    """Renumber remaining Step N labels and drop references to a removed step."""
    labels = [int(m.group('n')) for m in STEP_LABEL.finditer(text)]
    if labels:
        present = sorted(set(labels))
        missing = [n for n in range(1, max(present) + 1) if n not in present]
        if missing:
            text = _drop_missing_step_refs(text, set(missing))
            remap = {old: i for i, old in enumerate(present, 1)}
            def relabel(match):
                n = int(match.group('n'))
                return match.group('prefix') + match.group('label') + str(remap.get(n, n))
            text = STEP_LABEL.sub(relabel, text)
    return _renumber_lists(text)


def _collapse_interior_spaces(text):
    """Collapse repeated spaces inside a line without flattening nested list indent."""
    return '\n'.join(re.sub(r'(?<=\S) {2,}', ' ', line) for line in (text or '').split('\n'))


def _norm_para(text):
    return re.sub(r'\s+', ' ', re.sub(r'[*_`]', '', text or '')).strip().lower()


def _tokens(text):
    return set(re.findall(r'[a-z0-9]+', text or ''))


def already_delivered(text, prior):
    """True when this paragraph was already shown in an earlier assistant turn."""
    needle = _norm_para(text)
    if not needle or not prior or len(needle) < 40:
        return False
    for para in re.split(r'\n\s*\n', prior):
        hay = _norm_para(para)
        if not hay:
            continue
        if hay == needle or (len(needle) > 80 and needle in hay) or (len(hay) > 80 and hay in needle):
            return True
        if abs(len(hay) - len(needle)) <= max(24, int(0.18 * max(len(hay), len(needle)))):
            import difflib
            ratio = difflib.SequenceMatcher(None, hay, needle).ratio()
            a, b = _tokens(needle), _tokens(hay)
            overlap = (len(a & b) / len(a | b)) if a and b else 0
            if ratio >= 0.88 or (ratio >= 0.84 and overlap >= 0.9 and min(len(a), len(b)) >= 20):
                return True
    return False


def drop_repeated_paragraphs(text, prior):
    """Replace near-verbatim earlier paragraphs with a one-line reference."""
    if not text or not prior:
        return text
    chunks = re.split(r'(\n\s*\n)', text)
    kept = []
    referenced = False
    for index, chunk in enumerate(chunks):
        if index % 2 == 1:
            kept.append(chunk)
            continue
        if already_delivered(chunk, prior) and len(_norm_para(chunk)) > 80:
            if not referenced:
                kept.append('Same constraints as earlier in this conversation.')
                referenced = True
            continue
        kept.append(chunk)
    result = re.sub(r'\n{3,}', '\n\n', ''.join(kept)).strip()
    return result or 'The previous answer still applies to this follow-up.'


def scrub_unretrieved_links(text, *, source='', trusted_facts=()):
    """Remove http(s) citations that were not retrieved or supplied by the user."""
    allowed = set(_allowed_urls(source, *trusted_facts))
    def keep(url):
        url = (url or '').rstrip('.,;:!?')
        return any(url == item or url.startswith(item) or item.startswith(url) for item in allowed)
    text = MARKDOWN_LINK.sub(lambda m: m[0] if keep(m[2]) else m[1], text)
    text = BARE_URL.sub(lambda m: m[0] if keep(m[0]) else '', text)
    return _collapse_interior_spaces(text)


def strip_journal_cursors(text):
    def clean_line(line):
        stripped, count = JOURNAL_CURSOR.subn('', line)
        if not count:
            return line
        stripped = _collapse_interior_spaces(stripped)
        stripped = re.sub(r' ?([,;:]){2,}', r'\1', stripped)
        return re.sub(r' ?,$', '', stripped)
    return '\n'.join(clean_line(line) for line in text.split('\n'))


def rewrite_unsourced_file_observations(text):
    """Rewrite path+epoch 'observed' claims as saved-record attribution.

    Raw internal epochs and inventory paths are not user-facing live-read
    evidence. Timing, if it matters, is 'as of the saved record'.
    """
    if not text:
        return text
    text = PATH_THEN_OBSERVED_EPOCH.sub(SAVED_RECORD_PHRASE, text)
    text = OBSERVED_EPOCH_THEN_PATH.sub(SAVED_RECORD_PHRASE, text)
    text = BARE_OBSERVED_EPOCH.sub('as of the saved record', text)
    text = _collapse_interior_spaces(text)
    text = re.sub(r' ?([,;:]){2,}', r'\1', text)
    return text


def _repair_count_leadins(text):
    """When a guard drops numbered items, keep the lead-in count consistent."""
    if not text:
        return text

    def noun_for(noun, count):
        base = re.sub(r's$', '', noun, flags=re.I) if re.search(r'(?i)s$', noun) and not re.search(
            r'(?i)ss$', noun) else noun
        if count == 1:
            return base
        return noun if re.search(r'(?i)s$', noun) else base + 's'

    def repl(match):
        items = re.findall(r'(?m)^\d+[.)]\s+', match.group('body'))
        actual = len(items)
        stated = COUNT_WORDS.get(match.group('count').lower())
        if stated is None:
            stated = int(match.group('count'))
        if actual == stated or actual == 0:
            return match[0]
        count_out = WORD_FOR.get(actual, str(actual))
        if match.group('count')[0].isdigit():
            count_out = str(actual)
        elif match.group('count')[0].isupper():
            count_out = count_out.capitalize()
        noun_out = noun_for(match.group('noun'), actual)
        if match.group('noun')[0].isupper():
            noun_out = noun_out[0].upper() + noun_out[1:]
        return match.group('verb') + ' ' + count_out + ' ' + noun_out + ':' + match.group('ws') + match.group('body')

    return COUNT_LEADIN.sub(repl, text)


def _repair_completion_headings(text):
    """A list of only prospective items cannot establish completed work."""
    sections = re.split(r'(?m)(?=^#{1,6}[ \t]+|^(?:-{3,}|\*{3,}|_{3,})[ \t]*$)', text)
    for index, section in enumerate(sections):
        heading, separator, body = section.partition('\n')
        if not re.match(r'^#{1,6}[ \t]+Completed\b', heading, re.I):
            continue
        items = re.findall(r'(?m)^[ \t]*(?:\d+[.)]|[-*+])[ \t]+(?:\*\*|__)?([^\n]+)', body)
        if items and all(re.match(r'(?:Next|Proposed|Pending)\b', item, re.I) for item in items):
            sections[index] = re.sub(r'\bCompleted\b', 'Proposed', heading, count=1, flags=re.I) + separator + body
    return ''.join(sections)


def finish_delivery(text, *, source='', trusted_facts=(), preserve_writing=False):
    """Final user-facing cleanup: no leaked tags, empty labels, or unretrieved links."""
    text = (text or '').replace('[Unverified claim withheld]', '')
    text = scrub_unretrieved_links(text, source=source, trusted_facts=trusted_facts)
    if not _user_asked_cursors(source):
        text = strip_journal_cursors(text)
    text = rewrite_unsourced_file_observations(text)
    # Complete writing with no rejected claims needs no fragment/list repair.
    # In particular, a greeting or sign-off ending in a comma is intentional.
    if preserve_writing:
        return text.strip()
    text = drop_empty_labels(text)
    text = _repair_completion_headings(text)
    text = drop_orphan_fragments(text)
    text = _repair_step_lists(text)
    text = _repair_count_leadins(text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _outcome_already_qualified(text, category, prior=''):
    note = QUALIFICATIONS.get(category)
    hay = '\n'.join(part for part in (text, prior) if part)
    if note and (note in hay or (category == 'quality' and
                                 'The quality or continuity outcome is unverified' in hay)):
        return True
    if category == 'quality' and ALREADY_STATED.search(hay):
        return True
    patterns = {
        'cost': r"cannot guarantee either outcome|"
                r"(?:cost|capacity|billing|overage|charges?).{0,80}(?:unverified|not guaranteed)|"
                r"(?:cannot|can['’]t)\s+guarantee.{0,100}(?:charges?|billing|overages?|either outcome)",
        'quality': r"cannot guarantee either outcome|"
                   r"(?:quality|continuity)[\s\S]{0,120}(?:unverified|not guaranteed|not (?:an )?inherent outcome)|"
                   r"(?:cannot|can['’]t)\s+guarantee.{0,100}(?:quality|continuity|either outcome)",
    }
    pattern = patterns.get(category)
    return bool(pattern and re.search(pattern, hay, re.I))


def _qualify_once(text, categories, prior=''):
    notes = []
    for category in categories:
        note = QUALIFICATIONS.get(category)
        if (note and note not in text and note not in notes and
                not _outcome_already_qualified(text, category, prior)):
            notes.append(note)
    if not notes:
        return text
    return (text + '\n\n' if text else '') + ' '.join(notes)


def deliver(content, *, source='', trusted_facts=(), artifact=False, prior=''):
    """Preserve independent content and drop unsupported claims cleanly.

    This is a partial answer, not a silent certification or a repaired model
    quotation. Close broken clause joins without altering unaffected units.
    Resource packets retain their stricter dependency handling. Guard notes
    are natural prose, never bracketed tags, and appear at most once.
    """
    findings = violations(content, source=source, trusted_facts=trusted_facts, artifact=artifact)
    if not findings:
        return finish_delivery(content, source=source, trusted_facts=trusted_facts,
                               preserve_writing=artifact), []
    # A rejected embedded claim must not leave half a parenthesis or table row.
    # Preserve original claim receipts; these are presentation replacement spans.
    from reported_records import containers
    spans=[];detached=[];noted=[]
    for finding in sorted(findings,key=lambda f:f['start']):
        start,end=finding['start'],finding['end']
        for a,b in containers(content):
            if a < end and start < b:
                if a <= start and end <= b:
                    detached.extend(finding['categories'])
                start,end=min(start,a),max(end,b)
        line_start=content.rfind('\n',0,start)+1
        line_end=content.find('\n',end)
        if line_end<0:line_end=len(content)
        if content[line_start:line_end].strip().startswith('|'):
            start,end=line_start,line_end + (line_end < len(content))
        if spans and start<=spans[-1]['end']:
            spans[-1]['end']=max(end,spans[-1]['end'])
            spans[-1]['categories']=sorted(set(spans[-1]['categories']+finding['categories']))
        else:
            embedded=any(a==start and b==end for a,b in containers(content))
            spans.append(dict(start=start,end=end,categories=[] if embedded else finding['categories']))
    parts = []; position = 0
    connector = re.compile(r'(?:,?\s*\b(?:and|or|but|yet|however|therefore|thus|so|then|because|since|now that|given that|which|that)\b\s*|[;,]\s*)$',re.I)
    leading = re.compile(r'^\s*(?:,?\s*\b(?:and|or|but|yet|however|therefore|thus|so|then|as|because|since|although|while)\b\s*|[,;]\s*)',re.I)
    dangling_relative = re.compile(
        r'^\s*,?\s*(?:which|that)\s+(?:prevents?|avoids?|reduces?|limits?|blocks?)\b[^.!?]{0,120}(?:\.|$)', re.I)
    def remainder(value):
        # A rejected clause cannot leave its join word attached to the next
        # independently checked instruction.
        return leading.sub('',value,count=1) if position else value
    for finding in spans:
        before = remainder(content[position:finding['start']])
        join = connector.search(before)
        if join:
            before = before[:join.start()].rstrip()
            # An antecedent without its consequent is not a useful standalone
            # claim. Preserve any preceding list marker, heading or sentence.
            antecedent = re.search(r'(?:^|(?<=[.!?])\s+|\n)(\s*(?:if|unless|until|when|once|before)\b[^.!?\n]*)$',before,re.I)
            if antecedent:
                before = before[:antecedent.start(1)]
            elif before.strip() and before[-1] not in '.!?:':
                from claim_scope import QUESTION, plain
                last = re.split(r'[.!?]\s+|\n',plain(before))[-1]
                before += '?' if QUESTION.match(last) else '.'
        parts.append(before)
        if before.strip() and before[-1] in '.!?':parts.append('\n')
        noted.extend(finding['categories'])
        position = finding['end']
    tail = remainder(content[position:])
    while tail:
        match = dangling_relative.match(tail)
        if not match:
            break
        tail = tail[match.end():].lstrip()
    parts.append(tail)
    noted.extend(dict.fromkeys(detached))
    text = finish_delivery(''.join(parts), source=source, trusted_facts=trusted_facts)
    if not artifact:
        text = finish_delivery(_qualify_once(text, dict.fromkeys(noted), prior=prior),
                               source=source, trusted_facts=trusted_facts)
    return text, findings
