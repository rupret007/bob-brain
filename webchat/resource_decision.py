"""Evidence-owned resource facts, model-selected bounded recommendations.

Advice does not change routing or enqueue work. The model chooses supported
actions; authentication, reach, quota, quality and billing assertions are rendered
from the same capability registry and observed evidence used by the product.
"""
import json
import re
import hashlib

import resource_inventory
from resource_capabilities import ROUTES, CAPABILITIES, supports, BILLING_FACTS

RESOURCE_NAMES = r'\b(?:'+'|'.join(ROUTES)+r')\b'
ACTIONABLE = tuple(name for name in ROUTES if supports(name,'conversation'))

STEPS = ('qualify_chat','prepare_report','provide_inputs','inspect_allowance','keep_current','review_dependency')
RULES = '''Answer the current question directly, including disagreement when warranted.
Return one JSON object with exactly answer, resource, steps. answer is natural
prose composed for this turn, not a routing receipt. Write the complete answer
in your own words and cite its evidence as [fact:ID] from the supplied facts
map; use at least one relevant citation. These references identify evidence;
they are not sentence placeholders. Explain the tradeoffs and reasoning. Do not restate
unknown account facts as verified or infer guarantees from login, pacing or price.
resource is null when no provider is selected, or codex/cursor/claude/gemini/minimax
for a recommendation. steps is an empty list or up to three distinct
choices: qualify_chat, prepare_report, provide_inputs, inspect_allowance,
keep_current, review_dependency. Describe the useful proposed next step in answer;
these fields neither start it nor change routing. prepare_report supports Claude
only; qualify_chat needs a selected provider. General inspection/preparation
steps do not require a provider selection. A billing premise needs an answer, not an
unrequested recommendation. On follow-up, advance the reasoning rather than
repeating the last answer. Preserve missing inputs and explicit route restrictions.
Use only needed facts; do not paste the whole inventory or all caveats. No invented
inspection, execution, file reach, remaining allowance, free usage or equal-quality
guarantees. Supported operations are independent: report-executor restrictions
never remove a provider's separate conversation adapter. An unqualified alternative
is a candidate for a bounded comparison, not yet the recommended active chat route.
When explaining a limitation, name the operation and adapter it applies to; do
not turn a chat adapter's tool boundary into a denial of its scoped executor.
Not buying another plan is distinct from incurring no charges: a comparison uses
allowance and may trigger extra usage under unknown account settings. Preparing
inputs or checking settings is not evidence that future generation is cost-free.
Return JSON only, without fences or trailing commentary.
'''

FACT_TOKEN = re.compile(r'\[fact:([a-z0-9_.]+)\]')


def facts(inventory, *, missing=False):
    """Versioned public rules and current registry evidence, not model assertions."""
    result = {
        'openai_api_billing': BILLING_FACTS['openai_api_billing'],
        'subscription_scope': BILLING_FACTS['subscription_scope'],
        'route_boundaries': 'Web Bob supports BOTH Codex/Cursor conversation adapters using supplied context AND their separate scoped executors for assigned local file/coding work. Tool limits apply to the named adapter, not the whole resource. Voice and images require their own supported operation. Signing in does not make routes interchangeable or authorize file work.',
        'quality_bar': 'Keep the qualified answer route and its reasoning settings until a representative comparison establishes the alternative’s quality. A cheaper price or successful login does not establish equivalent answers.',
        'capacity_and_pacing': 'Pacing may reduce demand; it cannot establish remaining allowance or prevent quota exhaustion. Capacity and extra-usage settings need current observations before admission.',
        'purchase_vs_usage': 'An existing subscription avoids purchasing another plan; it does not establish that another model invocation has no incremental charge. Extra-usage settings and remaining allowance are unverified until observed. Prepare evidence and inspect settings before admitting a comparison.',
        'manual_handoff': 'Dot and Grok have prepared handoff paths, but no verified automatic Web Bob push/acceptance interface. Preparation alone does not establish native execution.',
    }
    if missing:
        result['missing_inputs']='With the needed project inputs unavailable, project-specific conclusions remain unverified. The cause of missing access is not established; obtain a bounded evidence snapshot through a supported permitted read or owner-supplied material.'
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
    from structured_reply import loads
    value=loads(raw)
    if isinstance(value,dict) and isinstance(value.get('answer'),str):
        # Citation lists are equivalent to separate citations, not extra prose.
        grouped=re.compile(r'\[fact:([a-z0-9_.]+(?:\s*,\s*(?:fact:)?[a-z0-9_.]+)+)\]')
        value['answer']=grouped.sub(lambda m: ''.join('[fact:'+part.strip().removeprefix('fact:')+']'
                                      for part in m[1].split(',')),value['answer'])
    return value


def model_evidence(projection):
    """Task-relevant capabilities and observed facts, without stale raw balances.

    The complete inventory remains bound in the saved contract. Conversation
    does not need billing caches, duplicate routes or unrelated worker policies.
    """
    return {**{k:projection[k] for k in ('requested_view','requested_resources','allowed_resources',
                                       'scenario','missing_inputs','unavailable','facts')},
            'supported_operations':{name:sorted(values) for name,values in CAPABILITIES.items()},
            'observed_at':projection['inventory']['observed_at'],
            'authority':'Evidence for advice only; neither provider selection nor execution authorization.'}


