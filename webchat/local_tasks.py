"""Bounded personal actions. No shell, model, coding queue, or outbound sends.

Only visible paths below the owner's home are allowed. Files are opened through
directory descriptors with O_NOFOLLOW; private/configuration trees are excluded.
Destructive consent and execution claims are durable before effects begin.
"""
from contextlib import contextmanager
import csv
from datetime import datetime
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import uuid
from zoneinfo import ZoneInfo

import chat_intent
from approval_language import approval_requested
from failover import atomic_text

LIMIT = 64 * 1024
HEAD_LINES = 20
HEAD_BYTES = 8192
OPERATION_TIMEOUT = 5
LOCK_TIMEOUT = 1
TIMED_OUT = 'Local action timed out; no successful result was verified. ' + (
    'Any consumed confirmation will not be replayed. Inspect the file before making a new request.')
HELP = ('Local tasks: read file ~/Documents/notes.txt; list files ~/Documents; '
        'create file ~/Documents/note.txt: hello; write file ~/Documents/note.txt: replacement; '
        'delete file ~/Documents/note.txt. Overwrites and deletes need an exact yes wblocal-… reply. '
        'Terminal: run terminal: pwd, date, ls PATH, cat PATH, head PATH, wc PATH, or df PATH (no shell). '
        'Web: search the web for QUERY, or look up QUERY. '
        'Only visible paths under your home are allowed; credential files, private/configuration trees, symlinks, '
        'hard links and special files are excluded.')
UNCERTAIN = ('Local action outcome is unconfirmed. It will not be replayed automatically; '
             'inspect the file before making a new request.')
PREFIX = r'(?:(?:please\s+)|(?:(?:can|could|would) you\s+))*'
FILE = re.compile(r'^' + PREFIX + r'(read|create|write|delete)\s+(?:a\s+)?(?:local\s+)?file\b\s*([\s\S]*)$', re.I)
LIST = re.compile(r'^' + PREFIX + r'list\s+files(?:\s+in)?(?:\s+([\s\S]*))?$', re.I)
TERMINAL = re.compile(r'^' + PREFIX + r'(?:run\s+(?:in\s+)?(?:the\s+)?terminal|terminal)\s*:\s*([\s\S]*)$', re.I)
SEARCH = re.compile(r'^' + PREFIX + r'(?:search\s+(?:the\s+)?web(?:\s+for)?|look\s+up)\b\s*([\s\S]*)$', re.I)
CONTROL = re.compile(r'^(yes|cancel)\s+(wblocal-[0-9a-f]{32})$', re.I)
SECRET_PATH = re.compile(
    r'(?:^|[._ -])(?:credentials?|secrets?|passwords?|tokens?|private[ _-]?keys?|'
    r'id_(?:rsa|dsa|ecdsa|ed25519)|env)(?:$|[._ -])|\.(?:pem|key|p12|pfx|keystore)$', re.I)
SECRET_FIELD = (r'(?:[a-z0-9]+[_-])*(?:(?:client[_ -]?)?secret|[a-z0-9]*password|passwd|pwd|'
                r'(?:(?:refresh|access|auth)[_ -]?)?token|'
                r'api[_ -]?key|private[_ -]?key|access[_ -]?key)(?:[_-][a-z0-9]+)*')
SECRET_ASSIGNMENT = re.compile(
    r'(?<![\w])' + SECRET_FIELD + r'[\"\']?\s*[:=]|'
    r'^[ \t]*' + SECRET_FIELD + r'[ \t]+\S', re.I | re.M)
SECRET_KEY = re.compile(SECRET_FIELD, re.I)
SECRET_LABEL = re.compile(
    r'(?<![a-z0-9])(?:passwords?|passwd|pwd|passphrases?|secrets?|client[_ -]?secret|'
    r'tokens?|bearer|api[_ -]?key|access[_ -]?key|private[_ -]?key|credentials?|auth)(?![a-z0-9])', re.I)
SECRET_REFUSAL = (
    "I didn't show this file because it looks like it may contain a password, key or token. "
    "My check is a pattern match, not a guarantee either way, so I'm not displaying it. "
    'Secret files or credential content are outside the local file allowlist. No file content returned.')


