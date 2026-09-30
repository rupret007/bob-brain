"""Turn broad improvement/enable requests into a saved, bounded first step.

This is a local transcript audit, not a coding worker or an autonomous learning
loop. Its receipt records what was actually inspected and what remains to do.
"""
import hashlib
import json
import re
import time

from chat_intent import blocked_scopes, command, hold_reply, projects, state_for


ENABLE = re.compile(r"^enable (?:what we need to enable|(?:the )?(?:additional |project )?workers)[.!]*$", re.I)
RESOURCES = re.compile(r"^(?:top priority\s+)?(?:make it happen[,.]?\s+)?use (?:any and )?all (?:of )?(?:the |these )?resources[.!]*$", re.I)
SELF = re.compile(r"\bself[ -]improv(?:e|ement|ing)\b", re.I)
GOAL = re.compile(r"\b(?:better than|beat|match)\s+(?:bob the bot|grok(?: bot)?)\b", re.I)
DIRECTIVE = re.compile(r"^(?:well\s+)?(?:make|research|use|coordinate|self[ -]improve|improve yourself|"
                       r"top priority|the point is|constant self improvement|yep and coordinate)\b", re.I)
DISABLED = re.compile(r"\b(?:workers? (?:are |is |currently )*(?:disabled|paused)|"
                      r"scheduling is paused|can['’]t enable)\b", re.I)
ASSENT = re.compile(r"\b(?:ready|on board|always (?:learning|working)|I (?:can|will|'ll|’ll)\s+(?:use|focus|improve)|"
                    r"I understand|you['’]re (?:absolutely )?right)\b", re.I)


def direct_goal(text):
    value = command(text)
    if any(name != 'Web Bob' for name in projects(value)):
        return False
    if re.search(r"\b(?:do not|don['’]t|never|not to|stop)\b.{0,50}\b(?:self[ -]improv|improve|better)", value, re.I):
        return False
    own_improvement = SELF.search(value) and (re.search(r'\b(?:your|yourself|you|web bob|grok|bob the bot|use all)\b', value, re.I) or
                                            re.match(r'^self[ -]improve\b', value, re.I))
    own_comparison = GOAL.search(value) and re.search(
        r'\b(?:make\s+(?:web bob|you|yourself)|you\s+(?:be|get|become))\b', value, re.I)
    return bool(DIRECTIVE.match(value) and (own_improvement or own_comparison or
                re.fullmatch(r'(?:improve yourself|self[ -]improve)[.!]*', value, re.I)))


def resolve(text, previous):
    """Resolve a follow-up only from the immediately preceding user goal chain.

    Assistant claims cannot grant permission or invent a goal. An unrelated
    user turn ends the chain, so old project requests cannot be resurrected.
    """
    value = command(text)
    if direct_goal(text):
        return text
    enable = bool(ENABLE.fullmatch(value))
    if not enable and not RESOURCES.fullmatch(value):
        return None
    for message in reversed(previous):
        if message.get('role') != 'user':
            continue
        prior = message.get('content', '')
        if direct_goal(prior):
            return prior
        if ENABLE.fullmatch(command(prior)) or RESOURCES.fullmatch(command(prior)):
            continue
        break
    # A standalone enable request still warrants a real configuration check;
    # it does not authorize resuming an unrelated historical project.
    return 'Check worker scheduling prerequisites' if enable else None


def inspect(root, previous, goal, request_id, prompt):
    """Inspect only this chat and current block markers; never infer worker health."""
    relevant = []
    current_ask = None
    for message in previous:
        if message.get('role') == 'user':
            current_ask = message
        elif message.get('role') == 'assistant' and current_ask and message.get('status') == 'done':
            ask = current_ask.get('content', '')
            if not (direct_goal(ask) or ENABLE.fullmatch(command(ask)) or RESOURCES.fullmatch(command(ask))):
                continue
            if message.get('improvement_receipt') or message.get('task_id') or message.get('task_ids'):
                continue
            content = message.get('content', '')
            finding = 'historical_worker_block_claim' if DISABLED.search(content) else (
                'assent_without_action_receipt' if ASSENT.search(content) else None)
            if finding:
                relevant.append(dict(kind=finding, user_id=current_ask.get('id'), reply_id=message.get('id'),
                                     prompt=ask))
    markers = {name: (root / 'conductor' / name).exists() for name in ('SOLO-WORKER', 'MAINTENANCE')}
    if any(row['kind'] == 'historical_worker_block_claim' for row in relevant):
        target = 'Resolve enable requests from current scheduling facts instead of repeating older worker-block claims.'
    else:
        target = 'Route Web Bob self-improvement requests to a saved action receipt instead of readiness assent.'
    cases = list(dict.fromkeys([row['prompt'] for row in relevant] + [goal, prompt, 'Ok enable what we need to enable']))
    return dict(schema_version=1, request_id=request_id, observed_at=time.time(), goal=goal,
                completed_step='local_transcript_and_scheduling_audit',
                inspected_message_count=len(previous),
                transcript_sha256=hashlib.sha256(json.dumps(previous, sort_keys=True).encode()).hexdigest(),
                scheduling_blocks=markers, findings=relevant,
                regression_cases=[dict(prompt=prompt, expected='A saved action receipt and truthful current scheduling facts; no empty assent.')
                                  for prompt in cases],
                plan=[target, 'Implement the bounded routing fix in a draft branch and run these exact prompt regressions.',
                      'Run the full release gates and verify the owner conversation on the deployed build.'],
                workers_started=0, queued_jobs=0, code_changed=False,
                limitation='This audit prepares the next patch; it does not implement it or prove parity with Grok.')


def handle(chat, conversation, text, request_id):
    previous = conversation['messages'][:-2]
    goal = resolve(text, previous)
    if goal is None:
        return None
    scopes = blocked_scopes(state_for(conversation), ['Web Bob'])
    if scopes:
        return chat.intent_reply(conversation, hold_reply(scopes))
    receipt = inspect(chat.ledger_root(conversation['id']), previous, goal, request_id, text)
    blocks = receipt['scheduling_blocks']
    if blocks['SOLO-WORKER']:
        scheduling = 'The current solo-work setting blocks additional workers.'
    elif blocks['MAINTENANCE']:
        scheduling = 'Scheduling is currently paused for maintenance.'
    else:
        scheduling = 'I checked the current settings: no global scheduling block is set. There is no disabled-worker switch to clear.'
    claims = sum(row['kind'] == 'historical_worker_block_claim' for row in receipt['findings'])
    assent = sum(row['kind'] == 'assent_without_action_receipt' for row in receipt['findings'])
    finding = (f'The audit found {claims} earlier worker-block replies and {assent} assent replies without an action receipt. '
               'Those are historical replies, not evidence of the current worker state.' if receipt['findings'] else
               'There is no matching failed reply in this chat yet; the saved cases establish the baseline to test.')
    content = (f'First step completed: I audited {len(previous)} saved messages in this chat and recorded '
               f'{len(receipt["regression_cases"])} exact-prompt regression cases. {finding}\n\n' + scheduling +
               '\n\nNext implementation step: ' + receipt['plan'][0] +
               ' Test the saved cases, then run the release checks before deploying.\n\n'
               'The audit and plan are saved with this reply. No coding worker was started or queued, '
               'and no code has changed in this step. Worker availability and Grok parity remain unverified.')
    conversation['messages'][-1]['improvement_receipt'] = receipt
    for key in ('pending_job', 'pending_job_id', 'pending_council', 'pending_council_id'):
        conversation.pop(key, None)
    return chat.intent_reply(conversation, content, provider='planner')
