import contextlib
import io
import json
import unittest
from unittest.mock import patch

from project_board import ProjectBoard
from swarm_test_support import SwarmRepository
import swarm_eval


class ProjectBoardTests(SwarmRepository):
    def test_initialize_is_idempotent_and_cannot_replace_contract(self):
        before = self.planner.board.path.read_bytes()
        self.planner.initialize(self.repo, "integration/webbob", self.base)
        self.assertEqual(before, self.planner.board.path.read_bytes())
        with self.assertRaises(ValueError):
            self.planner.board.initialize(self.repo, "integration/another", self.base)
        self.assertEqual(before, self.planner.board.path.read_bytes())

    def test_board_survives_reload_with_required_worker_fields(self):
        self.worker()
        board = ProjectBoard(self.conductor, "webbob").read()
        row = board["workers"]["one"]
        self.assertTrue(set(("worker", "llm", "lease", "task", "branch", "sha", "status")) <= row.keys())
        self.assertGreater(board["revision"], 0)
        self.assertGreaterEqual(board["updated_at"], row["updated_at"])

    def test_invalid_status_or_corrupt_board_does_not_overwrite_evidence(self):
        self.worker()
        before = self.planner.board.path.read_bytes()
        with self.assertRaises(ValueError):
            self.planner.board.update("one", status="pretend-green")
        self.assertEqual(before, self.planner.board.path.read_bytes())
        self.planner.board.path.write_text("{broken")
        with self.assertRaises(ValueError):
            self.planner.board.update("one", status="merged")
        self.assertEqual(self.planner.board.path.read_text(), "{broken")


class OfflineEvalTests(unittest.TestCase):
    def test_real_parity_eval_passes_with_private_status_fixture(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(swarm_eval.main(), 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["passed"], result["total"])

    def test_even_one_failed_eval_is_red(self):
        with patch.object(swarm_eval, "run_eval", return_value=dict(passed=23, total=24)), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(swarm_eval.main(), 1)


if __name__ == "__main__":
    unittest.main()
