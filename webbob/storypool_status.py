"""On-demand, bounded, read-only StoryPool observations for the Stack Ops skill."""
from datetime import datetime, timezone
import http.client
import json
import os
from pathlib import Path
import stat
import time

from webbob.shared_context import ContextError, safe_fact

MAX_BYTES = 128 * 1024
STATUS_FILES = ('conductor/conductor-status.json', 'dispatch/dispatch-status.json')
JEFF_FILES = ('NEEDS_JEFF.md', 'conductor/NEEDS_JEFF.md')
COUNTS = ('dispatched', 'skipped', 'proposals_count', 'validated_count', 'rejected_count',
          'executed_count', 'total', 'running', 'pending', 'failed', 'completed')
STATES = {'running', 'stopped', 'error', 'unknown', 'up', 'down', 'degraded', 'paused'}


def _safe(value):
    if not isinstance(value, str):
        return '[omitted]'
    try:
        return safe_fact(value)
    except ContextError:
        return '[sensitive or unsafe content omitted]'


def _read(root, name):
    """Only fixed status files, no symlinks, devices, logs or credential config."""
    root = Path(root).expanduser().resolve()
    path = root / name
    if path.resolve() != path:
        raise OSError('symlink refused')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES:
            raise OSError('not a bounded regular file')
        raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise OSError('too large')
    return raw.decode('utf-8'), info.st_mtime


def _freshness(timestamp, now):
    try:
        observed = datetime.fromisoformat(_timestamp(timestamp)).timestamp()
        return 'fresh' if 0 <= now - observed <= 900 else 'stale'
    except (AttributeError, TypeError, ValueError, OverflowError):
        return 'unknown'


def _timestamp(value):
    # Validate and re-encode dates rather than treating numeric ISO offsets as
    # free-text facts (the fact credential filter can omit those legitimate dates).
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed.isoformat() if parsed.tzinfo is not None else 'unknown'
    except (AttributeError, TypeError, ValueError, OverflowError):
        return 'unknown'


def _counts(data):
    if not isinstance(data, dict):
        return {}
    return {key: data[key] for key in COUNTS if type(data.get(key)) is int and data[key] >= 0}


def _dashboard(port):
    # Direct literal loopback, GET only, no proxies, redirects, cookies or auth.
    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=2)
    try:
        connection.request('GET', '/api/data', headers={'Accept': 'application/json'})
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError('dashboard unavailable')
        raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError('dashboard response too large')
        return json.loads(raw)
    finally:
        connection.close()


def collect_status(data_dir=None, repo_dir=None, *, dashboard_port=8790, now=None):
    """Trusted host paths only. This function writes nothing and executes nothing."""
    if type(dashboard_port) is not int or not 1 <= dashboard_port <= 65535:
        raise ValueError('invalid dashboard port')
    now = time.time() if now is None else now
    data_dir = Path(data_dir or '~/.local/share/storypool').expanduser()
    repo_dir = Path(repo_dir or '~/storypool-install').expanduser()
    result = {'execution_authority': False, 'untrusted_observations': True,
              'files': [], 'dashboard': {'state': 'unavailable'}, 'needs_jeff': []}
    for name in STATUS_FILES:
        row = {'source': name, 'state': 'unavailable'}
        try:
            raw, _ = _read(data_dir, name)
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError('not a status object')
            timestamp = data.get('timestamp')
            row.update(state='observed', timestamp=_timestamp(timestamp),
                       freshness=_freshness(timestamp, now), summary=_counts(data.get('summary')))
        except (OSError, ValueError, UnicodeError):
            pass
        result['files'].append(row)
    # Read doctor, conductor and repo escalation files without marking them done.
    for root, name, label in [(data_dir, name, 'storypool/' + name) for name in JEFF_FILES] + [
            (repo_dir, 'NEEDS_JEFF.md', 'install/NEEDS_JEFF.md')]:
        row = {'source': label, 'state': 'unavailable', 'items': []}
        try:
            raw, modified = _read(root, name)
            row.update(state='observed', modified_at=datetime.fromtimestamp(modified, timezone.utc).isoformat(),
                       items=[_safe(line) for line in raw.splitlines() if line.strip()][-30:])
        except (OSError, ValueError, UnicodeError):
            pass
        result['needs_jeff'].append(row)
    try:
        data = _dashboard(dashboard_port)
        if not isinstance(data, dict):
            raise ValueError('not a dashboard object')
        rows = data.get('services', [])
        if not isinstance(rows, list):
            raise ValueError('invalid dashboard services')
        services = []
        for row in rows[:20]:
            if not isinstance(row, dict):
                continue
            services.append({'name': _safe(row.get('name')),
                             'status': row.get('status') if row.get('status') in STATES else 'unknown'})
        result['dashboard'] = {'state': 'observed', 'timestamp': _timestamp(data.get('timestamp')),
                               'freshness': _freshness(data.get('timestamp'), now),
                               'services': services, 'jobs_stats': _counts(data.get('jobs_stats'))}
    except (OSError, ValueError, TypeError, http.client.HTTPException):
        pass
    return result


if __name__ == '__main__':
    print(json.dumps(collect_status(), indent=2))
