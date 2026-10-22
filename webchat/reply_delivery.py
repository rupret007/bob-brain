"""Receipts for the existing saved-history transport. No send/model/action tools."""
import json
import hashlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from webbob.chat_reply import ChatReplyJournal, ChatReplyError

IDENTITY = re.compile(r'[a-f0-9-]{36}')


def rendering(message):
    """Bind the actual public text/artifact/attachment rendering, not model output."""
    if (message.get('role') != 'assistant' or message.get('status') != 'done'
            or message.get('texting') or message.get('private_memory')
            or message.get('private_draft')
            or message.get('provider') == 'drafts'
            or message.get('voice_call_id') or message.get('reminder_notice')
            or not isinstance(message.get('request_id'), str)
            or not isinstance(message.get('id'), str)
            or not IDENTITY.fullmatch(message['id']) or not message.get('content')):
        return None
    body = json.dumps({key: message.get(key) for key in ('content', 'artifact', 'attachments')},
                      ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    digest = hashlib.sha256(body.encode()).hexdigest()
    # A mutable status card is not another reply. Changed visible text is a new
    # version of the same display row; each version has its own exact receipt.
    # Journal only the rendering digest. Long writing/artifacts need receipts
    # too; no raw private reply text enters the journal's bounded payload.
    return dict(id='web:' + message['id'] + ':' + digest[:24], sha256=digest), 'sha256:' + digest


def acknowledge(folder, conversation_id, message, expected):
    observed = rendering(message)
    if observed is None or observed[0] != expected:
        raise ChatReplyError('Reply rendering changed or is unavailable.')
    metadata, body = observed
    journal = ChatReplyJournal(folder / 'reply-receipts.sqlite', 'bob-chat:' + conversation_id)
    return journal.acknowledge_visible(metadata['id'], body)
