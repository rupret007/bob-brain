#!/usr/bin/env python3
"""Read-only, anonymous M1 staging probes. Never logs in or activates a build."""
import argparse
import http.client
import json
import re
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True, help='Private origin, without credentials')
    parser.add_argument('--expected-sha', required=True, help='Selected full reviewed candidate SHA')
    args = parser.parse_args(argv)
    try:
        result = probe(args.url, args.expected_sha)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result['staging_probes_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
