#!/usr/bin/env python3
"""Record offline release gates for the immutable, already reviewed texting tip."""
import concurrent.futures
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/Users/jeffstory/Documents/bob-overnight-inject')
WT = ROOT / 'workspaces/webbob-texting-onto-a777736-0420'
REVIEWS = ROOT / 'conductor/reviews'
TIP = 'ce2482cce311ce4317c1b3aca316f1ca446aeddb'
assert subprocess.check_output(['git', '-C', str(WT), 'rev-parse', 'HEAD'], text=True).strip() == TIP
env = dict(os.environ, TMPDIR='/private/tmp')
env.pop('BOB_ROOT', None)
env.pop('BOB_CODE_ROOT', None)

def check(name, command, cwd):
    log = REVIEWS / ('TEXTING-0702-' + name + '.txt')
    with log.open('x') as stream:
        result = subprocess.run(command, cwd=cwd, env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=600)
    print(name + ': exit=' + str(result.returncode) + ' log=' + str(log), flush=True)
    return dict(exit=result.returncode, log=str(log))

with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    pending = {
        'webchat': pool.submit(check, 'webchat-tests', [sys.executable, '-m', 'unittest', 'discover', '-s', 'webchat'], WT),
        'services': pool.submit(check, 'services-tests', [sys.executable, '-m', 'unittest', 'discover', '-s', 'services'], WT),
        'eval': pool.submit(check, 'eval', [sys.executable, 'bob_parity_eval.py'], WT / 'webchat'),
    }
    results = {name: future.result() for name, future in pending.items()}
evaluation = json.loads((WT / 'webchat/evidence/bob-parity-eval.json').read_text())
record = dict(sha=TIP, at=datetime.now(timezone.utc).isoformat(), results=results,
              suite_exit=max(results[name]['exit'] for name in ('webchat', 'services')),
              eval_exit=results['eval']['exit'], eval=evaluation)
record['all_pass'] = all(value['exit'] == 0 for value in results.values()) and evaluation['all_pass']
(REVIEWS / 'TEXTING-0702-tests.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps({key: record[key] for key in ('sha', 'suite_exit', 'eval_exit', 'all_pass')}), flush=True)
raise SystemExit(0 if record['all_pass'] else 1)
