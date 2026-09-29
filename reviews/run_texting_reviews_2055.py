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
WT=Path(__file__).resolve().parents[1]
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
tests=json.loads((REVIEWS/'TEXTING-2055-tests.json').read_text())
assert tests['sha']==sha and tests['all_pass']
probe=json.loads((REVIEWS/'TEXTING-WORKER-2055.json').read_text())
assert probe['sha']==sha and probe['all_pass'] and len(probe['jobs'])==3 and probe['guard_contradiction_rejects']==0
assert probe['guard_consistency_job']['worker']=='gemini' and probe['guard_consistency_job']['status']=='succeeded'
for job in probe['jobs']:
    assert job['worker']=='minimax' and job['model']=='MiniMax-M2.7' and job['status']=='succeeded'
    assert job['acceptance']['accepted'] is True
    assert hashlib.sha256(job['result'].encode()).hexdigest()==job['result_sha256']
    assert Path(job['result_path']).read_text().strip()==job['result'].strip()
slot=14
while True:
    if any(REVIEWS.glob(f"TEXTING-LIVE-*-*-attempt{slot}.reserved")) or (REVIEWS/f"WEBBOB-TEXTING-DEPLOYMENT-0927-attempt{slot}.json").exists():
        slot+=1
        continue
    reservation=REVIEWS/f'TEXTING-LIVE-{sha[:7]}-2055-attempt{slot}.reserved'
    try:
        with reservation.open('x') as out:
            out.write(datetime.now(timezone.utc).isoformat()+'\n')
        break
    except FileExistsError:
        slot+=1
header=f'''Perform a fresh LIVE API code/release review of Web Bob tip {sha}, branch draft/webbob-texting-deploy-2055, attempt {slot}.
Review the supplied exact code and receipts. You have no tools; do not claim you ran tests or inspected live yourself. Prior approvals do not authorize this new tip.

Authoritative history: attempt12 on 8260f80 passed texting smoke and all 19 turns but exhausted Data while publishing LIVE_REPLAY evidence. The c87cb73 successor added the 5 GiB gate, bounded compact evidence, a physical recovery reserve and rollback-first failure recovery. Attempt13 on c87cb73 then passed smoke, 19/19 turns and all three named MiniMax regressions; disk checks and 330,375-byte checkpoint publication succeeded. Its additional replay job webchat-16057f2d2c3b5e27ba041d9ace204ee5 failed real semantic acceptance: the report used irrelevant check_completion_json cases instead of lane-specific regressions and the semantic reviewer also claimed the Findings/limits heading was missing. Inspection of the rejected queue answer proves that heading was present; the relevance failure remains binding, and no semantic gate is bypassed. Automatic rollback restored and verified a777736; nine unfinished claims were revoked. The attempt13 report and traceback below are authoritative. Do not describe the latest failure as ENOSPC.
Scope: the candidate starts at c87cb73 and changes report-generation tooling in services/api_worker.py plus its regressions, bare-lane task-evidence parsing in webchat/worker_evidence.py, and the release scripts. The exact diff and validation report below define the final scope. In particular, product/tooling source is NOT claimed byte-for-byte unchanged. The report prompt must provide applicable, task-grounded regression guidance without forcing unrelated completion-JSON guard examples on every task; Findings/limits remains an outer prose requirement. Existing result acceptance, completion JSON, Action/Unblock, outer regression drafts, literal guard Expected checks and report_repository worktree=None contracts must remain intact. Inspect the supplied implementation and its tests; do not infer a fix merely from this summary.
Release safety retained from c87cb73: exact-byte free-space floor 5 GiB on Data and evidence/workspace/staging volumes before activation and every live checkpoint; streamed compact JSON with a 1 MiB hard cap and atomic publication; hashes, identities, gate outcomes and saved report/session paths preserved without repeated queue dumps; rollback journal publishes conversation IDs before jobs can be queued; 64 MiB physical-block recovery reserve plus a fail-closed marker. On evidence or final-publication I/O failure, release reserve, cancel claims and restore a777736 before failure publication. Cancellation errors cannot suppress restoration, and parent recovery uses the predeclared rollback path even if records cannot be read. /private/tmp is staging on the checked filesystem, not extra capacity. Supervisor lock, durable service-screen protections, matching draft/remote head, equal-tree clean ancestry, own-lane allowance and rejection of other active Web Bob lanes remain. Fresh snapshots of the authenticated current a777736 baseline are required before activation; both pins and authenticated local/public full candidate SHA must match before smoke/replay and at the final gate.
Gates: fresh exact-tip full offline webchat/services/evals/browser and release guard tests; real private-queue MiniMax 20bfc6f, f2c47c4c and 1035/dd47c4cb probes plus exact 1803 Gemini guard-consistency probe; saved accepted result hashes and literal control audit; fresh cross-vendor BOTH_PASS. Matching draft PR and equal-tree regular clean merge are verified before activation, after this review. Attempt14+ slots are reserved exclusively. WEB BOB ONLY scope: the exact nine Web Bob turns run against production; the other ten historical turns run against an authenticated private same-SHA HTTP instance with private project clones and local bare remotes. The private draft-PR adapter is explicitly a local protocol test, never a real GitHub PR or a production claim. Original rubric checks, real worker execution, semantic acceptance, saved report hashes, coding validation and ref/draft-SHA checks remain required in each scope. All 19 frozen turns and every dispatched job must finish. A verified immutable same-SHA private replay receipt is required before activation and revalidated before LIVE_PASS. No cross-project work or publication occurs in production. Passing just the 19 turns never grants LIVE_PASS. Review the runner and launcher as well as the changed report prompt. Mocked release guard tests are separate from real provider probes and live evidence. The user allows at most five fresh deployment activations, with retries only after an identified tooling defect is fixed; no quality gate may be weakened to force a pass.
This review and release are Web Bob texting only. The user authorizes gaps, media, Instinct, voice and UI sequentially after texting succeeds; none of those are approved by this texting review. No Grok/xAI, force-push, Jeff notifications or real SMS/iMessage. Assess concrete blocking defects. Output exactly one line and nothing else: VERDICT: PASS or VERDICT: FAIL.
'''
parts=[header, '\n## Validation report\n'+(REVIEWS/'TEXTING-FIXED-2055.md').read_text(),
       '\n## Exact diff from c87cb73\n'+git('diff','c87cb73cbb0fd1a2162bbf939c86170fd26715a5',sha)]
