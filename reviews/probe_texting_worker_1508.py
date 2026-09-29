"""Exercise the candidate's real API worker in an isolated queue before release."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
from unittest.mock import patch

ROOT = Path('/Users/jeffstory/Documents/bob-overnight-inject')
WT = ROOT / 'workspaces/webbob-texting-replay-json-1508'
REVIEWS = ROOT / 'conductor/reviews'
os.environ['BOB_ROOT'] = str(ROOT)
os.umask(0o077)
sys.path.insert(0, str(WT / 'services'))
import dispatch_worker
from dispatch_worker import task_queue

sha = subprocess.check_output(['git', '-C', str(WT), 'rev-parse', 'HEAD'], text=True).strip()
fixtures = [json.loads((WT / ('services/fixtures/texting_jobcompletion_' + incident + '.json')).read_text()) for incident in ('1403', '1107')]
probe = REVIEWS / ('TEXTING-WORKER-1508-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
core = probe / 'conductor'
(core / 'services').mkdir(parents=True)
(core / 'services/projects.json').write_text(json.dumps({'Web Bob': {'repo': str(WT)}}))
record = dict(sha=sha, started_at=datetime.now(timezone.utc).isoformat(), all_pass=False,
              source_job_ids=[f['job_id'] for f in fixtures] + ['webchat-f4b8e359666155c6a06900f02b313c8c'],
              isolation='Private queue and reports; actual shared lane locks, API, budget and acceptance. No service pins changed.',
              jobs=[])
# Replay the actual 1403 assignment and the identical 1035/dd47c4cb assignment.
# Never repair, replace or retry a rejected answer.
with patch.object(dispatch_worker, 'ROOT', probe), patch.object(dispatch_worker, 'CONDUCTOR', core):
    for index, fixture in enumerate(fixtures):
        job = task_queue.enqueue(probe, '1508-worker-probe', str(uuid.uuid4()), fixture['prompt'],
                                 worker='minimax', kind=fixture['kind'], title='Web Bob regression drafts probe')
        claim = task_queue.claim(probe, 'minimax', identifier=job['id'])
        if not claim:
            raise RuntimeError('Could not claim private probe job')
        code = dispatch_worker.execute(job['id'], claim['claim_token'])
        row = task_queue.tasks(probe)[job['id']]
        prompt_path = core / 'state/task-runs' / job['id'] / 'prompt.txt'
        record['jobs'].append(dict(exit=code, **row,
            worker_prompt_sha256=hashlib.sha256(prompt_path.read_bytes()).hexdigest() if prompt_path.exists() else None,
            worker_prompt_bytes=prompt_path.stat().st_size if prompt_path.exists() else 0))
        print('LIVE MiniMax probe ' + str(index + 1) + ': ' + row['status'] + ' ' + str(row.get('error') or ''), flush=True)
        if code or row['status'] != 'succeeded':
            break
assert subprocess.check_output(['git', '-C', str(WT), 'rev-parse', 'HEAD'], text=True).strip() == sha
assert not subprocess.check_output(['git', '-C', str(WT), 'status', '--porcelain'], text=True).strip()
assert all((job.get('evidence') or {}).get('head') == sha for job in record['jobs'] if job['status'] == 'succeeded')
record.update(finished_at=datetime.now(timezone.utc).isoformat(),
              all_pass=len(record['jobs']) == 2 and all(r['status'] == 'succeeded' for r in record['jobs']))
body = json.dumps(record, indent=2, ensure_ascii=False) + '\n'
(probe / 'receipt.json').write_text(body)
(REVIEWS / 'TEXTING-WORKER-1508.json').write_text(body)
print('ALL_PASS=' + str(record['all_pass']) + ' evidence=' + str(probe / 'receipt.json'), flush=True)
raise SystemExit(0 if record['all_pass'] else 1)
