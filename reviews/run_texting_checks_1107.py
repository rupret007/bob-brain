"""Run the existing offline release suites at an exact clean candidate SHA."""
import concurrent.futures
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT=Path('/Users/jeffstory/Documents/bob-overnight-inject')
WT=ROOT/'workspaces/webbob-texting-jobcomplete-1107'
REVIEWS=ROOT/'conductor/reviews'
def git(*args):
    return subprocess.check_output(['git','-C',str(WT),*args],text=True).strip()
sha=git('rev-parse','HEAD')
assert not git('status','--porcelain')
commands={name:[sys.executable,'-m','unittest','discover','-s',name,'-p','test_*.py'] for name in ('webchat','services')}
commands['eval']=[sys.executable,'webchat/bob_parity_eval.py']
commands['browser']=[sys.executable,'webchat/texting_proof.py','--output-dir',str(REVIEWS/'TEXTING-1107-browser-proof')]
def check(item):
    name,argv=item
    log=REVIEWS/f'TEXTING-1107-{name}-tests.txt'
    env={k:v for k,v in os.environ.items() if not any(x in k.upper() for x in ('KEY','TOKEN','SECRET','PASSWORD'))}
    env.update(TMPDIR='/private/tmp',BOB_PLAYWRIGHT_MODULE=str(ROOT/'conductor/webchat/node_modules/playwright'))
    env.pop('PYTHONPATH',None)
    env.pop('NODE_PATH',None)
    with tempfile.TemporaryDirectory(prefix='texting-offline-',dir='/private/tmp') as tmp, log.open('w') as out:
        env['BOB_ROOT']=tmp
        result=subprocess.run(argv,cwd=WT,env=env,stdout=out,stderr=subprocess.STDOUT,timeout=600)
    body=log.read_text()
    data=dict(exit=result.returncode,log=str(log),command=argv,log_sha256=hashlib.sha256(log.read_bytes()).hexdigest())
    match=re.search(r'Ran (\d+) tests? in ([\d.]+)s',body)
    if match:
        skip=re.search(r'skipped=(\d+)',body)
        data.update(tests=int(match[1]),seconds=float(match[2]),skipped=int(skip[1]) if skip else 0)
    print(name+': '+json.dumps(data),flush=True)
    return name,data
# Browser proofs share live-listener observations; run the standalone after the webchat suite.
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    results=dict(pool.map(check,[(n,commands[n]) for n in ('webchat','services','eval')]))
name,data=check(('browser',commands['browser']))
results[name]=data
assert sha==git('rev-parse','HEAD') and not git('status','--porcelain')
parity=json.loads((WT/'webchat/evidence/bob-parity-eval.json').read_text())
passed=all(v['exit']==0 and not v.get('skipped',0) for v in results.values()) and parity['all_pass']
record=dict(sha=sha,at=datetime.now(timezone.utc).isoformat(),results=results,
            suite_exit=max(results[n]['exit'] for n in ('webchat','services')),
            eval_exit=results['eval']['exit'],eval={k:parity[k] for k in ('passed','total','score')},all_pass=passed)
(REVIEWS/'TEXTING-1107-tests.json').write_text(json.dumps(record,indent=2)+'\n')
print('ALL_PASS='+str(passed),flush=True)
raise SystemExit(0 if passed else 1)
