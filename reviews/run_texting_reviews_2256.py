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
tests=json.loads((REVIEWS/'TEXTING-2256-tests.json').read_text())
assert tests['sha']==sha and tests['all_pass']
probe=json.loads((REVIEWS/'TEXTING-WORKER-2256.json').read_text())
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
    reservation=REVIEWS/f'TEXTING-LIVE-{sha[:7]}-2256-attempt{slot}.reserved'
    try:
        with reservation.open('x') as out:
            out.write(datetime.now(timezone.utc).isoformat()+'\n')
        break
    except FileExistsError:
        slot+=1
header=f'''Perform a fresh LIVE API code/release review of Web Bob tip {sha}, branch draft/webbob-texting-minimax-probe-fix-2256, attempt {slot}.
Review the supplied exact code and receipts. You have no tools; do not claim you ran tests or inspected live yourself. Prior approvals do not authorize this tip.

Authoritative history: TEXTING-DEPLOY-2055 held c63dc2fb3d3b55eaaf6c8bf00275cd64290cde6e before activation after the mandatory MiniMax report omitted second-case action and expected fields and buried their labels inside setup. This was a genuine quality failure, not an acceptance override opportunity. Its exact rejected answer remains a fixture with the original rejection. Earlier c87cb73 attempt13 passed smoke and 19 turns but failed an additional semantic worker acceptance; rollback restored a777736. No 2055 activation occurred. The current work must substantively improve regression-draft generation, preserve rejection of malformed drafts, and prove the real provider output is accepted with saved hashes.
Scope is texting only. The candidate starts from c63dc2f; the exact product diff and current source below define the implementation. Structured API worker fields must render two outer Regression test cases, each with separate nonempty same-line Target, Setup, Action and Expected. Nested/historical labels never substitute for outer fields. Do not infer success merely from this description. Independent semantic acceptance, task relevance, completion JSON, Action/Unblock plan, Findings/limits, literal guard Expected checks, greeting policy, 180-second MiniMax worker deadline, fixture omission, shared budget/cooldown and report_repository worktree=None contracts remain binding.
Retained release safety: exact-byte free-space floor 5,368,709,120 bytes at preparation, activation and evidence checkpoints; bounded compact atomic JSON with a 1 MiB cap; physical 64 MiB recovery reserve; rollback journal and rollback-first failure recovery. Failed evidence publication must still cancel claims and restore a777736 before publishing failure. Durable svc-* peers remain protected, with only webchat/job-runner restarts allowed. Other lane-webbob-* screens block activation except this lane. A regular clean-branch merge must contain the reviewed candidate with an equal tree, matching remote and draft PR head. Those publishing gates occur after this review and before activation. Fresh rollback snapshots must match the authenticated current a777736 baseline and both local/public versions and service pins must match after activation and at final success. The five-activation texting cap spans 2055 and 2256; this task requests only one candidate activation. No retry of an unchanged rejected answer and no gate weakening.
Required exact-tip preactivation evidence: full webchat/services/release-guard suites, parity eval and texting browser proof; mandatory actual private-queue MiniMax 20bfc6f, f2c47c4c and 1035/dd47c4cb probes and Gemini 1803 guard-consistency probe, with accepted saved report hashes and a per-case assertion audit (every actual direct guard literally verified; remaining task-relevant drafts bound to independent semantic acceptance); authenticated private replay of all ten cross-project historical turns with actual worker jobs completed and accepted. That private instance uses private committed copies, local bare remotes and an explicitly local draft-PR test adapter. It never publishes cross-project production work. The original nine Web Bob turns then run against production. Every required job must finish; conversational 10/10 alone is not a completed private proof. Fresh exact-tip BOTH_PASS is required before activation. Mocked tests are separate from real provider evidence.
Inspect current reports, source, probe receipts and private proof. Report a concrete blocking defect or missing required preactivation evidence with FAIL. Do not reject because production replay/activation/merge has not happened yet: those are the subsequent guarded phase.
No Grok/xAI, force-push, Jeff notifications or real SMS/iMessage. Gaps, media, Instinct, voice and UI remain HOLD until texting LIVE_PASS and are not part of this release. Output exactly one line: VERDICT: PASS or VERDICT: FAIL.
'''
parts=[header, '\n## Validation report\n'+(REVIEWS/'TEXTING-FIXED-2256.md').read_text(),
       '\n## Exact product diff from c63dc2f (new release source is included below)\n'+git('diff','c63dc2fb3d3b55eaaf6c8bf00275cd64290cde6e',sha,'--','services','webchat','state')]