def safe_read(data):
    """Refuse the whole read before file content can reach a reply or receipt.

    Conservative credential markers supplement path protection; arbitrary
    unlabelled secrets cannot be inferred from otherwise ordinary prose.
    """
    from providers import KEY
    text = data.decode('utf-8')
    # Labels count in any syntax, including prose and XML attribute values.
    # Refuse before parsing, previewing, or persisting any of the file content.
    if SECRET_LABEL.search(text):
        raise LocalTaskError(SECRET_REFUSAL)

    def credential_fields(value):
        if isinstance(value, dict):
            return any(SECRET_KEY.fullmatch(key) or credential_fields(item)
                       for key, item in value.items())
        return isinstance(value, list) and any(credential_fields(item) for item in value)

    try:
        structured = json.loads(text)
    except ValueError:
        structured = None
    # CSV/TSV exports and XML tags label credentials without JSON's colon.
    # Inspect every record so leading comments/metadata cannot hide a header.
    delimited_secret = False
    for delimiter in (',', ';', '\t', '|'):
        try:
            delimited_secret |= any(len(row) > 1 and any(SECRET_KEY.fullmatch(cell.strip()) for cell in row)
                                    for row in csv.reader(io.StringIO(text), delimiter=delimiter))
        except csv.Error:
            raise LocalTaskError(SECRET_REFUSAL) from None
    xml_secret = re.search(r'<\s*(?:[\w.-]+:)?' + SECRET_FIELD + r'(?=[\s/>])|'
                           r'<\s*key\s*>\s*' + SECRET_FIELD + r'\s*</\s*key\s*>|'
                           r'<\s*[\w.:-]+\b[^<>]*\skey\s*=\s*(["\'])\s*' + SECRET_FIELD + r'\s*\1', text, re.I)
    # netrc records use whitespace, including newlines, instead of assignment
    # punctuation. Reject machine/default credential records as a whole.
    netrc_secret = re.search(r'(?<!\S)(?:machine\s+\S+|default)\s+'
                             r'(?:login|password|account)\s+\S+', text, re.I)
    if (delimited_secret or xml_secret or netrc_secret or credential_fields(structured) or SECRET_ASSIGNMENT.search(text) or KEY.search(text)
            or re.search(r'-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY(?: BLOCK)?-----', text)
            or re.search(r'\b(?:Authorization\s*:\s*)?(?:Bearer|Basic)\s+[A-Za-z0-9+/_.=-]+', text, re.I)
            or re.search(r'\b[a-z][a-z0-9+.-]*://[^\s/:]+:[^\s/@]+@', text, re.I)):
        raise LocalTaskError(SECRET_REFUSAL)
    return text


class LocalTaskError(ValueError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise LocalTaskError('Web lookup redirect refused; no result was verified.')


def search_web(query, opener=None):
    """One fixed GET endpoint; no cookies, credentials, proxies or redirects."""
    url = 'https://api.duckduckgo.com/?' + urllib.parse.urlencode(
        dict(q=query, format='json', no_redirect=1, no_html=1, skip_disambig=1))
    transport = opener or urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect()).open
    request = urllib.request.Request(url, headers={'User-Agent': 'WebBob/1.0 local lookup'})
    with transport(request, timeout=10) as response:
        raw = response.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise LocalTaskError('Web lookup response exceeded the size limit; no result was verified.')
    payload = json.loads(raw.decode('utf-8'))
    if not isinstance(payload, dict):
        raise LocalTaskError('Web lookup returned invalid data; no result was verified.')
    answer, source = payload.get('AbstractText', ''), payload.get('AbstractURL', '')
    if not answer:
        topics = payload.get('RelatedTopics', [])
        if not isinstance(topics, list):
            raise LocalTaskError('Web lookup returned invalid data; no result was verified.')
        for topic in topics:
            if isinstance(topic, dict) and topic.get('Text'):
                answer, source = topic['Text'], topic.get('FirstURL', '')
                break
    if not isinstance(answer, str) or not isinstance(source, str):
        raise LocalTaskError('Web lookup returned invalid data; no result was verified.')
    if not answer.strip():
        return 'DuckDuckGo returned no instant answer. Try a more specific query.'
    result = 'DuckDuckGo instant answer (source pages were not opened):\n' + answer[:16000]
    parsed = urllib.parse.urlsplit(source)
    if parsed.scheme in ('http', 'https') and parsed.netloc:
        result += '\nSource: ' + source[:2000]
    return result


