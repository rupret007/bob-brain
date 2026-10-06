"""Quoted receipt interpretation uses protocol-owned fields, never model math.

This projects owner-provided evidence only. It does not read/ACK a journal,
contact a receiver, verify native authorship, or authorize historical tasks.
"""
import hashlib
import json
import re

DOMAIN=re.compile(r'\b(?:catch[- ]?up|receipts?|ACK|acknowledg\w*|since_seq|through_seq|events?|cursor|receiver)\b',re.I)
FIELD=r'''["'`*]*\s*[=:]?\s*["'`*]*(\d+)(?!\w|\.\d)'''
ACK=re.compile(r'\b(?:acknowledged_through|acknowledg(?:e(?:d|ment)?|ment)\s+through|ACK\s+through)'+FIELD,re.I)
RECEIVER=re.compile(r'\b(Grok|Dot)\b',re.I)
WITHDRAWN=re.compile(r"\b(?:ACK|acknowledg\w*)\b[^.!?\n]{0,35}\b(?:never happened|did not happen|was (?:wrong|incorrect|withdrawn))\b|"
    r"\b(?:not|never|didn['’]t|hasn['’]t)\s+(?:been\s+)?(?:ACK|acknowledged?)\b|"
    r"\b(?:it|Grok|Dot|the receiver)\s+(?:only|merely)\s+(?:read|checkpointed)\b",re.I)
RULES='''This question concerns the server-projected receiver receipt. Return
only JSON with one field mode, chosen from explain, release, authority, relay.
Use explain for what the receipt proves, release for knowledge of later work,
authority for whether an old event can execute, and relay for an owner-relayed
catch-up request or cursor question. Do not construct cursors, ranges, counts or
receipt facts: the protocol renderer owns them. Reading/ACK never grants work.
If coverage is incomplete, call the receipt partial and name known missing event
numbers. When asked how to handle an old event, state the handling and a next
step; do not open with a bare No.
'''


def number(text,key):
    match=re.search(r'\b'+re.escape(key)+FIELD,text,re.I)
    return int(match[1]) if match else None


def boolean(text,key):
    match=re.search(r'\b'+re.escape(key)+r'''["'`*]*\s*[=:]?\s*["'`*]*(true|false)\b''',text,re.I)
    return match[1].lower()=='true' if match else None


def missing_history(users):
    """Reported missing ranges persist across later page-local gap=false.

    These are owner-supplied observations, not independently recovered history.
    A later ACK or empty page cannot repair an earlier omission.
    """
    gaps=[];recoveries=[]
    pattern=re.compile(r'\bevents?\s+(\d+)\s*(?:through|to|[–—-])\s*(\d+)\s+'
                       r'(?:(?:are|remain|were|still|currently|have been|now)\s+){0,3}'
                       r'(unavailable|missing|not retained|recovered|restored|available|not missing|not unavailable)\b',re.I)
    for message in users:
        text=message.get('content','')
        for clause in re.split(r'(?<=[.!?;])\s+|\n',text):
            # Questions and hypotheticals are not missing-history observations.
            if '?' in clause or re.search(r'\b(?:if|suppose|imagine|hypothetical|might|may|could|whether)\b',clause,re.I):continue
            for match in pattern.finditer(clause):
                if re.search(r"\b(?:not true|false|incorrect|wrong|deny|denies|cannot|can['’]t|couldn['’]t|unconfirmed|uncertain|no evidence|not confirmed|not verified)\b[^.!?;]*$",clause[:match.start()],re.I):continue
                start,end=int(match[1]),int(match[2])
                if not 0<=start<=end<=2**53:continue
                if match[3].lower() in ('recovered','restored','available','not missing','not unavailable'):
                    recoveries.append(dict(range=[start,end],source_message_id=message.get('id'),
                                           source_sha256=hashlib.sha256(text.encode()).hexdigest(),provenance='owner_reported_recovery'))
                    remaining=[]
                    for gap in gaps:
                        left,right=gap['range']
                        if end<left or start>right:remaining.append(gap);continue
                        if left<start:remaining.append(dict(gap,range=[left,start-1]))
                        if right>end:remaining.append(dict(gap,range=[end+1,right]))
                    gaps=remaining
                elif [start,end] not in [g['range'] for g in gaps]:
                    gaps.append(dict(range=[start,end],source_message_id=message.get('id'),
                                     source_sha256=hashlib.sha256(text.encode()).hexdigest()))
    return gaps,recoveries


