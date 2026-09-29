#!/usr/bin/env python3
"""Idempotent launchd/screen launcher. Never replaces or kills an existing process."""
import json
import os
import re
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'release'))
from release_ownership import controller
import activation_journal as journal
from build_info import load_build

URL = "http://127.0.0.1:8787"
IDENTITY_LIMIT = 4096


class IdentityError(RuntimeError):
    """A responding server cannot be accepted as the selected release."""


def bounded_file(path):
    """Read small startup metadata without following links or blocking on pipes."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > IDENTITY_LIMIT:
            raise RuntimeError('Web Bob startup metadata is invalid')
        raw = os.read(fd, IDENTITY_LIMIT + 1)
        if len(raw) > IDENTITY_LIMIT:
            raise RuntimeError('Web Bob startup metadata is oversized')
        return raw.decode('utf-8')
    finally:
        os.close(fd)


def selected_identity(root):
    # Resolve after acquiring ownership: the shell may have selected this Python
    # launcher before another release finished changing the application pin.
    code = root / 'conductor'
    for name in ('webchat', 'dispatch'):
        try:
            value = bounded_file(root / 'conductor/state' / (name + '-code-root'))
        except FileNotFoundError:
            continue
        value = value.removesuffix('\n')
        if not value or '\n' in value or '\r' in value or '\0' in value or not Path(value).is_absolute():
            raise RuntimeError('Web Bob startup pin is invalid')
        code = Path(value)
        break
    try:
        build = json.loads(bounded_file(code / 'webbob-build.json'))
    except FileNotFoundError:
        # Retain tracked-checkout support without borrowing an unrelated Git
        # parent's identity. Unknown/unversioned installations refuse startup.
        build = load_build(code)
    if (not isinstance(build, dict) or not isinstance(build.get('sha'), str)
            or not re.fullmatch(r'[0-9a-f]{40}', build['sha'])
            or not isinstance(build.get('built_at'), str) or not build['built_at']
            or build['built_at'] == 'unknown'):
        raise RuntimeError('Web Bob startup identity is unavailable')
    return {key: build[key] for key in ('sha', 'built_at')}


def healthy(expected):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(URL + "/login", timeout=2) as response:
            if response.status != 200 or response.headers.get("X-Bob-Webchat") != "1":
                return False
        try:
            with opener.open(URL + "/api", timeout=2):
                return False
        except urllib.error.HTTPError as response:
            with response:
                if response.code != 401 or response.headers.get("X-Bob-Webchat") != "1":
                    return False
    except (OSError, urllib.error.URLError):
        return False
    # A responding Web Bob is not permission to launch another one when its
    # release is wrong or unknown. Refuse before any screen command instead.
    try:
        with opener.open(URL + '/api/version', timeout=2) as response:
            if response.status != 200 or response.headers.get('X-Bob-Webchat') != '1':
                raise ValueError('Invalid version response')
            raw = response.read(IDENTITY_LIMIT + 1)
            if len(raw) > IDENTITY_LIMIT:
                raise ValueError('Oversized version response')
            build = json.loads(raw)
            if (not isinstance(build, dict) or build.get('name') != 'Web Bob'
                    or any(build.get(key) != value for key, value in expected.items())):
                raise ValueError('Different release identity')
    except (OSError, ValueError, urllib.error.URLError):
        raise IdentityError('Unverified Web Bob release') from None
    return True


def start(owner, expected):
    if healthy(expected):
        print("Bob web chat is healthy at " + URL)
        return 0
    result = subprocess.run(["/usr/bin/screen", "-ls"], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=5)
    inventory = result.stdout + result.stderr
    if re.search(r"\b\d+\.svc-webchat(?=\s|$)", inventory):
        # A slow health probe is not authorization to interrupt an existing chat.
        print("svc-webchat is present but not responding; inspect it before a deliberate restart.")
        return 1
    if not ((result.returncode == 0 and re.search(r"\b\d+ Sockets? in ", inventory))
            or (result.returncode == 1 and "No Sockets found in " in inventory)):
        print("Screen inventory is unavailable; refusing to guess whether Web Bob is running.")
        return 1
    env = os.environ.copy()
    env.setdefault("BOB_WEBCHAT_DRILLS", "0")
    owner.validate()
    subprocess.run(["/usr/bin/screen", "-dmS", "svc-webchat", "/bin/bash", str(HERE / "run.sh")],
                   stdin=subprocess.DEVNULL, check=True, timeout=10, env=env)
    for _ in range(40):
        if healthy(expected):
            print("Started svc-webchat at " + URL)
            return 0
        time.sleep(0.25)
    print("Webchat did not become ready; inspect logs/webchat-server.log.")
    return 1


def main():
    os.umask(0o077)
    root = Path(os.environ.get('BOB_ROOT') or HERE.parent.parent).resolve()
    try:
        # One installation-wide lock covers different pinned code directories and
        # cooperating release/rollback controllers, through readiness polling.
        with controller(root) as owner:
            try:
                journal.require_clear(root)
            except (OSError, RuntimeError, ValueError, KeyError, TypeError):
                print("Web Bob activation needs explicit recovery or inspection before periodic startup.")
                return 1
            try:
                expected = selected_identity(root)
            except (OSError, RuntimeError, ValueError, KeyError, TypeError):
                print('The selected Web Bob build cannot be identified; inspect the code pin before startup.')
                return 1
            return start(owner, expected)
    except IdentityError:
        print('Web Bob is responding but its release identity cannot be verified; inspect it before restarting.')
        return 1
    except (OSError, RuntimeError, ValueError, KeyError, TypeError):
        print("Web Bob periodic startup could not proceed safely; wait for any release or inspect startup logs.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