def parse(text):
    """Recognized but invalid commands stay in this lane, never a coding job."""
    text = text.strip()
    match = SEARCH.fullmatch(text)
    if match:
        query = match[1].strip()
        if not 1 <= len(query) <= 600:
            raise LocalTaskError('Use a web query between 1 and 600 characters.')
        return dict(kind='search', query=query)
    match = TERMINAL.fullmatch(text)
    if match:
        try:
            args = shlex.split(match[1])
        except ValueError:
            raise LocalTaskError(HELP) from None
        if args == ['pwd'] or args == ['date']:
            return dict(kind=args[0])
        if len(args) == 2 and args[0] in ('cat', 'ls', 'head', 'wc', 'df'):
            kinds = {'cat': 'read', 'ls': 'list', 'head': 'head', 'wc': 'wc', 'df': 'df'}
            return dict(kind=kinds[args[0]], path=args[1])
        raise LocalTaskError('That terminal command is outside the allowlist. ' + HELP)
    match = LIST.fullmatch(text)
    if match:
        return dict(kind='list', path=(match[1] or '~').strip())
    match = FILE.fullmatch(text)
    if match:
        kind, value = match[1].lower(), match[2].strip()
        if kind in ('create', 'write'):
            if re.search(r"\b(?:do\s+not|don't|don’t|never)\s+(?:actually\s+)?(?:create|write|save|execute)\b|"
                         r'\b(?:get|after)\s+my\s+approval\b|'
                         r'\bif\s+I\s+confirm\b|\bask\s+me\s+before\b', text, re.I):
                raise LocalTaskError('No file changed. Send a new file request when you want it performed.')
            path, separator, content = value.partition(': ')
            if not separator or not content or len(content.encode('utf-8')) > LIMIT:
                raise LocalTaskError('Use create/write file PATH: CONTENT (up to 64 KiB).')
            return dict(kind=kind, path=path.strip(), content=content)
        if not value:
            raise LocalTaskError(HELP)
        return dict(kind=kind, path=value)
    return None


