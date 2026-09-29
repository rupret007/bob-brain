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
from lanes import ask
from api_tasks import MODELS

def git(*args):
    return subprocess.check_output(['git','-C',str(WT),*args],text=True).strip()

sha=git('rev-parse','HEAD')
assert not git('status','--porcelain')
tests=json.loads((REVIEWS/'TEXTING-0810-tests.json').read_text())
assert tests['sha']==sha and tests['all_pass']
slot=1
while True:
    reservation=REVIEWS/f'TEXTING-LIVE-{sha[:7]}-0810-attempt{slot}.reserved'
    try:
        with reservation.open('x') as out:
            out.write(datetime.now(timezone.utc).isoformat()+'\n')
        break
    except FileExistsError:
        slot+=1
header=f'''Perform a fresh LIVE API code/release review of Web Bob tip {sha}, branch draft/webbob-texting-onto-a777736, attempt {slot}.
This is a new review; do not reuse any previous verdict. Review the supplied exact code and test evidence. You have no tools; do not claim you ran tests or inspected live yourself.

Authoritative problem: ce2482c was merged as 1d72c44 (must remain), deployed, and rolled back to a777736 after session b33fac25-3c8a-452d-8673-47d3a99dd92c turn 3 ('Ok great works on all LLMs now?') produced a raw diagnostic dump.
Requirement: short natural status, no missing-model placeholders, queue_counts, job-runner internals, or semicolon worker inventories in casual chat. Reuse existing status/reply infrastructure. Keep truthful running/waiting/unconfirmed/idle states, exact saved observations, dispatch effects, texting consent/privacy, and opt-in diagnostics.
Full model/task/duration inventories are deliberately no longer required in casual prose; they remain in the saved observation and explicit diagnostics. Evaluate the new behavioral tests independently, not just renderer equality.
Scope excludes media/voice/UI/Instinct deploy, Grok/xAI, force-push and Jeff notifications/texts. The only browser change is the existing isolated texting test harness's CSP-compatible locator wait.
The release runner is adapted from the previous guarded script, requires fresh reviews + full tests + exact draft head and clean-merge tree, snapshots rollback, checks texting smoke and all 19 exact replay turns, waits for real jobs, and rolls back to a777736 on failure.
Find actual blocking defects with concrete symbols and examples. Nonblocking suggestions are welcome, clearly labeled. End with exactly one line: VERDICT: PASS or VERDICT: FAIL.
'''
parts=[header, '\n## Validation report\n'+(REVIEWS/'TEXTING-FIXED-0810.md').read_text(),
       '\n## Exact diff from failed ce2482c\n'+git('diff','ce2482c',sha),
       '\n## Preserved observation validation\n'+(WT/'webchat/status_observation.py').read_text()]
source=(WT/'webchat/reply_authority.py').read_text()
parts.append('\n## Current operational formatting (including diagnostics)\n'+source[source.index('def _cooldown'):source.index('def operational_reply')])
source=(WT/'webchat/app.py').read_text()
parts.append('\n## Saved status route\n'+source[source.index('    def status_reply'):source.index('    def get(',source.index('    def status_reply'))])
parts.append('\n## Routing before generic work/provider handling\n'+'\n'.join(source.splitlines()[340:410]))
source=(WT/'webchat/texting.py').read_text()
parts.append('\n## Texting confirmation/handler (unchanged)\n'+source[source.index('    def confirm('):])
parts.append('\n## Release runner\n'+(REVIEWS/'deploy_texting_0810.py').read_text())
parts.append('\n## Guard test results\n'+(REVIEWS/'TEXTING-0810-deploy-guard-tests.txt').read_text())
context='\n'.join(parts)
context_path=REVIEWS/f'TEXTING-LIVE-{sha[:7]}-0810-attempt{slot}.context.md'
context_path.write_text(context)
context_hash=hashlib.sha256(context.encode()).hexdigest()
print(f'START LIVE reviews tip={sha} attempt={slot} context_bytes={len(context.encode())}',flush=True)

def review(lane):
    output=REVIEWS/f'LIVE-{lane.upper()}-draft_webbob-texting-onto-a777736-{sha[:7]}-0810-attempt{slot}.md'
    assert not output.exists()
    meta=dict(sha=sha,provider=lane,model=MODELS[lane],attempt=slot,started_at=datetime.now(timezone.utc).isoformat(),context=str(context_path),context_sha256=context_hash,output=str(output),exit=1,verdict='FAIL')
    try:
        answer=ask(lane,context,purpose='webbob-code-review-0810')
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
path=REVIEWS/f'TEXTING-LIVE-{sha[:7]}-0810-attempt{slot}.json'
path.write_text(json.dumps(record,indent=2)+'\n')
(REVIEWS/'TEXTING-LIVE-0810.json').write_text(path.read_text())
report=f'# Fresh LIVE texting reviews 0810\n\ntip: {sha}\nattempt_slot: {slot}\ncontext: {context_path}\ncontext_sha256: {context_hash}\n\n'
for lane,meta in reviews.items():
    report+=f'{lane}: {meta["model"]} — VERDICT: {meta["verdict"]}\noutput: {meta["output"]}\nstarted: {meta["started_at"]}\nfinished: {meta["finished_at"]}\n\n'
report+=f'GATE: {gate} tip={sha[:7]}\n'
(REVIEWS/'TEXTING-LIVE-0810.md').write_text(report)
print(report,flush=True)
raise SystemExit(0 if gate=='BOTH_PASS' else 1)
