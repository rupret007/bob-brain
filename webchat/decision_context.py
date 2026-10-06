"""Attributed decision conditions, separate from live state and generated advice.

The server retains source-bound conditions and renders them at final delivery.
It does not synthesize a plan, certify a model's recommendation, or grant work.
Extraction is deliberately bounded; ambiguous corrections remain observable.
"""
import hashlib
import re

SCENARIO = re.compile(r'\b(?:planning example|hypothetical (?:scenario|case|example)|'
                      r'fictional (?:scenario|case|example)|scenario|suppose)\b',re.I)
RESOURCE = re.compile(r'\b(?:models?|providers?|subscriptions?|routes?|credits?|allowance)\b',re.I)
FOLLOWUP = re.compile(r'\b(?:prepare|preparation|conclude|comparison|compare|proposals?|'
    r'resources?|routes?|allowance|charges?|quality|next steps?|way forward|recommend\w*|'
    r'decision|constraint|paid for|access|guarantee\w*)\b',re.I)
DECISION = re.compile(r'\b(?:next steps?|way forward|recommend\w*|sensible|prepare|preparation|'
                      r'what (?:should|can)|decision|conclude)\b',re.I)
CHECKS = {
    'allowance': re.compile(r'\b(?:remaining (?:allowance|capacity|usage)|quota)\b',re.I),
    'overage': re.compile(r'\b(?:(?:optional |extra[- ]usage )?overage settings|extra[- ]usage settings|billing settings|extra charges)\b',re.I),
    'quality': re.compile(r'\b(?:(?:answer|output|task) )?quality\b',re.I),
}
STATE = re.compile(r'\b(?:is|are|has|have|receives?|can|cannot|remains?|stopped|resumed|'
                   r'exhausted|depleted|restored|unavailable|inaccessible|missing|available)\b',re.I)
UNKNOWN = re.compile(r'\b(?:nobody|no one)\s+has\s+(?:checked|verified|measured|established)\s+|'
    r'\b(?:has|have)\s+not\s+(?:checked|verified|measured|established)\s+',re.I)
UNKNOWN_STATE = re.compile(r'\b(?:unverified|unknown|unchecked|unmeasured|not (?:checked|verified|measured|established))\b',re.I)
INPUT = re.compile(r'\b(?:proposal|input|document|snapshot|file|dataset)\s+[\w.-]+',re.I)
ROUTE = re.compile(r'\b(?:(?:hosted|subscription|report|chat|conversation|local|remote|primary|alternate|backup)\s+){0,3}'
                   r'(?:route|model|provider)\b',re.I)
RULES = '''A server-owned decision-context projection accompanies this answer.
Its conditions are attributed to the user's planning example, not live provider
observations or execution permission. The server will display the current bound
conditions before your answer; do not repeat that context block or emit its IDs.
Use those conditions in your reasoning: name the useful preparation possible now,
the conclusion still blocked by missing evidence, and the specific checks needed
before a proposed next action. Preserve task quality, funding and access limits.
Answer the requested question concisely; conditions alone are not a useful plan.
Do not invent completed checks, guarantees, spending or dispatched work. Later
user corrections supersede only the matching condition, not unrelated unknowns.
If the projection reports unresolved corrections or overflow, explain that the
recommendation is incomplete and name the unresolved decision; do not treat the
prior conditions as current or claim that the server has reconciled them.
'''


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def subject(text, pattern=ROUTE):
    matches = list(pattern.finditer(text))
    if not matches:
        return 'scenario'
    return re.sub(r'\s+',' ',matches[0][0].lower())


def source_text(original):
    from answer_intent import instructions
    # A leading scenario declaration supplies the example itself. Nested
    # imported notes remain references, using the same mask as action routing.
    framed=re.sub(r'^\s*(?:(?:new|another|different)\s+)?(?:hypothetical|fictional)\s+(?:scenario|case|example)\s*:',
                  lambda m:' '*len(m[0]),original,flags=re.I)
    return instructions(framed,preserve_offsets=True)


def route_scopes(text):
    result=[]
    for match in ROUTE.finditer(text):
        value=match[0].lower()
        tail=text[match.end():]
        if 'route' not in value:
            continue
        if re.search(r'\bchat\b|\bconversation\b',value):
            value='chat route'
        elif re.search(r'\breport\b',value) or re.match(r'\s+for\s+(?:read-only\s+)?reports\b',tail,re.I):
            value='report route'
        else:
            value=re.sub(r'^subscription\s+','',value)
        if value not in result:result.append(value)
    return result


