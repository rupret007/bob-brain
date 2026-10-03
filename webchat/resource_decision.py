"""Evidence-owned resource facts, model-selected bounded recommendations.

Advice does not change routing or enqueue work. The model chooses supported
actions; authentication, reach, quota, quality and billing assertions are rendered
from the same capability registry and observed evidence used by the product.
"""
import json
import re
import hashlib

import resource_inventory
from resource_capabilities import ROUTES, supports

RESOURCE_NAMES = r'\b(?:'+'|'.join(ROUTES)+r')\b'
ACTIONABLE = tuple(name for name in ROUTES if supports(name,'conversation'))

STEPS = ('qualify_chat','prepare_report','provide_inputs','inspect_allowance','keep_current','review_dependency')
RULES = '''This is resource advice, not an execution request. Return only JSON
with exactly resource and steps. resource is codex, cursor, claude, gemini or
minimax; steps is a list of one to three distinct choices from qualify_chat,
prepare_report, provide_inputs, inspect_allowance, keep_current, review_dependency.
Choose the most useful next step first, based on the owner's current question,
needed files, existing supported routes and evidence. prepare_report supports
Claude only. qualify_chat means a representative quality check, not changing
the default. Do not generate resource facts or guarantees: the server renders
verified reach and genuine unknowns. An outage scenario is not a live outage.
'''


def project(root, conversation):
    latest=next((m.get('content','') for m in reversed(conversation.get('messages',[])) if m.get('role')=='user'),'')
    comparison=bool(re.search(r'\b(?:compare|comparison|difference)\b',latest,re.I) and
                    len(set(re.findall(RESOURCE_NAMES,latest.lower())))>=2)
    if not resource_inventory.relevant(conversation) and not comparison:
        return None
    users=[m for m in conversation.get('messages',[]) if m.get('role')=='user'][-6:]
    current=users[-1].get('content','') if users else ''
    # Writing about a subscription can still be ordinary requested writing.
    if re.match(r'^(?:write|draft|compose)\b',current.strip(),re.I):return None
    scope=[]
    for message in reversed(users):
        text=message.get('content','')
        if re.match(r'^(?:different|new|another|unrelated) topic\b',text.strip(),re.I):break
        scope.insert(0,dict(request_id=message.get('request_id'),text=text[:1500]))
    source='\n'.join(m['text'] for m in scope)
    if not comparison and not re.search(r'\b(?:subscriptions?|paid|pay|billing|quotas?|allowances?|credits?|prepaid|extra usage)\b',source,re.I):
        return None
    unavailable=set();missing=False
    for message in scope:
        text=message['text']
        for clause in re.split(r'[.!\n;]|\b(?:while|but|whereas)\b',text,flags=re.I):
            if re.match(r'^\s*(?:is|are|can|could|should|would|check|verify|make|ensure)\b',clause,re.I):continue
            names=list(re.finditer(RESOURCE_NAMES,clause,re.I))
            for index,match in enumerate(names):
                tail=clause[match.end():names[index+1].start() if index+1<len(names) else len(clause)]
                name=match[0].lower()
                if '?' in tail and not re.search(r'\b(?:suppose|what if|scenario)\b',clause,re.I):continue
                if re.search(r"\b(?:not|isn['’]t|no longer)\s+(?:currently )?(?:unavailable|depleted|exhausted|down)\b",tail,re.I):unavailable.discard(name)
                elif re.search(r"\b(?:not|isn['’]t|no longer)\s+(?:currently )?(?:available|usable|funded)\b",tail,re.I):unavailable.add(name)
                elif re.search(r'\b(?:unavailable|depleted|exhausted|out of (?:tokens|credits)|down)\b',tail,re.I):unavailable.add(name)
                elif re.search(r'\b(?:available|usable|restored|back online|funded)\b',tail,re.I):unavailable.discard(name)
        if re.search(r"\b(?:cannot|can['’]t|couldn['’]t|unable to|doesn['’]t|does not)\s+(?:read|access|see|open)\b.{0,65}\b(?:files?|repository|repo|inputs?)\b|"
                     r'\b(?:missing|unavailable|inaccessible)\s+(?:project )?(?:files?|inputs?)\b',text,re.I):missing=True
        elif re.search(r'\b(?:files?|inputs?) (?:are |is |now )*(?:available|provided|attached|accessible)\b|\b(?:can|able to) (?:now )?(?:read|access) (?:the |those |needed |project )*files\b',text,re.I):missing=False
    view='comparison' if comparison else 'inventory' if re.search(r'\b(?:what|which)\b.{0,35}\bsubscriptions?\b.{0,25}\b(?:have|pay for)\b',latest,re.I) else 'advice'
    named=list(dict.fromkeys(re.findall(RESOURCE_NAMES,latest.lower())))
    restricted=set()
    for message in scope:
        text=message['text']
        for clause in re.split(r'[.!?;\n]',text):
            if re.search(r'\bonly\b',clause,re.I):
                selection=re.search(r'\bonly\s+('+RESOURCE_NAMES+r'(?:\s*(?:,|or|and)\s*'+RESOURCE_NAMES+r')*)',clause,re.I)
                names=set(re.findall(RESOURCE_NAMES,selection[1].lower())) if selection else {
                    name for name in ACTIONABLE if re.search(r'\b'+name+r'[- ]only\b',clause,re.I)}
                names.intersection_update(ACTIONABLE)
                if names:restricted=names
    return dict(version=1,inventory=resource_inventory.observe(root),
        owner_sources=[dict(request_id=m['request_id'],sha256=hashlib.sha256(m['text'].encode()).hexdigest()) for m in scope],
        requested_view=view,requested_resources=named,allowed_resources=sorted(restricted) if restricted else list(ACTIONABLE),
        scenario=bool(re.search(r'\b(?:suppose|scenario|what if)\b',source,re.I)),
        missing_inputs=missing,unavailable=sorted(unavailable))


