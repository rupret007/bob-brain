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
WT=ROOT/'workspaces/webbob-texting-replay-json-1508'
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
tests=json.loads((REVIEWS/'TEXTING-1508-tests.json').read_text())
assert tests['sha']==sha and tests['all_pass']
probe=json.loads((REVIEWS/'TEXTING-WORKER-1508.json').read_text())
assert probe['sha']==sha and probe['all_pass']
for job in probe['jobs']:
    assert job['worker']=='minimax' and job['model']=='MiniMax-M2.7' and job['status']=='succeeded'
    assert job['acceptance']['accepted'] is True
    assert hashlib.sha256(job['result'].encode()).hexdigest()==job['result_sha256']
    assert Path(job['result_path']).read_text().strip()==job['result'].strip()
slot=8
while True:
    if any(REVIEWS.glob(f"TEXTING-LIVE-*-*-attempt{slot}.reserved")):
        slot+=1
        continue
    reservation=REVIEWS/f'TEXTING-LIVE-{sha[:7]}-1508-attempt{slot}.reserved'
    try:
        with reservation.open('x') as out:
            out.write(datetime.now(timezone.utc).isoformat()+'\n')
        break
    except FileExistsError:
        slot+=1
header=f'''Perform a fresh LIVE API code/release review of Web Bob tip {sha}, branch draft/webbob-texting-replay-json-fix-1508, attempt {slot}.
This is a new review; do not reuse previous verdicts. Review supplied exact code and test evidence. You have no tools; do not claim you ran tests or inspected live yourself.

Authoritative failure: eb8029e passed prior reviews but deployment attempt7 rolled back to a777736 when MiniMax job webchat-34bc2543b29254c2b70aaca7a0fb545c omitted an actionable plan and a required completion JSON block. Its original worker prompt did not explicitly request that JSON, and the semantic reviewer confused its own verdict schema with worker output. The captured answer also used worktree=None as a repository-selection control. Previous approvals do not authorize this tip.
Requirement: live replay reports must supply real deliverables, concrete findings/limits, an actionable plan where requested and a completion accepted/reason JSON block, enforced deterministically before any semantic vote or success publication. The shared contract covers existing independent subtasks and explicit accepted/reason JSON requests across all dispatch and legacy workers. It is a self-report, not server acceptance; independent semantic checks still reject incorrect answers. Ordinary unrelated answers remain unchanged. Validation functions precede verbose prompt strings so the bounded MiniMax snapshot contains the complete completion checks, covered by an exact-1403-prompt snapshot test. Successful-control fixtures are explicitly told to include required plan, Findings/limits and JSON sections. A real worker probe exposed inline escaped Markdown test-fixture fences confusing JSON extraction; standalone-fence parsing and a regression now prevent that false rejection without accepting inline fixture JSON as completion. The exact failed answer remains rejected; missing, invalid, duplicate, quoted and negative completion JSON cannot win a positive vote. No synthetic answer repair or extra task retry.
report_repository must select an existing source worktree; missing source raises; None/missing/non-directory worktree returns None and the dispatcher stops before evidence/model use, without silently falling back to another repo. Reports without a source ID retain project lookup. The captured attempt7 answer actually expected the fallback repo Path; the old reviewer inaccurately described that as a worktree assertion. The new contract removes that ambiguous fallback explicitly and tests its behavior.
Preserve previous job-completion, texting consent/privacy, frozen chat style and dispatch behavior. The exact-tip real MiniMax probes exercise both the 1403 and the identical 1035/dd47c4cb task with saved accepted deliverables. Named completion snapshots include the complete tracked failure/control fixture and complete ReportRepositoryTests within the same byte budget. The inaccurate historical reviewer error is marked as an opinion rather than the specification, and current tests explicitly establish the unavailable-worktree None contract. Prompts require literal inputs or supplied fixture fields and forbid inferring isolation behavior or missing coverage from a lane title. A valid-JSON but vague/unsupported report was independently rejected during development; its rejection was not bypassed. A probe pass is not a deployment pass.
No media/voice/UI/Instinct deployment, Grok/xAI, force-push, Jeff notifications or real SMS/iMessage sends. Existing deploy_texting_1403.py was adapted to 1508; ancestry checks and durable-svc-peers-1403 screen policy are preserved. Only attempt8+ is allowed. Release requires exact-tip offline receipts/hashes, this fresh Gemini/MiniMax BOTH_PASS, a draft PR and an identical regular clean merge, fresh rollback, texting smoke, 19 frozen turns and the exact 1035/dd47c4cb MiniMax job with all accepted saved results. Any failure revokes replay claims and verifies local/public rollback to a777736. Review the full retained coding verification gates as supplied.
Assess actual blocking defects with concrete symbols/examples. Output exactly one line and nothing else: VERDICT: PASS or VERDICT: FAIL.
'''
parts=[header, '\n## Validation report\n'+(REVIEWS/'TEXTING-FIXED-1508.md').read_text(),
       '\n## Exact diff from failed eb8029e\n'+git('diff','eb8029e',sha)]
