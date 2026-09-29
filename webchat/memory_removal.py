"""Owner-reviewed removal of one exact saved note, bound to the whole file."""
import hashlib
import re

from memory_store import DATED_ROW, MAX_BYTES, locked_memory, read_at, read_memory, replace_at

MANAGE = frozenset(('manage saved memories', 'remove saved memories', 'delete my saved memories',
                    'forget everything about me'))
SELECT = re.compile(r'^remove saved note ([a-f0-9]{64})$', re.I)
CONFIRM = re.compile(r'^yes,? remove saved note proposal ([a-f0-9-]{36})$', re.I)
SCOPE = ('Your chat history, other copies and other profile context remain. '
         'Information already sent to models is not erased.')


class Changed(ValueError):
    pass


def notes(value):
    rows = value['text'].splitlines(keepends=True)
    if value['truncated'] or any(not DATED_ROW.fullmatch(row) for row in rows):
        raise Changed('Saved notes include long or older multiline content that cannot be separated reliably. '
                      'No removal is offered for this file; nothing was changed.')
    digest = hashlib.sha256(value['text'].encode('utf-8')).hexdigest()
    return [dict(id=hashlib.sha256(f'{digest}:{index}'.encode()).hexdigest(), text=row)
            for index, row in enumerate(rows)]


def find(rows, identifier):
    for index, row in enumerate(rows):
        if row['id'] == identifier:
            return index, row
    raise Changed('Saved notes changed or that selection is stale. Open “Manage saved notes” and review again.')


def remove(root, identifier):
    with locked_memory(root) as folder:
        rows = notes(read_at(folder, MAX_BYTES))
        index, _ = find(rows, identifier)
        replace_at(folder, ''.join(row['text'] for i, row in enumerate(rows) if i != index))


def handle(chat, conversation, text, request_id, *, source_voice=None, provider='auto', worker=None, attachments=None):
    normalized = re.sub(r'\s+', ' ', text.strip().lower()).rstrip('.?!')
    selection, confirmation = SELECT.fullmatch(normalized), CONFIRM.fullmatch(normalized)
    pending = conversation.pop('pending_memory_removal', None)
    if pending:
        for message in conversation['messages']:
            card = message.get('action_card', {})
            if card.get('kind') == 'memory-remove' and card.get('proposal_id') == pending['proposal_id']:
                card.update(state='superseded', executable=False)
    cancel = normalized in ('never mind memory', 'cancel memory', 'dismiss memory', 'cancel', 'never mind')
    matches = normalized in MANAGE or normalized.startswith(('remove saved note', 'yes, remove saved note', 'yes remove saved note'))
    if not matches and not (cancel and pending):
        return None  # Every intervening turn revokes the old proposal.
    chat.texting.invalidate(conversation)
    for key in ('pending_job', 'pending_job_id', 'pending_council', 'pending_council_id', 'pending_memory', 'pending_memory_id'):
        conversation.pop(key, None)
    for message in conversation['messages']:
        if message.get('request_id') == request_id:
            message['private_memory'] = True
            if message.get('role') == 'user':
                message['memory_action_label'] = ('Review saved note' if selection else
                    'Confirm note removal' if confirmation else text)
    reply = conversation['messages'][-1]

    def respond(content):
        return chat.intent_reply(conversation, content, provider='memory')

    if source_voice or provider != 'auto' or worker is not None or attachments or chat.ledger_root(conversation['id']) != chat.root:
        return respond('Review and remove saved notes in typed Chat with Auto selected and no attachments. ' + SCOPE)
    if cancel and pending:
        return respond('Memory removal cancelled. Nothing was changed.')
    try:
        if confirmation:
            earlier_users = [m for m in conversation['messages'] if m.get('role') == 'user' and m.get('request_id') != request_id]
            previous_request = earlier_users[-1].get('request_id') if earlier_users else None
            if not pending or pending['proposal_id'] != confirmation[1] or previous_request != pending['proposal_id']:
                return respond('That removal approval is stale. Open “Manage saved notes” and review the note again.')
            remove(chat.root, pending['note_id'])
            invalidate = getattr(chat.providers, 'invalidate_snapshot', None)
            if invalidate:
                invalidate()
            return respond('Removed one saved Web Bob note. ' + SCOPE)
        if selection:
            _, row = find(notes(read_memory(chat.root)), selection[1])
            conversation['pending_memory_removal'] = dict(proposal_id=request_id, note_id=row['id'])
            reply['action_card'] = dict(id=request_id, proposal_id=request_id, kind='memory-remove',
                state='confirm', executable=True, reason='Remove this saved note?')
            return respond('Review the exact saved note:\n\n' + chat.redact(row['text'].rstrip('\n')) + '\n\n' + SCOPE +
                           '\nUse “Remove this note” to confirm or “Keep note” to cancel.')
        if normalized in MANAGE:
            rows = notes(read_memory(chat.root))
            # Preserve duplicate rows as separate choices; a removal affects exactly one.
            visible, size = [], 0
            for row in reversed(rows):
                size += len(row['text'].encode('utf-8'))
                if len(visible) == 50 or size > 16000:
                    break
                visible.append(dict(id=row['id'], text=chat.redact(row['text'].rstrip('\n'))))
            reply['memory_notes'] = list(reversed(visible))
            if not rows:
                return respond('No saved Web Bob notes to remove. ' + SCOPE)
            return respond('Manage saved notes: select one to review before removal. ' + SCOPE +
                ('\nShowing the newest notes that fit here; older notes are not shown.' if len(visible) < len(rows) else ''))
        return respond('Removal needs an exact note and a separate confirmation. Open “Manage saved notes” in Settings to review one.')
    except FileNotFoundError:
        return respond('No saved Web Bob notes were found. ' + SCOPE)
    except Changed as exc:
        return respond(str(exc))
    except OSError:
        return respond('I could not verify this memory operation. Show saved notes and review again before trying removal; '
                       'the notes may still exist.')
