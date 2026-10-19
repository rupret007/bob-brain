#!/usr/bin/env python3
"""fill-queue.py: the one safe way to change ~/lane-wt/logs/fill.queue   (lane-ops v3, arch-review-2 B5)

Before v3, fill.sh rewrote the queue with `print > $QFILE` (not atomic, no lock) while fill-autoqueue.py and
gemini-feed.py appended to it, so appends could be lost, and a job whose lease was refused was simply dropped.
Now every writer goes through one exclusive lock (QUEUE + ".lock", fcntl.flock) and a temp-file + os.replace
rewrite, and a lease refusal DEFERS the job instead of dropping it.

  fill-queue.py ready              print queued jobs that are not deferred right now (space separated)
  fill-queue.py add JOB...         append jobs that are not already queued
  fill-queue.py remove JOB...      remove jobs (and their deferral state)
  fill-queue.py defer JOB [SECS]   keep JOB queued but skip it for SECS (default FILL_DEFER_S=600); after
                                   FILL_DEFER_MAX (12) deferrals it is dropped and "DROP JOB" is printed
Env: FILL_QUEUE (default ~/lane-wt/logs/fill.queue). Exit 0 ok, 2 usage, 3 lock timeout.
"""
import contextlib
import fcntl
import json
import os
import sys
import tempfile
import time

QUEUE = os.environ.get("FILL_QUEUE", os.path.expanduser("~/lane-wt/logs/fill.queue"))
DEFER_S = int(os.environ.get("FILL_DEFER_S", "600"))
DEFER_MAX = int(os.environ.get("FILL_DEFER_MAX", "12"))
LOCK_WAIT = float(os.environ.get("FILL_QUEUE_LOCK_WAIT", "60"))


def _paths(queue=None):
    q = queue or QUEUE
    return q, q + ".lock", q + ".deferred.json"


@contextlib.contextmanager
def locked(queue=None):
    _, lock, _ = _paths(queue)
    os.makedirs(os.path.dirname(os.path.abspath(lock)), exist_ok=True)
    with open(lock, "a") as f:
        t0 = time.time()
        while True:
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.time() - t0 > LOCK_WAIT:
                    raise TimeoutError("fill.queue lock timeout")
                time.sleep(0.05)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def _read(path):
    try:
        with open(path) as f:
            return [t for t in f.read().split() if t]
    except FileNotFoundError:
        return []


def _write_atomic(path, text):
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix=".fill-queue-", dir=d)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def _uniq(jobs):
    seen, out = set(), []
    for j in jobs:
        if j and j not in seen:
            seen.add(j)
            out.append(j)
    return out


def _write_queue(path, jobs):
    jobs = _uniq(jobs)
    _write_atomic(path, " ".join(jobs) + ("\n" if jobs else ""))


def _read_defer(path):
    try:
        with open(path) as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (FileNotFoundError, ValueError):
        return {}


def update(fn, queue=None):
    """Atomically replace the queue with fn(current_jobs). Returns the new list."""
    q, _, _ = _paths(queue)
    with locked(queue):
        new = _uniq(fn(_read(q)))
        _write_queue(q, new)
        return new


def add(jobs, queue=None):
    return update(lambda cur: cur + [j for j in jobs if j not in cur], queue)


def remove(jobs, queue=None):
    q, _, dp = _paths(queue)
    drop = set(jobs)
    with locked(queue):
        _write_queue(q, [j for j in _read(q) if j not in drop])
        d = _read_defer(dp)
        if any(j in d for j in drop):
            _write_atomic(dp, json.dumps({k: v for k, v in d.items() if k not in drop}, sort_keys=True))


def defer(job, secs=None, queue=None, now=None):
    """Keep job queued but not ready for secs. Returns 'DEFER' or 'DROP' (after DEFER_MAX deferrals)."""
    q, _, dp = _paths(queue)
    t = time.time() if now is None else now
    with locked(queue):
        d = _read_defer(dp)
        e = d.get(job) or {}
        count = int(e.get("count") or 0) + 1
        cur = _read(q)
        if count > DEFER_MAX:
            d.pop(job, None)
            _write_queue(q, [j for j in cur if j != job])
            verdict = "DROP"
        else:
            d[job] = {"count": count, "until": t + (DEFER_S if secs is None else secs)}
            if job not in cur:
                _write_queue(q, cur + [job])
            verdict = "DEFER"
        _write_atomic(dp, json.dumps(d, sort_keys=True))
        return verdict


def ready(queue=None, now=None):
    q, _, dp = _paths(queue)
    t = time.time() if now is None else now
    with locked(queue):
        d = _read_defer(dp)
        return [j for j in _read(q) if float((d.get(j) or {}).get("until") or 0) <= t]


def main(argv):
    if len(argv) < 2:
        print(__doc__.strip().splitlines()[0]); return 2
    cmd, args = argv[1], argv[2:]
    try:
        if cmd == "ready" and not args:
            print(" ".join(ready()))
        elif cmd == "add" and args:
            add(args)
        elif cmd == "remove" and args:
            remove(args)
        elif cmd == "defer" and len(args) in (1, 2):
            v = defer(args[0], int(args[1]) if len(args) == 2 else None)
            print(f"{v} {args[0]}")
        else:
            print("usage: fill-queue.py ready | add JOB... | remove JOB... | defer JOB [SECS]"); return 2
    except TimeoutError as e:
        print(f"BLOCKED {e}", file=sys.stderr); return 3
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
