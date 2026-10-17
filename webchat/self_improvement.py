"""Advance a user-authorized improvement goal through bounded local evidence.

Inspect current source, then verify one named regression suite through the
existing executor. Saved progress distinguishes evidence from broader quality.
"""
import copy
import hashlib
import json
import re
import time

from chat_intent import blocked_scopes, command, hold_reply, projects, state_for


ENABLE = re.compile(r"^enable (?:what we need to enable|(?:the )?(?:additional |project )?workers)[.!]*$", re.I)
RESOURCES = re.compile(r"^(?:top priority\s+)?(?:make it happen[,.]?\s+)?use (?:any and )?all (?:of )?(?:the |these )?resources[.!]*$", re.I)
DEICTIC = re.compile(r'^make (?:this|that|it) better than grok(?: bot)?[.!]*$', re.I)
PROGRESS = re.compile(r'^(?:what (?:did|have) you actually (?:do|done)|what have you (?:done|finished))[.!?]*$', re.I)
SELF = re.compile(r"\bself[ -]improv(?:e|ement|ing)\b", re.I)
GOAL = re.compile(r"\b(?:better than|beat|match)\s+(?:bob the bot|grok(?: bot)?)\b", re.I)
DIRECTIVE = re.compile(r"^(?:well\s+)?(?:make|research|use|coordinate|self[ -]improve|improve yourself|"
                       r"top priority|the point is|constant self improvement|yep and coordinate)\b", re.I)
DISABLED = re.compile(r"\b(?:workers? (?:are |is |currently )*(?:disabled|paused)|"
                      r"scheduling is paused|can['’]t enable)\b", re.I)
ASSENT = re.compile(r"\b(?:ready|on board|always (?:learning|working)|I (?:can|will|'ll|’ll)\s+(?:use|focus|improve)|"
                    r"I understand|you['’]re (?:absolutely )?right)\b", re.I)


def direct_goal(text):
    value = command(text).rstrip(' .!?')
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
    value = command(text).rstrip(' .!?')
    if direct_goal(text):
        return text
    enable = bool(ENABLE.fullmatch(value))
    if not enable and not RESOURCES.fullmatch(value) and not DEICTIC.fullmatch(value):
        return None
    for message in reversed(previous):
        if message.get('role') != 'user':
            continue
        prior = message.get('content', '')
        if direct_goal(prior):
            return prior
        if (ENABLE.fullmatch(command(prior).rstrip(' .!?')) or RESOURCES.fullmatch(command(prior).rstrip(' .!?'))
                or DEICTIC.fullmatch(command(prior).rstrip(' .!?'))):
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
    cases = list(dict.fromkeys([row['prompt'] for row in relevant] + [goal, prompt, 'Ok enable what we need to enable']))
    return dict(schema_version=1, request_id=request_id, observed_at=time.time(), goal=goal,
                completed_step='local_transcript_and_scheduling_audit',
                inspected_message_count=len(previous),
                transcript_sha256=hashlib.sha256(json.dumps(previous, sort_keys=True).encode()).hexdigest(),
                scheduling_blocks=markers, findings=relevant,
                regression_cases=[dict(prompt=prompt, expected='A saved action receipt and truthful current scheduling facts; no empty assent.')
                                  for prompt in cases],
                plan=['Inspect current routing source and run bounded routing probes.',
                      'Verify one named local regression suite within the saved user scope.',
                      'Report verified outcomes and separate remaining model-quality evaluation from local checks.'],
                workers_started=0, queued_jobs=0, code_changed=False,
                limitation='Historical findings do not establish a current defect. Local investigation/tests do not prove model quality or Grok parity.')


ADVANCE = re.compile(r"^(?:keep going|continue|do it|make it happen|use what we have|go(?: ahead)?|resume(?: web bob)?|"
                     r"you already audited it[.!]? do the next useful step|finish that(?:,? and tell me what actually changed)?)[.!]*$", re.I)


