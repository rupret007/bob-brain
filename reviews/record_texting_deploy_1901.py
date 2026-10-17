#!/usr/bin/env python3
"""Launch the existing texting deploy with absolute imports and durable early evidence."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import signal
import sys
import time
import traceback
import uuid

from texting_deploy_record import atomic_json, atomic_text, claim_record, launch_environment

ROOT = Path('/Users/jeffstory/Documents/bob-overnight-inject')
WT = Path(__file__).resolve().parents[1]
PREVIOUS = 'a777736b3f0a37c82b0c4c62be8c91117c4c9881'


def read(path):
    return json.loads(path.read_text())


def versions(root):
    from live_redeploy_check import Client
    password = root / 'conductor/webchat/.password'
    result = {}
    for name in ('local', 'public'):
        try:
            url = 'http://127.0.0.1:8787' if name == 'local' else (
                root / 'conductor/webchat/.public-origin').read_text().strip()
            client = Client(url, password)
            client.login()
            result[name] = client.call('/api/version')
        except Exception as error:
            result[name] = dict(error=type(error).__name__ + ': ' + str(error))
    return result


def matches(pair, sha):
    return all(pair.get(name, {}).get('sha') == sha for name in ('local', 'public'))


def report_text(evidence, record):
    passed = evidence.get('status') == 'LIVE_PASS'
    result = 'LIVE_PASS' if passed else 'FAIL_OR_ROLLBACK'
    lines = ['# TEXTING-DEPLOY-1901', '', 'RESULT: ' + result,
             'tip: ' + evidence['sha'], 'draft_pr: ' + evidence['draft_pr'],
             'attempt_slot: ' + str(evidence['attempt']), 'evidence: ' + str(record),
             'child_log: ' + evidence['child_log'],
             'exit: ' + str(evidence.get('exit', 1)),
             'rollback_path: ' + str(evidence.get('rollback', 'not activated')),
             'rollback_verified: ' + ('not exercised (live passed; snapshot ready)' if passed else
                                      str(evidence.get('rollback_version_verified', False))),
             'rollback_snapshot_sha: ' + str(evidence.get('previous_version', {}).get('sha', 'not activated')),
             'clean_merge: ' + str(evidence.get('clean_merge', {}).get('merge_sha', 'unavailable')),
             'screen_policy: ' + str(evidence.get('restart', {}).get('screen_isolation_policy', 'not run')),
             'screen_isolation: ' + str(evidence.get('restart', {}).get('other_screens_unchanged', 'not run'))]
    for label in ('before', 'after'):
        lines += ['', 'live ' + label + ' JSON (local and public):', '```json',
                  json.dumps(evidence.get(label, {}), indent=2), '```']
    lines += ['', 'Validation: TEXTING-1901-tests.json, TEXTING-1901-runner-checks.json, '
              'TEXTING-WORKER-1901.json, TEXTING-LIVE-1901.md; exact-tip gates checked by the runner.',
              'Activation local/public candidate SHA verified: ' + str(evidence.get('activation_verified', False)),
              'Texting smoke: ' + ('PASS' if evidence.get('texting_smoke', {}).get('all_pass') else 'not passed')]
    for label, key in (('1035/dd47c4cb MiniMax completion replay', 'jobcompletion_regression'),
                       ('f2c47c4c MiniMax Action plan replay', 'action_plan_regression'),
                       ('20bfc6f MiniMax regression drafts replay', 'regression_drafts_regression'),
                       ('1803 guard-consistency capture', 'guard_consistency_fixture_regression'),
                       ('1403 completion JSON regression', 'completion_json_1403_regression')):
        gate = evidence.get(key, {})
        lines.append(label + ': ' + ('PASS' if gate.get('pass_check') else 'not passed'))
        if gate.get('result_path'):
            lines.append('Accepted saved report: ' + gate['result_path'])
    exchanges = [x for s in evidence.get('sessions', []) for x in s.get('exchanges', [])]
    lines += ['Live replay: ' + str(sum(bool(x.get('request_id')) for x in exchanges)) +
              ' captured turns; ' + str(sum(bool(x.get('pass_check')) for x in exchanges)) +
              ' passed turns; ' + str(len(evidence.get('started_jobs', []))) + ' executed jobs.',
              'No Grok/xAI, force-push, notifications, or real SMS/iMessage.',
              'Gaps/media/voice/UI/Instinct deployments remain HOLD.']
    if evidence.get('wrapper_failure') or evidence.get('failure'):
        lines += ['', 'Failure: ' + str(evidence.get('wrapper_failure') or evidence['failure']),
                  'Failed stage: ' + str(evidence.get('failed_stage', 'launcher preflight'))]
    if evidence.get('child_error_tail'):
        lines += ['', 'Child exception/log tail:', '```text', evidence['child_error_tail'], '```']
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--candidate', type=Path, default=WT)
    parser.add_argument('--tip', required=True)
    parser.add_argument('--attempt', type=int, required=True)
    parser.add_argument('--draft-pr', required=True)
    parser.add_argument('--timeout', type=int, default=1800)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args(argv)
    root, candidate = args.root.resolve(), args.candidate.resolve()
    reviews = root / 'conductor/reviews'
    report = args.report or reviews / 'TEXTING-DEPLOY-1901.md'
    if args.attempt < 12 or report.exists():
        raise RuntimeError('Use an unused attempt >= 12 and a new final report path')
    os.umask(0o077)
    record = reviews / f'WEBBOB-TEXTING-DEPLOYMENT-0927-attempt{args.attempt}.json'
    log = reviews / f'TEXTING-1901-attempt{args.attempt}-deployment.log'
    owner = uuid.uuid4().hex
    evidence = dict(all_pass=False, status='PREFLIGHT', sha=args.tip, attempt=args.attempt,
                    draft_pr=args.draft_pr, record_owner=owner, started_at=time.time(),
                    sessions=[], task_ids=[], started_jobs=[], child_log=str(log))
    # This precedes candidate imports, credentials, version calls and child startup.
    claim_record(record, evidence)
    env = launch_environment(candidate, root)
    sys.path[:0] = env['PYTHONPATH'].split(os.pathsep)
    command = [sys.executable, '-u', str(candidate / 'reviews/deploy_texting_1901.py'),
               '--root', str(root), '--candidate', str(candidate), '--tip', args.tip,
               '--draft-pr', args.draft_pr, '--attempt', str(args.attempt),
               '--record-owner', owner, '--timeout', str(args.timeout)]
    redact = str
    previous_handlers = {}
    def interrupted(signum, frame):
        raise RuntimeError('Launcher interrupted: ' + str(signum))
    for signum in (signal.SIGTERM, signal.SIGINT):
        previous_handlers[signum] = signal.signal(signum, interrupted)
    try:
        from providers import Redactor
        redact = Redactor(root, (root / 'conductor/webchat/.password').read_text().strip())
        evidence['before'] = versions(root)
        atomic_json(record, evidence)
        if not matches(evidence['before'], PREVIOUS):
            raise RuntimeError('Local/public preflight no longer matches a777736')
        print('START tip=' + args.tip + ' attempt=' + str(args.attempt), flush=True)
        with log.open('x') as output:
            child = subprocess.run(command, cwd=candidate / 'webchat', env=env,
                                   stdout=output, stderr=subprocess.STDOUT, timeout=args.timeout + 120)
        evidence = read(record)
        evidence['exit'] = child.returncode
        evidence['after'] = versions(root)
        if child.returncode or not evidence.get('all_pass') or not matches(evidence['after'], args.tip):
            if log.exists():
                evidence['child_error_tail'] = redact(log.read_text()[-6000:])
            raise RuntimeError(evidence.get('failure') or
                               'Deploy child exited ' + str(child.returncode) + '; evidence or live SHA failed')
        evidence['status'] = 'LIVE_PASS'
    except BaseException as error:
        # The runner may have reached activation after our last local checkpoint.
        current = read(record)
        current.update({key: value for key, value in evidence.items()
                        if key in ('before', 'after', 'exit', 'child_error_tail')})
        evidence = current
        evidence.update(all_pass=False, status='FAIL_OR_ROLLBACK', exit=evidence.get('exit') or 1,
                        wrapper_failure=redact(type(error).__name__ + ': ' + str(error)),
                        wrapper_traceback=redact(traceback.format_exc()))
        if log.exists():
            evidence['child_error_tail'] = redact(log.read_text()[-6000:])
        atomic_json(record, evidence)
        try:
            after = versions(root)
            if evidence.get('activated') and evidence.get('rollback') and (
                    not evidence.get('rolled_back') or not matches(after, PREVIOUS)):
                try:
                    with log.open('a') as output:
                        recovery = subprocess.run(command + ['--rollback', evidence['rollback']],
                            cwd=candidate / 'webchat', env=env, stdout=output, stderr=subprocess.STDOUT, timeout=180)
                    recovered = read(record)
                    recovered.update({key: value for key, value in evidence.items() if key.startswith('wrapper_')
                                      or key in ('child_error_tail', 'exit', 'before')})
                    evidence = recovered
                    evidence['emergency_rollback_exit'] = recovery.returncode
                except BaseException as recovery_error:
                    evidence['emergency_rollback_error'] = redact(str(recovery_error))
                after = versions(root)
            evidence['after'] = after
            evidence['rollback_version_verified'] = matches(after, PREVIOUS)
        except BaseException as verify_error:
            evidence.update(rollback_version_verified=False, version_error=redact(str(verify_error)))
        evidence.update(all_pass=False, status='FAIL_OR_ROLLBACK')
    evidence['finished_at'] = time.time()
    atomic_json(record, evidence)
    atomic_text(report, report_text(evidence, record))
    for signum, handler in previous_handlers.items():
        signal.signal(signum, handler)
    print('RESULT: ' + evidence['status'], flush=True)
    print('LIVE_SHA: ' + str(evidence.get('after', {}).get('local', {}).get('sha', 'unknown')), flush=True)
    print('REPORT: ' + str(report), flush=True)
    return 0 if evidence['status'] == 'LIVE_PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
