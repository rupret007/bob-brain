"""Presentation and subject boundaries for discussing supplied task records.

These helpers provide no execution authority. Real permission/effect checks still
inspect the original text. Headings do not define a vocabulary of permitted facts.
"""
import hashlib
import re

ITEM = re.compile(r'^\s*(?:[-*+]\s+|\d+[.)]\s+)')
SENTENCE = re.compile(r'(?<=[!?])(?=\s)|(?<=[.])(?=\s)(?<!\d\.)')
ABBREVIATION = re.compile(r'\b(?:vs|e\.g|i\.e|etc|Mr|Mrs|Dr)\.$', re.I)
ENTITY = re.compile(r'\b(?:services?|workers?|reviewers?|daemons?|servers?|processes|process|systems?|apps?|hosts?|agents?|coordinators?|supervisors?)\b|\b[A-Z][A-Za-z]*(?:Worker|Agent|Service|Daemon)\b', re.I)
IDENTIFIER = r'[A-Za-z][\w]*-\d+'
TASK_ID = re.compile(r'\b(?:(?:task|assignment)\s+(?:ID\s+)?|(?:record|card|case|scenario)(?:\s+only)?\s*:\s*(?:task\s+)?)('+IDENTIFIER+r')\b', re.I)


def containers(text):
    """Balanced presentation spans; offsets always refer to original bytes."""
    stack = []
    for index, char in enumerate(text):
        if char in '([':
            stack.append((index, char))
        elif char in ')]' and stack and stack[-1][1] == {')':'(', ']':'['}[char]:
            start, _ = stack.pop()
            if not stack:
                yield start, index+1


def sentence_spans(text, *, clauses=False):
    """Shared boundaries: abbreviations and balanced containers stay intact.

    Containers affect presentation only. Claim callers separately inspect their
    contents, including finite assertions inside a nominal report description.
    """
    protected = list(containers(text))
    start = 0
    for index, char in enumerate(text):
        if any(a <= index < b for a,b in protected):
            continue
        terminal = char in '.!?' or clauses and char in ';\n'
        if not terminal or char != '\n' and index+1 < len(text) and not text[index+1].isspace():
            continue
        if char == '.' and (ABBREVIATION.search(text[:index+1]) or
                            re.search(r'\b\d+\.$',text[:index+1])):
            continue
        yield start,index+1
        start=index+1
    if start < len(text):
        yield start,len(text)


def units(content):
    """Keep list markers with their bodies, including indented continuation."""
    pending = ''
    for line in content.splitlines(keepends=True):
        item = bool(ITEM.match(line))
        if pending:
            if line.strip() and line[0].isspace() and not item:
                pending += line
                continue
            yield pending
            pending = ''
        if item:
            pending = line
        else:
            for start,end in sentence_spans(line):
                yield line[start:end]
    if pending:
        yield pending


def presentation(part):
    plain = re.sub(r'[*_`]', '', part)
    plain = re.sub(r'^\s*(?:[-+]\s+|\d+[.)]\s+)?', '', plain)
    label = re.match(r'^([^:\n]{1,128}):\s*', plain)
    return (label[1], plain[label.end():]) if label else ('', plain)


def foreign_label(label, projects, worker_names):
    return bool(projects(label) or ENTITY.search(label) or
                any(re.search(r'\b'+re.escape(name)+r'\b', label, re.I) for name in worker_names))


def foreign_subject(clause, projects, worker_names):
    # Only the grammatical subject changes the referent. Mentioning an actor
    # inside an uncertainty or evidence requirement does not switch the topic.
    subject = re.match(r'^\s*(.{1,96}?)\s+(?:is|are|was|were|remains?|has|have|does|do|did|will|can|may|might|could|must|should)\b', clause, re.I)
    return bool(subject and foreign_label(subject[1], projects, worker_names))


def prospective_hold_check(prefix, suffix=''):
    """A verification instruction may name a prospective release prerequisite.

    Bind only the dependent hold reference. This neither asserts termination
    nor exempts sibling claims, and the caller still checks permission effects.
    """
    from claim_scope import clauses, verification_governs, finite_predicate
    tail=suffix.strip(' .!?\n')
    if tail:
        continuation=re.fullmatch(r'(?:or|and)\s+(?:evaluate|consider|review|propose)\s+(.+)',tail,re.I)
        if not continuation or finite_predicate(continuation[1]) or re.search(
                r'\b(?:that|which|who|because|since|already|now)\b',continuation[1],re.I):
            return False
    boundary = re.search(r'\bbefore\s+(?:(?:taking\s+(?:any\s+)?action\s+to|'
        r'considering|evaluating|proposing)\s+)?(?:release|releasing|lift|lifting|clear|clearing)(?:\s+of)?\s*$',prefix,re.I)
    if not boundary:
        boundary = re.search(r'\bbefore\s+asking\s+(?:the\s+)?owner\s+to\s+(?:release|lift|clear)\s*$',prefix,re.I)
    if not boundary:
        return False
    directives = re.split(r'\b(?:and|or)\s+(?=(?:check|verify|confirm|assess|evaluate|inspect|examine|obtain|seek|require)\b)',
                          prefix[:boundary.start()],flags=re.I)
    checks = [clause for directive in directives for clause in clauses(directive)]
    if not checks:
        return False
    for check in checks:
        if verification_governs(check.text):
            continue
        head = re.match(r'^\s*(?:obtain|seek|require)\s+(?:(?:explicit|independent|documented|termination)\s+)?'
                        r'(?:confirmation|verification|evidence)\b',check.text,re.I)
        if not head or finite_predicate(check.text[head.end():]):
            return False
    return True


