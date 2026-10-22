"""Real local check execution must precede a successful coding result."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import mini_worker
from result_acceptance import ResultRejected
from workspaces import git


class CodingValidationTests(unittest.TestCase):
    def test_release_commands_cover_api_and_full_project_gates(self):
        storyboard = mini_worker.coding_commands("StoryBoard")
        self.assertEqual(storyboard, [["pnpm", name] for name in
                                     ("typecheck", "lint", "test", "build", "manager:eval")])
        webbob = mini_worker.coding_commands("Web Bob")
        self.assertEqual([argv[argv.index("-s") + 1] for argv in webbob[:2]], ["webchat", "services"])
        self.assertEqual(webbob[2][-1], "webchat/bob_parity_eval.py")

    def exercise(self, body, expected_error=None, timeout=False):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temporary:
            root = Path(temporary)
            cwd, logs = root / "checkout", root / "server-evidence"
            cwd.mkdir()
            logs.mkdir()
            git(cwd, "init", "-b", "draft/validation")
            (cwd / "check.py").write_text(body)
            git(cwd, "add", "check.py")
            git(cwd, "-c", "user.name=Test", "-c", "user.email=test@localhost", "commit", "-m", "Candidate")
            sha = git(cwd, "rev-parse", "HEAD")
            checks = [[sys.executable, "check.py"]]
            with patch.object(mini_worker, "coding_commands", return_value=checks), \
                    patch.dict(os.environ, VALIDATION_SECRET="private-fixture-secret"):
                if timeout:
                    with patch.object(mini_worker, "run", side_effect=subprocess.TimeoutExpired(checks[0], 600)):
                        with self.assertRaisesRegex(ResultRejected, expected_error):
                            mini_worker.verify_coding(cwd, "StoryBoard", logs, lambda text: text)
                elif expected_error:
                    with self.assertRaisesRegex(ResultRejected, expected_error):
                        mini_worker.verify_coding(cwd, "StoryBoard", logs, lambda text: text)
                else:
                    mini_worker.verify_coding(cwd, "StoryBoard", logs, lambda text: text)
            evidence = json.loads((logs / "CODING-VALIDATION.json").read_text())
            self.assertEqual(evidence["sha"], sha)
            self.assertEqual(evidence["all_pass"], expected_error is None)
            if not timeout:
                check = evidence["checks"][0]
                output = Path(check["log"]).read_bytes()
                self.assertEqual(check["sha256"], hashlib.sha256(output).hexdigest())
                self.assertNotIn(b"private-fixture-secret", output)
                self.assertGreaterEqual(check["started_at"], evidence["started_at"])
                self.assertGreaterEqual(check["finished_at"], check["started_at"])
            return evidence

    def test_actual_check_output_is_bound_to_committed_sha(self):
        result = self.exercise("import os\nassert 'VALIDATION_SECRET' not in os.environ\nprint('API tests: 3 passed')\n")
        self.assertIn("API tests: 3 passed", result["checks"][0]["summary"])
        self.assertEqual(result["checks"][0]["exit"], 0)

    def test_failure_and_timeout_never_count_as_pass(self):
        result = self.exercise("print('API test failed')\nraise SystemExit(1)\n", "Required coding check failed")
        self.assertEqual(result["checks"][0]["exit"], 1)
        self.exercise("print('not started')\n", "verification unavailable", timeout=True)

    def test_test_process_cannot_change_candidate_and_still_pass(self):
        self.exercise("from pathlib import Path\nPath('check.py').write_text('modified')\n", "checkout changed")


if __name__ == "__main__":
    unittest.main()
