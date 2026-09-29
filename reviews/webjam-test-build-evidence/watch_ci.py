"""Read-only watcher for the exact test-build and source-PR CI runs."""
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time

out = Path(__file__).resolve().parent
ids = (36294186058, 36294188304, 36294187158, 36294189148, 36294187169, 36294189448)
previous = None
while True:
    runs = []
    for run_id in ids:
        result = subprocess.run([
            'gh', 'run', 'view', str(run_id), '--repo', 'rupret007/webjam',
            '--json', 'databaseId,headBranch,headSha,status,conclusion,url,jobs,event,createdAt,updatedAt'
        ], capture_output=True, text=True, timeout=45)
        if result.returncode:
            print('GitHub read failed for', run_id, '— retrying next poll', flush=True)
            break
        run = json.loads(result.stdout)
        (out / ('ci-run-' + str(run_id) + '.json')).write_text(json.dumps(run, indent=2) + '\n')
        runs.append(run)
    if len(runs) == len(ids):
        summary = []
        failed = []
        for run in runs:
            jobs = run['jobs']
            counts = Counter(job['conclusion'] or job['status'] for job in jobs)
            pending = [job['name'] for job in jobs if job['status'] != 'completed']
            bad = [job['name'] for job in jobs if job['conclusion'] in ('failure', 'timed_out', 'cancelled', 'action_required')]
            summary.append(dict(id=run['databaseId'], branch=run['headBranch'],
                                status=run['status'], conclusion=run['conclusion'],
                                counts=dict(counts), pending=pending, failed=bad))
            if bad or (run['status'] == 'completed' and run['conclusion'] != 'success'):
                failed.append(run['databaseId'])
        snapshot = dict(checked_at=datetime.now(timezone.utc).isoformat(timespec='seconds'), runs=summary)
        (out / 'ci-summary.json').write_text(json.dumps(snapshot, indent=2) + '\n')
        if summary != previous:
            print(json.dumps(snapshot), flush=True)
            previous = summary
        if failed:
            print('Failed runs:', failed, flush=True)
            raise SystemExit(2)
        if all(run['status'] == 'completed' and run['conclusion'] == 'success' for run in runs):
            print('All six exact-head CI runs succeeded.', flush=True)
            break
    time.sleep(40)
