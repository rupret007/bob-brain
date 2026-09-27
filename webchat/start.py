#!/usr/bin/env python3
"""Idempotent launchd/screen launcher. Never replaces or kills an existing process."""
import fcntl
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
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


def main():
    os.umask(0o077)
    with (HERE / ".startup.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        if healthy():
            print("Bob web chat is healthy at " + URL)
            return 0
        result = subprocess.run(["/usr/bin/screen", "-ls"], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=5)
        for session in re.findall(r"\t(\d+\.svc-webchat)\s+\(", result.stdout):
            subprocess.run(["/usr/bin/screen", "-S", session, "-X", "quit"], stdin=subprocess.DEVNULL, timeout=5)
        result = subprocess.run(["/usr/bin/screen", "-ls"], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=5)
        if re.search(r"\b\d+\.svc-webchat\s+\(", result.stdout):
            print("svc-webchat still present after quit; inspect logs/webchat-server.log.")
            return 1
        env = os.environ.copy()
        env.setdefault("BOB_WEBCHAT_DRILLS", "1")
        subprocess.run(["/usr/bin/screen", "-dmS", "svc-webchat", "/bin/bash", str(HERE / "run.sh")],
                       stdin=subprocess.DEVNULL, check=True, timeout=10, env=env)
        for _ in range(40):
            if healthy():
                print("Started svc-webchat at " + URL)
                return 0
            time.sleep(0.25)
        print("Webchat did not become ready; inspect logs/webchat-server.log.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