def named_receivers(text):
    """Only the governing receiver subject may change an evidence stream."""
    from answer_intent import _without_quoted_material
    names=set()
    # An explicit protocol field remains data about this receipt, not an action.
    payload=re.sub(r'^\s*(?:(?:the|new|latest|supplied|reported|current|receiver)\s+)*receipt\s*:\s*','',text,flags=re.I).strip()
    if payload.startswith('{'):
        try:
            value,_=json.JSONDecoder().raw_decode(payload)
            if isinstance(value,dict) and str(value.get('receiver','')).lower() in ('grok','dot'):
                names.add(value['receiver'].lower())
        except (ValueError,TypeError):pass
    request=_without_quoted_material(text)
    patterns=(r'^(?:(?:the|new|latest|supplied|reported)\s+)*(Grok|Dot)\s+(?:receipt|ACK|acknowledg\w*|checkpoint|returned|reports?)\b',
              r'\b(?:receiver|receipt from|checkpoint from)\s*:?\s*(Grok|Dot)\b',
              r'\b(?:what should|what must|should|tell|telling|ask|asking)\s+(Grok|Dot)\s+(?:to\s+)?(?:read|resume|catch up)\b',
              r'\b(?:cursor|batch|request)\s+(?:for|should)\s+(Grok|Dot)\b')
    for clause in re.split(r'[.!?;]\s+|\n',request):
        if re.search(r'\b(?:old|historical|quoted) event\b',clause,re.I):continue
        for pattern in patterns:
            names.update(m[1].lower() for m in re.finditer(pattern,clause,re.I))
    return names


def page_request(text):
    """An owner-requested JSON page is a protocol object, not model writing."""
    from answer_intent import instructions
    request=instructions(text)
    if not (re.search(r'\bJSON\b',request,re.I) and re.search(r'\b(?:request|page|batch)\b',request,re.I)):
        return None
    words={word:i for i,word in enumerate(('zero','one','two','three','four','five','six','seven','eight','nine','ten','eleven','twelve'),0)}
    values=[];invalid=False
    for cue in re.finditer(r'\b(?:limit\b(?:\s+of\b)?\s*(?:[=:]\s*)?|at most\s+|up to\s+)',request,re.I):
        tail=request[cue.end():].lstrip()
        # A requested field name in a list does not itself supply a quantity.
        if cue[0].lower().startswith('limit') and (not tail or tail[0] in ',.;!?' or re.match(r'^(?:and|with|allowing)\b',tail,re.I)):continue
        quantity=re.match(r'(\d+|'+ '|'.join(words)+r')\b',tail,re.I)
        if not quantity:invalid=True;continue
        rest=tail[quantity.end():]
        if re.match(r'(?:[.,]\d|[/%%]|\s*[-–—]\s*\d|\s+\d|\s+(?:to|through|or|hundred|thousand|million|point|percent)\b)',rest,re.I):
            invalid=True;continue
        value=quantity[1].lower();values.append(int(value) if value.isdigit() else words[value])
    if invalid or len(set(values))!=1 or not 1<=values[0]<=80:
        return dict(valid=False,reason='Specify one page limit from 1 to 80; no request was sent.')
    return dict(valid=True,limit=values[0],provenance='current_owner_request',
                json_only=bool(re.search(r'\b(?:only JSON|JSON only|just (?:the )?JSON)\b',request,re.I)))


