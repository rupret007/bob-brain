"""Server-owned writing artifacts and assistant assertions are separate values.

The model may supply content, never its purpose, speaker, permissions or receipt
identity. Ordinary answers keep the existing effect guard. A valid writing
packet is displayed as a draft, with independently checked assistant commentary.
"""
import hashlib
import json
import re

RULES = '''The server has selected a writing artifact for this turn. Return ONLY
one JSON object with exactly "artifact" and "commentary", both strings. Put the
complete requested draft/revision in artifact. Usually commentary should be
empty: do not preface the writing. The artifact speaks for its requested author,
not for this application. Commentary speaks for Web Bob and cannot claim any
execution. Neither field may invent task receipts, IDs, tools or completed work.
Keep the user's requested length, facts, counts and latest corrections. Do not
turn a member of an existing group into an additional member: a new exception
changes treatment, not the original total, unless the owner changes that total.
wrap the JSON in fences. The server will label the artifact as a draft separately.
'''
WRITING = re.compile(r'^(?:write|draft|compose|rewrite|revise|rephrase|shorten|expand)\b', re.I)
ARTIFACT = re.compile(r'\b(?:message|note|email|letter|paragraph|poem|story|draft|speech|invitation|script|text|lyrics)\b', re.I)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def current(conversation):
    return next((m.get('_reply_contract') for m in reversed(conversation.get('messages', []))
                 if m.get('role') == 'assistant'), None)


def derive(conversation, redact, root=None):
    from answer_intent import requires_execution, requires_research, instructions, conceptual
    from chat_intent import command, permission_facts
    from conversation_focus import correction
    import draft_revision
    messages = conversation.get('messages', [])
    user = next((m for m in reversed(messages) if m.get('role') == 'user'), {})
    reply = messages[-1] if messages else {}
    text = user.get('content', '')
    request = instructions(command(text))
    kind, source = 'answer', None
    previous = next((m for m in reversed(messages[:-1]) if m.get('role')=='assistant' and m.get('status')=='done'), None)
    if previous and previous.get('_reply_contract',{}).get('kind')=='writing' and not previous.get('artifact',{}).get('accepted'):
        focus=conversation.get('answer_focus',{})
        allowed={ref.get('request_id') for ref in [focus.get('origin') or {},*focus.get('corrections',[])]}
        previous=next((m for m in reversed(messages[:-1]) if m.get('role')=='assistant' and
                       m.get('artifact',{}).get('accepted') and m.get('request_id') in allowed),None)
    eligible = not (requires_execution(text) or requires_research(text) or user.get('voice_call_id') or
                    reply.get('dispatch_blocked') or conceptual(text))
    if eligible:
        new = bool(WRITING.match(request) or
                   re.match(r'^(?:make|create|prepare|give me)\b', request, re.I) and ARTIFACT.search(request))
        refine = correction(text) or re.search(r'\b(?:final|updated|revised) (?:version|draft|wording)\b|'
                                               r'\b(?:think|work) (?:it|this|that) through\b',request,re.I)
        continuing = bool(previous and previous.get('artifact', {}).get('kind')=='writing' and previous.get('artifact', {}).get('accepted') and refine)
        if new or continuing:
            kind = 'writing'
            if continuing:
                source = dict(message_id=previous['id'], request_id=previous.get('request_id'),
                              sha256=digest(previous.get('artifact', {}).get('text', previous['content'])))
    edit = draft_revision.source(conversation, redact) if eligible else None
    if edit:
        kind = 'writing'
        source = dict(message_id=edit['message_id'], request_id=edit['request_id'], sha256=edit['source_sha256'])
    projection=None
    if root and kind=='answer' and not user.get('voice_call_id') and not reply.get('dispatch_blocked'):
        import resource_decision
        projection=resource_decision.project(root,conversation)
        if projection:kind='resource_advice'
    import catchup_contract
    catchup=catchup_contract.project(conversation) if not user.get('voice_call_id') and not requires_execution(text) else None
    # Drafting a receipt interpretation must not put cursor arithmetic or
    # coverage fields back into free-form artifact speech.
    if catchup and kind in ('answer','writing'):
        kind='catchup'
    else:
        catchup=None
    return dict(version=1, kind=kind, request_id=user.get('request_id'), reply_id=reply.get('id'),
                user_sha256=digest(text), allowed_effects=[], source=source,
                localized_edit=bool(edit), permissions=permission_facts(conversation),resource_projection=projection,catchup_projection=catchup)


