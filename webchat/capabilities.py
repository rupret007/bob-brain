"""Fast, server-owned capability and explanation answers; never perform actions."""
import re
import json


def needs_grounding(text):
    """Ground capability questions and stated integration needs in actual code."""
    from answer_intent import instructions, requires_execution
    from resource_inventory import question as resource_question
    if resource_question(text):
        return True
    value = instructions(text).strip()
    question = re.match(r'^(?:(?:ok|okay|hey bob)[,!. ]+)*(?:(?:can|could|do|are|will) you\b|'
                         r'what (?:can you|are your)\b|how (?:can|do|does) (?:you|web bob)\b)', value, re.I)
    integration_need = (re.match(
        r'^(?:i|we)\s+(?:want|need|would like)\s+'
        r'(?:(?:(?:it|you|web bob|grok(?: bot)?|this)\s+)?(?:to\s+)?(?:be able to\s+)?'
        r'(?:coordinate|connect|interface|integrate|catch up)\b|'
        r'(?:coordination|integration|a connection)\s+(?:with|between)\b)', value, re.I)
        and re.search(r'\b(?:Grok|Web Bob)\b', value, re.I))
    return bool((question or integration_need)
                and re.search(r'\b(?:capabilit\w*|featur\w*|interface|integrat\w*|connect|coordinat\w*|'
                              r'catch up|better|as good|replace|alternative|instead|rather than)\b', value, re.I)
                and not requires_execution(value))


GROUNDING_RULES = '''For an app-capability question, use the supplied implemented
capabilities and coordination observations. Address the user's intended use as
well as the literal connection question. Separate shared work records, a direct
chat connection, current availability, and permission to execute. Hosting on a
local computer does not mean all models run locally. Describe a useful available
path for the stated goal without pretending it is already underway. Do not infer
another product's features or superiority from its name. Never treat a saved
handoff or acknowledgment as a command, proof of available quota, or execution.
Explain implemented support in plain product language, including the existing
durable work record and read/checkpoint/acknowledgment path when relevant. Do not
collapse missing automatic delivery into missing shared records. Reuse the
implemented mechanism; do not propose replacement folders or ask the user to
choose between building a skeleton and writing a protocol that already exist.
Use saved record receipts as evidence only for what they actually recorded.
Recognize a verified historical receiver checkpoint when supplied. Distinguish
that evidence from consumption of a newly prepared batch and present availability.
Name the remaining receiver binding or availability gap precisely; do not
promise contact, monitoring or wake-up that this version cannot perform.
Direct native chat transport is optional for file-based coordination, not a
prerequisite for using the implemented local handoff. Explain the next use of
that path and the evidence still needed from the receiver. Do not leave the user
at a speculative API/webhook design. Keep raw implementation labels out of normal
product explanations unless the user needs a command or file location.
'''