def source_bindings(record):
    excerpts = (record or {}).get('user_excerpts', [])
    # Associated lease/snapshot/artifact identifiers are not task subjects.
    # Follow-up references can reuse an identity established by its task role.
    tasks = {m[1] for excerpt in excerpts for m in TASK_ID.finditer(excerpt.get('content', ''))}
    result = {}
    for excerpt in excerpts:
        text = excerpt.get('content', '')
        binding = dict(message_id=excerpt['message_id'], request_id=excerpt['request_id'],
                       excerpt_sha256=hashlib.sha256(text.encode()).hexdigest(),
                       truncated=excerpt.get('truncated', False))
        for identifier in re.findall(r'\b[A-Za-z][\w]*-\d+\b', text):
            if identifier in tasks:
                result.setdefault(identifier, []).append(binding)
    return result


def topic_record(record, bindings):
    """The original question's unique task stays the topic of its follow-ups.

    Later cached artifact/task IDs are evidence to compare, not automatic topic
    switches. A new question resets answer_focus upstream. Multiple original
    subjects remain ambiguous and receive no implicit task attribution.
    """
    excerpts = (record or {}).get('user_excerpts', [])
    candidates = {m[1] for m in TASK_ID.finditer(excerpts[0]['content'])} if excerpts else set()
    candidates &= set(bindings)
    from conversation_focus import CORRECTION
    for excerpt in excerpts[1:]:
        if CORRECTION.match(excerpt['content'].strip()):
            corrected = {m[1] for m in TASK_ID.finditer(excerpt['content'])} & set(bindings)
            if corrected and corrected != candidates:
                # A correction may change the target or only an associated
                # artifact. Require an explicit answer subject before inheriting
                # a task again; never continue using the old identity silently.
                return None
    return next(iter(candidates)) if len(candidates)==1 else None


def receipt(part, *, offset, accepted, reason, subject, bindings):
    return dict(start=offset, end=offset+len(part), sha256=hashlib.sha256(part.encode()).hexdigest(),
                accepted=accepted, reason=reason, referenced_record=subject,
                source_bindings=bindings.get(subject, []))


RECORD_ACTOR = re.compile(
    r'\b(?:I|we|you|he|she|they|someone|somebody|Bob|Codex|Claude|Cursor|Gemini|MiniMax|'
    r'the\s+(?:system|server|scheduler|owner|operator|dispatcher))\b', re.I)
DESCRIPTIVE_ASSIGNED = re.compile(
    r'\bassigned(?=\s+(?:worker|assignee|reviewer|agent)s?\b)', re.I)
FINITE_ASSIGN = re.compile(
    r'\b(?:was|were|is|are|been|being)\s+$|'
    r'\b(?:has|have|had)\s+(?:been\s+)?$', re.I)


def attributed_descriptive_bindings(content, bindings):
    """Mask adjectival assignment when restating a supplied task binding.

    'assigned worker ReviewWorker' names the recorded identity. It is not an
    actor assigning work. Finite I/we/system predicates and 'assigned to'
    verbal claims stay visible to the effect checks.
    """
    if not bindings:
        return content
    identity = '(?:'+'|'.join(re.escape(i) for i in sorted(bindings))+')'
    if not re.search(r'\b'+identity+r'\b', re.sub(r'[*_`]', ' ', content), re.I):
        return content
    masked = list(content)
    for match in DESCRIPTIVE_ASSIGNED.finditer(content):
        local = re.split(r'[.;!?\n]', content[:match.start()])[-1]
        if RECORD_ACTOR.search(local) or FINITE_ASSIGN.search(local):
            continue
        masked[match.start():match.end()] = ' '*(match.end()-match.start())
    return ''.join(masked)


def attributed_parentheticals(content, bindings):
    """Mask passive descriptive predicates whose head is a supplied task ID.

    Only reduced relative clauses inside a parenthesis inherit that head.
    Finite actors, concrete application IDs and text outside the parenthesis
    remain visible to the independent effect checks. This supplies reference
    scope, never evidence of an actual assignment.
    """
    if not bindings:
        return content
    plain = re.sub(r'[*_`]', ' ', content)
    identity = '(?:'+'|'.join(re.escape(i) for i in sorted(bindings))+')'
    parenthetical = re.compile(r'\b'+identity+r'\s*\((?P<body>[^()\n.!?]{1,240})\)', re.I)
    predicate = re.compile(r'(?:^|\b(?:and|or)\s+)(?P<verb>bound|assigned|queued|scheduled|delegated)'
                           r'(?=\s+(?:to|for|in|under|with|by)\b)', re.I)
    masked = list(content)
    for item in parenthetical.finditer(plain):
        body = item['body']
        # Reduced relatives have no independent finite subject. Do not let
        # "R-41 (I assigned...)" or a later finite clause borrow task scope.
        if not predicate.match(body) or re.search(r'\b(?:I|we|you|he|she|it|they|is|are|was|were|has|have|will|did|your|our|my|actual|real|live)\b',body,re.I):
            continue
        for match in predicate.finditer(body):
            start = item.start('body')+match.start('verb')
            end = item.start('body')+match.end('verb')
            masked[start:end] = ' '*(end-start)
    return ''.join(masked)
