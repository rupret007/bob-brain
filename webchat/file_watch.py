"""Explicit one-file chat notices. No OS watcher, no file-body summary, no follow-on action."""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import time
import uuid

import chat_intent
from failover import atomic_text
from local_tasks import LocalTaskError

CHECK_INTERVAL = 60
MAX_WATCHES = 20
PREFIX = r'^(?:(?:please\s+)|(?:(?:can|could|would) you\s+))*'
REGISTER = re.compile(
    PREFIX +
    r'(?:watch\s+(?:the\s+)?(?:local\s+)?file\s+|'
    r'notify\s+this\s+chat\s+when\s+(?:(?:the\s+)?(?:local\s+)?file\s+)?)'
    r'(?P<path>.+?)(?:\s+changes)?[.?!]?$',
    re.I)
LIST = re.compile(PREFIX + r'(?:list|show|my)\s+file\s+watches[.?!]?$', re.I)
CANCEL = re.compile(PREFIX + r'cancel\s+file\s+watch\s+(?P<id>[0-9a-f]{16})[.?!]?$', re.I)
HELP = ('File watches: “watch file ~/Documents/notes.txt”, “notify this chat when ~/Documents/notes.txt changes”, '
        '“list file watches”, or “cancel file watch ID”. One allowlisted local file per watch. '
        'Web Bob records a baseline fingerprint and later posts at most one chat notice per change. '
        'No file content is read into chat, executed, or summarized. No job or hold is changed.')
CHANGED = 'Watched file changed: {path}. No file content was read or executed.'
MISSING = 'Watched file is no longer available: {path}. No file content was read or executed.'
UNAVAILABLE = 'The file is unavailable or outside the allowlist. No watch was saved.'
NEED_FILE = 'Name one visible file under your home. No watch was saved.'


class FileWatchError(ValueError):
    pass


def parse(text):
    text = text.strip()
    if text.lower() == 'file watch help':
        return dict(action='help')
    match = CANCEL.fullmatch(text)
    if match:
        return dict(action='cancel', identifier=match['id'])
    if LIST.fullmatch(text):
        return dict(action='list')
    match = REGISTER.fullmatch(text)
    if match:
        path = match['path'].strip()
        if re.search(r'[;&|`$<>\n]|\s--\S|\$\(', path):
            return dict(action='error', error=NEED_FILE)
        if not path or path.lower() == 'changes':
            return dict(action='error', error=NEED_FILE)
        return dict(action='register', path=path)
    return None


def notice_id(watch_id, event, digest):
    return uuid.uuid5(uuid.NAMESPACE_URL, 'file-watch-notice:' + watch_id + ':' + event + ':' + digest).hex


