#!/usr/bin/env python3
"""Idempotent launchd/screen launcher. Never replaces or kills an existing process."""
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'release'))
from release_ownership import controller
import activation_journal as journal

URL = "http://127.0.0.1:8787"


def healthy():
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(URL + "/login", timeout=2) as response:
            if response.status != 200 or response.headers.get("X-Bob-Webchat") != "1":
                return False
        try:
            opener.open(URL + "/api", timeout=2)
        except urllib.error.HTTPError as response:
            return response.code == 401 and response.headers.get("X-Bob-Webchat") == "1"
    except (OSError, urllib.error.URLError):
        pass
    return False


def start(owner):
    if healthy():
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
        if healthy():
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
            return start(owner)
    except (OSError, RuntimeError):
        print("Web Bob periodic startup could not proceed safely; wait for any release or inspect startup logs.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
