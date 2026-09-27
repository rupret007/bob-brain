"""Exercise real rebases, ref advances, conflicts, and failures in private repos."""
import concurrent.futures
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from leases import LeaseStore
from merge_train import MergeTrain, command_reviewer, review_ok
from swarm_test_support import SwarmRepository

PASS = [[sys.executable, "-c", "pass"]]
FAIL = [[sys.executable, "-c", "import sys; print('expected failure'); sys.exit(1)"]]


class MergeTrainTests(SwarmRepository):
    def approve(self, context):
        return dict(llm="claude", vendor="anthropic", sha=context["sha"], approved=True)

    def train(self, **kwargs):
        return MergeTrain(self.conductor, "webbob", **dict(tests=PASS, evals=PASS, reviewer=self.approve, **kwargs))

    def assert_unchanged(self, row, tip):
        self.assertEqual(self.git("rev-parse", "integration/webbob"), tip)
        self.assertEqual(self.git("rev-parse", row["branch"]), row["sha"])
        self.assertEqual(len(self.git("worktree", "list", "--porcelain").split("worktree ")) - 1, 1)

    def test_green_runs_tests_and_evals_on_rebased_tip_then_fast_forwards(self):
        row = self.worker()
        old = self.advance()
        seen = []
        tests = [[sys.executable, "-c", "from pathlib import Path; assert Path('other.py').read_text() == 'train\\n'; Path('tested').touch()"]]
        evals = [[sys.executable, "-c", "from pathlib import Path; assert Path('tested').exists(); assert Path('code.py').read_text() == 'feature\\n'"]]
        def review(context):
            seen.append(context)
            self.assertNotEqual(context["sha"], row["sha"])
            self.assertEqual(context["integration_sha"], old)
            self.assertIn("feature", context["diff"])
            self.assertEqual(context["intent"], row["task"])
            return self.approve(context)
        train = MergeTrain(self.conductor, "webbob", tests=tests, evals=evals, reviewer=review)
        result = train.process("one")
        self.assertEqual(result["status"], "merged")
        self.assertEqual(self.git("rev-parse", "integration/webbob"), seen[0]["sha"])
        self.git("merge-base", "--is-ancestor", old, seen[0]["sha"])
        self.assertEqual(self.git("rev-parse", row["branch"]), row["sha"])
        self.assertEqual([gate["stage"] for gate in result["gates"]], ["tests", "evals"])
        self.assertFalse(LeaseStore(self.conductor, "webbob").list())
        self.assertIsNone(result["lease"])
        self.assertEqual(train.process("one")["status"], "merged")

    def test_inherited_rebase_update_refs_cannot_rewrite_worker_branch(self):
        row = self.worker()
        self.advance()
        self.git("config", "rebase.updateRefs", "true")
        result = self.train().process("one")
        self.assertEqual(result["status"], "merged")
        self.assertNotEqual(result["integrated_sha"], row["sha"])
        self.assertEqual(self.git("rev-parse", row["branch"]), row["sha"])

    def test_test_failure_bounces_to_same_worker_without_evals_or_review(self):
        row = self.worker()
        with patch.object(self, "approve") as review:
            train = MergeTrain(self.conductor, "webbob", tests=FAIL, evals=PASS, reviewer=review)
            result = train.process("one")
        review.assert_not_called()
        self.assertEqual((result["worker"], result["llm"], result["branch"]), (row["worker"], row["llm"], row["branch"]))
        self.assertEqual(result["status"], "bounced")
        self.assertEqual(result["failure"]["stage"], "tests")
        self.assertIn("expected failure", result["failure"]["detail"])
        self.assertEqual(result["lease"], row["lease"])
        self.assert_unchanged(row, self.base)
        self.planner.start("one", row["lease"]["token"])
        self.planner.finish("one", row["lease"]["token"], row["sha"])
        self.assertEqual(self.train().process("one")["status"], "merged")

    def test_eval_failure_blocks_even_when_unit_tests_pass(self):
        row = self.worker()
        train = MergeTrain(self.conductor, "webbob", tests=PASS, evals=FAIL, reviewer=self.approve)
        result = train.process("one")
        self.assertEqual(result["status"], "bounced")
        self.assertEqual(result["failure"]["stage"], "evals")
        self.assertEqual([gate["returncode"] for gate in result["gates"]], [0, 1])
        self.assert_unchanged(row, self.base)

    def test_no_review_is_not_green(self):
        row = self.worker()
        train = MergeTrain(self.conductor, "webbob", tests=PASS, evals=PASS)
        result = train.process("one")
        self.assertEqual(result["failure"]["stage"], "review")
        self.assert_unchanged(row, self.base)

    def test_conflict_job_has_both_diffs_intent_and_codex_ownership_then_reenters_gates(self):
        row = self.worker()
        old = self.advance("code.py", "other worker\n")
        result = self.train().process("one")
        self.assertEqual(result["status"], "conflict")
        job = self.planner.board.read()["resolver_jobs"][result["resolver_job_id"]]
        self.assertEqual((job["status"], job["llm"]), ("queued", "codex"))
        self.assertEqual(job["intent"], row["task"])
        self.assertEqual(job["conflicts"], ["code.py"])
        self.assertIn("+feature", job["worker_diff"])
        self.assertIn("+other worker", job["integration_diff"])
        self.assert_unchanged(row, old)
        self.assertEqual(self.train().tick(), [])
        resolver = self.planner.claim_resolver(job["id"], "resolver-one")
        self.assertEqual(resolver["llm"], "codex")
        self.assertEqual(LeaseStore(self.conductor, "webbob").list(), [resolver["lease"]])
        with self.assertRaises(ValueError):
            self.planner.finish("one", row["lease"]["token"], row["sha"])
        with self.assertRaises(ValueError):
            self.planner.claim_resolver(job["id"], "resolver-two")
        self.git("checkout", resolver["branch"])
        rebase = subprocess.run(["git", "-C", str(self.repo), "rebase", "--onto", old, job["base_sha"]],
                                capture_output=True, text=True, timeout=15)
        self.assertNotEqual(rebase.returncode, 0)
        (self.repo / "code.py").write_text("feature and other worker\n")
        self.git("add", "code.py")
        self.git("-c", "core.editor=true", "rebase", "--continue")
        resolved_sha = self.git("rev-parse", "HEAD")
        self.git("checkout", "main")
        self.planner.finish(resolver["worker"], resolver["lease"]["token"], resolved_sha)
        self.assertEqual(self.train().process(resolver["worker"])["status"], "merged")
        board = self.planner.board.read()
        self.assertEqual(board["resolver_jobs"][job["id"]]["status"], "resolved")
        self.assertEqual(board["workers"]["one"]["status"], "merged")
        self.assertFalse(LeaseStore(self.conductor, "webbob").list())
        self.assertEqual(self.git("rev-parse", row["branch"]), row["sha"])

    def test_wrong_scope_and_renamed_unowned_source_cannot_integrate(self):
        row = self.worker()
        self.git("checkout", "draft/one")
        self.git("mv", "other.py", "extra.py")
        sha = self.commit("rename outside lease")
        self.git("checkout", "main")
        self.planner.board.update("one", status="running")
        self.planner.finish("one", row["lease"]["token"], sha)
        result = self.train().process("one")
        self.assertEqual(result["failure"]["stage"], "lease")
        self.assertEqual(self.git("rev-parse", "integration/webbob"), self.base)

    def test_leading_space_filename_cannot_impersonate_an_owned_path(self):
        row = self.worker()
        self.git("checkout", "draft/one")
        (self.repo / " code.py").write_text("unowned file\n")
        sha = self.commit("unowned leading-space path")
        self.git("checkout", "main")
        self.planner.board.update("one", status="running")
        self.planner.finish("one", row["lease"]["token"], sha)
        self.assertEqual(self.train().process("one")["failure"]["stage"], "lease")
        self.assertEqual(self.git("rev-parse", "integration/webbob"), self.base)

    def test_tip_race_during_gates_does_not_overwrite_other_integrator(self):
        row = self.worker()
        advanced = []
        def review(context):
            advanced.append(self.advance())
            return self.approve(context)
        train = MergeTrain(self.conductor, "webbob", tests=PASS, evals=PASS, reviewer=review)
        result = train.process("one")
        self.assertEqual(result["failure"]["stage"], "integration")
        self.assert_unchanged(row, advanced[0])

    def test_worker_movement_during_review_invalidates_result(self):
        row = self.worker()
        def review(context):
            self.git("checkout", "draft/one")
            (self.repo / "code.py").write_text("new untested work\n")
            self.commit("new work")
            self.git("checkout", "main")
            return self.approve(context)
        train = MergeTrain(self.conductor, "webbob", tests=PASS, evals=PASS, reviewer=review)
        self.assertEqual(train.process("one")["failure"]["stage"], "worker")
        self.assertEqual(self.git("rev-parse", "integration/webbob"), self.base)
        self.assertNotEqual(self.git("rev-parse", row["branch"]), row["sha"])

    def test_lease_release_during_review_blocks_advance(self):
        row = self.worker()
        def review(context):
            LeaseStore(self.conductor, "webbob").release("one", row["lease"]["token"])
            return self.approve(context)
        train = MergeTrain(self.conductor, "webbob", tests=PASS, evals=PASS, reviewer=review)
        self.assertEqual(train.process("one")["failure"]["stage"], "lease")
        self.assert_unchanged(row, self.base)

    def test_gates_cannot_modify_the_candidate_they_certify(self):
        row = self.worker()
        tests = [[sys.executable, "-c", "from pathlib import Path; Path('code.py').write_text('tampered')"]]
        train = MergeTrain(self.conductor, "webbob", tests=tests, evals=PASS, reviewer=self.approve)
        self.assertEqual(train.process("one")["failure"]["stage"], "checkout")
        self.assert_unchanged(row, self.base)

    def test_source_checkout_and_unfinished_workers_are_untouched(self):
        row = self.worker(finish=False)
        (self.repo / "code.py").write_text("uncommitted bystander\n")
        with self.assertRaises(ValueError):
            self.train().process("one")
        self.planner.finish("one", row["lease"]["token"], self.git("rev-parse", row["branch"]))
        self.assertEqual(self.train().process("one")["status"], "merged")
        self.assertEqual((self.repo / "code.py").read_text(), "uncommitted bystander\n")
        self.assertEqual(self.git("branch", "--show-current"), "main")

    def test_checked_out_train_is_refused(self):
        row = self.worker()
        self.git("checkout", "integration/webbob")
        result = self.train().process("one")
        self.assertEqual(result["failure"]["stage"], "integration")
        self.assert_unchanged(row, self.base)

    def test_timeout_and_missing_command_bounce_without_advancing(self):
        row = self.worker()
        for suite in ([[sys.executable, "-c", "import time; time.sleep(10)"]], [["/no/such/swarm-command"]]):
            self.planner.board.update("one", status="finished")
            train = MergeTrain(self.conductor, "webbob", tests=suite, evals=PASS, reviewer=self.approve, timeout=.1)
            result = train.process("one")
            self.assertEqual(result["status"], "bounced")
            self.assertEqual(result["failure"]["stage"], "tests")
            self.assert_unchanged(row, self.base)

    def test_concurrent_processors_advance_and_review_only_once(self):
        self.worker()
        with patch.object(self, "approve", wraps=self.approve) as review:
            train = MergeTrain(self.conductor, "webbob", tests=PASS, evals=PASS, reviewer=review)
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(train.process, ["one", "one"]))
            self.assertEqual(review.call_count, 1)
        self.assertEqual([r["status"] for r in results], ["merged", "merged"])

    def test_interruption_after_ref_advance_recovers_board_and_releases_lease(self):
        row = self.worker()
        train = self.train()
        update = train.board.update
        def interrupt(worker, **fields):
            if fields.get("status") == "merged":
                raise KeyboardInterrupt("simulated process death")
            return update(worker, **fields)
        with patch.object(train.board, "update", side_effect=interrupt), self.assertRaises(KeyboardInterrupt):
            train.process("one")
        self.assertNotEqual(self.git("rev-parse", "integration/webbob"), self.base)
        self.assertEqual(self.planner.board.read()["workers"]["one"]["status"], "integrating")
        self.assertEqual(self.train().process("one")["status"], "merged")
        self.assertFalse(LeaseStore(self.conductor, "webbob").list())
        self.assertEqual(self.git("rev-parse", row["branch"]), row["sha"])

    def test_board_io_error_after_advance_does_not_claim_a_false_bounce(self):
        self.worker()
        train = self.train()
        update = train.board.update
        def disk_error(worker, **fields):
            if fields.get("status") == "merged":
                raise OSError("board disk unavailable")
            return update(worker, **fields)
        with patch.object(train.board, "update", side_effect=disk_error), self.assertRaises(OSError):
            train.process("one")
        self.assertEqual(self.planner.board.read()["workers"]["one"]["status"], "integrating")
        self.assertEqual(self.train().tick()[0]["status"], "merged")

    def test_tick_releases_lease_after_interrupted_green_closeout(self):
        self.worker()
        with patch.object(LeaseStore, "release", side_effect=OSError("disk unavailable")), self.assertRaises(OSError):
            self.train().process("one")
        self.assertEqual(self.planner.board.read()["workers"]["one"]["status"], "merged")
        self.assertTrue(LeaseStore(self.conductor, "webbob").list())
        self.assertEqual(self.train().tick()[0]["status"], "merged")
        self.assertFalse(LeaseStore(self.conductor, "webbob").list())

    def test_resolver_claim_recovers_after_transfer_before_board_write(self):
        self.worker()
        self.advance("code.py", "conflict\n")
        row = self.train().process("one")
        change = self.planner.board.change
        count = 0
        def disk_error(callback):
            nonlocal count
            count += 1
            if count == 2:
                raise OSError("interrupted resolver claim")
            return change(callback)
        with patch.object(self.planner.board, "change", side_effect=disk_error), self.assertRaises(OSError):
            self.planner.claim_resolver(row["resolver_job_id"], "resolver-one")
        lease = LeaseStore(self.conductor, "webbob").list()[0]
        self.assertEqual(lease["owner"], "resolver-one")
        claimed = self.planner.claim_resolver(row["resolver_job_id"], "resolver-one")
        self.assertEqual(claimed["lease"], lease)
        self.assertEqual(self.planner.claim_resolver(row["resolver_job_id"], "resolver-one"), claimed)

    def test_tick_rebases_two_disjoint_workers_in_sequence(self):
        self.worker()
        self.worker("two", "other.py")
        results = self.train().tick()
        self.assertEqual([r["status"] for r in results], ["merged", "merged"])
        self.assertEqual(self.git("show", "integration/webbob:code.py"), "feature")
        self.assertEqual(self.git("show", "integration/webbob:other.py"), "feature")