def prepare_coordination(chat, conversation, text, request_id):
    """Turn an explicit coordination need into a saved, unconsumed local batch.

    Questions remain model answers. This operation reads the existing protocol;
    it neither contacts a receiver nor changes any acknowledgment or work scope.
    The private payload stays out of model context and public conversation exports.
    """
    from answer_intent import instructions
    value = instructions(text).strip()
    if (not needs_grounding(text) or not re.match(r'^(?:i|we)\s+(?:want|need|would like)\b', value, re.I)
            or not re.search(r'\bGrok\b', value, re.I)
            or re.search(r"\b(?:do not|don't|don’t|not yet|just explain|only explain)\b", value, re.I)
            or re.search(r'\b(?:eventually|for now|later|wait|await|only if|not until|'
                         r'(?:after|once|if) (?:I|we)|(?:just|only) (?:describe|outline|discuss|plan))\b', value, re.I)
            or re.search(r'\b(?:and|then|also)\s+(?:please\s+)?(?:write|draft|create|build|modify|edit)\b', value, re.I)):
        return None
    if chat.ledger_root(conversation['id']) != chat.root or conversation.get('_coordination_excluded'):
        return None
    chat.texting.invalidate(conversation)
    for key in ('pending_job', 'pending_job_id', 'pending_council', 'pending_council_id'):
        conversation.pop(key, None)
    from app import state_ledger
    try:
        batch = state_ledger.bob_catchup(chat.root, limit=12)
        if len(json.dumps(batch, ensure_ascii=False).encode()) > 256 * 1024:
            raise ValueError('Batch exceeds the bounded handoff size')
    except (OSError, ValueError, TypeError):
        return chat.intent_reply(conversation,
            'I could not prepare a catch-up batch because the saved coordination record could not be read safely. '
            'The existing record and acknowledgment are unchanged; repairing that record is the next step.',
            provider='coordination')
    # Chat.submit has already deduplicated the request. Commit the exact batch
    # with the delivered receipt using Chat's existing atomic private save.
    conversation.setdefault('_coordination_prepared_batches', {})[request_id] = batch
    count = len(batch['events'])
    receipt = {key: batch[key] for key in ('journal_id', 'since_seq', 'through_seq',
                                          'receipt_sha256', 'has_more', 'history_gap')}
    from receiver_evidence import observe, describe
    historical = observe(chat.root)
    receipt.update(record_count=count, receiver_verified=False, acknowledged=False,
                   historical_receiver=historical,
                   execution_started=False, completed_step='prepared_local_catchup_batch')
    conversation['messages'][-1]['coordination_receipt'] = receipt
    prepared = (f'I prepared and saved a catch-up batch of {count} earlier recorded updates with this conversation '
                f"(records {batch['events'][0]['seq']}–{batch['through_seq']}). " if count else
                'I checked the saved work record and saved an empty catch-up batch with this conversation; no unacknowledged updates were available. ')
    coverage = ('Web Bob records delivered replies, scope changes, and task outcomes; this does not include every external action or private message. ')
    gaps = ('More recorded updates remain after this batch. ' if batch['has_more'] else '')
    gaps += ('Some earlier history is missing from the retained record. ' if batch['history_gap'] else '')
    return chat.intent_reply(conversation, prepared + coverage + gaps +
        describe(historical) + ' Preparing this batch has not contacted Grok or marked anything as read.',
        provider='coordination')


