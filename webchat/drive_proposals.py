"""Exact-text, local-only Drive proposals. This module has no remote write route.

P13's raw export/download is complete or raises at its transport byte limit.
Never build a complete-document proposal from its formatted excerpt receipt.
Approval is consumed durably before storage; ambiguous failures require a fresh
preview, never an automatic retry. A restart cannot replay the old approval.
"""
from datetime import datetime
import difflib
import hashlib
import itertools
import json
import os
import re
import secrets
import time
import unicodedata

import chat_intent
from drive_read import DOC_MIME, TEXT_MIME, DriveError, verified_metadata
from memory_edit import sensitive

APPROVAL_SECONDS = 300
SOURCE_LIMIT = 32 * 1024
REPLACEMENT_LIMIT = 16 * 1024
DIFF_LIMIT = 2000
SELECT = re.compile(r'^prepare drive replacement ([A-Za-z0-9_-]{10,128})\r?\n([\s\S]*)$', re.I)
CONFIRM = re.compile(r'^yes,? save drive proposal ([a-f0-9-]{36})$', re.I)
COMMAND = re.compile(r'^\s*(?:prepare\s+drive\s+replacement\b|(?:yes,?\s+)?save\s+drive\s+proposal\b|cancel\s+drive\s+proposal\b|drive\s+proposal\s+help\b)', re.I)
HELP = ('Type “prepare drive replacement FILE_ID”, then a newline and the exact replacement text. '
        'Only one Google Doc or plain text ID is supported. Review the diff, then separately approve '
        'saving a local proposal. No Drive edit, upload, sharing or send is authorized.')


class Invalid(ValueError):
    pass


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n'


def sensitive_text(text, redact):
    return sensitive(text, redact) or bool(re.search(r'\bya29\.[A-Za-z0-9_.-]+', text))


def validate_text(text, redact, limit):
    if not isinstance(text, str):
        raise Invalid('Source read was incomplete or invalid; no complete-document proposal was produced.')
    try:
        if len(text.encode('utf-8')) > limit:
            raise Invalid('Text exceeds the complete-document limit; no proposal was produced. Nothing was truncated into a proposal.')
        if any(unicodedata.category(c).startswith('C') and c not in '\n\r\t' for c in text):
            raise Invalid('Unsupported control characters; no proposal was produced.')
        if sensitive_text(text, redact):
            raise Invalid('Sensitive text refused; no proposal was produced. Remove credentials and secret paths.')
    except UnicodeError:
        raise Invalid('Invalid text; no proposal was produced.') from None


def validate_request(text, redact):
    """Run before history, title or any generic intent observes replacement prose."""
    if not COMMAND.match(text):
        return
    selection = SELECT.fullmatch(text)
    if selection:
        validate_text(selection[2], redact, REPLACEMENT_LIMIT)
    elif not CONFIRM.fullmatch(text.strip()) and sensitive_text(text, redact):
        raise Invalid('Sensitive proposal command refused; it was not saved.')


def take_pending(conversation):
    pending = None
    for message in conversation['messages']:
        value = message.pop('_drive_proposal', None)
        if value is not None:
            pending = value
    return pending


def read_source(client, source_id, redact):
    client.configured()
    raw = client.metadata(source_id)
    if isinstance(raw, dict) and not raw.get('modifiedTime'):
        raise Invalid('Source version could not be observed; no local proposal saved.')
    meta = verified_metadata(raw, source_id)
    if datetime.fromisoformat(meta['modifiedTime'].replace('Z', '+00:00')).tzinfo is None:
        raise Invalid('Source version could not be observed; no local proposal saved.')
    if meta['mimeType'] == DOC_MIME:
        text = client.export_text(source_id)
    elif meta['mimeType'] == TEXT_MIME:
        text = client.download_text(source_id)
    else:
        raise Invalid('Only a Google Doc or plain text source is supported; no proposal was produced.')
    # P13 returns raw text, never a {text, truncated} excerpt object. Reject all
    # alternate/incomplete envelopes and reject oversize rather than slicing.
    validate_text(text, redact, SOURCE_LIMIT)
    return meta, text