def safe_artifact(content, source_text=''):
    """Artifact speech is not app status; invented concrete receipts still fail.

    Check asserted operational predicates, rather than spanning from a draft's
    first-person speaker across an unrelated temporal/conditional clause.
    """
    from dispatch_receipts import claims_dispatch, dispatch_prose, REFERENCE_EFFECT
    identifiers = re.findall(r'\b(?:webchat-[a-f0-9]{32}|wb-[a-zA-Z0-9]{8,})\b', content)
    if any(identifier not in source_text for identifier in identifiers):
        return False
    prose = dispatch_prose(content, reference=source_text)
    if REFERENCE_EFFECT.search(prose) and content not in source_text:
        return False
    # App effects remain claims when passive or actorless, including outside
    # the job queue. Artifact labelling cannot establish a send or permission.
    external = re.compile(r"\b(?:I|we)(?:['’]ve| have)?\s+(?:just |already )?(?:sent|delivered|enabled|disabled|resumed|paused)\b"
                          r'[^.!?\n]{0,60}\b(?:text|message|email|workers?|holds?|permissions?)\b|'
                          r'\b(?:your|the|this)\s+(?:text|message|email|workers?|holds?|permissions?)\b'
                          r'[^.!?\n]{0,35}\b(?:was|were|is|are|has been|have been)\s+(?:now |successfully )?'
                          r'(?:sent|delivered|enabled|disabled|resumed|paused|cleared)\b', re.I)
    if external.search(prose) and content not in source_text:
        return False
    app_status = re.compile(
        r'\b(?:Web Bob|Codex|Claude|Cursor|Gemini|MiniMax)\s+(?:is|has been)\s+'
        r'(?:now |currently |still )?(?:handling|answering|running|paused|held|unavailable)\b|'
        r'\b(?:your|our|the)\s+(?:Web Bob\s+)?(?:jobs?|tasks?|workers?|holds?)\s+'
        r'(?:is|are|has been|have been)\s+(?:now |currently |still )?(?:paused|held|active|cleared|resumed)\b', re.I)
    for sentence in re.split(r'(?<=[.!?])\s+|\n', prose):
        if app_status.search(sentence) and sentence not in source_text:
            return False
    operational = re.compile(
        r"\b(?:I|we)(?:['’]ve| have)?\s+(?:(?:just|already|now)\s+)?"
        r'(?:queued|dispatched|delegated|assigned|launched|submitted|scheduled)\b|'
        r"\b(?:I|we)(?:['’]ve| have)?\s+(?:(?:just|already|now)\s+)?started\s+(?:a |the |your |our )?(?:job|task|worker|council)\b|"
        r'\b(?:Web Bob|Codex|Claude|Cursor|Gemini|MiniMax|the dispatcher)\b', re.I)
    for sentence in re.split(r'(?<=[.!?])\s+|\n', prose):
        concrete = re.search(r'\b(?:job|task|worker|council|queue|Codex|Claude|Cursor|Gemini|MiniMax|Web Bob)\b',sentence,re.I)
        if concrete and operational.search(sentence) and claims_dispatch(sentence, reference=source_text) and sentence not in source_text:
            return False
    return True


