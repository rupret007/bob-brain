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
WT=ROOT/'workspaces/webbob-texting-action-plan-1605'
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
tests=json.loads((REVIEWS/'TEXTING-1605-tests.json').read_text())
assert tests['sha']==sha and tests['all_pass']
probe=json.loads((REVIEWS/'TEXTING-WORKER-1605.json').read_text())
assert probe['sha']==sha and probe['all_pass']
for job in probe['jobs']:
    assert job['worker']=='minimax' and job['model']=='MiniMax-M2.7' and job['status']=='succeeded'
    assert job['acceptance']['accepted'] is True
    assert hashlib.sha256(job['result'].encode()).hexdigest()==job['result_sha256']
    assert Path(job['result_path']).read_text().strip()==job['result'].strip()
slot=9
while True:
    if any(REVIEWS.glob(f"TEXTING-LIVE-*-*-attempt{slot}.reserved")):
        slot+=1
        continue
    reservation=REVIEWS/f'TEXTING-LIVE-{sha[:7]}-1605-attempt{slot}.reserved'
    try:
        with reservation.open('x') as out:
            out.write(datetime.now(timezone.utc).isoformat()+'\n')
        break
    except FileExistsError:
        slot+=1
header=f'''Perform a fresh LIVE API code/release review of Web Bob tip {sha}, branch draft/webbob-texting-action-plan-fix-1605, attempt {slot}.
Review the supplied exact code and receipts. You have no tools; do not claim you ran tests or inspected live yourself. Prior approvals do not authorize this new tip.

Authoritative failure: deployment attempt8 at 2cd1006 rolled back to a777736. MiniMax job webchat-f2c47c4c66fd5163b806595b146cb5b0 failed deterministic acceptance: Missing actionable action plan (change, validation and exit condition required). Its Action plan heading and Change label were embedded in an escaped Setup fixture, not outer report lines. The exact prompt and rejected_result are captured in services/fixtures/texting_action_plan_1605.json. 1035/dd47c4cb also must pass the deploy gate with an accepted saved report.
Requirement: all workers must receive literal Action plan/Unblock plan headings and nonempty same-line Change, Validation and Exit condition fields when required. Drafts and nested fixture plans cannot replace the outer plan. Preserve strict fail-closed acceptance, completion accepted/reason JSON, Findings/limits, Target/Setup/Action/Expected drafts, report_repository unavailable-worktree=None behavior and independent semantic review. No fabricated plan or automatic task retry may turn a rejected answer into success.
Regression reports now request a structured JSON transport envelope on dispatch and legacy worker paths. The worker must supply all draft, plan, completion and findings values. api_worker.render_report formats those values into the existing Markdown report and fenced accepted/reason block before unchanged deterministic and independent semantic checks. It rejects missing plan content, empty/wrong-type fields, unknown envelope fields and duplicate JSON keys; it invents no content and performs no retry. Nested input newlines are escaped so they cannot become outer labels. Already-valid Markdown remains supported under the same gates. The shared worker contract also supplies the literal outer plan template and a self-check; current assignments explicitly request it. Bounded MiniMax evidence includes the captured failure and a complete grounded layout, preserving complete deterministic guards and the 1035 fixture. An initial real probe produced the outer plan but failed closed on invalid reviewer JSON. A later probe also exposed the reviewer confusing a historical fixture error with the current report. Current task/answer data now follows the bounded evidence, with explicit instructions to judge only top-level payload.answer. The valid unescaped layout is the last source example. A captured 1035 probe was falsely rejected for placing a control report inside a literal input string; an AST/literal-evaluation regression proves its two inputs have the stated failure/control behavior. Reviewer instructions distinguish valid inner fixture sections from mandatory outer report sections without relaxing either gate. Worker-output instructions now live as data in payload.worker_output_contract, separate from reviewer verdict instructions; tests enforce that distinction. Receipts for the initial failed tip are retained and do not authorize this candidate.
Fresh exact-tip offline tests, real MiniMax probes of both historical assignments, and isolated deploy guards are supplied. A probe pass is not a deployment pass. The 1605 runner is directly adapted from 1508, retaining clean-branch ancestry/refetch and durable-svc-peers-1403 screen isolation. Deployment requires this fresh Gemini/MiniMax BOTH_PASS, exact-tip offline receipts, draft PR plus equal-tree regular clean merge, a fresh rollback, texting smoke, all 19 frozen turns, and exact 1035/dd47c4cb plus f2c47c4c MiniMax tasks with actual accepted saved deliverables and verified hashes. Only attempt9+ is allowed. Any failure revokes both regression conversations and all replay claims, restores a777736 and verifies local/public version.
No gaps/media/voice/UI/Instinct deployment, Grok/xAI, force-push, Jeff notifications or real SMS/iMessage. Assess actual blocking defects with concrete symbols/examples. Output exactly one line and nothing else: VERDICT: PASS or VERDICT: FAIL.
'''
parts=[header, '\n## Validation report\n'+(REVIEWS/'TEXTING-FIXED-1605.md').read_text(),
       '\n## Exact diff from failed 2cd1006\n'+git('diff','2cd1006',sha)]