class GateContractTests(unittest.TestCase):
    def test_empty_or_shell_string_suites_are_rejected(self):
        for value in (None, [], "python tests.py", ["python tests.py"], [[]], [[""]]):
            with self.subTest(value=value), self.assertRaises(ValueError):
                MergeTrain("unused", "webbob", tests=value, evals=PASS)
            with self.assertRaises(ValueError):
                MergeTrain("unused", "webbob", tests=PASS, evals=value)

    def test_review_is_exact_sha_cross_vendor_allowlisted_and_boolean(self):
        authors = [dict(llm="cursor", vendor="anthropic"), dict(llm="codex", vendor="openai")]
        good = dict(llm="gemini", vendor="google", sha="candidate", approved=True)
        self.assertTrue(review_ok(good, "candidate", authors))
        for change in (dict(llm="grok", vendor="xai"), dict(llm="claude", vendor="anthropic"),
                       dict(llm="codex", vendor="openai"), dict(llm="cursor", vendor="google"),
                       dict(llm="gemini", vendor="anthropic"), dict(sha="old"), dict(approved="true"),
                       dict(approved=False)):
            with self.subTest(change=change):
                self.assertFalse(review_ok(dict(good, **change), "candidate", authors))
        self.assertFalse(review_ok(None, "candidate", authors))

    def test_command_reviewer_receives_candidate_context_and_parses_receipt(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            context = dict(worktree=folder, sha="candidate", intent="Review")
            # Use a nested directory so the adapter's context stays in this fixture.
            context["worktree"] = str(Path(folder) / "candidate")
            Path(context["worktree"]).mkdir()
            script = ("import json,sys; c=json.load(open(sys.argv[1])); "
                      "print(json.dumps(dict(llm='gemini', vendor='google', sha=c['sha'], approved=True)))")
            result = command_reviewer([sys.executable, "-c", script], 5)(context)
            self.assertTrue(review_ok(result, "candidate", [dict(llm="codex", vendor="openai")]))
            self.assertEqual(json.loads((Path(folder) / "review-context.json").read_text()), context)


if __name__ == "__main__":
    unittest.main()
