"""Typed, expiring approval to replace one version-bound private memory row."""
import hashlib
import re
import time
import unicodedata

import chat_intent
from local_tasks import LocalTaskError, SECRET_PATH, safe_read
from memory_removal import Changed, SCOPE, find, notes
from memory_store import MAX_BYTES, locked_memory, read_at, read_memory, replace_at

MAX_REPLACEMENT_BYTES = 512
APPROVAL_SECONDS = 300
SELECT = re.compile(r'^edit saved note ([a-f0-9]{64}) with ([\s\S]*)$', re.I)
CONFIRM = re.compile(r'^yes,? edit saved note proposal ([a-f0-9-]{36})$', re.I)
COMMAND = re.compile(r'^(?:yes,?\s+)?edit\s+saved\s+note\b', re.I)
CANCEL = frozenset(('never mind memory', 'cancel memory', 'dismiss memory', 'cancel', 'never mind'))
SOURCE = 'conductor/webchat/memory/profile.md'


class Invalid(ValueError):
    pass


def sensitive(text, redact):
    if redact(text) != text:
        return True
    try:
        safe_read(text.encode('utf-8'))
    except LocalTaskError:
        return True
    parts = re.split(r'[\s/\\"\'<>:]+', text)
    return (any(SECRET_PATH.search(part) or part.lower() in ('.ssh', '.aws', '.gnupg', '.netrc')
                for part in parts)
            or bool(re.search(r'(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)', text))
            or bool(re.search(r'\b(?:password|passwd|api key|access token|private key)\s+(?:is\s+)?\S+', text, re.I)))


def validate_replacement(text, redact):
    if not text.strip():
        raise Invalid('Replacement text must not be empty.')
    if any(unicodedata.category(char).startswith('C') or char in '\u2028\u2029' for char in text):
        raise Invalid('Replacement must be one line without control characters.')
    if len(text.encode('utf-8')) > MAX_REPLACEMENT_BYTES:
        raise Invalid(f'Replacement must be at most {MAX_REPLACEMENT_BYTES} UTF-8 bytes.')
    if sensitive(text, redact):
        raise Invalid('Sensitive replacement refused. Remove credentials, payment card numbers and secret paths.')


def validate_request(text, redact):
    """Reject unsafe typed input before conversation, title or audit persistence."""
    if not COMMAND.match(text.lstrip()):
        return
    if any(unicodedata.category(char).startswith('C') or char in '\u2028\u2029' for char in text):
        raise Invalid('Saved-note edits must be one line without control characters.')
    selection = SELECT.fullmatch(text.strip())
    if selection:
        validate_replacement(selection[2], redact)
    elif not CONFIRM.fullmatch(text.strip()) and sensitive(text, redact):
        raise Invalid('Sensitive saved-note command refused. Remove credentials, payment card numbers and secret paths.')


def take_pending(conversation):
    """Every admitted turn revokes approval; private message storage stays off prompts."""
    pending = None
    for message in conversation['messages']:
        value = message.pop('_memory_edit', None)
        if value is not None:
            pending = value
    return pending


def replace(root, identifier, replacement, before_write):
    """Validate and consume under the same lock as append/removal, then verify bytes."""
    with locked_memory(root) as folder:
        rows = notes(read_at(folder, MAX_BYTES))
        index, row = find(rows, identifier)
        # Retain this row's date; the receipt records the correction separately.
        updated = row['text'][:13] + replacement + '\n'
        expected = ''.join(updated if i == index else item['text'] for i, item in enumerate(rows))
        if len(expected.encode('utf-8')) > MAX_BYTES:
            raise Invalid('The corrected saved-note file would be too large. Nothing was changed.')
        before_write()
        replace_at(folder, expected)
        observed = read_at(folder, MAX_BYTES)
        if observed['truncated'] or observed['text'] != expected:
            raise OSError('Memory replacement readback did not match.')
        return dict(new_note_id=notes(observed)[index]['id'],
                    version=hashlib.sha256(expected.encode('utf-8')).hexdigest())


