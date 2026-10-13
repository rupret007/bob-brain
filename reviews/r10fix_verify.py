#!/usr/bin/env python3
"""Run all six offline R10 checks with the existing release dependency setup.

No deployment, network dependency installation, or live provider probe is run.
Browser proofs use isolated synthetic fixtures and local loopback listeners.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile

CODE = Path(__file__).resolve().parents[1]
SUITES = ('webchat', 'services', 'reviews', 'release')
PROOFS = {'cold-browser': 'cold_start_proof.py',
          'remaining-browser': 'remaining_proof.py'}


def stop_check(process):
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        pass
    finally:
        # A browser grandchild can outlive its Python parent after TERM.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=10)


def check(name, output, environment):
    if name in SUITES:
        command = [sys.executable, '-m', 'unittest', 'discover', '-s', name,
                   '-p', 'test_*.py']
    else:
        command = [sys.executable, 'webchat/' + PROOFS[name],
                   '--output-dir', str(output / name)]
    log = output / (name + '.log')
    env = environment.copy()
    with tempfile.TemporaryDirectory(prefix='r10fix-check-', dir=env['TMPDIR']) as root:
        env['BOB_ROOT'] = root
        with log.open('w') as stream:
            process = subprocess.Popen(command, cwd=CODE, env=env, stdout=stream,
                                       stderr=subprocess.STDOUT, start_new_session=True)
            try:
                exit_code = process.wait(timeout=900)
            except subprocess.TimeoutExpired:
                stop_check(process)
                stream.write('\nR10 verification timed out after 900 seconds.\n')
                exit_code = 124
            except BaseException:
                stop_check(process)
                raise
    body = log.read_text()
    counts = re.findall(r'^Ran (\d+) tests? in [^\r\n]+$', body, re.M)
    summaries = re.findall(r'^(?:OK|FAILED)(?: \([^\r\n]*\))?$', body, re.M)
    summary = summaries[-1] if summaries else ''
    skipped = re.search(r'\bskipped=(\d+)\b', summary)
    receipt = dict(command=command, exit=exit_code, log=str(log),
                   log_sha256=hashlib.sha256(log.read_bytes()).hexdigest(),
                   tests=int(counts[-1]) if counts else None,
                   skipped=int(skipped[1]) if skipped else 0)
    receipt['all_pass'] = (exit_code == 0 and receipt['skipped'] == 0
                           and (name not in SUITES or (bool(receipt['tests'])
                                                      and summary.startswith('OK'))))
    (output / (name + '-receipt.json')).write_text(json.dumps(receipt, indent=2) + '\n')
    print(f"{name}: exit={exit_code}, tests={receipt['tests']}, skipped={receipt['skipped']} ({log})",
          flush=True)
    return name, receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path,
                        help='receipt directory (default: a unique private temporary directory)')
    args = parser.parse_args()
    os.umask(0o077)
    output = (args.output_dir or Path(tempfile.mkdtemp(prefix='r10fix-verification-'))).resolve()
    output.mkdir(parents=True, exist_ok=True)
    # Even setup failure must invalidate an earlier successful run here.
    (output / 'checks.json').write_text(json.dumps(dict(all_pass=False), indent=2) + '\n')
    print('R10 verification receipts: ' + str(output), flush=True)

    # Match release/solo.py checks: isolate credentials, model attribution, and
    # fixture storage. Canonical TMPDIR preserves repository identity on macOS.
    env = {key: value for key, value in os.environ.items()
           if not any(word in key.upper() for word in ('KEY', 'TOKEN', 'SECRET', 'PASSWORD'))
           and not key.startswith(('BOB_GENERATION_', 'BOB_QUALIFICATION_'))
           and key not in ('BOB_REQUIRE_GENERATION_BUDGET', 'PYTHONPATH', 'NODE_PATH',
                           'BOB_ANDREA_WEBBOB_CONFIG', 'ANDREA_WEBBOB_CONFIG_PATH')}
    env['TMPDIR'] = str(Path('/tmp').resolve())
    env['PYTHONOPTIMIZE'] = '0'
    sys.path.insert(0, str(CODE / 'webchat'))
    from proof_runtime import playwright_environment
    env = playwright_environment(CODE / 'webchat', env)
    # Fail before discovery if its unchanged optional browser test would skip.
    subprocess.run(['node', '-e', 'require(process.env.BOB_PLAYWRIGHT_MODULE)'],
                   cwd=CODE / 'webchat', env=env, check=True, timeout=15)
    sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=CODE, text=True).strip()
    (output / 'checks.json').write_text(json.dumps(dict(sha=sha, all_pass=False), indent=2) + '\n')
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = dict(pool.map(lambda name: check(name, output, env), SUITES))
    # Browser/listener assertions run after the independent discovery suites.
    for name in PROOFS:
        _, results[name] = check(name, output, env)
    passed = all(receipt['all_pass'] for receipt in results.values())
    summary = dict(sha=sha, all_pass=passed, results=results,
                   environment={key: env[key] for key in ('TMPDIR', 'BOB_PLAYWRIGHT_MODULE')})
    (output / 'checks.json').write_text(json.dumps(summary, indent=2) + '\n')
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
