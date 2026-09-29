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
WT=ROOT/'workspaces/webbob-texting-guard-consistency-1803'
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
tests=json.loads((REVIEWS/'TEXTING-1803-tests.json').read_text())
assert tests['sha']==sha and tests['all_pass']
probe=json.loads((REVIEWS/'TEXTING-WORKER-1803.json').read_text())
assert probe['sha']==sha and probe['all_pass'] and len(probe['jobs'])==3 and probe['guard_contradiction_rejects']==0
assert probe['guard_consistency_job']['worker']=='gemini' and probe['guard_consistency_job']['status']=='succeeded'
for job in probe['jobs']:
    assert job['worker']=='minimax' and job['model']=='MiniMax-M2.7' and job['status']=='succeeded'
    assert job['acceptance']['accepted'] is True
    assert hashlib.sha256(job['result'].encode()).hexdigest()==job['result_sha256']
    assert Path(job['result_path']).read_text().strip()==job['result'].strip()
slot=11
while True:
    if any(REVIEWS.glob(f"TEXTING-LIVE-*-*-attempt{slot}.reserved")) or (REVIEWS/f"WEBBOB-TEXTING-DEPLOYMENT-0927-attempt{slot}.json").exists():
        slot+=1
        continue
    reservation=REVIEWS/f'TEXTING-LIVE-{sha[:7]}-1803-attempt{slot}.reserved'
    try:
        with reservation.open('x') as out:
            out.write(datetime.now(timezone.utc).isoformat()+'\n')
        break
    except FileExistsError:
        slot+=1
header=f'''Perform a fresh LIVE API code/release review of Web Bob tip {sha}, branch draft/webbob-texting-guard-consistency-fix-1803, attempt {slot}.
Review the supplied exact code and receipts. You have no tools; do not claim you ran tests or inspected live yourself. Prior approvals do not authorize this new tip.

Authoritative failure: TEXTING-DEPLOY-1658 attempt10 on d32d0f7 rolled back to a777736. Gemini job webchat-8e7eee346e1d51099fdf99d23fe7c353 called check_completion_json with answer='Findings only.' and an outer Expected of returns None. The guard actually raised Missing or ambiguous required completion JSON output block. It tried to test a false control by making the outer draft itself false, instead of calling the auditor on a nested false draft.
Requirements: regression draft outcomes must match literal guards exactly, including the actual ResultRejected text. Keep the two complete OUTER regression cases, Action/Unblock plans, fenced accepted/reason completion JSON, Findings/limits, independent semantic acceptance, report_repository worktree=None, ancestry/refetch and durable-svc-peers-1403 policy. Never repair contradictory worker output into success.
Change: a shared pure-guard outcome helper derives canonical examples and the final report schema from the running check_completion_json. Evidence reports disclose regenerated fixture fields. Structured direct-guard cases may explicitly supply expected={{"guard_outcome":"pass"}} or expected={{"guard_outcome":"reject"}}. The renderer evaluates known pure guards on supplied literal inputs, rejects a wrong mode, and only then derives the exact Expected string from the guard result. This is an explicit expectation specification, not repairing contradictory prose or adding a missing field; absent/unknown specs and missing/nonliteral inputs fail closed. Existing text expectations retain exact error checking. Workers are instructed to use the supplied narrow completion pair for dispatch/completion assignments, keep deliberately false test data inside Setup, and have Expected describe the actual Action. The literal audit now compares the claimed quoted ResultRejected message exactly, also rejecting vague outcomes, pass/reject mismatches, and unresolvable direct guard inputs. It parses literal data only, never executes model code. Markdown label variants accepted by the outer-draft parser get the same audit. Structured reports are audited at render time, with the same final acceptance check still applied before review/publication.
The exact prompt, rejected answer/control, contradiction error and artifact hashes are captured in services/fixtures/texting_guard_consistency_1803.json. Focused tests cover missing/ambiguous JSON, paraphrases/wrong error classes, truthful rejection and pass controls, every worker's save/hash path, and prior outer draft/plan contracts. A first exploratory probe on 6869354 passed all three MiniMax jobs but Gemini proposed an incomplete nested check_deliverables control; it failed closed before review/save. That exact additional capture is retained and excluded from release evidence. The final typed-outcome candidate must pass fresh probes. Bounded snapshot allocation also preserves the existing named build/assignment and source-selector evidence coverage tests under the 64000-byte budget. All offline suites and 125 eval cases must pass on this tip. Three fresh real MiniMax jobs replay 20bfc6f, f2c47c4c Action plan and 1035/dd47c4cb completion; an additional real Gemini job replays the exact 8e7eee34 prompt. All must have accepted saved deliverables, verified hashes and zero guard-contradiction rejects.
The runner/wrapper are adapted from deploy_texting_1658.py, preserving the ancestry fix and durable service screen policy. Attempt11+ requires exact-tip offline and probe receipts, fresh Gemini/MiniMax BOTH_PASS, a draft PR and an equal-tree regular clean merge. One activation takes a fresh rollback, runs texting smoke, all 19 frozen turns and the three named MiniMax regressions. Every result must complete and save with deterministic/semantic acceptance and verified hashes. Any failure revokes replay claims, restores a777736 and verifies local/public versions.
No gaps/media/voice/UI/Instinct deployment, Grok/xAI, force-push, Jeff notifications or real SMS/iMessage. Assess concrete blocking defects. Output exactly one line and nothing else: VERDICT: PASS or VERDICT: FAIL.
'''
parts=[header, '\n## Validation report\n'+(REVIEWS/'TEXTING-FIXED-1803.md').read_text(),
       '\n## Exact diff from failed d32d0f7\n'+git('diff','d32d0f7',sha)]
