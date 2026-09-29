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
WT=ROOT/'workspaces/webbob-texting-onto-a777736-0420'
REVIEWS=ROOT/'conductor/reviews'
os.environ['BOB_ROOT']=str(ROOT)
os.umask(0o077)
sys.path.insert(0,str(WT/'services'))
from review_transport_1035 import ask_verdict
from api_tasks import MODELS

def git(*args):
    return subprocess.check_output(['git','-C',str(WT),*args],text=True).strip()

sha=git('rev-parse','HEAD')
assert not git('status','--porcelain')
tests=json.loads((REVIEWS/'TEXTING-0916-tests.json').read_text())
assert tests['sha']==sha and tests['all_pass']
slot=2
while True:
    reservation=REVIEWS/f'TEXTING-LIVE-{sha[:7]}-0916-attempt{slot}.reserved'
    try:
        with reservation.open('x') as out:
            out.write(datetime.now(timezone.utc).isoformat()+'\n')
        break
    except FileExistsError:
        slot+=1
header=f'''Perform a fresh LIVE API code/release review of Web Bob tip {sha}, branch draft/webbob-texting-diagdump-fix-0916, attempt {slot}.
This is a new review; do not reuse previous verdicts. Review supplied exact code and test evidence. You have no tools; do not claim you ran tests or inspected live yourself.

Authoritative failure: 9cfe548 had BOTH_PASS but deployment attempt2 rolled back to a777736 because StoryBoard/Cursor job webchat-53ff7beab93c5adaad5c4177ec9b9e7f claimed an API install fix passed after only shared tests and prepare smoke, explicitly admitting API tests were not re-run. Its rejected answer is captured in the new regression fixture. Old 9cfe548 reviews do not authorize this release.
Requirement: coding jobs must finish relevant application/project checks on their final commit before acceptance/publication; no empty promises or earlier test claims. Preserve the prior 0810 casual-status fix: short natural status, no missing-model placeholders, queue_counts, job-runner internals, or semicolon worker inventories. Preserve texting consent/privacy, exact saved observations, draft-only publication and verified rollback.
Implementation extends existing dispatch_worker, result_acceptance and mini_worker; no new orchestrator. Coding worker/reviewer share an explicit fresh-verification contract. Server collects the actual committed diff and test definitions for the existing reviewer. Explicit incomplete verification is a deterministic reject. The existing local CPU test runner re-runs fixed Web Bob webchat/API/services/evals or StoryBoard's documented typecheck/lint/test/build/manager:eval commands, records output hashes and SHA, and refuses failure/unavailable commands or checkout drift. Other projects retain task/diff-aware semantic acceptance.
The CPU runner uses the existing Mini isolated data root and credential-stripped environment; the full Web Bob services suite tests sandbox-exec itself, which macOS cannot nest. Assess this boundary explicitly. No arbitrary worker-proposed command list is executed. Tests use isolated fixtures, not real providers.
No changes to media/voice/UI/Instinct, no Grok/xAI, force-push or Jeff messages/texts. Release runner requires exact fresh review/test SHA, log hashes, draft PR and identical clean-merge tree. It snapshots rollback, checks texting smoke, both regressions, all 19 frozen replay turns and actual completed jobs with committed validation. Any failure rolls back to a777736 and verifies local/public versions.
Assess actual blocking defects with concrete symbols/examples. Output exactly one line and nothing else: VERDICT: PASS or VERDICT: FAIL.
'''
parts=[header, '\n## Validation report\n'+(REVIEWS/'TEXTING-FIXED-0916.md').read_text(),
       '\n## Exact diff from failed 9cfe548\n'+git('diff','9cfe548',sha)]
for name in ('services/dispatch_worker.py','services/mini_worker.py','services/result_acceptance.py',
             'services/api_worker.py','services/workspaces.py','webchat/test_texting_diagdump.py'):
    parts.append('\n## '+name+'\n'+(WT/name).read_text())
parts.append('\n## Release runner\n'+(REVIEWS/'deploy_texting_0916.py').read_text())
parts.append('\n## Guard test results\n'+(REVIEWS/'TEXTING-0916-deploy-guard-tests.txt').read_text())
context='\n'.join(parts)
context_path=REVIEWS/f'TEXTING-LIVE-{sha[:7]}-0916-attempt{slot}.context.md'
context_path.write_text(context)
context_hash=hashlib.sha256(context.encode()).hexdigest()
print(f'START LIVE reviews tip={sha} attempt={slot} context_bytes={len(context.encode())}',flush=True)

def review(lane):
    output=REVIEWS/f'LIVE-{lane.upper()}-draft_webbob-texting-diagdump-fix-0916-{sha[:7]}-0916-attempt{slot}.md'
    assert not output.exists()
    meta=dict(sha=sha,provider=lane,model=MODELS[lane],attempt=slot,started_at=datetime.now(timezone.utc).isoformat(),context=str(context_path),context_sha256=context_hash,output=str(output),exit=1,verdict='FAIL')
    meta['transport_receipts']=[]
    meta['review_transport_sha256']=hashlib.sha256((REVIEWS/'review_transport_1035.py').read_bytes()).hexdigest()
    try:
        answer=ask_verdict(lane,context,purpose='webbob-code-review-0916',timeout=600,receipts=meta['transport_receipts'])
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
path=REVIEWS/f'TEXTING-LIVE-{sha[:7]}-0916-attempt{slot}.json'
path.write_text(json.dumps(record,indent=2)+'\n')
(REVIEWS/'TEXTING-LIVE-0916.json').write_text(path.read_text())
report=f'# Fresh LIVE texting reviews 0916\n\ntip: {sha}\nattempt_slot: {slot}\ncontext: {context_path}\ncontext_sha256: {context_hash}\n\n'
for lane,meta in reviews.items():
    report+=f'{lane}: {meta["model"]} — VERDICT: {meta["verdict"]}\noutput: {meta["output"]}\nstarted: {meta["started_at"]}\nfinished: {meta["finished_at"]}\n\n'
report+=f'GATE: {gate} tip={sha[:7]}\n'
(REVIEWS/'TEXTING-LIVE-0916.md').write_text(report)
print(report,flush=True)
raise SystemExit(0 if gate=='BOTH_PASS' else 1)