def asserted_envelope(masked,start):
    """Retain outer governors even when a clause or heading was separated."""
    from claim_scope import plain, verification_governs, QUESTION, DENIED, NOMINAL_DENIAL
    from reported_records import presentation
    begin=max((m.end() for m in re.finditer(r'[.!?;\n]',masked[:start])),default=0)
    terminal=re.search(r'[.!?;\n]',masked[start:])
    finish=start+terminal.end() if terminal else len(masked)
    envelope=plain(masked[begin:finish]).strip()
    for value in (envelope,presentation(envelope)[1]):
        if (re.match(r'^(?:if|unless|when|once|until|before|after)\b',value,re.I) or
                QUESTION.match(value) or verification_governs(value) or
                DENIED.search(value) or NOMINAL_DENIAL.search(value)):
            return False
    return True


def extract(message, redact, routes=None):
    """Compile complete declarative source spans; quoted commands are not facts."""
    from claim_scope import clauses, plain
    from answer_intent import instructions
    original = message.get('content','')
    request = instructions(original)
    # Use original offsets. Mask quoted/fenced content rather than promoting
    # imported instructions into conditions or attempting to execute them.
    masked = source_text(original)
    if not request.strip():
        return []
    rows = []
    for clause in clauses(masked):
        start,end=clause.start,clause.end
        # Clause splitting must not erase a conditional/verification governor
        # around a consequent. Inspect the enclosing source sentence first.
        if not asserted_envelope(masked,start):
            continue
        value=original[start:end].strip()
        clean=plain(masked[start:end]).strip()
        clean=re.sub(r'^(?:planning example only|in (?:this|the) (?:hypothetical )?(?:scenario|example)|'
                     r'(?:one )?correction|actually)\s*:\s*','',clean,flags=re.I)
        # A causal credit clause needs its actual route subject. Reunite it
        # only with the same sentence's explicit subject, never a prior turn.
        if re.match(r'^(?:its|their)\s+(?:credit|funding|balance|budget)\b',clean,re.I):
            sentence_start=max((m.end() for m in re.finditer(r'[.!?;\n]',masked[:start])),default=0)
            candidate=plain(masked[sentence_start:end]).strip()
            if ROUTE.search(candidate) and re.search(r'\bbecause\b',candidate,re.I):
                start=sentence_start
                clean=re.sub(r'^planning example(?: only)?\s*:\s*','',candidate,flags=re.I)
        if not clean or '?' in clean or not STATE.search(clean):
            continue
        if re.match(r'^(?:if|unless|whether|when|until)\b',clean,re.I):
            continue
        if re.match(r'^(?:do not|don.t|ignore|execute|send|buy|switch|use|tell|give|keep|check|verify|confirm)\b',clean,re.I):
            continue
        source=dict(message_id=message.get('id'),request_id=message.get('request_id',message.get('id')),
                    source_sha256=digest(original),start=start,end=end,excerpt_sha256=digest(original[start:end]))
        def add(key, statement, kind, scope=None):
            statement=redact(statement).strip()
            if not statement or len(statement)>700:
                return
            rows.append(dict(key=key,kind=kind,statement=statement,source=source,
                             subject=scope,subject_source=(routes or {}).get(scope),
                             id=digest(str(source)+key+statement)[:20]))
        def check_scopes():
            explicit=route_scopes(clean)
            return explicit or list(routes or {}) or ['scenario resources']
        def check_fact(category,statement):
            for scope in check_scopes():
                add('checks.'+scope+'.'+category,scope.capitalize()+': '+statement,category,scope)
        unknown=UNKNOWN.search(clean)
        if unknown:
            if clean[:unknown.start()].strip().lower() not in ('','we','they','you','the team'):
                continue
            for item in re.split(r',\s*(?:or\s+|and\s+)?|\s+(?:or|and)\s+',clean[unknown.end():]):
                item=re.sub(r'^(?:their|the|our|its)\s+','',item.strip(' .'),flags=re.I)
                for category,pattern in CHECKS.items():
                    if pattern.search(item):
                        check_fact(category,item[0].upper()+item[1:]+': not checked in the supplied example.')
            continue
        matched_check=False
        for category,pattern in CHECKS.items():
            if pattern.search(clean) and UNKNOWN_STATE.search(clean):
                check_fact(category,clean); matched_check=True
        if matched_check:
            continue
        # An explicit correction about a previously unknown check replaces
        # only that property. Merely proposing a check never counts as done.
        if re.search(r'\b(?:is|are|has been|have been)\s+(?:now\s+)?(?:checked|verified|measured|established)\b',clean,re.I):
            for category,pattern in CHECKS.items():
                if pattern.search(clean):
                    check_fact(category,clean); matched_check=True
        if matched_check:
            continue
        if re.search(r'\b(?:credits?|funding|balance|budget)\b',clean,re.I) and re.search(
                r'\b(?:stopp?\w*|exhaust\w*|deplet\w*|restor\w*|resum\w*|unavailable)\b',clean,re.I):
            add('funding.'+subject(clean),clean,'funding',subject(clean))
        elif INPUT.search(clean) and re.search(r'\b(?:inaccessible|unavailable|missing|available|accessible|provided|received)\b',clean,re.I):
            add('input.'+subject(clean,INPUT),clean,'input')
        elif ROUTE.search(clean) and re.search(r'\b(?:tools?|file[- ]reading|supplied text|access)\b',clean,re.I):
            add('access.'+subject(clean),clean,'access',subject(clean))
    return rows


