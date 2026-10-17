"""Audit accepted drafts without executing model code or inventing literal coverage.

The inherited 2055 audit demanded two literal guard calls although the frozen
tasks and acceptance contract also permit concrete nonliteral drafts with an
independent semantic review. Classify those honestly; this tooling correction
does not change the genuine c63dc2f failure to provide two complete outer cases.
"""
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


def require(condition, reason):
    if not condition:
        raise RuntimeError(reason)


def json_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def audit_job(row):
    """Bind per-case coverage to the accepted answer, saved bytes, and review."""
    answer = row['result']
    acceptance.check_answer(row['prompt'], answer, kind=row['kind'])
    review = row.get('acceptance', {})
    require(review.get('accepted') is True and review.get('method') == 'task-answer-review' and
            isinstance(review.get('reason'), str) and bool(review['reason'].strip()),
            'Probe report lacks an independent semantic acceptance review')
    require(hashlib.sha256(answer.encode()).hexdigest() == row['result_sha256'], 'Probe answer hash changed')
    path = Path(row['result_path'])
    require(path.read_text().strip() == answer.strip(), 'Accepted saved report differs from answer')
    require(hashlib.sha256(path.read_bytes()).hexdigest() == row['saved_report_sha256'],
            'Probe accepted saved report changed')
    outer = re.split(acceptance.CASE_HEADING, acceptance.draft_prose(answer))[1:]
    require(len(outer) == 2, 'Probe report needs exactly two complete outer regression drafts')
    cases = []
    for index, case in enumerate(outer, start=1):
        fields = {name: re.search(r'(?im)^[ \t]{0,3}(?:[-*][ \t]+)?(?:\*\*)?' + name +
                                  r'[ \t]*:(?:\*\*)?[ \t]*([^\n]+)', case)
                  for name in ('Target', 'Setup', 'Action', 'Expected')}
        require(all(match and match[1].strip(' *`\t') for match in fields.values()) and
                bool(case.splitlines()[0].strip(' *\t')),
                'Probe report needs exactly two complete outer regression drafts')
        fields = {name: match[1] for name, match in fields.items()}
        name = case.splitlines()[0].strip(' *\t')
        audited = dict(index=index, name=name, target=fields['Target'],
                       draft_sha256=json_hash(dict(name=name, **fields)))
        inputs = acceptance.literal_guard_inputs(fields['Setup'], fields['Action'])
        if inputs:
            guard, kwargs = inputs
            # check_answer above already requires this exact literal outcome.
            audited.update(classification='literal-verified', guard=guard,
                actual_error=acceptance.literal_guard_outcome(guard, **kwargs), expected=fields['Expected'],
                inputs_sha256=json_hash(kwargs), consistent=True)
        else:
            audited.update(classification='semantic-reviewed',
                           basis='independent-task-answer-review', literal_verified=False)
        cases.append(audited)
    literal_count = sum(case['classification'] == 'literal-verified' for case in cases)
    return dict(job_id=row['id'], worker=row['worker'], model=row['model'],
                result_sha256=row['result_sha256'], saved_report_sha256=row['saved_report_sha256'],
                semantic_acceptance_sha256=json_hash(review), independent_semantic_review=True,
                complete_outer_drafts=2, literal_guard_count=literal_count,
                semantic_reviewed_count=2 - literal_count, cases=cases, accepted_saved_hash_verified=True)


def audit_probe(probe, sha):
    require(probe['sha'] == sha and probe['all_pass'] and len(probe['jobs']) == 3 and
            probe['guard_contradiction_rejects'] == 0, 'Fresh worker probe did not pass on this tip')
    jobs = [audit_job(row) for row in probe['jobs'] + [probe['guard_consistency_job']]]
    return dict(sha=sha, all_pass=True, guard_contradiction_rejects=0, jobs=jobs,
                complete_outer_drafts=sum(job['complete_outer_drafts'] for job in jobs),
                literal_guard_count=sum(job['literal_guard_count'] for job in jobs),
                semantic_reviewed_count=sum(job['semantic_reviewed_count'] for job in jobs))


def main():
    sha = subprocess.check_output(['git', '-C', str(WT), 'rev-parse', 'HEAD'], text=True).strip()
    probe = json.loads((REVIEWS / 'TEXTING-WORKER-2256.json').read_text())
    record = audit_probe(probe, sha)
    record['at'] = datetime.now(timezone.utc).isoformat()
    (REVIEWS / 'TEXTING-2256-probe-assertion-audit.json').write_text(json.dumps(record, indent=2) + '\n')
    print('AUDIT_PASS: ' + str(len(record['jobs'])) + ' accepted saved reports; ' +
          str(record['complete_outer_drafts']) + ' complete outer drafts; ' +
          str(record['literal_guard_count']) + ' literal-verified; ' +
          str(record['semantic_reviewed_count']) + ' semantic-reviewed')


if __name__ == '__main__':
    main()
