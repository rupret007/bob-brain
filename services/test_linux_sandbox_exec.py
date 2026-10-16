"""Linux sandbox-exec helper: deny core writes without blocking sibling git work."""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
HELPER = HERE.parent / ".github/scripts/linux-sandbox-exec.py"


def load_helper():
    spec = importlib.util.spec_from_file_location("linux_sandbox_exec", HELPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HelperPolicyTests(unittest.TestCase):
    def test_deny_list_extracts_subpaths_and_ignores_read_denies(self):
        helper = load_helper()
        policy = (
            '(version 1) (allow default) (deny file-write* '
            '(subpath "/tmp/core") (subpath "/tmp/bin")) '
            '(deny file-read-data (literal "/tmp/core/keys.env"))'
        )
        self.assertEqual(helper.deny_write_paths(policy), ["/tmp/core", "/tmp/bin"])

    def test_bare_write_deny_uses_allow_list(self):
        helper = load_helper()
        policy = (
            '(version 1)(allow default)(deny network*)(deny file-write*)'
            '(allow file-write* (subpath "/tmp/draft") (literal "/dev/null"))'
        )
        self.assertEqual(helper.allow_write_paths(policy), ["/tmp/draft", "/dev/null"])
        self.assertEqual(helper.deny_write_paths(policy), [])


@unittest.skipUnless(Path("/usr/bin/sandbox-exec").is_file(), "sandbox-exec required")
class SiblingWriteTests(unittest.TestCase):
    def test_git_commit_in_sibling_repo_while_core_writes_are_denied(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp", prefix="sandbox-sibling-") as folder:
            root = Path(folder)
            core = root / "conductor"
            repo = root / "repo"
            core.mkdir()
            repo.mkdir()
            (core / "PROMPT.md").write_text("protected\n")
            subprocess.run(["git", "init", "-b", "draft/fixture", str(repo)], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "Fixture"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.email", "fixture@localhost"], check=True)
            (repo / "proof.txt").write_text("verified sibling write\n")
            policy = (
                "(version 1) (allow default) (deny file-write* (subpath "
                + json.dumps(str(core))
                + "))"
            )
            added = subprocess.run(
                ["/usr/bin/sandbox-exec", "-p", policy, "git", "-C", str(repo), "add", "proof.txt"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(added.returncode, 0, added.stderr)
            committed = subprocess.run(
                ["/usr/bin/sandbox-exec", "-p", policy, "git", "-C", str(repo), "commit", "-m", "fixture"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(committed.returncode, 0, committed.stderr)
            denied = subprocess.run(
                [
                    "/usr/bin/sandbox-exec",
                    "-p",
                    policy,
                    sys.executable,
                    "-c",
                    "from pathlib import Path; Path(%r).write_text('bad')" % str(core / "PROMPT.md"),
                ],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(denied.returncode, 0, denied.stdout + denied.stderr)
            self.assertEqual((core / "PROMPT.md").read_text(), "protected\n")


if __name__ == "__main__":
    unittest.main()