for name in ('services/dispatch_worker.py','services/mini_worker.py','services/result_acceptance.py',
             'services/api_worker.py','services/worker.py','services/test_replay_completion.py','services/test_action_plan.py','services/test_regression_drafts.py','services/test_guard_consistency.py','services/fixtures/texting_guard_consistency_1803.json','services/fixtures/texting_regression_control_1658.json','services/fixtures/texting_regression_drafts_1658.json','services/fixtures/texting_action_plan_control_1605.json','services/fixtures/texting_action_plan_1605.json','services/fixtures/texting_jobcompletion_1403.json','services/workspaces.py','webchat/worker_assignment.py','webchat/worker_evidence.py','webchat/test_worker_evidence.py','webchat/test_release_imports.py','services/test_report_task_scope.py','webchat/test_texting_diagdump.py'):
    parts.append('\n## '+name+'\n'+(WT/name).read_text())
for receipt in ('TEXTING-2055-tests.json', 'TEXTING-2055-runner-checks.json', 'TEXTING-2055-probe-assertion-audit.json', 'TEXTING-2055-isolated-replay.json'):
    parts.append('\n## '+receipt+'\n'+(REVIEWS/receipt).read_text())
parts.append('\n## Live worker probe\n'+(REVIEWS/'TEXTING-WORKER-2055.json').read_text())
for name in ('deploy_texting_2055.py','record_texting_deploy_2055.py','texting_deploy_record.py','test_record_texting_deploy_2055.py','test_disk_evidence_2055.py','isolated_replay_2055.py','test_isolated_replay_2055.py','test_deploy_scope_2055.py'):
    parts.append('\n## Release script '+name+'\n'+(WT/'reviews'/name).read_text())
parts.append('\n## Exact prior rejected answer and heading audit\n'+(REVIEWS/'TEXTING-2055-previous-rejection.json').read_text())
parts.append('\n## Authoritative attempt13 deployment report\n'+(REVIEWS/'TEXTING-DEPLOY-2003.md').read_text())
parts.append('\n## Guard test results\n'+(REVIEWS/'TEXTING-2055-deploy-guard-tests.txt').read_text())
context='\n'.join(parts)
context_path=REVIEWS/f'TEXTING-LIVE-{sha[:7]}-2055-attempt{slot}.context.md'
atomic_text(context_path, context)
context_hash=hashlib.sha256(context.encode()).hexdigest()
print(f'START LIVE reviews tip={sha} attempt={slot} context_bytes={len(context.encode())}',flush=True)

def review(lane):
    output=REVIEWS/f'LIVE-{lane.upper()}-draft_webbob-texting-deploy-2055-{sha[:7]}-2055-attempt{slot}.md'
    assert not output.exists()
    meta=dict(sha=sha,provider=lane,model=MODELS[lane],attempt=slot,started_at=datetime.now(timezone.utc).isoformat(),context=str(context_path),context_sha256=context_hash,output=str(output),exit=1,verdict='FAIL')
    meta['transport_receipts']=[]
    meta['review_transport_sha256']=hashlib.sha256((REVIEWS/'review_transport_1035.py').read_bytes()).hexdigest()
    try:
        answer=ask_verdict(lane,context,purpose='webbob-code-review-2055',timeout=600,receipts=meta['transport_receipts'])
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
path=REVIEWS/f'TEXTING-LIVE-{sha[:7]}-2055-attempt{slot}.json'
path.write_text(json.dumps(record,indent=2)+'\n')
(REVIEWS/'TEXTING-LIVE-2055.json').write_text(path.read_text())
report=f'# Fresh LIVE texting reviews 2055\n\ntip: {sha}\nattempt_slot: {slot}\ncontext: {context_path}\ncontext_sha256: {context_hash}\n\n'
for lane,meta in reviews.items():
    report+=f'{lane}: {meta["model"]} — VERDICT: {meta["verdict"]}\noutput: {meta["output"]}\nstarted: {meta["started_at"]}\nfinished: {meta["finished_at"]}\n\n'
report+=f'GATE: {gate} tip={sha[:7]}\n'
(REVIEWS/'TEXTING-LIVE-2055.md').write_text(report)
print(report,flush=True)
raise SystemExit(0 if gate=='BOTH_PASS' else 1)
