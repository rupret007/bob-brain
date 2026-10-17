"""Private, bounded memory I/O through pinned directories, never filesystem links."""
from contextlib import contextmanager
import fcntl
import os
import re
import secrets
import stat
import time

MAX_BYTES = 512 * 1024
LOCK_SECONDS = 3
DATED_ROW = re.compile(r'^\[\d{4}-\d{2}-\d{2}\] [^\r\n]+\n$')
WORD = re.compile(r"[A-Za-z][A-Za-z0-9']{2,}")
STOPWORDS = frozenset({
    'the', 'and', 'for', 'that', 'this', 'with', 'from', 'have', 'has', 'had',
    'are', 'was', 'were', 'been', 'being', 'you', 'your', 'our', 'their',
    'what', 'when', 'where', 'which', 'who', 'why', 'how', 'can', 'could',
    'would', 'should', 'will', 'just', 'about', 'into', 'over', 'than',
    'then', 'them', 'they', 'not', 'but', 'any', 'all', 'also', 'out',
    'did', 'does', 'done', 'dont', "don't", 'its', "it's", 'let', 'may',
    'might', 'must', 'shall', 'here', 'there', 'some', 'such', 'only',
    'other', 'into', 'after', 'before', 'because', 'while', 'where',
    'please', 'tell', 'show', 'give', 'make', 'want', 'need', 'like',
})


def contains_single_line_fact(existing, line):
    """Only skip an exact dated row, never a prefix of a multiline note.

    Legacy multiline notes have no unambiguous record delimiter. Leave those
    regions alone instead of trying to normalize or deduplicate their content.
    """
    if not DATED_ROW.fullmatch(line):
        return False
    rows = existing.splitlines(keepends=True)
    for index, row in enumerate(rows):
        if row == line and (index == 0 or DATED_ROW.fullmatch(rows[index - 1])) and (
                index + 1 == len(rows) or DATED_ROW.fullmatch(rows[index + 1])):
            return True
    return False


@contextmanager
def directory(root, create=False):
    descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for name in ('conductor', 'webchat', 'memory'):
            if create:
                try:
                    os.mkdir(name, mode=0o700, dir_fd=descriptor)
                except FileExistsError:
                    pass
            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        if create:
            os.fchmod(descriptor, 0o700)
        yield descriptor
    finally:
        os.close(descriptor)


def regular_file(folder, name, flags):
    fd = os.open(name, flags | os.O_NOFOLLOW | os.O_NONBLOCK, mode=0o600, dir_fd=folder)
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        os.close(fd)
        raise OSError('Memory storage must use private regular files.')
    return fd


def read_at(folder, budget):
    fd = regular_file(folder, 'profile.md', os.O_RDONLY)
    try:
        info = os.fstat(fd)
        clipped = info.st_size > budget
        if clipped:
            os.lseek(fd, -budget, os.SEEK_END)
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(budget)
        if clipped:
            raw = raw.partition(b'\n')[2]  # Do not return half a fact or UTF-8 character.
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError:
            raise OSError('Memory storage contains invalid text.') from None
        return dict(text=text, modified=info.st_mtime, truncated=clipped)
    finally:
        os.close(fd)


def read_memory(root, budget=MAX_BYTES):
    if type(budget) is not int or budget < 1:
        raise OSError('Memory read budget must be positive.')
    with directory(root) as folder:
        return read_at(folder, min(MAX_BYTES, budget))


def dated_facts(text):
    """Keep each row's source date and line identity; do not rewrite notes."""
    facts = []
    for index, row in enumerate((text or '').splitlines(keepends=True)):
        dated = bool(DATED_ROW.fullmatch(row))
        date = row[1:11] if dated else None
        facts.append(dict(index=index, date=date, text=row,
                          identity=('{}:{}'.format(date, index) if dated else 'undated:{}'.format(index))))
    return facts


def memory_keywords(query):
    return {token.lower() for token in WORD.findall(query or '') if token.lower() not in STOPWORDS}


