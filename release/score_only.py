#!/usr/bin/env python3
"""Read-only score-only helper for one already-fixed Andrea commit.

Parked unless a one-shot Jeff ack names that exact sha. Never mutates the pin,
never honors environment overrides, never invents rounds, and never retries
except transport-only with max 2.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pin_change

N = 9
MAX_TRANSPORT_RETRIES = 2
PREREGISTERED_ROUNDS = (
    'major',
    'docs',
    'build',
    'bridge-contract',
    'no-send-replay',
    'receipt-guard',
    'health',
    'instinct-readonly',
    'delivery-protocol',
)
SCORE_LOCK = 'conductor/locks/andrea-score-only.lock'
ONESHOT_KIND = 'andrea-score-only-oneshot'


class ScoreOnlyRefused(pin_change.FailClosed):
    pass


def score_lock_path(root):
    return Path(root) / SCORE_LOCK


def oneshot_ack_path(root, sha):
    return Path(root) / 'conductor/acks' / ('jeff-andrea-score-' + pin_change.sha12(sha) + '.json')


def require_lock(root):
    path = score_lock_path(root)
    if path.is_symlink() or not path.is_file():
        raise ScoreOnlyRefused('score-only lock missing')
    pin_change.require_readonly_file(path, 'score-only lock')
    try:
        lock = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ScoreOnlyRefused('score-only lock unreadable') from exc
    if lock.get('holder') != 'score-only' or lock.get('exclusive') is not True:
        raise ScoreOnlyRefused('score-only lock is not exclusive')
    if lock.get('parked') is not False:
        # The lock inode is the exclusion record. Parked-ness is decided by ack.
        pass
    return lock


def verify_oneshot_ack(root, sha):
    pin_change.require_sha(sha)
    path = oneshot_ack_path(root, sha)
    log_path = pin_change.protected_ack_log(root)
    if not path.exists():
        raise ScoreOnlyRefused('score-only parked without one-shot Jeff ack')
    pin_change.require_readonly_file(path, 'one-shot Jeff ack')
    pin_change.require_readonly_file(log_path, 'protected ack log')
    try:
        ack = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ScoreOnlyRefused('score-only parked without one-shot Jeff ack') from exc
    if ack.get('kind') != ONESHOT_KIND or ack.get('sha') != sha or ack.get('used') is True:
        raise ScoreOnlyRefused('score-only parked without one-shot Jeff ack')
    ack_sha = pin_change.digest(path)
    hits = 0
    for line in log_path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ScoreOnlyRefused('protected ack log corrupt') from exc
        if row.get('sha') == sha and row.get('ack_sha256') == ack_sha and row.get('kind') == ONESHOT_KIND:
            hits += 1
    if hits != 1:
        raise ScoreOnlyRefused('score-only parked without one-shot Jeff ack')
    return dict(path=str(path), sha256=ack_sha)


def validate_rounds(rounds):
    if list(rounds) != list(PREREGISTERED_ROUNDS) or len(rounds) != N:
        raise ScoreOnlyRefused('N!=9')
    return list(PREREGISTERED_ROUNDS)


def validate_retries(retries):
    if not isinstance(retries, dict):
        raise ScoreOnlyRefused('extra retries')
    allowed = frozenset(('class', 'max'))
    extra = set(retries) - allowed
    if extra:
        raise ScoreOnlyRefused('extra retries')
    if retries.get('class') != 'transport':
        raise ScoreOnlyRefused('extra retries')
    maximum = retries.get('max')
    if not isinstance(maximum, int) or isinstance(maximum, bool) or maximum > MAX_TRANSPORT_RETRIES or maximum < 0:
        raise ScoreOnlyRefused('extra retries')
    return {'class': 'transport', 'max': maximum}


def score_only_plan(root, sha, *, rounds=PREREGISTERED_ROUNDS, retries=None,
                    environ=None, pin_verdict=None, code=pin_change.CODE,
                    on_main=None, baseline_sha=None):
    """Build a read-only plan for a fixed commit. Mutates nothing."""
    retries = {'class': 'transport', 'max': MAX_TRANSPORT_RETRIES} if retries is None else retries
    if isinstance(retries, dict) and 'class_' in retries and 'class' not in retries:
        retries = dict(retries)
        retries['class'] = retries.pop('class_')
    try:
        pin_change.guard_env(environ)
        pin_change.require_sha(sha)
        if pin_verdict is None:
            pin_verdict = pin_change.verify_pin_change(
                root, code=code, on_main=on_main, baseline_sha=baseline_sha,
                environ=environ)
        if pin_verdict.get('status') != pin_change.ALLOWED:
            raise ScoreOnlyRefused(pin_verdict.get('reason') or 'pin not clean')
        require_lock(root)
        ack = verify_oneshot_ack(root, sha)
        planned = validate_rounds(rounds)
        retry = validate_retries(retries)
        return dict(
            status='planned',
            mode='score-only',
            readonly=True,
            parked=False,
            sha=sha,
            rounds=planned,
            n=N,
            retries=retry,
            ack_sha256=ack['sha256'],
            pin=pin_verdict,
        )
    except pin_change.FailClosed as exc:
        return dict(status=pin_change.NEEDS_JEFF, reason=exc.reason, mode='score-only', readonly=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Read-only Andrea score-only planner')
    parser.add_argument('--root', required=True)
    parser.add_argument('--sha', required=True)
    parser.add_argument('--code', default=str(pin_change.CODE))
    parser.add_argument('--andrea-git', default='')
    args = parser.parse_args(argv)
    row = score_only_plan(
        args.root, args.sha, code=Path(args.code),
        on_main=(None if not args.andrea_git else
                 (lambda sha: pin_change.andrea_on_main(sha, andrea_git=args.andrea_git))))
    print(json.dumps(row, sort_keys=True))
    return 0 if row.get('status') == 'planned' else 1


if __name__ == '__main__':
    sys.exit(main())
