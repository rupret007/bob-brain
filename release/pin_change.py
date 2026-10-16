#!/usr/bin/env python3
"""Fail-closed Andrea pin-change verifier for the Web Bob admission gate.

The conductor gate currently refuses any `release/` diff versus GATE_BASE.
This module is the only exception path: it may allow a change if and only if
the entire attestation chain holds. Any missing condition is needs_jeff.
Environment overrides never relax a check.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

CODE = Path(__file__).resolve().parents[1]
GATE_BASE = 'ca378fd00b3d0e26eefea69e2dafa221b1e0b017'
PIN_PATH = 'release/andrea-bridge.json'
ALLOWED_PIN_KEYS = frozenset(('sha', 'worktree'))
RECEIPT_NAMES = ('major', 'docs', 'build')
ANDREA_REPO = 'rupret007/Andrea_NanoBot'
SHA_RE = re.compile(r'^[0-9a-f]{40}$')
NEEDS_JEFF = 'needs_jeff'
ALLOWED = 'allowed'

# Any of these in the process environment is an override attempt.
OVERRIDE_ENV = frozenset((
    'ANDREA_SHA',
    'ANDREA_PIN_SHA',
    'ANDREA_BRIDGE_SHA',
    'ANDREA_RECEIPT_DIR',
    'ANDREA_RECEIPT_PATH',
    'ANDREA_RECEIPTS',
    'ANDREA_ON_MAIN',
    'ANDREA_MAIN_SHA',
    'ANDREA_GIT',
    'BOB_ANDREA_SHA',
    'BOB_ANDREA_RECEIPT_DIR',
    'BOB_ANDREA_WEBBOB_CONFIG',
    'ANDREA_WEBBOB_CONFIG_PATH',
    'BOB_PIN_OVERRIDE',
    'WEBBOB_GATE_ALLOW_RELEASE',
    'WEBBOB_GATE_BASE',
    'WEBBOB_PIN_CHANGE_ALLOW',
    'PIN_CHANGE_ALLOW',
    'RECEIPT_GUARD_SKIP',
    'JEFF_ACK_OVERRIDE',
    'SCORE_ONLY_N',
    'SCORE_ONLY_ROUNDS',
    'SCORE_ONLY_RETRIES',
    'SCORE_ONLY_UNPARK',
))


class FailClosed(RuntimeError):
    """Admission refused. Gate callers treat this as needs_jeff."""

    def __init__(self, reason):
        super().__init__(reason)
        self.status = NEEDS_JEFF
        self.reason = reason


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sha12(sha):
    return sha[:12]


def current_receipt_dir(root, sha):
    return Path(root) / 'conductor/receipts' / ('andrea-' + sha12(sha))


def historical_receipt_dir(root, sha):
    return Path(root) / 'conductor/reviews' / ('SOLO-0018-andrea-bridge-' + sha12(sha))


def pin_ack_path(root, sha):
    return Path(root) / 'conductor/acks' / ('jeff-andrea-pin-' + sha12(sha) + '.json')


def protected_ack_log(root):
    return Path(root) / 'conductor/acks/protected-jeff-ack.jsonl'


def env_overrides(environ=None):
    environ = os.environ if environ is None else environ
    return sorted(name for name in OVERRIDE_ENV if name in environ)


def guard_env(environ=None):
    found = env_overrides(environ)
    if found:
        raise FailClosed('env overrides present: ' + ','.join(found))


def require_readonly(path, label):
    path = Path(path)
    if path.is_symlink() or not path.exists():
        raise FailClosed(label + ' missing or symlink')
    mode = path.stat().st_mode
    if mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH):
        raise FailClosed('writable ' + label)
    if not (path.is_file() or path.is_dir()):
        raise FailClosed(label + ' is not a regular file or directory')


def require_readonly_file(path, label):
    path = Path(path)
    require_readonly(path, label)
    if not path.is_file() or path.is_symlink():
        raise FailClosed(label + ' is not a regular file')


def require_sha(sha, label='sha'):
    if not isinstance(sha, str) or not SHA_RE.fullmatch(sha):
        raise FailClosed(label + ' is not a 40-char commit')
    return sha


def andrea_on_main(sha, *, andrea_git=None, inspect=None):
    require_sha(sha)
    if inspect is not None:
        return bool(inspect(sha))
    if not andrea_git:
        return False
    repo = Path(andrea_git)
    if repo.is_symlink() or not (repo / '.git').exists():
        return False
    try:
        subprocess.check_output(
            ['git', '-C', str(repo), 'rev-parse', '--verify', '--quiet', sha + '^{commit}'],
            stderr=subprocess.DEVNULL)
        subprocess.check_call(
            ['git', '-C', str(repo), 'merge-base', '--is-ancestor', sha, 'refs/heads/main'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, OSError):
        return False
    return True


def baseline_pin(code=CODE, show=None, base=GATE_BASE):
    if show is not None:
        return json.loads(show(base + ':' + PIN_PATH))
    try:
        raw = subprocess.check_output(
            ['git', '-C', str(code), 'show', base + ':' + PIN_PATH],
            text=True, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, OSError) as exc:
        raise FailClosed('baseline pin unreadable') from exc
    return json.loads(raw)


def release_diff_names(code=CODE, base=GATE_BASE, names=None):
    if names is not None:
        return list(names)
    try:
        raw = subprocess.check_output(
            ['git', '-C', str(code), 'diff', '--name-only', '-z', base, '--', 'release/'],
            text=True)
    except (subprocess.CalledProcessError, OSError) as exc:
        raise FailClosed('release/ diff unreadable') from exc
    return [name for name in raw.split('\0') if name]


def load_pin(path):
    path = Path(path)
    require_readonly_file(path, 'andrea pin')
    try:
        pin = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise FailClosed('andrea pin unreadable') from exc
    if not isinstance(pin, dict):
        raise FailClosed('andrea pin is not an object')
    return pin


def pin_key_delta(old, new):
    if set(old) != set(new):
        extra = sorted(set(new) - set(old) | set(old) - set(new))
        raise FailClosed('extra keys: ' + ','.join(extra))
    changed = sorted(key for key in new if old.get(key) != new.get(key))
    illegal = [key for key in changed if key not in ALLOWED_PIN_KEYS]
    if illegal:
        raise FailClosed('extra keys: ' + ','.join(illegal))
    return changed


def receipt_dir(root, sha, *, baseline_sha=None):
    require_sha(sha)
    current = current_receipt_dir(root, sha)
    historical = historical_receipt_dir(root, sha)
    if current.exists():
        if current.is_symlink() or not current.is_dir():
            raise FailClosed('current Andrea receipts are not a directory')
        return current, 'current'
    if baseline_sha and sha == baseline_sha and historical.exists():
        if historical.is_symlink() or not historical.is_dir():
            raise FailClosed('historical Andrea receipts are not a directory')
        return historical, 'historical'
    raise FailClosed('Andrea receipts missing')


def _blob_path(folder, digest_hex, label):
    blob = Path(folder) / 'blobs' / digest_hex
    require_readonly_file(blob, label + ' blob')
    if digest(blob) != digest_hex:
        raise FailClosed('receipt hash mismatch')
    return blob


def receipt_guard(folder, sha, environ=None):
    """Exit 0, content-addressed log blob, no env overrides, config hash match."""
    guard_env(environ)
    folder = Path(folder)
    require_readonly(folder, 'Andrea receipt directory')
    require_sha(sha)
    results = []
    config_hashes = set()
    for name in RECEIPT_NAMES:
        path = folder / (name + '.json')
        require_readonly_file(path, name + ' receipt')
        try:
            row = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise FailClosed(name + ' receipt unreadable') from exc
        if row.get('sha') != sha:
            raise FailClosed(name + ' receipt sha mismatch')
        if row.get('exit') != 0:
            raise FailClosed(name + ' receipt exit is not 0')
        log_sha = row.get('log_sha256')
        config_sha = row.get('config_sha256')
        if not isinstance(log_sha, str) or not re.fullmatch(r'^[0-9a-f]{64}$', log_sha):
            raise FailClosed(name + ' log sha256 missing')
        if not isinstance(config_sha, str) or not re.fullmatch(r'^[0-9a-f]{64}$', config_sha):
            raise FailClosed(name + ' config hash missing')
        expected_log = 'blobs/' + log_sha
        if row.get('log') != expected_log:
            raise FailClosed(name + ' log is not the content-addressed blob')
        blob = _blob_path(folder, log_sha, name + ' log')
        if digest(folder / expected_log) != log_sha:
            raise FailClosed(name + ' receipt hash mismatch')
        _blob_path(folder, config_sha, 'config')
        config_hashes.add(config_sha)
        results.append(dict(row, name=name, path=str(path), receipt_sha256=digest(path),
                            log_blob=str(blob)))
    if len(config_hashes) != 1:
        raise FailClosed('receipt config hash mismatch')
    return results


def receipt_hashes(results):
    return {row['name']: row['receipt_sha256'] for row in results}


def load_andrea_receipts(root, sha, *, baseline_sha=None, environ=None):
    folder, _source = receipt_dir(root, sha, baseline_sha=baseline_sha)
    return receipt_guard(folder, sha, environ=environ)


def verify_jeff_ack(root, sha, hashes):
    require_sha(sha)
    ack_path = pin_ack_path(root, sha)
    log_path = protected_ack_log(root)
    if not ack_path.exists():
        raise FailClosed('unsigned pin')
    require_readonly_file(ack_path, 'Jeff ack')
    require_readonly_file(log_path, 'protected ack log')
    try:
        ack = json.loads(ack_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise FailClosed('unsigned pin') from exc
    if ack.get('sha') != sha:
        raise FailClosed('unsigned pin')
    named = ack.get('receipt_sha256')
    if not isinstance(named, dict) or named != hashes:
        raise FailClosed('unsigned pin')
    ack_sha = digest(ack_path)
    matched = False
    try:
        lines = log_path.read_text().splitlines()
    except OSError as exc:
        raise FailClosed('protected ack log unreadable') from exc
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise FailClosed('protected ack log corrupt') from exc
        if (row.get('sha') == sha and row.get('ack_sha256') == ack_sha and
                row.get('receipt_sha256') == hashes):
            matched = True
            break
    if not matched:
        raise FailClosed('unsigned pin')
    return dict(path=str(ack_path), sha256=ack_sha)


def verdict(status, reason, **extra):
    row = dict(status=status, reason=reason)
    row.update(extra)
    return row


def verify_pin_change(root, *, code=CODE, base=GATE_BASE, changed_files=None,
                      old_pin=None, new_pin=None, on_main=None, andrea_git=None,
                      baseline_sha=None, environ=None):
    """Return an allowed/needs_jeff verdict. Never raises past FailClosed mapping."""
    try:
        return _verify_pin_change(
            root, code=code, base=base, changed_files=changed_files,
            old_pin=old_pin, new_pin=new_pin, on_main=on_main,
            andrea_git=andrea_git, baseline_sha=baseline_sha, environ=environ)
    except FailClosed as exc:
        return verdict(NEEDS_JEFF, exc.reason)


def _verify_pin_change(root, *, code, base, changed_files, old_pin, new_pin,
                       on_main, andrea_git, baseline_sha, environ):
    guard_env(environ)
    names = release_diff_names(code, base, changed_files)
    if not names:
        return verdict(ALLOWED, 'release/ unchanged versus gate base', base=base)
    unexpected = [name for name in names if name != PIN_PATH]
    if unexpected:
        raise FailClosed('extra release/ file change: ' + ','.join(unexpected))
    if names != [PIN_PATH]:
        raise FailClosed('extra release/ file change')
    if old_pin is None:
        old_pin = baseline_pin(code, base=base)
    if new_pin is None:
        new_pin = load_pin(Path(code) / PIN_PATH)
    changed = pin_key_delta(old_pin, new_pin)
    if not changed:
        return verdict(ALLOWED, 'release/andrea-bridge.json identical after parse', base=base)
    sha = require_sha(new_pin.get('sha'), 'pin sha')
    if not andrea_on_main(sha, andrea_git=andrea_git, inspect=on_main):
        raise FailClosed('non-main sha')
    if baseline_sha is None:
        baseline_sha = old_pin.get('sha') if isinstance(old_pin.get('sha'), str) else None
    results = load_andrea_receipts(root, sha, baseline_sha=baseline_sha, environ=environ)
    hashes = receipt_hashes(results)
    ack = verify_jeff_ack(root, sha, hashes)
    return verdict(
        ALLOWED, 'attested andrea pin change',
        sha=sha, worktree=new_pin.get('worktree'), changed_keys=changed,
        receipt_sha256=hashes, ack_sha256=ack['sha256'], source=results[0].get('path'))


def main(argv=None):
    parser = argparse.ArgumentParser(description='Fail-closed Andrea pin-change verifier')
    parser.add_argument('--root', required=True, help='Conductor root that holds receipts and acks')
    parser.add_argument('--code', default=str(CODE), help='Web Bob checkout')
    parser.add_argument('--base', default=GATE_BASE, help='Gate baseline commit')
    parser.add_argument('--andrea-git', default='', help='Local Andrea_NanoBot checkout used to prove main membership')
    args = parser.parse_args(argv)
    row = verify_pin_change(
        args.root, code=Path(args.code), base=args.base,
        andrea_git=args.andrea_git or None)
    print(json.dumps(row, sort_keys=True))
    return 0 if row['status'] == ALLOWED else 1


if __name__ == '__main__':
    sys.exit(main())
