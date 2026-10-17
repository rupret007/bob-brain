#!/usr/bin/env python3
"""Fresh metered cross-vendor reviews, with immutable per-attempt receipts."""
import concurrent.futures
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT=Path('/Users/jeffstory/Documents/bob-overnight-inject')
WT=ROOT/'workspaces/webbob-texting-smoke-replay-1901'
REVIEWS=ROOT/'conductor/reviews'
os.environ['BOB_ROOT']=str(ROOT)
os.umask(0o077)
sys.path[:0]=[str(WT/name) for name in ('webchat','services','state','reviews')]
sys.path.append(str(REVIEWS))
from review_transport_1035 import ask_verdict
from api_tasks import MODELS

def git(*args):
    return subprocess.check_output(['git','-C',str(WT),*args],text=True).strip()

sha=git('rev-parse','HEAD')
assert not git('status','--porcelain')
tests=json.loads((REVIEWS/'TEXTING-1901-tests.json').read_text())
assert tests['sha']==sha and tests['all_pass']
probe=json.loads((REVIEWS/'TEXTING-WORKER-1901.json').read_text())
assert probe['sha']==sha and probe['all_pass'] and len(probe['jobs'])==3 and probe['guard_contradiction_rejects']==0
assert probe['guard_consistency_job']['worker']=='gemini' and probe['guard_consistency_job']['status']=='succeeded'
for job in probe['jobs']:
    assert job['worker']=='minimax' and job['model']=='MiniMax-M2.7' and job['status']=='succeeded'
    assert job['acceptance']['accepted'] is True
    assert hashlib.sha256(job['result'].encode()).hexdigest()==job['result_sha256']
    assert Path(job['result_path']).read_text().strip()==job['result'].strip()
slot=12
while True:
    if any(REVIEWS.glob(f"TEXTING-LIVE-*-*-attempt{slot}.reserved")) or (REVIEWS/f"WEBBOB-TEXTING-DEPLOYMENT-0927-attempt{slot}.json").exists():
        slot+=1
        continue
    reservation=REVIEWS/f'TEXTING-LIVE-{sha[:7]}-1901-attempt{slot}.reserved'
    try:
        with reservation.open('x') as out:
            out.write(datetime.now(timezone.utc).isoformat()+'\n')
        break
    except FileExistsError:
        slot+=1
header=f'''Perform a fresh LIVE API code/release review of Web Bob tip {sha}, branch draft/webbob-texting-smoke-replay-fix-1901, attempt {slot}.
Review the supplied exact code and receipts. You have no tools; do not claim you ran tests or inspected live yourself. Prior approvals do not authorize this new tip.

Authoritative failure: TEXTING-DEPLOY-1803 attempt11 never activated. The parent launcher inherited PYTHONPATH=webchat:services:state, then launched the child with cwd=candidate/webchat. The child failed at import deploy_parity, before creating attempt11 evidence. The wrapper only wrote failure evidence if the file already existed, and replaced the useful exception with a generic marker. The owning lane was already allowlisted. Product tip 3b522c5 passed offline and BOTH_PASS but live stayed a777736.
Scope: only the existing deploy/review scripts and regression tests under reviews/ change. Product source under webchat/, services/, state/ is byte-for-byte identical to 3b522c5. All completion JSON, Action/Unblock, outer regression drafts, literal guard Expected, Findings/limits and report_repository worktree=None contracts remain.
Fix: the wrapper seeds a complete, exclusive, atomic attempt record before candidate imports or child startup, binds a run owner, gives the child absolute import paths, records combined child output/traceback, and writes a final marker for early failure too. The runner bootstraps modules from its own reviewed checkout. Existing supervisor-locked restart, durable-svc-peers-1403 policy, own-lane exception, other-lane rejection, exact draft/remote SHA and equal-tree clean ancestry checks remain. Both service pins and mandatory authenticated local/public full SHA must match the candidate before texting smoke or the 19 frozen live turns. The final full SHA is rechecked on both endpoints. All postactivation failures revoke replay claims and restore a fresh a777736 snapshot, verifying pins and both endpoints; the parent timeout/crash path independently recovers using the recorded snapshot. Failed preactivation runs leave the existing baseline untouched and verify both endpoints. Captured-turn counts only include actual replies, not the reserved frozen inputs.
Gates: fresh exact-tip full offline webchat/services/evals/browser plus release guard tests; real private-queue MiniMax 20bfc6f, f2c47c4c and 1035/dd47c4cb probes plus exact 1803 Gemini guard-consistency probe; saved/accepted result hashes; fresh cross-vendor BOTH_PASS. A matching draft PR and equal-tree regular clean merge are checked before activation, after this review. Attempt12+ is exclusively reserved. One activation runs texting smoke, 19 frozen turns, exact named MiniMax live jobs, acceptance/saved hashes and existing coding evidence checks. No claim of LIVE_PASS is made before those finish. Review the supplied runner AND launcher, not just the product. Mocks in deployment guard tests isolate services and test failure paths; they are not live evidence. Actual provider probes below are separate.
No gaps/media/voice/UI/Instinct deployment, Grok/xAI, force-push, Jeff notifications or real SMS/iMessage. Assess concrete blocking defects. Output exactly one line and nothing else: VERDICT: PASS or VERDICT: FAIL.
'''
parts=[header, '\n## Validation report\n'+(REVIEWS/'TEXTING-FIXED-1901.md').read_text(),
       '\n## Exact diff from 3b522c5\n'+git('diff','3b522c5',sha)]
