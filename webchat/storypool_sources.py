"""Bounded local StoryPool observations; source prose never grants authority."""
import os
from pathlib import Path
import re
import stat

from shared_chat import MAX_SOURCE, SOURCES, _directory, _freshness, _stamp, safe_text


def _observe(folder, name, *, tail=False):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=folder)
    try:
        info = os.fstat(fd)
        # Operational status files can be group-readable/writable. They are
        # untrusted observations, separate from the private approval journal.
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or info.st_nlink != 1 or info.st_mode & 0o002):
            raise OSError('Unsafe operational source')
        limit = 4000 if tail else MAX_SOURCE
        clipped = info.st_size > limit
        if clipped and tail:
            os.lseek(fd, -limit, os.SEEK_END)
        raw = os.read(fd, limit)
        if clipped and tail:
            raw = raw.partition(b'\n')[2]
        text = raw.decode('utf-8')
        return safe_text(text), info, clipped or len(text) > 4000
    finally:
        os.close(fd)


def status_sources(root, now):
    """Read fixed status names and the latest dated conductor digest.

    Paths are trusted server configuration, never model/chat input. Pin
    directories and refuse source links; never include exception payloads.
    MONITOR is an append-only growing log, so expose its newest bounded tail.
    """
    rows = []
    for name in SOURCES:
        row = {'source': name, 'state': 'unavailable', 'execution_authority': False}
        try:
            with _directory(root) as folder:
                selected = name
                if name == 'MORNING_DIGEST.md':
                    with _directory(Path(root) / 'conductor') as digests:
                        names = sorted(n for n in os.listdir(digests) if re.fullmatch(
                            r'digest-\d{4}-\d{2}-\d{2}-(?:am|pm)\.md', n))
                        if not names:
                            raise FileNotFoundError('No conductor digest')
                        selected = names[-1]
                        text, info, clipped = _observe(digests, selected)
                else:
                    text, info, clipped = _observe(folder, selected, tail=name == 'MONITOR.md')
            row.update(state='observed', text=text, observed_at=_stamp(info.st_mtime),
                       freshness=_freshness(info.st_mtime, now), truncated=clipped,
                       provenance='read-only local StoryPool observation',
                       source_path=('conductor/' if name == 'MORNING_DIGEST.md' else '') + selected)
        except (OSError, ValueError, UnicodeError):
            pass
        rows.append(row)
    return rows