def project(conversation, redact):
    from answer_intent import TOPIC_CHANGE, requires_execution, live_observation, instructions
    from conversation_focus import correction
    from reply_contract import WRITING
    active=False; facts={}; superseded=[]; origin=None; current=None; ambiguous=[]; routes={}
    for message in conversation.get('messages',[]):
        if message.get('role')!='user':
            continue
        text=message.get('content',''); request=instructions(text); masked=source_text(text)
        explicit_new=bool(re.match(r'^\s*(?:new|another|different)\s+(?:(?:hypothetical|fictional|planning)\s+)?(?:scenario|case|example)\b',request,re.I))
        fresh=bool(SCENARIO.search(request) and RESOURCE.search(masked) and (not active or explicit_new))
        reset=bool(TOPIC_CHANGE.match(request) or WRITING.match(request) or
                   requires_execution(text) or live_observation(text))
        if reset or active and not fresh and not (FOLLOWUP.search(request) or DECISION.search(request) or correction(text)):
            active=False; facts={}; superseded=[]; origin=None; ambiguous=[]; routes={}
        if fresh:
            active=True; facts={}; superseded=[]; ambiguous=[]; routes={}; origin=message.get('id')
        if not active:
            continue
        current=message
        for name in route_scopes(masked):
            routes.setdefault(name,dict(message_id=message.get('id'),source_sha256=digest(text)))
        extracted=extract(message,redact,routes)
        withdrawn=[]
        attempted_withdrawal=False; unresolved_withdrawal=False
        from claim_scope import clauses
        from reported_records import presentation
        for withdrawal in re.finditer(r'\b(?:disregard|withdraw|ignore)\s+(?:(?:the|earlier|previous|old)\s+)*'
                                     r'(funding|access|quality|allowance|overage)\s+(?:statement|condition|claim)\b',masked,re.I):
            enclosing=next((part for part in clauses(masked) if part.start<=withdrawal.start()<part.end),None)
            if not enclosing or not asserted_envelope(masked,withdrawal.start()):
                continue
            prefix=presentation(masked[enclosing.start:withdrawal.start()])[1].strip()
            if not re.fullmatch(r'(?:(?:please|also)\s*)*',prefix,re.I):
                continue
            attempted_withdrawal=True
            category=withdrawal[1].lower()
            tail=re.split(r'[.!?;\n]',masked[withdrawal.end():],maxsplit=1)[0]
            target=re.fullmatch(r'\s*(?:for|on|in)\s+(?:the\s+)?(.+?)\s*',tail,re.I) if tail.strip() else None
            targets=[]
            if tail.strip():
                if not target or not ROUTE.fullmatch(target[1]):
                    unresolved_withdrawal=True;continue
                targets=route_scopes(target[1]) or [subject(target[1])]
            matched=False
            for key,row in list(facts.items()):
                if row['kind']==category and (not targets or row.get('subject') in targets):
                    withdrawn.append(row['id']);del facts[key];matched=True
            if not matched:unresolved_withdrawal=True
        # A correction that contains another unresolved state-changing clause
        # must not silently retain the prior interpretation of that clause.
        unresolved=(unresolved_withdrawal or re.search(r'\b(?:replace|instead)\b',masked,re.I) and not extracted)
        if (attempted_withdrawal and unresolved_withdrawal or
                correction(text) and (not extracted and not withdrawn or unresolved)):
            ambiguous.append(dict(message_id=message.get('id'),source_sha256=digest(text)))
        if withdrawn:
            superseded.extend(dict(old=i,new=None,withdrawn_by=message.get('id')) for i in withdrawn)
        for row in extracted:
            if row['key'] in facts:
                superseded.append(dict(old=facts[row['key']]['id'],new=row['id']))
            facts[row['key']]=row
    if not active or not current or not facts or not DECISION.search(current.get('content','')):
        return None
    bounded=list(facts.values())[:12]
    return dict(version=1,scope='user-supplied planning example, not live observations',origin=origin,
        request_id=current.get('request_id',current.get('id')),facts=bounded,superseded=superseded,
        ambiguous_corrections=ambiguous[-3:],required_ids=[v['id'] for v in bounded],
        truncated=len(facts)>12,omitted_conditions=max(0,len(facts)-12),authority='No execution, routing, budget or permission authority.')