class FileWatch:
    def __init__(self, folder, files, clock=time.time):
        self.folder = Path(folder) / 'file-watch'
        self.files = files
        self.clock = clock

    def observe(self, path):
        if hasattr(self.files, 'observe'):
            return self.files.observe(path)
        prepared = self.files.prepare(dict(kind='read', path=path))
        return prepared.get('snapshot')

    @contextmanager
    def locked(self):
        if self.folder.is_symlink():
            raise FileWatchError('File-watch storage needs repair.')
        self.folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.folder.chmod(0o700)
        path, lock_path = self.folder / 'watches.json', self.folder / 'watches.lock'
        if path.is_symlink() or lock_path.is_symlink():
            raise FileWatchError('File-watch storage needs repair.')
        fd = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        with os.fdopen(fd, 'a') as lock:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise FileWatchError('File-watch storage needs repair.')
            os.fchmod(fd, 0o600)
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                if path.exists() and (not path.is_file() or path.stat().st_size > 2 * 1024 * 1024):
                    raise FileWatchError('File-watch storage is full or needs repair.')
                state = json.loads(path.read_text()) if path.exists() else dict(last_scan_at=0, watches={})
                if not isinstance(state, dict) or not isinstance(state.get('watches'), dict):
                    raise FileWatchError('File-watch storage needs repair.')
                yield state
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def save(self, state):
        atomic_text(self.folder / 'watches.json', json.dumps(state, ensure_ascii=False))
        (self.folder / 'watches.json').chmod(0o600)

    def handle(self, text, cid, request_id, intent_state):
        spec = parse(text)
        if spec is None:
            return None
        try:
            scopes = chat_intent.blocked_scopes(intent_state, chat_intent.projects(text))
            if scopes:
                return chat_intent.hold_reply(scopes)
            if spec['action'] == 'help':
                return HELP
            if spec['action'] == 'error':
                return spec['error']
            if spec['action'] == 'list':
                return self.listing(cid)
            if spec['action'] == 'cancel':
                return self.cancel(cid, spec['identifier'])
            return self.register(cid, request_id, spec['path'])
        except FileWatchError as exc:
            return str(exc)
        except LocalTaskError as exc:
            return str(exc)
        except (OSError, ValueError, TypeError, KeyError):
            return 'File watch request could not finish. No successful change was verified.'

    def listing(self, cid):
        with self.locked() as state:
            rows = [w for w in state['watches'].values()
                    if w['conversation_id'] == cid and w['state'] == 'active']
        if not rows:
            return 'No active file watches in this conversation. ' + HELP
        return 'File watches:\n' + '\n'.join(
            f"• {row['path']} · ID {row['id']}" for row in sorted(rows, key=lambda r: r['created_at']))

    def cancel(self, cid, identifier):
        with self.locked() as state:
            row = state['watches'].get(identifier)
            if not row or row['conversation_id'] != cid:
                return 'No file watch with that ID was found in this conversation. Nothing cancelled.'
            if row['state'] != 'active':
                return 'That file watch is already cancelled. Nothing else changed.'
            row['state'] = 'cancelled'
            row['pending_notice'] = None
            self.save(state)
        return f"File watch cancelled: {row['path']}. ID {identifier}."

    def register(self, cid, request_id, path):
        try:
            snapshot = self.observe(path)
        except FileNotFoundError:
            return UNAVAILABLE
        except OSError:
            return UNAVAILABLE
        except LocalTaskError as exc:
            return str(exc)
        if not isinstance(snapshot, dict) or not snapshot.get('digest'):
            return UNAVAILABLE
        identifier = uuid.uuid5(uuid.NAMESPACE_URL, 'webbob-file-watch:' + cid + ':' + request_id).hex[:16]
        with self.locked() as state:
            existing = state['watches'].get(identifier)
            if existing:
                return (f"File watch already registered: {existing['path']}. ID {existing['id']}. "
                        'Baseline fingerprint recorded; no notice was posted.')
            if sum(1 for w in state['watches'].values() if w['state'] == 'active') >= MAX_WATCHES:
                return 'The file-watch limit is reached. Cancel a watch before adding another. Nothing saved.'
            now = self.clock()
            row = dict(id=identifier, conversation_id=cid, request_id=request_id, path=path,
                       last_observed=snapshot, last_notified=None, pending_notice=None,
                       state='active', created_at=now)
            state['watches'][identifier] = row
            state['last_scan_at'] = now
            self.save(state)
        return (f'File watch registered: {path}. ID {identifier}. '
                'Baseline fingerprint recorded; no notice was posted. '
                'Later changes post at most one chat notice each; file content is not read or executed.')

    def poll(self, deliver, intent_state_for=None):
        """Observe at most once per minute. Deliver pending notices without executing content."""
        with self.locked() as state:
            now = self.clock()
            scanned = now - float(state.get('last_scan_at') or 0) >= CHECK_INTERVAL
            if scanned:
                state['last_scan_at'] = now
                for row in state['watches'].values():
                    if row['state'] == 'active':
                        self._refresh(row)
            delivered = False
            for row in state['watches'].values():
                pending = row.get('pending_notice')
                if row['state'] != 'active' or not pending:
                    continue
                if intent_state_for:
                    scopes = chat_intent.blocked_scopes(intent_state_for(row['conversation_id']), [])
                    if scopes:
                        continue
                if not deliver(row, pending['id'], pending['content']):
                    continue
                row['last_notified'] = pending['digest']
                row['pending_notice'] = None
                delivered = True
            if scanned or delivered:
                self.save(state)

    def _refresh(self, row):
        try:
            snapshot = self.observe(row['path'])
            event, digest = 'changed', snapshot['digest']
        except FileNotFoundError:
            snapshot, event, digest = None, 'missing', 'missing'
        except LocalTaskError:
            snapshot, event, digest = None, 'missing', 'unavailable'
        except (OSError, TypeError, KeyError, ValueError):
            return
        previous = row.get('last_observed') or {}
        if snapshot == previous:
            return
        if snapshot is not None:
            row['last_observed'] = snapshot
        else:
            row['last_observed'] = dict(digest=digest, missing=True)
        if row.get('last_notified') == digest:
            return
        template = MISSING if event == 'missing' else CHANGED
        row['pending_notice'] = dict(
            id=notice_id(row['id'], event, digest),
            digest=digest,
            content=template.format(path=row['path']))