def continuation(text):
    """A continuation references existing work; it cannot name a new assignment."""
    value = command(text).rstrip(' .!?')
    if any(name != 'Web Bob' for name in projects(value)):
        return False
    if ADVANCE.fullmatch(value):
        return True
    return bool(re.match(r'^(?:continue|finish|resume|carry on|keep working)\s+(?:(?:with|on)\s+)?'
                         r'(?:the|this|that|our|your|what|where)\b', value, re.I)
                and re.search(r'\b(?:work|task|goal|step|plan|investigation|agreed|started|left off)\b', value, re.I)
                and not execution_limit(value))


def execution_limit(text):
    from answer_intent import instructions
    value = instructions(text)
    return bool(re.search(r"\b(?:do not|don['’]t|never|without|no)\b[^.!?]{0,80}\b"
                          r"(?:run|execute|start|launch|dispatch|workers?|tests?|commands?)\b|"
                          r"\b(?:only|just)\s+(?:inspect|read|explain|plan|audit)\b|"
                          r"\b(?:inspection|read)[ -]only\b", value, re.I))


def network_scope(text):
    """Explicit user scope only; quoted instructions cannot change it."""
    from answer_intent import instructions
    value = instructions(text)
    operation = r'(?:browse|research|look up|search(?: (?:the )?web)?|use (?:the )?(?:web|network)|go online)'
    # Conditional/deferred permission is not present permission. Retain that
    # limit across continuations until an unconditional user grant replaces it.
    deferred = r'\b(?:later|eventually|not yet|wait|await|only if|only after|(?:after|once|when|if|until) (?:I|we|you))\b'
    if re.search(r'\b' + operation + r'\b', value, re.I) and re.search(deferred, value, re.I):
        return False
    if re.search(r"\b(?:do not|don['’]t|never|without|no)\s+" + operation + r'\b|'
                 r'\b(?:stay|work|keep it|only)\s+(?:offline|local[- ]only)\b|'
                 r'\b(?:use|using)\s+only\s+(?:(?:the|this)\s+)?(?:local|supplied|provided)\s+(?:sources|evidence|facts|data)\b', value, re.I):
        return False
    if re.search(r'\b(?:you (?:can|may)|I (?:allow|permit))\s+(?:now\s+)?' + operation + r'\b', value, re.I):
        return True
    return None


def research_directive(text):
    """An unquoted imperative authorizes research; a mention does not."""
    from answer_intent import instructions
    value = instructions(command(text))
    return bool(re.search(
        r'(?:^|[.!?;]\s*|\b(?:and|then|also)\s+)(?:please\s+)?research\b'
        r'(?!\s+(?:is|was|means|has|should|would|could|must|may|can)\b)', value, re.I))


def recover_research(conversation):
    """An admitted attempt has an unknown effect after interruption, not a retry."""
    attempts = conversation.get('improvement_goal', {}).get('comparison_research', {})
    pending = {a['request_id'] for a in attempts.values() if a.get('status') == 'admitted'}
    for message in conversation.get('messages', []):
        if message.get('role') == 'assistant' and message.get('request_id') in pending and message.get('status') == 'error':
            message['content'] = ('Research was admitted before the interruption, but no completed result was saved. '
                                  'Its outcome is unknown. I will not repeat the search automatically; '
                                  'the local investigation and verified task result remain saved.')


def observe_turn(conversation, text, request_id):
    """Bind unscoped continuation to user focus before any handler returns."""
    saved = conversation.get('improvement_goal')
    if not saved:
        return
    value = command(text).rstrip(' .!?')
    network = network_scope(text)
    if network is False:
        saved['network_restriction'] = dict(request_id=request_id, text=text[:600])
    elif network is True:
        saved.pop('network_restriction', None)
    if execution_limit(value):
        saved['execution_restriction'] = dict(request_id=request_id, text=text[:600])
        saved['authorized_steps'] = ['local routing investigation']
    if (network is not None or direct_goal(text) or continuation(value) or ENABLE.fullmatch(value)
            or RESOURCES.fullmatch(value) or DEICTIC.fullmatch(value) or PROGRESS.fullmatch(value)):
        return
    from reply_authority import STATUS_QUESTION, HOLD_QUESTION
    from answer_intent import conceptual
    from chat_intent import HOLD, RELEASE, LIFT
    if (HOLD.match(value) or RELEASE.match(value) or LIFT.match(value) or HOLD_QUESTION.fullmatch(value)
            or STATUS_QUESTION.search(value) and not conceptual(value)
            or re.fullmatch(r'(?:thanks|thank you|ok|okay)[.!]*', value, re.I)):
        return
    # Keep the first focus-change boundary. Later questions and revisions must
    # not erase the relevant conversation that followed that boundary.
    saved.setdefault('suspended_by', dict(request_id=request_id, reason='A newer user request changed the focus.'))


