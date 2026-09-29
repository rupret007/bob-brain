#!/usr/bin/env python3
"""Solo release checks and rollback transaction; never starts council or workers.

Historical vendor gates are superseded by Jeff's 2026-09-29 solo instruction.
Product acceptance tests remain unchanged. Live replay must never send a text.
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone

CODE = Path(__file__).resolve().parents[1]
if __name__ == '__main__' and '--root' in sys.argv:
    os.environ['BOB_ROOT'] = sys.argv[sys.argv.index('--root') + 1]
sys.path[:0] = [str(CODE / d) for d in ('webchat', 'services', 'state', 'reviews')]
from texting_deploy_record import atomic_json, atomic_text, require_disk_space, reserve_recovery, release_recovery
from live_redeploy_check import Client, require

ORDER = ('texting', 'gaps', 'media', 'voice', 'ui', 'instinct', 'remaining')
BASE = 'draft/webbob-clean-0927'


def run(argv, **kw):
    return subprocess.check_output([str(a) for a in argv], text=True, timeout=60, **kw).strip()


def git(*args):
    return run(['git', '-C', CODE, *args])


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_digest(folder):
    values = []
    for path in sorted(Path(folder).rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
            values.append((str(path.relative_to(folder)), digest(path)))
    return hashlib.sha256(json.dumps(values, separators=(',', ':')).encode()).hexdigest()


def identity():
    sha = git('rev-parse', 'HEAD')
    require(git('branch', '--show-current').startswith('draft/'), 'Release requires a draft branch')
    require(not git('status', '--porcelain'), 'Release checkout must be clean')
    return sha


def submit(client, cid, prompt, request=None):
    import uuid
    request = request or str(uuid.uuid4())
    value = client.call('/api/messages', dict(conversation_id=cid, message=prompt, request_id=request))
    deadline = time.monotonic() + 90
    while True:
        answer = next(m for m in value['messages'] if m.get('role') == 'assistant' and m.get('request_id') == request)
        if answer['status'] == 'done':
            require(bool(answer['content'].strip()), 'Empty reply')
            require(not answer.get('task_ids') and not answer.get('task_id'), 'Solo replay dispatched a worker')
            return value, answer
        require(answer['status'] not in ('error', 'cancelled', 'waiting'), 'Replay reply failed')
        require(time.monotonic() < deadline, 'Replay reply timed out')
        time.sleep(.2)
        value = client.call('/api/conversations/' + cid)


def replay(client, root, sha, *, real_reads=False):
    """Authenticated no-send regression; sensitive message content stays in sessions."""
    client.login()
    require(client.call('/api/version')['sha'] == sha, 'Live version differs from candidate')
    cid = client.new()
    receipts = []
    for prompt, provider, expected in (
        ('texting help', 'texting', 'draft'),
        ('yes wbtxt-00000000000000000000000000000000', 'texting', 'Nothing sent.'),
        ('cancel text draft 0000000000000000', 'texting', 'no longer current'),
        ('what version are you?', 'dispatcher', sha[:7]),
    ):
        value, answer = submit(client, cid, prompt)
        require(answer.get('provider') == provider, 'Wrong route for ' + prompt)
        require(expected.lower() in answer['content'].lower(), 'Wrong response for ' + prompt)
        again, duplicate = submit(client, cid, prompt, answer['request_id'])
        require(duplicate == answer and len(again['messages']) == len(value['messages']), 'Idempotency failed')
        receipts.append(dict(prompt=prompt, request_id=answer['request_id'], provider=provider,
                             answer_sha256=hashlib.sha256(answer['content'].encode()).hexdigest(), passed=True))
    if real_reads:
        # Real BlueBubbles reads; do not include thread content/addresses in evidence.
        _, answer = submit(client, cid, 'texts')
        require(answer.get('provider') == 'texting' and answer['content'].startswith('Recent text threads'),
                'BlueBubbles live read failed')
        receipts.append(dict(prompt='texts', provider='texting', passed=True,
                             answer_sha256=hashlib.sha256(answer['content'].encode()).hexdigest()))
    from texting import BlueBubbles
    target = BlueBubbles().chats()[0]['guid'] if real_reads else 'Alex Morgan'
    _, drafted = submit(client, cid, 'draft reply to ' + target + ': Web Bob no-send verification. Cancel this draft.')
    card = drafted.get('text_draft', {})
    require(card.get('state') == 'pending' and card.get('body') == 'Web Bob no-send verification. Cancel this draft.',
            'Draft did not bind the exact recipient/body')
    token = card['confirm_message']
    _, bare = submit(client, cid, 'yes')
    require(bare['content'].startswith('Nothing sent.'), 'Bare yes authorized delivery')
    _, cancelled = submit(client, cid, 'cancel text draft ' + card['id'])
    require(cancelled['content'] == 'Text draft cancelled. Nothing sent.', 'Draft cancel failed')
    _, stale = submit(client, cid, token)
    require('already used, cancelled, or replaced' in stale['content'], 'Cancelled token was accepted')
    receipts.append(dict(check='exact draft, bare approval, cancel, stale token', passed=True))
    from task_dispatch import task_queue
    require(not any(r['conversation_id'] == cid for r in task_queue.tasks(root).values()), 'Replay queued work')
    saved = json.loads((root / 'conductor/webchat/sessions' / (cid + '.json')).read_text())
    require(not saved.get('_texting', {}).get('audit'), 'Replay attempted delivery')
    return dict(all_pass=True, conversation_id=cid, checks=receipts, real_texts_sent=0, queued_workers=0)


def staging(root, sha):
    from app import Chat, Server
    # No model inference needed for these deterministic commands. Real messaging reads
    # are reserved for production. No fixture can authorize a real send.
    from texting_fixture import MockMessaging, OfflineProviders
    from texting import Texting, BlueBubbles, Andrea
    with tempfile.TemporaryDirectory(prefix='solo-staging-') as folder:
        private = Path(folder)
        mock = MockMessaging(private)
        chat = Chat(private / 'conductor/webchat', private, OfflineProviders(),
                    texting=Texting(BlueBubbles(mock.config_db), Andrea(mock.base, mock.token)))
        server = Server(('127.0.0.1', 0), chat)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            proof = replay(Client(f'http://127.0.0.1:{server.server_port}', chat.folder / '.password'), private, sha)
            require(not mock.sends and not mock.unexpected_writes, 'Staging attempted messaging write')
            return dict(scope='real isolated HTTP; synthetic messaging; no workers', **proof)
        finally:
            server.shutdown()
            server.server_close()
            chat.close()
            mock.close()


def checks(root, feature):
    sha = identity()
    out = root / 'conductor/reviews' / f'SOLO-0018-{feature}-{sha[:12]}'
    out.mkdir(mode=0o700, exist_ok=True)
    require_disk_space(root, CODE, 'checks')
    commands = {name: [sys.executable, '-m', 'unittest', 'discover', '-s', name, '-p', 'test_*.py']
                for name in ('webchat', 'services', 'reviews', 'release')}
    commands['eval'] = [sys.executable, 'webchat/bob_parity_eval.py']
    commands['browser'] = [sys.executable, 'webchat/texting_proof.py', '--output-dir', str(out / 'texting-browser')]
    for path in sorted((CODE / 'webchat').glob('test_*.mjs')):
        commands[path.stem] = ['node', str(path)]

    def check(item):
        name, argv = item
        log = out / (name + '.log')
        env = {k: v for k, v in os.environ.items() if not any(s in k.upper() for s in ('KEY', 'TOKEN', 'SECRET', 'PASSWORD'))}
        env.pop('PYTHONPATH', None)
        env.pop('NODE_PATH', None)
        # macOS /var is a symlink: existing repo identity tests expect canonical
        # temporary paths, matching the predecessor release harness.
        env['TMPDIR'] = '/private/tmp'
        env['BOB_PLAYWRIGHT_MODULE'] = str(root / 'conductor/webchat/node_modules/playwright')
        with tempfile.TemporaryDirectory(prefix='solo-tests-', dir='/private/tmp') as tmp, log.open('w') as stream:
            env['BOB_ROOT'] = tmp
            process = subprocess.Popen(argv, cwd=CODE, env=env, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
            deadline = time.monotonic() + 900
            try:
                while process.poll() is None:
                    # Stop our own test groups with headroom before crossing the floor.
                    require(shutil.disk_usage(root).free >= 5 * 1024**3 + 128 * 1024**2,
                            'Tests reached disk safety headroom')
                    require(time.monotonic() < deadline, 'Test suite exceeded deadline')
                    time.sleep(.5)
            except BaseException:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=10)
                raise
        body = log.read_text()
        count = re.search(r'Ran (\d+) tests?', body)
        skipped = re.search(r'skipped=(\d+)', body)
        receipt = dict(command=argv, exit=process.returncode, log=str(log), log_sha256=digest(log),
                       tests=int(count[1]) if count else None, skipped=int(skipped[1]) if skipped else 0)
        print(name + ': ' + str(process.returncode), flush=True)
        return name, receipt

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = dict(pool.map(check, [(n, a) for n, a in commands.items() if n != 'browser']))
    # Browser/listener assertions are serialized after suites that use private listeners.
    name, receipt = check(('browser', commands['browser']))
    results[name] = receipt
    require(identity() == sha, 'Candidate changed during checks')
    passed = all(r['exit'] == 0 and r['skipped'] == 0 for r in results.values())
    record = dict(sha=sha, feature=feature, all_pass=passed, results=results, at=time.time())
    if passed:
        record['staging'] = staging(root, sha)
    atomic_json(out / 'checks.json', record)
    require(passed, 'Offline check failed; inspect ' + str(out))
    print(str(out / 'checks.json'), flush=True)


def verify_gates(sha, feature, check_path, review_path):
    check = json.loads(check_path.read_text())
    review = json.loads(review_path.read_text())
    require(check['sha'] == review['sha'] == sha and check['feature'] == review['feature'] == feature,
            'Stale or wrong-feature release evidence')
    require(check['all_pass'] and check['staging']['all_pass'], 'Tests/evals/staging failed')
    required = {'webchat', 'services', 'reviews', 'release', 'eval', 'browser'}
    required.update(p.stem for p in (CODE / 'webchat').glob('test_*.mjs'))
    require(required <= check['results'].keys(), 'Missing mandatory suite')
    for name in required:
        row = check['results'][name]
        require(row['exit'] == 0 and row['skipped'] == 0 and digest(row['log']) == row['log_sha256'],
                'Failed/skipped/changed check: ' + name)
    require(review['reviewer'] == 'Codex solo' and review['verdict'] == 'PASS' and
            review['checks_sha256'] == digest(check_path) and review['findings'] and
            not review.get('unresolved_blockers'), 'Self-review missing or unresolved')
    return dict(checks_sha256=digest(check_path), self_review_sha256=digest(review_path))


def versions(root, expected):
    result = {}
    origin = (root / 'conductor/webchat/.public-origin').read_text().strip()
    for name, url in (('local', 'http://127.0.0.1:8787'), ('public', origin)):
        client = Client(url, root / 'conductor/webchat/.password')
        client.login()
        result[name] = client.call('/api/version')
        require(result[name]['sha'] == expected, 'Wrong ' + name + ' version')
    return result


def restart(root, pins):
    """Only the web server restarts; no job-runner or council resurrection."""
    from state import lock
    from runtime import screen_sessions
    with lock('supervisor'):
        before = screen_sessions()
        require('svc-job-runner' not in before, 'Solo deployment requires stopped worker runner')
        p = subprocess.run(['lsof', '-t', '-iTCP:8787', '-sTCP:LISTEN'], capture_output=True, text=True)
        pids = p.stdout.split()
        require(p.returncode in (0, 1) and len(pids) <= 1, 'Ambiguous server listener')
        pid = int(pids[0]) if pids else None
        if pid:
            command = run(['ps', '-p', pid, '-o', 'command='])
            require(str(root) in command and '/webchat/app.py' in command, 'Listener ownership mismatch')
        for name, code in pins.items():
            atomic_text(root / 'conductor/state' / (name + '-code-root'), str(code) + '\n')
        if 'svc-webchat' in before:
            run(['screen', '-S', before['svc-webchat'], '-X', 'quit'])
        if pid:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            for _ in range(60):
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    break
                time.sleep(.25)
            else:
                raise RuntimeError('Old web server did not exit')
        env = dict(os.environ, BOB_ROOT=str(root), BOB_WEBCHAT_DRILLS='0')
        run(['screen', '-dmS', 'svc-webchat', '/bin/bash', root / 'conductor/webchat/run.sh'], env=env)
        import urllib.request
        for _ in range(80):
            try:
                with urllib.request.urlopen('http://127.0.0.1:8787/login', timeout=1) as response:
                    if response.status == 200 and response.headers.get('X-Bob-Webchat') == '1':
                        break
            except OSError:
                pass
            time.sleep(.25)
        else:
            raise RuntimeError('New web server did not become healthy')
        after = screen_sessions()
        require(all(after.get(n) == value for n, value in before.items() if n.startswith('svc-') and n != 'svc-webchat'),
                'Unrelated durable service changed')
        require('svc-job-runner' not in after, 'Worker runner unexpectedly started')
        return dict(before=before, after=after, restarted=['svc-webchat'])


def recover(root, record):
    release_recovery(record)
    for name, expected in record.get('snapshot_hashes', {}).items():
        require(source_digest(Path(record['snapshots'][name])) == expected, 'Rollback snapshot changed: ' + name)
    unchanged = False
    try:
        versions(root, record['previous'])
        pins = [Path((root / 'conductor/state' / (name + '-code-root')).read_text().strip()) for name in ('webchat', 'dispatch')]
        unchanged = all(json.loads((p / 'webbob-build.json').read_text())['sha'] == record['previous'] for p in pins)
    except (OSError, ValueError, RuntimeError):
        pass
    if not unchanged:
        restart(root, record['snapshots'])
    record['rollback_restart_needed'] = not unchanged
    record['restored'] = versions(root, record['previous'])
    record.update(rolled_back=True, all_pass=False, status='ROLLED_BACK')


def transaction(root, record, path, activate, live, publish=atomic_json, final_path=None):
    """Any post-activation failure, including final publication, restores predecessor."""
    activated = False
    try:
        require_disk_space(root, CODE, 'before-activation')
        record.update(activated=True, status='ACTIVATING')
        publish(path, record)
        activated = True
        activate()
        record['rounds'] = []
        for index in (1, 2):
            require_disk_space(root, CODE, 'live-round-' + str(index))
            proof = live()
            require(proof.get('all_pass') is True, 'Live replay failed')
            record['rounds'].append(proof)
            publish(path, record)
        record.update(all_pass=True, status='LIVE_PASS', finished_at=time.time())
        publish(path, record)
        if final_path:
            publish(final_path, record)
        release_recovery(record)
    except BaseException as exc:
        record.update(all_pass=False, failure=type(exc).__name__ + ': ' + str(exc))
        if activated:
            try:
                recover(root, record)
            except BaseException as recovery_error:
                record['rollback_error'] = type(recovery_error).__name__ + ': ' + str(recovery_error)
        else:
            release_recovery(record)
        # Rollback happens before attempting any potentially failing evidence write.
        atomic_json(path, record)
        if final_path:
            atomic_json(final_path, record)
        raise


def deploy(args):
    root = args.root
    sha = identity()
    gates = verify_gates(sha, args.feature, args.checks, args.review)
    from runtime import screen_sessions, service_enabled
    require(not service_enabled('job-runner') and not service_enabled('reviewer'), 'Persistent solo shutdown marker missing')
    require(not {'svc-job-runner', 'svc-reviewer'} & screen_sessions().keys(), 'Council/worker service is running')
    index = ORDER.index(args.feature)
    if index:
        prior = json.loads((root / 'conductor/reviews' / ('SOLO-0018-' + ORDER[index - 1] + '-live.json')).read_text())
        require(prior['all_pass'] and prior['sha'] == args.previous and len(prior['rounds']) == 2 and
                all(r['all_pass'] for r in prior['rounds']), 'Predecessor has not passed two live rounds')
    else:
        require(args.previous == 'a777736b3f0a37c82b0c4c62be8c91117c4c9881', 'Initial baseline changed')
    remote = dict(line.split()[::-1] for line in git('ls-remote', 'origin', 'refs/heads/' + BASE).splitlines())
    merge = remote['refs/heads/' + BASE]
    git('fetch', '--no-tags', 'origin', BASE)
    git('merge-base', '--is-ancestor', sha, merge)
    require(not git('diff', '--name-only', sha, merge), 'Clean merge differs from checked tree')
    pr = json.loads(run(['gh', 'pr', 'view', args.pr, '--json', 'headRefOid,baseRefName,isDraft,state']))
    require(pr['headRefOid'] == sha and pr['baseRefName'] == BASE and pr['isDraft'] and
            pr['state'] in ('OPEN', 'MERGED'), 'PR is not the checked draft')
    versions(root, args.previous)
    client = Client('http://127.0.0.1:8787', root / 'conductor/webchat/.password')
    client.login()
    session = client.call('/api/session')
    require(not session.get('active_conversations') and not session.get('active_conversation'), 'Chat reply in flight')
    require_disk_space(root, CODE, 'snapshot')
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    folder = root / 'rollbacks' / ('webbob-solo-' + args.feature + '-' + stamp)
    folder.mkdir(mode=0o700)
    record = dict(sha=sha, feature=args.feature, previous=args.previous, gates=gates, draft_pr=args.pr,
                  rollback=str(folder), all_pass=False, activated=False, snapshots={}, at=time.time())
    for name in ('webchat', 'dispatch'):
        prior = Path((root / 'conductor/state' / (name + '-code-root')).read_text().strip())
        require(json.loads((prior / 'webbob-build.json').read_text())['sha'] == args.previous, 'Pin baseline mismatch')
        snapshot = folder / ('previous-' + name)
        shutil.copytree(prior, snapshot, ignore=shutil.ignore_patterns('.git', '.password', '.session-secret',
            'keys.env', '.env', '.env.*', 'sessions', 'node_modules', '__pycache__', 'uploads', 'evidence', 'task-runs'))
        record['snapshots'][name] = str(snapshot)
    record['snapshot_hashes'] = {name: source_digest(Path(p)) for name, p in record['snapshots'].items()}
    # Freeze tracked candidate bytes; future edits to the worktree cannot change live code.
    release = folder / 'candidate'
    release.mkdir(mode=0o700)
    archive = subprocess.Popen(['git', '-C', str(CODE), 'archive', sha], stdout=subprocess.PIPE)
    extracted = subprocess.run(['tar', '-xf', '-', '-C', str(release)], stdin=archive.stdout)
    archive.stdout.close()
    require(extracted.returncode == archive.wait() == 0, 'Candidate archive failed')
    atomic_json(release / 'webbob-build.json', dict(sha=sha, built_at=datetime.now(timezone.utc).isoformat()))
    path = folder / 'release.json'
    atomic_text(folder / 'rollback.sh', '#!/bin/bash\nset -euo pipefail\n' + shlex.join([
        sys.executable, str(release / 'release/solo.py'), 'rollback', '--root', str(root),
        '--feature', args.feature, '--record', str(path)]) + '\n')
    (folder / 'rollback.sh').chmod(0o700)
    reserve_recovery(path, record)
    atomic_json(path, record)
    origin = (root / 'conductor/webchat/.public-origin').read_text().strip()

    def live():
        pair = versions(root, sha)
        results = [replay(Client(url, root / 'conductor/webchat/.password'), root, sha, real_reads=True)
                   for url in ('http://127.0.0.1:8787', origin)]
        number = len(record.get('rounds', [])) + 1
        browser_path = folder / f'browser-round-{number}.json'
        env = dict(os.environ, BOB_PLAYWRIGHT_MODULE=str(root / 'conductor/webchat/node_modules/playwright'))
        run(['node', CODE / 'webchat/capture_parity.cjs', root, origin, sha,
             folder / f'browser-round-{number}.png', browser_path], env=env)
        browser = json.loads(browser_path.read_text())
        require(browser['pass_check'], 'Live browser check failed')
        return dict(all_pass=all(r['all_pass'] for r in results), versions=pair, endpoints=results,
                    browser=dict(path=str(browser_path), sha256=digest(browser_path), passed=True))

    transaction(root, record, path, lambda: restart(root, dict(webchat=release, dispatch=release)), live,
                final_path=root / 'conductor/reviews' / ('SOLO-0018-' + args.feature + '-live.json'))
    print('LIVE_PASS ' + sha + ' rollback=' + str(folder), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('check', 'deploy', 'rollback'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--feature', choices=ORDER, required=True)
    parser.add_argument('--previous')
    parser.add_argument('--pr')
    parser.add_argument('--checks', type=Path)
    parser.add_argument('--review', type=Path)
    parser.add_argument('--record', type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    os.environ['BOB_ROOT'] = str(args.root)
    def interrupted(signum, frame):
        raise RuntimeError('Release interrupted by signal ' + str(signum))
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, interrupted)
    if args.action == 'check':
        checks(args.root, args.feature)
    elif args.action == 'deploy':
        deploy(args)
    else:
        record = json.loads(args.record.read_text())
        recover(args.root, record)
        atomic_json(args.record, record)


if __name__ == '__main__':
    main()
