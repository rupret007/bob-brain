"""Execute a fenced chat task; persist the answer before releasing the lane."""
from __future__ import annotations

import hashlib
import contextlib
import json
import os
import re
import signal
import sys
import threading
from pathlib import Path

from state import CONDUCTOR, ROOT, atomic_write, lock, read_json
from lanes import ask
from workspaces import prepare, git

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "state"))
import task_queue


def task_repository(prompt):
    for project, spec in read_json(CONDUCTOR / "services/projects.json", {}).items():
        if re.search(r"\b" + re.escape(project) + r"\b", prompt, re.I):
            return project, Path(spec["repo"]).expanduser().resolve()
    return "WebBob", CONDUCTOR


def prepare_task(record, coding):
    if not coding:
        return prepare(record)
    # Independent Git metadata is needed for conductor code tasks: the model's
    # sandbox denies writes to the live conductor, including its .git directory.
    # Shared objects are read-only; new commits/refs live in this private clone.
    folder = Path(record["worktree"])
    with lock("dispatch-workspace"):
        if not folder.exists():
            folder.parent.mkdir(parents=True, exist_ok=True)
            git(ROOT, "clone", "--shared", "--no-checkout", record["repo"], str(folder))
            git(folder, "checkout", "-b", record["branch"], "HEAD")
            git(folder, "remote", "remove", "origin")
        if git(folder, "branch", "--show-current") != record["branch"]:
            raise RuntimeError("Private task branch ownership mismatch")
        hooks = folder / ".git/hooks"
        atomic_write(hooks / "pre-push", "#!/bin/sh\necho 'Web Bob tasks are local only' >&2\nexit 1\n")
        (hooks / "pre-push").chmod(0o700)
    return folder


def redact(text):
    # Do not persist provider output containing any loaded credential.
    for name, value in os.environ.items():
        if (name.endswith(("KEY", "TOKEN", "SECRET", "PASSWORD"))) and len(value) >= 8:
            text = text.replace(value, "[secret removed]")
    return re.sub(r"\b(?:sk-[A-Za-z0-9_-]{20,}|AIza[A-Za-z0-9_-]{25,}|gh[pousr]_[A-Za-z0-9_]{25,})\b",
                  "[secret removed]", text)


def execute(identifier, token):
    row = task_queue.tasks(ROOT).get(identifier)
    if not row or row.get("claim_token") != token or row["status"] not in task_queue.ACTIVE:
        return 0
    stopped = threading.Event()
    heartbeat = None
    owns_task = False
    try:
        with contextlib.ExitStack() as stack:
            stack.enter_context(lock("dispatch-" + identifier, blocking=False))
            owns_task = True
            stack.enter_context(lock("lane-" + row["worker"], blocking=False))
            project, repo = task_repository(row["prompt"])
            if project.lower() == "webjam" and row["kind"] == "coding":
                stack.enter_context(lock("webjam-coder", blocking=False))
                from jobs import external_webjam_lease
                from runtime import screen_sessions
                if external_webjam_lease(screen_sessions()):
                    raise BlockingIOError("External WebJam coder is active")
            if not task_queue.transition(ROOT, identifier, token, "running"):
                return 0

            def renew():
                while not stopped.wait(10):
                    try:
                        current = task_queue.transition(ROOT, identifier, token, "heartbeat")
                    except Exception:
                        current = None
                    if not current:
                        # command.run handles TERM by killing the entire model
                        # subprocess group. An expired worker cannot keep editing.
                        if not stopped.is_set():
                            os.kill(os.getpid(), signal.SIGTERM)
                        return

            heartbeat = threading.Thread(target=renew, daemon=True)
            heartbeat.start()
            folder = CONDUCTOR / "state/task-runs" / identifier
            folder.mkdir(parents=True, exist_ok=True)
            branch = "draft/" + identifier
            record = dict(repo=str(repo), worktree=str(ROOT / "workspaces" / identifier),
                          branch=branch, job_dir=str(folder))
            cwd = prepare_task(record, row["kind"] == "coding")
            prompt = ("Web Bob assigned this task from Jeff. Complete it and return the actual result in your final answer. "
                      "Do not merely propose a plan or claim another worker will do it. If blocked, begin BLOCKER:. "
                      "Keep all work local: never push or create/modify a PR. "
                      "Use only the assigned worktree " + str(cwd) + " on " + branch + ". "
                      "For code changes, commit locally and report the SHA, changed paths and tests. "
                      "For analysis, use the evidence in the request; do not invent repository observations.\n\n"
                      "TASK:\n" + row["prompt"])
            answer = redact(ask(row["worker"], prompt, cwd=cwd, coding=row["kind"] == "coding",
                                timeout=1800 if row["kind"] == "coding" else 240,
                                purpose="small-review" if row["worker"] == "claude" else "webbob-" + identifier,
                                locked=True)).strip()
            if not answer or re.search(r"(?im)^\s*(?:```\s*)?(?:\*\*)?BLOCKER\s*:", answer):
                raise RuntimeError(answer[:1500] or "Worker returned an empty answer")
            if row["kind"] == "coding":
                if git(cwd, "branch", "--show-current") != branch:
                    raise RuntimeError("Worker changed its assigned draft branch")
                if git(cwd, "status", "--porcelain", "--untracked-files=normal"):
                    raise RuntimeError("Worker left uncommitted changes; task is not complete")
            # The queue is the result outbox. A result file alone is never proof
            # of completion, and a superseded claim cannot publish a result.
            digest = hashlib.sha256(answer.encode()).hexdigest()
            result = task_queue.transition(ROOT, identifier, token, "succeeded", result=answer,
                                           result_sha256=digest, worktree=str(cwd), branch=branch)
            stopped.set()
            if result:
                atomic_write(folder / "RESULT.md", answer + "\n")
            return 0 if result else 1
    except BlockingIOError:
        if owns_task:
            task_queue.transition(ROOT, identifier, token, "busy", error="Waiting for the shared worker lane")
        return 0
    except Exception as exc:
        message = redact(str(exc)) if isinstance(exc, RuntimeError) else type(exc).__name__
        task_queue.transition(ROOT, identifier, token, "retry", error=message[:1500])
        return 1
    finally:
        stopped.set()
        if heartbeat:
            heartbeat.join(timeout=1)


if __name__ == "__main__":
    raise SystemExit(execute(*sys.argv[1:3]))