def completed_followup(chat, conversation, root, saved, row, text, request_id):
    """Keep a verified step while advancing or explaining the current request.

    The finite next step is a local comparison worksheet and, only on an
    explicit research request, one bounded existing web search. Neither can
    mark the broader goal complete, authorize a second worker or edit code.
    """
    from pathlib import Path
    value = command(text).rstrip(' .!?')
    comparison = bool(GOAL.search(saved['outcome']) or re.search(r'\bgrok\b', saved['outcome'], re.I))
    from receiver_evidence import observe, describe
    receiver = observe(root) if comparison else None
    result_link = '/api/jobs/result?id=' + row['id']
    completed = ('Completed: the source-backed routing investigation and the local regression suite. '
                 'The executor returned a verified result; no code was changed. '
                 '[Read the verified result](' + result_link + ').')
    if ENABLE.fullmatch(value):
        return (completed + '\n\nThe local execution path already completed this task. '
                'This configuration check changed no setting and enabled no new worker. '
                'Enabling a model is not the remaining step: matched workflow evidence is still needed.' +
                (' ' + describe(receiver) if comparison else '')), (
                    saved.get('current_step') if saved.get('comparison_plan') else 'verification_complete')

    code = Path(__file__).resolve().parents[1]
    if 'comparison_plan' not in saved:
        from capabilities import grounding
        capabilities = grounding(root, [])['capabilities']
        paths = sorted({p.strip() for item in capabilities for p in item['source'].split(';')})
        plan = dict(request_id=request_id, prepared_at=time.time(),
                    scope='Current local capability inventory; no Grok comparison or external search implied.',
                    capabilities=capabilities,
                    sources=[dict(path=p, sha256=hashlib.sha256((code / p).read_bytes()).hexdigest()) for p in paths],
                    missing_evidence=['Matched task/context answers and independently verified effects.'] +
                    (['Current first-party information for the actual Grok Bot environment.',
                      ('Receiver checkpoint and acknowledgment for newer unconsumed batches; current availability remains unknown.'
                       if receiver['historical_checkpoint_ack_verified'] else
                       'A native receiver-owned read, checkpoint and exact batch acknowledgment.')] if comparison else
                     ['A saved baseline for the requested workflow.']))
        if comparison:
            plan['historical_receiver'] = receiver
        plan['sha256'] = hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()
        saved['comparison_plan'] = plan
        preparation = 'I inspected the implemented capability sources and saved a comparison worksheet in this conversation.'
    else:
        preparation = 'The saved comparison worksheet preserves the local capability sources and remaining evidence gaps.'
    saved['next_decision'] = (('Verify first-party information for the actual Grok Bot environment, then compare matched '
                              'writing, research, execution and continuity tasks. Local test success is not that comparison.')
                             if comparison else 'Establish the saved workflow baseline and evaluate matched answer quality. '
                             'Local test success does not establish answer quality.')
    content = (completed + '\n\n' + preparation + ' It covers writing/reasoning, research, local project work, '
               'and durable coordination. The worksheet identifies implemented local paths; it does not score Grok '
               'or claim its receiver consumed anything.')
    if comparison:
        content += ' Current receiver evidence: ' + describe(receiver)
    saved['completed_effects'].append('local capability comparison worksheet')
    step = ('comparison_needs_primary_evidence' if hashlib.sha256(saved['outcome'].encode()).hexdigest()
            in saved.get('comparison_research', {}) else 'comparison_prepared')
    # The saved goal preserves an earlier explicit user instruction across a
    # regression step/restart. New words such as "research" cannot grant scope.
    if comparison and research_directive(saved['outcome']):
        if saved.get('execution_restriction') or saved.get('network_restriction') or network_scope(text) is False:
            content += '\n\nYour saved or current restriction keeps this step local; no web search was made.'
            step = 'comparison_scope_limited'
        else:
            # The goal is an explicit Bob/Grok comparison. Send only that public
            # topic to the existing bounded search, never the private transcript.
            query = 'Grok Bot capabilities official documentation'
            attempts = saved.setdefault('comparison_research', {})
            key = hashlib.sha256(saved['outcome'].encode()).hexdigest()
            if key not in attempts:
                from bob_gaps import web_search
                from urllib.error import URLError
                attempts[key] = dict(request_id=request_id, query=query, admitted_at=time.time(), status='admitted')
                saved['current_step'] = 'comparison_research_admitted'
                # Commit before network I/O. A crash or failed final save keeps
                # an unknown attempt instead of silently repeating the request.
                chat.save(conversation)
                chat.conversations[conversation['id']] = copy.deepcopy(conversation)
                try:
                    result = web_search(query)
                    attempts[key].update(status='completed', observed_at=time.time(),
                                         result=result, scope='Search summary only; linked page not retrieved or verified.')
                except (OSError, URLError, ValueError, TimeoutError):
                    attempts[key].update(status='failed', observed_at=time.time(),
                                         error='The bounded search did not return usable evidence.')
                retrieval = 'I attempted the next research step and saved its result.'
            else:
                retrieval = 'The earlier search attempt is saved; this turn did not repeat it.'
            evidence = attempts[key]
            content += '\n\n' + retrieval
            if evidence.get('status') == 'admitted':
                content += ' Its outcome is unknown because completion was not saved; no automatic retry was made.'
            elif evidence.get('result', {}).get('source'):
                from bob_gaps import format_web_search_reply
                content += '\n\nSearch lead (the linked page has not been verified):\n' + format_web_search_reply(evidence['result'])
            else:
                content += ' It provided no source-backed comparison, so Grok capabilities remain unverified.'
            step = 'comparison_needs_primary_evidence'
    content += '\n\nNext: ' + saved['next_decision']
    return content, step


