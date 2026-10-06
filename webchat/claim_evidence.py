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
EPISTEMIC_WITHOUT = re.compile(r'^\s*(?:establishing|preserving|assuming|claiming|promising|proving)\b', re.I)
QUALIFICATIONS = {
    'cost': 'The cost or capacity outcome is unverified from what’s available here. Check the actual route, allowance and billing controls before admitting generation.',
    'quality': 'The quality or continuity outcome is unverified from what’s available here.',
    'operation_mode': 'That execution mode is unverified from what’s available here. Inspect the exact command’s writes, network access and isolation contract before treating a test run as read-only.',
    'diagnostic_cause': 'A missing result does not identify its cause from what’s available here. Match the request and source across save, stored state, access, retrieval and rendering.',
    'operational_state': "I can’t confirm live queue, task, or process state from what’s available here.",
}
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
EMPTY_LABEL = re.compile(
    r'^(?:#{1,6}\s+)?(?:\d+[.)]\s+|[-*+]\s+)?(?:\*\*[^*\n]{1,80}\*\*|__[^_\n]{1,80}__|[^\n:]{1,80}):(?:\*\*|__)?\s*$')
ITEM_START = re.compile(r'^(?:#{1,6}\s+|\d+[.)]\s+|[-*+]\s+)')


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
                states = list(state_predicates(clause, objects))
                for predicate in states:
                    start, end = predicate.span('state')
                    if not disposition(part, start, end, predicate['state'], copular=True):
                        categories.add(kind)
                        claims.append(dict(start=part.start+start,end=part.start+end,
                                           category=kind,disposition='asserted_without_support'))
                for predicate in ASSURANCE.finditer(clause):
                    # Acquisition is a different operation from metered use.
                    tail = clause[predicate.end():]
                    negative = predicate[0].lower() in ('no', 'cannot', "can't", 'can’t', 'does not', 'do not', 'will not', "won't", 'won’t')
                    if negative and re.match(r'\s+(?:evidence|proof|basis|mean|imply|establish|prove|guarantee|promise|assume|prevent|protect|preserve|maintain|avoid|guard|ensure|eliminate)\b', tail, re.I):
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
                    # A predicate must govern an outcome in this clause. A cost
                    # noun before "without buying" cannot change that operation.
                    if labelled or _assurance_governs_outcome(clause, predicate, objects) or re.search(
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
        if stripped and EMPTY_LABEL.match(stripped):
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            nxt = lines[j].strip() if j < len(lines) else ''
            next_heading = bool(nxt and (EMPTY_LABEL.match(nxt) or re.match(r'^#{1,6}\s+', nxt)))
            next_number = bool(nxt and re.match(r'^\d+[.)]\s+', nxt))
            if not nxt or next_heading or (numbered and next_number):
                dropped_number = dropped_number or numbered
                i += 1
                continue
        kept.append(lines[i])
        i += 1
    text = '\n'.join(kept)
    return _renumber_lists(text) if dropped_number else text


def _renumber_lists(text):
    lines = text.split('\n')
    i = 0
    while i < len(lines):
        match = re.match(r'^(\s*)(\d+)([.)]\s+)', lines[i])
        if not match:
            i += 1
            continue
        indent, delim = match.group(1), match.group(3)
        n = 0
        j = i
        while j < len(lines):
            numbered = re.match(r'^(\s*)(\d+)([.)]\s+)(.*)$', lines[j])
            if numbered and numbered.group(1) == indent and numbered.group(3) == delim:
                n += 1
                lines[j] = indent + str(n) + delim + numbered.group(4)
                j += 1
                continue
            if not lines[j].strip():
                k = j + 1
                while k < len(lines) and not lines[k].strip():
                    k += 1
                if k < len(lines) and re.match(r'^' + re.escape(indent) + r'\d+' + re.escape(delim), lines[k]):
                    j += 1
                    continue
                break
            if ITEM_START.match(lines[j].strip()) or EMPTY_LABEL.match(lines[j].strip()):
                break
            j += 1
        i = j if j > i else i + 1
    return '\n'.join(lines)


def scrub_unretrieved_links(text, *, source='', trusted_facts=()):
    """Remove http(s) citations that were not retrieved or supplied by the user."""
    allowed = set(_allowed_urls(source, *trusted_facts))
    def keep(url):
        url = (url or '').rstrip('.,;:!?')
        return any(url == item or url.startswith(item) or item.startswith(url) for item in allowed)
    text = MARKDOWN_LINK.sub(lambda m: m[0] if keep(m[2]) else m[1], text)
    text = BARE_URL.sub(lambda m: m[0] if keep(m[0]) else '', text)
    return re.sub(r' {2,}', ' ', text)


def strip_journal_cursors(text):
    text = JOURNAL_CURSOR.sub('', text)
    text = re.sub(r' {2,}', ' ', text)
    text = re.sub(r' ?([,;:]){2,}', r'\1', text)
    return re.sub(r' ?,$', '', text, flags=re.M)


def finish_delivery(text, *, source='', trusted_facts=()):
    """Final user-facing cleanup: no leaked tags, empty labels, or unretrieved links."""
    text = (text or '').replace('[Unverified claim withheld]', '')
    text = scrub_unretrieved_links(text, source=source, trusted_facts=trusted_facts)
    if not _user_asked_cursors(source):
        text = strip_journal_cursors(text)
    text = drop_empty_labels(text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _qualify_once(text, categories):
    notes = []
    for category in categories:
        note = QUALIFICATIONS.get(category)
        if note and note not in text and note not in notes:
            notes.append(note)
    if not notes:
        return text
    return (text + '\n\n' if text else '') + ' '.join(notes)


def deliver(content, *, source='', trusted_facts=(), artifact=False):
    """Preserve independent content and drop unsupported claims cleanly.

    This is a partial answer, not a silent certification or a repaired model
    quotation. Close broken clause joins without altering unaffected units.
    Resource packets retain their stricter dependency handling. Guard notes
    are natural prose, never bracketed tags, and appear at most once.
    """
    findings = violations(content, source=source, trusted_facts=trusted_facts, artifact=artifact)
    if not findings:
        return finish_delivery(content, source=source, trusted_facts=trusted_facts), []
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
            start,end=line_start,line_end
        if spans and start<=spans[-1]['end']:
            spans[-1]['end']=max(end,spans[-1]['end'])
            spans[-1]['categories']=sorted(set(spans[-1]['categories']+finding['categories']))
        else:
            embedded=any(a==start and b==end for a,b in containers(content))
            spans.append(dict(start=start,end=end,categories=[] if embedded else finding['categories']))
    parts = []; position = 0
    connector = re.compile(r'(?:,?\s*\b(?:and|or|but|yet|however|therefore|thus|so|then|because|since|now that|given that|which|that)\b\s*|,\s*)$',re.I)
    leading = re.compile(r'^\s*(?:,?\s*\b(?:and|or|but|yet|however|therefore|thus|so|then)\b\s*|[,;]\s*)',re.I)
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
        text = finish_delivery(_qualify_once(text, dict.fromkeys(noted)),
                               source=source, trusted_facts=trusted_facts)
    return text, findings
