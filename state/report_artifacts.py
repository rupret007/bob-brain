"""Private immutable report inputs/results; no path supplied by a model is opened."""
from contextlib import contextmanager
import hashlib
import json
import os
import re
import secrets
import stat

from report_contract import canonical, relative, MAX_INPUT_BYTES

MAX_BUNDLE_BYTES = 300000


@contextmanager
def directory(root, parts, *, create=False):
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts:
            if not relative(part) or '/' in part:
                raise ValueError('Invalid artifact directory')
            if create:
                try:
                    os.mkdir(part, 0o700, dir_fd=fd)
                except FileExistsError:
                    pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        yield fd
    finally:
        os.close(fd)


def read_at(fd, name, limit):
    child = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    with os.fdopen(child, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit:
            raise ValueError('Artifact must be a bounded private regular file')
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('Artifact exceeds the read limit')
    return raw


def read(root, path, limit=MAX_BUNDLE_BYTES):
    if not relative(path):
        raise ValueError('Invalid artifact path')
    parts = path.split('/')
    with directory(root, parts[:-1]) as fd:
        return read_at(fd, parts[-1], limit)


def put_once(root, path, raw):
    """Complete-or-absent publication; existing content must match exactly."""
    if not relative(path) or not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BUNDLE_BYTES:
        raise ValueError('Invalid bounded artifact')
    parts = path.split('/')
    with directory(root, parts[:-1], create=True) as fd:
        recover_pending_link(fd, parts[-1])
        try:
            if read_at(fd, parts[-1], MAX_BUNDLE_BYTES) != raw:
                raise ValueError('This assignment already has different saved content')
            return
        except FileNotFoundError:
            pass
        tmp = '.pending-' + secrets.token_hex(16)
        child = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
        try:
            with os.fdopen(child, 'wb') as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(tmp, parts[-1], src_dir_fd=fd, dst_dir_fd=fd, follow_symlinks=False)
            except FileExistsError:
                # A different writer must never replace an accepted result.
                if read_at(fd, parts[-1], MAX_BUNDLE_BYTES) != raw:
                    raise ValueError('Conflicting artifact publication') from None
            finally:
                try:
                    os.unlink(tmp, dir_fd=fd)
                except FileNotFoundError:
                    pass
            os.fsync(fd)
        finally:
            try:
                os.unlink(tmp, dir_fd=fd)
            except FileNotFoundError:
                pass


def recover_pending_link(fd, name):
    """Unlink only our exact same-inode temporary left by a crashed publisher.

    Never follow a link or guess among unknown hardlinks. This is called only
    by an authorized replayed write, not by ordinary source/evidence reads.
    """
    try:
        info = os.stat(name, dir_fd=fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 2 or info.st_uid != os.getuid():
        return
    names = os.listdir(fd)
    if len(names) > 4096:
        return
    matching = []
    for candidate in names:
        if not re.fullmatch(r'\.pending-[a-f0-9]{32}', candidate):
            continue
        try:
            other = os.stat(candidate, dir_fd=fd, follow_symlinks=False)
        except FileNotFoundError:
            continue
        if stat.S_ISREG(other.st_mode) and (other.st_dev, other.st_ino) == (info.st_dev, info.st_ino):
            matching.append(candidate)
    if len(matching) == 1:
        try:
            os.unlink(matching[0], dir_fd=fd)
        except FileNotFoundError:
            pass
        os.fsync(fd)


def input_path(contract):
    return 'conductor/state/project-report-inputs/' + contract['task_id'] + '.json'


def validate_inputs(contract, sources):
    if not isinstance(sources, list) or len(sources) != len(contract['input_manifest']):
        raise ValueError('Assigned evidence is missing')
    total = 0
    for expected, source in zip(contract['input_manifest'], sources):
        if not isinstance(source, dict) or set(source) != {'path', 'text'} or source['path'] != expected['path']:
            raise ValueError('Assigned evidence identity differs')
        raw = source['text'].encode('utf-8')
        total += len(raw)
        if len(raw) != expected['bytes'] or hashlib.sha256(raw).hexdigest() != expected['sha256']:
            raise ValueError('Assigned evidence version differs')
    if total > MAX_INPUT_BYTES:
        raise ValueError('Assigned evidence exceeds the context limit')
    return sources


def save_inputs(root, contract, sources):
    validate_inputs(contract, sources)
    value = dict(contract_sha256=contract['contract_sha256'], sources=sources)
    put_once(root, input_path(contract), canonical(value).encode())


def load_inputs(root, contract):
    value = json.loads(read(root, input_path(contract)))
    if value.get('contract_sha256') != contract['contract_sha256']:
        raise ValueError('Saved evidence belongs to another assignment')
    return validate_inputs(contract, value.get('sources'))
