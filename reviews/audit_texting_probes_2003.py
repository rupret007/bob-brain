"""Record literal outcomes from the accepted fresh probe answers, without executing model code."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

WT = Path(__file__).resolve().parents[1]
ROOT = Path('/Users/jeffstory/Documents/bob-overnight-inject')
REVIEWS = ROOT / 'conductor/reviews'
sys.path[:0] = [str(WT / name) for name in ('webchat', 'services', 'state')]
import result_acceptance as acceptance

sha = subprocess.check_output(['git', '-C', str(WT), 'rev-parse', 'HEAD'], text=True).strip()
probe = json.loads((REVIEWS / 'TEXTING-WORKER-2003.json').read_text())
assert probe['sha'] == sha and probe['all_pass'] and probe['guard_contradiction_rejects'] == 0
jobs = []
for row in probe['jobs'] + [probe['guard_consistency_job']]:
    answer = row['result']
    acceptance.check_answer(row['prompt'], answer, kind=row['kind'])
    assert row['acceptance']['accepted'] is True
    assert hashlib.sha256(answer.encode()).hexdigest() == row['result_sha256']
    assert Path(row['result_path']).read_text().strip() == answer.strip()
    controls = []
    for case in re.split(acceptance.CASE_HEADING, acceptance.draft_prose(answer))[1:]:
        fields = {name: re.search(r'(?im)^[ \t]{0,3}(?:[-*][ \t]+)?(?:\*\*)?' + name +
                                  r'[ \t]*:(?:\*\*)?[ \t]*([^\n]+)', case)[1]
                  for name in ('Setup', 'Action', 'Expected')}
        inputs = acceptance.literal_guard_inputs(fields['Setup'], fields['Action'])
        if inputs:
            guard, kwargs = inputs
            error = acceptance.literal_guard_outcome(guard, **kwargs)
            controls.append(dict(guard=guard, actual_error=error, expected=fields['Expected'],
                inputs_sha256=hashlib.sha256(json.dumps(kwargs, sort_keys=True).encode()).hexdigest(), consistent=True))
    assert len(controls) == 2, 'Named report probes need two literal audited controls'
    jobs.append(dict(job_id=row['id'], worker=row['worker'], model=row['model'],
                     result_sha256=row['result_sha256'], controls=controls, accepted_saved_hash_verified=True))
record = dict(sha=sha, all_pass=True, at=datetime.now(timezone.utc).isoformat(),
              guard_contradiction_rejects=0, jobs=jobs)
(REVIEWS / 'TEXTING-2003-probe-assertion-audit.json').write_text(json.dumps(record, indent=2) + '\n')
print('AUDIT_PASS: ' + str(len(jobs)) + ' accepted saved reports; ' + str(sum(len(j['controls']) for j in jobs)) + ' literal controls')
