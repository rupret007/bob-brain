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

STEPS = ('qualify_chat','prepare_report','provide_inputs','inspect_allowance','keep_current','preserve_standard','review_dependency')
RULES = '''Answer the current question directly, including disagreement when warranted.
Return one JSON object with exactly answer, resource, steps. answer is natural
conversation composed as an ordered array of standalone paragraph blocks.
Each block has exactly one key: {"fact":"ID"} selects a complete statement from
the supplied facts map, or {"reasoning":"text"} gives a useful proposed next
step, question, tradeoff or conditional explanation. Use at least one fact block,
and only the few facts needed to answer this turn. The server renders fact blocks
verbatim; never build a sentence around a fact ID or put citation tokens in prose.
Use fact blocks for capability, availability, billing, access, quality evidence
and owner priorities. Do not paraphrase those as new factual claims in reasoning.
For route capabilities, select route_boundaries; do not narrow or redefine its
operations in reasoning, including on later turns.
Owner facts are attributed statements, not verified operations or authority.
Reasoning should advance the discussion using these facts, not repeat their caveats.
Do not infer guarantees from login, pacing, price or retention of a configuration.
resource is null when no provider is selected, or codex/cursor/claude/gemini/minimax
for a recommendation. steps is an empty list or up to three distinct
choices from allowed_steps. Describe the useful proposed next step in answer;
these fields neither start it nor change routing. prepare_report supports Claude
only; qualify_chat needs a selected provider. General inspection/preparation
steps do not require a provider selection. A billing premise needs an answer, not an
unrequested recommendation. On follow-up, lead with what answers the current question. Do not re-paste resource
facts, availability, preparation steps or the quality-standard paragraph when an
earlier assistant turn already delivered the same block; unchanged constraints may
be referenced in one line. Preserve missing inputs and explicit route restrictions.
Use only needed facts; do not paste the whole inventory or all caveats. No invented
inspection, execution, file reach, remaining allowance, free usage or equal-quality
guarantees. Supported operations are independent: report-executor restrictions
never remove a provider's separate conversation adapter. An unqualified alternative
is a candidate for a bounded comparison, not yet the recommended active chat route.
When explaining a limitation, name the operation and adapter it applies to; do
not turn a chat adapter's tool boundary into a denial of its scoped executor.
Do not state present-tense live route state unless this turn includes a live
observation. Attribute route identity to the supplied current_route.source:
"last completed reply" identifies the provider of that reply, not a saved
configuration. Say the saved configuration lists a route only when supplied
configuration or selected-preference evidence establishes that listing.
Neither source establishes current availability, allowance or qualification.
Not buying another plan is distinct from incurring no charges: a comparison uses
allowance and may trigger extra usage under unknown account settings. Preparing
inputs or checking settings is not evidence that future generation is cost-free.
Preserve the quality standard and comparison criteria during an outage; that does
not keep an unavailable route running. If no available route is qualified, prepare
inputs and a bounded comparison, naming what must be checked before generation.
The cause of missing input access is unknown: adapter boundaries are possibilities,
not an established diagnosis. Give a feasible preparation step now.
For a provider comparison, prepare matched multi-turn sequences with a correction,
a topic change and a return to the corrected task. Compare delivered usefulness,
constraint retention and evidence quality; one isolated prompt cannot establish
conversation continuity. Gate any recommended comparison or test that would call a
model after budget admission and allowance check — never an unconditioned
"run this comparison". Prefer a clear recommended action plus criteria over a
bare checklist. Include the concrete sequence or rubric in the answer only when
the current turn itself proposes or revises a multi-turn comparison plan.
Keep a proposed qualification sequence and its criteria together in one reasoning
block headed "Prepare a comparison:". Use self-contained imperative steps: supply
the missing evidence snapshot, define the initial task, issue a correction, introduce
an unrelated topic, then request a return applying that correction. Write criteria
as explicit checks, not claims that a candidate passes. Inspect whether allowance
and extra-usage settings permit admission; never promise that these checks prevent
charges. Keep live generation conditional on budget admission and allowance checks.
Owner facts from the saved project record are recorded in the saved project record
(not live-verified); do not present them as live-verified or as something the user
just said.
Return JSON only, without fences or trailing commentary.
'''