for name in ('services/dispatch_worker.py','services/mini_worker.py','services/result_acceptance.py',
             'services/api_worker.py','services/worker.py','services/test_replay_completion.py','services/test_action_plan.py','services/test_regression_drafts.py','services/test_guard_consistency.py','services/fixtures/texting_guard_consistency_1803.json','services/fixtures/texting_regression_control_1658.json','services/fixtures/texting_regression_drafts_1658.json','services/fixtures/texting_action_plan_control_1605.json','services/fixtures/texting_action_plan_1605.json','services/fixtures/texting_jobcompletion_1403.json','services/workspaces.py','webchat/worker_assignment.py','webchat/worker_evidence.py','webchat/test_worker_evidence.py','webchat/test_release_imports.py','services/test_report_task_scope.py','services/test_minimax_probe_2256.py','services/fixtures/texting_minimax_probe_2256.json','webchat/test_texting_diagdump.py'):
    parts.append('\n## '+name+'\n'+(WT/name).read_text())
for receipt in ('TEXTING-2256-tests.json', 'TEXTING-2256-runner-checks.json', 'TEXTING-2256-probe-assertion-audit.json', 'TEXTING-2256-isolated-replay.json'):
    parts.append('\n## '+receipt+'\n'+(REVIEWS/receipt).read_text())
parts.append('\n## Live worker probe\n'+(REVIEWS/'TEXTING-WORKER-2256.json').read_text())
for name in ('test_audit_texting_probes_2256.py','probe_texting_worker_2256.py','audit_texting_probes_2256.py','run_texting_checks_2256.py','run_texting_reviews_2256.py','deploy_texting_2256.py','record_texting_deploy_2256.py','texting_deploy_record.py','test_record_texting_deploy_2256.py','test_disk_evidence_2256.py','isolated_replay_2256.py','test_isolated_replay_2256.py','test_deploy_scope_2256.py'):
    parts.append('\n## Release script '+name+'\n'+(WT/'reviews'/name).read_text())
parts.append('\n## Authoritative c63dc2f held release\n'+(REVIEWS/'TEXTING-DEPLOY-2055.md').read_text())
parts.append('\n## Authoritative attempt13 deployment report\n'+(REVIEWS/'TEXTING-DEPLOY-2003.md').read_text())
parts.append('\n## Guard test results\n'+(REVIEWS/'TEXTING-2256-deploy-guard-tests.txt').read_text())
context='\n'.join(parts)
context_path=REVIEWS/f'TEXTING-LIVE-{sha[:7]}-2256-attempt{slot}.context.md'
atomic_text(context_path, context)
context_hash=hashlib.sha256(context.encode()).hexdigest()
print(f'START LIVE reviews tip={sha} attempt={slot} context_bytes={len(context.encode())}',flush=True)

def review(lane):
    output=REVIEWS/f'LIVE-{lane.upper()}-draft_webbob-texting-minimax-probe-fix-2256-{sha[:7]}-2256-attempt{slot}.md'
    assert not output.exists()
    meta=dict(sha=sha,provider=lane,model=MODELS[lane],attempt=slot,started_at=datetime.now(timezone.utc).isoformat(),context=str(context_path),context_sha256=context_hash,output=str(output),exit=1,verdict='FAIL')
    meta['transport_receipts']=[]
    meta['review_transport_sha256']=hashlib.sha256((REVIEWS/'review_transport_1035.py').read_bytes()).hexdigest()
    try:
        answer=ask_verdict(lane,context,purpose='webbob-code-review-2256',timeout=600,attempts=1,receipts=meta['transport_receipts'])
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
path=REVIEWS/f'TEXTING-LIVE-{sha[:7]}-2256-attempt{slot}.json'
path.write_text(json.dumps(record,indent=2)+'\n')
(REVIEWS/'TEXTING-LIVE-2256.json').write_text(path.read_text())
report=f'# Fresh LIVE texting reviews 2256\n\ntip: {sha}\nattempt_slot: {slot}\ncontext: {context_path}\ncontext_sha256: {context_hash}\n\n'
for lane,meta in reviews.items():
    report+=f'{lane}: {meta["model"]} — VERDICT: {meta["verdict"]}\noutput: {meta["output"]}\nstarted: {meta["started_at"]}\nfinished: {meta["finished_at"]}\n\n'
report+=f'GATE: {gate} tip={sha[:7]}\n'
(REVIEWS/'TEXTING-LIVE-2256.md').write_text(report)
print(report,flush=True)
raise SystemExit(0 if gate=='BOTH_PASS' else 1)