def render(content, projection, conversation, redact):
    """Compose after final guards/redaction; only frozen user sources may render.

    Coverage describes visible source facts, never model reasoning quality. If
    the guarded answer is incomplete, this context cannot turn it into a pass.
    """
    if not projection:
        return content,None
    users={m.get('id'):m for m in conversation.get('messages',[]) if m.get('role')=='user'}
    displayed=[]; rejected=[]
    for row in projection['facts']:
        source=row['source']; message=users.get(source['message_id'],{})
        raw=message.get('content','')
        valid=(message.get('request_id',message.get('id'))==source['request_id'] and
            digest(raw)==source['source_sha256'] and
            digest(raw[source['start']:source['end']])==source['excerpt_sha256'] and
            redact(row['statement'])==row['statement'])
        subject_source=row.get('subject_source')
        if subject_source:
            valid=valid and digest(users.get(subject_source['message_id'],{}).get('content',''))==subject_source['source_sha256']
        if valid:
            displayed.append(row)
        else:
            rejected.append(row['id'])
    # Unparsed corrections make the previous conditions insufficiently current.
    # Preserve useful model prose, but never silently present stale source facts.
    ambiguous=bool(projection['ambiguous_corrections'] or projection['truncated'])
    if ambiguous:
        rejected.extend(r['id'] for r in displayed); displayed=[]
    statements=[]; unchecked={}
    for row in displayed:
        tail=': not checked in the supplied example.'
        if row.get('subject') and row['statement'].endswith(tail):
            property=row['statement'].split(': ',1)[1][:-len(tail)]
            unchecked.setdefault(property,[]).append(row['subject'])
        else:
            statements.append(row['statement'].rstrip(' .;'))
    grouped={}
    for property,subjects in unchecked.items():
        grouped.setdefault(tuple(sorted(set(subjects))),[]).append(property)
    for subjects,properties in grouped.items():
        statements.append('For '+ ' and '.join(subjects)+', '+ ', '.join(properties)+' have not been checked in the supplied example')
    statements=list(dict.fromkeys(statements))
    context='Your stated planning conditions: '+ '; '.join(statements)+'.' if statements else ''
    if ambiguous:
        excerpts=[]
        for reference in projection['ambiguous_corrections']:
            raw=users.get(reference['message_id'],{}).get('content','')
            if digest(raw)==reference['source_sha256']:
                excerpts.append(redact(raw)[:700])
        context='The current planning conditions are unresolved; this recommendation is incomplete.'
        if excerpts:context+=' Your correction still needs reconciliation: '+ ' '.join(excerpts)
        if projection['truncated']:context+=' The supplied conditions exceed this bounded context projection.'
    empty_sections=bool(re.search(r'(?m)^\s*(?:#{1,6}\s*)?(?:\*\*)?[^\n:]{1,100}:(?:\*\*)?\s*\Z',content))
    if empty_sections:
        from claim_evidence import drop_empty_labels
        content=drop_empty_labels(content)
    final=(context+'\n\n' if context else '')+content
    review=dict(scope='Visible attributed source conditions only; usefulness and next-step completeness require separate review.',
        required_ids=projection['required_ids'],rendered_ids=[r['id'] for r in displayed],
        rejected_ids=rejected,partial=bool(rejected or empty_sections),empty_final_section=empty_sections,
        context_supplied_by='server from frozen user sources',context_sha256=digest(context),
        delivered_sha256=digest(final),recommendation_verified=False)
    return final,review
