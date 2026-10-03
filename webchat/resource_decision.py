"""Evidence-owned resource facts, model-selected bounded recommendations.

Advice does not change routing or enqueue work. The model chooses supported
actions; authentication, reach, quota, quality and billing assertions are rendered
from the same capability registry and observed evidence used by the product.
"""
import json
import re
import hashlib

import resource_inventory
from resource_capabilities import ROUTES, supports, BILLING_FACTS

RESOURCE_NAMES = r'\b(?:'+'|'.join(ROUTES)+r')\b'
ACTIONABLE = tuple(name for name in ROUTES if supports(name,'conversation'))

STEPS = ('qualify_chat','prepare_report','provide_inputs','inspect_allowance','keep_current','review_dependency')
RULES = '''Answer the current question directly, including disagreement when warranted.
Return one JSON object with exactly answer, resource, steps. answer is natural
prose composed for this turn, not a routing receipt. Insert server-owned facts
as [fact:ID] using the supplied facts map; use at least one relevant fact. Explain
tradeoffs and reasoning in your own words around those facts. Do not restate
unknown account facts as verified or infer guarantees from login, pacing or price.
resource is null for an explanation, or codex/cursor/claude/gemini/minimax for an
actual recommendation. steps is an optional empty list or up to three distinct
choices: qualify_chat, prepare_report, provide_inputs, inspect_allowance,
keep_current, review_dependency. Describe the useful proposed next step in answer;
these fields neither start it nor change routing. prepare_report supports Claude
only. A question about a billing premise needs an answer to that premise, not an
unrequested recommendation. On follow-up, advance the reasoning rather than
repeating the last answer. Preserve missing inputs and explicit route restrictions.
Use only needed facts; do not paste the whole inventory or all caveats. No invented
inspection, execution, file reach, remaining allowance, free usage or equal-quality
guarantees. Return JSON only, without fences or trailing commentary.
'''

FACT_TOKEN = re.compile(r'\[fact:([a-z0-9_.]+)\]')


def facts(inventory, *, missing=False):
    """Versioned public rules and current registry evidence, not model assertions."""
    result = {
        'openai_api_billing': BILLING_FACTS['openai_api_billing'],
        'subscription_scope': BILLING_FACTS['subscription_scope'],
        'route_boundaries': 'Web Bob’s Codex and Cursor chat adapters use supplied context. Local file work uses a separate scoped executor; voice, images and other tools depend on the particular adapter. Signing in does not make those routes interchangeable.',
        'quality_bar': 'Keep the qualified answer route and its reasoning settings until a representative comparison establishes the alternative’s quality. A cheaper price or successful login does not establish equivalent answers.',
        'manual_handoff': 'Dot and Grok have prepared handoff paths, but no verified automatic Web Bob push/acceptance interface. Preparation alone does not establish native execution.',
    }
    if missing:
        result['missing_inputs']='The needed project files are still missing. A bounded evidence snapshot can make the next task useful; without it, project-specific findings cannot be verified.'
    for item in inventory['resources']:
        name=item['name'];obs=item['observation'];fresh=obs.get('freshness')=='recent'
        result[name+'.reach']=item['reach']
        result[name+'.billing']=item['billing']+'.'
        auth=('Sign-in was observed recently' if fresh and obs.get('authenticated') is True else 'Current sign-in is unverified')
        unknown=[]
        if not fresh or obs.get('remaining_usage') is None:unknown.append('remaining allowance')
        if not fresh or obs.get('extra_usage') is None:unknown.append('possible extra charges')
        measured=obs.get('quality_evidence')
        if not fresh or not isinstance(measured,dict) or measured.get('qualified') is not True or measured.get('task')!='conversation':unknown.append('comparable answer quality')
        result[name+'.observation']=auth+('. Unverified: '+', '.join(unknown) if unknown else '. Recent evidence is limited to the recorded task and observation time')+'.'
    return result


def parse(raw):
    # A single fenced JSON value is presentation noise, not permission for
    # appended prose or a second packet to escape validation.
    fenced=re.fullmatch(r'\s*```(?:json)?\s*\n(.*?)\n```\s*',raw,re.S)
    return json.loads(fenced[1] if fenced else raw)


