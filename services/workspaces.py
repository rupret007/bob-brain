#!/usr/bin/env python3
"""Allocate private Git worktrees; never reset or reuse someone else's checkout."""
from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path

from command import run
from state import CONDUCTOR, ROOT, atomic_write, lock


def git(repo, *args):
    return run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=60, check=True).stdout.strip()


def analysis_workspace(lane):
    base = ROOT / "workspaces" / "analysis"
    with lock("analysis-worktree"):
        if not (base / ".git").exists():
            base.mkdir(parents=True, exist_ok=True)
            git(base, "init", "-b", "draft/analysis")
            git(base, "-c", "user.name=Conductor", "-c", "user.email=conductor@localhost",
                "commit", "--allow-empty", "-m", "Initialize isolated analysis repository")
        job_id = lane + "-" + uuid.uuid4().hex[:12]
        folder = ROOT / "workspaces" / job_id
        git(base, "worktree", "add", "-b", "draft/" + job_id, str(folder), "HEAD")
        return folder


def prepare(record):
    repo = Path(record["repo"]).expanduser().resolve()
    folder = Path(record["worktree"]).expanduser().resolve()
    branch = record["branch"]
    if not branch.startswith("draft/") or not re.fullmatch(r"[\w./-]+", branch):
        raise RuntimeError("job must use an explicit draft/ branch")
    if folder == repo or CONDUCTOR == folder or CONDUCTOR in folder.parents:
        raise RuntimeError("job worktree must be separate from the live core and source checkout")
    with lock("worktree-create"):
        if not folder.exists():
            folder.parent.mkdir(parents=True, exist_ok=True)
            if record.get("fetch_ref"):
                git(repo, "fetch", "origin", record["fetch_ref"])
                base = "FETCH_HEAD"
            else:
                base = record.get("base_ref", "HEAD")
            git(repo, "worktree", "add", "-b", branch, str(folder), base)
        if not (folder / ".git").is_file() or git(folder, "branch", "--show-current") != branch:
            raise RuntimeError("worktree ownership or draft branch mismatch")
        if git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir") != git(folder, "rev-parse", "--path-format=absolute", "--git-common-dir"):
            raise RuntimeError("worktree belongs to a different repository")
        # Each worktree gets its own push guard. No main/release or non-FF push.
        hooks = Path(record["job_dir"]) / "hooks"
        hooks.mkdir(parents=True, exist_ok=True)
        hook = hooks / "pre-push"
        allowed = record.get("publish_branch", branch)
        if not re.fullmatch(r"[\w./-]+", allowed) or allowed in ("main", "master", "develop") or allowed.startswith("release/"):
            raise RuntimeError("invalid draft push target")
        atomic_write(hook, '''#!/bin/bash
set -eu
while read -r local_ref local_sha remote_ref remote_sha; do
  case "$remote_ref" in refs/heads/__APPROVED_BRANCH__) ;; *) echo "Only draft/ pushes allowed" >&2; exit 1;; esac
  case "$local_sha" in 0000000000000000000000000000000000000000) exit 1;; esac
  if [ "$remote_sha" != 0000000000000000000000000000000000000000 ]; then
    git merge-base --is-ancestor "$remote_sha" "$local_sha" || exit 1
  fi
done
'''.replace('__APPROVED_BRANCH__', allowed))
        hook.chmod(0o555)
        git(repo, "config", "extensions.worktreeConfig", "true")
        git(folder, "config", "--worktree", "core.hooksPath", str(hooks))
    return folder


def sandbox_command(argv, workspace, read_only=False):
    """macOS denies core writes even to same-user jobs using --force/bypass."""
    if os.uname().sysname != "Darwin":
        raise RuntimeError("the configured core write boundary requires macOS sandbox-exec")
    denied = [Path(__file__).resolve().parents[1], CONDUCTOR, ROOT / "bin", ROOT / "next-prompts", ROOT / "BOB-HANDOFF.md"]
    if read_only:
        denied.append(Path(workspace))
        # A Git worktree's refs/index may live outside its working directory.
        # Deny those writes too while allowing the CLI to maintain its own cache.
        metadata = git(workspace, "rev-parse", "--path-format=absolute", "--git-common-dir")
        denied.append(Path(metadata))
    filters = " ".join("(subpath " + json.dumps(str(p.resolve())) + ")" for p in denied)
    policy = '(version 1) (allow default) (deny file-write* ' + filters + ')'
    policy += ' (deny file-read-data (literal ' + json.dumps(str(CONDUCTOR / "keys.env")) + '))'
    return ["/usr/bin/sandbox-exec", "-p", policy, *argv]
