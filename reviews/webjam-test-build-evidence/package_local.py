"""Finish the local test bundle using the v0.28.4 macOS packaging path."""
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys

ROOT = Path('/Users/jeffstory/Documents/webjam-jeff-test-build')
EVIDENCE = Path(__file__).resolve().parent
PYTHON = ROOT / '.venv-build/bin/python'
APP = ROOT / 'dist/WebJam.app'
BASELINE = ROOT / 'build/v0284-baseline/extracted/WebJam.app'


def run(*args, **kwargs):
    print('RUN', ' '.join(map(str, args)), flush=True)
    kwargs.setdefault('cwd', ROOT)
    return subprocess.run(list(map(str, args)), check=True, **kwargs)


sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
assert not subprocess.check_output(['git', 'diff', 'HEAD', '--'], cwd=ROOT)
assert (APP / 'Contents/Resources/webjam-build-id.txt').read_text().strip() == sha
assert plistlib.loads((APP / 'Contents/Info.plist').read_bytes())['CFBundleShortVersionString'] == '0.28.4'
run(PYTHON, 'tools/runtime_dependency_policy.py', '--verify-bundle', APP, '--target', 'macos-arm64')
run('packaging/macos/verify-jamulus-headless-client.sh',
    BASELINE / 'Contents/Resources/JamulusHeadlessClient.app', 'arm64',
    BASELINE / 'Contents/Resources/JamulusHeadlessClient.sha256')

resources = APP / 'Contents/Resources'
for name in ('Jamulus.app', 'JamulusServer.app', 'JamulusHeadlessClient.app'):
    assert not (resources / name).exists()
    run('ditto', BASELINE / 'Contents/Resources' / name, resources / name)
shutil.copy2(BASELINE / 'Contents/Resources/JamulusHeadlessClient.sha256', resources)
shutil.copy2(ROOT / 'licenses/JAMULUS_COPYING.txt', resources / 'THIRD_PARTY_LICENSES')
transport = APP / 'Contents/MacOS/webjam-fabric'
shutil.copy2(ROOT / 'transport/build/package/webjam-fabric', transport)
transport.chmod(0o755)
for name in ('Jamulus.app', 'JamulusServer.app'):
    run('codesign', '--force', '--deep', '--sign', '-', resources / name)
run('codesign', '--force', '--sign', '-', transport)
(resources / 'webjam-fabric.sha256').write_text(hashlib.sha256(transport.read_bytes()).hexdigest() + '\n')
headless = resources / 'JamulusHeadlessClient.app/Contents/MacOS/JamulusHeadlessClient'
(resources / 'JamulusHeadlessClient.sha256').write_text(
    hashlib.sha256(headless.read_bytes()).hexdigest() +
    '  JamulusHeadlessClient.app/Contents/MacOS/JamulusHeadlessClient\n')
run(PYTHON, '-m', 'tests.support.verify_packaged_transport', '--binary', transport,
    '--manifest', resources / 'webjam-fabric.sha256', '--build-id', sha, '--machine', 'arm64')
run('packaging/macos/verify-jamulus-headless-client.sh',
    resources / 'JamulusHeadlessClient.app', 'arm64', resources / 'JamulusHeadlessClient.sha256')
run('.github/scripts/assert-no-appdata-usage.sh', APP)
run('codesign', '--force', '--sign', '-', APP)
run('codesign', '--verify', '--deep', '--strict', APP)

destination = Path('/Users/jeffstory/Desktop') / ('WebJam-TEST-' + sha[:7] + '.app')
assert not destination.exists(), 'Do not overwrite an existing Desktop test app'
run('ditto', APP, destination)
run('xattr', '-dr', 'com.apple.quarantine', destination)
run('codesign', '--verify', '--deep', '--strict', destination)
attributes = subprocess.check_output(['xattr', '-r', str(destination)], text=True)
assert 'com.apple.quarantine' not in attributes
assert (destination / 'Contents/Resources/webjam-build-id.txt').read_text().strip() == sha

binary = destination / 'Contents/MacOS/WebJam'
environment = {**os.environ, 'QT_QPA_PLATFORM': 'offscreen'}
for probe in ('reference_studio', 'pocket_stage'):
    run(PYTHON, '-m', 'tests.support.run_frozen_' + probe + '_smoke',
        '--binary', binary, '--cwd', destination.parent, env=environment)
run(sys.executable, EVIDENCE / 'verify_desktop.py')
