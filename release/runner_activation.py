"""Refresh an already enabled runner and verify its actual executable source.

The caller owns release, supervisor and web-dispatch locks in that order.
No absent service is enabled, and a running task is never killed to deploy.
"""
import json
from contextlib import contextmanager
import fcntl
import threading
from pathlib import Path
import shlex
import subprocess
import time

import runtime
import task_queue

_held = threading.local()


@contextmanager
def shared_lock(root, name):
    """Reentrant only within this controller thread; uses the runtime's inode."""
    path = root / 'conductor/locks' / (name + '.lock')
    path.parent.mkdir(parents=True, exist_ok=True)
    key = str(path.resolve())
    owned = getattr(_held, 'names', set())
    if key in owned:
        yield
        return
    with path.open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        _held.names = owned | {key}
        try:
            yield
        finally:
            _held.names = owned


@contextmanager
def coordinated(root):
    with shared_lock(root, 'supervisor'), shared_lock(root, 'web-dispatch'):
        yield


def required(root, record):
    if record.get('runner_refresh', {}).get('required'):
        return True
    path = Path(record['rollback']) / 'runner-required.json'
    try:
        from activation_journal import private_json
        value = private_json(path)
    except FileNotFoundError:
        return False
    if value.get('sha') != record['sha'] or value.get('required') is not True:
        raise RuntimeError('Runner preservation receipt identity mismatch')
    return True


def preserve_observed(root, record, observed):
    if observed and not required(root, record):
        from texting_deploy_record import atomic_json
        atomic_json(Path(record['rollback']) / 'runner-required.json',
                    dict(sha=record['sha'], required=True, observed=observed))


def observe(root):
    sessions = runtime.screen_sessions()
    locked = runtime.service_lock_held('job-runner')
    if not locked:
        if 'svc-job-runner' in sessions:
            raise RuntimeError('Runner screen has no verified lifetime lock')
        return None
    pid = int((root / 'conductor/locks/job-runner.pid').read_text().strip())
    if pid <= 1:
        raise RuntimeError('Invalid runner PID')
    result = subprocess.run(['ps', '-p', str(pid), '-o', 'command='],
                            capture_output=True, text=True, timeout=5)
    parts = shlex.split(result.stdout.strip()) if result.returncode == 0 else []
    scripts = [Path(part) for part in parts if part.endswith('/services/job-runner.sh')]
    if len(scripts) != 1 or '--locked' not in parts or not scripts[0].is_absolute():
        raise RuntimeError('Runner PID does not identify the expected locked script')
    code = scripts[0].parent.parent.resolve(strict=True)
    if not code.is_relative_to(root.resolve()) or scripts[0].resolve() != code / 'services/job-runner.sh':
        raise RuntimeError('Runner process belongs to another installation')
    build = json.loads((code / 'webbob-build.json').read_text())
    return dict(pid=pid, code_root=str(code), sha=build['sha'], screen=sessions.get('svc-job-runner'))


def obligation(root):
    observed = observe(root)
    return dict(required=observed is not None, prior=observed)


def matches(root, target):
    observed = observe(root)
    target = Path(target).resolve()
    return bool(observed and observed['code_root'] == str(target) and observed['screen'] and
                observed['sha'] == json.loads((target / 'webbob-build.json').read_text())['sha'])


def drain(root, *, timeout=15):
    deadline = time.monotonic() + timeout
    def alive(row):
        # Unlike web_dispatch.worker_alive, this never reaps an expired live
        # worker. A held execution lock is enough to leave it alone.
        path = root / 'conductor/locks' / ('dispatch-' + row['id'] + '.lock')
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a') as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return False
            except BlockingIOError:
                return True
    while True:
        task_queue.recover(root, alive)
        if not any(row['status'] in task_queue.ACTIVE for row in task_queue.tasks(root).values()):
            return
        if time.monotonic() >= deadline:
            raise RuntimeError('Runner refresh deferred: active tasks did not finish within the drain window')
        # tasks() releases the queue lock before waiting; heartbeat/result writers
        # must be able to finish while web-dispatch admission is fenced.
        time.sleep(.1)


def stop(root, allowed):
    observed = observe(root)
    if observed is None:
        return None
    if Path(observed['code_root']).resolve() not in {Path(path).resolve() for path in allowed}:
        raise RuntimeError('Runner source changed to an unrelated release')
    runtime.stop_service_process('job-runner')
    if runtime.service_lock_held('job-runner'):
        raise RuntimeError('Old runner did not release its lifetime lock')
    if observed['screen']:
        result = subprocess.run(['screen', '-S', observed['screen'], '-X', 'quit'],
                                capture_output=True, timeout=10)
        if result.returncode and observed['screen'] in runtime.screen_sessions().values():
            raise RuntimeError('Old runner screen did not stop')
    return observed


def start(root, target):
    if not runtime.start_screen('job-runner'):
        raise RuntimeError('Required runner did not restart')
    for _ in range(40):
        try:
            if matches(root, target):
                return observe(root)
        except (OSError, ValueError, RuntimeError):
            pass
        time.sleep(.1)
    raise RuntimeError('Runner restarted without the intended dispatch source')


@contextmanager
def refresh(root, pins, intent):
    record = (intent or {}).get('record', {})
    obligation = record.get('runner_refresh') or {}
    ticket = dict(required=False)
    if not obligation:
        yield ticket
        return
    with shared_lock(root, 'web-dispatch'):
        observed = observe(root)
        allowed = [*record['snapshots'].values(), *record.get('original_pins', {}).values(),
                   str(Path(record['rollback']) / 'candidate')]
        if obligation.get('prior'):
            allowed.append(obligation['prior']['code_root'])
        if observed and Path(observed['code_root']).resolve() not in {Path(p).resolve() for p in allowed}:
            raise RuntimeError('Runner source changed to an unrelated release')
        preserve_observed(root, record, observed)
        ticket['required'] = required(root, record)
        drain(root)
        if Path(pins['dispatch']).resolve() == Path(record['snapshots']['dispatch']).resolve():
            ticket['cancelled_pending_tasks'] = [row['id'] for row in task_queue.cancel_for_rollback(root, record.get('at', 0))]
        if ticket['required']:
            ticket['before'] = stop(root, allowed)
        yield ticket
        if ticket['required']:
            ticket['after'] = start(root, pins['dispatch'])
