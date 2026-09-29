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
WT=ROOT/'workspaces/webbob-texting-jobcomplete-1107'
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
tests=json.loads((REVIEWS/'TEXTING-1107-tests.json').read_text())
assert tests['sha']==sha and tests['all_pass']
slot=4
while True:
    if any(REVIEWS.glob(f"TEXTING-LIVE-*-*-attempt{slot}.reserved")):
        slot+=1
        continue
    reservation=REVIEWS/f'TEXTING-LIVE-{sha[:7]}-1107-attempt{slot}.reserved'
    try:
        with reservation.open('x') as out:
            out.write(datetime.now(timezone.utc).isoformat()+'\n')
        break
    except FileExistsError:
        slot+=1
header=f'''Perform a fresh LIVE API code/release review of Web Bob tip {sha}, branch draft/webbob-texting-jobcomplete-fix-1107, attempt {slot}.
This is a new review; do not reuse previous verdicts. Review supplied exact code and test evidence. You have no tools; do not claim you ran tests or inspected live yourself.

Authoritative failure: 1ca5e12 had BOTH_PASS but deployment attempt3 rolled back to a777736 because MiniMax job webchat-f4b8e359666155c6a06900f02b313c8c delivered architecture findings and search commands instead of regression test drafts and a concrete plan for Web Bob unblock 1035. This was a substantive completion failure, not empty transport or verdict parsing. Previous reviews do not authorize this tip.
Requirement: API and peer analysis/test-writing workers must deliver concrete regression cases with setup, action and assertions (or actual test code) and an actionable plan for a named unblock. Missing original lane context must be acknowledged without using that limit to omit the available deliverables. Preserve casual status voice and the 0810/0916 incomplete-verification rejection, truthful saved observations, texting consent/privacy, draft-only publication and verified rollback.
Implementation tightens the existing assignment prompt, shared result_acceptance contract, dispatch_worker and legacy API worker. It rejects missing drafts/plans before semantic acceptance; headings alone cannot replace that separate semantic review. Bounded repository snapshots now prioritize named files and test definitions so MiniMax gets relevant evidence. No new orchestration or acceptance retries were added.
Existing independent coding validation remains intact: fixed Web Bob webchat/API/services/evals or StoryBoard typecheck/lint/test/build/manager:eval commands, output hashes and final SHA. The CPU runner uses isolated BOB_ROOT and a credential-stripped environment; full services tests exercise sandbox-exec itself and cannot nest it.
No media/voice/UI/Instinct deployment, Grok/xAI, force-push, Jeff notifications or real SMS/iMessage sends. The release runner requires this exact tip's test/review receipts and an identical regular clean-merge tree, creates a fresh rollback, checks texting smoke, all prior regressions and 19 frozen live turns, replays the exact captured 1035 MiniMax task as an additional real job, and requires all jobs to succeed with saved deliverables. Any failure revokes replay claims and verifies local/public rollback to a777736.
Assess actual blocking defects with concrete symbols/examples. Output exactly one line and nothing else: VERDICT: PASS or VERDICT: FAIL.
'''
parts=[header, '\n## Validation report\n'+(REVIEWS/'TEXTING-FIXED-1107.md').read_text(),
       '\n## Exact diff from failed 1ca5e12\n'+git('diff','1ca5e12',sha)]
for name in ('services/dispatch_worker.py','services/mini_worker.py','services/result_acceptance.py',
             'services/api_worker.py','services/worker.py','services/workspaces.py','webchat/worker_assignment.py','webchat/test_texting_diagdump.py'):
    parts.append('\n## '+name+'\n'+(WT/name).read_text())
parts.append('\n## Release runner\n'+(REVIEWS/'deploy_texting_1107.py').read_text())
parts.append('\n## Guard test results\n'+(REVIEWS/'TEXTING-1107-deploy-guard-tests.txt').read_text())
context='\n'.join(parts)
context_path=REVIEWS/f'TEXTING-LIVE-{sha[:7]}-1107-attempt{slot}.context.md'
context_path.write_text(context)
context_hash=hashlib.sha256(context.encode()).hexdigest()
print(f'START LIVE reviews tip={sha} attempt={slot} context_bytes={len(context.encode())}',flush=True)

def review(lane):
    output=REVIEWS/f'LIVE-{lane.upper()}-draft_webbob-texting-jobcomplete-fix-1107-{sha[:7]}-1107-attempt{slot}.md'
    assert not output.exists()
    meta=dict(sha=sha,provider=lane,model=MODELS[lane],attempt=slot,started_at=datetime.now(timezone.utc).isoformat(),context=str(context_path),context_sha256=context_hash,output=str(output),exit=1,verdict='FAIL')
    meta['transport_receipts']=[]
    meta['review_transport_sha256']=hashlib.sha256((REVIEWS/'review_transport_1035.py').read_bytes()).hexdigest()
    try:
        answer=ask_verdict(lane,context,purpose='webbob-code-review-1107',timeout=600,receipts=meta['transport_receipts'])
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
path=REVIEWS/f'TEXTING-LIVE-{sha[:7]}-1107-attempt{slot}.json'
path.write_text(json.dumps(record,indent=2)+'\n')
(REVIEWS/'TEXTING-LIVE-1107.json').write_text(path.read_text())
report=f'# Fresh LIVE texting reviews 1107\n\ntip: {sha}\nattempt_slot: {slot}\ncontext: {context_path}\ncontext_sha256: {context_hash}\n\n'
for lane,meta in reviews.items():
    report+=f'{lane}: {meta["model"]} — VERDICT: {meta["verdict"]}\noutput: {meta["output"]}\nstarted: {meta["started_at"]}\nfinished: {meta["finished_at"]}\n\n'
report+=f'GATE: {gate} tip={sha[:7]}\n'
(REVIEWS/'TEXTING-LIVE-1107.md').write_text(report)
print(report,flush=True)
raise SystemExit(0 if gate=='BOTH_PASS' else 1)
