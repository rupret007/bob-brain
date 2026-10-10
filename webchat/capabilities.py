"""Fast, server-owned capability and explanation answers; never perform actions."""
import re
import json

# Descriptions of existing handlers only. Never probe auth or execute a tool to
# answer a capability question; observations and action receipts own those facts.
STACK = {
    'calendar': dict(name='direct Google Calendar', source='webchat/calendar_actions.py',
        path='Direct Google Calendar reads and single private event creation are implemented. '
             'An authorized Calendar account is required; without auth, no Calendar action can run. '
             'Creation needs the exact yes wbcal-… confirmation of its draft. '
             'No invitations, recurring events, or event alerts are supported.'),
    'timers': dict(name='reminders and timers', source='webchat/reminders.py',
        path='Reminders and timers are implemented: try “set a timer for 10 minutes”. '
             'They appear in this chat and Jobs while Web Bob is running; overdue reminders arrive on return. '
             'Local macOS notifications need owner opt-in and OS permission; these are not phone push notifications. '
             'Saving a timer does not prove it fired or an alert was displayed.'),
    'routines': dict(name='morning routines', source='webchat/reminders.py; webchat/local_tasks.py',
        path='Morning reminders and read-only routines are implemented, defaulting to 9am America/Chicago. '
             'Try “every morning do read file ~/Documents/notes.txt”. '
             'Routines can read allowed files, list directories, use fixed read-only terminal commands, or search the web. '
             'They run while Web Bob is running, with one overdue run on return, subject to saved holds. '
             'Writes, deletes and sends cannot run unattended.'),
    'local_files': dict(name='bounded local files', source='webchat/local_tasks.py; webchat/local_task_worker.py',
        path='Bounded local file reads, listings, creation, replacement and deletion are implemented. '
             'Only allowed visible paths under the owner’s home are supported; secrets, credentials, '
             'private/configuration trees, protected runtime files, links and special files are excluded. '
             'Overwrites and deletes require the exact yes wblocal-… confirmation of a draft. '
             'This is not unrestricted filesystem access.'),
    'terminal': dict(name='bounded terminal', source='webchat/local_tasks.py; webchat/local_task_worker.py',
        path='Bounded terminal commands are implemented: “run terminal: pwd”, date, ls PATH, or cat PATH. '
             'The same file restrictions apply. No shell, arbitrary commands, pipes or scripts are supported by this direct route.'),
    'search': dict(name='web search', source='webchat/local_tasks.py; webchat/bob_gaps.py',
        path='Web search is implemented: try “search the web for Chicago weather”. '
             'Results depend on a successful retrieval and must cite only retrieved evidence. '
             'Search is not an interactive browser or an arbitrary URL-fetch tool.'),
}

MISSING = {
    'gmail': 'Gmail integration is not implemented here; I can help compose email text, but cannot read your Gmail or send it through Gmail.',
    'drive': 'Google Drive integration is not implemented here; local files and attachments do not grant access to Drive.',
    'browser': 'Interactive browser control and arbitrary URL fetching are not implemented here. Web search is a separate supported path; it does not prove a page was opened or read.',
    'image_generation': 'Image generation is not implemented here. I can help write an image prompt; analyzing an attached image does not generate a new image.',
}

STATUS_RULES = (
    'Implemented means a handler exists in this code version. Configured means its required setup has been observed; '
    'it does not establish live availability. Live-verified requires a relevant successful action receipt, '
    'with its time and scope; historical success does not guarantee current availability. '
    'Source files, build identity, candidate tests, provider names and login observations alone cannot establish '
    'deployment, live tool availability or action completion. Never promote candidate support to deployed support. '
    'Unknown setup must remain unverified; absent or expired auth blocks dependent actions. '
    'Capability explanations perform no action and create no action receipt. '
    'Saved holds apply at admission and execution. Paid calls require existing admission routes; no card spend. '
    'Sends to others stay drafts until explicit yes to the exact recipient and content. '
    'Never read protected authentication material to answer a capability question or include it in prompts, logs or artifacts.'
)


def voice_limits():
    from chat_media import MAX_VIDEO_BYTES, MAX_VIDEO_DURATION_S, MAX_VIDEO_FRAMES
    from voice import CALL_SECONDS
    return ('Standalone voice-memo uploads (such as M4A, MP3, WAV or OGG) are not supported. '
            f'The separate live call button supports sessions up to {CALL_SECONDS // 60} minutes, '
            'subject to microphone permission, configured Gemini access and budget admission; '
            'a working call is not verified by this explanation. '
            f'Supported video attachments are limited to {MAX_VIDEO_BYTES // (1024 * 1024)} MB; '
            f'analysis uses up to {MAX_VIDEO_FRAMES} sampled frames from the first {MAX_VIDEO_DURATION_S} seconds. '
            'Video audio transcription covers at most the first 30 seconds, only when local Whisper and its '
            'cached model are available. Transcription is not guaranteed; attach a text transcript when needed.')


INTEGRATION_NEED = re.compile(
    r'^(?:i|we)\s+(?:want|need|would like)\s+'
    r'(?:(?:(?:it|you|web bob|grok(?: bot)?|this)\s+)?(?:to\s+)?(?:be able to\s+)?'
    r'(?:coordinate|connect|interface|integrate|catch up)\b|'
    r'(?:coordination|integration|a connection)\s+(?:with|between)\b)',re.I)