for name in ('services/dispatch_worker.py','services/mini_worker.py','services/result_acceptance.py',
             'services/api_worker.py','services/worker.py','services/test_replay_completion.py','services/test_action_plan.py','services/test_regression_drafts.py','services/test_guard_consistency.py','services/fixtures/texting_guard_consistency_1803.json','services/fixtures/texting_regression_control_1658.json','services/fixtures/texting_regression_drafts_1658.json','services/fixtures/texting_action_plan_control_1605.json','services/fixtures/texting_action_plan_1605.json','services/fixtures/texting_jobcompletion_1403.json','services/workspaces.py','webchat/worker_assignment.py','webchat/test_texting_diagdump.py'):
    parts.append('\n## '+name+'\n'+(WT/name).read_text())
for receipt in ('TEXTING-1803-tests.json', 'TEXTING-1803-runner-checks.json', 'TEXTING-1803-probe-assertion-audit.json'):
    parts.append('\n## '+receipt+'\n'+(REVIEWS/receipt).read_text())
parts.append('\n## Live worker probe\n'+(REVIEWS/'TEXTING-WORKER-1803.json').read_text())
parts.append('\n## Release runner\n'+(REVIEWS/'deploy_texting_1803.py').read_text())
parts.append('\n## Guard test results\n'+(REVIEWS/'TEXTING-1803-deploy-guard-tests.txt').read_text())
context='\n'.join(parts)
context_path=REVIEWS/f'TEXTING-LIVE-{sha[:7]}-1803-attempt{slot}.context.md'
context_path.write_text(context)
context_hash=hashlib.sha256(context.encode()).hexdigest()
print(f'START LIVE reviews tip={sha} attempt={slot} context_bytes={len(context.encode())}',flush=True)

def review(lane):
    output=REVIEWS/f'LIVE-{lane.upper()}-draft_webbob-texting-guard-consistency-fix-1803-{sha[:7]}-1803-attempt{slot}.md'
    assert not output.exists()
    meta=dict(sha=sha,provider=lane,model=MODELS[lane],attempt=slot,started_at=datetime.now(timezone.utc).isoformat(),context=str(context_path),context_sha256=context_hash,output=str(output),exit=1,verdict='FAIL')
    meta['transport_receipts']=[]
    meta['review_transport_sha256']=hashlib.sha256((REVIEWS/'review_transport_1035.py').read_bytes()).hexdigest()
    try:
        answer=ask_verdict(lane,context,purpose='webbob-code-review-1803',timeout=600,receipts=meta['transport_receipts'])
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
path=REVIEWS/f'TEXTING-LIVE-{sha[:7]}-1803-attempt{slot}.json'
path.write_text(json.dumps(record,indent=2)+'\n')
(REVIEWS/'TEXTING-LIVE-1803.json').write_text(path.read_text())
report=f'# Fresh LIVE texting reviews 1803\n\ntip: {sha}\nattempt_slot: {slot}\ncontext: {context_path}\ncontext_sha256: {context_hash}\n\n'
for lane,meta in reviews.items():
    report+=f'{lane}: {meta["model"]} — VERDICT: {meta["verdict"]}\noutput: {meta["output"]}\nstarted: {meta["started_at"]}\nfinished: {meta["finished_at"]}\n\n'
report+=f'GATE: {gate} tip={sha[:7]}\n'
(REVIEWS/'TEXTING-LIVE-1803.md').write_text(report)
print(report,flush=True)
raise SystemExit(0 if gate=='BOTH_PASS' else 1)
