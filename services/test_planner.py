import concurrent.futures
import subprocess
import unittest

from leases import LeaseConflict, LeaseStore
from planner import ROLES, route, vendor
from swarm_test_support import SwarmRepository


class RoutingTests(unittest.TestCase):
    def test_roles_use_documented_strengths(self):
        expected = dict(architecture="codex", hard_fix="codex", conflict_resolution="codex", deploy="codex",
            design="claude", reply_quality="claude", ux_quality="claude", refactor="claude", final_review="claude",
            feature="cursor", tests="cursor", audit="gemini", gap_analysis="gemini", planning="gemini",
            second_review="gemini", review="minimax", test_cases="minimax", eval_grading="minimax", push_critique="minimax")
        for role, llm in expected.items():
            with self.subTest(role=role):
                self.assertEqual(route(role, author="codex"), llm)
        self.assertEqual(set(expected), set(ROLES))

    def test_no_grok_or_cheap_conflict_or_deploy_fallback(self):
        for role in ROLES:
            with self.subTest(role=role), self.assertRaises(ValueError):
                route(role, available=["grok", "xai"], author="codex")
        for llm in ("grok", "xai", "xAI", "grok-4", "mini"):
            with self.assertRaises(ValueError):
                vendor(llm)
        for role in ("deploy", "conflict_resolution", "hard_fix"):
            for cheap in ("cursor", "minimax", "gemini"):
                with self.assertRaises(ValueError):
                    route(role, requested=cheap)
        with self.assertRaises(ValueError):
            route("feature", available=["codex", "claude"])
        self.assertEqual(route("architecture", available=["claude"]), "claude")

    def test_review_cannot_use_author_or_authors_underlying_vendor(self):
        self.assertEqual(route("review", author="minimax"), "gemini")
        self.assertEqual(route("review", author="cursor", author_vendor="minimax"), "gemini")
        with self.assertRaises(ValueError):
            route("final_review", author="cursor", author_vendor="anthropic")
        for args in ({}, dict(author="cursor"), dict(author="grok")):
            with self.assertRaises(ValueError):
                route("review", **args)
        with self.assertRaises(ValueError):
            vendor("codex", "anthropic")
        with self.assertRaises(ValueError):
            vendor("cursor", "xai")


class PlannerTests(SwarmRepository):
    def test_assignment_board_contains_contract_owner_and_finished_sha(self):
        row = self.worker()
        board = self.planner.board.read()
        self.assertEqual(board["contract_sha"], self.base)
        self.assertEqual(board["workers"]["one"], row)
        self.assertEqual(row["llm"], "cursor")
        self.assertEqual(row["vendor"], "openai")
        self.assertEqual(row["lease"]["paths"], ["code.py"])
        self.assertEqual(row["sha"], self.git("rev-parse", "draft/one"))
        self.assertEqual(row["status"], "finished")

    def test_overlapping_assignment_does_not_add_board_row(self):
        self.worker()
        self.git("branch", "draft/two", self.base)
        with self.assertRaises(LeaseConflict):
            self.planner.assign("two", "Refactor hot file first", "refactor", "draft/two", ["."])
        self.assertEqual(list(self.planner.board.read()["workers"]), ["one"])
        self.assertEqual(len(LeaseStore(self.conductor, "webbob").list()), 1)

    def test_separate_workers_get_distinct_leases_and_atomic_board_updates(self):
        self.worker()
        self.worker("two", "other.py")
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda worker: self.planner.board.update(worker, note=worker), ["one", "two"]))
        board = self.planner.board.read()
        self.assertEqual(board["workers"]["one"]["note"], "one")
        self.assertEqual(board["workers"]["two"]["note"], "two")

    def test_hot_file_refactor_reserves_the_whole_project(self):
        self.git("branch", "draft/refactor")
        self.git("branch", "draft/feature")
        row = self.planner.assign("refactor", "Split shared router", "refactor", "draft/refactor", ["code.py"])
        self.assertEqual(row["lease"]["paths"], ["."])
        with self.assertRaises(LeaseConflict):
            self.planner.assign("feature", "Feature", "feature", "draft/feature", ["other.py"], model_vendor="openai")

    def test_finish_requires_ownership_and_exact_full_sha(self):
        row = self.worker(finish=False)
        for token, sha in [("stale", row["sha"]), (row["lease"]["token"], "deadbeef")]:
            with self.assertRaises(ValueError):
                self.planner.finish("one", token, sha)
        self.planner.start("one", row["lease"]["token"])
        self.planner.finish("one", row["lease"]["token"], self.git("rev-parse", "draft/one"))
        with self.assertRaises(ValueError):
            self.planner.start("one", row["lease"]["token"])

    def test_readonly_reviews_need_author_but_do_not_take_a_write_lease(self):
        self.git("branch", "draft/review")
        row = self.planner.assign("reviewer", "Review repository", "review", "draft/review", ["."], author="codex")
        self.assertEqual(row["llm"], "minimax")
        self.assertIsNone(row["lease"])
        self.assertFalse(LeaseStore(self.conductor, "webbob").list())

    def test_worker_cannot_use_integration_ref_or_ignore_contract(self):
        with self.assertRaises(ValueError):
            self.planner.assign("bad", "Modify", "hard_fix", "integration/webbob", ["."])
        with self.assertRaises(ValueError):
            self.planner.initialize(self.repo, "main", self.base)
        self.git("checkout", "--orphan", "draft/unrelated")
        self.commit("unrelated history")
        self.git("checkout", "main")
        with self.assertRaises(subprocess.CalledProcessError):
            self.planner.assign("bad", "Modify", "hard_fix", "draft/unrelated", ["."])
        self.assertFalse(self.planner.board.read()["workers"])


if __name__ == "__main__":
    unittest.main()
