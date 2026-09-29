#!/usr/bin/env python3
"""Run the bounded deployment, recover if needed, and always record the result."""
import argparse
import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from live_redeploy_check import Client

ROOT = Path('/Users/jeffstory/Documents/bob-overnight-inject')
REVIEWS = ROOT / 'conductor/reviews'
WT = ROOT / 'workspaces/webbob-texting-replay-json-1508'
TIP = '2cd10065b55d4aba4179a1f49e11f1949bbbb5be'
PREVIOUS = 'a777736b3f0a37c82b0c4c62be8c91117c4c9881'
PR = json.loads((REVIEWS / 'TEXTING-CLEAN-MERGE-1508.json').read_text())['draft_pr']
RUNNER = REVIEWS / 'deploy_texting_1508.py'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--report', type=Path, default=REVIEWS / 'TEXTING-DEPLOY-1508.md')
REPORT = parser.parse_args().report.resolve()
os.umask(0o077)
if REPORT.exists():
    raise SystemExit('Refusing to overwrite an existing final 1508 report')

def version():
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open('http://127.0.0.1:8787/api/version', timeout=15) as response:
        return json.load(response)

def read(path):
    return json.loads(path.read_text()) if path.exists() else {}

def public_version():
    client = Client((ROOT / 'conductor/webchat/.public-origin').read_text().strip(), ROOT / 'conductor/webchat/.password')
    client.login()
    return client.call('/api/version')

attempt = 8
while (REVIEWS / f'WEBBOB-TEXTING-DEPLOYMENT-0927-attempt{attempt}.json').exists():
    attempt += 1
record = REVIEWS / f'WEBBOB-TEXTING-DEPLOYMENT-0927-attempt{attempt}.json'
before = read(REVIEWS / 'TEXTING-DEPLOY-1508.preflight.json').get('local', {})
after, evidence, failure = {}, {}, ''
public_before, public_after = {}, {}
exit_code = 1
command = [sys.executable, '-u', str(RUNNER), '--root', str(ROOT), '--candidate', str(WT),
           '--draft-pr', PR, '--expected-live', 'a777736', '--attempt', str(attempt), '--timeout', '1800']
print('START=' + datetime.now(timezone.utc).isoformat(), flush=True)
print('PR=' + PR + ' attempt=' + str(attempt), flush=True)
try:
    before = version()
    public_before = public_version()
    if before.get('sha') != PREVIOUS or public_before.get('sha') != PREVIOUS:
        raise RuntimeError('Local/public preflight no longer matches a777736')
    print('live before: ' + json.dumps(before), flush=True)
    result = subprocess.run(command, cwd=WT / 'webchat', timeout=1920)
    exit_code = result.returncode
    evidence = read(record)
    after = version()
    public_after = public_version()
    if exit_code or not evidence.get('all_pass') or after.get('sha') != TIP or public_after.get('sha') != TIP:
        raise RuntimeError(evidence.get('failure') or 'Deployment exit, evidence, or live SHA did not pass')
except BaseException as error:
    failure = str(error)
    exit_code = exit_code or 1
    evidence = read(record)
    rollback = evidence.get('rollback')
    if evidence.get('activated') and rollback:
        try:
            current = version()
        except Exception:
            current = {}
        if current.get('sha') != PREVIOUS or not evidence.get('rolled_back'):
            try:
                recovery = subprocess.run(command + ['--rollback', rollback], cwd=WT / 'webchat', timeout=180)
                evidence['emergency_rollback_exit'] = recovery.returncode
            except BaseException as recovery_error:
                evidence['emergency_rollback_error'] = str(recovery_error)
    try:
        after = version()
    except Exception as version_error:
        after = dict(error=str(version_error))
    try:
        public_after = public_version()
    except Exception as version_error:
        public_after = dict(error=str(version_error))
    evidence['wrapper_failure'] = failure
    evidence['rollback_version_verified'] = after.get('sha') == public_after.get('sha') == PREVIOUS
    if record.exists():
        temporary = record.with_suffix('.wrapper.tmp')
        temporary.write_text(json.dumps(evidence, indent=2) + '\n')
        temporary.replace(record)