for name in ('services/dispatch_worker.py','services/mini_worker.py','services/result_acceptance.py',
             'services/api_worker.py','services/worker.py','services/test_replay_completion.py','services/test_action_plan.py','services/test_regression_drafts.py','services/test_guard_consistency.py','services/fixtures/texting_guard_consistency_1803.json','services/fixtures/texting_regression_control_1658.json','services/fixtures/texting_regression_drafts_1658.json','services/fixtures/texting_action_plan_control_1605.json','services/fixtures/texting_action_plan_1605.json','services/fixtures/texting_jobcompletion_1403.json','services/workspaces.py','webchat/worker_assignment.py','webchat/test_texting_diagdump.py'):
    parts.append('\n## '+name+'\n'+(WT/name).read_text())
for receipt in ('TEXTING-1901-tests.json', 'TEXTING-1901-runner-checks.json', 'TEXTING-1901-probe-assertion-audit.json'):
    parts.append('\n## '+receipt+'\n'+(REVIEWS/receipt).read_text())
parts.append('\n## Live worker probe\n'+(REVIEWS/'TEXTING-WORKER-1901.json').read_text())
for name in ('deploy_texting_1901.py','record_texting_deploy_1901.py','texting_deploy_record.py','test_record_texting_deploy_1901.py'):
    parts.append('\n## Release script '+name+'\n'+(WT/'reviews'/name).read_text())
parts.append('\n## Original failure reproduction\n'+(REVIEWS/'TEXTING-1901-root-cause-repro.txt').read_text())
parts.append('\n## Guard test results\n'+(REVIEWS/'TEXTING-1901-deploy-guard-tests.txt').read_text())
context='\n'.join(parts)
context_path=REVIEWS/f'TEXTING-LIVE-{sha[:7]}-1901-attempt{slot}.context.md'
context_path.write_text(context)
context_hash=hashlib.sha256(context.encode()).hexdigest()
print(f'START LIVE reviews tip={sha} attempt={slot} context_bytes={len(context.encode())}',flush=True)

def review(lane):
    output=REVIEWS/f'LIVE-{lane.upper()}-draft_webbob-texting-smoke-replay-fix-1901-{sha[:7]}-1901-attempt{slot}.md'
    assert not output.exists()
    meta=dict(sha=sha,provider=lane,model=MODELS[lane],attempt=slot,started_at=datetime.now(timezone.utc).isoformat(),context=str(context_path),context_sha256=context_hash,output=str(output),exit=1,verdict='FAIL')
    meta['transport_receipts']=[]
    meta['review_transport_sha256']=hashlib.sha256((REVIEWS/'review_transport_1035.py').read_bytes()).hexdigest()
    try:
        answer=ask_verdict(lane,context,purpose='webbob-code-review-1901',timeout=600,receipts=meta['transport_receipts'])
        output.write_text(answer+'\n')
        verdicts=re.findall(r'^\s*\**VERDICT:\s*(PASS|FAIL|BLOCKED)\**\s*$',answer,re.M|re.I)
        meta.update(exit=0,verdict=verdicts[-1].upper() if len(verdicts)==1 else 'INVALID')
    except BaseException as exc:
        meta['error']=str(exc)
        output.write_text('LIVE REVIEW ERROR: '+type(exc).__name__+': '+str(exc)+'\n')
    meta.update(finished_at=datetime.now(timezone.utc).isoformat(),output_sha256=hashlib.sha256(output.read_bytes()).hexdigest())
    output.with_suffix('.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(meta),flush=True)
    return lane,meta

with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    reviews=dict(pool.map(review,('gemini','minimax')))
gate='BOTH_PASS' if all(x['exit']==0 and x['verdict']=='PASS' for x in reviews.values()) else 'NOT_BOTH_PASS'
assert git('rev-parse','HEAD')==sha and not git('status','--porcelain')
record=dict(sha=sha,attempt=slot,gate=gate,context_sha256=context_hash,reviews=reviews,finished_at=datetime.now(timezone.utc).isoformat())
path=REVIEWS/f'TEXTING-LIVE-{sha[:7]}-1901-attempt{slot}.json'
path.write_text(json.dumps(record,indent=2)+'\n')
(REVIEWS/'TEXTING-LIVE-1901.json').write_text(path.read_text())
report=f'# Fresh LIVE texting reviews 1901\n\ntip: {sha}\nattempt_slot: {slot}\ncontext: {context_path}\ncontext_sha256: {context_hash}\n\n'
for lane,meta in reviews.items():
    report+=f'{lane}: {meta["model"]} — VERDICT: {meta["verdict"]}\noutput: {meta["output"]}\nstarted: {meta["started_at"]}\nfinished: {meta["finished_at"]}\n\n'
report+=f'GATE: {gate} tip={sha[:7]}\n'
(REVIEWS/'TEXTING-LIVE-1901.md').write_text(report)
print(report,flush=True)
raise SystemExit(0 if gate=='BOTH_PASS' else 1)
