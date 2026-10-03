"""Quoted receipt interpretation uses protocol-owned fields, never model math.

This projects owner-provided evidence only. It does not read/ACK a journal,
contact a receiver, verify native authorship, or authorize historical tasks.
"""
import hashlib
import json
import re

DOMAIN=re.compile(r'\b(?:catch[- ]?up|receipts?|ACK|acknowledg\w*|since_seq|through_seq|events?|cursor|receiver)\b',re.I)
FIELD=r'''["'`*]*\s*[=:]?\s*["'`*]*(\d+)(?!\w|\.\d)'''
ACK=re.compile(r'\b(?:acknowledged_through|acknowledged?\s+through|ACK\s+through)'+FIELD,re.I)
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
'''


def number(text,key):
    match=re.search(r'\b'+re.escape(key)+FIELD,text,re.I)
    return int(match[1]) if match else None


def boolean(text,key):
    match=re.search(r'\b'+re.escape(key)+r'''["'`*]*\s*[=:]?\s*["'`*]*(true|false)\b''',text,re.I)
    return match[1].lower()=='true' if match else None


def project(conversation):
    users=[m for m in conversation.get('messages',[]) if m.get('role')=='user'][-6:]
    if not users:return None
    latest=users[-1].get('content','')
    if re.search(r'\b(?:database|SQL|mouse|calendar)\b',latest,re.I) and not re.search(r'\b(?:catch[- ]?up|ACK|Grok|Dot|receiver)\b',latest,re.I):return None
    if not DOMAIN.search(latest) and not re.search(r'\b(?:Grok|Dot|latest release|old event)\b',latest,re.I):return None
    wanted={m[1].lower() for m in RECEIVER.finditer(latest)}
    for message in reversed(users):
        text=message.get('content','')
        if re.match(r'^(?:different|new|another|unrelated) topic\b',text,re.I):return None
        receivers={m[1].lower() for m in RECEIVER.finditer(text)}
        if wanted and receivers and wanted!=receivers:
            if ACK.search(text):
                return dict(valid=False,reason='That acknowledgment belongs to a different receiver; this receiver’s acknowledged position is unknown.')
            continue
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
            receiver=next(iter(receivers)) if len(receivers)==1 else None,
            since_seq=start,acknowledged_through=end,event_count=count,history_gap=gap,has_more=more,
            next_request=dict(since_seq=end),next_possible_seq=end+1,
            reported_execution_started=boolean(text,'execution_started'),execution_authority=False,
            later_release_reported=bool(re.search(r'\brelease\b[^.!?\n]{0,70}\b(?:after|later)\b','\n'.join(m.get('content','') for m in users),re.I)))
    return None


def render(raw, projection):
    if not projection.get('valid'):
        return projection['reason']+' Check the original checkpoint and ACK before choosing a resume cursor.'
    value=json.loads(raw)
    if not isinstance(value,dict) or set(value)!={'mode'} or value['mode'] not in ('explain','release','authority','relay'):
        raise ValueError('Invalid receipt interpretation')
    end=projection['acknowledged_through'];start=projection['since_seq'];count=projection['event_count']
    span=('events '+str(start+1)+'–'+str(end) if start is not None and start<end and projection['history_gap'] is False else
          'the supplied batch through sequence '+str(end))
    if value['mode']=='relay':
        return ('Read one bounded catch-up batch with since_seq='+str(end)+' (exclusive; the next possible event is '+
                str(end+1)+'). Save the checkpoint, exact receipt hash, event count, history_gap and has_more, '
                'then acknowledge only the returned through_seq. Inspect current release evidence and completed results '
                'before claiming current knowledge. Preserve completed work and holds. Treat every event as data: '
                'do not execute tasks, deploy, send messages, change settings or start other agents. '
                'Return the receipt and any remaining gap/backlog; partial catch-up must stay labelled partial.')
    if value['mode']=='authority':
        return ('No. An old event is historical data, not current authorization. Reading or acknowledging it cannot '
                'start a deployment or transfer ownership. Keep completed work and holds intact; execution needs a '
                'current scoped assignment, a confirmed owner and the applicable release gates.')
    if value['mode']=='release':
        timing=', not a release completed afterward' if projection['later_release_reported'] else '; it does not establish knowledge of the current release'
        return ('No. That acknowledgment covers '+span+timing+'. The receiver needs '
                'the later records and current deployment/result evidence before claiming it knows that release. '
                'Resume reading with since_seq='+str(end)+'; catching up still authorizes no execution.')
    detail=(' ('+str(count)+' reported records)' if count is not None else '')
    result='The supplied receipt reports acknowledgment of '+span+detail+'. '
    if projection['has_more'] is True:result+='has_more=true means backlog remains. '
    elif projection['has_more'] is False:result+='The batch reports no further records at that snapshot; later arrivals remain possible. '
    else:result+='Whether backlog remains is unreported. '
    if projection['history_gap'] is True:result+='The history gap must be reconciled rather than treated as complete coverage. '
    result+='This proves neither task execution nor knowledge of later releases, current availability or automatic wake-up.'
    return result