def handle(chat, conversation, text, request_id, *, pending=None, source_voice=None,
           provider='auto', worker=None, attachments=None):
    selection, confirmation = SELECT.fullmatch(text), CONFIRM.fullmatch(text)
    cancel = text.lower() in CANCEL
    if not COMMAND.match(text) and not (cancel and pending):
        return None
    chat.texting.invalidate(conversation)
    for key in ('pending_job', 'pending_job_id', 'pending_council', 'pending_council_id',
                'pending_memory', 'pending_memory_id'):
        conversation.pop(key, None)
    for message in conversation['messages']:
        if message.get('request_id') == request_id:
            message['private_memory'] = True
            if message.get('role') == 'user':
                message['memory_action_label'] = 'Confirm note correction' if confirmation else 'Review note correction'
    reply = conversation['messages'][-1]

    def respond(content):
        return chat.intent_reply(conversation, content, provider='memory')

    def check_hold():
        # Personal memory has no project scope. Replacement prose cannot narrow
        # a saved hold, or act as permission to lift it.
        scopes = chat_intent.blocked_scopes(chat_intent.state_for(conversation), [])
        if scopes:
            raise Invalid(chat_intent.hold_reply(scopes) + ' No saved note was changed.')

    if source_voice or provider != 'auto' or worker is not None or attachments or chat.ledger_root(conversation['id']) != chat.root:
        return respond('Review and correct saved notes in typed Chat with Auto selected and no attachments. ' + SCOPE)
    if cancel:
        return respond('Memory correction cancelled. Nothing was changed.')
    try:
        check_hold()
        if confirmation:
            users = [m for m in conversation['messages'] if m.get('role') == 'user' and m.get('request_id') != request_id]
            previous = users[-1].get('request_id') if users else None
            if (not pending or pending['conversation_id'] != conversation['id'] or
                    pending['proposal_id'] != confirmation[1].lower() or previous != pending['proposal_id']):
                return respond('That correction approval is stale or unavailable. Review an exact replacement again; no edit is confirmed.')
            if not pending['created_at'] <= time.time() < pending['expires_at']:
                return respond('That correction approval expired. Review an exact replacement again; no edit is confirmed.')
            validate_replacement(pending['replacement'], chat.redact)
            invalidate = getattr(chat.providers, 'invalidate_snapshot', None)
            if not callable(invalidate):
                return respond('Memory correction is unavailable because fresh model context cannot be ensured. No edit is confirmed.')
            receipt = dict(state='unconfirmed', approval_state='consumed', source=SOURCE, note_id=pending['note_id'],
                           proposal_id=pending['proposal_id'], request_id=request_id)

            def consume():
                check_hold()
                if not pending['created_at'] <= time.time() < pending['expires_at']:
                    raise Invalid('That correction approval expired. No saved note was changed.')
                reply['memory_edit_receipt'] = receipt
                # take_pending removed the approval. This fsynced conversation
                # commit must succeed before the memory mutation can start.
                respond('Correction outcome not yet verified. Show saved notes before trying another correction.')

            verified = replace(chat.root, pending['note_id'], pending['replacement'], consume)
            invalidate()
            reply['memory_edit_receipt'] = dict(receipt, state='verified', **verified)
            return respond('Corrected one saved Web Bob note; the replacement was read back and verified. ' + SCOPE)
        if selection:
            validate_replacement(selection[2], chat.redact)
            _, row = find(notes(read_memory(chat.root)), selection[1].lower())
            now = time.time()
            reply['_memory_edit'] = dict(conversation_id=conversation['id'], proposal_id=request_id,
                note_id=row['id'], replacement=selection[2], created_at=now, expires_at=now + APPROVAL_SECONDS)
            old = row['text'][13:].rstrip('\n')
            old = '[sensitive note text redacted]' if sensitive(old, chat.redact) else chat.redact(old)
            return respond('Review saved note ' + row['id'] + ':\n\nOld: ' + old +
                '\nNew: ' + chat.redact(selection[2]) + '\n\nNothing has changed. Within five minutes, type:\n'
                'yes, edit saved note proposal ' + request_id + '\nAny intervening turn cancels this approval. ' + SCOPE)
        return respond('Use “manage saved memories” to find a note ID, then type “edit saved note <ID> with <replacement>”. '
                       'Review the old and new text before a separate confirmation. Replacement must be one line, at most 512 UTF-8 bytes.')
    except (Changed, Invalid) as exc:
        reply.pop('_memory_edit', None)
        return respond(str(exc))
    except OSError:
        reply.pop('_memory_edit', None)
        if 'memory_edit_receipt' in reply:
            reply['memory_edit_receipt']['state'] = 'unconfirmed'
        return respond('I could not verify this memory correction. No edit is confirmed; the saved note may have changed. '
                       'Show saved notes and review again before trying another correction.')
