#!/usr/bin/env python3
"""Read-only M1 staging probes. Never logs in or activates a build."""
import argparse
import http.client
import json
import os
import re
import stat
from datetime import datetime, timezone
from urllib.parse import urlsplit


MAX_BODY = 128 * 1024


def target(url):
    parsed = urlsplit(url)
    host = parsed.hostname
    local = host in ('127.0.0.1', '::1', 'localhost')
    if (parsed.scheme not in ('http', 'https') or not host
            or parsed.username is not None or parsed.password is not None
            or parsed.path not in ('', '/') or parsed.query or parsed.fragment
            or not (local or host.endswith('.ts.net'))
            or parsed.scheme == 'http' and not local):
        raise ValueError('Use an HTTPS tailnet origin or a loopback test origin without credentials or paths')
    # Validate the port before any transport is opened.
    return parsed.scheme, host, parsed.port


def probe(url, expected_sha):
    """Return bounded observations, never authenticated acceptance or go-live OK."""
    if not re.fullmatch(r'[0-9a-f]{40}', expected_sha or ''):
        raise ValueError('Expected SHA must be the full 40-character lowercase commit SHA')
    scheme, host, port = target(url)
    transport = http.client.HTTPSConnection if scheme == 'https' else http.client.HTTPConnection
    checks = []
    observed_sha = None
    for path in ('/api/version', '/login', '/api/state', '/api/session', '/api/conversations'):
        connection = transport(host, port, timeout=5)
        check = {'path': path, 'ok': False}
        try:
            # No cookies, authorization, ambient proxies, credentials or redirects.
            connection.request('GET', path, headers={'Accept': 'application/json, text/html'})
            response = connection.getresponse()
            body = response.read(MAX_BODY + 1)
            check['status'] = response.status
            if len(body) > MAX_BODY:
                check['reason'] = 'response exceeds bounded probe limit'
            elif path == '/api/version':
                try:
                    value = json.loads(body)
                    sha = value.get('sha') if isinstance(value, dict) else None
                except (ValueError, UnicodeError):
                    sha = None
                if isinstance(sha, str) and re.fullmatch(r'[0-9a-f]{40}', sha):
                    observed_sha = sha
                check['ok'] = response.status == 200 and observed_sha == expected_sha
                if not check['ok']:
                    check['reason'] = 'selected candidate build is not verified'
            elif path == '/login':
                check['ok'] = (response.status == 200 and b'password' in body.lower()
                               and 'no-store' in response.getheader('Cache-Control', '').lower())
                if not check['ok']:
                    check['reason'] = 'private login page is not verified'
            else:
                check['ok'] = response.status == 401
                if not check['ok']:
                    check['reason'] = 'anonymous access was not rejected with 401'
        except (OSError, http.client.HTTPException):
            # Exception payloads and remote bodies can contain credentials.
            check['reason'] = 'transport unavailable'
        finally:
            connection.close()
        checks.append(check)
    return {'observed_at': datetime.now(timezone.utc).isoformat(),
            'expected_sha': expected_sha, 'observed_sha': observed_sha,
            'staging_probes_passed': all(row['ok'] for row in checks),
            'authenticated_phone_acceptance': 'not exercised',
            'activation_authorized': False, 'checks': checks}


def authenticated_probe(url, expected_sha, session_file):
    """Opt-in read-only checks with an existing owner session; never log secrets.

    An anonymous candidate mismatch stops before reading or transmitting the
    credential. This does not log in, send chat, exercise memory or approve work.
    """
    result = probe(url, expected_sha)
    result['authenticated_read_probes_passed'] = False
    if not result['staging_probes_passed']:
        return result
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    try:
        fd = os.open(session_file, flags)
        with os.fdopen(fd, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or stat.S_IMODE(info.st_mode) & 0o077):
                raise ValueError('Session file must be an owner-only regular file')
            raw = stream.read(4097)
        # Only the raw token, never a Cookie header or arbitrary header content.
        token = raw.decode('ascii').strip()
        if len(raw) > 4096 or not re.fullmatch(r'[A-Za-z0-9_-]{32,256}', token):
            raise ValueError('Session file must contain one existing raw session token')
    except (OSError, UnicodeError):
        raise ValueError('Cannot read a private session file') from None
    scheme, host, port = target(url)
    transport = http.client.HTTPSConnection if scheme == 'https' else http.client.HTTPConnection
    checks = []
    for path in ('/api/session', '/api/conversations'):
        connection = transport(host, port, timeout=5)
        check = {'path': path, 'ok': False}
        try:
            connection.request('GET', path, headers={'Accept': 'application/json',
                                                    'Cookie': 'bob_session=' + token})
            response = connection.getresponse()
            body = response.read(MAX_BODY + 1)
            check['status'] = response.status
            if len(body) <= MAX_BODY:
                try:
                    value = json.loads(body)
                except (ValueError, UnicodeError):
                    value = None
                valid = isinstance(value, dict)
                if path == '/api/session':
                    valid = valid and isinstance(value.get('csrf'), str) and bool(value['csrf'])
                else:
                    valid = valid and isinstance(value.get('conversations'), list)
                check['ok'] = (response.status == 200 and valid
                               and 'no-store' in response.getheader('Cache-Control', '').lower())
            if not check['ok']:
                check['reason'] = 'private authenticated read was not verified'
        except (OSError, http.client.HTTPException):
            check['reason'] = 'authenticated transport unavailable'
        finally:
            connection.close()
        checks.append(check)
    # Check that the candidate still matches after the authenticated reads.
    final = probe(url, expected_sha)
    result['authenticated_checks'] = checks
    result['candidate_still_matches'] = final['staging_probes_passed']
    result['authenticated_read_probes_passed'] = (
        all(row['ok'] for row in checks) and final['staging_probes_passed'])
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True, help='Private origin, without credentials')
    parser.add_argument('--expected-sha', required=True, help='Selected full reviewed candidate SHA')
    parser.add_argument('--session-file', help='Optional owner-only file with existing raw session token; GET checks only')
    args = parser.parse_args(argv)
    try:
        result = (authenticated_probe(args.url, args.expected_sha, args.session_file)
                  if args.session_file else probe(args.url, args.expected_sha))
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2, sort_keys=True))
    passed = result.get('authenticated_read_probes_passed', result['staging_probes_passed'])
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