def handle(chat, conversation, text, request_id):
    from improvement_investigation import investigate, render
    from task_dispatch import task_queue
    previous = conversation['messages'][:-2]
    saved = conversation.get('improvement_goal')
    value = command(text).rstrip(' .!?')
    if saved and not saved.get('suspended_by') and PROGRESS.fullmatch(value):
        request = saved.get('verification_request_id')
        row = next((r for r in task_queue.tasks(chat.root).values() if r.get('conversation_id') == conversation['id']
                    and r.get('request_id') == request), None) if request else None
        content = 'I completed the saved local routing investigation.\n\n' + render(saved['investigation'])
        if row:
            accepted = row.get('acceptance') if isinstance(row.get('acceptance'), dict) else {}
            verified = (row['status'] == 'succeeded' and row.get('execution_started_at') and
                        accepted.get('accepted') is True and accepted.get('method') == 'verified-execution' and
                        row.get('result_sha256') == hashlib.sha256(row.get('result', '').encode()).hexdigest() and
                        accepted.get('result_sha256') == row['result_sha256'] and
                        accepted.get('execution_identity') == saved['investigation']['code_identity'])
            content += ('\n\nThe regression execution passed and its result was verified: [Result](/api/jobs/result?id=' + row['id'] + ').'
                        if verified else '\n\nThe saved regression task is ' + row['status'] + ': `' + row['id'] +
                        '`. That does not establish a verified passing result.')
        else:
            content += '\n\nNo linked regression task is recorded for this investigation; I cannot claim execution.'
        content += '\n\nThis is a report of saved evidence. I did not start another step or change code.'
        return chat.intent_reply(conversation, content, provider='planner')
    goal = resolve(text, previous)
    if saved and saved['outcome'] == 'Check worker scheduling prerequisites' and direct_goal(text):
        saved = None
    followup = bool(continuation(value) or ENABLE.fullmatch(value) or RESOURCES.fullmatch(value) or DEICTIC.fullmatch(value))
    if saved and followup and not saved.get('suspended_by'):
        # An intervening project directive supersedes an unscoped continuation.
        intervening = [m for m in previous if m.get('role') == 'user'
                       and m.get('created_at', 0) > saved['updated_at']]
        if any(any(name != 'Web Bob' for name in projects(m.get('content', ''))) for m in intervening):
            return None
        goal = saved['outcome']
    elif saved and followup and saved.get('suspended_by'):
        return None
    if goal is None:
        if RESOURCES.fullmatch(value) or DEICTIC.fullmatch(value):
            from conversation_focus import answer_only
            if not answer_only(conversation, text):
                scopes = blocked_scopes(state_for(conversation), [])
                if scopes:
                    return chat.intent_reply(conversation, hold_reply(scopes))
                question = ('Which task should I work on, and what result do you want?'
                            if RESOURCES.fullmatch(value) else
                            'What should I improve—Web Bob itself, or a particular answer or project?')
                return chat.intent_reply(conversation, question, provider='planner')
        return None
    if saved and direct_goal(text):
        saved.pop('suspended_by', None)
        if saved['outcome'] != goal:
            saved.setdefault('user_revisions', []).append(dict(request_id=request_id, outcome=goal))
            saved['outcome'] = goal
    scopes = blocked_scopes(state_for(conversation), ['Web Bob'])
    if scopes:
        return chat.intent_reply(conversation, hold_reply(scopes))
    root = chat.ledger_root(conversation['id'])
    blocks = {name:(root / 'conductor' / name).exists() for name in ('SOLO-WORKER', 'MAINTENANCE')}
    scheduling = ('The current solo-work setting blocks additional workers.' if blocks['SOLO-WORKER'] else
                  'Scheduling is currently paused for maintenance.' if blocks['MAINTENANCE'] else
                  'No global scheduling block is set; worker health is a separate check.')
    if not saved:
        receipt = inspect(root, previous, goal, request_id, text)
        investigation = investigate()
        receipt['investigation'] = investigation
        saved = dict(version=1, outcome=goal, scope=['Web Bob'], origin_request_id=request_id,
                     authorized_steps=['local routing investigation', 'one named local regression suite'],
                     audit=receipt, investigation=investigation, current_step='regression_verification',
                     created_at=time.time(), updated_at=time.time(), completed_effects=['local routing investigation'],
                     next_decision='Run webchat/test_answer_intent.py through the existing local CPU executor.')
        conversation['improvement_goal'] = saved
        configuration_only = goal == 'Check worker scheduling prerequisites'
        if configuration_only:
            saved.update(authorized_steps=['local scheduling inspection'], current_step='configuration_checked',
                         next_decision='Identify the concrete task and desired result before starting project work.')
            receipt['plan'] = ['Inspect current scheduling blocks.', 'Report actual routing checks and their limits.',
                               saved['next_decision']]
        if execution_limit(text):
            saved['execution_restriction'] = dict(request_id=request_id, text=text[:600])
            saved['authorized_steps'] = ['local routing investigation']
            saved['next_decision'] = 'Report the local investigation within the user\'s inspection-only scope.'
        if network_scope(text) is False:
            saved['network_restriction'] = dict(request_id=request_id, text=text[:600])
        conversation['messages'][-1]['improvement_receipt'] = receipt
        content = ('I completed a source-backed routing investigation and saved the cases, actual outcomes, '
                   'source locations, and hashes with this conversation.\n\n' + render(investigation) +
                   '\n\n' + scheduling + '\n\n' +
                   ('Next: tell me the task and desired result; no project execution was requested. ' if configuration_only else
                    'Your inspection-only limit is saved; no regression execution is authorized. ' if saved.get('execution_restriction') else
                    'Next: verify the answer/execution boundary with the local regression suite. ') +
                   'This step changed no code, launched no worker, and made no external Grok comparison.')
    else:
        saved['updated_at'] = time.time()
        from source_identity import fingerprint
        from pathlib import Path
        identity = fingerprint(Path(__file__).resolve().parents[1], 'webchat/test_answer_intent.py')
        if identity != saved['investigation']['code_identity']:
            current = investigate()
            saved.setdefault('previous_evidence', []).append(dict(
                investigation_sha256=saved['investigation']['sha256'],
                verification_job_id=saved.get('verification_job_id'),
                verification_request_id=saved.get('verification_request_id')))
            saved.update(investigation=current, current_step='regression_verification',
                         completed_effects=['local routing investigation'])
            saved.pop('verification_request_id', None)
            saved.pop('verification_job_id', None)
            saved.pop('result_sha256', None)
            saved.pop('comparison_plan', None)
            return chat.intent_reply(conversation, 'The running source changed. I refreshed the local investigation; '
                                     'previous tests cannot verify this revision.\n\n' + render(current), provider='planner')
        request = saved.get('verification_request_id')
        row = next((row for row in task_queue.tasks(chat.root).values()
                    if row.get('conversation_id') == conversation['id'] and row.get('request_id') == request), None) if request else None
        if row:
            saved['verification_job_id'] = row['id']
            if row['status'] == 'succeeded':
                result = row.get('result', '')
                accepted = row.get('acceptance') or {}
                if (not row.get('execution_started_at') or not isinstance(accepted, dict)
                        or accepted.get('method') != 'verified-execution'
                        or accepted.get('accepted') is not True or not row.get('result_sha256')
                        or hashlib.sha256(result.encode()).hexdigest() != row['result_sha256']
                        or accepted.get('result_sha256') != row['result_sha256']
                        or accepted.get('execution_identity') != saved['investigation']['code_identity']):
                    content = 'The regression result failed its integrity check. I cannot count it as completed.'
                    saved['current_step'] = 'blocked_result_integrity'
                else:
                    saved['completed_effects'] = ['local routing investigation', 'local regression verification']
                    saved['result_sha256'] = row['result_sha256']
                    content, saved['current_step'] = completed_followup(chat, conversation, root, saved, row, text, request_id)
            elif row['status'] == 'failed':
                saved['current_step'] = 'blocked_regression'
                content = 'The local regression step did not complete: ' + str(row.get('error') or 'No accepted result.')
            else:
                content = ('The saved regression task is ' + row['status'] + ': `' + row['id'] + '`. '
                           'Its result is not complete yet. I kept the same task; no duplicate was created.')
        elif saved.get('execution_restriction'):
            saved['current_step'] = 'inspection_only'
            content = ('The local investigation is complete. Your saved scope excludes execution, '
                       'so this continuation did not queue tests or workers.\n\n' + render(saved['investigation']))
        elif any(blocks.values()):
            content = scheduling + ' The completed investigation is preserved. The next regression step has not started.'
        elif saved['outcome'] == 'Check worker scheduling prerequisites':
            content = scheduling + ' The configuration check is complete. No specific project execution was requested.'
        else:
            saved['verification_request_id'] = request_id
            saved['current_step'] = 'regression_verification'
            return chat.submit_task(conversation, 'Run Web Bob local regression suite webchat/test_answer_intent.py', request_id,
                                    worker='mini', expected_code_identity=saved['investigation']['code_identity'], attempt_limit=1)
        content += '\n\n' + scheduling
    conversation['messages'][-1]['improvement_progress'] = dict(
        origin_request_id=saved['origin_request_id'], current_step=saved['current_step'],
        completed_effects=saved['completed_effects'], investigation_sha256=saved['investigation']['sha256'])
    for key in ('pending_job', 'pending_job_id', 'pending_council', 'pending_council_id'):
        conversation.pop(key, None)
    return chat.intent_reply(conversation, content, provider='planner')