def deliver(root, text, answer, conversation, *, observation, redact):
    """Return (visible answer, accepted artifact) from a saved server contract."""
    from reply_authority import enforce
    from reply_guard import repair_hollow_progress
    contract = current(conversation)
    raw = answer['content']
    if contract and contract['kind']=='catchup' and contract['user_sha256']==digest(text):
        import catchup_contract
        try:
            content=catchup_contract.render(raw,contract['catchup_projection'])
        except (ValueError,TypeError,KeyError):
            content=catchup_contract.render('{"mode":"explain"}',contract['catchup_projection'])
        conversation['messages'][-1]['catchup_observation']=contract['catchup_projection']
        return content,None
    if contract and contract['kind']=='resource_advice' and contract['user_sha256']==digest(text):
        import resource_decision
        try:
            content, decision=resource_decision.render(raw,contract['resource_projection'],root=root)
        except (ValueError,TypeError,KeyError):
            projection=contract['resource_projection']
            facts=projection.get('facts') or resource_decision.facts(projection['inventory'],missing=projection['missing_inputs'])
            names=[r for r in projection.get('requested_resources',[]) if r in projection.get('allowed_resources',[])]
            content='I could not validate that resource answer.'
            if projection['missing_inputs']:
                content+=' '+facts['missing_inputs']
            for name in names[:2]:
                content+=' '+name.title()+': '+facts[name+'.observation']
            decision=dict(resource=None,steps=[],execution_started=False,model_proposal_accepted=False)
        guarded=enforce(root,text,dict(answer,content=content),conversation,observation=observation,redact=redact)
        if guarded!=content:
            decision['model_proposal_accepted']=False
        content=guarded
        conversation['messages'][-1]['resource_decision']=decision
        return content,None
    valid = bool(contract and contract['kind']=='writing' and contract['allowed_effects']==[] and
                 contract['user_sha256']==digest(text) and contract['reply_id']==conversation['messages'][-1]['id'])
    packet = None
    if valid and contract['localized_edit']:
        packet = dict(artifact=raw, commentary='')
    elif valid:
        try:
            from structured_reply import loads
            packet = loads(raw)
        except (ValueError, TypeError):
            if raw.lstrip().startswith(('{','[','```')):
                return 'I could not produce a valid draft. Please retry.', None
        if packet is not None and (not isinstance(packet,dict) or set(packet)!= {'artifact','commentary'} or
                any(not isinstance(v,str) for v in packet.values()) or not packet['artifact'].strip()):
            return 'I could not produce a valid draft. Please retry.', None
    if packet is not None:
        source = contract.get('source')
        prior = next((m for m in conversation['messages'] if source and m.get('id')==source['message_id'] and
                      digest(m.get('artifact',{}).get('text',m.get('content','')))==source['sha256']), None)
        if source and not prior:
            return 'The source draft changed; this revision was not applied.', None
        artifact = redact(packet['artifact']).strip()
        if not safe_artifact(artifact, text + '\n' + (prior['content'] if prior else '')):
            return 'The draft contained an unsupported action claim; I could not deliver that version.', None
        commentary = packet['commentary'].strip()
        if commentary:
            guarded = enforce(root,text,dict(answer,content=commentary),conversation,observation=observation,redact=redact)
            if guarded != commentary:
                return 'The reply contained an unsupported action claim; I could not deliver that version.', None
            commentary = repair_hollow_progress(guarded)
        visible = artifact + ('\n\n' + commentary if commentary else '')
        return visible, dict(accepted=True, kind='writing', label='Draft',
                             text=artifact, sha256=digest(artifact), source=source, commentary=commentary)
    guarded = enforce(root,text,dict(answer,content=raw),conversation,observation=observation,redact=redact)
    delivered = guarded if observation else repair_hollow_progress(guarded)
    # Legacy/plain-text providers remain guarded. They can establish a source
    # only after their entire answer survives, never after a substituted denial.
    accepted = valid and delivered == raw and not raw.lstrip().startswith(('{','['))
    return delivered, dict(accepted=True,kind='writing',label='Draft',text=raw,sha256=digest(raw),source=contract['source'],commentary='') if accepted else None