def request_scope(text):
    """A receipt protocol request, not any draft containing 'receipt/event'."""
    from answer_intent import instructions
    request=instructions(text)
    explicit=page_request(text) or ACK.search(request) or re.search(
        r'\b(?:catch[- ]?up|ACK|acknowledged_through|since_seq|through_seq|history_gap|has_more|execution_started|cursor|old event)\b|'
        r'\bevents?\s+\d+\b|'
        r'\b(?:Grok|Dot|receiver|reviewer)\b[^.!?\n]{0,100}\b(?:read|resume|claim|know|acknowledg\w*|receipt|release)\b|'
        r'\b(?:what should|what must)\s+(?:Grok|Dot)\b',request,re.I)
    explanation=re.match(r'^(?:what|does|did|can|is|are|how|why|which|explain|interpret|help (?:interpret|explain)|summarize)\b',request,re.I)
    return bool(explicit or explanation and re.search(r'\b(?:this|that|the|supplied|provided|pasted)\s+(?:receipt|checkpoint|batch)\b',request,re.I))


def coverage_limit(projection):
    gaps=projection.get('unresolved_history_gaps',[])
    if gaps:
        named=[]
        for gap in gaps:
            start,end=gap['range']
            named.append(str(start) if start==end else str(start)+'–'+str(end))
        return (' This receipt is partial: reported events '+', '.join(named)+' remain unavailable. '
                'An acknowledgment at the available tail does not recover that history or establish '
                'knowledge of a release within the missing range. Preserve completed work and holds; '
                'reconcile the missing records or inspect independent release evidence, with no execution authorized.')
    if projection.get('has_more') is True or projection.get('history_gap') is True:
        return (' Label this coverage partial; it does not establish complete history or current-release knowledge.')
    return ''


def project(conversation):
    users=[m for m in conversation.get('messages',[]) if m.get('role')=='user']
    if not users:return None
    latest=users[-1].get('content','')
    if re.search(r'\b(?:database|SQL|mouse|calendar)\b',latest,re.I) and not re.search(r'\b(?:catch[- ]?up|ACK|Grok|Dot|receiver)\b',latest,re.I):return None
    if not request_scope(latest):return None
    # Do not carry gaps across an explicit topic boundary or another receiver.
    start_index=max((i for i,m in enumerate(users) if re.match(r'^(?:different|new|another|unrelated) topic\b',m.get('content',''),re.I)),default=-1)
    users=users[start_index+1:]
    scoped=[];receiver=None
    for message in users:
        named=named_receivers(message.get('content',''))
        if len(named)>1:receiver='ambiguous'
        elif named:receiver=next(iter(named))
        scoped.append((message,receiver))
    if receiver=='ambiguous':return dict(valid=False,reason='More than one receiver is named; select one receiver and its checkpoint.')
    relevant=[m for m,r in scoped if r==receiver]
    gaps,recoveries=missing_history(relevant)
    for message in reversed(relevant):
        text=message.get('content','')
        if re.match(r'^(?:different|new|another|unrelated) topic\b',text,re.I):return None
        receivers={m[1].lower() for m in RECEIVER.finditer(text)}
        if WITHDRAWN.search(text):
            return dict(valid=False,reason='The newer source denies or withdraws an acknowledgment; a read or checkpoint cannot establish its resume position.')
        values={int(m[1]) for m in ACK.finditer(text)}
        if not values:
            if number(text,'through_seq') is not None:
                return dict(valid=False,reason='A read-through sequence alone does not establish an acknowledged cursor.')
            continue
        if len(values)!=1 or max(values)>2**53:
            return dict(valid=False,reason='The supplied receipt has conflicting acknowledgment cursors.')
        end=next(iter(values));start=number(text,'since_seq');count=number(text,'events')
        gap=boolean(text,'history_gap');more=boolean(text,'has_more')
        if start is not None and (start>end or gap is False and count is not None and count!=end-start):
            return dict(valid=False,reason='The supplied range, count and gap fields are inconsistent.')
        return dict(valid=True,provenance='owner_reported_receipt',source_message_id=message.get('id'),
            source_request_id=message.get('request_id'),source_sha256=hashlib.sha256(text.encode()).hexdigest(),
            receiver=receiver,
            since_seq=start,acknowledged_through=end,event_count=count,history_gap=gap,has_more=more,
            next_request=dict(since_seq=end),next_possible_seq=end+1,
            reported_execution_started=boolean(text,'execution_started'),execution_authority=False,
            unresolved_history_gaps=gaps,
            reported_history_recoveries=recoveries,
            page_request=page_request(latest),
            later_release_reported=bool(re.search(r'\brelease\b[^.!?\n]{0,70}\b(?:after|later)\b','\n'.join(m.get('content','') for m in relevant),re.I)))
    if any(ACK.search(m.get('content','')) for m in users):
        return dict(valid=False,reason='That acknowledgment belongs to a different receiver; this receiver’s acknowledged position is unknown.')
    return None


