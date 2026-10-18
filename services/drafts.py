#!/usr/bin/env python3
"""Isolated conductor proposals. This module never promotes a draft to live files."""
from __future__ import annotations

import difflib
import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from process_control import run as run_bounded
from state import atomic_write, write_json


def sources(root):
    root = Path(root)
    paths = [root / name for name in (
        "conductor/PROMPT.md", "conductor/BUILD-SERVICES.md", "conductor/STATUS.md",
        "conductor/scorecard.md", "self-improve-log.md", "BOB-HANDOFF.md",
        "next-prompts/INDEX.md")]
    for directory in ("bin", "conductor/services", "conductor/launchd", "next-prompts"):
        paths.extend((root / directory).glob("*"))
    result = {}
    for path in sorted(set(paths)):
        if path.is_symlink():
            raise ValueError("draft source must not be a symlink: " + str(path))
        if path.is_file() and path.suffix in (".py", ".sh", ".md", ".plist"):
            result[str(path.relative_to(root))] = path.read_text()
    return result


def prepare(root, folder):
    """Copy code and selected evidence, never keys, locks, journals or live jobs."""
    workspace = Path(folder) / "workspace"
    workspace.mkdir(parents=True, exist_ok=False)
    before = sources(root)
    for name, body in before.items():
        atomic_write(workspace / name, body)
    write_json(Path(folder) / "draft-baseline.json", {
        name: hashlib.sha256(body.encode()).hexdigest() for name, body in before.items()})
    return workspace, before


def collect(workspace):
    """Include deletions and new code; refuse aliases out of the draft."""
    workspace = Path(workspace)
    for path in workspace.rglob("*"):
        if path.is_symlink():
            raise ValueError("symlink in draft: " + str(path.relative_to(workspace)))
    return sources(workspace)


def diff(before, after):
    names = sorted(name for name in set(before) | set(after) if before.get(name) != after.get(name))
    patch = "".join("".join(difflib.unified_diff(
        before.get(name, "").splitlines(True), after.get(name, "").splitlines(True),
        fromfile="a/" + name if name in before else "/dev/null",
        tofile="b/" + name if name in after else "/dev/null")) for name in names)
    return names, patch


def validate(workspace, baseline, after, log_path):
    """Run fixed checks, including the original tests, against the candidate copy."""
    workspace, log_path = Path(workspace), Path(log_path)
    tests = sorted(name for name in baseline
                   if name.startswith("conductor/services/test_") and name.endswith(".py"))
    if "conductor/services/test_services.py" not in tests:
        return "baseline test_services.py missing"
    for name in tests:
        if after.get(name) != baseline[name]:
            return "baseline test altered or deleted: " + name
    # Catch a broken entrypoint even when it was not part of the proposed diff.
    for name, body in after.items():
        if name.endswith(".py"):
            try:
                compile(body, name, "exec")
            except (SyntaxError, ValueError):
                return "syntax check failed: " + name
    env = {key: value for key, value in os.environ.items()
           if not any(s in key.upper() for s in ("KEY", "TOKEN", "SECRET", "PASSWORD"))}
    env.update(BOB_ROOT=str(workspace), PYTHONDONTWRITEBYTECODE="1")
    env.pop("PYTHONPATH", None)
    sandbox = Path("/usr/bin/sandbox-exec")
    if not sandbox.is_file():
        return "validation sandbox unavailable; draft retained without executing candidate code"
    # Candidate imports can execute code too. Restrict test writes and network
    # access independently of the agent's own sandbox. Failure is never a pass.
    profile = ('(version 1)(allow default)(deny network*)(deny file-write*)'
               '(allow file-write* (subpath (param "DRAFT"))'
               ' (subpath (param "CHECK_TMP")) (literal "/dev/null"))')
    with tempfile.TemporaryDirectory(prefix="bob-draft-check-") as check_tmp, log_path.open("w") as out:
        env["TMPDIR"] = check_tmp
        for name in sorted(after):
            if name.endswith(".sh"):
                command = ["/bin/bash", "-n", str(workspace / name)]
            elif name in tests:
                command = [sys.executable, str(workspace / name)]
            else:
                continue
            command = [str(sandbox), "-D", "DRAFT=" + str(workspace.resolve()),
                       "-D", "CHECK_TMP=" + str(Path(check_tmp).resolve()), "-p", profile] + command
            out.write("CHECK " + name + "\n")
            out.flush()
            try:
                result = run_bounded(command, cwd=str(workspace), env=env,
                                     stdin=subprocess.DEVNULL, stdout=out,
                                     stderr=subprocess.STDOUT, timeout=300)
            except (OSError, subprocess.TimeoutExpired) as exc:
                return "check unavailable: " + name + " (" + type(exc).__name__ + ")"
            if result.returncode:
                return "check failed: " + name
    return None


def finish(workspace, baseline, folder, *, agent_ok, stage="improvement"):
    """Persist a reviewable diff and honest validation; there is no live rollback."""
    folder = Path(folder)
    after = collect(workspace)
    changed, patch = diff(baseline, after)
    atomic_write(folder / ("proposed.diff" if stage == "improvement" else "work-proposed.diff"), patch)
    failure = None
    if not agent_ok:
        failure = "agent did not complete"
    elif not changed:
        failure = "no proposed change"
    else:
        failure = validate(workspace, baseline, after, folder / (stage + "-validation.log"))
    result = {"applied": False, "draft_verified": failure is None, "changed_files": changed,
              "verification_failure": failure, "workspace": str(workspace),
              "candidate_sha256": {name: hashlib.sha256(body.encode()).hexdigest()
                                   for name, body in after.items() if name in changed}}
    write_json(folder / ("learned-evidence.json" if stage == "improvement" else "work-evidence.json"), result)
    return result
