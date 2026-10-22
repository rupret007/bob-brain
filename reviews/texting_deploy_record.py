"""Stdlib-only durable evidence primitives shared by the texting launcher/runner."""
import json
import os
import hashlib
import errno
from pathlib import Path
import shutil
import tempfile
import time

MIN_FREE_BYTES = 5 * 1024 ** 3
MAX_EVIDENCE_BYTES = 1024 ** 2
RECOVERY_BYTES = 64 * 1024 ** 2


def disk_space(root, candidate, stage):
    paths = [Path(root) / 'conductor/reviews', Path(root) / 'workspaces', Path(candidate), Path('/private/tmp')]
    if Path('/System/Volumes/Data').exists():
        paths.insert(0, Path('/System/Volumes/Data'))
    volumes = []
    for path in paths:
        while not path.exists():
            path = path.parent
        volumes.append(dict(path=str(path.resolve()), device=path.stat().st_dev,
                            free_bytes=shutil.disk_usage(path).free))
    return dict(stage=stage, at=time.time(), required_bytes=MIN_FREE_BYTES,
                minimum_free_bytes=min(v['free_bytes'] for v in volumes), volumes=volumes)


def require_disk_space(root, candidate, stage):
    receipt = disk_space(root, candidate, stage)
    if receipt['minimum_free_bytes'] < MIN_FREE_BYTES:
        raise OSError(errno.ENOSPC, '5 GiB free-space gate failed at ' + stage + ': ' +
                      str(receipt['minimum_free_bytes']) + ' bytes available')
    return receipt


def _atomic_chunks(path, chunks, *, exclusive=False, max_bytes=MAX_EVIDENCE_BYTES):
    """Stream a bounded file; /private/tmp is staging, not extra disk capacity."""
    path = Path(path)
    staging = Path('/private/tmp')
    if not staging.exists() or staging.stat().st_dev != path.parent.stat().st_dev:
        staging = path.parent  # Atomic rename must stay on the destination volume.
    fd, temporary = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=staging)
    size = 0
    try:
        with os.fdopen(fd, 'wb') as stream:
            for chunk in chunks:
                data = chunk.encode('utf-8')
                size += len(data)
                if size > max_bytes:
                    raise OSError(errno.EFBIG, 'Evidence exceeds bounded checkpoint size', str(path))
                stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if exclusive:
            os.link(temporary, path)
        else:
            os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic_text(path, text, *, exclusive=False):
    _atomic_chunks(path, (text[i:i + 65536] for i in range(0, len(text), 65536)), exclusive=exclusive)


def atomic_json(path, value, *, exclusive=False):
    _atomic_chunks(path, json.JSONEncoder(ensure_ascii=False, separators=(',', ':')).iterencode(value),
                   exclusive=exclusive)


def json_hash(value):
    digest = hashlib.sha256()
    size = 0
    for chunk in json.JSONEncoder(sort_keys=True, ensure_ascii=False, separators=(',', ':')).iterencode(value):
        raw = chunk.encode('utf-8')
        digest.update(raw)
        size += len(raw)
    return dict(sha256=digest.hexdigest(), bytes=size)


def compact_evidence(value):
    """Retain gate results and IDs; hash large observations already saved in sessions."""
    if isinstance(value, list):
        return [compact_evidence(row) for row in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, item in value.items():
        if key in ('queue_jobs', 'snapshot', 'receipts') and item and key + '_digest' not in value:
            result[key + '_digest'] = json_hash(item)
            if key == 'receipts':
                result[key] = [{k: row.get(k) for k in ('id', 'worker', 'kind', 'status',
                              'execution_started_at', 'result_path', 'result_sha256')} for row in item]
        else:
            result[key] = compact_evidence(item)
    return result


def reserve_recovery(record, evidence):
    """Allocate actual blocks before activation; a sparse truncate is insufficient."""
    reserve = Path(str(record) + '.recovery-reserve')
    emergency = Path(str(record) + '.emergency.md')
    evidence.update(recovery_reserve=str(reserve), emergency_marker=str(emergency))
    atomic_text(emergency, 'RESULT: FAIL_OR_ROLLBACK\nDeployment incomplete; recovery verification pending.\n' + ' ' * 16000)
    with reserve.open('xb') as stream:
        for _ in range(RECOVERY_BYTES // (1024 ** 2)):
            stream.write(b'\0' * (1024 ** 2))
        stream.flush()
        os.fsync(stream.fileno())
    if reserve.stat().st_blocks * 512 < RECOVERY_BYTES:
        raise OSError('Recovery reserve did not allocate physical blocks')


def release_recovery(evidence):
    path = evidence.get('recovery_reserve')
    if path:
        Path(path).unlink(missing_ok=True)


def failure_publish(record, report, evidence, text):
    """Only called AFTER recovery. Never promote a failed write to LIVE_PASS."""
    evidence.update(all_pass=False, status='FAIL_OR_ROLLBACK')
    errors = []
    try:
        atomic_json(record, compact_evidence(evidence))
    except BaseException as error:
        errors.append(str(error))
    try:
        atomic_text(report, text)
        return str(report)
    except BaseException as error:
        errors.append(str(error))
    tiny = ('RESULT: FAIL_OR_ROLLBACK\ntip: ' + str(evidence.get('sha')) +
            '\ndraft_pr: ' + str(evidence.get('draft_pr')) +
            '\nevidence: ' + str(record) + '\nrollback_path: ' + str(evidence.get('rollback')) +
            '\nrollback_verified: ' + str(evidence.get('rollback_version_verified', evidence.get('rolled_back', False))) +
            '\nlive_before: ' + json.dumps(evidence.get('before', {})) +
            '\nlive_after: ' + json.dumps(evidence.get('after', {})) +
            '\nfree_space: ' + json.dumps(evidence.get('free_space', {})) +
            '\nfailure: ' + str(evidence.get('wrapper_failure', evidence.get('failure', 'evidence I/O')))[:1000] +
            '\npublish_errors: ' + repr(errors)[:1000] + '\n')
    emergency = Path(evidence.get('emergency_marker', str(record) + '.emergency.md'))
    try:
        with emergency.open('r+b') as stream:
            stream.write(tiny.encode()[:16000])
            stream.flush()
            os.fsync(stream.fileno())
            stream.truncate()
        # Keep the reserve marker available for the recording parent's later publish.
        # The child may also need it while reporting its recovery result.
        target = Path(str(emergency) + '.publish')
        target.unlink(missing_ok=True)
        os.link(emergency, target)
        os.replace(target, report)
        return str(report)
    except BaseException:
        # An existing fail-closed marker and stdout remain if the volume rejects all writes.
        print(tiny, flush=True)
        return str(emergency)


def claim_record(path, evidence):
    atomic_json(path, evidence, exclusive=True)


def launch_environment(candidate, root):
    candidate, root = Path(candidate).resolve(), Path(root).resolve()
    return dict(os.environ, BOB_ROOT=str(root), TMPDIR='/private/tmp',
                PYTHONPATH=os.pathsep.join(str(candidate / name)
                    for name in ('webchat', 'services', 'state', 'reviews')))
