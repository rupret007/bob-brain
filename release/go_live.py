#!/usr/bin/env python3
"""Stage a release plan; activation additionally requires Jeff's exact-SHA OK.

The existing solo controller owns snapshots, authenticated health rounds,
service coordination, durable recovery and automatic rollback. This wrapper
adds the current Karen/paired-scoring gates; it never merges or changes a PR.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys

import solo
from release_ownership import serialized

PREVIOUS = 'cf83a9a80e0426d6998a0bf7b3a0574e52ac8e1a'
REPO = 'rupret007/bob-brain'
CI_NAMES = {'python-ubuntu-latest', 'python-macos-latest', 'unittest'}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def packet(path, sha):
    """Read a trusted runner's private normalized receipt and its raw evidence.

    Normalization must be performed by the operator from the actual runner
    output. A packet/label written by a conversation is not a review verdict.
    Hash binding protects against later accidental replacement, not forgery by
    a process with access to the operator's private evidence directory.
    """
    path = Path(path)
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 65536
            and not path.stat().st_mode & 0o077, 'Private gate receipt required')
    value = json.loads(path.read_text())
    require(value.get('sha') == sha and value.get('verdict') == 'PASS'
            and value.get('unresolved_blockers') == [], 'Gate is stale, failed or incomplete')
    evidence = value.get('evidence', [])
    require(isinstance(evidence, list) and evidence, 'Raw gate evidence required')
    for row in evidence:
        source = Path(row['path'])
        require(source.is_absolute() and source.is_file() and not source.is_symlink()
                and source.resolve().is_relative_to(path.parent.resolve())
                and source.stat().st_size <= 8 * 1024 * 1024, 'Gate evidence must stay in its receipt directory')
        require(hashlib.sha256(source.read_bytes()).hexdigest() == row['sha256'], 'Gate evidence changed')
    return value


def external_gates(sha, karen_path, scores_path):
    karen = packet(karen_path, sha)
    require(karen.get('reviewer') == 'Karen' and karen.get('findings'), 'Exact-head Karen PASS required')
    scores = packet(scores_path, sha)
    require(scores.get('reviewers') == ['Claude', 'Codex'], 'Scoring requires Claude+Codex only')
    for name in ('main', 'holdout'):
        row = scores.get(name, {})
        require(row.get('sha') == sha and row.get('verdict') == 'PASS'
                and row.get('reviewers') == ['Claude', 'Codex'], 'Both paired sets must pass at this SHA')
    score = scores['main'].get('score')
    require(type(score) in (int, float) and math.isfinite(score) and score >= 144,
            'Paired main score must be at least 144')


def github_gates(sha, pr, gh):
    def read(*argv):
        return json.loads(subprocess.check_output([str(gh), *argv], text=True, timeout=30))
    value = read('pr', 'view', pr, '--repo', REPO, '--json', 'headRefOid,isDraft,state')
    require(value['headRefOid'] == sha and value['isDraft'] and value['state'] == 'OPEN',
            'Candidate must still be the exact open draft PR')
    checks = read('api', f'repos/{REPO}/commits/{sha}/check-runs?per_page=100')
    require(checks.get('total_count', 101) <= 100, 'CI inventory needs explicit inspection')
    latest = {}
    for row in sorted(checks.get('check_runs', []), key=lambda r: r['id']):
        if row.get('head_sha') == sha and row.get('app', {}).get('slug') == 'github-actions':
            latest[row['name']] = row
    require(all(name in latest and latest[name].get('conclusion') == 'success'
                and latest[name].get('status') == 'completed' for name in CI_NAMES),
            'Fresh final-head GitHub Actions checks must all pass')


def approval_text(sha):
    return f'GO LIVE {sha} rollback {PREVIOUS}'


def plan(sha):
    return dict(stage_only=True, candidate=sha, previous=PREVIOUS,
                predecessor_live_identity='Must be freshly verified on Mini; commit resolution alone is insufficient',
                approval_required=approval_text(sha),
                controller='release/solo.py deploy --feature improve',
                health='Existing authenticated local and public exact-build checks, two complete live rounds',
                rollback='Existing transaction restores and authenticates the pinned predecessor on any post-activation failure',
                recovery='release/solo.py recover-pending --root ROOT --feature improve',
                gates=['full unscoped consecutive release greens and self-review', 'final-head CI',
                       'Karen PASS at exact SHA with raw evidence', 'Claude+Codex main >=144 and holdout PASS',
                       'fresh Mini predecessor/build/state verification', 'Jeff exact-SHA go-live OK'],
                legacy_controller_precondition='Existing checked-tree merge/base/predecessor rules still apply; wrapper never merges')


@serialized
def activate(args):
    sha = solo.identity()
    require(args.jeff_ok == approval_text(sha), 'Jeff exact-SHA go-live OK required')
    require(solo.qualification_scope.selected() is None, 'Go-live requires complete unscoped qualification')
    require(solo.git('rev-parse', PREVIOUS + '^{commit}') == PREVIOUS, 'Pinned predecessor unavailable')
    external_gates(sha, args.karen, args.scores)
    github_gates(sha, args.pr, args.gh)
    # Keep every existing release guard, including two consecutive full greens.
    solo.verify_gates(sha, 'improve', args.checks, args.review)
    solo.versions(args.root, PREVIOUS)
    require(solo.identity() == sha, 'Candidate changed during go-live preflight')
    solo.deploy(argparse.Namespace(root=args.root, feature='improve', previous=PREVIOUS,
                                  pr=args.pr, checks=args.checks, review=args.review))


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('plan', 'activate'))
    parser.add_argument('--root', type=Path)
    parser.add_argument('--pr', default='161')
    for name in ('checks', 'review', 'karen', 'scores'):
        parser.add_argument('--' + name, type=Path)
    parser.add_argument('--gh', type=Path, default=Path.home() / '.local/bin/gh')
    parser.add_argument('--jeff-ok')
    args = parser.parse_args()
    if args.action == 'plan':
        print(json.dumps(plan(solo.identity()), indent=2))
    else:
        require(all(getattr(args, name) is not None for name in ('root', 'checks', 'review', 'karen', 'scores')),
                'Root and every qualification/review receipt are required')
        def interrupted(signum, frame):
            raise RuntimeError('Release interrupted by signal ' + str(signum))
        for signum in (signal.SIGTERM, signal.SIGINT):
            signal.signal(signum, interrupted)
        activate(args)


if __name__ == '__main__':
    main()
