"""Verify the live signed catalog and native launch of the delivered app."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

evidence = Path(__file__).resolve().parent
repo = Path('/Users/jeffstory/Documents/webjam-jeff-test-build')
sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
app = Path('/Users/jeffstory/Desktop') / ('WebJam-TEST-' + sha[:7] + '.app')
binary = app / 'Contents/MacOS/WebJam'
assert (app / 'Contents/Resources/webjam-build-id.txt').read_text().strip() == sha
prior = (evidence / 'package-and-smoke.log').read_text()
for marker in ('WebJam Reference Studio frozen-runtime smoke passed',
               'WebJam Pocket Stage frozen-runtime smoke passed',
               'Packaged transport verification passed.'):
    assert marker in prior

# Exercise the app's built-in, fixed-URL signed catalog probe. The separate
# publication-gate wrapper requires release-workflow inputs; no release is
# being made here. The app itself verifies its catalog signature and policy.
with tempfile.TemporaryDirectory(prefix='webjam-component-catalog-smoke-') as scratch:
    result = Path(scratch) / 'result.json'
    environment = {**os.environ, 'QT_QPA_PLATFORM': 'offscreen',
                   'WEBJAM_SMOKE_COMPONENT_CATALOG_RUNTIME': '1',
                   'WEBJAM_SMOKE_COMPONENT_CATALOG_RESULT': str(result)}
    completed = subprocess.run([str(binary)], cwd=app.parent, env=environment,
                               capture_output=True, text=True, timeout=60)
    if completed.returncode:
        catalog = dict(status='failed', exit_code=completed.returncode,
                       stderr=completed.stderr,
                       limitation='Live catalog fetch failed; compare with baseline-live-catalog.json.')
    else:
        catalog = json.loads(result.read_text())
        assert catalog['status'] == 'passed'
        assert catalog['webjam_version'] == '0.28.4'
        assert catalog['target'] == 'macos-arm64'
        assert catalog['available_version'] == '3.12.3'
        assert catalog['catalog_sequence'] >= 6
        assert catalog['component_count'] == 8
        assert catalog['trust_status'] == 'ready'
    (evidence / 'frozen-catalog-result.json').write_text(json.dumps(catalog, indent=2) + '\n')
    print('Live catalog smoke:', catalog['status'], flush=True)

launch_log = evidence / 'desktop-launch.log'
environment = {**os.environ, 'WEBJAM_LOG_FILE': str(launch_log),
               'WEBJAM_SMOKE_LAUNCH_ONLY': '1', 'WEBJAM_SMOKE_EXIT_MS': '3000'}
environment.pop('QT_QPA_PLATFORM', None)
subprocess.run([str(binary)], cwd=app.parent, env=environment, check=True, timeout=45)
contents = launch_log.read_text()
assert 'Starting Conductor UI' in contents
assert 'WebJam failed during startup' not in contents
assert 'Unhandled WebJam UI error' not in contents
subprocess.run(['codesign', '--verify', '--deep', '--strict', str(app)], check=True)
assert 'com.apple.quarantine' not in subprocess.check_output(['xattr', '-r', str(app)], text=True)
receipt = dict(sha=sha, app=str(app), architecture='arm64', version='0.28.4',
               signing='ad-hoc', quarantine_cleared=True, native_launch_exit=0,
               frozen_smokes_passed=['reference_studio', 'pocket_stage'],
               live_catalog=catalog,
               component_source='checksum-verified official v0.28.4 macos-arm64 archive',
               build_method='release lock + webjam.spec + locally built transport + release component staging',
               binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest())
(evidence / 'local-build.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt, indent=2), flush=True)