def safe_reasoning(text):
    """Bounded assertion checks; evidence links cannot excuse adjacent claims.

    This is not a proof of arbitrary factual correctness. Only a directly
    negated assertion is exempt; unknowns elsewhere do not validate a promise.
    """
    from reply_contract import safe_artifact
    prose=FACT_TOKEN.sub('',text)
    if not safe_artifact(prose):return False
    guarantee=re.compile(r"\b(?:guarantee[ds]?|unlimited|free|zero[- ]cost|no (?:extra |additional )?(?:costs?|charges?)|same quality|equal quality|equivalent (?:quality|answers)|(?:quality|quota|allowance) (?:is|stays|remains) (?:protected|unchanged)|(?:preserv|protect|maintain)(?:e[ds]?|ing) (?:the |your )?(?:quality|quota|allowance)|(?:avoid|prevent)(?:s|ed|ing)? (?:exhaustion|rate limits?|extra charges)|will not (?:cost|exhaust|run out)|won[’']t (?:cost|exhaust|run out))\b",re.I)
    observed=re.compile(r"\b(?:I|we|Codex|Claude|Cursor|Gemini|MiniMax)(?:['’]ve| have)? (?:checked|verified|confirmed|inspected|tested|read)\b|\b(?:can|could|will) (?:already |now )?(?:read|access|open) (?:all |your |the |those |needed |project )*(?:files?|repository|repo)\b|\b(?:remaining|available) (?:quota|allowance|credits?) (?:is|are)\b",re.I)
    negation=re.compile(r"\b(?:cannot|can['’]t|does not|doesn['’]t|is not|isn['’]t|not|no proof of|no evidence of|no)\s+(?:(?:be|a|any|necessarily|guarantee|establish|imply|prove)\s+){0,3}$",re.I)
    for clause in re.split(r'(?<=[.!?])\s+|[;\n]|\b(?:and|but|however|therefore|so|thus|although|yet|whereas)\b',prose,flags=re.I):
        for match in guarantee.finditer(clause):
            if not negation.search(clause[:match.start()]):return False
        for match in observed.finditer(clause):
            if not negation.search(clause[:match.start()]):return False
    return True


def validate_route(resource,steps,projection,*,empty=False):
    if (resource not in ACTIONABLE or not isinstance(steps,list) or
            not (0 if empty else 1)<=len(steps)<=3 or
            any(not isinstance(s,str) or s not in STEPS for s in steps) or len(set(steps))!=len(steps)):
        raise ValueError('Invalid resource decision')
    if (resource not in projection.get('allowed_resources',ACTIONABLE) or resource in projection['unavailable'] or
            'prepare_report' in steps and not supports(resource,'bounded-report')):
        raise ValueError('The proposed route does not meet the task constraints')


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
    inventory=resource_inventory.observe(root)
    return dict(version=2,inventory=inventory,facts=facts(inventory,missing=missing),
        owner_sources=[dict(request_id=m['request_id'],sha256=hashlib.sha256(m['text'].encode()).hexdigest()) for m in scope],
        requested_view=view,requested_resources=named,allowed_resources=sorted(restricted) if restricted else list(ACTIONABLE),
        scenario=bool(re.search(r'\b(?:suppose|scenario|what if)\b',source,re.I)),
        missing_inputs=missing,unavailable=sorted(unavailable))


def render(raw, projection):
    """Compose grounded facts and checked reasoning; advice creates no effects."""
    value=parse(raw)
    modern=isinstance(value,dict) and set(value)=={'answer','resource','steps'}
    if not modern and projection.get('requested_view') in ('comparison','inventory'):
        names=projection.get('requested_resources') or list(ROUTES)
        rows=['| Resource | Supported use | Billing / evidence |','|---|---|---|']
        for item in projection['inventory']['resources']:
            if item['name'] not in names:continue
            observed=item['observation']
            auth=(str(observed.get('plan') or observed.get('auth_mode'))+' observed; ' if observed.get('freshness')=='recent' and observed.get('authenticated') is True else 'Current sign-in/plan unverified; ')
            rows.append('| '+item['name'].title()+' | '+', '.join(item['tasks'])+' | '+auth+item['billing']+' |')
        return '\n'.join(rows)+'\n\nThese are supported routes, not a verified subscription invoice. Login alone establishes neither remaining capacity nor comparative answer quality; use a matched task before changing the default.',dict(view=projection['requested_view'],execution_started=False)
    if modern:
        if not isinstance(value['answer'],str) or not 1<=len(value['answer'])<=7000:
            raise ValueError('Invalid answer composition')
        tokens=FACT_TOKEN.findall(value['answer'])
        known=projection.get('facts') or facts(projection['inventory'],missing=projection['missing_inputs'])
        if not tokens or any(t not in known for t in tokens) or not safe_reasoning(value['answer']):
            raise ValueError('Ungrounded answer composition')
        content=FACT_TOKEN.sub(lambda m:known[m[1]],value['answer']).strip()
        resource=value['resource']
        if resource is None:
            if value['steps']!=[]:raise ValueError('Explanation cannot select actions')
            if projection['missing_inputs'] and 'missing_inputs' not in tokens:
                content+='\n\n'+known['missing_inputs']
            return content,dict(resource=None,steps=[],fact_ids=tokens,execution_started=False,model_proposal_accepted=True)
        validate_route(resource,value['steps'],projection,empty=True)
        decision=dict(resource=resource,missing_inputs=projection['missing_inputs'],scenario=projection['scenario'],
                      execution_started=False,observation_time=projection['inventory']['observed_at'])
        if projection['missing_inputs'] and 'missing_inputs' not in tokens:
            content+='\n\n'+known['missing_inputs']
        if resource+'.observation' not in tokens:
            content+='\n\n'+known[resource+'.observation']
        decision.update(steps=value['steps'],fact_ids=tokens,model_proposal_accepted=True)
        return content,decision
    if not isinstance(value,dict) or set(value)!= {'resource','steps'}:
        raise ValueError('Invalid resource decision')
    resource=value['resource'];steps=value['steps']
    validate_route(resource,steps,projection)
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
