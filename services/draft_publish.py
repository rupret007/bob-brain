"""Publish only a user-authorized project task's own draft ref, then verify it."""
import os
import re
from urllib.parse import quote

from command import run
from state import atomic_write
from workspaces import git


def publish(row, cwd, folder, projects):
    project = row.get("publish_project")
    if project is None:
        return None
    spec = next((value for name, value in projects.items() if name.lower() == project.lower()), None)
    if row["kind"] != "coding" or not spec:
        raise RuntimeError("No authorized project destination for draft push")
    remote = spec["remote"]
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", remote):
        raise RuntimeError("Invalid project remote")
    if not re.fullmatch(r"webchat-[a-f0-9]{32}", row["id"]):
        raise RuntimeError("Invalid task draft identity")
    branch = "draft/" + row["id"]
    if git(cwd, "branch", "--show-current") != branch or git(cwd, "status", "--porcelain"):
        raise RuntimeError("Draft push requires the assigned, clean branch")
    sha = git(cwd, "rev-parse", "HEAD")
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise RuntimeError("Invalid draft SHA")
    # The model still has a deny-all hook. Only this server-side call gets a
    # separate hook, stored outside the model's writable checkout.
    hooks = folder / "publish-hooks"
    atomic_write(hooks / "pre-push", "#!/bin/sh\nset -eu\nwhile read local_ref local_sha remote_ref remote_sha; do\n"
                 '  [ "$remote_ref" = "refs/heads/' + branch + '" ] || exit 1\n'
                 '  [ "$local_sha" = "' + sha + '" ] || exit 1\ndone\n')
    (hooks / "pre-push").chmod(0o500)
    url = "https://github.com/" + remote + ".git"
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    result = run(["git", "-C", str(cwd), "-c", "core.hooksPath=" + str(hooks), "push", url,
                  sha + ":refs/heads/" + branch], env=env, capture_output=True, text=True, timeout=60)
    if result.returncode:
        # The dispatcher redacts this before any journal/result persistence.
        raise RuntimeError("Draft push failed for " + remote + "; git exit " + str(result.returncode) + ": " + result.stderr[-500:])
    result = run(["git", "ls-remote", "--exit-code", url, "refs/heads/" + branch],
                 env=env, capture_output=True, text=True, timeout=30)
    if result.returncode or result.stdout.split() != [sha, "refs/heads/" + branch]:
        raise RuntimeError("Published draft SHA could not be verified")
    return dict(project=project, repo=remote, branch=branch, sha=sha,
                url="https://github.com/" + remote + "/tree/" + quote(branch, safe=""))
