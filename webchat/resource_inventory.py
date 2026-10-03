"""Evidence-backed resource projection, with explicit freshness and unknowns."""
import json
import re
import time

import report_artifacts

OBSERVATION = 'conductor/state/resource-inventory.json'
MAX_AGE = 900
ROUTES = {
    'codex': dict(tasks=['local coding', 'scoped project jobs'], auth='ChatGPT login or separately billed API; inspect observed mode',
                  reach='Assigned local worktrees through the existing executor', billing='ChatGPT plan allowance when authenticated with ChatGPT; credits may apply',
                  report_adapter='No qualified tool-free bounded report adapter'),
    'claude': dict(tasks=['bounded project reports', 'short reviews'], auth='claude.ai subscription login for bounded reports',
                   reach='Supplied evidence only on bounded report route; server writes the assigned artifact',
                   billing='Claude plan allowance; actual extra usage and invoice unverified',
                   report_adapter='One attempt, high effort, requested Opus family, no model tools; model identity checked'),
    'cursor': dict(tasks=['local coding', 'scoped project jobs'], auth='Observe Cursor authenticated status; login alone does not prove funding route',
                   reach='Assigned local worktrees through existing executor', billing='Cursor account; included versus on-demand usage unverified',
                   dependency='Reducing Cursor may reduce Grok Bot included allowance; verify linked account before changing plan'),
    'gemini': dict(tasks=['conversation', 'reasoning', 'voice', 'research', 'evidence reports'], auth='Funded Gemini API account',
                   reach='Configured Web Bob tools; bounded server evidence and approved actions', billing='Separately metered API; ledger charge/reservation is not account credit balance',
                   default='Keep existing quality settings until representative comparison qualifies an alternative'),
    'minimax': dict(tasks=['conversation fallback', 'evidence reports'], auth='Configured API account',
                    reach='Supplied evidence; no native local command execution', billing='Separately metered API under existing budget stops'),
    'dot': dict(tasks=['owner-relayed review handoffs'], auth='Reported Mini/connected-app access; native product route unverified',
                reach='Reported read access; journal-write check failed', billing='Ordinary Dot conversation and Work/Codex task usage differ; task allowance shared with ChatGPT Work/Codex',
                automatic_dispatch=False),
    'grok': dict(tasks=['owner-relayed handoffs', 'native receiver catch-up when available'], auth='Historical receiver evidence only',
                 reach='Grok reported local bridge reads; no authenticated Web Bob push interface established',
                 billing='Grok Bot allowance may depend on Cursor or linked SuperGrok; xAI API is separate; no assumed capacity stacking',
                 automatic_dispatch=False),
}


def question(text):
    from answer_intent import instructions
    value=instructions(text).strip()
    from reply_authority import STATUS_QUESTION
    if (STATUS_QUESTION.search(value) and
            re.search(r'\b(?:status|health|healthy|doing|using|utilization|going|running|failing|errors?)\b',value,re.I)):
        return False
    general = (re.match(r'^(?:(?:ok|okay)[,. ]+)?(?:what|which|how|can we|do we|are there)\b',value,re.I) and
               re.search(r'\b(?:resources?|subscriptions?|allowances?|paid (?:tools|plans)|billing|existing (?:tools|plans))\b',value,re.I) and
               not re.search(r'\b(?:doing|using|utilization|usage|going|running|health)\b',value,re.I))
    provider = (re.search(r'\b(?:ChatGPT|OpenAI|Codex|Claude|Cursor|Gemini|Grok|MiniMax|Dot)\b',value,re.I) and
                re.search(r'\b(?:subscriptions?|Pro|plans?|pay|paid|free|API|logged in|login|quota|allowance|'
                          r'credits?|balance|capacity|available|unavailable|access|read files|use .{0,30}everything)\b',value,re.I))
    return bool(general or provider)


def relevant(conversation):
    """Carry capability evidence through adjacent discussion, never permission.

    Explicit new topics and unrelated content requests end this small scope;
    no private transcript or whole resource journal is added to the inventory.
    """
    from answer_intent import wants_answer
    users=[m.get('content','') for m in conversation.get('messages',[]) if m.get('role')=='user'][-6:]
    for index,text in enumerate(reversed(users)):
        if re.match(r'^(?:different|new|another|unrelated) topic\b',text.strip(),re.I):
            return False
        if question(text):
            return True
        if wants_answer(text) and not re.match(
                r'^(?:then|so|but|what if|give me .{0,20}(?:recommendation|next step)|use resources)\b',text.strip(),re.I):
            return False
    return False


def observe(root, *, now=None):
    now=time.time() if now is None else now
    try:
        saved=json.loads(report_artifacts.read(root,OBSERVATION,64000))
        if saved.get('version')!=1 or not isinstance(saved.get('resources'),dict):
            raise ValueError()
    except (OSError,ValueError,TypeError,AttributeError):
        saved={}
    resources=[]
    for name,route in ROUTES.items():
        item=dict(name=name,**route)
        evidence=saved.get('resources',{}).get(name)
        if isinstance(evidence,dict):
            # The producer saves a safe structured observation, never raw CLI
            # auth JSON or credentials. Unrecognized fields do not enter prompts.
            allowed=('observed_at','source','authenticated','auth_mode','plan','availability',
                     'remaining_usage','cost','quality_evidence','limitations','extra_usage')
            evidence={k:evidence[k] for k in allowed if k in evidence}
            observed=evidence.get('observed_at')
            age=now-observed if isinstance(observed,(int,float)) and not isinstance(observed,bool) else None
            evidence.update(age_seconds=max(0,int(age)) if age is not None else None,
                            freshness='recent' if age is not None and 0 <= age <= MAX_AGE else 'stale_or_unknown')
            item['observation']=evidence
        else:
            item['observation']=dict(freshness='unknown',authenticated=None,remaining_usage=None,quality_evidence=None)
        resources.append(item)
    return dict(observed_at=now,source_path=OBSERVATION,resources=resources,
        rules='Distinguish supported adapter, observed login, freshness, remaining quota and measured quality. '
              'An unchecked circuit is unobserved, not unhealthy or disabled. A prior successful response is not a separate probe. '
              'A subscription-authenticated CLI and separately billed provider API are different routes. '
              'No paid subscription implies unlimited capacity or API entitlement. '
              'A login or remaining allowance is not proof of usable output quality. Do not quote stale balances as current. '
              'Credit units are not dollars. Never change plans or start workers because this question asks about resources. '
              'Prefer useful scoped work and preserved answer quality over simultaneous utilization.',
        recommendation='Provisional: preserve Gemini conversation quality and use qualified subscription workers for bounded work. '
                       'Do not reduce Cursor until the Grok Bot dependency and a representative week of use are measured. '
                       'Do not claim a subscription is redundant from an unused login alone.')
