#!/usr/bin/env python3
"""Trusted host handoff CLI for both chat runners; no sends or execution tools."""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time

from shared_chat import SharedChatContext, SharedChatError, MAX_SOURCE, SOURCES, _directory, _file, safe_text

# Fixed read-only remote program, never interpolated with chat/model input.
NUCBOX_READ = r'''
import json, os, stat
from pathlib import Path
root = Path.home() / '.local/share/storypool'
rows = []
for name in ('MONITOR.md', 'NEEDS_JEFF.md', 'PARITY.md'):
    row = {'name': name, 'state': 'unavailable'}
    try:
        path = root / name
        if path.resolve() != path:
            raise OSError('symlink refused')
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > 65536:
                raise OSError('not a bounded file')
            raw = stream.read(65537)
        if len(raw) > 65536:
            raise ValueError('too large')
        row.update(state='observed', text=raw.decode('utf-8'), modified=info.st_mtime)
    except (OSError, ValueError, UnicodeError):
        pass
    rows.append(row)
print(json.dumps(rows))
'''


def pull_nucbox():
    # Known-host verification is mandatory. Missing login is an explicit setup
    # blocker, never an invitation to read auth files or change SSH settings.
    result = subprocess.run(['ssh', '-F', '/dev/null', '-oBatchMode=yes', '-oConnectTimeout=5',
        '-oStrictHostKeyChecking=yes', 'rupret@100.93.165.1', 'python3 -'],
        input=NUCBOX_READ.encode(), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=10)
    if result.returncode or len(result.stdout) > 4 * MAX_SOURCE:
        raise SharedChatError('NucBox source read unavailable; check trusted host access')
    return json.loads(result.stdout)


def sync_sources(folder, rows):
    """Install only fixed, validated read-only copies with source mtime intact."""
    if not isinstance(rows, list) or len(rows) > len(SOURCES):
        raise SharedChatError('Invalid source bundle')
    validated = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or row.get('name') not in SOURCES or row['name'] in seen:
            raise SharedChatError('Invalid source identity')
        seen.add(row['name'])
        if row.get('state') != 'observed':
            continue  # Leave the previous dated copy in place; it ages to stale.
        modified = row.get('modified')
        if type(modified) not in (int, float) or not 0 < modified <= time.time() + 5:
            raise SharedChatError('Invalid source timestamp')
        raw = row.get('text')
        if not isinstance(raw, str) or len(raw.encode('utf-8')) > MAX_SOURCE:
            raise SharedChatError('Source exceeds limit')
        validated.append((row['name'], safe_text(raw, MAX_SOURCE).encode('utf-8'), modified))
    receipts = []
    with _directory(folder, create=True) as directory:
        for name, raw, modified in validated:
            # Refuse planted links/hardlinks instead of replacing their name.
            try:
                fd = _file(directory, name, os.O_RDONLY)
            except FileNotFoundError:
                pass
            else:
                os.close(fd)
            temporary = '.' + name + '.' + secrets.token_hex(12)
            fd = _file(directory, temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
            try:
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.utime(temporary, (modified, modified), dir_fd=directory, follow_symlinks=False)
                os.rename(temporary, name, src_dir_fd=directory, dst_dir_fd=directory)
                os.fsync(directory)
            finally:
                try:
                    os.unlink(temporary, dir_fd=directory)
                except FileNotFoundError:
                    pass
            receipts.append({'source': name, 'copied': True})
    return receipts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('snapshot', 'append', 'sync'))
    parser.add_argument('--folder', type=Path, default=None)
    parser.add_argument('--digest', type=Path, help='Trusted Mini conductor morning digest path; read only')
    args = parser.parse_args()
    context = SharedChatContext(args.folder) if args.folder else SharedChatContext.configured()
    try:
        if args.command == 'snapshot':
            result = context.snapshot()
        elif args.command == 'append':
            raw = sys.stdin.buffer.read(16001)
            if len(raw) > 16000:
                raise SharedChatError('Handoff input exceeds limit')
            result = {'appended': context.append(**json.loads(raw))}
        else:
            rows = pull_nucbox()
            if args.digest:
                # The operator names this file, never a chat message. The final
                # path and its parents must be link-free; a missing digest is a
                # visible failure, not a claim of having synced it.
                from shared_chat import _read
                with _directory(args.digest.parent) as folder:
                    text, info, _ = _read(folder, args.digest.name, MAX_SOURCE)
                rows.append({'name': 'MORNING_DIGEST.md', 'state': 'observed',
                             'text': text, 'modified': info.st_mtime})
            result = {'sources': sync_sources(context.folder, rows)}
        print(json.dumps(result, ensure_ascii=True))
    except (OSError, ValueError, TypeError, subprocess.SubprocessError):
        # Exception messages and source bodies may be untrusted or sensitive.
        print('Shared context operation unavailable; no success claimed.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
