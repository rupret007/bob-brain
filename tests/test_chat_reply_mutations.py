"""Regression gate: Karen m158 mutants must not survive chat reply tests."""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MUTATION_FILE = REPO_ROOT / "tests" / "fixtures" / "chat_reply_m158.json"
TARGET = REPO_ROOT / "webbob" / "chat_reply.py"


class ChatReplyMutationGate(unittest.TestCase):
    def test_m158_mutants_killed(self):
        muts = json.loads(MUTATION_FILE.read_text())
        orig = TARGET.read_text()
        survivors = []
        try:
            for mutation in muts:
                count = orig.count(mutation["old"])
                if count != 1:
                    self.fail(f"{mutation['name']}: expected one match, found {count}")
                TARGET.write_text(orig.replace(mutation["old"], mutation["new"], 1))
                proc = subprocess.run(
                    [sys.executable, "-m", "unittest", "tests.test_chat_reply", "tests.test_chat_reply_karen_repro", "-q"],
                    cwd=REPO_ROOT,
                    capture_output=True,
                    text=True,
                    timeout=600,
                )
                if proc.returncode == 0:
                    survivors.append(mutation["name"])
        finally:
            TARGET.write_text(orig)
        self.assertEqual(survivors, [], f"surviving mutants: {survivors}")


if __name__ == "__main__":
    unittest.main()
