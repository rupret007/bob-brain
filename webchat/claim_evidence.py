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
    'cost': re.compile(r'\b(?:charges?|costs?|fees?|spend(?:ing)?|overages?|billing|credits?|quota|allowance|exhaustion|rate limits?)\b', re.I),
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
OBJECT_BOUNDARY = re.compile(r'\b(?:about|above|across|after|against|along|among|around|as|at|before|behind|below|'
    r'beneath|beside|between|beyond|by|despite|during|except|for|from|in|inside|into|near|of|off|on|onto|out|outside|'
    r'over|past|per|since|through|throughout|to|toward|under|until|upon|via|with|within|when|while|because|using|or|that|which|where|if)\b', re.I)
IMPERATIVE = re.compile(r'^\s*(?:[-*]\s*|\d+[.)]\s*)?(?:compare|check|inspect|prepare|require|preserve|protect|maintain|keep|record|verify)\b', re.I)
QUALIFICATIONS = {
    'cost': 'The cost or capacity outcome is unverified. Check the actual route, allowance and billing controls before admitting generation; preparing a plan does not establish its charges.',
    'quality': 'The quality or continuity outcome is unverified. Preserve it as an acceptance requirement and obtain representative evidence before claiming it is protected.',
    'operation_mode': 'That execution mode is unverified. Inspect the exact command’s writes, network access and isolation contract before treating a test run as read-only.',
    'diagnostic_cause': 'A missing result does not identify its cause. Match the request and source across save acknowledgment, stored state, access, retrieval and rendering to separate the explanations.',
}


def _plain(text):
    return re.sub(r'[*_`]', '', text)


def _nonasserted(prefix, predicate, clause, *, sentence_start=False):
    from assertion_scope import nonasserted
    prefix = _plain(prefix)
    scoped_predicate = predicate + ' ' if predicate.lower() in ('preserve', 'protect', 'maintain') else predicate
    if nonasserted(prefix, scoped_predicate, sentence_start=sentence_start):
        return True
    if (sentence_start and not prefix.strip() and predicate.lower() in ('preserving', 'protecting', 'maintaining')
            and re.match(r'^\w+\s+[^.!?;:]{1,60}:', _plain(clause).strip())):
        return True
    # A goal or check is not an assertion that its desired result is established.
    # An appended independent clause gets a new prefix in violations().
    if re.search(r'\b(?:require|aim for|target|acceptance criterion|acceptance criteria|goal|objective)\s*:?\s*$', prefix, re.I):
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


def violations(content, *, source='', trusted_facts=(), artifact=False):
    from claim_scope import clauses, disposition
    findings = []
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
            for kind, objects in OUTCOMES.items():
                targets = list(objects.finditer(clause))
                labelled = bool(objects.search(part.label))
                if not targets and not labelled:
                    continue
                for predicate in ASSURANCE.finditer(clause):
                    # Acquisition is a different operation from metered use.
                    tail = clause[predicate.end():]
                    negative = predicate[0].lower() in ('no', 'cannot', "can't", 'can’t', 'does not', 'do not', 'will not', "won't", 'won’t')
                    if negative and re.match(r'\s+(?:evidence|proof|basis|mean|imply|establish|prove|guarantee|promise|assume|prevent|protect|preserve|maintain|avoid|guard|ensure|eliminate)\b', tail, re.I):
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
                    if disposition(part, predicate.start(), predicate.end(), predicate[0]):
                        continue
                    # A predicate must govern an outcome in this clause. A cost
                    # noun before "without buying" cannot change that operation.
                    if labelled or any(t.start() >= predicate.end() for t in targets) or re.search(
                            r'\b(?:is|are|stays?|remains?|will be)\s*$', clause[:predicate.start()], re.I):
                        categories.add(kind)
                        claims.append(dict(start=part.start+predicate.start(), end=part.start+predicate.end(),
                                           category=kind, disposition='asserted_without_support'))
            if TEST.search(clause):
                for mode in MODE.finditer(clause):
                    if not disposition(part, mode.start(), mode.end(), mode[0]):
                        categories.add('operation_mode')
                        claims.append(dict(start=part.start+mode.start(), end=part.start+mode.end(),
                                           category='operation_mode', disposition='asserted_without_support'))
            if ABSENCE.search(text) and PERSISTENCE.search(clause):
                for predicate in CAUSE.finditer(clause):
                    if not disposition(part, predicate.start(), predicate.end(), predicate[0]):
                        categories.add('diagnostic_cause')
                        claims.append(dict(start=part.start+predicate.start(), end=part.start+predicate.end(),
                                           category='diagnostic_cause', disposition='asserted_without_support'))
        if categories:
            findings.append(dict(start=part.start, end=part.end, categories=sorted(categories), claims=claims,
                sha256=hashlib.sha256(original.encode()).hexdigest(), reason='conclusion_exceeds_available_support'))
    return findings


def deliver(content, *, source='', trusted_facts=(), artifact=False):
    """Preserve independent content and expose replaced unsupported claims.

    This is a partial answer, not a silent certification or a repaired model
    quotation. Close broken clause joins without altering unaffected units.
    Resource packets retain their stricter dependency handling.
    """
    findings = violations(content, source=source, trusted_facts=trusted_facts, artifact=artifact)
    if not findings:
        return content, []
    parts = []; position = 0
    connector = re.compile(r'(?:,?\s*\b(?:and|or|but|yet|however|therefore|thus|so|then|because|since|now that|given that|which|that)\b\s*|,\s*)$',re.I)
    leading = re.compile(r'^\s*(?:,?\s*\b(?:and|or|but|yet|however|therefore|thus|so|then)\b\s*|[,;]\s*)',re.I)
    def remainder(value):
        # A rejected clause cannot leave its join word attached to the next
        # independently checked instruction.
        return leading.sub('',value,count=1) if position else value
    for finding in findings:
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
        marker = re.match(r'^\s*(?:[-*+]\s+|\d+[.)]\s+)',content[finding['start']:finding['end']])
        if marker:parts.append(marker[0])
        for category in finding['categories']:
            parts.append(' [Unverified claim withheld] ' + QUALIFICATIONS[category] + '\n')
        position = finding['end']
    parts.append(remainder(content[position:]))
    return ''.join(parts).strip(), findings
