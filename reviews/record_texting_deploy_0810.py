#!/usr/bin/env python3
"""Run the bounded deployment, recover if needed, and always record the result."""
import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/Users/jeffstory/Documents/bob-overnight-inject')
REVIEWS = ROOT / 'conductor/reviews'
WT = ROOT / 'workspaces/webbob-texting-onto-a777736-0420'
TIP = '9cfe54840bed5cb0ca7f2e94db7ef6596b014cf7'
PREVIOUS = 'a777736b3f0a37c82b0c4c62be8c91117c4c9881'
PR = json.loads((REVIEWS / 'TEXTING-CLEAN-MERGE-0810.json').read_text())['draft_pr']
RUNNER = REVIEWS / 'deploy_texting_0810.py'
REPORT = REVIEWS / 'TEXTING-DEPLOY-0810.md'
os.umask(0o077)
if REPORT.exists():
    raise SystemExit('Refusing to overwrite an existing final 0810 report')

def version():
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open('http://127.0.0.1:8787/api/version', timeout=15) as response:
        return json.load(response)

def read(path):
    return json.loads(path.read_text()) if path.exists() else {}

attempt = 1
while (REVIEWS / f'WEBBOB-TEXTING-DEPLOYMENT-0927-attempt{attempt}.json').exists():
    attempt += 1
record = REVIEWS / f'WEBBOB-TEXTING-DEPLOYMENT-0927-attempt{attempt}.json'
before = read(REVIEWS / 'TEXTING-DEPLOY-0810.preflight.json').get('live_before', {})
after, evidence, failure = {}, {}, ''
exit_code = 1
command = [sys.executable, '-u', str(RUNNER), '--root', str(ROOT), '--candidate', str(WT),
           '--draft-pr', PR, '--expected-live', 'a777736', '--attempt', str(attempt), '--timeout', '1800']
print('START=' + datetime.now(timezone.utc).isoformat(), flush=True)
print('PR=' + PR + ' attempt=' + str(attempt), flush=True)
try:
    before = version()
    print('live before: ' + json.dumps(before), flush=True)
    result = subprocess.run(command, cwd=WT / 'webchat', timeout=1920)
    exit_code = result.returncode
    evidence = read(record)
    after = version()
    if exit_code or not evidence.get('all_pass') or after.get('sha') != TIP:
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
    evidence['wrapper_failure'] = failure
    evidence['rollback_version_verified'] = after.get('sha') == PREVIOUS
    if record.exists():
        temporary = record.with_suffix('.wrapper.tmp')
        temporary.write_text(json.dumps(evidence, indent=2) + '\n')
        temporary.replace(record)

passed = exit_code == 0 and evidence.get('all_pass') and after.get('sha') == TIP
result = 'LIVE_PASS' if passed else 'FAIL_OR_ROLLBACK'
finished = datetime.now().astimezone().isoformat()
clean = read(REVIEWS / 'TEXTING-CLEAN-MERGE-0810.json')
lines = [
    '# TEXTING-DEPLOY-0810', '',
    f'exit: {exit_code}', f'finished: {finished}', f'tip: {TIP}', f'draft_pr: {PR}',
    f'deploy_runner: {RUNNER}', f'attempt_slot: {attempt}', f'evidence: {record}',
    'clean_merge: ' + clean.get('merge_sha', 'not merged'),
    'clean_note: ' + clean.get('clean_note', 'unavailable'),
    'rollback_path: ' + str(evidence.get('rollback', 'not activated')),
    'rollback_verified: ' + str(evidence.get('rolled_back') or evidence.get('rollback_version_verified', False)),
    '', 'live before JSON:', '```json', json.dumps(before, indent=2), '```',
    '', 'live after JSON:', '```json', json.dumps(after, indent=2), '```',
    '', 'Validation: TEXTING-0810-tests.json and fresh TEXTING-LIVE-0810.md BOTH_PASS gate.',
    'Texting smoke: ' + ('PASS' if evidence.get('texting_smoke', {}).get('all_pass') else 'not passed'),
    'Live replay: ' + str(sum(len(s.get('exchanges', [])) for s in evidence.get('sessions', []))) +
        ' captured turns; ' + str(sum(x.get('pass_check', False) for s in evidence.get('sessions', []) for x in s.get('exchanges', []))) + ' passed turns; ' + str(len(evidence.get('started_jobs', []))) + ' executed jobs.',
    'No Grok/xAI, force-push, notifications, or real texting delivery requests were used.',
]
if failure:
    lines.extend(['', 'Failure: ' + failure])
lines.extend(['', 'RESULT: ' + result, ''])
if passed:
    (REVIEWS / 'TEXTING-LIVE-PASS-0810.md').write_text(
        '# TEXTING-LIVE-PASS-0810\n\nfinished: ' + finished + '\nnew live short SHA: 9cfe548\nfull SHA: ' + TIP +
        '\ndraft_pr: ' + PR + '\nevidence: ' + str(record) + '\nreport: TEXTING-DEPLOY-0810.md\n\nRESULT: LIVE_PASS\n')
temporary = REPORT.with_suffix('.md.tmp')
temporary.write_text('\n'.join(lines))
temporary.replace(REPORT)
print('RESULT: ' + result, flush=True)
print('LIVE_SHA: ' + str(after.get('short_sha', 'unknown')), flush=True)
print('REPORT: ' + str(REPORT), flush=True)
raise SystemExit(0 if passed else 1)
