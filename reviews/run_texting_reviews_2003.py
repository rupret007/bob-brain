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
WT=ROOT/'workspaces/webbob-texting-disk-evidence-2003'
REVIEWS=ROOT/'conductor/reviews'
os.environ['BOB_ROOT']=str(ROOT)
os.umask(0o077)
sys.path[:0]=[str(WT/name) for name in ('webchat','services','state','reviews')]
sys.path.append(str(REVIEWS))
from review_transport_1035 import ask_verdict
from api_tasks import MODELS
from texting_deploy_record import atomic_json, atomic_text, require_disk_space

def git(*args):
    return subprocess.check_output(['git','-C',str(WT),*args],text=True).strip()

require_disk_space(ROOT, WT, 'LIVE_REVIEW')
sha=git('rev-parse','HEAD')
assert not git('status','--porcelain')
tests=json.loads((REVIEWS/'TEXTING-2003-tests.json').read_text())
assert tests['sha']==sha and tests['all_pass']
probe=json.loads((REVIEWS/'TEXTING-WORKER-2003.json').read_text())
assert probe['sha']==sha and probe['all_pass'] and len(probe['jobs'])==3 and probe['guard_contradiction_rejects']==0
assert probe['guard_consistency_job']['worker']=='gemini' and probe['guard_consistency_job']['status']=='succeeded'
for job in probe['jobs']:
    assert job['worker']=='minimax' and job['model']=='MiniMax-M2.7' and job['status']=='succeeded'
    assert job['acceptance']['accepted'] is True
    assert hashlib.sha256(job['result'].encode()).hexdigest()==job['result_sha256']
    assert Path(job['result_path']).read_text().strip()==job['result'].strip()
slot=13
while True:
    if any(REVIEWS.glob(f"TEXTING-LIVE-*-*-attempt{slot}.reserved")) or (REVIEWS/f"WEBBOB-TEXTING-DEPLOYMENT-0927-attempt{slot}.json").exists():
        slot+=1
        continue
    reservation=REVIEWS/f'TEXTING-LIVE-{sha[:7]}-2003-attempt{slot}.reserved'
    try:
        with reservation.open('x') as out:
            out.write(datetime.now(timezone.utc).isoformat()+'\n')
        break
    except FileExistsError:
        slot+=1
header=f'''Perform a fresh LIVE API code/release review of Web Bob tip {sha}, branch draft/webbob-texting-disk-evidence-fix-2003, attempt {slot}.
Review the supplied exact code and receipts. You have no tools; do not claim you ran tests or inspected live yourself. Prior approvals do not authorize this new tip.

Authoritative failure: TEXTING-DEPLOY-1901 attempt12 activated tip 8260f80 and passed texting smoke, 19 turns, three named MiniMax jobs, and the 1803 guard capture. At LIVE_REPLAY deploy_texting_1901.py:565 called save():291, then texting_deploy_record.py:13 exhausted Data while writing the temporary next to the attempt12 JSON. Repeated queue/status observations made that retained checkpoint 4,863,559 bytes. The runner's failure save at :644 and parent's :157 save ran before their rollback calls and failed too. An agent invoked the prepared rollback.sh; local/public returned to a777736. This proves the write path and recovery ordering; it does not identify every historical consumer of Data disk capacity.
Scope: only deployment/review scripts and regression tests under reviews/ change. Product source under webchat/, services/, state/ is byte-for-byte identical to 8260f80. All completion JSON, Action/Unblock, outer regression drafts, literal guard Expected, Findings/limits and report_repository worktree=None contracts remain.
Fix: exact byte free-space floor 5 GiB on Data and evidence/workspace/staging volumes before activation and every live checkpoint. Stream compact bounded JSON (1 MiB hard cap) via same-volume /private/tmp and atomic publication; retain hashes, identities, gate outcomes and saved session/report paths without repeating full queue/context snapshots. Small rollback journal publishes conversation IDs before jobs can be queued. Preallocate a 64 MiB physical-block recovery reserve plus a tiny fail-closed marker. On checkpoint/final publication I/O error, release recovery space, cancel claims and restore a777736 BEFORE attempting failure evidence. Cancellation errors cannot suppress service restoration. Parent recovery reads are best-effort, never require log writes, and final JSON/markdown publication is inside the recovery-protected block. Parent knows the planned rollback path before launching the child. Failure publication can fall back to the preallocated tiny marker. /private/tmp is NOT treated as additional capacity; its volume is checked and rename stays on one filesystem. Existing supervisor lock, durable service screen protections, matching draft/remote head, equal-tree clean ancestry, own-lane allowance and rejection of other Web Bob lanes remain. Both service pins and mandatory authenticated local/public full SHA match before smoke/replay; final SHA is rechecked. All 19 turns and every dispatched job must still finish and pass original acceptance, saved hashes and coding validation. No LIVE_PASS is possible just because the 19 turns passed.
Gates: fresh exact-tip full offline webchat/services/evals/browser plus release guard tests; real private-queue MiniMax 20bfc6f, f2c47c4c and 1035/dd47c4cb probes plus exact 1803 Gemini guard-consistency probe; saved/accepted result hashes; fresh cross-vendor BOTH_PASS. A matching draft PR and equal-tree regular clean merge are checked before activation, after this review. Attempt13+ is exclusively reserved. One activation runs texting smoke, 19 frozen turns, exact named MiniMax live jobs, acceptance/saved hashes and existing coding evidence checks. No claim of LIVE_PASS is made before those finish. Review the supplied runner AND launcher, not just the product. Mocks in deployment guard tests isolate services and test failure paths; they are not live evidence. Actual provider probes below are separate.
No gaps/media/voice/UI/Instinct deployment, Grok/xAI, force-push, Jeff notifications or real SMS/iMessage. Assess concrete blocking defects. Output exactly one line and nothing else: VERDICT: PASS or VERDICT: FAIL.
'''
parts=[header, '\n## Validation report\n'+(REVIEWS/'TEXTING-FIXED-2003.md').read_text(),
       '\n## Exact diff from 8260f80\n'+git('diff','8260f80',sha)]
