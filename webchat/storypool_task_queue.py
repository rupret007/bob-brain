"""Bounded owner-task admission through the installed StoryPool scheduler.

This is an adapter contract, not another dispatcher.  No legacy queue, process
launcher or local scheduling fallback exists.  The installed scheduler must
implement the transactional contract documented in OWNER_TASK_CONTRACT below.
"""
import fcntl
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time

from failover import atomic_json

OWNER_TASK_CONTRACT = 1
REPO = 'rupret007/bob-brain'
POLICY = 'draft-only-exact-head-karen-v1'
CHECKS = frozenset(('shared_coordination', 'global_unpaused', 'codex_unpaused',
                    'node_available', 'machine_guards', 'lane_capacity',
                    'branch_claim', 'fresh_shared_quota', 'draft_only',
                    'exact_head_karen_required', 'durable_idempotency'))
FORBIDDEN = re.compile(r'\b(?:rad-dad-show-night|grok|merge|undraft|force.push|go.live|send|publish|release|disable.{0,20}(?:guard|test))\b', re.I)


class QueueUnavailable(RuntimeError):
    """No admission was confirmed; an ambiguous attempt must not be repeated."""


class SchedulerNotInstalled(QueueUnavailable):
    """No scheduler was invoked and no enqueue could have happened."""