for name in ('services/dispatch_worker.py','services/mini_worker.py','services/result_acceptance.py',
             'services/api_worker.py','services/worker.py','services/test_replay_completion.py','services/fixtures/texting_jobcompletion_1403.json','services/workspaces.py','webchat/worker_assignment.py','webchat/test_texting_diagdump.py'):
    parts.append('\n## '+name+'\n'+(WT/name).read_text())
parts.append('\n## Live worker probe\n'+(REVIEWS/'TEXTING-WORKER-1508.json').read_text())
parts.append('\n## Release runner\n'+(REVIEWS/'deploy_texting_1508.py').read_text())
parts.append('\n## Guard test results\n'+(REVIEWS/'TEXTING-1508-deploy-guard-tests.txt').read_text())
context='\n'.join(parts)
context_path=REVIEWS/f'TEXTING-LIVE-{sha[:7]}-1508-attempt{slot}.context.md'
context_path.write_text(context)
context_hash=hashlib.sha256(context.encode()).hexdigest()
print(f'START LIVE reviews tip={sha} attempt={slot} context_bytes={len(context.encode())}',flush=True)

def review(lane):
    output=REVIEWS/f'LIVE-{lane.upper()}-draft_webbob-texting-replay-json-fix-1508-{sha[:7]}-1508-attempt{slot}.md'
    assert not output.exists()
    meta=dict(sha=sha,provider=lane,model=MODELS[lane],attempt=slot,started_at=datetime.now(timezone.utc).isoformat(),context=str(context_path),context_sha256=context_hash,output=str(output),exit=1,verdict='FAIL')
    meta['transport_receipts']=[]
    meta['review_transport_sha256']=hashlib.sha256((REVIEWS/'review_transport_1035.py').read_bytes()).hexdigest()
    try:
        answer=ask_verdict(lane,context,purpose='webbob-code-review-1508',timeout=600,receipts=meta['transport_receipts'])
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
path=REVIEWS/f'TEXTING-LIVE-{sha[:7]}-1508-attempt{slot}.json'
path.write_text(json.dumps(record,indent=2)+'\n')
(REVIEWS/'TEXTING-LIVE-1508.json').write_text(path.read_text())
report=f'# Fresh LIVE texting reviews 1508\n\ntip: {sha}\nattempt_slot: {slot}\ncontext: {context_path}\ncontext_sha256: {context_hash}\n\n'
for lane,meta in reviews.items():
    report+=f'{lane}: {meta["model"]} — VERDICT: {meta["verdict"]}\noutput: {meta["output"]}\nstarted: {meta["started_at"]}\nfinished: {meta["finished_at"]}\n\n'
report+=f'GATE: {gate} tip={sha[:7]}\n'
(REVIEWS/'TEXTING-LIVE-1508.md').write_text(report)
print(report,flush=True)
raise SystemExit(0 if gate=='BOTH_PASS' else 1)
