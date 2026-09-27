#!/usr/bin/env python3
"""One bounded, noninteractive subprocess boundary for all service commands."""
from __future__ import annotations

import os
import signal
import subprocess
import threading


def kill_group(process):
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            break
        if sig == signal.SIGTERM:
            try:
                process.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                pass
    process.wait(timeout=5)


def run(argv, *, timeout=60, capture_output=False, text=False, check=False, detach=False, **kwargs):
    """Even grandchildren are killed on timeout, signal or interrupted parent.

    detach=True is only for launchers such as `screen -dmS`, whose daemon is meant to outlive the call."""
    if timeout is None or timeout <= 0:
        raise ValueError("a positive wall-clock timeout is required")
    if "input" in kwargs or kwargs.pop("stdin", subprocess.DEVNULL) != subprocess.DEVNULL:
        raise ValueError("commands must use /dev/null stdin; pass secrets via private files")
    if capture_output:
        kwargs.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, start_new_session=True,
                               text=text, **kwargs)
    previous = {}
    def interrupted(signum, frame):
        kill_group(process)
        raise SystemExit(128 + signum)
    if threading.current_thread() is threading.main_thread():
        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            previous[sig] = signal.signal(sig, interrupted)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except BaseException:
        kill_group(process)
        for pipe in (process.stdout, process.stderr):
            if pipe:
                pipe.close()
        raise
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    # A CLI must not leave background tools behind after returning success.
    if not detach:
        kill_group(process)
    result = subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)
    if check:
        result.check_returncode()
    return result