class LocalFiles:
    """OS boundary. Test with a temporary home, never the real owner's files."""
    def __init__(self, home=None, clock=time.time, excluded=(), protected=None):
        self.home = (Path.home() if home is None else Path(home)).resolve()
        self.clock = clock
        self.excluded = tuple(Path(p).resolve() for p in excluded)
        self.protected = protected

    def parts(self, value):
        value = value.strip()
        if value.startswith(('"', "'")):
            args = shlex.split(value)
            if len(args) != 1:
                raise LocalTaskError('Use one file path.')
            value = args[0]
        path = self.home / value[2:] if value.startswith('~/') else self.home if value == '~' else Path(value)
        try:
            parts = path.relative_to(self.home).parts
        except ValueError:
            raise LocalTaskError('Path must be inside your home directory.') from None
        if any(p.startswith('.') or p.casefold() in ('library', 'applications') or '\x00' in p for p in parts):
            raise LocalTaskError('Private/configuration paths and traversal are outside the allowlist.')
        # macOS commonly uses a case-insensitive filesystem. A spelling change
        # must not allow editing the server's saved holds or consent receipts.
        folded = tuple(p.casefold() for p in path.parts)
        excluded_paths = self.excluded + (tuple(self.protected()) if self.protected else ())
        if any(folded[:len(excluded.parts)] == tuple(p.casefold() for p in excluded.parts)
               for excluded in excluded_paths):
            raise LocalTaskError('Web Bob storage is outside the local file allowlist.')
        if any(SECRET_PATH.search(part) for part in parts):
            raise LocalTaskError(SECRET_REFUSAL)
        return parts

    @contextmanager
    def directory(self, parts):
        fd = os.open(self.home, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            for part in parts:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = child
            yield fd
        finally:
            os.close(fd)

    @contextmanager
    def file(self, parent, name, flags=os.O_RDONLY):
        fd = os.open(name, flags | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > LIMIT:
                raise LocalTaskError('Only regular, single-link files up to 64 KiB are allowed.')
            yield fd
        finally:
            os.close(fd)

    def inspect_read(self, parent, name, cap):
        """Read at most cap bytes from a regular single-link file. Never follows links."""
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise LocalTaskError('Only regular, single-link files are allowed.')
            data = os.read(fd, cap + 1)
        except TimeoutError:
            raise LocalTaskError(TIMED_OUT) from None
        finally:
            os.close(fd)
        return data[:cap], info.st_size, len(data) > cap

    @staticmethod
    def snapshot(fd):
        info = os.fstat(fd)
        os.lseek(fd, 0, os.SEEK_SET)
        data = os.read(fd, LIMIT + 1)
        if len(data) > LIMIT:
            raise LocalTaskError('File exceeded the 64 KiB limit.')
        return dict(device=info.st_dev, inode=info.st_ino, modified=info.st_mtime_ns,
                    size=info.st_size, digest=hashlib.sha256(data).hexdigest()), data

    def prepare(self, spec):
        if spec['kind'] in ('create', 'write'):
            safe_read(spec['content'].encode('utf-8'))
        if 'path' not in spec:
            return dict(spec)
        parts = self.parts(spec['path'])
        prepared = dict(spec, path=str(self.home.joinpath(*parts)))
        if spec['kind'] == 'list':
            with self.directory(parts):
                return prepared
        if spec['kind'] == 'df':
            try:
                with self.directory(parts):
                    return prepared
            except (OSError, LocalTaskError):
                if not parts:
                    raise LocalTaskError('Choose a path inside your home directory.') from None
                with self.directory(parts[:-1]):
                    return prepared
        if not parts:
            raise LocalTaskError('Choose a file below your home directory.')
        if spec['kind'] in ('head', 'wc'):
            with self.directory(parts[:-1]) as parent:
                try:
                    self.inspect_read(parent, parts[-1], 1)
                except TimeoutError:
                    raise LocalTaskError(TIMED_OUT) from None
            return prepared
        with self.directory(parts[:-1]) as parent:
            try:
                with self.file(parent, parts[-1]) as fd:
                    snapshot, data = self.snapshot(fd)
                    if spec['kind'] in ('write', 'delete'):
                        safe_read(data)
            except FileNotFoundError:
                if spec['kind'] not in ('create', 'write'):
                    raise
                return dict(prepared, kind='create')
            if spec['kind'] == 'create':
                raise LocalTaskError('File already exists. Use write file to draft an overwrite.')
            return dict(prepared, snapshot=snapshot)

    def execute(self, spec):
        kind = spec['kind']
        if kind in ('create', 'write'):
            safe_read(spec['content'].encode('utf-8'))
        if kind == 'pwd':
            return 'Terminal pwd (local task directory): ' + str(self.home)
        if kind == 'date':
            return 'Terminal date: ' + datetime.fromtimestamp(self.clock(), ZoneInfo('America/Chicago')).isoformat()
        parts = self.parts(spec['path'])
        if kind == 'list':
            with self.directory(parts) as fd:
                entries = []
                with os.scandir(fd) as scan:
                    for entry in scan:
                        if not entry.name.startswith('.') and entry.name.casefold() not in ('library', 'applications'):
                            entries.append(entry.name)
                        if len(entries) > 200:
                            break
                suffix = '\nListing truncated to 200 entries.' if len(entries) > 200 else ''
                return 'Directory listing: ' + spec['path'] + '\n' + '\n'.join(sorted(entries[:200])) + suffix
        if kind == 'df':
            return self._disk_free(spec, parts)
        if not parts:
            raise LocalTaskError('Choose a file below your home directory.')
        with self.directory(parts[:-1]) as parent:
            if kind == 'create':
                fd = os.open(parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
                with os.fdopen(fd, 'wb') as target:
                    target.write(spec['content'].encode('utf-8'))
                    target.flush()
                    os.fsync(target.fileno())
                os.fsync(parent)
                return 'File created: ' + spec['path']
            if kind in ('head', 'wc'):
                cap = HEAD_BYTES if kind == 'head' else LIMIT
                try:
                    data, size, truncated = self.inspect_read(parent, parts[-1], cap)
                except TimeoutError:
                    raise LocalTaskError(TIMED_OUT) from None
                if data and b'\x00' not in data:
                    safe_read(data)
                return self._head_receipt(spec['path'], data, truncated) if kind == 'head' else self._wc_receipt(
                    spec['path'], data, size, truncated)
            with self.file(parent, parts[-1], os.O_RDWR if kind == 'write' else os.O_RDONLY) as fd:
                snapshot, data = self.snapshot(fd)
                if kind == 'read':
                    return 'File read: ' + spec['path'] + '\n' + safe_read(data)
                # Absolute exclusion: consent and legacy drafts cannot authorize
                # changes to a credential file, even with a matching snapshot.
                safe_read(data)
                if snapshot != spec.get('snapshot'):
                    raise LocalTaskError('File changed since the draft. Make a fresh request; nothing changed by this attempt.')
                if kind == 'write':
                    content = spec['content'].encode('utf-8')
                    os.lseek(fd, 0, os.SEEK_SET)
                    with os.fdopen(os.dup(fd), 'wb') as target:
                        target.write(content)
                        target.flush()
                    os.ftruncate(fd, len(content))
                    os.fsync(fd)
                    return 'File overwritten: ' + spec['path']
                if kind == 'delete':
                    current = os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
                    if (current.st_dev, current.st_ino, current.st_mtime_ns, current.st_size) != (
                            snapshot['device'], snapshot['inode'], snapshot['modified'], snapshot['size']):
                        raise LocalTaskError('File changed since the draft. Make a fresh request; nothing changed by this attempt.')
                    os.unlink(parts[-1], dir_fd=parent)
                    os.fsync(parent)
                    return 'File deleted: ' + spec['path']
                raise LocalTaskError('Unsupported local action.')

    def _disk_free(self, spec, parts):
        with self.directory(parts[:-1] if parts else ()) as parent:
            if parts:
                info = os.lstat(parts[-1], dir_fd=parent)
                if stat.S_ISLNK(info.st_mode) or not (stat.S_ISDIR(info.st_mode) or (
                        stat.S_ISREG(info.st_mode) and info.st_nlink == 1)):
                    raise LocalTaskError('Only regular, single-link files or directories are allowed.')
                fd = parent
                if stat.S_ISDIR(info.st_mode):
                    with self.directory(parts) as directory:
                        vfs = os.fstatvfs(directory)
                else:
                    vfs = os.fstatvfs(fd)
            else:
                vfs = os.fstatvfs(parent)
        free = vfs.f_bavail * vfs.f_frsize
        total = vfs.f_blocks * vfs.f_frsize
        return (f'Terminal disk free (local filesystem API, no shell):\n'
                f'path={spec["path"]}\nfree_bytes={free}\ntotal_bytes={total}')

    @staticmethod
    def _head_receipt(path, data, truncated):
        heading = (f'Terminal head (local file, at most {HEAD_LINES} lines / {HEAD_BYTES} bytes):\n'
                   f'path={path}')
        if not data:
            return heading + '\nempty=true\ntruncated=false'
        if b'\x00' in data:
            return heading + f'\nbinary=true\nbytes_shown={len(data)}\ntruncated={str(truncated).lower()}'
        text = data.decode('utf-8')
        lines = text.splitlines()
        shown = lines[:HEAD_LINES]
        line_trunc = len(lines) > HEAD_LINES
        body = '\n'.join(f'{index}: {line}' for index, line in enumerate(shown, 1))
        return heading + f'\n{body}\ntruncated={str(truncated or line_trunc).lower()}'

    @staticmethod
    def _wc_receipt(path, data, size, truncated):
        binary = b'\x00' in data
        if binary:
            lines = words = 0
        else:
            text = data.decode('utf-8')
            lines = text.count('\n') + (0 if not text or text.endswith('\n') else 1)
            words = len(text.split())
        return (f'Terminal wc (local file, first {LIMIT} bytes):\n'
                f'path={path}\nlines={lines}\nwords={words}\nbytes={len(data)}\n'
                f'file_size={size}\ntruncated={str(truncated).lower()}\nbinary={str(binary).lower()}')


class LocalTasks:
    def __init__(self, folder, files=None, search=None, clock=time.time, *, root=None, _worker=False):
        self.folder = Path(folder) / 'local-tasks'
        self.root = Path(root if root is not None else os.environ.get('BOB_ROOT', Path(folder).parent.parent)).resolve()
        self.files = files if files is not None else LocalFiles(
            clock=clock, excluded=(folder, Path(__file__).resolve().parent.parent),
            protected=self.protected_paths)
        self.search = search if search is not None else search_web
        self.clock = clock
        # Explicitly injected file adapters are the in-process test boundary.
        # Production file work, including receipts and routine validation, runs
        # in a fresh killable interpreter; never fork the threaded chat server.
        self.isolated_files = files is None and not _worker

    def file_worker(self, method, args, kwargs):
        payload = dict(folder=str(self.folder.parent), root=str(self.root), home=str(self.files.home),
                       now=self.clock(), method=method, args=args, kwargs=kwargs)
        process = subprocess.Popen([sys.executable, str(Path(__file__).with_name('local_task_worker.py'))],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                   text=True)
        try:
            output, _ = process.communicate(json.dumps(payload), timeout=OPERATION_TIMEOUT)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            raise LocalTaskError(TIMED_OUT) from None
        if process.returncode:
            raise LocalTaskError(UNCERTAIN)
        result = json.loads(output)
        if 'error' in result:
            raise LocalTaskError(result['error'])
        return result['result']

    def protected_paths(self):
        # Use the same policy reader as provider admission. Refresh at every
        # prepare/execute boundary, including confirmations saved before restart.
        # Protect entire operator-owned roots: policies, budgets, keys, queues,
        # executable configuration and future stores must not be chat-editable.
        from generation_budget import AdmissionDenied, read_policy
        roots = {self.root}
        for name in ('BOB_ROOT', 'BOB_GENERATION_BUDGET_ROOT'):
            if os.environ.get(name):
                roots.add(Path(os.environ[name]).resolve())
        try:
            for root in tuple(roots):
                policy = read_policy(root)
                if policy:
                    roots.add(Path(policy['accounting_root']).resolve())
        except (AdmissionDenied, OSError, ValueError, TypeError):
            raise LocalTaskError('Runtime storage protection could not be verified. No local file action ran.') from None
        # Calendar accepts an operator-configured OAuth file anywhere, including
        # visible home directories. Recheck it for saved drafts and routines too.
        credentials = os.environ.get('BOB_GOOGLE_CALENDAR_CREDENTIALS')
        if credentials:
            roots.add(Path(credentials).expanduser().resolve())
        return roots

    @contextmanager
    def locked(self):
        if self.folder.is_symlink():
            raise LocalTaskError('Local receipt storage needs repair.')
        self.folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.folder.chmod(0o700)
        path, lock_path = self.folder / 'receipts.json', self.folder / 'receipts.lock'
        if path.is_symlink() or lock_path.is_symlink():
            raise LocalTaskError('Local receipt storage needs repair.')
        fd = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        with os.fdopen(fd, 'a') as lock:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise LocalTaskError('Local receipt storage needs repair.')
            os.fchmod(fd, 0o600)
            deadline = time.monotonic() + LOCK_TIMEOUT
            while True:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise LocalTaskError('Local receipt storage is busy; no action ran. Try again later.')
                    time.sleep(0.01)
            try:
                if path.exists() and (not path.is_file() or path.stat().st_size > 4 * 1024 * 1024):
                    raise LocalTaskError('Local receipt storage is full or needs repair.')
                rows = json.loads(path.read_text()) if path.exists() else {}
                if not isinstance(rows, dict):
                    raise LocalTaskError('Local receipt storage needs repair.')
                yield rows
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def save(self, rows):
        payload = json.dumps(rows, ensure_ascii=False)
        if len(payload.encode('utf-8')) > 4 * 1024 * 1024:
            raise LocalTaskError('Local receipt storage is full. No successful result was verified.')
        atomic_text(self.folder / 'receipts.json', payload)

    def validate_routine(self, text, *, check_path=True):
        if self.isolated_files and check_path and not SEARCH.fullmatch(text.strip()):
            return self.file_worker('validate_routine', [text], {})
        spec = parse(text)
        if not spec or spec['kind'] not in ('read', 'list', 'pwd', 'date', 'search', 'head', 'wc', 'df'):
            raise LocalTaskError('Routines can only read files, list directories, run the fixed read-only terminal commands, '
                                 'or look up the web. For a personal reminder use “every morning remind me to X”. '
                                 'Writes, deletes and sends require a fresh direct request and any required confirmation.')
        if check_path:
            try:
                self.files.prepare(spec)
            except OSError:
                raise LocalTaskError('The routine path is unavailable or outside the allowlist. No routine was saved.') from None
        return text

    @staticmethod
    def receipt(row):
        if row['state'] == 'done':
            return row['receipt']
        if row['state'] in ('claimed', 'unconfirmed'):
            return UNCERTAIN
        if row['state'] != 'draft':
            return 'That local draft was cancelled, replaced, or expired. Make a fresh request.'
        spec = row['spec']
        if spec['kind'] in ('create', 'write'):
            safe_read(spec['content'].encode('utf-8'))
        preview = '\nReplacement content:\n' + spec['content'] if spec['kind'] == 'write' else ''
        if spec['kind'] == 'create':
            return ("I haven't created it yet — the request contains approval language, so I'm checking first. "
                    f'Create {spec["path"]}. Within one hour reply exactly “yes {row["token"]}” '
                    f'to create it or “cancel {row["token"]}”.')
        return (f'Local draft; no file changed: {spec["kind"]} {spec["path"]}.{preview}\n'
                f'Within one hour reply exactly “yes {row["token"]}” or “cancel {row["token"]}”.')

    def execute(self, spec):
        return self.search(spec['query']) if spec['kind'] == 'search' else self.files.execute(spec)

    def handle(self, text, cid, request_id, intent_state, *, routine=False):
        try:
            if self.isolated_files and not SEARCH.fullmatch(text.strip()) and (
                    CONTROL.fullmatch(text.strip()) or FILE.fullmatch(text.strip()) or
                    LIST.fullmatch(text.strip()) or TERMINAL.fullmatch(text.strip())):
                return self.file_worker('handle', [text, cid, request_id, intent_state], dict(routine=routine))
            control = CONTROL.fullmatch(text.strip())
            if control:
                if routine:
                    raise LocalTaskError('Routine confirmations are not permitted.')
                return self.control(control[1].lower(), control[2].lower(), cid, request_id, intent_state)
            if re.match(r'^(?:yes|cancel)\s+wblocal-', text.strip(), re.I):
                return 'Use the exact confirmation message from the local draft. No action ran.'
            if text.strip().lower() == 'local tasks help':
                return HELP
            spec = parse(text)
            if spec is None:
                return None
            scopes = chat_intent.blocked_scopes(intent_state, chat_intent.projects(text))
            if scopes:
                return chat_intent.hold_reply(scopes)
            if routine:
                self.validate_routine(text, check_path=False)
            with self.locked() as rows:
                existing = next((r for r in rows.values() if r['cid'] == cid and r['request_id'] == request_id), None)
                if existing:
                    return self.receipt(existing) if existing['text'] == text else 'Request ID already used for a different local action.'
                if len(rows) >= 1000:
                    raise LocalTaskError('Local receipt limit reached. No action ran.')
                spec = self.files.prepare(spec)
                needs_confirmation = (spec['kind'] in ('write', 'delete') or
                                      (spec['kind'] == 'create' and approval_requested(text)))
                token = 'wblocal-' + uuid.uuid4().hex
                row = dict(cid=cid, request_id=request_id, text=text, token=token, spec=spec,
                           state='draft' if needs_confirmation else 'claimed', expires=self.clock() + 3600)
                if needs_confirmation:
                    for old in rows.values():
                        if old['cid'] == cid and old['state'] == 'draft':
                            old['state'] = 'replaced'
                rows[token] = row
                self.save(rows)
                if needs_confirmation:
                    return self.receipt(row)
                return self.finish(rows, row)
        except LocalTaskError as exc:
            return str(exc)
        except (OSError, ValueError, TypeError, KeyError):
            return 'Local request could not finish. No successful result was verified. ' + UNCERTAIN

    def finish(self, rows, row):
        try:
            result = self.execute(row['spec'])
            if not isinstance(result, str) or not result:
                raise LocalTaskError('No result was returned.')
            row.update(state='done', receipt=result)
        except LocalTaskError as exc:
            row.update(state='done', receipt=str(exc))
        except Exception:
            row.update(state='unconfirmed')
        self.save(rows)
        return self.receipt(row)

    def control(self, command, token, cid, request_id, intent_state):
        with self.locked() as rows:
            row = rows.get(token)
            if not row or row['cid'] != cid:
                return 'No matching local draft in this conversation.'
            if row['state'] != 'draft':
                return self.receipt(row)
            if command == 'cancel':
                row['state'] = 'cancelled'
                self.save(rows)
                return 'Local draft cancelled. No file changed.'
            scopes = chat_intent.blocked_scopes(intent_state, chat_intent.projects(row['text']))
            if scopes:
                return chat_intent.hold_reply(scopes)
            if request_id == row['request_id']:
                return 'Confirm the local draft in a separate message.'
            if self.clock() >= row['expires']:
                row['state'] = 'expired'
                self.save(rows)
                return self.receipt(row)
            row.update(state='claimed', approved_request_id=request_id)
            self.save(rows)
            return self.finish(rows, row)
