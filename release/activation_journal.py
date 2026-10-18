"""Durable intent for cooperating controllers; no runtime admission guarantee.

Hold controller ownership for the entire operation. A pending journal survives
process death and must be recovered explicitly before another release begins.
"""
import copy
import json
import os
from pathlib import Path
import re
import stat
import uuid

from release_ownership import controller

NAME = 'webbob-activation.json'
LIMIT = 1024 * 1024
IDENTITY = ('sha', 'previous', 'rollback', 'snapshots', 'snapshot_hashes',
            'original_pins', 'recovery_reserve', 'emergency_marker', 'runner_refresh')


def private_json(path, *, directory=None):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=directory)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid()
                or info.st_mode & 0o077 or info.st_size > LIMIT):
            raise RuntimeError('Activation recovery file is unsafe or oversized')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(LIMIT + 1)
        if len(raw) > LIMIT:
            raise RuntimeError('Activation recovery file is oversized')
        after = os.fstat(fd)
        named = os.stat(path, dir_fd=directory, follow_symlinks=False)
        if ((info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
                != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
                or (after.st_dev, after.st_ino) != (named.st_dev, named.st_ino) or after.st_nlink != 1):
            raise RuntimeError('Activation recovery file changed while reading')
        return json.loads(raw)
    finally:
        os.close(fd)


def identity(record):
    return {name: record.get(name) for name in IDENTITY}


def local_path(root, value):
    path = Path(value)
    if not path.is_absolute() or not path.resolve().is_relative_to(Path(root).resolve()):
        raise RuntimeError('Activation recovery path is outside this installation')
    return path


def validate(root, value):
    if not isinstance(value, dict) or value.get('schema') != 1 or value.get('state') != 'pending':
        raise RuntimeError('Invalid activation recovery journal')
    uuid.UUID(value['id'])
    record = value['record']
    if not isinstance(record, dict) or any(not re.fullmatch(r'[0-9a-f]{40}', record.get(k, ''))
                                           for k in ('sha', 'previous')):
        raise RuntimeError('Incomplete activation recovery identity')
    local_path(root, record['rollback'])
    for key in ('snapshots', 'snapshot_hashes'):
        if set(record.get(key, {})) != {'webchat', 'dispatch'}:
            raise RuntimeError('Incomplete activation recovery snapshots')
    for path in record['snapshots'].values():
        local_path(root, path)
    for digest in record['snapshot_hashes'].values():
        if not re.fullmatch(r'[0-9a-f]{64}', digest):
            raise RuntimeError('Invalid activation recovery snapshot hash')
    for path in record.get('original_pins', {}).values():
        local_path(root, path)
    runner = record.get('runner_refresh')
    if runner is not None:
        if not isinstance(runner, dict) or type(runner.get('required')) is not bool:
            raise RuntimeError('Invalid runner refresh obligation')
        if runner['required']:
            local_path(root, runner['prior']['code_root'])
            if not re.fullmatch(r'[0-9a-f]{40}', runner['prior'].get('sha', '')):
                raise RuntimeError('Invalid prior runner source identity')
    path = local_path(root, value['path'])
    for name, suffix in (('recovery_reserve', '.recovery-reserve'), ('emergency_marker', '.emergency.md')):
        if record.get(name) and Path(record[name]) != Path(str(path) + suffix):
            raise RuntimeError('Invalid activation recovery reserve path')
    if value['final_path']:
        local_path(root, value['final_path'])


def pending(root):
    with controller(root) as owner:
        try:
            value = private_json(NAME, directory=owner.directory)
        except FileNotFoundError:
            return None
        validate(root, value)
        owner.validate()
        return value


def require_clear(root):
    if pending(root) is not None:
        raise RuntimeError('An unfinished Web Bob activation requires recover-pending before another release.')


def match(root, record, path=None):
    value = pending(root)
    if value is not None and (identity(value['record']) != identity(record)
            or path is not None and Path(path).resolve() != Path(value['path']).resolve()):
        raise RuntimeError('Recovery does not belong to the unfinished Web Bob activation')
    return value


def begin(root, record, path, final_path=None):
    with controller(root) as owner:
        require_clear(root)
        value = dict(schema=1, state='pending', id=str(uuid.uuid4()), record=copy.deepcopy(record),
                     path=str(local_path(root, path)),
                     final_path=str(local_path(root, final_path)) if final_path else None)
        validate(root, value)
        raw = json.dumps(value, separators=(',', ':')).encode()
        if len(raw) > LIMIT:
            raise RuntimeError('Activation recovery journal is oversized')
        temporary = NAME + '.' + value['id'] + '.tmp'
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                     0o600, dir_fd=owner.directory)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            owner.validate()
            os.rename(temporary, NAME, src_dir_fd=owner.directory, dst_dir_fd=owner.directory)
            os.fsync(owner.directory)
        finally:
            try:
                os.unlink(temporary, dir_fd=owner.directory)
            except FileNotFoundError:
                pass
        return value


def finish(root, value):
    with controller(root) as owner:
        current = pending(root)
        if current is None or current['id'] != value['id']:
            raise RuntimeError('Activation recovery journal identity changed')
        owner.validate()
        os.unlink(NAME, dir_fd=owner.directory)
        try:
            os.fsync(owner.directory)
        except OSError:
            # Restore the obligation if removal durability fails. The caller
            # still rolls back and must verify/publish before clearing again.
            restored = begin(root, value['record'], value['path'], value['final_path'])
            value.update(restored)
            raise


def saved_record(root, value):
    try:
        record = private_json(local_path(root, value['path']))
    except FileNotFoundError:
        record = copy.deepcopy(value['record'])
        record['recovered_from_journal'] = True
    match(root, record, value['path'])
    return record


def permit_restart(root, pins):
    value = pending(root)
    if value is None:
        return
    record = value['record']
    for name, path in pins.items():
        allowed = {Path(record['rollback']) / 'candidate', Path(record['snapshots'][name])}
        if Path(path).resolve() not in {p.resolve() for p in allowed}:
            raise RuntimeError('Restart does not belong to the unfinished Web Bob activation')
