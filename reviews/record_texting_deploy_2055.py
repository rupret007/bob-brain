#!/usr/bin/env python3
"""Launch the existing texting deploy with absolute imports and durable early evidence."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import signal
import sys
import time
import traceback
import uuid

from texting_deploy_record import (atomic_json, atomic_text, claim_record, launch_environment,
    compact_evidence, disk_space, require_disk_space, reserve_recovery, release_recovery, failure_publish)

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
    lines = ['# TEXTING-DEPLOY-2055', '', 'RESULT: ' + result,
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
    lines += ['', 'free_space: ' + json.dumps(evidence.get('free_space', {}), sort_keys=True)]
    for label in ('before', 'after'):
        lines += ['', 'live ' + label + ' JSON (local and public):', '```json',
                  json.dumps(evidence.get(label, {}), indent=2), '```']
    lines += ['', 'Validation: TEXTING-2055-tests.json, TEXTING-2055-runner-checks.json, '
              'TEXTING-WORKER-2055.json, TEXTING-LIVE-2055.md; exact-tip gates checked by the runner.',
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
    lines += ['Production Web Bob replay: ' + str(sum(bool(x.get('request_id')) for x in exchanges)) +
              ' captured turns; ' + str(sum(bool(x.get('pass_check')) for x in exchanges)) +
              ' passed turns; ' + str(len(evidence.get('started_jobs', []))) + ' executed jobs.',
              'Isolated cross-project replay (local test remotes): ' +
              str(evidence.get('isolated_replay', {}).get('passed_turns', 0)) + '/10 turns; proof: ' +
              str(evidence.get('isolated_replay', {}).get('path', 'not verified')),
              'No Grok/xAI, force-push, notifications, or real SMS/iMessage.',
              ('Next authorized order: gaps, media, Instinct, voice, UI; each needs its own gates.' if passed else
               'Gaps/media/Instinct/voice/UI deployments remain HOLD until texting passes.')]
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
    report = args.report or reviews / 'TEXTING-DEPLOY-2055.md'
    if args.attempt < 14 or report.exists():
        raise RuntimeError('Use an unused attempt >= 14 and a new final report path')
    os.umask(0o077)
    record = reviews / f'WEBBOB-TEXTING-DEPLOYMENT-0927-attempt{args.attempt}.json'
    log = reviews / f'TEXTING-2055-attempt{args.attempt}-deployment.log'
    owner = uuid.uuid4().hex
    evidence = dict(all_pass=False, status='PREFLIGHT', sha=args.tip, attempt=args.attempt, release_series='2055',
                    draft_pr=args.draft_pr, record_owner=owner, started_at=time.time(),
                    sessions=[], task_ids=[], started_jobs=[], child_log=str(log),
                    planned_rollback=str(root / 'rollbacks' / ('webbob-texting-' + datetime.now().strftime('%Y%m%d-%H%M%S'))))
    env = launch_environment(candidate, root)
    sys.path[:0] = env['PYTHONPATH'].split(os.pathsep)
    # This precedes candidate imports, credentials, version calls and child startup.
    try:
        claim_record(record, evidence)
    except FileExistsError:
        raise  # Never overwrite another attempt's record or result.
    except OSError as error:
        evidence.update(wrapper_failure=str(error), before=versions(root), after=versions(root))
        failure_publish(record, report, evidence, report_text(evidence, record))
        print('RESULT: FAIL_OR_ROLLBACK; initial evidence I/O: ' + str(error), flush=True)
        return 1
    command = [sys.executable, '-u', str(candidate / 'reviews/deploy_texting_2055.py'),
               '--root', str(root), '--candidate', str(candidate), '--tip', args.tip,
               '--draft-pr', args.draft_pr, '--attempt', str(args.attempt),
               '--record-owner', owner, '--timeout', str(args.timeout)]
    redact = str
    previous_handlers = {}
    child_started = False
    def interrupted(signum, frame):
        raise RuntimeError('Launcher interrupted: ' + str(signum))
    for signum in (signal.SIGTERM, signal.SIGINT):
        previous_handlers[signum] = signal.signal(signum, interrupted)
    try:
        evidence['free_space'] = dict(before=require_disk_space(root, candidate, 'LAUNCHER_PREFLIGHT'))
        reserve_recovery(record, evidence)
        evidence['free_space']['reserved'] = require_disk_space(root, candidate, 'RECOVERY_RESERVED')
        from providers import Redactor
        redact = Redactor(root, (root / 'conductor/webchat/.password').read_text().strip())
        evidence['before'] = versions(root)
        atomic_json(record, evidence)
        if not matches(evidence['before'], PREVIOUS):
            raise RuntimeError('Local/public preflight no longer matches a777736')
        print('START tip=' + args.tip + ' attempt=' + str(args.attempt), flush=True)
        with log.open('x') as output:
            child_started = True
            child = subprocess.run(command, cwd=candidate / 'webchat', env=env,
                                   stdout=output, stderr=subprocess.STDOUT, timeout=args.timeout + 120)
        evidence = read(record)
        evidence['exit'] = child.returncode
        evidence['after'] = versions(root)
        if child.returncode or not evidence.get('all_pass') or not matches(evidence['after'], args.tip):
            raise RuntimeError(evidence.get('failure') or
                               'Deploy child exited ' + str(child.returncode) + '; evidence or live SHA failed')
        evidence.update(status='LIVE_PASS', finished_at=time.time())
        evidence.setdefault('free_space', {})['after'] = require_disk_space(root, candidate, 'FINAL_PUBLISH')
        # Include final report publication in the rollback-protected block.
        atomic_json(record, evidence)
        atomic_text(report, report_text(evidence, record))
        release_recovery(evidence)
        Path(evidence['emergency_marker']).unlink(missing_ok=True)
    except BaseException as error:
        # Free the reserved physical blocks before queue cancellation/restart need disk.
        recovery_errors = []
        try:
            release_recovery(evidence)
        except BaseException as release_error:
            recovery_errors.append(str(release_error))
        try:
            current = read(record)
            current.update({key: value for key, value in evidence.items()
                            if key in ('before', 'after', 'exit')})
            evidence.update(current)
        except BaseException as read_error:
            recovery_errors.append('record read: ' + str(read_error))
        evidence.update(all_pass=False, status='FAIL_OR_ROLLBACK', exit=evidence.get('exit') or 1,
                        wrapper_failure=redact(type(error).__name__ + ': ' + str(error)),
                        wrapper_traceback=redact(traceback.format_exc()))
        # No evidence or log write is required for the independent recovery subprocess.
        after = versions(root)
        rollback = evidence.get('rollback') or evidence.get('planned_rollback')
        needs_recovery = child_started and (not matches(after, PREVIOUS) or
                          (evidence.get('activated') and not evidence.get('rolled_back')))
        if rollback and needs_recovery:
            evidence['rollback'] = rollback
            try:
                recovery = subprocess.run(command + ['--rollback', rollback],
                    cwd=candidate / 'webchat', env=env, capture_output=True, text=True, timeout=180)
                evidence['emergency_rollback_exit'] = recovery.returncode
                evidence['emergency_rollback_output'] = redact(recovery.stdout[-6000:] + recovery.stderr[-3000:])
                try:
                    recovered = read(record)
                    recovered.update({key: value for key, value in evidence.items() if key.startswith('wrapper_')
                                      or key.startswith('emergency_') or key in ('exit', 'before')})
                    evidence.update(recovered)
                except BaseException as read_error:
                    recovery_errors.append('recovered record read: ' + str(read_error))
            except BaseException as recovery_error:
                recovery_errors.append('rollback: ' + redact(str(recovery_error)))
            after = versions(root)
        evidence.update(after=after, rollback_version_verified=matches(after, PREVIOUS),
                        all_pass=False, status='FAIL_OR_ROLLBACK', finished_at=time.time())
        if recovery_errors:
            evidence['recovery_errors'] = recovery_errors
        try:
            with log.open('rb') as output:
                output.seek(0, os.SEEK_END)
                output.seek(max(0, output.tell() - 6000))
                evidence['child_error_tail'] = redact(output.read(6000).decode('utf-8', errors='replace'))
        except OSError:
            pass
        try:
            evidence.setdefault('free_space', {})['after'] = disk_space(root, candidate, 'AFTER_RECOVERY')
        except OSError:
            pass
        evidence = json.loads(redact(json.dumps(compact_evidence(evidence), ensure_ascii=False)))
        published = failure_publish(record, report, evidence, report_text(evidence, record))
        evidence['final_marker'] = published
    for signum, handler in previous_handlers.items():
        signal.signal(signum, handler)
    print('RESULT: ' + evidence['status'], flush=True)
    print('LIVE_SHA: ' + str(evidence.get('after', {}).get('local', {}).get('sha', 'unknown')), flush=True)
    print('REPORT: ' + str(report), flush=True)
    return 0 if evidence['status'] == 'LIVE_PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