for name in ('services/dispatch_worker.py','services/mini_worker.py','services/result_acceptance.py',
             'services/api_worker.py','services/worker.py','services/test_replay_completion.py','services/test_action_plan.py','services/test_regression_drafts.py','services/test_guard_consistency.py','services/fixtures/texting_guard_consistency_1803.json','services/fixtures/texting_regression_control_1658.json','services/fixtures/texting_regression_drafts_1658.json','services/fixtures/texting_action_plan_control_1605.json','services/fixtures/texting_action_plan_1605.json','services/fixtures/texting_jobcompletion_1403.json','services/workspaces.py','webchat/worker_assignment.py','webchat/test_texting_diagdump.py'):
    parts.append('\n## '+name+'\n'+(WT/name).read_text())
for receipt in ('TEXTING-2003-tests.json', 'TEXTING-2003-runner-checks.json', 'TEXTING-2003-probe-assertion-audit.json'):
    parts.append('\n## '+receipt+'\n'+(REVIEWS/receipt).read_text())
parts.append('\n## Live worker probe\n'+(REVIEWS/'TEXTING-WORKER-2003.json').read_text())
for name in ('deploy_texting_2003.py','record_texting_deploy_2003.py','texting_deploy_record.py','test_record_texting_deploy_2003.py','test_disk_evidence_2003.py'):
    parts.append('\n## Release script '+name+'\n'+(WT/'reviews'/name).read_text())
parts.append('\n## Original attempt12 traceback\n'+(REVIEWS/'TEXTING-1901-attempt12-deployment.log').read_text())
parts.append('\n## Guard test results\n'+(REVIEWS/'TEXTING-2003-deploy-guard-tests.txt').read_text())
context='\n'.join(parts)
context_path=REVIEWS/f'TEXTING-LIVE-{sha[:7]}-2003-attempt{slot}.context.md'
atomic_text(context_path, context)
context_hash=hashlib.sha256(context.encode()).hexdigest()
print(f'START LIVE reviews tip={sha} attempt={slot} context_bytes={len(context.encode())}',flush=True)

def review(lane):
    output=REVIEWS/f'LIVE-{lane.upper()}-draft_webbob-texting-disk-evidence-fix-2003-{sha[:7]}-2003-attempt{slot}.md'
    assert not output.exists()
    meta=dict(sha=sha,provider=lane,model=MODELS[lane],attempt=slot,started_at=datetime.now(timezone.utc).isoformat(),context=str(context_path),context_sha256=context_hash,output=str(output),exit=1,verdict='FAIL')
    meta['transport_receipts']=[]
    meta['review_transport_sha256']=hashlib.sha256((REVIEWS/'review_transport_1035.py').read_bytes()).hexdigest()
    try:
        answer=ask_verdict(lane,context,purpose='webbob-code-review-2003',timeout=600,receipts=meta['transport_receipts'])
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
path=REVIEWS/f'TEXTING-LIVE-{sha[:7]}-2003-attempt{slot}.json'
path.write_text(json.dumps(record,indent=2)+'\n')
(REVIEWS/'TEXTING-LIVE-2003.json').write_text(path.read_text())
report=f'# Fresh LIVE texting reviews 2003\n\ntip: {sha}\nattempt_slot: {slot}\ncontext: {context_path}\ncontext_sha256: {context_hash}\n\n'
for lane,meta in reviews.items():
    report+=f'{lane}: {meta["model"]} — VERDICT: {meta["verdict"]}\noutput: {meta["output"]}\nstarted: {meta["started_at"]}\nfinished: {meta["finished_at"]}\n\n'
report+=f'GATE: {gate} tip={sha[:7]}\n'
(REVIEWS/'TEXTING-LIVE-2003.md').write_text(report)
print(report,flush=True)
raise SystemExit(0 if gate=='BOTH_PASS' else 1)