def grounding(root, reply_providers, conversation_id=None):
    """Project implemented metadata, following StoryOps' tool-metadata pattern.

    These describe existing handlers, not a second tool dispatcher. Product
    hold, admission and result checks continue to own execution.
    """
    observations = dict(durable_shared_records_implemented=True, exact_batch_acknowledgment_implemented=True,
                        journal_path='conductor/state/coordination-events.jsonl',
                        reader_path='state/bob_sync.py in the active candidate identified by conductor/state/webchat-code-root',
                        durable_journal_present=(root / 'conductor/state/coordination-events.jsonl').is_file(),
                        saved_conversation_receipts=[],
                        consumer_last_acknowledged_through=None,
                        consumer_availability='unverified', native_grok_automatic_delivery_implemented=False)
    observations['file_coordination'] = dict(
        outbound='Web Bob saves delivered answers, scope changes and completed task outcomes for Bob to read.',
        inbound='Existing conductor/handback/BOB-STATE.md supplies Bob-authored handoff context through webchat/handback.py.',
        use='Keep working in Web Bob. A returning Bob with local tools can read the saved batch, '
            'checkpoint it and acknowledge exactly that batch, then leave its own handoff in BOB-STATE.md.',
        next_verification='Have the native Bob receiver actually read/checkpoint/acknowledge one batch. '
                          'No such receiver contact or acknowledgment is claimed by this reply.',
        direct_chat_api_required=False,
        authority='Shared evidence and context only; no work is authorized or executed by exchanging records.')
    from receiver_evidence import observe, describe
    observations['historical_receiver'] = observe(root)
    observations['file_coordination']['next_verification'] = describe(observations['historical_receiver'])
    try:
        import alignment_events
        observations['saved_conversation_receipts'] = [
            {key:row.get(key) for key in ('seq', 'kind', 'message_id', 'answer_sha256')}
            for row in alignment_events.read_events(root, limit=80)
            if conversation_id and row.get('conversation_id') == conversation_id][-4:]
    except OSError:
        observations['journal_read_error'] = True
    try:
        path = root / 'conductor/state/STATE.json'
        state = json.loads(path.read_text()) if path.exists() else {}
        receipt = state.get('bob_coordination_last_receipt') or {}
        observations['consumer_last_acknowledged_through'] = receipt.get('through_seq')
        observations['consumer_acknowledged_at'] = receipt.get('acknowledged_at')
    except (OSError, ValueError, TypeError, AttributeError):
        observations['record_read_error'] = True
    return dict(
        source='Implemented Web Bob handlers in this code version; not proof of current provider health.',
        reply_providers=list(reply_providers),
        capabilities=[
            dict(name='persistent project context', source='webchat/project_context.py',
                 path='Versioned owner priorities and corrections, selective retrieval, inspect/remove through chat; facts do not grant execution permission.'),
            dict(name='bounded subscription reports', source='webchat/project_reports.py; services/subscription_report.py',
                 path='Explicit read-only Web Bob reports with one pinned owner, exact source snapshot, one attempt and a verified saved artifact.',
                 limitation='Claude subscription route is implemented; current login/quota and real output quality require observed evidence.'),
            dict(name='review handoff and returned artifact', source='webchat/project_handoffs.py',
                 path='Prepared owner-relayed handoff with context and bounded journal delta; strict assignment/source-bound return import.',
                 limitation='Prepared is not accepted; imported authorship remains unverified; no automatic native Dot/Grok dispatch.'),
            dict(name='writing and reasoning', source='webchat/providers.py',
                 path='Replies and revisions in this conversation using configured model providers.'),
            dict(name='research', source='webchat/bob_gaps.py; webchat/task_dispatch.py',
                 path='Server web search or a research task; cite only evidence actually retrieved.'),
            dict(name='local project work', source='webchat/task_dispatch.py; services/dispatch_worker.py',
                 path='Authorized jobs use the existing executor and result validation; jobs are not Grok chat calls.'),
            dict(name='Grok/Bob coordination', source='state/bob_sync.py; state/alignment_events.py',
                 path='A shared durable work record with explicit read and exact-batch acknowledgment. '
                      'Bob/Grok can catch up through its local file tools when it returns. '
                      'The local reader must actually run before consumption can be claimed.',
                 limitation='No verified direct native Grok chat transport or automatic wake-up is configured. '
                            'Only current Web Bob publishers contribute after the retained legacy import; '
                            'older external publishers and already-trimmed history are not covered.'),
        ], coordination=observations, resources=__import__('resource_inventory').observe(root),
        comparison='Grok feature parity and answer superiority require matched evidence; not established here.')


QUESTIONS = {
    'overview': ('what can you do', 'what can you help with', 'how can you help me',
                 'what are your capabilities', 'what can web bob do'),
    'texting': ('can you send texts', 'can you send text messages', 'can you text',
                'can you send messages', 'can you read my texts', 'can you text people'),
    'instinct': ('can you text instinct', 'can you send messages to instinct',
                'can you send texts to instinct', 'can you reply to instinct'),
    'memory': ('can you remember things', 'can you remember things about me',
               'how does your memory work', 'is my memory private',
               'where do you save memories'),
    'reminders': ('can you set reminders', 'can you remind me', 'can you set routines'),
    'media': ('can you read images', 'can you see photos', 'can you read files',
              'can you watch videos', 'can i attach files'),
    'voice': ('can we talk', 'can you do voice calls', 'can i talk to you'),
    'workers': ('can you start workers', 'can you run coding jobs',
                'can you use other models', 'can you run council'),
    'git_force': ('what is a force push', 'what is a force-push', 'what does force push mean',
                  'what does force-push mean', 'explain force push', 'explain force-push'),
    'git_ready': ('what does undraft mean', 'what does undrafting a pr mean',
                  'what does gh pr ready do', 'what does gh pr ready mean', 'explain gh pr ready'),
    'git_merge': ('what does merging a pr mean', 'what does merging a pull request mean',
                  'what does merge a pr mean', 'what is a pull request merge'),
}