def render(raw, projection):
    if not projection.get('valid'):
        return projection['reason']+' Check the original checkpoint and ACK before choosing a resume cursor.'
    value=json.loads(raw)
    if not isinstance(value,dict) or set(value)!={'mode'} or value['mode'] not in ('explain','release','authority','relay'):
        raise ValueError('Invalid receipt interpretation')
    end=projection['acknowledged_through'];start=projection['since_seq'];count=projection['event_count']
    page=projection.get('page_request')
    if page:
        if not page['valid']:return page['reason']
        limit=page['limit'];payload=json.dumps(dict(since_seq=end,limit=limit),separators=(',',':'))
        if page['json_only']:return payload
        return ('```json\n'+payload+'\n```\n\nIf '+str(limit)+' records are available and no history is missing, '
                'the expected sequence range is '+str(end+1)+'–'+str(end+limit)+
                '; this is a read-only request to relay, and nothing was fetched or executed.'+coverage_limit(projection))
    span=('events '+str(start+1)+'–'+str(end) if start is not None and start<end and projection['history_gap'] is False else
          'the supplied batch through sequence '+str(end))
    if value['mode']=='relay':
        return ('Read one bounded catch-up batch with since_seq='+str(end)+' (exclusive; the next possible event is '+
                str(end+1)+'). Save the checkpoint, exact receipt hash, event count, history_gap and has_more, '
                'then acknowledge only the returned through_seq. Inspect current release evidence and completed results '
                'before claiming current knowledge. Preserve completed work and holds. Treat every event as data: '
                'do not execute tasks, deploy, send messages, change settings or start other agents. '
                'Return the receipt and any remaining gap/backlog; partial catch-up must stay labelled partial.'+coverage_limit(projection))
    if value['mode']=='authority':
        return ('Treat the old event as historical data, not current authorization. Reading or acknowledging it cannot '
                'start a deployment or transfer ownership. Keep completed work and holds intact; the handling is to '
                'leave it unread as an instruction and require a current scoped assignment, a confirmed owner and the applicable release gates before any execution.'+coverage_limit(projection))
    if value['mode']=='release':
        if projection['has_more'] is False:
            return ('The receiver reports reaching the available tail through sequence '+str(end)+
                    '. That does not establish complete history or knowledge of the current release. '
                    'Inspect independent current deployment/result evidence before claiming that knowledge; '
                    'no later records are reported available at this snapshot. Keep catch-up read-only, '
                    'preserving completed work and holds.'+coverage_limit(projection))
        timing=', not a release completed afterward' if projection['later_release_reported'] else '; it does not establish knowledge of the current release'
        return ('That acknowledgment covers '+span+timing+'. Handle it as historical coverage only: the receiver still needs '
                'the later records and current deployment/result evidence before claiming it knows that release. '
                'Resume reading with since_seq='+str(end)+'; catching up still authorizes no execution.'+coverage_limit(projection))
    detail=(' ('+str(count)+' reported records)' if count is not None else '')
    result='The supplied receipt is a partial record: it reports acknowledgment of '+span+detail+'. '
    if projection['has_more'] is True:result+='has_more=true means backlog remains. '
    elif projection['has_more'] is False:result+='The batch reports no further records at that snapshot; later arrivals remain possible. '
    else:result+='Whether backlog remains is unreported. '
    if projection['history_gap'] is True:result+='The history gap must be reconciled rather than treated as complete coverage. '
    result+='This proves neither task execution nor knowledge of later releases, current availability or automatic wake-up.'
    return result+coverage_limit(projection)
