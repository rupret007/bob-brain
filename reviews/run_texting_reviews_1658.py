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
WT=ROOT/'workspaces/webbob-texting-regression-drafts-1658'
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
tests=json.loads((REVIEWS/'TEXTING-1658-tests.json').read_text())
assert tests['sha']==sha and tests['all_pass']
probe=json.loads((REVIEWS/'TEXTING-WORKER-1658.json').read_text())
assert probe['sha']==sha and probe['all_pass'] and len(probe['jobs'])==3
for job in probe['jobs']:
    assert job['worker']=='minimax' and job['model']=='MiniMax-M2.7' and job['status']=='succeeded'
    assert job['acceptance']['accepted'] is True
    assert hashlib.sha256(job['result'].encode()).hexdigest()==job['result_sha256']
    assert Path(job['result_path']).read_text().strip()==job['result'].strip()
slot=10
while True:
    if any(REVIEWS.glob(f"TEXTING-LIVE-*-*-attempt{slot}.reserved")) or (REVIEWS/f"WEBBOB-TEXTING-DEPLOYMENT-0927-attempt{slot}.json").exists():
        slot+=1
        continue
    reservation=REVIEWS/f'TEXTING-LIVE-{sha[:7]}-1658-attempt{slot}.reserved'
    try:
        with reservation.open('x') as out:
            out.write(datetime.now(timezone.utc).isoformat()+'\n')
        break
    except FileExistsError:
        slot+=1
header=f'''Perform a fresh LIVE API code/release review of Web Bob tip {sha}, branch draft/webbob-texting-regression-drafts-fix-1658, attempt {slot}.
Review the supplied exact code and receipts. You have no tools; do not claim you ran tests or inspected live yourself. Prior approvals do not authorize this new tip.

Authoritative failure: TEXTING-DEPLOY-1605 attempt9 on c6b3e79 rolled back to a777736. MiniMax job webchat-20bfc6f211c05e1f95221804051ff8a9 failed before publication with Missing concrete regression test drafts (setup, action and expected assertion required). Its Action/Expected labels appeared only in escaped Setup inputs. It ignored the requested structured transport in a prompt also showing repeated Markdown templates and a Markdown example.
Requirements: exactly two complete OUTER regression cases with same-line Target/Setup/Action/Expected plus the required Unblock/Action plan, accepted/reason JSON and Findings/limits. Retain prior completion and plan guards, report_repository unavailable-worktree=None behavior, independent semantic acceptance, ancestry/refetch and durable-svc-peers-1403 policy. Missing substantive content must fail closed; no fabricated fields or automatic task retry.
Change: use one structured output contract for both API and CLI report paths. The final example uses the same JSON envelope. A bounded source snapshot reserves the complete example, deterministic guards and source-selection tests. Workers supply every value; render_report materializes separate outer labels and escapes nested newlines. It now requires two fully populated cases and also supports test-writing reports without a plan using plan=null. Markdown compatibility faces a strengthened deterministic gate: both outer cases must be complete. Quoted, fenced, indented and escaped fixture labels cannot replace outer drafts. Historical 1035 answer/layout text is now omitted from production evidence, with rendered-field metadata disclosing the omission. A manual audit caught an accepted probe with an invalid one-case inner control; its exact capture and AST literal-input regression are retained, its receipt does not authorize this tip, and semantic reviewer instructions explicitly require the inner control to satisfy its own full contract. The historical 1605 inner control has only one case, so its exact capture is preserved and its test now expects rejection under the stronger pair contract.
Exact 20bfc6f task/rejected answer with hashes and artifact hashes are in services/fixtures/texting_regression_drafts_1658.json. Offline tests cover exact rejection before review, full accept/save paths, all five workers, nested history, missing fields and two-case enforcement. Evals include the new failure/control cases. A bounded literal-input audit also checks claimed success/rejection for check_completion_json and check_deliverables against those pure local guards. It parses literals with ast.literal_eval, never executes model code, and leaves nonliteral/mock-based drafts to independent semantic review. Two captured false controls (one missing inner sections, one using the serialization envelope as completion JSON) now fail before any positive review vote. Three fresh real MiniMax dispatch executions replay 20bfc6f, f2c47c4c Action plan and 1035/dd47c4cb completion, with accepted saved reports and verified hashes. A probe pass is not a deployment pass.
The 1658 runner is adapted directly from deploy_texting_1605.py. It requires exact-tip offline receipts and three probe receipts, fresh Gemini/MiniMax BOTH_PASS, draft PR with an equal-tree regular clean merge, and attempt10+. One activation takes a fresh rollback, runs texting smoke and all 19 frozen turns, plus three separate named MiniMax tasks. Every result must complete with deterministic/semantic acceptance, saved deliverables and matching hashes. Any failure revokes all replay conversations/claims, restores a777736 and verifies local/public versions. Unrelated durable service screen identities are protected; ephemeral project-tick and lanes may churn.
No gaps/media/voice/UI/Instinct deployment, Grok/xAI, force-push, Jeff notifications or real SMS/iMessage. Assess actual blocking defects with concrete symbols/examples. Output exactly one line and nothing else: VERDICT: PASS or VERDICT: FAIL.
'''
parts=[header, '\n## Validation report\n'+(REVIEWS/'TEXTING-FIXED-1658.md').read_text(),
       '\n## Exact diff from failed c6b3e79\n'+git('diff','c6b3e79',sha)]
