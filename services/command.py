#!/usr/bin/env python3
"""One bounded, noninteractive subprocess boundary for all service commands."""
from __future__ import annotations

import os
import signal
import subprocess
import threading
import selectors
import time


def signal_group(group, sig):
    """A Darwin zombie-only group can return EPERM, despite being terminal.

    Prove that narrow case after the failed signal. A live member, failed
    observation or malformed row retains the original permission error.
    """
    try:
        os.killpg(group, sig)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        try:
            result = subprocess.run(['/bin/ps', '-axo', 'pgid=,stat='],
                                    capture_output=True, text=True, timeout=3)
            rows = [(int(pgid), status) for pgid, status in
                    (line.split() for line in result.stdout.splitlines() if line.strip())]
            terminal = result.returncode == 0 and all(
                status.startswith('Z') for pgid, status in rows if pgid == group)
        except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
            terminal = False
        if not terminal:
            raise
        return False


def kill_group(process):
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            if not signal_group(process.pid, sig):
                break
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
        # Cleanup belongs to the BaseException path. A cleanup OSError must
        # never replace this cancellation and become a retryable HTTP error.
        raise SystemExit(128 + signum)
    if threading.current_thread() is threading.main_thread():
        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            previous[sig] = signal.signal(sig, interrupted)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except BaseException as original:
        try:
            kill_group(process)
        except Exception as cleanup:
            if isinstance(original, (SystemExit, KeyboardInterrupt)):
                raise original from cleanup
            raise
        finally:
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


def run_input(argv, input_text, *, timeout, max_output_bytes=2000000, **kwargs):
    """Bounded stdin and output for an evidence-only CLI; kill its whole group.

    Evidence stays off argv. No shell, helper process, or disk transcript is used.
    This explicit interface leaves run()'s existing /dev/null contract intact.
    """
    raw = input_text.encode('utf-8')
    if not 0 < len(raw) <= 300000 or timeout <= 0 or not 0 < max_output_bytes <= 4000000:
        raise ValueError('Invalid evidence command limits')
    process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               start_new_session=True, **kwargs)
    previous = {}
    def interrupted(signum, frame):
        raise SystemExit(128 + signum)
    if threading.current_thread() is threading.main_thread():
        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            previous[sig] = signal.signal(sig, interrupted)
    deadline = time.monotonic() + timeout
    outputs = {'stdout': bytearray(), 'stderr': bytearray()}
    offset = 0
    try:
        with selectors.DefaultSelector() as selector:
            for pipe, events, label in ((process.stdin, selectors.EVENT_WRITE, 'stdin'),
                                        (process.stdout, selectors.EVENT_READ, 'stdout'),
                                        (process.stderr, selectors.EVENT_READ, 'stderr')):
                os.set_blocking(pipe.fileno(), False)
                selector.register(pipe, events, label)
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(argv, timeout)
                for key, _ in selector.select(min(remaining, .25)):
                    if key.data == 'stdin':
                        try:
                            offset += os.write(key.fd, raw[offset:offset + 16384])
                        except BlockingIOError:
                            continue
                        except BrokenPipeError:
                            offset = len(raw)
                        if offset == len(raw):
                            selector.unregister(key.fileobj)
                            key.fileobj.close()
                        continue
                    try:
                        chunk = os.read(key.fd, 65536)
                    except BlockingIOError:
                        continue
                    if not chunk:
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                    else:
                        outputs[key.data].extend(chunk)
                        if sum(map(len, outputs.values())) > max_output_bytes:
                            raise RuntimeError('Worker output exceeded its bound')
            process.wait(timeout=max(.001, deadline - time.monotonic()))
        return subprocess.CompletedProcess(argv, process.returncode,
                                           outputs['stdout'].decode('utf-8', 'replace'),
                                           outputs['stderr'].decode('utf-8', 'replace'))
    finally:
        import sys
        original = sys.exc_info()[1]
        try:
            kill_group(process)
        except Exception as cleanup:
            if isinstance(original, (SystemExit, KeyboardInterrupt)):
                raise original from cleanup
            raise
        finally:
            for pipe in (process.stdin, process.stdout, process.stderr):
                pipe.close()
            for sig, handler in previous.items():
                signal.signal(sig, handler)