def small_diff(old, new):
    lines = list(itertools.islice(difflib.unified_diff(
        old.splitlines(keepends=True), new.splitlines(keepends=True),
        fromfile='observed source', tofile='exact replacement', n=2), 41))
    value = '\n'.join(line.rstrip('\r\n') for line in lines[:40])
    clipped = len(lines) > 40 or len(value) > DIFF_LIMIT
    return (value[:DIFF_LIMIT] or '(No text differences.)') + (
        '\n[Diff preview clipped; source read was complete.]' if clipped else '')


def save_private(folder, record, before_commit):
    """Publish one immutable 0600 JSON file through pinned, non-symlink dirs.

    Exclusive link prevents overwrites across processes. Failed temporary writes
    are removed; a failure after publication remains unconfirmed, never retried.
    """
    if not re.fullmatch(r'[a-f0-9-]{36}', record['proposal_id']):
        raise Invalid('Invalid proposal identity.')
    payload = encode(record).encode('utf-8')
    parent = os.open(folder, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    directory = None
    temporary = '.' + secrets.token_hex(16) + '.tmp'
    try:
        try:
            os.mkdir('drive-proposals', mode=0o700, dir_fd=parent)
        except FileExistsError:
            pass
        directory = os.open('drive-proposals', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        os.fchmod(directory, 0o700)
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=directory)
        with os.fdopen(fd, 'wb') as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        before_commit()
        filename = record['proposal_id'] + '.json'
        os.link(temporary, filename, src_dir_fd=directory, dst_dir_fd=directory, follow_symlinks=False)
        os.unlink(temporary, dir_fd=directory)
        os.fsync(directory)
        os.fsync(parent)
        fd = os.open(filename, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        with os.fdopen(fd, 'rb') as handle:
            if handle.read(len(payload) + 1) != payload:
                raise OSError('Local proposal readback mismatch.')
        return hashlib.sha256(payload).hexdigest()
    finally:
        if directory is not None:
            try:
                os.unlink(temporary, dir_fd=directory)
            except FileNotFoundError:
                pass
            finally:
                os.close(directory)
        os.close(parent)


def handle(chat, conversation, text, request_id, *, source_voice=None, provider='auto',
           worker=None, attachments=None):
    pending = take_pending(conversation)  # Every admitted intervening turn revokes approval.
    if not COMMAND.match(text):
        return None
    selection, confirmation = SELECT.fullmatch(text), CONFIRM.fullmatch(text.strip())
    chat.texting.invalidate(conversation)
    for key in ('pending_job', 'pending_job_id', 'pending_council', 'pending_council_id',
                'pending_memory', 'pending_memory_id', 'pending_memory_removal'):
        conversation.pop(key, None)
    for message in conversation['messages']:
        message.pop('_memory_edit', None)
        if message.get('request_id') == request_id:
            # Existing private rendering, voice, provider and handoff boundaries.
            message['private_memory'] = True
            if message.get('role') == 'user':
                message['memory_action_label'] = 'Review Drive replacement' if selection else 'Local Drive proposal control'
    if conversation['title'] == 'New conversation':
        conversation['title'] = 'Private Drive proposal'
    reply = conversation['messages'][-1]

    def respond(content):
        return chat.intent_reply(conversation, content, provider='drive-proposal')

    def check_hold():
        scopes = chat_intent.blocked_scopes(chat_intent.state_for(conversation), [])
        if scopes:
            raise Invalid('On hold: ' + ', '.join(scopes) + '. No local proposal saved; Drive unchanged.')

    if source_voice or provider != 'auto' or worker is not None or attachments or chat.ledger_root(conversation['id']) != chat.root:
        return respond('Use typed Chat with Auto and no attachments for local Drive proposals.')
    if text.strip().lower() == 'cancel drive proposal':
        return respond('Local proposal approval cancelled. Drive unchanged.')
    try:
        check_hold()
        if confirmation:
            users = [m for m in conversation['messages'] if m.get('role') == 'user' and m.get('request_id') != request_id]
            previous = users[-1] if users else {}
            if (not pending or pending.get('conversation_id') != conversation['id'] or
                    pending.get('proposal_id') != confirmation[1].lower() or
                    previous.get('request_id') != pending.get('proposal_id')):
                return respond('That local proposal approval is stale, consumed or belongs to another chat. Prepare a new proposal.')
            sealed = {k: v for k, v in pending.items() if k != 'approval_digest'}
            original = SELECT.fullmatch(previous.get('content', ''))
            if (digest(encode(sealed)) != pending.get('approval_digest') or not original or
                    original[1] != pending.get('source_id') or original[2] != pending.get('replacement_text') or
                    digest(pending['replacement_text']) != pending.get('replacement_digest')):
                return respond('The local replacement or proposal changed; approval invalidated. Prepare a new proposal.')

            def recheck():
                check_hold()
                if not pending['created_at'] <= time.time() < pending['expires_at']:
                    raise Invalid('That local proposal approval expired. Prepare a new proposal.')

            recheck()
            validate_text(pending['replacement_text'], chat.redact, REPLACEMENT_LIMIT)
            record = dict(sealed, status='local_only', approval_state='consumed',
                          confirmation_request_id=request_id, saved_at=time.time())
            receipt = dict(state='unconfirmed', approval_state='consumed', proposal_id=pending['proposal_id'],
                           source_id=pending['source_id'], observed_modified_time=pending['observed_modified_time'],
                           replacement_digest=pending['replacement_digest'], request_id=request_id,
                           remote_mutation_attempted=False, source_version_reverified_at_save=False)
            reply['drive_proposal_receipt'] = receipt
            # Persist consumption before the local effect. If this fails, the
            # storage function is never reached. Never restore uncertain consent.
            respond('Local save is unconfirmed. Drive unchanged. Approval consumed; prepare a new proposal before retrying.')
            stored = chat.drive_proposal_store(chat.folder, record, recheck)
            if stored != digest(encode(record)):
                raise OSError('Local proposal storage did not verify exact bytes.')
            reply['drive_proposal_receipt'] = dict(receipt, state='saved', local_file_digest=stored)
            return respond('Local proposal saved. Drive unchanged.\nProposal: ' + pending['proposal_id'] +
                           '\nSource ID: ' + pending['source_id'] + '\nObserved modifiedTime: ' + pending['observed_modified_time'] +
                           '\nReplacement SHA-256: ' + pending['replacement_digest'] +
                           '\nSource version was observed during preview; it was not reverified at local save. '
                           'This approval does not authorize applying or sharing the replacement.')
        if selection:
            validate_text(selection[2], chat.redact, REPLACEMENT_LIMIT)
            meta, old = read_source(chat.drive.client, selection[1], chat.redact)
            check_hold()
            now = time.time()
            value = dict(conversation_id=conversation['id'], proposal_id=request_id, source_id=selection[1],
                         observed_modified_time=meta['modifiedTime'], source_mime_type=meta['mimeType'],
                         source_digest=digest(old), source_bytes=len(old.encode('utf-8')),
                         replacement_text=selection[2], replacement_digest=digest(selection[2]),
                         replacement_bytes=len(selection[2].encode('utf-8')), diff_preview=small_diff(old, selection[2]),
                         created_at=now, expires_at=now + APPROVAL_SECONDS)
            value['approval_digest'] = digest(encode(value))
            reply['_drive_proposal'] = value
            return respond('Review local replacement only. Source ID: ' + selection[1] +
                           '\nObserved modifiedTime: ' + meta['modifiedTime'] +
                           '\nComplete source bytes: ' + str(value['source_bytes']) +
                           '\nExact replacement bytes: ' + str(value['replacement_bytes']) +
                           '\nReplacement SHA-256: ' + value['replacement_digest'] +
                           '\n\nUntrusted document text — diff preview:\n' + value['diff_preview'] +
                           '\n\nNo proposal file saved yet. Drive unchanged. Within five minutes, type:\n'
                           'yes, save drive proposal ' + request_id +
                           '\nAny intervening turn cancels approval. Approval saves only this exact local proposal; '
                           'it never authorizes a remote edit or sharing.')
        return respond(HELP)
    except Invalid as exc:
        reply.pop('_drive_proposal', None)
        return respond(str(exc))
    except (DriveError, OSError, ValueError, TypeError, KeyError):
        reply.pop('_drive_proposal', None)
        if 'drive_proposal_receipt' in reply:
            reply['drive_proposal_receipt']['state'] = 'unconfirmed'
            return respond('Local proposal save could not be confirmed; a local file may exist. Drive unchanged. '
                           'Approval consumed; prepare a new proposal before retrying. Source version was not reverified at save.')
        return respond('Could not completely read the source and its version. No proposal created. Drive unchanged.')