for name in ('services/dispatch_worker.py','services/mini_worker.py','services/result_acceptance.py',
             'services/api_worker.py','services/worker.py','services/test_replay_completion.py','services/test_action_plan.py','services/test_regression_drafts.py','services/fixtures/texting_regression_control_1658.json','services/fixtures/texting_regression_drafts_1658.json','services/fixtures/texting_action_plan_control_1605.json','services/fixtures/texting_action_plan_1605.json','services/fixtures/texting_jobcompletion_1403.json','services/workspaces.py','webchat/worker_assignment.py','webchat/test_texting_diagdump.py'):
    parts.append('\n## '+name+'\n'+(WT/name).read_text())
for receipt in ('TEXTING-1658-tests.json', 'TEXTING-1658-runner-checks.json', 'TEXTING-1658-probe-assertion-audit.json'):
    parts.append('\n## '+receipt+'\n'+(REVIEWS/receipt).read_text())
parts.append('\n## Live worker probe\n'+(REVIEWS/'TEXTING-WORKER-1658.json').read_text())
parts.append('\n## Release runner\n'+(REVIEWS/'deploy_texting_1658.py').read_text())
parts.append('\n## Guard test results\n'+(REVIEWS/'TEXTING-1658-deploy-guard-tests.txt').read_text())
context='\n'.join(parts)
context_path=REVIEWS/f'TEXTING-LIVE-{sha[:7]}-1658-attempt{slot}.context.md'
context_path.write_text(context)
context_hash=hashlib.sha256(context.encode()).hexdigest()
print(f'START LIVE reviews tip={sha} attempt={slot} context_bytes={len(context.encode())}',flush=True)

def review(lane):
    output=REVIEWS/f'LIVE-{lane.upper()}-draft_webbob-texting-regression-drafts-fix-1658-{sha[:7]}-1658-attempt{slot}.md'
    assert not output.exists()
    meta=dict(sha=sha,provider=lane,model=MODELS[lane],attempt=slot,started_at=datetime.now(timezone.utc).isoformat(),context=str(context_path),context_sha256=context_hash,output=str(output),exit=1,verdict='FAIL')
    meta['transport_receipts']=[]
    meta['review_transport_sha256']=hashlib.sha256((REVIEWS/'review_transport_1035.py').read_bytes()).hexdigest()
    try:
        answer=ask_verdict(lane,context,purpose='webbob-code-review-1658',timeout=600,receipts=meta['transport_receipts'])
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
path=REVIEWS/f'TEXTING-LIVE-{sha[:7]}-1658-attempt{slot}.json'
path.write_text(json.dumps(record,indent=2)+'\n')
(REVIEWS/'TEXTING-LIVE-1658.json').write_text(path.read_text())
report=f'# Fresh LIVE texting reviews 1658\n\ntip: {sha}\nattempt_slot: {slot}\ncontext: {context_path}\ncontext_sha256: {context_hash}\n\n'
for lane,meta in reviews.items():
    report+=f'{lane}: {meta["model"]} — VERDICT: {meta["verdict"]}\noutput: {meta["output"]}\nstarted: {meta["started_at"]}\nfinished: {meta["finished_at"]}\n\n'
report+=f'GATE: {gate} tip={sha[:7]}\n'
(REVIEWS/'TEXTING-LIVE-1658.md').write_text(report)
print(report,flush=True)
raise SystemExit(0 if gate=='BOTH_PASS' else 1)
