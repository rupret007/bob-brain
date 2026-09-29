"""Close out only after all requested PRs and exact build workflows are green."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone

EVIDENCE = Path(__file__).resolve().parent
CONDUCTOR = EVIDENCE.parents[1]
REPO = Path('/Users/jeffstory/Documents/webjam-jeff-test-build')
SHA = '9d44589a081bed69fb45e5857f48c7f5cecb2264'
EXPECTED = {158: 'b11a7c44f79a672328110f0054a86d6106c6e0b4',
            159: '4a75c7ea56f09563826932f0367dffa4e51e724a',
            160: SHA, 161: SHA}
summary = json.loads((EVIDENCE / 'ci-summary.json').read_text())
assert len(summary['runs']) == 6
assert all(r['status'] == 'completed' and r['conclusion'] == 'success'
           and not r['failed'] and not r['pending'] for r in summary['runs'])
stamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
prs = []
for number, expected in EXPECTED.items():
    encoded = subprocess.check_output([
        'gh', 'pr', 'view', str(number), '--repo', 'rupret007/webjam', '--json',
        'number,title,headRefName,headRefOid,baseRefName,isDraft,state,url,statusCheckRollup'
    ], text=True)
    pr = json.loads(encoded)
    assert pr['headRefOid'] == expected, (number, pr['headRefOid'])
    assert pr['isDraft'] and pr['state'] == 'OPEN', number
    assert pr['statusCheckRollup'], number
    for check in pr['statusCheckRollup']:
        if check['__typename'] == 'CheckRun':
            assert check['status'] == 'COMPLETED', (number, check['name'])
            assert check['conclusion'] in ('SUCCESS', 'SKIPPED', 'NEUTRAL'), (number, check)
        else:
            assert check['state'] == 'SUCCESS', (number, check)
    (EVIDENCE / f'pr-{number}-final.json').write_text(json.dumps(pr, indent=2) + '\n')
    prs.append(pr)

assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip() == SHA
assert not subprocess.check_output(['git', 'diff', 'HEAD', '--'], cwd=REPO)
receipt = json.loads((EVIDENCE / 'local-build.json').read_text())
app = Path(receipt['app'])
assert (app / 'Contents/Resources/webjam-build-id.txt').read_text().strip() == SHA
assert hashlib.sha256((app / 'Contents/MacOS/WebJam').read_bytes()).hexdigest() == receipt['binary_sha256']
preserved = json.loads((EVIDENCE / 'provenance.json').read_text())
original = preserved['original_worktree']
assert subprocess.check_output(['git', '-C', original, 'rev-parse', 'HEAD'], text=True).strip() == preserved['original_head']
assert subprocess.check_output(['git', '-C', original, 'status', '--short'], text=True) == preserved['original_status']
assert hashlib.sha256(subprocess.check_output([
    'git', '-C', original, 'diff', '--', 'tests/test_art_host_platforms.py'
])).hexdigest() == preserved['local_fix_sha256']

sys.path.insert(0, str(CONDUCTOR / 'services'))
from state import alert, atomic_write, lock

result_path = CONDUCTOR / 'reviews/WEBJAM-TEST-BUILD-RESULT.md'
result = result_path.read_text()
result = re.sub(r'^Local build and delivery complete\..*$',
                'Complete: local app delivered and CI green on #158, #159, #160, and #161. Verified ' + stamp + '.',
                result, count=1, flags=re.M)
result = re.sub(r'^- CI: .*$',
                '- CI: **GREEN** on all four open draft PRs. All six new push/PR workflows completed successfully; manual certification, signing, and release jobs were skipped by design.',
                result, count=1, flags=re.M)
result = result.replace('## Local build and validation\n',
    '## Final CI evidence\n\n' +
    '| Draft PR | Exact head | State |\n| --- | --- | --- |\n' +
    ''.join(f"| [#{p['number']}]({p['url']}) | `{p['headRefOid']}` | GREEN; still draft |\n" for p in prs) +
    '\nThe combined build CI test job passed **10,571 tests across 458 modules**, with 41 explicit skips. '
    'The real Jamulus 3.12.2/3.12.3 integrations, both component update-input checks, mobile simulators, '
    'transport/reference-service checks, and Windows/Linux/Apple Silicon/Intel desktop builds passed.\n\n' +
    '\n'.join(f"- [{r['branch']} — run {r['id']}](https://github.com/rupret007/webjam/actions/runs/{r['id']}): SUCCESS." for r in summary['runs']) +
    '\n\n## Local build and validation\n')
atomic_write(result_path, result)

notes_path = Path('/Users/jeffstory/Desktop/WEBJAM-TEST-NOTES.md')
notes = notes_path.read_text()
notes = re.sub(r'^- CI: .*$', '- CI: green on #158, #159, #160, and #161; verified ' + stamp + '.',
               notes, count=1, flags=re.M)
notes = notes.replace('About may still say 0.28.4', 'About still says 0.28.4')
notes = notes.replace('623 tests across all 17 changed test modules, plus 45 subtests, passed.',
    'Full CI passed: 10,571 tests across 458 modules, with 41 explicit skips; all desktop package and integration jobs passed. '
    'Locally, 623 tests across all 17 changed test modules, plus 45 subtests, passed.')
assert len(re.findall(r'^[1-5]\. ', notes, re.M)) == 5
atomic_write(notes_path, notes)

body = '''Combine #158's door/copy work, #159's host startup checklist, and #160's Music rehearsal recap into one local macOS test candidate for Jeff. The branch includes the original #160 worktree's local platform-test correction. The ready host checklist now shows completed setup and the Copy Invite action, with visible/accessibility transition coverage for all four profiles. The non-macOS platform assertion reads the dedicated host-reason label.

CI is green on #158, #159, #160, and this draft. All six new push/PR workflows passed, including the full suite (10,571 tests, 41 explicit skips on the combined build), real Jamulus integrations, mobile simulator checks, and all four desktop package targets. Locally, 623 changed-module tests plus 45 subtests and the UX smoke gate passed.

Built the Apple Silicon app from `9d44589a081bed69fb45e5857f48c7f5cecb2264` using v0.28.4's hashed release dependencies, unchanged spec, newly compiled transport, and checksum-verified native release components. Delivered `~/Desktop/WebJam-TEST-9d44589.app` and `~/Desktop/WEBJAM-TEST-NOTES.md`. The actual Desktop copy passed native startup, frozen Reference Studio/Pocket Stage probes, transport/headless-companion verification, and deep signature checks; quarantine is cleared.

Known gap: the live component-catalog fetch returns an HTTP error on this Mac in both this app and official v0.28.4. Bundled Jamulus 3.12.2 is included and verified. Real multi-machine audio/recording and Jeff's manual feel review remain untested.

Draft only. No merge, undraft, force push, tag, release, or Final Build action. Full local record: conductor/reviews/WEBJAM-TEST-BUILD-RESULT.md.
'''
body_path = EVIDENCE / 'pr-body.md'
atomic_write(body_path, body)
subprocess.run(['gh', 'pr', 'edit', '161', '--repo', 'rupret007/webjam',
                '--body-file', str(body_path)], check=True)

with lock('queue'):
    path = CONDUCTOR / 'reviews/WEBJAM-TEST-BUILD-SCHEDULER.md'
    notice = path.read_text().replace('Status: ACTIVE', 'Status: COMPLETE')
    notice += '\nCompleted: ' + stamp + '. App delivered, all requested CI green.\n'
    notice += 'Result: reviews/WEBJAM-TEST-BUILD-RESULT.md. The external session hold can expire when svc-webjam-test exits; this task made no global scheduler changes.\n'
    atomic_write(path, notice)
alert('webjam-test-build')
atomic_write(result_path, result_path.read_text() +
             '\nScheduler closeout: notice marked COMPLETE at ' + stamp +
             '; this task’s alert cleared. The session-based hold can expire when svc-webjam-test exits.\n')
final = dict(completed_at=stamp, sha=SHA, pr=161, app=str(app),
             notes=str(notes_path), result=str(result_path), all_prs_draft=True,
             all_requested_ci_green=True, original_worktree_preserved=True)
atomic_write(EVIDENCE / 'completion.json', json.dumps(final, indent=2) + '\n')
print(json.dumps(final, indent=2))
