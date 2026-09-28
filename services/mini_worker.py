"""Local CPU work: run named, bounded test suites without invoking a model."""
import os
import hashlib
import json
import re
import sys
import tempfile
import time
from pathlib import Path

from command import run
from state import atomic_write
from workspaces import git
from result_acceptance import ResultRejected

CODE_ROOT = Path(__file__).resolve().parents[1]


def coding_commands(project):
    """Release-owned checks, never commands supplied by a worker's answer."""
    if project.lower().replace(" ", "") == "webbob":
        return [[sys.executable, "-m", "unittest", "discover", "-s", name, "-p", "test_*.py"]
                for name in ("webchat", "services")] + [[sys.executable, "webchat/bob_parity_eval.py"]]
    if project.lower() == "storyboard":
        # StoryBoard's documented finish gate; pnpm test includes API tests/build.
        return [["pnpm", name] for name in ("typecheck", "lint", "test", "build", "manager:eval")]
    return []


def verify_coding(cwd, project, folder, redact):
    """Reuse the local CPU runner to check a committed coding result before publication."""
    commands = coding_commands(project)
    if not commands:
        return None  # Other projects still require task/diff-aware acceptance.
    sha = git(cwd, "rev-parse", "HEAD")
    evidence = dict(sha=sha, project=project, started_at=time.time(), all_pass=False, checks=[])
    record = folder / "CODING-VALIDATION.json"
    try:
        with tempfile.TemporaryDirectory(prefix="webbob-verify-", dir="/private/tmp") as temporary:
            env = {k: v for k, v in os.environ.items()
                   if not any(s in k.upper() for s in ("KEY", "TOKEN", "SECRET", "PASSWORD"))}
            env.update(BOB_ROOT=temporary, PYTHONDONTWRITEBYTECODE="1", TMPDIR=temporary, CI="1")
            env.pop("PYTHONPATH", None)
            for index, argv in enumerate(commands):
                started = time.time()
                # Use Mini's existing isolated-data execution boundary. The full
                # services suite exercises sandbox-exec itself (macOS cannot nest it).
                result = run(argv, cwd=cwd, env=env,
                             capture_output=True, text=True, timeout=600)
                output = redact(result.stdout + result.stderr)
                path = folder / ("coding-check-" + str(index + 1) + ".log")
                atomic_write(path, output)
                evidence["checks"].append(dict(command=argv, exit=result.returncode, started_at=started,
                                               finished_at=time.time(), log=str(path),
                                               sha256=hashlib.sha256(output.encode()).hexdigest(),
                                               summary=output[-4000:]))
                if result.returncode:
                    raise ResultRejected("Required coding check failed: " + " ".join(argv) + "\n" + output[-1000:])
        if git(cwd, "rev-parse", "HEAD") != sha or git(cwd, "status", "--porcelain"):
            raise ResultRejected("Coding checkout changed during validation")
        evidence["all_pass"] = True
        return evidence
    except Exception as exc:
        evidence["error"] = redact(str(exc))
        if isinstance(exc, ResultRejected):
            raise
        raise ResultRejected("Required coding verification unavailable: " + type(exc).__name__) from exc
    finally:
        evidence["finished_at"] = time.time()
        atomic_write(record, redact(json.dumps(evidence, indent=2)) + "\n")


def execute(row):
    suite = row.get("local_suite")
    if not suite:
        match = re.search(r"\b(services|webchat)/(test_[a-z0-9_]+)\.py\b", row["prompt"])
        suite = "/".join(match.groups()) + ".py" if match else "services/test_services.py"
    if not re.fullmatch(r"(?:services|webchat)/test_[a-z0-9_]+\.py", suite):
        raise RuntimeError("Mini accepts a services/test_*.py or webchat/test_*.py suite")
    target = CODE_ROOT / suite
    if not target.is_file():
        raise RuntimeError("Mini test suite does not exist: " + suite)
    # Tests run from the deployed code with an isolated data root and no keys.
    # No user-supplied shell command, module path, or environment is executed.
    with tempfile.TemporaryDirectory(prefix="webbob-mini-") as folder:
        env = {k: v for k, v in os.environ.items() if not k.endswith(("KEY", "TOKEN", "SECRET", "PASSWORD"))}
        env.update(BOB_ROOT=folder, PYTHONDONTWRITEBYTECODE="1")
        env.pop("PYTHONPATH", None)
        result = run([sys.executable, "-m", "unittest", target.stem, "-v"],
                     cwd=target.parent, env=env, capture_output=True, text=True, timeout=300)
    output = (result.stdout + result.stderr)[-20000:]
    if result.returncode:
        raise RuntimeError("Mini tests failed: " + suite + "\n" + output)
    return "Local CPU test suite: " + suite + "\nExit code: 0\n\n" + output