def installed_scheduler(install):
    """Load only the fixed operator-owned installation, never a chat path.

    The scheduler API is deliberately absent from older installations. Its
    implementation must atomically deduplicate request_id cluster-wide, check
    every CHECKS authority, enqueue into the single scheduler, and return a
    durable receipt. It must repeat controls/quota/guards and hold the branch
    lease when execution starts; admission never authorizes a send or merge.
    """
    path = Path(install).absolute() / 'cluster/control_plane/owner_task_scheduler.py'
    if not path.is_file() or path.resolve() != path:
        raise SchedulerNotInstalled('Trusted owner-task scheduler is not installed')
    for candidate in (path, *path.parents):
        info = candidate.stat()
        if info.st_uid not in (0, os.getuid()) or stat.S_IMODE(info.st_mode) & 0o022:
            raise QueueUnavailable('Unsafe trusted scheduler installation')
    install = path.parents[2]
    for name, expected in (('cluster', install / 'cluster/__init__.py'),
                           ('cluster.control_plane', install / 'cluster/control_plane/__init__.py'),
                           ('cluster.control_plane.owner_task_scheduler', path)):
        cached = sys.modules.get(name)
        if cached is not None and Path(getattr(cached, '__file__', '')).resolve() != expected:
            raise QueueUnavailable('Cached scheduler package is outside trusted installation')
    if str(install) not in sys.path:
        sys.path.insert(0, str(install))
    spec = importlib.util.spec_from_file_location('cluster.control_plane.owner_task_scheduler', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(spec.name, None)
        raise
    if (type(getattr(module, 'OWNER_TASK_CONTRACT', None)) is not int
            or module.OWNER_TASK_CONTRACT != OWNER_TASK_CONTRACT
            or not callable(getattr(module, 'admit_owner_draft_task', None))):
        raise SchedulerNotInstalled('Trusted scheduler contract is unavailable')
    return module.admit_owner_draft_task


class OwnerTaskQueue:
    def __init__(self, folder, scheduler, *, clock=time.time):
        self.folder = Path(folder) / 'owner-task-receipts'
        self.folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.scheduler, self.clock = scheduler, clock

    def enqueue(self, description, approval_token, head):
        # Input is a bounded task description, never shell text or authority.
        if (not isinstance(description, str) or not description.strip()
                or len(description) > 2000 or '\x00' in description
                or FORBIDDEN.search(description)
                or not isinstance(approval_token, str)
                or not re.fullmatch(r'wbsp-[a-f0-9]{32}', approval_token)
                or not isinstance(head, str) or not re.fullmatch(r'[a-f0-9]{40}', head)):
            raise QueueUnavailable('Invalid bounded owner task')
        fingerprint = hashlib.sha256(approval_token.encode()).hexdigest()
        request = dict(contract=OWNER_TASK_CONTRACT, request_id='webbob-' + fingerprint,
                       repo=REPO, head_sha=head, branch='draft/webbob-task-' + fingerprint[:24],
                       provider='codex', policy=POLICY, description=description)
        digest = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
        with (self.folder / 'receipts.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            path = self.folder / 'receipts.json'
            rows = json.loads(path.read_text()) if path.exists() else {}
            previous = rows.get(fingerprint)
            if previous:
                if previous.get('digest') != digest or previous.get('state') not in ('queued', 'awaiting_admission'):
                    raise QueueUnavailable('Approval attempt already consumed; request a fresh approval')
                return previous['answer']
            # A crash/timeout following this durable consume is never replayed.
            rows[fingerprint] = dict(state='unconfirmed', digest=digest)
            atomic_json(path, rows)
            receipt = self.scheduler(dict(request))
            self._validate_receipt(receipt, request)
            if receipt['state'] == 'awaiting_admission':
                answer = ('Owner-approved Codex draft task recorded in the shared StoryPool inbox. Receipt '
                          + receipt['receipt_id'] + '. It is awaiting guarded scheduler admission; no Codex lane has started.')
            else:
                answer = ('Codex draft task accepted by the guarded StoryPool scheduler. Receipt '
                          + receipt['receipt_id'] + '. Execution remains subject to scheduler guards and Karen review.')
            rows[fingerprint].update(state=receipt['state'], answer=answer)
            atomic_json(path, rows)
            return answer

    def _validate_receipt(self, receipt, request):
        if not isinstance(receipt, dict):
            raise QueueUnavailable('No durable scheduler receipt')
        expected = {k: request[k] for k in ('contract', 'request_id', 'repo', 'head_sha', 'branch', 'provider', 'policy')}
        if receipt.get('state') == 'awaiting_admission':
            recorded = receipt.get('recorded_at')
            if (any(receipt.get(k) != v for k, v in expected.items())
                    or type(receipt.get('contract')) is not int
                    or receipt.get('receipt_id') != request['request_id']
                    or type(recorded) not in (int, float) or not math.isfinite(recorded)
                    or not 0 <= recorded <= self.clock()
                    or 'checks' in receipt or 'codex_weekly_pct' in receipt):
                raise QueueUnavailable('No durable shared inbox receipt')
            return
        checks = receipt.get('checks')
        observed, quota = receipt.get('admitted_at'), receipt.get('codex_weekly_pct')
        if (any(receipt.get(k) != v for k, v in expected.items())
                or type(receipt.get('contract')) is not int
                or receipt.get('state') != 'queued'
                or not isinstance(receipt.get('receipt_id'), str)
                or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', receipt['receipt_id'])
                or not isinstance(checks, dict) or set(checks) != CHECKS
                or any(value is not True for value in checks.values())
                or type(observed) not in (int, float) or not math.isfinite(observed)
                or not 0 <= self.clock() - observed <= 30
                or type(quota) not in (int, float) or not math.isfinite(quota)
                or not 0 <= quota < 75):
            raise QueueUnavailable('Scheduler did not verify guarded task admission')


def _require_available(root, data):
    if (Path(root) / 'conductor/MAINTENANCE').exists():
        raise QueueUnavailable('Scheduling paused')
    control = Path(data) / 'node-control.json'
    if control.exists():
        try:
            value = json.loads(control.read_text())
            if not isinstance(value, dict) or value.get('maintenance') is not False:
                raise ValueError('Node unavailable')
        except (OSError, ValueError):
            raise QueueUnavailable('Node draining or operator state unreadable') from None


def enqueue_installed_owner_task(root, install, data, description, token):
    """Called only after StoryPoolActions consumes a fresh typed approval."""
    _require_available(root, data)
    # Check scheduler availability before creating receipts or querying git.
    scheduler = installed_scheduler(install)
    result = subprocess.run(['git', '-C', str(root), 'rev-parse', 'HEAD'],
                            capture_output=True, text=True, timeout=5, check=True)
    def admit(request):
        _require_available(root, data)
        return scheduler(request)
    return OwnerTaskQueue(data, admit).enqueue(description, token, result.stdout.strip())
