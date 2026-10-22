#!/usr/bin/env python3
"""Read-only host-shell source binding inventory; never readiness or authority."""
import argparse
import json
from pathlib import Path
import re
import stat
import subprocess
import os
import sys

# Import only the selected checkout's observation readers, never Chat (which
# initializes persistent state) or an installed scheduler/provider adapter.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'webchat'))
from build_info import load_build, _git
from shared_chat import SharedChatContext

REQUIRED = ('MONITOR.md', 'NEEDS_JEFF.md', 'MORNING_DIGEST.md', 'Mini chat/HANDOFF.md')
AUTHORITIES = ('cluster/control_plane/coordination.py',
               'cluster/control_plane/node_control.py',
               'cluster/control_plane/owner_task_scheduler.py')


def _authority_file(install, name):
    """Check installation metadata, without reading/importing executable code."""
    path = install / name
    row = {'component': name, 'state': 'unavailable'}
    try:
        if path.resolve(strict=True) != path:
            row['unavailable_reason'] = 'symlink_or_noncanonical_path'
            return row
        for candidate in (path, *path.parents):
            info = candidate.stat()
            if info.st_uid not in (0, os.getuid()) or stat.S_IMODE(info.st_mode) & 0o022:
                row['unavailable_reason'] = 'unsafe_owner_or_permissions'
                return row
        if stat.S_ISREG(path.stat().st_mode):
            row['state'] = 'present_not_verified'
        else:
            row['unavailable_reason'] = 'not_regular_file'
    except FileNotFoundError:
        row['unavailable_reason'] = 'missing'
    except OSError:
        row['unavailable_reason'] = 'metadata_unreadable'
    return row


def inventory(expected_sha, *, context=None, install=None):
    if not re.fullmatch(r'[0-9a-f]{40}', expected_sha or ''):
        raise ValueError('Expected SHA must be the full lowercase commit SHA')
    context = context if context is not None else SharedChatContext.configured()
    install = Path(install or '~/storypool-install').expanduser().absolute()
    try:
        checkout_sha = _git(ROOT, 'rev-parse', 'HEAD')
        clean = not _git(ROOT, 'status', '--porcelain', '--untracked-files=normal')
        build_sha = load_build(ROOT)['sha']
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
        checkout_sha, build_sha, clean = None, None, False
    snapshot = context.snapshot(include_engines=False)
    rows = []
    for source in snapshot['sources']:
        name = source['source']
        if name == 'Mini chat/HANDOFF.md':
            path = context.folder / 'HANDOFF.md'
        elif 'synced source copy' in source.get('provenance', '') or context.source_folder is None:
            path = context.folder / name
        else:
            path = context.source_folder / source.get('source_path', name)
        # Never output the observation text, exception payloads, credentials or
        # approval journal. Paths are host configuration, not execution input.
        rows.append({key: source[key] for key in
                     ('source', 'state', 'observed_at', 'freshness', 'truncated', 'provenance')
                     if key in source} | {'path': str(path.absolute()), 'execution_authority': False})
    readable = all(any(row['source'] == name and row['state'] == 'observed' for row in rows)
                   for name in REQUIRED)
    return {'expected_sha': expected_sha, 'checkout_sha': checkout_sha, 'build_sha': build_sha,
            'candidate_matches': checkout_sha == build_sha == expected_sha and clean,
            'checkout_clean': clean, 'required_sources_readable': readable,
            'sources': rows, 'observed_at': snapshot['observed_at'],
            'configuration_scope': 'current host shell; running service environment not verified',
            'action_installation': str(install),
            'action_components': [_authority_file(install, name) for name in AUTHORITIES],
            'action_authority_verified': False, 'actions_exercised': False,
            'cluster_claims_exercised': False, 'authenticated_phone_acceptance': 'not exercised',
            'activation_authorized': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-sha', required=True)
    args = parser.parse_args(argv)
    try:
        result = inventory(args.expected_sha)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if result['candidate_matches'] and result['required_sources_readable'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
