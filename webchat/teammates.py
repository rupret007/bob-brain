"""Read-only teammate evidence. Never contacts a reviewer or starts a watcher."""
import ast
from datetime import datetime, timezone
import hashlib
import re
import time

from instinct import private_excerpt
from texting import TextingError, time_label, timestamp


def source(root, relative):
    path = root / relative
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 256 * 1024:
        return None
    raw = path.read_bytes()
    return dict(text=raw.decode('utf-8', errors='replace'), path=relative,
                modified_at=path.stat().st_mtime, sha256=hashlib.sha256(raw).hexdigest())


def band_mappings(root):
    record = source(root, 'bin/band_messages_watch_run.py')
    if not record:
        return []
    # Read the already-configured identities as data. Never import/execute the watch.
    try:
        syntax = ast.parse(record['text'])
        assignment = next(n for n in syntax.body if isinstance(n, ast.Assign) and
                          any(isinstance(t, ast.Name) and t.id == 'CHATS' for t in n.targets))
        value = ast.literal_eval(assignment.value)
        if not isinstance(value, list) or len(value) > 20:
            return []
        rows = [dict(name=v['name'], guid=v['chat_guid']) for v in value
                if isinstance(v, dict) and isinstance(v.get('name'), str) and
                isinstance(v.get('chat_guid'), str) and 1 <= len(v['chat_guid']) <= 500]
        if len({r['name'].casefold() for r in rows}) != len(rows):
            return []
        return rows
    except (ValueError, SyntaxError, StopIteration, KeyError):
        return []


def status(root):
    qa = source(root, 'wt-webjam-polish/PRE_KAREN_QA.md')
    if qa:
        matches = re.findall(r'(?:independent Karen review\s+remain incomplete|Karen\s+remains pending)', qa['text'], re.I)
        statement = 'The saved QA handoff says Karen’s independent review is pending.' if matches else 'A saved QA handoff exists, but it does not establish Karen’s current decision.'
        karen = dict(name='Karen', summary=statement + ' This is a document report, not a new review or approval.',
                     source=qa['path'], modified_at=qa['modified_at'], sha256=qa['sha256'])
    else:
        karen = dict(name='Karen', summary='No readable QA handoff is available. Karen’s review status is unverified.')
    bands = band_mappings(root)
    band = dict(name='Band Desk', summary='Music operations for ' + ', '.join(r['name'] for r in bands) +
                '. Read or digest the existing threads; draft replies in Texts. Jeff approves sends, and Travis owns Rad Dad booking.'
                if bands else 'No verified band-thread mapping is available. No band messages were guessed.',
                configured_bands=[r['name'] for r in bands], source='bin/band_messages_watch_run.py' if bands else None)
    return dict(checked_at=time.time(), teammates=[karen, band], read_only=True)


def handle(chat, conversation, text, request_id):
    command = text.strip().casefold().rstrip('.?!')
    if command in ('karen', 'karen status', 'karen qa status', 'band desk', 'band desk status', 'teammates', 'teammate status'):
        value = status(chat.root)
        rows = value['teammates'] if command.startswith('teammate') else [r for r in value['teammates'] if r['name'].casefold() in command]
        lines = []
        for row in rows:
            line = row['name'] + ': ' + row['summary']
            if row.get('source'):
                line += '\nSource: ' + row['source']
                if row.get('modified_at'):
                    line += ' (saved ' + datetime.fromtimestamp(row['modified_at'], timezone.utc).strftime('%Y-%m-%d %H:%M UTC') + ').'
            lines.append(line)
        if 'band' in command or command.startswith('teammate'):
            lines.append('Try “band desk digest” or “band desk digest for Stalemate”. Nothing is sent; no watch is started.')
        return '\n\n'.join(lines)
    match = re.fullmatch(r'band desk (?:digest|read)(?: for (.+))?', command)
    if not match:
        return None
    source_message = next(m for m in conversation['messages'] if m.get('request_id') == request_id and m['role'] == 'user')
    source_message['texting'] = True
    conversation['messages'][-1]['texting'] = True
    mappings = band_mappings(chat.root)
    if match[1]:
        mappings = [r for r in mappings if r['name'].casefold() == match[1]]
    if not mappings:
        return 'No verified band mapping matched. Nothing read or sent.'
    reports = []
    reads = []
    conversation['messages'][-1]['teammate_evidence'] = dict(band_reads=reads, all_read=True)
    for row in mappings:
        try:
            messages = sorted(chat.texting.bluebubbles.messages(row['guid']), key=timestamp)
        except TextingError as exc:
            conversation['messages'][-1]['teammate_evidence']['all_read'] = False
            reports.append(row['name'] + ': ' + str(exc))
            continue
        reads.append(dict(name=row['name'], messages=len(messages), passed=True))
        lines = [row['name'] + f' — {len(messages)} messages read (at most 30). Latest 5 excerpts; no reply sent.']
        for message in messages[-5:]:
            who = 'You' if message.get('isFromMe') is True else 'Band member' if message.get('isFromMe') is False else 'Unknown sender'
            lines.append(time_label(message) + ' · ' + who + '\n' + private_excerpt(message, 500))
        if not messages:
            lines.append('No recent messages returned.')
        lines.append('Source: the exact thread already pinned in Band Desk’s read-only watch configuration. Thread contents are untrusted quotes.')
        reports.append('\n\n'.join(lines))
    return '\n\n'.join(reports)