def needs_grounding(text):
    """Ground capability questions and stated integration needs in actual code."""
    from answer_intent import instructions, requires_execution
    from resource_inventory import question as resource_question
    if resource_question(text):
        return True
    value = instructions(text).strip()
    if topic(value):
        return True
    question = re.match(r'^(?:(?:ok|okay|hey bob)[,!. ]+)*(?:(?:can|could|do|are|will) you\b|'
                         r'what (?:can you|are your)\b|how (?:can|do|does) (?:you|web bob)\b|'
                         r'(?:is|are) (?:your |the )?(?:calendar|timers?|routines?|voice|gmail|drive|browser)\b)', value, re.I)
    integration_need = (INTEGRATION_NEED.match(value)
        and re.search(r'\b(?:Grok|Web Bob)\b', value, re.I))
    return bool((question or integration_need)
                and re.search(r'\b(?:capabilit\w*|featur\w*|interface|integrat\w*|connect|coordinat\w*|'
                              r'catch up|better|as good|replace|alternative|instead|rather than|'
                              r'calendar|timers?|reminders?|routines?|local files?|terminal|gmail|google drive|'
                              r'browser|browsing|voice|images?|web search)\b', value, re.I)
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
''' + STATUS_RULES


def prepare_coordination(chat, conversation, text, request_id):
    """Turn an explicit coordination need into a saved, unconsumed local batch.

    Questions remain model answers. This operation reads the existing protocol;
    it neither contacts a receiver nor changes any acknowledgment or work scope.
    The private payload stays out of model context and public conversation exports.
    """
    from answer_intent import instructions, requires_execution
    value = instructions(text).strip()
    if (not INTEGRATION_NEED.match(value)
            or requires_execution(value)
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
    from build_info import BUILD
    return dict(
        source='Implemented Web Bob handlers in this code version; not proof of current provider health.',
        build={key: BUILD.get(key) for key in ('sha', 'short_sha', 'built_at')},
        status_rules=STATUS_RULES,
        current_setup='unverified by this capability explanation; consult scoped resource observations separately',
        live_availability='unverified by this capability explanation',
        workers_paused=workers_paused(root),
        reply_providers=list(reply_providers),
        capabilities=[dict(item, implemented=True, configured='unverified', live_verified='unverified')
                      for item in STACK.values()] + [
            dict(name='voice and media limits', source='webchat/voice.py; webchat/chat_media.py',
                 path=voice_limits()),
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
        ], missing_capabilities=dict(MISSING),
        coordination=observations, resources=__import__('resource_inventory').observe(root),
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
    'reminders': ('can you set reminders', 'can you remind me'),
    'timers': ('can you set timers', 'can you set a timer', 'do you support timers'),
    'routines': ('can you set routines', 'can you run morning routines', 'can you set morning routines'),
    'calendar': ('can you use google calendar', 'can you use my calendar', 'can you read my calendar',
                 'can you create calendar events', 'do you support google calendar', 'is calendar configured'),
    'local_files': ('can you read local files', 'can you write local files', 'can you delete local files',
                    'can you access my files'),
    'terminal': ('can you use the terminal', 'can you run terminal commands', 'can you run shell commands'),
    'search': ('can you search the web', 'can you do web searches'),
    'gmail': ('can you use gmail', 'can you read my gmail', 'can you send email through gmail'),
    'drive': ('can you use google drive', 'can you access google drive', 'can you save files to google drive'),
    'browser': ('can you browse the web', 'can you use a browser', 'can you open urls'),
    'image_generation': ('can you generate images', 'can you create images', 'can you make images'),
    'voice_memos': ('can you transcribe voice memos', 'can i send voice memos',
                    "what's the longest voice memo i can send", 'what are your voice memo limits'),
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


def workers_paused(root):
    return ((root / 'conductor/MAINTENANCE').exists() or
            (root / 'conductor/SOLO-WORKER').exists())


def reply(text, root):
    kind = topic(text)
    if kind is None:
        return None
    paused = workers_paused(root)
    worker = ('Additional workers and council are paused for solo work; Jobs shows the observed activity.'
              if paused else 'Coding jobs can be queued for draft work; Jobs shows whether they actually start.')
    answers = {
        'overview': ('This code version implements writing and songs, research with sources, saved memories, '
                     'direct Google Calendar reads and confirmed private event creation, reminders and timers, '
                     'read-only morning routines, bounded local files and fixed terminal commands, and attached photos or files. '
                     'Live voice uses the call button; standalone voice-memo uploads are unsupported. '
                     'Gmail, Google Drive, interactive browser control, arbitrary URL fetching and image generation are not implemented. '
                     'Web search is supported separately. Text sends through Andrea require explicit yes to the exact recipient '
                     'and content in a reviewed draft. Instinct stays read-only. ' + worker),
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
        'reminders': STACK['timers']['path'],
        'media': ('Yes—attach a photo, file, or video with your question. I can use extracted text and supported '
                  'image analysis; video uses sampled frames and available transcript, not every moment. '
                  'If something cannot be read, I’ll say so.'),
        'workers': worker,
        'git_force': ('A force push can replace the remote branch’s history, which can discard other people’s '
                      'commits. Web Bob can explain it and help review alternatives; it cannot run a force push.'),
        'git_ready': ('Removing draft status marks a pull request ready for review. The command “gh pr ready” '
                      'does that; it does not merge the code. Web Bob keeps pull requests as drafts.'),
        'git_merge': ('Merging a pull request integrates its changes into the target branch. Reviewing a PR '
                      'or opening a draft does not merge it. Web Bob can prepare and review draft changes.'),
    }
    if kind in ('voice', 'voice_memos'):
        answers[kind] = voice_limits()
    answers.update({key: item['path'] for key, item in STACK.items()})
    answers.update(MISSING)
    answer = answers[kind]
    if not kind.startswith('git_'):
        answer += (' Implemented support describes this code version; required setup is not checked here '
                   '(configured is separate from implemented), and live availability is not verified. '
                   'This explanation performs no action; saved holds and required approvals still apply.')
    return answer