def render(raw, projection):
    """No ungrounded free-text factual field can enter a resource recommendation."""
    if projection.get('requested_view') in ('comparison','inventory'):
        names=projection.get('requested_resources') or list(ROUTES)
        rows=['| Resource | Supported use | Billing / evidence |','|---|---|---|']
        for item in projection['inventory']['resources']:
            if item['name'] not in names:continue
            observed=item['observation']
            auth=(str(observed.get('plan') or observed.get('auth_mode'))+' observed; ' if observed.get('freshness')=='recent' and observed.get('authenticated') is True else 'Current sign-in/plan unverified; ')
            rows.append('| '+item['name'].title()+' | '+', '.join(item['tasks'])+' | '+auth+item['billing']+' |')
        return '\n'.join(rows)+'\n\nThese are supported routes, not a verified subscription invoice. Login alone establishes neither remaining capacity nor comparative answer quality; use a matched task before changing the default.',dict(view=projection['requested_view'],execution_started=False)
    value=json.loads(raw)
    if (not isinstance(value,dict) or set(value)!= {'resource','steps'} or
            value['resource'] not in ('codex','cursor','claude','gemini','minimax') or
            not isinstance(value['steps'],list) or not 1<=len(value['steps'])<=3 or
            len(set(value['steps']))!=len(value['steps']) or any(s not in STEPS for s in value['steps'])):
        raise ValueError('Invalid resource decision')
    resource=value['resource']; steps=value['steps']
    if resource not in projection.get('allowed_resources',ACTIONABLE) or resource in projection['unavailable'] or 'prepare_report' in steps and not supports(resource,'bounded-report'):
        raise ValueError('The proposed route does not meet the task constraints')
    item=next(r for r in projection['inventory']['resources'] if r['name']==resource)
    name={'codex':'Codex','cursor':'Cursor','claude':'Claude','gemini':'Gemini','minimax':'MiniMax'}[resource]
    parts=[]
    if projection['scenario']:
        parts.append('In that scenario, ')
    else:
        parts.append('My recommendation: ')
    missing=projection['missing_inputs']
    first=steps[0]
    if missing:
        parts.append('prepare the smallest relevant project-file snapshot and acceptance criteria before asking '+name+' for a substantive answer. ')
        parts.append('Without those inputs, it can help outline the questions and checks, but cannot verify the project. ')
    elif first=='prepare_report':
        parts.append('use '+name+'’s supported bounded report route with a small evidence snapshot and a clear deliverable. ')
    elif first=='keep_current':
        parts.append('keep the current qualified answer route while testing a subscription route on a representative task. ')
    elif first=='inspect_allowance':
        parts.append('check '+name+'’s current sign-in, remaining allowance and extra-usage settings before admitting a bounded task. ')
    elif first=='review_dependency':
        parts.append('check the linked Cursor/Grok allowance and actual use before changing a subscription. ')
    elif first=='provide_inputs':
        parts.append('prepare the relevant files, current constraints and acceptance criteria for one bounded '+name+' task. ')
    else:
        parts.append('qualify '+name+' on one representative question using the same evidence and quality criteria as the strong current route. ')
    if missing or 'qualify_chat' in steps[1:]:
        parts.append('Then compare its answer against those criteria before changing the default. ')
    elif 'provide_inputs' in steps[1:]:
        parts.append('Supply the relevant file snapshot and acceptance criteria first. ')
    obs=item['observation']
    fresh=obs.get('freshness')=='recent'
    if resource in ('codex','cursor','claude'):
        auth='Its sign-in was observed recently' if fresh and obs.get('authenticated') is True else 'First verify its supported subscription sign-in'
        parts.append(auth+'; the chat adapter uses supplied context, while file access depends on the separate task route. ')
    else:
        parts.append(name+' is a separately metered API route, so an existing chat subscription does not fund it. ')
    unknown=[]
    if not fresh or obs.get('remaining_usage') is None:unknown.append('remaining allowance')
    if not fresh or obs.get('extra_usage') is None:unknown.append('possible extra charges')
    measured=obs.get('quality_evidence')
    if not fresh or not isinstance(measured,dict) or measured.get('qualified') is not True or measured.get('task')!='conversation':
        unknown.append('comparable answer quality')
    if unknown:
        parts.append('Unverified: '+', '.join(unknown)+'. ')
    parts.append('Preserve the quality bar, stop at observed limits, and change no purchase or plan settings.')
    return ''.join(parts).strip(),dict(resource=resource,steps=steps,missing_inputs=missing,
                                    scenario=projection['scenario'],execution_started=False,
                                    observation_time=projection['inventory']['observed_at'])