FACT_TOKEN = re.compile(r'\[fact:([a-z0-9_.]+)\]')


def facts(inventory, *, missing=False):
    """Versioned public rules and current registry evidence, not model assertions."""
    result = {
        'openai_api_billing': BILLING_FACTS['openai_api_billing'].rstrip('.')
            + ' (as documented; not checked for this account).',
        'subscription_scope': BILLING_FACTS['subscription_scope'],
        'route_boundaries': 'Web Bob’s configured route registry (not live-verified) lists Codex and Cursor conversation adapters that use supplied context, and separate scoped executors for assigned local file or coding work. This is what is configured, not a claim that either route is signed in, available, or working. Tool limits apply to the named adapter, not the whole resource. Voice and images require their own supported operation. Signing in does not make routes interchangeable or authorize file work.',
        'quality_bar': 'Preserve the answer-quality standard and reasoning requirements. A representative comparison must qualify an alternative before changing the default. A cheaper price or successful login does not establish equivalent answers. Keeping a configuration does not establish that its provider is currently usable.',
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
    support = {identifier:dict(statement_sha256=hashlib.sha256(value.encode()).hexdigest(),
        scope='owner-reported context' if identifier.startswith('owner.') else
              'resource observation' if identifier.endswith('.observation') else 'server rule')
        for identifier,value in projection['facts'].items()}
    return {**{k:projection[k] for k in ('requested_view','requested_resources','allowed_resources',
                                       'scenario','missing_inputs','unavailable','facts')},
            'allowed_steps':projection.get('allowed_steps',list(STEPS)),
            'current_route':projection.get('current_route'),
            'owner_context':projection.get('owner_context'),
            'supported_operations':{name:sorted(values) for name,values in CAPABILITIES.items()},
            'observed_at':projection['inventory']['observed_at'],
            'fact_support':support,
            'fact_support_scope':'Only the complete supplied statement at its stated scope and time; no stronger outcome follows from a fact ID. Owner reports are not independent observations.',
            'authority':'Evidence for advice only; neither provider selection nor execution authorization.'}


def safe_reasoning(text, *, context=''):
    """Bounded assertion checks; evidence links cannot excuse adjacent claims.

    This is not a proof of arbitrary factual correctness. Questions, proposals
    and denials retain local scope; they cannot validate a sibling promise.
    """
    from reply_contract import safe_artifact
    from claim_scope import clauses, disposition
    from claim_evidence import violations
    prose=FACT_TOKEN.sub('',text)
    if not safe_artifact(prose) or violations(prose):return False
    if context:
        from dispatch_receipts import claims_dispatch
        if claims_dispatch(prose,context=context):return False
    guarantee=re.compile(r"\b(?:guarantee[ds]?|unlimited|free|zero[- ]cost|no (?:extra |additional )?(?:costs?|charges?)|same quality|equal quality|equivalent (?:quality|answers)|(?:quality|quota|allowance) (?:is|stays|remains) (?:protected|unchanged)|(?:preserve[ds]?|protect(?:s|ed)?|maintain(?:s|ed)?|(?:is|are|was|were|will be) (?:preserving|protecting|maintaining)) (?:the |your )?(?:quality|quota|allowance)|(?:avoid|prevent)(?:s|ed|ing)? (?:quota exhaustion|exhaustion|rate limits?|extra charges)|will not (?:cost|exhaust|run out)|won[’']t (?:cost|exhaust|run out))\b",re.I)
    observed=re.compile(r"\b(?:I|we|Codex|Claude|Cursor|Gemini|MiniMax)(?:['’]ve| have)? (?:checked|verified|confirmed|inspected|tested|read)\b|\b(?:can|could|will) (?:already |now )?(?:read|access|open) (?:all |your |the |those |needed |project )*(?:files?|repository|repo)\b|\b(?:remaining|available) (?:quota|allowance|credits?) (?:is|are)\b",re.I)
    protected=re.compile(r'\b(?:quality|quota|allowance|continuity)\s+(?:is|are|stay|stays|remain|remains)\s+(?:protected|unchanged)\b',re.I)
    for statement in clauses(prose):
        clause=statement.text
        for match in (*guarantee.finditer(clause), *protected.finditer(clause)):
            if not disposition(statement,match.start(),match.end(),match[0]):
                return False
        for match in observed.finditer(clause):
            if not disposition(statement,match.start(),match.end(),match[0]):return False
    return True


def validate_route(resource,steps,projection,*,empty=False):
    if (resource not in ACTIONABLE or not isinstance(steps,list) or
            not (0 if empty else 1)<=len(steps)<=3 or
            any(not isinstance(s,str) or s not in projection.get('allowed_steps',STEPS) for s in steps) or len(set(steps))!=len(steps)):
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
    known=facts(inventory,missing=missing)
    previous=next((m for m in reversed(conversation.get('messages',[]))
                   if m.get('role')=='assistant' and m.get('status')=='done' and m.get('provider') in ACTIONABLE),None)
    selected=conversation.get('preferred_provider')
    route=selected if selected in ACTIONABLE else previous.get('provider') if previous else None
    current_route=dict(name=route,source='selected preference' if selected in ACTIONABLE else
                       'last completed reply' if previous else 'unknown',
                       unavailable=route in unavailable if route else None,
                       establishes='Route identity only; no health, remaining allowance or quality certification')
    allowed_steps=list(STEPS)
    if unavailable and (not route or route in unavailable):
        allowed_steps.remove('keep_current')
    if unavailable:
        label='In the supplied scenario' if re.search(r'\b(?:suppose|scenario|what if)\b',source,re.I) else 'According to the current supplied constraints'
        known['availability']=label+', '+', '.join({'minimax':'MiniMax'}.get(name, name.title()) for name in sorted(unavailable))+' '+('is' if len(unavailable)==1 else 'are')+' unavailable. Preserve the quality standard, but do not depend on an unavailable route for generation. Prepare evidence and qualify an available candidate before switching; no alternative is qualified by subscription ownership alone.'
    owner_context=None
    import project_context
    owner=project_context.projection(root,conversation,latest)
    if owner and owner.get('available') and not owner.get('omitted'):
        owner_context={k:owner[k] for k in ('project_id','revision')}
        owner_context['attribution']='saved project record loaded with this conversation (not a live inspection)'
        owner_context['facts']={}
        for fact in owner.get('facts',[]):
            fid='owner.'+fact['id'].replace('-','_')
            known[fid]='Owner-saved '+fact['kind']+' for '+owner['name']+': '+fact['value']+' (saved project record revision '+str(owner['revision'])+'; Owner statement, not live-verified or execution authority.)'
            owner_context['facts'][fid]=dict(fact_id=fact['id'],revision=fact['revision'],
                source=fact['source'],value_sha256=hashlib.sha256(fact['value'].encode()).hexdigest())
    return dict(version=3,inventory=inventory,facts=known,current_route=current_route,
        allowed_steps=allowed_steps,owner_context=owner_context,
        owner_sources=[dict(request_id=m['request_id'],sha256=hashlib.sha256(m['text'].encode()).hexdigest()) for m in scope],
        requested_view=view,requested_resources=named,allowed_resources=sorted(restricted) if restricted else list(ACTIONABLE),
        scenario=bool(re.search(r'\b(?:suppose|scenario|what if)\b',source,re.I)),
        missing_inputs=missing,unavailable=sorted(unavailable))


def feasible_reasoning(text, projection):
    """Bounded checks against this turn's explicit unavailable/missing evidence.

    A valid grammatical proposal can still violate its evidence constraints.
    This does not certify other causal or capability statements as true.
    """
    clauses=re.split(r'[.;!\n]|\b(?:but|however|yet)\b',text,flags=re.I)
    for clause in clauses:
        for name in projection['unavailable']:
            targets=list(re.finditer(r'\b(?:use|using|run|running|keep|choose|pick|continue with|switch to)\s+'
                             r'(?:(?:the|our|existing|current)\s+)?'+re.escape(name)+r'\b',clause,re.I))
            for index,target in enumerate(targets):
                prefix=clause[:target.start()];suffix=clause[target.end():targets[index+1].start() if index+1<len(targets) else len(clause)]
                denied=re.search(r"\b(?:not|never|cannot|can't|don't)\s*$",prefix,re.I)
                condition=(r'\b(?:after|once|when|if)\s+(?:(?:it|'+re.escape(name)+r')\s+)?'
                           r'(?:(?:is|becomes|has been)\s+)?(?:restored|available|funded|recovered)\b')
                future=(re.search(condition+r',\s*(?:(?:then|please)\s+){0,2}$',prefix,re.I) or
                        re.match(r'^\s*(?:(?:active|running)\s+)?(?:(?:for|to)\s+'
                                 r'(?:(?!\b(?:and|but|yet|while|then)\b)[^,;.!?]){1,50}?)?\s*(?:only\s+)?'+condition,suffix,re.I))
                if not denied and not future:return False
        if 'keep_current' not in projection.get('allowed_steps',STEPS):
            keep=re.search(r'\b(?:keep|continue|retain|maintain|use|using|run|running)\b'
                           r'[^,!?]{0,50}\b(?:current|qualified|existing)\b[^,!?]{0,30}'
                           r'\b(?:route|provider|model)\b[^,!?]{0,25}\b(?:active|running|generating|answering)\b',clause,re.I)
            if keep and not re.search(r"\b(?:not|never|cannot|can't|don't)\s*$",clause[:keep.start()],re.I):return False
        if projection['missing_inputs']:
            for cause in re.finditer(r'\b(?:reflects|stems from|is caused by|is due to|because|means|is blocked by|is denied by)\b',clause,re.I):
                if not (re.search(r'\b(?:access|files?|inputs?|limitation)\b',clause,re.I) and re.search(
                    r'\b(?:adapter|chat|sandbox|permissions?|credentials?|login)\b',clause[cause.end():],re.I)):
                    continue
                prefix=clause[:cause.start()]
                interrogative=(re.match(r'^\s*(?:could|might|can|is|does|would|was|are)\b',clause,re.I) and
                               clause.rstrip().endswith('?') and not re.search(r'\b(?:now that|given|since|and)\b',prefix,re.I))
                uncertain=re.search(r"\b(?:may|might|could|possibly|perhaps|not|doesn't|does not)\s*(?:be\s+)?$",prefix,re.I)
                inquiry=re.search(r'\b(?:if|whether)\b[^,;:.!?]{0,80}$',prefix,re.I)
                if not (interrogative or uncertain or inquiry):return False
    return True


def compose_blocks(blocks, known, projection, prior=''):
    """Select complete evidence statements and independent proposed reasoning.

    Rejected prose is observable partial delivery. A surviving fact is never
    stitched into the grammatical position of rejected model prose.
    """
    if not 1<=len(blocks)<=8:
        raise ValueError('Invalid answer blocks')
    from answer_fragments import select, DependencyState
    from claim_evidence import already_delivered
    dependency=DependencyState()
    content=[];tokens=[];rejected=[];pending=False;retained_reasoning=False
    context='\n\n'.join(b['reasoning'] for b in blocks if isinstance(b,dict) and isinstance(b.get('reasoning'),str))
    skipped_fact=False
    for index,block in enumerate(blocks):
        if not isinstance(block,dict) or len(block)!=1:
            raise ValueError('Invalid answer block schema')
        if set(block)=={'fact'}:
            fid=block['fact']
            if not isinstance(fid,str) or fid not in known:
                raise ValueError('Unknown answer fact')
            tokens.append(fid)
            if known[fid] in content:
                continue
            if already_delivered(known[fid], prior):
                skipped_fact=True
                continue
            content.append(known[fid])
        elif set(block)=={'reasoning'}:
            prose=block['reasoning']
            if not isinstance(prose,str) or not 1<=len(prose)<=2500 or '[fact:' in prose:
                raise ValueError('Invalid reasoning block')
            retained,units,pending=select(prose,
                lambda part:safe_reasoning(part,context=context) and feasible_reasoning(part,projection),state=dependency)
            if any(not unit['accepted'] for unit in units):
                from claim_evidence import violations
                rejected.append(dict(index=index,reason='unsupported_assertion',sha256=hashlib.sha256(prose.encode()).hexdigest(),
                                     claim_findings=violations(prose),units=units))
            if retained.strip():
                content.append(qualify_route_restatement(retained.strip(), prior));retained_reasoning=True
        else:
            raise ValueError('Unknown answer block type')
    if not tokens or sum(len(p) for p in content)>10000:
        raise ValueError('Answer evidence or size invalid')
    if skipped_fact and not content:
        content.append('The previously stated resource facts still apply.')
    return '\n\n'.join(content),tokens,rejected,retained_reasoning


def preparation_steps(steps, resource, projection):
    """Render independently validated proposal fields, never repaired prose.

    These are preparation instructions, not authority or a claim of execution.
    A rejected causal explanation cannot remove a valid next step or turn it
    into a promise about outcome, account capacity, cost or answer quality.
    """
    name=resource.title() if resource else 'the candidate route'
    descriptions={
        'provide_inputs':'Assemble the smallest relevant source snapshot, current constraints and acceptance criteria using an already-permitted read or owner-supplied material. Missing inputs remain unverified.',
        'inspect_allowance':'Check the authentication route, current remaining allowance and extra-usage settings. Record unknowns; require budget admission before any comparison generates an answer.',
        'keep_current':'Leave the default configuration unchanged while checking current availability and evaluating alternatives; retaining a configuration does not establish service health or answer quality.',
        'preserve_standard':'Write the acceptance criteria and prepare matched tasks, including multi-turn corrections, using the same inputs for each candidate. Require quality evidence before changing the default.',
        'review_dependency':'Verify the linked Cursor/Grok allowance and observed usage before recommending a subscription change.',
        'qualify_chat':'Prepare matched tasks and an evaluation rubric for '+name+'. Verify current access and budget admission before running the comparison; its result must qualify any default change.',
        'prepare_report':'Define a bounded '+name+' report assignment with its source snapshot, expected artifact and acceptance criteria. Obtain task and budget admission before execution.',
    }
    if not steps:return ''
    return '\n\nProposed preparation steps (not started):\n'+'\n'.join(
        str(i)+'. '+descriptions[s] for i,s in enumerate(steps,1))


SAME_UNAVAILABLE = 'Same constraints as above: unavailable routes are unchanged.'
SAME_MISSING_INPUTS = 'Same missing-input limit as above: needed project inputs remain unavailable until supplied.'
SAME_STEPS = 'The previously listed preparation steps still apply.'
ROUTE_MENTION = re.compile(
    r'\b(?:conversation adapter|scoped executors?|route registry|configured routes? for|scoped workspace assignments|supported (?:chat |conversation )?route)\b',
    re.I)
ROUTE_QUALIFIED = re.compile(
    r'\b(?:configured, not|not live-verified|not (?:a claim that|verified)|availability[/ ]sign-in not verified|'
    r'sign-in(?: status)? is unverified|availability.{0,40}not verified)\b',
    re.I)
ROUTE_NOTE = 'That listing is configured in Web Bob’s route registry; availability and sign-in are not verified.'


def qualify_route_restatement(text, prior=''):
    """Carry configured-not-verified on each turn that restates a route claim."""
    if not text or not ROUTE_MENTION.search(text) or ROUTE_QUALIFIED.search(text):
        return text
    if ROUTE_NOTE.lower() in text.lower():
        return text
    return text.rstrip() + ('' if text.rstrip()[-1:] in '.!?' else '.') + ' ' + ROUTE_NOTE


def maybe_append(content, block, prior, *, reference=''):
    """Keep a block once per conversation; omit already-delivered Same-as-above lines."""
    from claim_evidence import already_delivered
    block = (block or '').strip()
    if not block:
        return content
    if block in (content or ''):
        return content
    if already_delivered(block, prior):
        # "Same … as above" restatements add no constraint and bury this turn.
        # Keep other one-line reminders such as previously listed steps.
        if (reference and not reference.startswith('Same ')
                and reference not in (content or '')
                and not already_delivered(reference, prior)):
            return ((content or '') + '\n\n' + reference).strip()
        return content
    return ((content or '') + '\n\n' + block).strip()


def finish_resource_content(content, projection, known, prior, *, observation='', steps_text=''):
    """Restore one-line constraint refs instead of restating unchanged blocks."""
    if projection.get('unavailable'):
        content = maybe_append(content, known.get('availability'), prior, reference=SAME_UNAVAILABLE)
    if projection.get('missing_inputs'):
        content = maybe_append(content, known.get('missing_inputs'), prior, reference=SAME_MISSING_INPUTS)
    if observation:
        content = maybe_append(content, observation, prior)
    if steps_text:
        content = append_preparation_steps(content, steps_text, prior)
    return content


def append_preparation_steps(content, steps_text, prior):
    """Keep novel steps; replace an already-delivered checklist with one line."""
    from claim_evidence import already_delivered
    steps_text = (steps_text or '').strip()
    if not steps_text:
        return content
    numbered = []
    for line in steps_text.split('\n'):
        match = re.match(r'\d+\.\s+(.*)', line)
        if match:
            numbered.append(match[1].strip())
    prior_has_steps = bool(re.search(r'Proposed preparation steps \(not started\)', prior or '', re.I))
    novel = [step for step in numbered if not already_delivered(step, prior)]
    if prior_has_steps and not novel:
        return maybe_append(content, steps_text, prior, reference=SAME_STEPS)
    if prior_has_steps and novel and len(novel) < len(numbered):
        block = 'Additional preparation (not started):\n' + '\n'.join(
            str(i)+'. '+step for i, step in enumerate(novel, 1))
        return maybe_append(content, block, prior, reference=SAME_STEPS)
    return maybe_append(content, steps_text, prior, reference=SAME_STEPS)


class InvalidAdviceSteps(ValueError):
    """Reject proposal fields while retaining independently checked answer text."""
    def __init__(self, content):
        super().__init__('Invalid general advice steps')
        self.content = content


def render(raw, projection, *, root=None, prior=''):
    """Compose grounded facts and checked reasoning; advice creates no effects."""
    value=parse(raw)
    modern=isinstance(value,dict) and set(value)=={'answer','resource','steps'}
    if not modern and projection.get('requested_view') in ('comparison','inventory'):
        # The empty packet is the historical inventory request. Other packets
        # must pass the same legacy schema and constraint gate before rendering.
        if value!={}:
            if not isinstance(value,dict) or set(value)!={'resource','steps'}:
                raise ValueError('Invalid resource decision')
            validate_route(value['resource'],value['steps'],projection)
        names=projection.get('requested_resources') or list(ROUTES)
        rows=['| Resource | Supported use | Billing / evidence |','|---|---|---|']
        for item in projection['inventory']['resources']:
            if item['name'] not in names:continue
            observed=item['observation']
            auth=(str(observed.get('plan') or observed.get('auth_mode'))+' observed; ' if observed.get('freshness')=='recent' and observed.get('authenticated') is True else 'Current sign-in/plan unverified; ')
            rows.append('| '+item['name'].title()+' | '+', '.join(item['tasks'])+' | '+auth+item['billing']+' |')
        return '\n'.join(rows)+'\n\nThese are supported routes, not a verified subscription invoice. Login alone establishes neither remaining capacity nor comparative answer quality; use a matched task before changing the default.',dict(view=projection['requested_view'],execution_started=False)
    if modern:
        blocked=isinstance(value['answer'],list)
        if not blocked and (not isinstance(value['answer'],str) or not 1<=len(value['answer'])<=7000):
            raise ValueError('Invalid answer composition')
        known=projection.get('facts') or facts(projection['inventory'],missing=projection['missing_inputs'])
        rejected=[];retained_reasoning=False
        if blocked:
            content,tokens,rejected,retained_reasoning=compose_blocks(value['answer'],known,projection,prior)
        else:
            tokens=FACT_TOKEN.findall(value['answer'])
        if not blocked:
            if not tokens or any(t not in known for t in tokens) or '[fact:' in FACT_TOKEN.sub('',value['answer']):
                raise ValueError('Ungrounded answer composition')
            if not safe_reasoning(value['answer']) or not feasible_reasoning(value['answer'],projection):
                # Keep the legacy citation format's complete independent
                # reasoning, using the same dependency checks as block format.
                # Mask citations in place; they cannot stitch rejected prose
                # into a fact or establish a rejected premise.
                from answer_fragments import select
                prose=FACT_TOKEN.sub(lambda m:' '*len(m[0]),value['answer'])
                retained,units,_=select(prose,lambda part:safe_reasoning(part,context=prose) and feasible_reasoning(part,projection))
                if not retained.strip():raise ValueError('Ungrounded answer composition')
                content,tokens,rejected,retained_reasoning=compose_blocks([*[dict(fact=t) for t in dict.fromkeys(tokens)],
                    dict(reasoning=prose)],known,projection,prior)
                blocked=True
        owner=projection.get('owner_context')
        if root is not None and owner and any(t.startswith('owner.') for t in tokens):
            import project_context
            current=project_context.read(root)['projects'].get(owner['project_id'])
            if not current or current['revision']!=owner['revision']:
                raise ValueError('Owner context changed during composition')
        bare=FACT_TOKEN.sub('',value['answer']).strip(' .,:;\n') if not blocked else None
        if blocked:
            pass
        elif not bare:
            content='\n\n'.join(known[t] for t in dict.fromkeys(tokens))
        else:
            content=FACT_TOKEN.sub('',value['answer']).strip()
            content=re.sub(r' +([.,;:])',r'\1',content)
            content=re.sub(r' {2,}',' ',content)
        if not content:raise ValueError('Empty composed answer')
        resource=value['resource']
        if resource is None:
            steps=value['steps']
            if (not isinstance(steps,list) or len(steps)>3 or
                    any(not isinstance(s,str) or s not in ('provide_inputs','inspect_allowance','keep_current','preserve_standard','review_dependency') or
                        s not in projection.get('allowed_steps',STEPS) for s in steps) or
                    len(set(steps))!=len(steps)):
                raise InvalidAdviceSteps(finish_resource_content(content,projection,known,prior))
            extra=''
            if rejected and not retained_reasoning:
                extra=preparation_steps(steps,None,projection)
            content=finish_resource_content(content,projection,known,prior,steps_text=extra)
            from claim_evidence import finish_delivery
            return finish_delivery(content),dict(resource=None,steps=steps if not rejected else [],fact_ids=tokens,execution_started=False,model_proposal_accepted=not rejected,
                verified_preparation_steps=steps if rejected else [],partial=bool(rejected),rejected_blocks=rejected,acceptance_scope='schema and bounded claim checks; not semantic certification')
        validate_route(resource,value['steps'],projection,empty=True)
        decision=dict(resource=resource,missing_inputs=projection['missing_inputs'],scenario=projection['scenario'],
                      execution_started=False,observation_time=projection['inventory']['observed_at'])
        observation=known[resource+'.observation'] if resource in ('codex','claude','cursor') else ''
        extra=''
        decision.update(steps=value['steps'],fact_ids=tokens,model_proposal_accepted=not rejected,
                        partial=bool(rejected),rejected_blocks=rejected,acceptance_scope='schema and bounded claim checks; not semantic certification')
        if rejected:
            if not retained_reasoning:
                extra=preparation_steps(value['steps'],resource,projection)
            decision.update(resource=None,steps=[],verified_preparation_steps=value['steps'])
        content=finish_resource_content(content,projection,known,prior,observation=observation,steps_text=extra)
        from claim_evidence import finish_delivery
        return finish_delivery(content),decision
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
    elif first=='preserve_standard':
        parts.append('preserve the answer-quality criteria and prepare evidence for a bounded comparison before changing the default. ')
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