for name in ('services/dispatch_worker.py','services/mini_worker.py','services/result_acceptance.py',
             'services/api_worker.py','services/worker.py','services/test_replay_completion.py','services/test_action_plan.py','services/fixtures/texting_action_plan_control_1605.json','services/fixtures/texting_action_plan_1605.json','services/fixtures/texting_jobcompletion_1403.json','services/workspaces.py','webchat/worker_assignment.py','webchat/test_texting_diagdump.py'):
    parts.append('\n## '+name+'\n'+(WT/name).read_text())
parts.append('\n## Live worker probe\n'+(REVIEWS/'TEXTING-WORKER-1605.json').read_text())
parts.append('\n## Release runner\n'+(REVIEWS/'deploy_texting_1605.py').read_text())
parts.append('\n## Guard test results\n'+(REVIEWS/'TEXTING-1605-deploy-guard-tests.txt').read_text())
context='\n'.join(parts)
context_path=REVIEWS/f'TEXTING-LIVE-{sha[:7]}-1605-attempt{slot}.context.md'
context_path.write_text(context)
context_hash=hashlib.sha256(context.encode()).hexdigest()
print(f'START LIVE reviews tip={sha} attempt={slot} context_bytes={len(context.encode())}',flush=True)

def review(lane):
    output=REVIEWS/f'LIVE-{lane.upper()}-draft_webbob-texting-action-plan-fix-1605-{sha[:7]}-1605-attempt{slot}.md'
    assert not output.exists()
    meta=dict(sha=sha,provider=lane,model=MODELS[lane],attempt=slot,started_at=datetime.now(timezone.utc).isoformat(),context=str(context_path),context_sha256=context_hash,output=str(output),exit=1,verdict='FAIL')
    meta['transport_receipts']=[]
    meta['review_transport_sha256']=hashlib.sha256((REVIEWS/'review_transport_1035.py').read_bytes()).hexdigest()
    try:
        answer=ask_verdict(lane,context,purpose='webbob-code-review-1605',timeout=600,receipts=meta['transport_receipts'])
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
path=REVIEWS/f'TEXTING-LIVE-{sha[:7]}-1605-attempt{slot}.json'
path.write_text(json.dumps(record,indent=2)+'\n')
(REVIEWS/'TEXTING-LIVE-1605.json').write_text(path.read_text())
report=f'# Fresh LIVE texting reviews 1605\n\ntip: {sha}\nattempt_slot: {slot}\ncontext: {context_path}\ncontext_sha256: {context_hash}\n\n'
for lane,meta in reviews.items():
    report+=f'{lane}: {meta["model"]} — VERDICT: {meta["verdict"]}\noutput: {meta["output"]}\nstarted: {meta["started_at"]}\nfinished: {meta["finished_at"]}\n\n'
report+=f'GATE: {gate} tip={sha[:7]}\n'
(REVIEWS/'TEXTING-LIVE-1605.md').write_text(report)
print(report,flush=True)
raise SystemExit(0 if gate=='BOTH_PASS' else 1)
