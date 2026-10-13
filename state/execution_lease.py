"""Opt-in shared-machine execution lease for background worker jobs.

Disabled by default. When the profile is enabled, background jobs share a
small global slot count (one unless configured otherwise). The lease layers
on existing per-lane locks and queue admission. Interactive chat locks stay
outside it. The OS releases the flock when the holding process exits.
"""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import sys
import time

DEFAULT_SLOTS = 1
PROFILE_ENV = 'BOB_SHARED_EXECUTION_LEASE'
SLOTS_ENV = 'BOB_SHARED_EXECUTION_LEASE_SLOTS'
LOCK_ENV = 'BOB_SHARED_EXECUTION_LEASE_LOCK'
CAPACITY_REASON = 'shared execution lease at capacity'


def _env(env):
    return os.environ if env is None else env


def _truthy(value):
    return str(value or '').strip().lower() in ('1', 'true', 'yes', 'on')


def _falsey(value):
    return str(value or '').strip().lower() in ('0', 'false', 'no', 'off')


def _slots(value, default=DEFAULT_SLOTS):
    if type(value) is int and value >= 1:
        return value
    raw = str(value or '').strip()
    if raw.isdigit() and int(raw) >= 1:
        return int(raw)
    return default


def load_profile(root, env=None):
    env = _env(env)
    override = env.get(PROFILE_ENV, '')
    if _falsey(override):
        return dict(enabled=False, slots=DEFAULT_SLOTS)
    if _truthy(override):
        return dict(enabled=True, slots=_slots(env.get(SLOTS_ENV), DEFAULT_SLOTS))
    path = Path(root) / 'conductor/webchat/execution-lease.json'
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError, TypeError):
        return dict(enabled=False, slots=DEFAULT_SLOTS)
    if not isinstance(data, dict) or not data.get('enabled'):
        return dict(enabled=False, slots=DEFAULT_SLOTS)
    return dict(enabled=True, slots=_slots(data.get('slots'), DEFAULT_SLOTS))


def lock_path(root, env=None, index=0):
    override = _env(env).get(LOCK_ENV, '').strip()
    if override:
        path = Path(override)
        return path if index == 0 else path.with_name(path.name + '-' + str(index))
    return Path(root) / 'conductor/locks' / ('execution-lease-' + str(index) + '.lock')


def admission_block(root, env=None):
    """Recorded capacity reason, or None when the profile is off or a slot is free."""
    if available(root, env):
        return None
    return CAPACITY_REASON


def available(root, env=None):
    if not load_profile(root, env)['enabled']:
        return True
    try:
        with hold(root, env):
            return True
    except BlockingIOError:
        return False


@contextmanager
def hold(root, env=None):
    """Acquire one global background slot. No-op when the profile is disabled."""
    profile = load_profile(root, env)
    if not profile['enabled']:
        yield None
        return
    for index in range(profile['slots']):
        path = lock_path(root, env, index)
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = path.open('a+')
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            handle.close()
            continue
        try:
            yield handle
            return
        finally:
            handle.close()
    raise BlockingIOError(CAPACITY_REASON)


def _fixture_main(argv):
    """Offline subprocess helper. Requires a test lock override; never production paths."""
    env = os.environ
    if not env.get(LOCK_ENV):
        raise SystemExit('execution-lease fixture refused to use a production lock path')
    root = env.get('BOB_EXECUTION_LEASE_TEST_ROOT') or env.get('BOB_ROOT') or '.'
    action = argv[1] if len(argv) > 1 else 'hold'
    if action == 'probe':
        sys.stdout.write(('FREE' if available(root) else 'BUSY') + '\n')
        return
    if action != 'hold':
        raise SystemExit('unknown execution-lease fixture action')
    with hold(root):
        sys.stdout.write('HELD\n')
        sys.stdout.flush()
        ready = env.get('BOB_EXECUTION_LEASE_TEST_READY')
        if ready:
            Path(ready).write_text('HELD\n')
        if env.get('BOB_EXECUTION_LEASE_TEST_CRASH') == '1':
            os._exit(1)
        time.sleep(float(env.get('BOB_EXECUTION_LEASE_TEST_SECONDS', '8')))


if __name__ == '__main__':
    _fixture_main(sys.argv)
