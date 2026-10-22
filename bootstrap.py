#!/usr/bin/env python3
"""Minimal entrypoint: syntax gate and Git rollback before importing the core."""
from __future__ import annotations

import os
import fcntl
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def bounded(argv, **kwargs):
    process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, start_new_session=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
    try:
        out, err = process.communicate(timeout=30)
    except BaseException:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=5)
        raise
    return process.returncode, out, err


def files():
    return [HERE / "PROMPT.md", HERE / "bootstrap.py"] + list((HERE / "services").glob("*.py")) + list((HERE / "services").glob("*.sh")) + list(HERE.glob("*.sh")) + list((HERE / "launchd").glob("*.sh")) + list((HERE / "launchd").glob("*.py"))


def validate():
    failed = []
    with tempfile.TemporaryDirectory(prefix="bob-compile-") as tmp:
        for path in files():
            if path.suffix == ".py":
                env = dict(os.environ, PYTHONPYCACHEPREFIX=tmp)
                rc, _, _ = bounded([sys.executable, "-m", "py_compile", str(path)], env=env)
            elif path.suffix == ".sh":
                rc, _, _ = bounded(["/bin/bash", "-n", str(path)])
            else:
                rc = 0 if path.is_file() else 1
            if rc:
                failed.append(str(path.relative_to(HERE)))
    return failed


def gate():
    # Several service/worker launches can arrive together. One guard owns
    # validation/recovery, and an in-progress local edit is never rolled back.
    with (HERE / ".bootstrap-guard.lock").open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        return _gate_locked()


def _gate_locked():
    failures = validate()
    if failures:
        failures = validate()  # A file may have been replaced during validation.
    if failures:
        rc, _, _ = bounded(["git", "-C", str(HERE), "diff", "--quiet", "HEAD", "--",
                            "bootstrap.py", "PROMPT.md", "services", "launchd", "*.sh"])
        if rc:
            raise RuntimeError("core validation failed with local changes; launch deferred without rollback")
        rc, tracked, _ = bounded(["git", "-C", str(HERE), "ls-tree", "-r", "--name-only", "last-good"])
        if rc:
            raise RuntimeError("core invalid; no last-good tag; launch refused")
        names = [n for n in tracked.decode().splitlines() if n == "PROMPT.md" or n == "bootstrap.py" or
                 n.endswith(".sh") or (n.startswith(("services/", "launchd/")) and n.endswith(".py"))]
        quarantine = HERE / "reviews/quarantine" / str(time.time_ns())
        quarantine.mkdir(parents=True)
        for name in names:
            source = HERE / name
            if source.exists():
                dest = quarantine / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(source.read_bytes())
                source.chmod(source.stat().st_mode | 0o200)
        rc, _, _ = bounded(["git", "-C", str(HERE), "restore", "--source=last-good", "--worktree", "--", *names])
        if rc or validate():
            raise RuntimeError("core rollback failed; launch refused")
        (quarantine / "ROLLBACK.txt").write_text("Syntax failure: " + ", ".join(failures) + "\nRestored last-good before executing services.\n")
    for path in files():
        path.chmod(path.stat().st_mode & ~0o222)


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else "check"
    if command == "check":
        failures = validate()
        print("syntax: " + (", ".join(failures) if failures else "PASS"))
        return bool(failures)
    if (HERE / "MAINTENANCE").exists():
        print("maintenance: launch paused")
        return 0
    gate()
    if command == "guard":
        return 0
    targets = {"runtime": "runtime.py", "worker": "worker.py", "council": "council.py",
               "pass": "conductor_pass.py", "ask": "lanes.py", "smoke": "smoke.py"}
    if command not in targets:
        raise ValueError("unknown bootstrap command")
    os.execv(sys.executable, [sys.executable, str(HERE / "services" / targets[command]), *sys.argv[2:]])


if __name__ == "__main__":
    raise SystemExit(main())
