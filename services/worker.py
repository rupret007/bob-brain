#!/usr/bin/env python3
"""Codex/Claude job execution with a durable, honest closeout on every exit."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path

from state import CONDUCTOR, ROOT, append_event, atomic_write, job_event, jobs, lock, stamp


def main():
    job = sys.argv[1]
    record = jobs()[job]
    folder = Path(record["job_dir"])
    with lock("worker-" + job, blocking=False):
        if any((folder / name).exists() for name in ("RESULT.txt", "RESULT.md", "BLOCKER.txt")):
            return 0
        prompt = (folder / "PROMPT.txt").read_text()
        prompt += ("\nHard rules: drafts only; never merge, undraft, force-push, send messages/emails, "
                   "spend money/buy credits, change logins, or launch other workers. Only one WebJam coding job. "
                   "Use bash/python3; no rg or GNU timeout. Never reset, overwrite, or stash preexisting edits. "
                   "Inspect existing work and resume it; an earlier invocation may already have made progress. "
                   "Write an honest RESULT.txt or BLOCKER.txt in " + str(folder) + ".\n")
        brief = (folder / "BRIEF.txt").read_text() if (folder / "BRIEF.txt").exists() else ""
        coding = record.get("kind") == "coding" or "coding" in brief.replace("non-coding", "")
        engine = record.get("engine") or ("codex" if coding else "claude")
        if engine not in ("codex", "claude"):
            engine = "codex"
        cwd = Path.home() / "Documents/webjam-pr158-fold" if coding and "webjam" in job else folder
        if not cwd.exists():
            atomic_write(folder / "BLOCKER.txt", "BLOCKER: required worktree is missing; no work started.\n")
            return 1
        cmd = (["codex", "exec", "-s", "workspace-write", "-c", "sandbox_workspace_write.network_access=true",
                "--skip-git-repo-check", prompt] if engine == "codex" else
               ["claude", "-p", prompt, "--permission-mode", "acceptEdits"])
        env = dict(os.environ)
        env.pop("ANTHROPIC_API_KEY", None)  # use the existing CLI login; never buy credits
        job_event(job, "running", engine=engine, recovery="worker_started")
        with (folder / (engine + ".log")).open("a") as out:
            out.write("\n=== " + stamp() + " resume/start\n")
            out.flush()
            try:
                result = subprocess.run(cmd, cwd=str(cwd), env=env, stdin=subprocess.DEVNULL,
                                        stdout=out, stderr=subprocess.STDOUT, timeout=5400)
                rc = result.returncode
            except Exception as exc:
                out.write("worker error: " + type(exc).__name__ + "\n")
                rc = 1
            out.write("\nEXIT=" + str(rc) + "\n")
        append_event("model-runs", {"model": engine, "ok": rc == 0, "job_id": job, "kind": "worker"})
        if not any((folder / name).is_file() and (folder / name).stat().st_size for name in ("RESULT.txt", "RESULT.md", "BLOCKER.txt")):
            atomic_write(folder / "BLOCKER.txt", "BLOCKER: " + engine + " exited " + str(rc) + " without a closeout; inspect its log and existing work before retry.\n")
        return rc


if __name__ == "__main__":
    raise SystemExit(main())