def topic(text):
    # Full-turn matching avoids stealing real requests, quoted text, or a
    # recipient/body from the handlers that enforce approval and privacy.
    normalized = re.sub(r'\s+', ' ', text.strip().casefold()).rstrip('?.!')
    normalized = re.sub(r'^(?:hey bob[, ]+|bob[, ]+)', '', normalized)
    return next((key for key, phrases in QUESTIONS.items() if normalized in phrases), None)


def reply(text, root):
    kind = topic(text)
    if kind is None:
        return None
    paused = ((root / 'conductor/MAINTENANCE').exists() or
              (root / 'conductor/SOLO-WORKER').exists())
    worker = ('Additional workers and council are paused for solo work; Jobs shows the observed activity.'
              if paused else 'Coding jobs can be queued for draft work; Jobs shows whether they actually start.')
    answers = {
        'overview': ('I can help with writing and songs, research with sources, saved memories, reminders, '
                     'and attached photos or files. You can talk with me using the call button, read texts, '
                     'or review an exact draft before sending through Andrea. Instinct stays read-only. ' + worker),
        'texting': ('Yes—Web Bob supports reading texts and sending a reviewed draft to a direct recipient through '
                    'Andrea’s BlueBubbles bridge. Review the exact recipient and message, then confirm that draft '
                    'separately. A missing delivery receipt means delivery is unconfirmed; use Check delivery on '
                    'the draft to inspect it without resending. Instinct stays read-only.'),
        'instinct': ('I can read and summarize Instinct’s messages and prepare an unsent reply draft. '
                     'Instinct is read-only here; its drafts cannot be sent from Web Bob.'),
        'memory': ('Ask “remember that…” and I’ll show the memory for your confirmation before saving it locally. '
                   'Ask “show my saved memories” to inspect confirmed Web Bob notes directly. '
                   'Use Settings → Manage saved notes to review one note for removal; chat and other copies remain. '
                   'Saved memories can be included in future model context, so they are not device-only. '
                   'Private texting turns are excluded from model chat context; don’t save secrets as memories.'),
        'reminders': ('Yes—ask “remind me to stretch in 10 minutes” or set a recurring reminder. '
                      'Reminders appear in this chat while Web Bob is running; they are not phone push notifications.'),
        'media': ('Yes—attach a photo, file, or video with your question. I can use extracted text and supported '
                  'image analysis; video uses sampled frames and available transcript, not every moment. '
                  'If something cannot be read, I’ll say so.'),
        'voice': ('Yes—tap the call button and allow microphone access for a two-way voice conversation. '
                   'You can interrupt me or hang up; the transcript stays in this conversation.'),
        'workers': worker,
        'git_force': ('A force push can replace the remote branch’s history, which can discard other people’s '
                      'commits. Web Bob can explain it and help review alternatives; it cannot run a force push.'),
        'git_ready': ('Removing draft status marks a pull request ready for review. The command “gh pr ready” '
                      'does that; it does not merge the code. Web Bob keeps pull requests as drafts.'),
        'git_merge': ('Merging a pull request integrates its changes into the target branch. Reviewing a PR '
                      'or opening a draft does not merge it. Web Bob can prepare and review draft changes.'),
    }
    return answers.get(kind)