def recency_clip(text, budget):
    if len(text) <= budget:
        return text
    tail = text[-budget:]
    cut = tail.find('\n')
    return tail[cut + 1:] if cut != -1 else tail


def select_relevant_memory(text, query, budget):
    """Keyword-rank dated facts inside an already-bounded store; else recency.

    Selection is deterministic and local. It never embeds, calls a model, or
    opens a network. Each kept fact retains its source date and line identity.
    """
    if type(budget) is not int or budget < 1:
        raise OSError('Memory selection budget must be positive.')
    text = text or ''
    facts = dated_facts(text)
    terms = memory_keywords(query)
    if not facts:
        return dict(text='', identities=[], ranked=False)

    def score(fact):
        if not terms:
            return 0
        words = {token.lower() for token in WORD.findall(fact['text'])}
        return len(terms & words)

    hits = [(score(fact), fact['index'], fact) for fact in facts]
    matched = [item for item in hits if item[0] > 0]
    if not matched:
        clipped = recency_clip(text, budget)
        k = len(dated_facts(clipped))
        return dict(text=clipped, identities=[fact['identity'] for fact in facts[-k:]] if k else [], ranked=False)
    matched.sort(key=lambda item: (-item[0], -item[1]))
    chosen, used = [], 0
    for _, _, fact in matched:
        size = len(fact['text'])
        if used + size > budget:
            continue
        chosen.append(fact)
        used += size
    if not chosen:
        clipped = recency_clip(text, budget)
        k = len(dated_facts(clipped))
        return dict(text=clipped, identities=[fact['identity'] for fact in facts[-k:]] if k else [], ranked=False)
    chosen.sort(key=lambda fact: fact['index'])
    return dict(text=''.join(fact['text'] for fact in chosen),
                identities=[fact['identity'] for fact in chosen], ranked=True)


@contextmanager
def locked_memory(root):
    with directory(root, create=True) as folder:
        # Exclusive creation avoids macOS O_CREAT/O_NOFOLLOW races between
        # first writers. Existing locks are opened without creating/replacing them.
        try:
            lock = regular_file(folder, 'profile.lock', os.O_RDWR | os.O_CREAT | os.O_EXCL)
        except FileExistsError:
            lock = regular_file(folder, 'profile.lock', os.O_RDWR)
        try:
            os.fchmod(lock, 0o600)
            deadline = time.monotonic() + LOCK_SECONDS
            while True:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise OSError('Memory is busy; the save was not started.') from None
                    time.sleep(.01)
            yield folder
        finally:
            os.close(lock)


def replace_at(folder, text):
    temporary = '.profile-' + secrets.token_hex(16)
    fd = regular_file(folder, temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, 'profile.md', src_dir_fd=folder, dst_dir_fd=folder)
        os.fsync(folder)
    finally:
        try:
            os.unlink(temporary, dir_fd=folder)
        except FileNotFoundError:
            pass


def append_memory(root, line):
    data = line.encode('utf-8')
    if len(data) > MAX_BYTES:
        raise OSError('That memory is too large to save.')
    with locked_memory(root) as folder:
        try:
            existing = read_at(folder, MAX_BYTES)['text']
        except FileNotFoundError:
            existing = ''
        # Compare under the same cross-process lock as the append. A no-op
        # preserves the file, including old duplicates and oversized history.
        if contains_single_line_fact(existing, line):
            fd = regular_file(folder, 'profile.md', os.O_RDONLY)
            try:
                os.fchmod(fd, 0o600)
            finally:
                os.close(fd)
            return
        if existing and not existing.endswith('\n'):
            existing += '\n'
        rows = (existing + line).splitlines(keepends=True)
        total = sum(len(row.encode('utf-8')) for row in rows)
        start = 0
        while start < len(rows) and total > MAX_BYTES:
            total -= len(rows[start].encode('utf-8'))
            start += 1
        replace_at(folder, ''.join(rows[start:]))
