#!/usr/bin/env python3
"""Solo release checks and rollback transaction; never starts council or workers.

Historical vendor gates are superseded by Jeff's 2026-09-29 solo instruction.
Product acceptance tests remain unchanged. Live replay must never send a text.
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone

CODE = Path(__file__).resolve().parents[1]
if __name__ == '__main__' and '--root' in sys.argv:
    os.environ['BOB_ROOT'] = sys.argv[sys.argv.index('--root') + 1]
sys.path[:0] = [str(CODE / d) for d in ('webchat', 'services', 'state', 'reviews', 'release')]
from release_ownership import serialized
import activation_journal as journal
from texting_deploy_record import atomic_json, atomic_text, require_disk_space, reserve_recovery, release_recovery
from live_redeploy_check import Client, require

ORDER = ('texting', 'gaps', 'media', 'voice', 'ui', 'instinct', 'remaining', 'bridge', 'improve')
BASE = 'draft/webbob-clean-0927'


def andrea_pin():
    return json.loads((CODE / 'release/andrea-bridge.json').read_text())


def andrea_gates(root):
    sha = andrea_pin()['sha']
    folder = root / 'conductor/reviews' / ('SOLO-0018-andrea-bridge-' + sha[:12])
    results = [json.loads((folder / (name + '.json')).read_text()) for name in ('major', 'docs', 'build')]
    for row in results:
        require(row['sha'] == sha and row['exit'] == 0 and digest(row['log']) == row['log_sha256'],
                'Andrea exact-tip full checks failed or changed')
    return dict(sha=sha, results=results)


def bridge_replay(root, cid, draft_id):
    """Inspect health and committed cancellation; never try an ordinary send."""
    import sqlite3
    from texting import Andrea
    config_path = root / 'conductor/webchat/andrea-bridge.json'
    require(config_path.is_file() and not config_path.is_symlink() and not config_path.stat().st_mode & 0o077,
            'Bridge configuration is not private')
    cfg = json.loads(config_path.read_text())
    health = Andrea(cfg['url'], cfg['token']).call('health')
    require(health.get('ok') and health.get('connected') and health.get('paused') is False and
            health.get('instinctReadOnly') is True and health.get('sha') == andrea_pin()['sha'],
            'Actual Andrea bridge is unavailable or at the wrong revision')
    saved = json.loads((root / 'conductor/webchat/sessions' / (cid + '.json')).read_text())
    remote = saved['_texting']['drafts'][draft_id]['bridge']
    with sqlite3.connect(Path(cfg['audit_db']).resolve().as_uri() + '?mode=ro', uri=True) as db:
        row = db.execute('SELECT state, digest, actionId FROM webbob_drafts WHERE id = ?', (remote['draftId'],)).fetchone()
    require(row == ('cancelled', remote['digest'], remote['actionId']), 'Andrea cancellation was not durably recorded')
    return [dict(check='actual Andrea exact-build health, persisted challenge and durable cancellation',
                 andrea_sha=health['sha'], passed=True, real_texts_sent=0)]


def run(argv, **kw):
    return subprocess.check_output([str(a) for a in argv], text=True, timeout=60, **kw).strip()


def git(*args):
    return run(['git', '-C', CODE, *args])


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_digest(folder):
    values = []
    for path in sorted(Path(folder).rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
            values.append((str(path.relative_to(folder)), digest(path)))
    return hashlib.sha256(json.dumps(values, separators=(',', ':')).encode()).hexdigest()


def identity():
    sha = git('rev-parse', 'HEAD')
    require(git('branch', '--show-current').startswith('draft/'), 'Release requires a draft branch')
    require(not git('status', '--porcelain'), 'Release checkout must be clean')
    return sha


def submit(client, cid, prompt, request=None, attachments=None):
    import uuid
    request = request or str(uuid.uuid4())
    payload = dict(conversation_id=cid, message=prompt, request_id=request)
    if attachments:
        payload['attachments'] = attachments
    value = client.call('/api/messages', payload)
    deadline = time.monotonic() + 90
    while True:
        answer = next(m for m in value['messages'] if m.get('role') == 'assistant' and m.get('request_id') == request)
        if answer['status'] == 'done':
            require(bool(answer['content'].strip()), 'Empty reply')
            require(not answer.get('task_ids') and not answer.get('task_id'), 'Solo replay dispatched a worker')
            return value, answer
        require(answer['status'] not in ('error', 'cancelled', 'waiting'), 'Replay reply failed')
        require(time.monotonic() < deadline, 'Replay reply timed out')
        time.sleep(.2)
        value = client.call('/api/conversations/' + cid)


def bridge_replay_target(chat):
    """Select a personal direct recipient; SMS short codes are not send targets."""
    from texting import recipient, TextingError
    try:
        target = recipient(chat)
        if len(target['addresses']) != 1 or not re.fullmatch(r'(?:iMessage|SMS|RCS);-;[^;\s]+', target['guid']):
            return False
        address = target['addresses'][0].strip().lower()
        guid_address = target['guid'].split(';')[2].strip().lower()
        if address != guid_address:
            return False
        if '@' in address:
            return bool(re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9.-]+\.[a-z]{2,}", address))
        return bool(re.fullmatch(r'\+?[0-9 ().-]+', address) and
                    10 <= len(re.sub(r'\D', '', address)) <= 15)
    except (TextingError, KeyError, TypeError):
        return False


def replay(client, root, sha, *, real_reads=False, feature='texting'):
    """Authenticated no-send regression; sensitive message content stays in sessions."""
    client.login()
    require(client.call('/api/version')['sha'] == sha, 'Live version differs from candidate')
    cid = client.new()
    receipts = []
    for prompt, provider, expected in (
        ('texting help', 'texting', 'draft'),
        ('yes wbtxt-00000000000000000000000000000000', 'texting', 'Nothing sent.'),
        ('cancel text draft 0000000000000000', 'texting', 'no longer current'),
        ('what version are you?', 'dispatcher', sha[:7]),
    ):
        value, answer = submit(client, cid, prompt)
        require(answer.get('provider') == provider, 'Wrong route for ' + prompt)
        require(expected.lower() in answer['content'].lower(), 'Wrong response for ' + prompt)
        again, duplicate = submit(client, cid, prompt, answer['request_id'])
        require(duplicate == answer and len(again['messages']) == len(value['messages']), 'Idempotency failed')
        receipts.append(dict(prompt=prompt, request_id=answer['request_id'], provider=provider,
                             answer_sha256=hashlib.sha256(answer['content'].encode()).hexdigest(), passed=True))
    if real_reads:
        # Real BlueBubbles reads; do not include thread content/addresses in evidence.
        _, answer = submit(client, cid, 'texts')
        require(answer.get('provider') == 'texting' and answer['content'].startswith('Recent text threads'),
                'BlueBubbles live read failed')
        receipts.append(dict(prompt='texts', provider='texting', passed=True,
                             answer_sha256=hashlib.sha256(answer['content'].encode()).hexdigest()))
    from texting import BlueBubbles
    target = 'Alex Morgan'
    if real_reads:
        from instinct import Instinct
        from texting import recipient
        chats = BlueBubbles().chats()
        protected = Instinct(None)
        protected.bind_state(root / 'conductor/webchat')
        protected.observe(chats)
        choices = [c for c in chats if not protected.is_target(recipient(c)) and
                   (ORDER.index(feature) < ORDER.index('bridge') or bridge_replay_target(c))]
        require(bool(choices), 'No ordinary messaging thread available for no-send replay')
        target = choices[0]['guid']
    _, drafted = submit(client, cid, 'draft reply to ' + target + ': Web Bob no-send verification. Cancel this draft.')
    card = drafted.get('text_draft', {})
    require(card.get('state') == 'pending' and card.get('body') == 'Web Bob no-send verification. Cancel this draft.',
            'Draft did not bind the exact recipient/body')
    if ORDER.index(feature) >= ORDER.index('bridge'):
        require(card.get('delivery_available') is True, 'Andrea did not persist the exact draft challenge')
    token = card['confirm_message']
    _, bare = submit(client, cid, 'yes')
    require(bare['content'].startswith('Nothing sent.'), 'Bare yes authorized delivery')
    _, cancelled = submit(client, cid, 'cancel text draft ' + card['id'])
    require(cancelled['content'] == 'Text draft cancelled. Nothing sent.', 'Draft cancel failed')
    _, stale = submit(client, cid, token)
    require('already used, cancelled, or replaced' in stale['content'], 'Cancelled token was accepted')
    receipts.append(dict(check='exact draft, bare approval, cancel, stale token', passed=True))
    if ORDER.index(feature) >= ORDER.index('bridge') and real_reads:
        receipts.extend(bridge_replay(root, cid, card['id']))
    _, newer = submit(client, cid, 'draft reply to ' + target + ': Version interruption check. Do not send.')
    require(newer.get('text_draft', {}).get('state') == 'pending', 'Interruption-check draft failed')
    confirmation = newer['text_draft']['confirm_message']
    submit(client, cid, 'what version are you?')
    _, revoked = submit(client, cid, confirmation)
    require('already used, cancelled, or replaced' in revoked['content'], 'Version lookup retained stale text consent')
    receipts.append(dict(check='version lookup revokes previous text consent', passed=True))
    if ORDER.index(feature) >= ORDER.index('gaps'):
        receipts.extend(gaps_replay(client, cid, root, real=real_reads))
    if ORDER.index(feature) >= ORDER.index('media'):
        receipts.extend(media_replay(client, root, real=real_reads))
    if ORDER.index(feature) >= ORDER.index('instinct'):
        receipts.extend(instinct_replay(client, cid))
    if ORDER.index(feature) >= ORDER.index('remaining'):
        receipts.extend(remaining_replay(client, cid))
    if feature == 'improve':
        receipts.extend(capability_replay(client, cid, root))
        receipts.extend(memory_removal_replay(client, cid, root, real=real_reads))
        if real_reads:
            receipts.extend(delivered_notice_replay(client, root))
    from task_dispatch import task_queue
    require(not any(r['conversation_id'] == cid for r in task_queue.tasks(root).values()), 'Replay queued work')
    saved = json.loads((root / 'conductor/webchat/sessions' / (cid + '.json')).read_text())
    require(not saved.get('_texting', {}).get('audit'), 'Replay attempted delivery')
    return dict(all_pass=True, conversation_id=cid, checks=receipts, real_texts_sent=0, queued_workers=0)


def memory_removal_replay(client, cid, root, *, real):
    import uuid
    from bob_gaps import profile_path
    path = profile_path(root)
    before = path.read_bytes()
    _, answer = submit(client, cid, 'manage saved memories')
    require(answer.get('provider') == 'memory' and answer.get('private_memory') and not answer.get('attempts'),
            'Memory management must stay private and deterministic')
    if real:
        # Production replay may inspect/cancel but never remove an owner note.
        _, refusal = submit(client, cid, 'yes, remove saved note proposal ' + str(uuid.uuid4()))
        require('stale' in refusal['content'], 'Unbound removal approval was accepted')
        require(path.read_bytes() == before, 'Memory inspection/refusal modified owner notes')
        return [dict(check='private memory management and unbound removal refusal; owner notes unchanged', passed=True)]
    choices = answer.get('memory_notes', [])
    require(bool(choices), 'Synthetic staging notes are missing removal choices')
    _, proposed = submit(client, cid, 'remove saved note ' + choices[0]['id'])
    require(path.read_bytes() == before, 'Review changed memory before confirmation')
    _, removed = submit(client, cid, 'yes, remove saved note proposal ' + proposed['action_card']['proposal_id'])
    require('Removed one saved Web Bob note' in removed['content'], 'Synthetic removal failed')
    require(path.read_bytes() == b''.join(before.splitlines(keepends=True)[1:]), 'Removal changed another note')
    return [dict(check='synthetic staging exact-note review and separate removal confirmation', passed=True)]


def capability_replay(client, cid, root):
    from capabilities import reply
    checks = []
    jobs = client.call('/api/jobs/activity')
    solo_mode = (root / 'conductor/SOLO-WORKER').exists()
    paused = solo_mode or (root / 'conductor/MAINTENANCE').exists()
    require(jobs.get('dispatch', {}).get('mode') == ('solo' if solo_mode else 'paused' if paused else 'enabled')
            and jobs.get('dispatch_paused') == paused, 'Jobs must explain the current dispatch pause')
    require(jobs['dispatch']['queued'] == (jobs['details']['queued'] if jobs['inspection']['queue_available'] else None),
            'Jobs waiting count must agree with the inspected queue')
    checks.append(dict(check='Jobs dispatch mode and honest waiting count', passed=True))
    for row in jobs['recently_finished']:
        if row.get('source') == 'lane_observation':
            require(row['state'] == 'unverified' and row.get('finished_at') is None
                    and isinstance(row.get('last_activity_at'), (int, float)),
                    'Archived lane has no authority to claim completion')
    checks.append(dict(check='archived lanes cannot claim verified completion', passed=True))
    for prompt in ('Can you send texts?', 'What can you do?', 'Can you remember things?',
                   'Can you start workers?', 'Can you text Instinct?', 'Can you set reminders?',
                   'Can you watch videos?', 'Can we talk?', 'What does force-push mean?',
                   'Explain gh pr ready.', 'What does merging a PR mean?'):
        started = time.monotonic()
        value, answer = submit(client, cid, prompt)
        elapsed = time.monotonic() - started
        require(answer.get('provider') == 'capabilities' and answer['content'] == reply(prompt, root),
                'Capability reply must be accurate and server-owned')
        require(not answer.get('attempts'), 'Capability question entered a model lane')
        again, duplicate = submit(client, cid, prompt, answer['request_id'])
        require(answer == duplicate and len(value['messages']) == len(again['messages']),
                'Capability replay was not idempotent')
        checks.append(dict(prompt=prompt, passed=True, seconds=round(elapsed, 4), provider='capabilities'))
    return checks


def delivered_notice_replay(client, root):
    """Recover one already delivered release notice; never submit send authority."""
    notice_path = root / 'conductor/reviews/BEAT-GROK-0700-milestone-1-notice.json'
    if not notice_path.exists():
        return []
    notice = json.loads(notice_path.read_text())
    require(notice.get('real_confirmations_submitted') == notice.get('real_texts_sent') == 1 and
            notice.get('resends') == 0, 'Notice requires reconciliation before receipt replay')
    path = root / 'conductor/webchat/sessions' / (notice['conversation_id'] + '.json')
    before = json.loads(path.read_text())['_texting']
    draft = before['drafts'][notice['draft_id']]
    require(draft['state'] in ('delivery_unconfirmed', 'sent') and draft['token'] is None and
            draft['bridge']['actionId'] == notice['action_id'] and
            hashlib.sha256(draft['body'].encode()).hexdigest() == notice['body_sha256'] and
            len(before['audit']) == 1, 'Existing notice consent or identity changed')
    _, answer = submit(client, notice['conversation_id'], 'check text delivery ' + notice['draft_id'])
    after = json.loads(path.read_text())['_texting']
    require(answer.get('provider') == 'texting' and 'nothing was resent' in answer['content'].lower() and
            after['drafts'][notice['draft_id']]['state'] == 'sent' and len(after['audit']) == 1 and
            after['audit'][0]['event'] == 'owner_sent_via_andrea', 'Existing verified receipt was not recovered')
    _, cancelled = submit(client, notice['conversation_id'], 'cancel text draft ' + notice['draft_id'])
    final = json.loads(path.read_text())['_texting']
    require(cancelled.get('provider') == 'texting' and 'already verified sent' in cancelled['content'] and
            'cannot recall' in cancelled['content'] and 'Nothing sent.' not in cancelled['content'] and
            final == after, 'Cancellation must preserve the verified delivery outcome and consumed consent')
    return [dict(check='existing delivered milestone receipt recovered without another confirmation or send',
                 passed=True, real_texts_sent=0, additional_confirmations=0),
            dict(check='cancel after delivery preserves the verified outcome and makes no recall claim', passed=True)]


def instinct_replay(client, cid):
    _, answer = submit(client, cid, 'digest Instinct')
    require(answer.get('provider') == 'instinct' and 'read from BlueBubbles' in answer['content'],
            'Verified live Instinct mapping/read is unavailable')
    for category in ('Bills / deadlines', 'Security', 'Appointments'):
        require(category + ':' in answer['content'], 'Missing Instinct digest category')
    digest_hash = hashlib.sha256(answer['content'].encode()).hexdigest()
    _, drafted = submit(client, cid, 'draft reply to Instinct: Please prepare options for Jeff to review.')
    card = drafted.get('text_draft', {})
    require(card.get('state') == 'read_only' and card.get('read_only') and card.get('confirm_message') is None,
            'Instinct draft exposed send authority')
    require(card.get('body') == '[Bob via Andrea]\nPlease prepare options for Jeff to review.', 'Instinct draft differs')
    for attempt in ('yes', 'yes wbtxt-' + 'a' * 32):
        _, denied = submit(client, cid, attempt)
        require('Instinct is read-only' in denied['content'], 'Instinct confirmation was not permanently refused')
    _, cancelled = submit(client, cid, 'cancel text draft ' + card['id'])
    require('Nothing sent.' in cancelled['content'], 'Instinct cancellation failed')
    return [dict(check='verified Instinct digest, all flag categories, read-only draft, confirmations refused, cancel',
                 answer_sha256=digest_hash, passed=True)]


def remaining_replay(client, cid):
    import uuid
    body = 'Web Bob local reminder replay ' + uuid.uuid4().hex[:8]
    _, saved = submit(client, cid, 'remind me to ' + body + ' in 1 second')
    require(saved.get('provider') == 'reminders' and 'Reminder saved' in saved['content'], 'Reminder was not saved')
    deadline = time.monotonic() + 10
    while True:
        history = client.call('/api/conversations/' + cid)
        notices = [m for m in history['messages'] if m.get('reminder_notice') and body in m['content']]
        if notices:
            break
        require(time.monotonic() < deadline, 'Due reminder did not reach chat through the background loop')
        time.sleep(.2)
    require(len(notices) == 1, 'Duplicate reminder delivery')
    _, repeated = submit(client, cid, 'remind me every 1 minute to ' + body + ' recurring')
    match = re.search(r'ID ([0-9a-f]{16})', repeated['content'])
    require(match is not None, 'Recurring reminder did not save')
    identifier = match[1]
    _, cancelled = submit(client, cid, 'cancel reminder ' + identifier)
    require('cancelled' in cancelled['content'], 'Recurring reminder cancellation failed')
    rows = client.call('/api/reminders')['reminders']
    require(next(r for r in rows if r['id'] == identifier)['state'] == 'cancelled', 'Cancellation was not durable')
    for command in ('Karen QA status', 'band desk status'):
        _, answer = submit(client, cid, command)
        require(answer.get('provider') == 'teammates' and 'Source:' in answer['content'], 'Teammate status lacks its source')
    _, digest = submit(client, cid, 'band desk digest')
    evidence = digest.get('teammate_evidence', {})
    require(digest.get('provider') == 'teammates' and evidence.get('all_read') is True and
            bool(evidence.get('band_reads')), 'Configured Band Desk read failed')
    return [dict(check='real due reminder, exactly once, repeating cancellation, sourced Karen/Band Desk status and read-only digest',
                 passed=True, answer_sha256=hashlib.sha256(digest['content'].encode()).hexdigest())]


def gaps_replay(client, cid, root, *, real):
    from bob_gaps import profile_path
    fact = 'Instinct may digest and flag bills, security and appointments, and draft replies, but must never send.'
    base = root / 'bob-brain/memory/profile.md'
    original_hash = digest(base) if base.exists() else None
    _, proposal = submit(client, cid, 'remember that ' + fact)
    require(proposal.get('action_card', {}).get('state') == 'confirm', 'Memory lacks confirmation')
    _, saved = submit(client, cid, 'yes, save memory proposal ' + proposal['action_card']['proposal_id'])
    require(saved.get('action_card', {}).get('state') == 'done' and fact.rstrip('.') in profile_path(root).read_text(),
            'Confirmed memory was not persisted')
    require((digest(base) if base.exists() else None) == original_hash, 'Memory modified main checkout')
    from memory_store import read_memory
    import stat
    require(fact.rstrip('.') in read_memory(root)['text'], 'Private memory reader did not recover saved fact')
    require(stat.S_IMODE(profile_path(root).stat().st_mode) == 0o600 and
            stat.S_IMODE(profile_path(root).parent.stat().st_mode) == 0o700,
            'Memory file/directory permissions are not private')
    saved_hash = digest(profile_path(root))
    _, repeated = submit(client, cid, 'remember that ' + fact)
    require(repeated.get('action_card', {}).get('state') == 'confirm', 'Repeated memory lacks confirmation')
    _, confirmed = submit(client, cid, 'yes, save memory proposal ' + repeated['action_card']['proposal_id'])
    require(confirmed.get('action_card', {}).get('state') == 'done' and
            digest(profile_path(root)) == saved_hash, 'Repeated confirmed memory changed saved bytes')
    _, inspected = submit(client, cid, 'show my saved memories')
    require(inspected.get('provider') == 'memory' and inspected.get('private_memory') is True and
            fact.rstrip('.') in inspected['content'] and 'not all profile or chat context' in inspected['content'] and
            not inspected.get('attempts'), 'Memory inspection must read saved facts directly without model inference')
    _, search = submit(client, cid, 'look up Python programming language')
    require(search['provider'] == 'state' and 'python' in search['content'].lower() and 'https://' in search['content'],
            'Web research lacked a supported answer/source')
    _, shot = submit(client, cid, 'take a screenshot')
    match = re.search(r'/api/captures/([0-9a-f]{16})', shot['content'])
    require(match is not None, 'Screenshot capture failed')
    import urllib.request
    raw = client.open(urllib.request.Request(client.url + match[0], headers={'Origin': client.url}), parse=False)
    require(raw.startswith(b'\x89PNG\r\n\x1a\n'), 'Authenticated screenshot is not PNG')
    return [dict(check='confirmed private memory overlay; bounded direct private inspection; owner-only permissions; main unchanged', passed=True),
            dict(check='separate confirmation of the same dated fact preserves saved memory bytes', passed=True),
            dict(check='web research with source', real_network=real, passed=True),
            dict(check='authenticated screenshot PNG', real_capture=real, sha256=hashlib.sha256(raw).hexdigest(), passed=True)]


def media_replay(client, root, *, real):
    import base64
    import uuid
    import urllib.request
    from test_chat_media import png_fixture, pdf_fixture
    cid = client.new()
    note, pdf = 'clarinet-' + uuid.uuid4().hex[:8], 'cello-' + uuid.uuid4().hex[:8]
    files = [('picture.png', png_fixture()), ('note.txt', ('Token: ' + note).encode()),
             ('document.pdf', pdf_fixture('Token: ' + pdf))]
    uploaded = []
    for filename, raw in files:
        info = client.call('/api/media/upload', dict(conversation_id=cid, filename=filename,
                          data_base64=base64.b64encode(raw).decode()))
        served = client.open(urllib.request.Request(client.url + info['url'], headers={'Origin': client.url}), parse=False)
        require(served == raw, 'Media download changed bytes')
        uploaded.append(info)
    with tempfile.TemporaryDirectory(prefix='solo-live-media-') as tmp:
        clip = Path(tmp) / 'clip.mp4'
        subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi',
                        '-i', 'color=c=red:s=64x64:d=1', '-an', '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
                        '-movflags', '+faststart', str(clip)], check=True, timeout=15)
        raw = clip.read_bytes()
        video = client.call('/api/media/upload', dict(conversation_id=cid, filename='clip.mp4', data_base64=base64.b64encode(raw).decode()))
        partial = client.open(urllib.request.Request(client.url + video['url'],
                              headers={'Origin': client.url, 'Range': 'bytes=0-15'}), parse=False)
        require(partial == raw[:16], 'Live video range/seek failed')
    wrong = client.new()
    try:
        client.call(uploaded[0]['url'].replace(cid, wrong))
    except RuntimeError as error:
        require('HTTP 404' in str(error), 'Cross-conversation media denial was not 404')
    else:
        raise RuntimeError('Cross-conversation attachment access succeeded')
    prompt = "Describe the dominant color in the attached image and give the Token value in the text file and PDF. Echo the image as an attachment."
    ids = [row['media_id'] for row in uploaded]
    value, answer = submit(client, cid, prompt, attachments=ids)
    verify_media_answer(answer, note, pdf, ids[0], real=real)
    repeated, duplicate = submit(client, cid, prompt, answer['request_id'], attachments=ids)
    require(duplicate == answer and len(repeated['messages']) == len(value['messages']), 'Media replay duplicated inference')
    return [dict(check='image/text/PDF upload/download ownership and idempotent multimodal reply',
                 conversation_id=cid, provider=answer.get('provider'), real_provider=real,
                 answer_sha256=hashlib.sha256(answer['content'].encode()).hexdigest(), passed=True)]


def verify_media_answer(answer, note, pdf, image_id, *, real):
    require(not real or answer.get('provider') == 'gemini', 'Live image answer did not use the vision provider')
    require('red' in answer['content'].lower() and note in answer['content'] and pdf in answer['content'],
            'Media model did not read the real image/text/PDF')
    require('Attachment notes:' not in answer['content'], 'Media model used incomplete attachment content')
    require(any(a['media_id'] == image_id for a in answer.get('attachments', [])), 'Image was not returned as an owned attachment')


def staging(root, sha, feature):
    from app import Chat, Server
    # No model inference needed for these deterministic commands. Real messaging reads
    # are reserved for production. No fixture can authorize a real send.
    from texting_fixture import MockMessaging, OfflineProviders
    from texting import Texting, BlueBubbles, Andrea
    with tempfile.TemporaryDirectory(prefix='solo-staging-') as folder:
        private = Path(folder)
        mock = MockMessaging(private)
        mock.enable_web_bob_send = ORDER.index(feature) >= ORDER.index('bridge')
        if ORDER.index(feature) >= ORDER.index('instinct'):
            from instinct_fixture import GUID, MESSAGES
            mock.chats.append(dict(guid=GUID, displayName='Instinct',
                participants=[dict(address='+15550101999')], lastMessage=dict(MESSAGES[0])))
            mock.messages = [dict(m) for m in MESSAGES]
        class StagingProviders(OfflineProviders):
            def reply(self, conversation, cancel, progress):
                user = next(m for m in reversed(conversation['messages']) if m['role'] == 'user')
                if user.get('attachments'):
                    from chat_media import validate_attachment_ids, enrich_for_model
                    metas = validate_attachment_ids(private, user['attachments'], conversation_id=conversation['id'])
                    bundle = enrich_for_model(private, metas, redact=lambda text: text)
                    require(not bundle['warnings'], 'Staging media extraction failed')
                    tokens = re.findall(r'(?:clarinet|cello)-[0-9a-f]{8}', bundle['text'])
                    return dict(content='Red. ' + ' '.join(tokens) + ' <bob-webchat-attachment media_id="' + metas[0]['media_id'] + '" />', provider='fixture', attempts=[])
                return super().reply(conversation, cancel, progress)
        chat = Chat(private / 'conductor/webchat', private, StagingProviders(),
                    texting=Texting(BlueBubbles(mock.config_db), Andrea(mock.base, mock.token)))
        if ORDER.index(feature) >= ORDER.index('remaining'):
            band = private / 'bin/band_messages_watch_run.py'
            band.parent.mkdir()
            band.write_text("CHATS = [{'name': 'Stalemate', 'chat_guid': 'fixture-band'}]\n")
            mock.chats.append(dict(guid='fixture-band', displayName='Stalemate', participants=[]))
            qa = private / 'wt-webjam-polish/PRE_KAREN_QA.md'
            qa.parent.mkdir()
            qa.write_text('Karen remains pending.')
            from unittest.mock import Mock
            chat.providers.start_probes = lambda: None
            chat.providers.circuit = Mock()
            chat.start_background()
        server = Server(('127.0.0.1', 0), chat)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            from contextlib import ExitStack
            from unittest.mock import patch
            with ExitStack() as stack:
                if ORDER.index(feature) >= ORDER.index('gaps'):
                    def fake_capture(root, target=None):
                        path = root / 'conductor/webchat/captures/0123456789abcdef.png'
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes(b'\x89PNG\r\n\x1a\n')
                        return path.stem, path
                    stack.enter_context(patch('app.capture_screenshot', side_effect=fake_capture))
                    stack.enter_context(patch('app.web_search', return_value=dict(answer='Python is a programming language.', source='https://www.python.org/')))
                proof = replay(Client(f'http://127.0.0.1:{server.server_port}', chat.folder / '.password'), private, sha, feature=feature)
            require(not mock.sends and not mock.unexpected_writes, 'Staging attempted messaging write')
            return dict(scope='real isolated HTTP; synthetic messaging; no workers', **proof)
        finally:
            server.shutdown()
            server.server_close()
            chat.close()
            mock.close()


def checks(root, feature):
    sha = identity()
    out = root / 'conductor/reviews' / f'SOLO-0018-{feature}-{sha[:12]}'
    out.mkdir(mode=0o700, exist_ok=True)
    if feature == 'improve':
        attempts = sorted(out.glob('attempt-*'))
        out = out / f'attempt-{len(attempts) + 1:04d}'
        out.mkdir(mode=0o700)
        # A crash or failed staging run remains a failed attempt, never an old green.
        atomic_json(out / 'checks.json', dict(sha=sha, feature=feature, all_pass=False, at=time.time()))
    require_disk_space(root, CODE, 'checks')
    commands = {name: [sys.executable, '-m', 'unittest', 'discover', '-s', name, '-p', 'test_*.py']
                for name in ('webchat', 'services', 'reviews', 'release')}
    if ORDER.index(feature) >= ORDER.index('bridge'):
        commands['bridge-contract'] = [sys.executable, 'release/bridge_probe.py', '--andrea',
            str(root / 'workspaces/andrea-webbob-bridge-0018'), '--output', str(out / 'bridge-contract.json')]
    commands['eval'] = [sys.executable, 'webchat/bob_parity_eval.py']
    commands['browser'] = [sys.executable, 'webchat/texting_proof.py', '--output-dir', str(out / 'texting-browser')]
    if ORDER.index(feature) >= ORDER.index('media'):
        commands['media-browser'] = [sys.executable, 'webchat/media_browser_test.py', '--screenshots', str(out / 'media-browser')]
    if ORDER.index(feature) >= ORDER.index('voice'):
        commands['voice-js'] = ['node', '--test', 'webchat/test_voice_js.cjs']
        commands['voice-browser'] = [sys.executable, 'release/voice_probe.py', '--root', str(root), '--output', str(out / 'voice-browser')]
    if ORDER.index(feature) >= ORDER.index('instinct'):
        commands['instinct-browser'] = [sys.executable, 'webchat/instinct_proof.py', '--output-dir', str(out / 'instinct-browser')]
    if ORDER.index(feature) >= ORDER.index('remaining'):
        commands['remaining-browser'] = [sys.executable, 'webchat/remaining_proof.py', '--output-dir', str(out / 'remaining-browser')]
    if feature == 'improve':
        commands['cold-browser'] = [sys.executable, 'webchat/cold_start_proof.py', '--output-dir', str(out / 'cold-browser')]
        commands['startup-recovery-browser'] = [sys.executable, 'webchat/startup_recovery_proof.py', '--output-dir', str(out / 'startup-recovery-browser')]
        commands['voice-availability-browser'] = [sys.executable, 'webchat/voice_availability_proof.py', '--output-dir', str(out / 'voice-availability-browser')]
        commands['jobs-results-browser'] = [sys.executable, 'webchat/jobs_results_proof.py', '--output-dir', str(out / 'jobs-results-browser')]
        commands['memory-removal-browser'] = [sys.executable, 'webchat/memory_removal_proof.py', '--output-dir', str(out / 'memory-removal-browser')]
        commands['reply-lifecycle-browser'] = [sys.executable, 'webchat/reply_lifecycle_proof.py', '--output-dir', str(out / 'reply-lifecycle-browser')]
    for path in sorted((CODE / 'webchat').glob('test_*.mjs')):
        commands[path.stem] = ['node', str(path)]

    def check(item):
        name, argv = item
        log = out / (name + '.log')
        env = {k: v for k, v in os.environ.items() if not any(s in k.upper() for s in ('KEY', 'TOKEN', 'SECRET', 'PASSWORD'))}
        env.pop('PYTHONPATH', None)
        env.pop('NODE_PATH', None)
        env.pop('BOB_ANDREA_WEBBOB_CONFIG', None)
        env.pop('ANDREA_WEBBOB_CONFIG_PATH', None)
        # macOS /var is a symlink: existing repo identity tests expect canonical
        # temporary paths, matching the predecessor release harness.
        env['TMPDIR'] = '/private/tmp'
        env['BOB_PLAYWRIGHT_MODULE'] = str(root / 'conductor/webchat/node_modules/playwright')
        with tempfile.TemporaryDirectory(prefix='solo-tests-', dir='/private/tmp') as tmp, log.open('w') as stream:
            env['BOB_ROOT'] = tmp
            process = subprocess.Popen(argv, cwd=CODE, env=env, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
            deadline = time.monotonic() + 900
            try:
                while process.poll() is None:
                    # Stop our own test groups with headroom before crossing the floor.
                    require(shutil.disk_usage(root).free >= 5 * 1024**3 + 128 * 1024**2,
                            'Tests reached disk safety headroom')
                    require(time.monotonic() < deadline, 'Test suite exceeded deadline')
                    time.sleep(.5)
            except BaseException:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=10)
                raise
        body = log.read_text()
        count = re.search(r'Ran (\d+) tests?', body)
        skipped = re.search(r'skipped=(\d+)', body)
        receipt = dict(command=argv, exit=process.returncode, log=str(log), log_sha256=digest(log),
                       tests=int(count[1]) if count else None, skipped=int(skipped[1]) if skipped else 0)
        print(name + ': ' + str(process.returncode), flush=True)
        return name, receipt

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = dict(pool.map(check, [(n, a) for n, a in commands.items() if not n.endswith('browser')]))
    # Browser/listener assertions are serialized after suites that use private listeners.
    for name in (n for n in commands if n.endswith('browser')):
        name, receipt = check((name, commands[name]))
        results[name] = receipt
    require(identity() == sha, 'Candidate changed during checks')
    passed = all(r['exit'] == 0 and r['skipped'] == 0 for r in results.values())
    record = dict(sha=sha, feature=feature, all_pass=passed, results=results, at=time.time())
    if passed and ORDER.index(feature) >= ORDER.index('bridge'):
        record['andrea'] = andrea_gates(root)
    if passed:
        record['staging'] = staging(root, sha, feature)
    atomic_json(out / 'checks.json', record)
    require(passed, 'Offline check failed; inspect ' + str(out))
    print(str(out / 'checks.json'), flush=True)


def verify_checks(sha, feature, check_path):
    check = json.loads(check_path.read_text())
    require(check['sha'] == sha and check['feature'] == feature,
            'Stale or wrong-feature release evidence')
    require(check['all_pass'] and check['staging']['all_pass'], 'Tests/evals/staging failed')
    required = {'webchat', 'services', 'reviews', 'release', 'eval', 'browser'}
    if ORDER.index(feature) >= ORDER.index('media'):
        required.add('media-browser')
    if ORDER.index(feature) >= ORDER.index('voice'):
        required.update(('voice-js', 'voice-browser'))
    if ORDER.index(feature) >= ORDER.index('instinct'):
        required.add('instinct-browser')
    if ORDER.index(feature) >= ORDER.index('remaining'):
        required.add('remaining-browser')
    if feature == 'improve':
        required.update(('cold-browser', 'startup-recovery-browser', 'voice-availability-browser', 'jobs-results-browser', 'reply-lifecycle-browser', 'memory-removal-browser'))
    if ORDER.index(feature) >= ORDER.index('bridge'):
        required.add('bridge-contract')
        require(check.get('andrea', {}).get('sha') == andrea_pin()['sha'], 'Andrea exact-tip evidence missing')
        for row in check['andrea']['results']:
            require(row['exit'] == 0 and digest(row['log']) == row['log_sha256'], 'Andrea suite/log changed')
        contract = json.loads((check_path.parent / 'bridge-contract.json').read_text())
        require(contract['all_pass'] and contract['andrea_sha'] == andrea_pin()['sha'] and contract['real_texts_sent'] == 0,
                'Cross-repository protocol proof failed')
    required.update(p.stem for p in (CODE / 'webchat').glob('test_*.mjs'))
    require(required <= check['results'].keys(), 'Missing mandatory suite')
    for name in required:
        row = check['results'][name]
        require(row['exit'] == 0 and row['skipped'] == 0 and digest(row['log']) == row['log_sha256'],
                'Failed/skipped/changed check: ' + name)


def consecutive_checks(sha, feature, check_path):
    attempts = sorted(check_path.parent.parent.glob('attempt-*'))
    require(len(attempts) >= 2 and attempts[-1] == check_path.parent,
            'Two consecutive latest pre-deploy greens are required')
    for attempt in attempts[-2:]:
        verify_checks(sha, feature, attempt / 'checks.json')
    return [dict(path=str(p / 'checks.json'), sha256=digest(p / 'checks.json')) for p in attempts[-2:]]


def verify_gates(sha, feature, check_path, review_path):
    verify_checks(sha, feature, check_path)
    review = json.loads(review_path.read_text())
    require(review['sha'] == sha and review['feature'] == feature, 'Stale or wrong-feature release evidence')
    pair = consecutive_checks(sha, feature, check_path) if feature == 'improve' else None
    require(review['reviewer'] == 'Codex solo' and review['verdict'] == 'PASS' and
            review['checks_sha256'] == digest(check_path) and review['findings'] and
            not review.get('unresolved_blockers'), 'Self-review missing or unresolved')
    result = dict(checks_sha256=digest(check_path), self_review_sha256=digest(review_path))
    if pair:
        result['predeploy_greens'] = pair
    return result


def versions(root, expected):
    result = {}
    origin = (root / 'conductor/webchat/.public-origin').read_text().strip()
    for name, url in (('local', 'http://127.0.0.1:8787'), ('public', origin)):
        client = Client(url, root / 'conductor/webchat/.password')
        client.login()
        result[name] = client.call('/api/version')
        require(result[name]['sha'] == expected, 'Wrong ' + name + ' version')
    return result


@serialized
def restart(root, pins):
    """Only the web server restarts; no job-runner or council resurrection."""
    journal.permit_restart(root, pins)
    from state import lock
    from runtime import screen_sessions
    with lock('supervisor'):
        before = screen_sessions()
        require('svc-job-runner' not in before, 'Solo deployment requires stopped worker runner')
        p = subprocess.run(['lsof', '-t', '-iTCP:8787', '-sTCP:LISTEN'], capture_output=True, text=True)
        pids = p.stdout.split()
        require(p.returncode in (0, 1) and len(pids) <= 1, 'Ambiguous server listener')
        pid = int(pids[0]) if pids else None
        if pid:
            command = run(['ps', '-p', pid, '-o', 'command='])
            require(str(root) in command and '/webchat/app.py' in command, 'Listener ownership mismatch')
        for name, code in pins.items():
            atomic_text(root / 'conductor/state' / (name + '-code-root'), str(code) + '\n')
        if 'svc-webchat' in before:
            run(['screen', '-S', before['svc-webchat'], '-X', 'quit'])
        if pid:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            for _ in range(60):
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    break
                time.sleep(.25)
            else:
                raise RuntimeError('Old web server did not exit')
        env = dict(os.environ, BOB_ROOT=str(root), BOB_WEBCHAT_DRILLS='0')
        run(['screen', '-dmS', 'svc-webchat', '/bin/bash', root / 'conductor/webchat/run.sh'], env=env)
        import urllib.request
        for _ in range(80):
            try:
                with urllib.request.urlopen('http://127.0.0.1:8787/login', timeout=1) as response:
                    if response.status == 200 and response.headers.get('X-Bob-Webchat') == '1':
                        break
            except OSError:
                pass
            time.sleep(.25)
        else:
            raise RuntimeError('New web server did not become healthy')
        after = screen_sessions()
        require(all(after.get(n) == value for n, value in before.items() if n.startswith('svc-') and n != 'svc-webchat'),
                'Unrelated durable service changed')
        require('svc-job-runner' not in after, 'Worker runner unexpectedly started')
        return dict(before=before, after=after, restarted=['svc-webchat'])


def verify_recovery_pins(root, record):
    """An old rollback must never replace a newer release, even at the same SHA."""
    candidate = Path(record['rollback']) / 'candidate'
    for name in ('webchat', 'dispatch'):
        current = Path((root / 'conductor/state' / (name + '-code-root')).read_text().strip())
        allowed = {candidate.resolve(): record['sha'],
                   Path(record['snapshots'][name]).resolve(): record['previous']}
        original = record.get('original_pins', {}).get(name)
        if original:
            allowed[Path(original).resolve()] = record['previous']
        require(current.is_absolute() and current.resolve() in allowed,
                'Rollback refused: code pin belongs to an unrelated release')
        require(json.loads((current / 'webbob-build.json').read_text())['sha'] == allowed[current.resolve()],
                'Rollback refused: pinned build identity changed')


@serialized
def recover(root, record):
    journal.match(root, record)
    verify_recovery_pins(root, record)
    for name, expected in record.get('snapshot_hashes', {}).items():
        require(source_digest(Path(record['snapshots'][name])) == expected, 'Rollback snapshot changed: ' + name)
    release_recovery(record)
    unchanged = False
    try:
        versions(root, record['previous'])
        pins = [Path((root / 'conductor/state' / (name + '-code-root')).read_text().strip()) for name in ('webchat', 'dispatch')]
        unchanged = all(json.loads((p / 'webbob-build.json').read_text())['sha'] == record['previous'] for p in pins)
    except (OSError, ValueError, RuntimeError):
        pass
    if not unchanged:
        restart(root, record['snapshots'])
    record['rollback_restart_needed'] = not unchanged
    record['restored'] = versions(root, record['previous'])
    record.update(rolled_back=True, all_pass=False, status='ROLLED_BACK')


@serialized
def transaction(root, record, path, activate, live, publish=atomic_json, final_path=None):
    """Any post-activation failure, including final publication, restores predecessor."""
    journal.require_clear(root)
    activated = False
    intent = None
    try:
        require_disk_space(root, CODE, 'before-activation')
        record.update(activated=True, status='ACTIVATING')
        publish(path, record)
        intent = journal.begin(root, record, path, final_path)
        activated = True
        activate()
        record['rounds'] = []
        for index in (1, 2):
            require_disk_space(root, CODE, 'live-round-' + str(index))
            proof = live()
            require(proof.get('all_pass') is True, 'Live replay failed')
            record['rounds'].append(proof)
            publish(path, record)
        record.update(all_pass=True, status='LIVE_PASS', finished_at=time.time())
        publish(path, record)
        if final_path:
            publish(final_path, record)
        release_recovery(record)
        journal.finish(root, intent)
    except BaseException as exc:
        record.update(all_pass=False, failure=type(exc).__name__ + ': ' + str(exc))
        if activated:
            try:
                recover(root, record)
            except BaseException as recovery_error:
                record['rollback_error'] = type(recovery_error).__name__ + ': ' + str(recovery_error)
        else:
            release_recovery(record)
        # Rollback happens before attempting any potentially failing evidence write.
        atomic_json(path, record)
        if final_path:
            atomic_json(final_path, record)
        if intent and record.get('rolled_back') and not record.get('rollback_error'):
            journal.finish(root, intent)
        raise


@serialized
def deploy(args):
    root = args.root
    journal.require_clear(root)
    sha = identity()
    gates = verify_gates(sha, args.feature, args.checks, args.review)
    from runtime import screen_sessions, service_enabled
    require(not service_enabled('job-runner') and not service_enabled('reviewer'), 'Persistent solo shutdown marker missing')
    require(not {'svc-job-runner', 'svc-reviewer'} & screen_sessions().keys(), 'Council/worker service is running')
    index = ORDER.index(args.feature)
    if index:
        predecessor = root / 'conductor/reviews' / ('SOLO-0018-' + ORDER[index - 1] + '-live.json')
        if args.feature == 'improve':
            latest = root / 'conductor/reviews/SOLO-0018-improve-live.json'
            if latest.exists():
                value = json.loads(latest.read_text())
                if value.get('all_pass') and value.get('sha') == args.previous:
                    predecessor = latest
                elif value.get('previous') == args.previous and value.get('rolled_back'):
                    predecessor = Path(value['predecessor_receipt'])
        prior = json.loads(predecessor.read_text())
        require(prior['all_pass'] and prior['sha'] == args.previous and len(prior['rounds']) == 2 and
                all(r['all_pass'] for r in prior['rounds']), 'Predecessor has not passed two live rounds')
    else:
        require(args.previous == 'a777736b3f0a37c82b0c4c62be8c91117c4c9881', 'Initial baseline changed')
    remote = dict(line.split()[::-1] for line in git('ls-remote', 'origin', 'refs/heads/' + BASE).splitlines())
    merge = remote['refs/heads/' + BASE]
    git('fetch', '--no-tags', 'origin', BASE)
    git('merge-base', '--is-ancestor', sha, merge)
    require(not git('diff', '--name-only', sha, merge), 'Clean merge differs from checked tree')
    pr = json.loads(run(['gh', 'pr', 'view', args.pr, '--json', 'headRefOid,baseRefName,isDraft,state']))
    require(pr['headRefOid'] == sha and pr['baseRefName'] == BASE and pr['isDraft'] and
            pr['state'] in ('OPEN', 'MERGED'), 'PR is not the checked draft')
    versions(root, args.previous)
    client = Client('http://127.0.0.1:8787', root / 'conductor/webchat/.password')
    client.login()
    session = client.call('/api/session')
    require(not session.get('active_conversations') and not session.get('active_conversation'), 'Chat reply in flight')
    require_disk_space(root, CODE, 'snapshot')
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    folder = root / 'rollbacks' / ('webbob-solo-' + args.feature + '-' + stamp)
    folder.mkdir(mode=0o700)
    record = dict(sha=sha, feature=args.feature, previous=args.previous, gates=gates, draft_pr=args.pr,
                  rollback=str(folder), all_pass=False, activated=False, snapshots={}, original_pins={}, at=time.time())
    if index:
        shutil.copyfile(predecessor, folder / 'predecessor-receipt.json')
        record['predecessor_receipt'] = str(folder / 'predecessor-receipt.json')
    for name in ('webchat', 'dispatch'):
        prior = Path((root / 'conductor/state' / (name + '-code-root')).read_text().strip())
        require(json.loads((prior / 'webbob-build.json').read_text())['sha'] == args.previous, 'Pin baseline mismatch')
        record['original_pins'][name] = str(prior)
        snapshot = folder / ('previous-' + name)
        shutil.copytree(prior, snapshot, ignore=shutil.ignore_patterns('.git', '.password', '.session-secret',
            'keys.env', '.env', '.env.*', 'sessions', 'node_modules', '__pycache__', 'uploads', 'evidence', 'task-runs'))
        record['snapshots'][name] = str(snapshot)
    record['snapshot_hashes'] = {name: source_digest(Path(p)) for name, p in record['snapshots'].items()}
    # Freeze tracked candidate bytes; future edits to the worktree cannot change live code.
    release = folder / 'candidate'
    release.mkdir(mode=0o700)
    archive = subprocess.Popen(['git', '-C', str(CODE), 'archive', sha], stdout=subprocess.PIPE)
    extracted = subprocess.run(['tar', '-xf', '-', '-C', str(release)], stdin=archive.stdout)
    archive.stdout.close()
    require(extracted.returncode == archive.wait() == 0, 'Candidate archive failed')
    atomic_json(release / 'webbob-build.json', dict(sha=sha, built_at=datetime.now(timezone.utc).isoformat()))
    path = folder / 'release.json'
    atomic_text(folder / 'rollback.sh', '#!/bin/bash\nset -euo pipefail\n' + shlex.join([
        sys.executable, str(release / 'release/solo.py'), 'rollback', '--root', str(root),
        '--feature', args.feature, '--record', str(path)]) + '\n')
    (folder / 'rollback.sh').chmod(0o700)
    reserve_recovery(path, record)
    atomic_json(path, record)
    origin = (root / 'conductor/webchat/.public-origin').read_text().strip()

    def live():
        pair = versions(root, sha)
        results = [replay(Client(url, root / 'conductor/webchat/.password'), root, sha, real_reads=True, feature=args.feature)
                   for url in ('http://127.0.0.1:8787', origin)]
        number = len(record.get('rounds', [])) + 1
        browser_path = folder / f'browser-round-{number}.json'
        env = dict(os.environ, BOB_PLAYWRIGHT_MODULE=str(root / 'conductor/webchat/node_modules/playwright'))
        run(['node', CODE / 'webchat/capture_parity.cjs', root, origin, sha,
             folder / f'browser-round-{number}.png', browser_path], env=env)
        browser = json.loads(browser_path.read_text())
        require(browser['pass_check'], 'Live browser check failed')
        if ORDER.index(args.feature) >= ORDER.index('voice'):
            from voice_probe import probe
            for name, url in (('local', 'http://127.0.0.1:8787'), ('public', origin)):
                results.append(probe(root, folder / f'voice-{name}-round-{number}', url,
                                     engines=('chromium',) if name == 'local' else ('webkit',)))
        return dict(all_pass=all(r['all_pass'] for r in results), versions=pair, endpoints=results,
                    browser=dict(path=str(browser_path), sha256=digest(browser_path), passed=True))

    transaction(root, record, path, lambda: restart(root, dict(webchat=release, dispatch=release)), live,
                final_path=root / 'conductor/reviews' / ('SOLO-0018-' + args.feature + '-live.json'))
    print('LIVE_PASS ' + sha + ' rollback=' + str(folder), flush=True)


@serialized
def rollback(root, path):
    intent = journal.pending(root)
    if intent:
        require(Path(path).resolve() == Path(intent['path']).resolve(),
                'Rollback does not belong to the unfinished Web Bob activation')
        record = journal.saved_record(root, intent)
    else:
        record = journal.private_json(path)
        # Validate before creating a recovery obligation for a stale receipt.
        verify_recovery_pins(root, record)
        intent = journal.begin(root, record, path)
    recover(root, record)
    atomic_json(path, record)
    if intent['final_path']:
        atomic_json(intent['final_path'], record)
    journal.finish(root, intent)


@serialized
def recover_pending(root):
    intent = journal.pending(root)
    require(intent is not None, 'No unfinished Web Bob activation to recover')
    rollback(root, Path(intent['path']))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('check', 'deploy', 'rollback', 'recover-pending'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--feature', choices=ORDER, required=True)
    parser.add_argument('--previous')
    parser.add_argument('--pr')
    parser.add_argument('--checks', type=Path)
    parser.add_argument('--review', type=Path)
    parser.add_argument('--record', type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    os.environ['BOB_ROOT'] = str(args.root)
    def interrupted(signum, frame):
        raise RuntimeError('Release interrupted by signal ' + str(signum))
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, interrupted)
    if args.action == 'check':
        checks(args.root, args.feature)
    elif args.action == 'deploy':
        deploy(args)
    elif args.action == 'recover-pending':
        recover_pending(args.root)
    else:
        rollback(args.root, args.record)


if __name__ == '__main__':
    main()
