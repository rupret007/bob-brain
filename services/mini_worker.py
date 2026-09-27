"""Local CPU work: run named, bounded test suites without invoking a model."""
import os
import re
import sys
import tempfile
from pathlib import Path

from command import run

CODE_ROOT = Path(__file__).resolve().parents[1]


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
