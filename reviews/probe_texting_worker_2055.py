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
WT = Path(__file__).resolve().parents[1]
REVIEWS = ROOT / 'conductor/reviews'
os.environ['BOB_ROOT'] = str(ROOT)
os.umask(0o077)
sys.path.insert(0, str(WT / 'services'))
import dispatch_worker
from dispatch_worker import task_queue

sha = subprocess.check_output(['git', '-C', str(WT), 'rev-parse', 'HEAD'], text=True).strip()
fixtures = [json.loads((WT / name).read_text()) for name in ('services/fixtures/texting_regression_drafts_1658.json', 'services/fixtures/texting_action_plan_1605.json', 'services/fixtures/texting_jobcompletion_1107.json', 'services/fixtures/texting_guard_consistency_1803.json')]
probe = REVIEWS / ('TEXTING-WORKER-2055-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
core = probe / 'conductor'
(core / 'services').mkdir(parents=True)
(core / 'services/projects.json').write_text(json.dumps({'Web Bob': {'repo': str(WT)}}))
record = dict(sha=sha, started_at=datetime.now(timezone.utc).isoformat(), all_pass=False,
              source_job_ids=[f['job_id'] for f in fixtures] + ['webchat-f4b8e359666155c6a06900f02b313c8c'],
              isolation='Private queue and reports; actual shared lane locks, API, budget and acceptance. No service pins changed.',
              jobs=[])
# Replay exact 20bfc6f, f2c47c4c and 1035/dd47c4cb assignments as independent real executions.
# Never repair, replace or retry a rejected answer.
real_ask = dispatch_worker.ask
calls = []
def recorded_ask(*args, **kwargs):
    answer = real_ask(*args, **kwargs)
    path = probe / ('call-' + str(len(calls) + 1) + '.txt')
    path.write_text(dispatch_worker.redact(answer))
    calls.append(dict(purpose=kwargs.get('purpose'), worker=args[0], output=str(path),
                      output_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    return answer
with patch.object(dispatch_worker, 'ROOT', probe), patch.object(dispatch_worker, 'CONDUCTOR', core), patch.object(dispatch_worker, 'ask', side_effect=recorded_ask):
    for index, fixture in enumerate(fixtures):
        engine = 'gemini' if index == 3 else 'minimax'
        job = task_queue.enqueue(probe, '2055-worker-probe', str(uuid.uuid4()), fixture['prompt'],
                                 worker=engine, kind=fixture['kind'], title='Web Bob regression drafts probe')
        claim = task_queue.claim(probe, engine, identifier=job['id'])
        if not claim:
            raise RuntimeError('Could not claim private probe job')
        code = dispatch_worker.execute(job['id'], claim['claim_token'])
        row = task_queue.tasks(probe)[job['id']]
        prompt_path = core / 'state/task-runs' / job['id'] / 'prompt.txt'
        record['jobs'].append(dict(exit=code, **row,
            worker_prompt_sha256=hashlib.sha256(prompt_path.read_bytes()).hexdigest() if prompt_path.exists() else None,
            worker_prompt_bytes=prompt_path.stat().st_size if prompt_path.exists() else 0))
        print('LIVE ' + engine + ' probe ' + str(index + 1) + ': ' + row['status'] + ' ' + str(row.get('error') or ''), flush=True)
        if code or row['status'] != 'succeeded':
            break
assert subprocess.check_output(['git', '-C', str(WT), 'rev-parse', 'HEAD'], text=True).strip() == sha
assert not subprocess.check_output(['git', '-C', str(WT), 'status', '--porcelain'], text=True).strip()
assert all((job.get('evidence') or {}).get('head') == sha for job in record['jobs'] if job['status'] == 'succeeded')
record.update(finished_at=datetime.now(timezone.utc).isoformat(),
              all_pass=len(record['jobs']) == 4 and all(r['status'] == 'succeeded' for r in record['jobs']))
for job, fixture in zip(record['jobs'], fixtures):
    if job['status'] == 'succeeded':
        from result_acceptance import check_answer
        check_answer(job['prompt'], job['result'], kind=job['kind'])
        assert job['prompt'] == fixture['prompt'] and job['kind'] == fixture['kind']
        assert job['acceptance']['accepted'] is True
        assert hashlib.sha256(job['result'].encode()).hexdigest() == job['result_sha256']
        assert Path(job['result_path']).read_text().strip() == job['result'].strip()
record['guard_contradiction_rejects'] = sum('contradicts literal guard outcome' in str(job.get('error', '')) for job in record['jobs'])
if len(record['jobs']) == 4:
    record['guard_consistency_job'] = record['jobs'].pop()
record['calls'] = calls
body = json.dumps(record, indent=2, ensure_ascii=False) + '\n'
(probe / 'receipt.json').write_text(body)
(REVIEWS / 'TEXTING-WORKER-2055.json').write_text(body)
print('ALL_PASS=' + str(record['all_pass']) + ' evidence=' + str(probe / 'receipt.json'), flush=True)
raise SystemExit(0 if record['all_pass'] else 1)