def safe_reasoning(text):
    """Bounded assertion checks; evidence links cannot excuse adjacent claims.

    This is not a proof of arbitrary factual correctness. Only a directly
    negated assertion is exempt; unknowns elsewhere do not validate a promise.
    """
    from reply_contract import safe_artifact
    prose=FACT_TOKEN.sub('',text)
    if not safe_artifact(prose):return False
    guarantee=re.compile(r"\b(?:guarantee[ds]?|unlimited|free|zero[- ]cost|no (?:extra |additional )?(?:costs?|charges?)|same quality|equal quality|equivalent (?:quality|answers)|(?:quality|quota|allowance) (?:is|stays|remains) (?:protected|unchanged)|(?:preserve[ds]?|protect(?:s|ed)?|maintain(?:s|ed)?|(?:is|are|was|were|will be) (?:preserving|protecting|maintaining)) (?:the |your )?(?:quality|quota|allowance)|(?:avoid|prevent)(?:s|ed|ing)? (?:quota exhaustion|exhaustion|rate limits?|extra charges)|will not (?:cost|exhaust|run out)|won[’']t (?:cost|exhaust|run out))\b",re.I)
    observed=re.compile(r"\b(?:I|we|Codex|Claude|Cursor|Gemini|MiniMax)(?:['’]ve| have)? (?:checked|verified|confirmed|inspected|tested|read)\b|\b(?:can|could|will) (?:already |now )?(?:read|access|open) (?:all |your |the |those |needed |project )*(?:files?|repository|repo)\b|\b(?:remaining|available) (?:quota|allowance|credits?) (?:is|are)\b",re.I)
    direct_denial=re.compile(r"\b(?:cannot|can['’]t|does not|doesn['’]t|is not|isn['’]t|not|no)\s+(?:(?:be|a|an|any|necessarily|ever|actually|guarantee|establish|imply|prove)\s+){0,3}$",re.I)
    scoped_denial=re.compile(r"\b(?:cannot assume|can['’]t assume|(?:does not|doesn['’]t) (?:make|imply|establish|prove)|no proof of|no evidence of|rather than (?:assuming|inferring)|without (?:assuming|claiming|promising))\b(?:(?!\b(?:guarantee[ds]?|ensures?|therefore|since|because)\b)[^,;:.!?]){0,90}$",re.I)
    inquiry=re.compile(r'\b(?:whether|to (?:check|test|compare|assess|verify|measure|evaluate|qualify)|(?:should|must|need to) (?:check|test|compare|assess|verify|measure|evaluate|qualify))\b[^,;:.!?]{0,70}$',re.I)
    contrast=re.compile(r'\brather than\s+(?:(?:being|offering|providing|an?|any|completely|truly)\s+){0,3}$',re.I)
    clauses=re.split(r'((?<=[.!?])\s+|[,;\n]|\b(?:and|but|however|therefore|so|thus|although|yet|whereas|because|since)\b)',prose,flags=re.I)
    for index in range(0,len(clauses),2):
        clause=clauses[index]
        sentence_start=index==0 or (clauses[index-1].isspace() and clauses[index-2].rstrip().endswith(('.','!','?')))
        for match in guarantee.finditer(clause):
            prefix=clause[:match.start()]
            # A test/comparison noun never establishes a guarantee. Negation
            # must attach to that promise itself, not an unrelated condition.
            if match[0].lower().startswith('guarantee'):
                if not (direct_denial.search(prefix) or scoped_denial.search(prefix)):return False
            elif (sentence_start and re.match(r'^(?:preserve|protect|maintain) ',match[0],re.I) and
                  re.fullmatch(r'\s*(?:to\s+)?',prefix,re.I)):
                continue  # Imperative/topic objective, not an asserted outcome.
            elif not (direct_denial.search(prefix) or scoped_denial.search(prefix) or contrast.search(prefix) or inquiry.search(prefix)):
                return False
        for match in observed.finditer(clause):
            if not direct_denial.search(clause[:match.start()]):return False
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
        if (not tokens or any(t not in known for t in tokens) or
                '[fact:' in FACT_TOKEN.sub('',value['answer']) or not safe_reasoning(value['answer'])):
            raise ValueError('Ungrounded answer composition')
        bare=FACT_TOKEN.sub('',value['answer']).strip(' .,:;\n')
        if not bare:
            content='\n\n'.join(known[t] for t in dict.fromkeys(tokens))
        else:
            links={'openai_api_billing':'[OpenAI pricing](https://learn.chatgpt.com/docs/pricing)',
                   'subscription_scope':'[OpenAI pricing](https://learn.chatgpt.com/docs/pricing)'}
            linked=set()
            def citation(match):
                link=links.get(match[1],'')
                if link in linked:return ''
                linked.add(link);return link
            content=FACT_TOKEN.sub(citation,value['answer']).strip()
            content=re.sub(r' +([.,;:])',r'\1',content)
            content=re.sub(r' {2,}',' ',content)
        if not content:raise ValueError('Empty composed answer')
        resource=value['resource']
        if resource is None:
            steps=value['steps']
            if (not isinstance(steps,list) or len(steps)>3 or
                    any(not isinstance(s,str) or s not in ('provide_inputs','inspect_allowance','keep_current','review_dependency') for s in steps) or
                    len(set(steps))!=len(steps)):
                raise ValueError('Invalid general advice steps')
            if projection['missing_inputs']:
                content+='\n\n'+known['missing_inputs']
            return content,dict(resource=None,steps=steps,fact_ids=tokens,execution_started=False,model_proposal_accepted=True,acceptance_scope='schema and bounded claim checks; not semantic certification')
        validate_route(resource,value['steps'],projection,empty=True)
        decision=dict(resource=resource,missing_inputs=projection['missing_inputs'],scenario=projection['scenario'],
                      execution_started=False,observation_time=projection['inventory']['observed_at'])
        if projection['missing_inputs']:
            content+='\n\n'+known['missing_inputs']
        if resource in ('codex','claude','cursor'):
            content+='\n\n'+known[resource+'.observation']
        decision.update(steps=value['steps'],fact_ids=tokens,model_proposal_accepted=True,acceptance_scope='schema and bounded claim checks; not semantic certification')
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