passed = exit_code == 0 and evidence.get('all_pass') and after.get('sha') == public_after.get('sha') == TIP
result = 'LIVE_PASS' if passed else 'FAIL_OR_ROLLBACK'
finished = datetime.now().astimezone().isoformat()
clean = read(REVIEWS / 'TEXTING-CLEAN-MERGE-1508.json')
lines = [
    '# TEXTING-DEPLOY-1508', '',
    f'exit: {exit_code}', f'finished: {finished}', f'tip: {TIP}', f'draft_pr: {PR}',
    f'deploy_runner: {RUNNER}', f'attempt_slot: {attempt}', f'evidence: {record}',
    'clean_merge: ' + clean.get('merge_sha', 'not merged'),
    'clean_note: ' + clean.get('clean_note', 'unavailable'),
    'rollback_path: ' + str(evidence.get('rollback', 'not activated')),
    'rollback_verified: ' + ('not exercised (live passed; snapshot ready)' if passed else str(evidence.get('rolled_back') or evidence.get('rollback_version_verified', False))),
    'rollback_snapshot_sha: ' + str(evidence.get('previous_version', {}).get('sha', 'not activated')),
    'ancestry_repository: ' + str(evidence.get('clean_ancestry', {}).get('repo', 'unavailable')),
    'screen_isolation: ' + str(evidence.get('restart', {}).get('other_screens_unchanged', 'not run')),
    'screen_policy: ' + str(evidence.get('restart', {}).get('screen_isolation_policy', 'not run')),
    '', 'live before JSON:', '```json', json.dumps(before, indent=2), '```',
    '', 'live after JSON:', '```json', json.dumps(after, indent=2), '```',
    '', 'public before JSON:', '```json', json.dumps(public_before, indent=2), '```',
    '', 'public after JSON:', '```json', json.dumps(public_after, indent=2), '```',
    '', 'Validation: fresh exact-tip TEXTING-1508-tests.json and TEXTING-LIVE-1508.md BOTH_PASS; TEXTING-WORKER-1508.json real worker probes.',
    'Deploy guard validation: TEXTING-1508-deploy-guard-tests.txt; TEXTING-1508-runner-checks.json.',
    'Texting smoke: ' + ('PASS' if evidence.get('texting_smoke', {}).get('all_pass') else 'not passed'),
    '1035/dd47c4cb MiniMax completion replay: ' + ('PASS' if evidence.get('jobcompletion_regression', {}).get('pass_check') else 'not passed'),
    '1403 completion JSON regression: ' + ('PASS' if evidence.get('completion_json_1403_regression', {}).get('pass_check') else 'not passed'),
    'Completion report: ' + str(evidence.get('jobcompletion_regression', {}).get('result_path', 'unavailable')),
    'Prior status-dump and incomplete-verification regressions: ' + ('PASS' if all(evidence.get(k, {}).get('pass_check') for k in (
        'prior_failure_regression', 'incomplete_verification_regression', 'incomplete_deliverable_regression',
        'incomplete_deliverable_1107_regression')) else 'not passed'),
    'Live replay: ' + str(sum(len(s.get('exchanges', [])) for s in evidence.get('sessions', []))) +
        ' captured turns; ' + str(sum(x.get('pass_check', False) for s in evidence.get('sessions', []) for x in s.get('exchanges', []))) + ' passed turns; ' + str(len(evidence.get('started_jobs', []))) + ' executed jobs.',
    'No Grok/xAI, force-push, notifications, or real texting delivery requests were used.',
    'Gaps/media/voice/UI/Instinct deployments remain HOLD.',
]
if failure:
    lines.extend(['', 'Failure: ' + failure])
lines.extend(['', 'RESULT: ' + result, ''])
if passed:
    (REVIEWS / 'TEXTING-LIVE-PASS-1508.md').write_text(
        '# TEXTING-LIVE-PASS-1508\n\nfinished: ' + finished + '\nnew live short SHA: 2cd1006\nfull SHA: ' + TIP +
        '\ndraft_pr: ' + PR + '\nevidence: ' + str(record) + '\nreport: TEXTING-DEPLOY-1508.md\n\nRESULT: LIVE_PASS\n')
temporary = REPORT.with_suffix('.md.tmp')
temporary.write_text('\n'.join(lines))
temporary.replace(REPORT)
print('RESULT: ' + result, flush=True)
print('LIVE_SHA: ' + str(after.get('short_sha', 'unknown')), flush=True)
print('REPORT: ' + str(REPORT), flush=True)
raise SystemExit(0 if passed else 1)
