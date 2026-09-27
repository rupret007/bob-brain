#!/usr/bin/env python3
"""Scheduler regressions with isolated journals, real Git, and no paid model calls."""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import api
import budget
import jobs
import lanes
import queue_store as queue
import runtime
import scheduler
import state
import worker
import workspaces


class SchedulerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="lane-scheduler-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.core = self.root / "conductor"
        self.core.mkdir()
        for module in (api, budget, jobs, lanes, runtime, state, worker, workspaces):
            for name, value in (("ROOT", self.root), ("CONDUCTOR", self.core)):
                if hasattr(module, name):
                    self.start_patch(patch.object(module, name, value))
        self.start_patch(patch.object(runtime, "HEARTBEATS", self.core / "heartbeats"))
        self.start_patch(patch.dict(os.environ, {"BOB_ROOT": str(self.root)}))
        self.sessions = {}
        self.health = {lane: {"state": "ready"} for lane in lanes.SCHEDULER_LANES}
        self.start_patch(patch.object(runtime, "screen_sessions", side_effect=lambda: dict(self.sessions)))
        self.start_patch(patch.object(lanes, "refresh", side_effect=lambda: json.loads(json.dumps(self.health))))
        self.launcher = self.start_patch(patch.object(jobs, "launch", side_effect=self.fake_launch))
        self.repo = self.root / "repo"
        self.repo.mkdir()
        workspaces.git(self.repo, "init", "-b", "draft/fixture")
        workspaces.git(self.repo, "config", "user.name", "Scheduler Test")
        workspaces.git(self.repo, "config", "user.email", "scheduler@localhost")
        (self.repo / "src").mkdir()
        for name in ("a", "b"):
            (self.repo / "src" / name).write_text("baseline\n")
        workspaces.git(self.repo, "add", ".")
        workspaces.git(self.repo, "commit", "-m", "fixture")
        self.remote = self.root / "remote.git"
        workspaces.git(self.root, "init", "--bare", str(self.remote))
        workspaces.git(self.repo, "remote", "add", "origin", str(self.remote))

    def start_patch(self, p):
        self.addCleanup(p.stop)
        return p.start()

    def fake_launch(self, identifier, folder):
        self.sessions[identifier] = "123." + identifier
        state.job_event(identifier, "running")

    def enqueue(self, identifier="task", **fields):
        spec = dict(id=identifier, goal="Inspect the fixture", repo=str(self.repo), role="research", priority=10)
        spec.update(fields)
        return queue.enqueue(spec)

    def record(self, identifier="task"):
        return scheduler.execution_for(queue.snapshot()[identifier], state.jobs())

    def finish(self, identifier="task", verdict=None):
        """A verified fixture closeout; tests of real execution use execute() below."""
        record = self.record(identifier)
        result = Path(record["job_dir"]) / "RESULT.txt"
        result.write_text("Fixture evidence.\n" + ("VERDICT: " + verdict + "\n" if verdict else ""))
        state.job_event(record["job_id"], verified=True, verified_sha256=hashlib.sha256(result.read_bytes()).hexdigest(), verdict=verdict)
        self.sessions.pop(record["job_id"], None)
        jobs.recover()
        scheduler.reconcile()

    def execute(self, identifier="task", answer="Observed fixture evidence."):
        record = self.record(identifier)
        kwargs = {"side_effect": answer} if callable(answer) else {"return_value": answer}
        with patch.object(worker, "ask", **kwargs):
            result = worker.execute(record["job_id"], record["attempt_token"])
        self.sessions.pop(record["job_id"], None)
        jobs.recover()
        scheduler.reconcile()
        return result

    def build_answer(self, filename="src/a", text="changed\n"):
        def answer(lane, prompt, *, cwd, **kwargs):
            (cwd / filename).write_text(text)
            workspaces.git(cwd, "add", filename)
            workspaces.git(cwd, "commit", "-m", "fixture scoped change")
            workspaces.git(cwd, "push", "origin", "HEAD")
            return "Committed and pushed fixture change; scheduler must verify tests."
        return answer

    def test_concurrent_enqueue_is_durable_and_idempotent(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda _: self.enqueue(), range(24)))
        self.assertEqual(len(queue.snapshot()), 1)
        self.assertEqual(len((self.core / "state/queue.jsonl").read_text().splitlines()), 1)
        with self.assertRaisesRegex(ValueError, "different request"):
            self.enqueue(goal="Different goal")

    def test_interrupted_queue_tail_recovered_middle_corruption_rejected(self):
        self.enqueue()
        path = self.core / "state/queue.jsonl"
        with path.open("ab") as out:
            out.write(b'{"partial')
        self.assertIn("task", queue.snapshot())
        self.assertTrue(path.with_name("queue.jsonl.interrupted-tail").exists())
        path.write_text("bad\n" + path.read_text())
        with self.assertRaises(ValueError):
            queue.snapshot()

    def test_targeted_tick_leaves_unrequested_work_queued(self):
        self.enqueue("target")
        self.enqueue("other", priority=1)
        scheduler.tick(request_ids={"target"})
        self.assertIsNotNone(self.record("target"))
        self.assertIsNone(self.record("other"))
        self.assertEqual(queue.snapshot()["other"]["status"], "queued")

    def test_launch_intent_is_not_a_started_worker_receipt(self):
        import dispatch_request
        self.enqueue()
        result = dispatch_request.start_request("task", wait_seconds=0)
        self.assertFalse(result["started"])
        self.assertEqual(result["status"], "running")
        self.assertIsNone(result["worker_pid"])

    def test_busy_lane_and_paused_scheduler_keep_request_queued(self):
        import dispatch_request
        self.enqueue()
        for lane in self.health:
            self.health[lane]["state"] = "busy"
        result = dispatch_request.start_request("task", wait_seconds=0)
        self.assertFalse(result["started"])
        self.assertEqual(result["status"], "queued")
        (self.core / "MAINTENANCE").touch()
        result = dispatch_request.start_request("task", wait_seconds=0)
        self.assertFalse(result["started"])
        self.assertIn("paused", result["reason"])
        self.launcher.assert_not_called()

    def test_producer_updates_refuse_assigned_jobs(self):
        self.enqueue()
        scheduler.tick()
        with self.assertRaisesRegex(ValueError, "already assigned"):
            queue.edit_pending("task", status="cancelled")
        self.assertEqual(queue.snapshot()["task"]["status"], "running")

    def test_producer_roots_do_not_share_journals_or_locks(self):
        self.enqueue()
        other = self.root / "other/conductor"
        queue.enqueue(dict(id="task", goal="Separate root", repo=str(self.repo)), conductor=other)
        queue.edit_pending("task", priority=1, status="cancelled", conductor=other)
        self.assertEqual(queue.snapshot()["task"]["status"], "queued")
        self.assertEqual(queue.snapshot(conductor=other)["task"]["status"], "cancelled")
        self.assertTrue((other / "locks/queue-store.lock").is_file())

    def test_scope_validation_and_directory_overlap(self):
        for scope in (["../outside"], ["/absolute"], [".git/config"], ["src/*.py"], []):
            with self.subTest(scope=scope), self.assertRaises(ValueError):
                self.enqueue(scope=scope)
        self.assertTrue(queue.overlaps(["src"], ["src/a"]))
        self.assertTrue(queue.overlaps(None, ["src/a"]))
        self.assertFalse(queue.overlaps(["src/a"], ["src/ab"]))

    def test_queue_without_index_fills_six_lanes_and_does_not_duplicate(self):
        for identifier, role, scope in (("build-a", "build", ["src/a"]), ("build-b", "build", ["src/b"]),
                                        ("review", "review", ["."]), ("research", "research", ["."]),
                                        ("critique", "critique", ["."]), ("tests", "test", ["."])):
            self.enqueue(identifier, role=role, scope=scope)
        scheduler.tick()
        self.assertEqual({r["engine"] for r in state.jobs().values()}, set(lanes.SCHEDULER_LANES))
        self.assertEqual(len({r["branch"] for r in state.jobs().values()}), 6)
        self.assertEqual(len({r["worktree"] for r in state.jobs().values()}), 6)
        scheduler.tick()
        self.assertEqual(self.launcher.call_count, 6)
        self.assertFalse((self.root / "next-prompts/INDEX.md").exists())

    def test_priority_and_overlapping_scopes_serialize_same_repo(self):
        self.enqueue("late", role="build", scope=["src"], priority=20)
        self.enqueue("first", role="build", scope=["src/a"], priority=1)
        self.enqueue("parallel", role="build", scope=["other"], priority=10)
        scheduler.tick()
        self.assertIsNone(self.record("late"))
        self.assertEqual(self.record("first")["engine"], "cursor")
        self.assertEqual(self.record("parallel")["engine"], "codex")

    def test_legacy_webjam_unknown_scope_remains_exclusive(self):
        coder = dict(kind="coding", project="WebJam")
        self.assertFalse(jobs.can_assign(coder, "cursor", [dict(coder, engine="codex")], self.health))
        self.assertTrue(jobs.can_assign(dict(coder, repo=str(self.repo), scope=["src/a"]), "cursor",
                        [dict(coder, repo=str(self.repo), scope=["src/b"], engine="codex")], self.health))

    def test_same_repo_worktree_alias_cannot_bypass_scope(self):
        alias = self.root / "alias"
        workspaces.git(self.repo, "worktree", "add", "-b", "draft/alias", str(alias))
        spec = dict(kind="coding", repo=str(self.repo), scope=["src"])
        active = [dict(spec, repo=str(alias), engine="codex")]
        self.assertFalse(jobs.can_assign(spec, "cursor", active, self.health))

    def test_split_is_idempotent_after_partial_expansion(self):
        self.enqueue("large", parts=[{"goal": "Build A", "role": "build", "scope": ["src/a"]},
                                      {"goal": "Build B", "role": "build", "scope": ["src/b"]}])
        children = queue.split("large")
        queue.update("large", status="queued")  # crash before parent transition
        self.assertEqual(queue.split("large"), children)
        scheduler.tick()
        self.assertEqual(len(queue.snapshot()), 3)
        self.assertEqual(len(state.jobs()), 2)

    def test_malformed_parts_are_rejected_before_any_journal_write(self):
        for parts in ([{"role": "build"}], [{"goal": "child", "scope": ["../outside"]}],
                      [{"goal": "child", "parts": [{"goal": "nested"}]}]):
            with self.subTest(parts=parts), self.assertRaises(ValueError):
                self.enqueue(parts=parts)
        self.assertEqual(queue.snapshot(), {})

    def test_launch_reservation_survives_screen_visibility_delay(self):
        self.enqueue(role="build", scope=["src/a"])
        scheduler.tick()
        self.sessions.clear()
        scheduler.tick()
        self.assertEqual(self.launcher.call_count, 1)
        self.assertEqual(self.record()["attempts"], 1)

    def test_one_retry_then_fallback_each_lane_has_bounded_attempts(self):
        self.enqueue(role="build", scope=["src/a"])
        chosen = []
        for _ in range(4):
            scheduler.tick()
            record = self.record()
            chosen.append(record["engine"])
            self.sessions.clear()
            jobs.blocked(record, "fixture failure")
            state.job_event(record["job_id"], retry_at=0)
            scheduler.reconcile()
        scheduler.tick()
        self.assertEqual(chosen, ["cursor", "cursor", "codex", "codex"])
        self.assertEqual(queue.snapshot()["task"]["status"], "blocked")
        self.assertEqual(self.launcher.call_count, 4)

    def test_unavailable_primary_falls_back_without_using_ineligible_lanes(self):
        self.health["cursor"]["state"] = "needs_login"
        self.enqueue(role="build")
        scheduler.tick()
        self.assertEqual(self.record()["engine"], "codex")
        self.assertFalse(jobs.can_assign(queue.snapshot()["task"], "claude", [], self.health))

    def test_stale_worker_must_stop_before_reassignment(self):
        self.enqueue()
        scheduler.tick()
        record = self.record()
        state.job_event(record["job_id"], heartbeat=time.time() - 200)
        with patch.object(scheduler, "stop_stale_worker", return_value=False):
            scheduler.tick()
        self.assertEqual(self.launcher.call_count, 1)
        self.assertEqual(self.record()["state"], "running")
        with patch.object(scheduler, "stop_stale_worker", return_value=True):
            jobs.recover()
        self.assertEqual(self.record()["state"], "blocked")
        self.assertGreater(self.record()["retry_at"], time.time())

    def test_live_worker_lease_prevents_orphan_retry_even_without_screen(self):
        self.enqueue()
        scheduler.tick()
        record = self.record()
        self.sessions.clear()
        with state.lock("worker-" + record["job_id"]):
            jobs.recover()
        self.assertEqual(self.record()["state"], "running")

    def test_worker_pulses_heartbeat_while_model_is_running(self):
        self.enqueue()
        scheduler.tick()
        before = self.record()["heartbeat"]
        def answer(*args, **kwargs):
            time.sleep(.06)
            self.assertGreater(self.record()["heartbeat"], before)
            self.assertGreater(queue.snapshot()["task"]["heartbeat"], before)
            return "Observed local evidence."
        with patch.object(worker, "HEARTBEAT_SECONDS", .01):
            self.assertEqual(self.execute(answer=answer), 0)
        self.assertEqual(queue.snapshot()["task"]["status"], "review")

    def test_old_attempt_token_cannot_execute_or_overwrite_current_job(self):
        self.enqueue()
        scheduler.tick()
        record = self.record()
        with patch.object(worker, "ask") as ask:
            self.assertEqual(worker.execute(record["job_id"], "old-token"), 0)
        ask.assert_not_called()
        state.job_event(record["job_id"], "blocked", expected_token="old-token")
        queue.update("task", expected_token="old-token", heartbeat=1)
        self.assertEqual(self.record()["state"], "running")
        self.assertNotEqual(queue.snapshot()["task"]["heartbeat"], 1)

    def test_lane_contention_does_not_consume_an_attempt(self):
        self.enqueue()
        scheduler.tick()
        record = self.record()
        with state.lock("lane-" + record["engine"]):
            self.assertEqual(worker.execute(record["job_id"], record["attempt_token"]), 0)
        self.assertEqual(self.record()["attempts"], 0)
        self.assertEqual(self.record()["lane_attempts"][record["engine"]], 0)

    def test_build_runs_real_tests_and_records_exact_sha(self):
        self.enqueue(role="build", scope=["src/a"], test_commands=[[sys.executable, "-c", "assert open('src/a').read() == 'changed\\n'"]])
        scheduler.tick()
        self.assertEqual(self.execute(answer=self.build_answer()), 0)
        record = self.record()
        self.assertEqual(record["tests_sha"], record["head_sha"])
        self.assertEqual(record["changed_paths"], ["src/a"])
        self.assertEqual(queue.snapshot()["task"]["status"], "review")
        self.assertTrue((Path(record["job_dir"]) / "tests.json").exists())

    def test_failed_tests_and_out_of_scope_changes_cannot_promote(self):
        self.enqueue("bad-tests", role="build", scope=["src/a"], test_commands=[[sys.executable, "-c", "raise SystemExit(7)"]])
        self.enqueue("bad-scope", role="build", scope=["src/b"], test_commands=[[sys.executable, "-c", "pass"]])
        scheduler.tick()
        self.assertEqual(self.execute("bad-tests", self.build_answer()), 1)
        self.assertEqual(self.execute("bad-scope", self.build_answer()), 1)
        self.assertIn("branch test failed", self.record("bad-tests")["recovery"])
        self.assertIn("outside assigned scope", self.record("bad-scope")["recovery"])
        self.assertFalse(any(r["stage"] == "review" for r in queue.snapshot().values()))

    def test_mini_lane_executes_tests_without_a_model(self):
        self.enqueue(role="test", test_commands=[[sys.executable, "-c", "assert open('src/a').read() == 'baseline\\n'"]])
        scheduler.tick()
        self.assertEqual(self.record()["engine"], "mini")
        with patch.object(worker, "ask", side_effect=AssertionError("mini must not call a model")):
            record = self.record()
            self.assertEqual(worker.execute(record["job_id"], record["attempt_token"]), 0)

    def test_missing_tests_blocks_before_spending_model_call(self):
        self.enqueue(role="build")
        scheduler.tick()
        record = self.record()
        with patch.object(worker, "ask") as ask:
            self.assertEqual(worker.execute(record["job_id"], record["attempt_token"]), 1)
        ask.assert_not_called()

    def test_result_tampering_is_not_harvested(self):
        self.enqueue()
        scheduler.tick()
        record = self.record()
        with patch.object(worker, "ask", return_value="Verified original"):
            worker.execute(record["job_id"], record["attempt_token"])
        (Path(record["job_dir"]) / "RESULT.txt").write_text("Changed after verification")
        self.sessions.clear()
        jobs.recover()
        self.assertEqual(self.record()["state"], "blocked")
        self.assertFalse(self.record()["verified"])

    def test_untracked_implementation_cannot_be_presented_as_tested_commit(self):
        self.enqueue(role="build", scope=["src"], test_commands=[[sys.executable, "-c", "pass"]])
        scheduler.tick()
        def answer(*args, cwd, **kwargs):
            (cwd / "src/uncommitted.py").write_text("print('missing from commit')\n")
            return "Claimed implementation complete"
        self.assertEqual(self.execute(answer=answer), 1)
        self.assertIn("untracked changes remain", self.record()["recovery"])
        self.assertFalse(self.record()["verified"])

    def test_legacy_queued_job_without_ready_index_row_is_adopted(self):
        record = jobs.create_record(dict(id="old", project="WebBob", repo=str(self.repo),
                                         prompt="Retain old research job", kind="non-coding"), "gemini")
        scheduler.tick()
        self.assertEqual(queue.snapshot()["old"]["execution_id"], record["job_id"])
        self.assertEqual(len(state.jobs()), 1)
        self.assertEqual(self.record("old")["state"], "running")

    def test_result_promotes_review_then_two_distinct_council_receipts(self):
        self.enqueue()
        scheduler.tick()
        self.finish()
        review = queue.snapshot()["task"]["review_id"]
        scheduler.tick()
        self.assertEqual(self.record(review)["engine"], "claude")
        self.finish(review, "PASS")
        self.assertEqual(queue.snapshot()["task"]["status"], "council")
        scheduler.tick()
        members = queue.snapshot()["task"]["council_ids"]
        self.assertEqual({self.record(i)["engine"] for i in members}, {"gemini", "minimax"})
        self.finish(members[0], "PASS")
        self.assertEqual(queue.snapshot()["task"]["status"], "council")
        self.finish(members[1], "PASS")
        self.assertEqual(queue.snapshot()["task"]["status"], "jeff-draft")
        count = len(queue.snapshot())
        scheduler.tick()
        self.assertEqual(len(queue.snapshot()), count)

    def test_review_missing_or_negative_verdict_never_advances(self):
        self.enqueue()
        scheduler.tick()
        self.finish()
        review = queue.snapshot()["task"]["review_id"]
        scheduler.tick()
        self.assertEqual(self.execute(review, "Looks okay, but no explicit approval."), 1)
        self.assertEqual(queue.snapshot()["task"]["status"], "review")
        self.assertFalse(any(r["stage"] == "council" for r in queue.snapshot().values()))

    def test_explicit_rejection_is_preserved_without_retrying_for_an_approval(self):
        self.enqueue()
        scheduler.tick()
        self.finish()
        review = queue.snapshot()["task"]["review_id"]
        scheduler.tick()
        self.assertEqual(self.execute(review, "Reproducible defect found.\nVERDICT: FAIL"), 0)
        scheduler.tick()
        self.assertEqual(queue.snapshot()[review]["status"], "blocked")
        self.assertTrue(queue.snapshot()[review]["decision_rejected"])
        self.assertIn("review blocked", queue.snapshot()["task"]["reason"])
        self.assertEqual(self.record(review)["attempts"], 1)
        self.assertFalse(any(r["stage"] == "council" for r in queue.snapshot().values()))

    def test_launch_return_cannot_overwrite_a_fast_worker_blocker(self):
        self.enqueue()
        scheduler.tick()
        record = self.record()
        state.job_event(record["job_id"], "blocked")
        state.job_event(record["job_id"], "running", expected_states=("launched",),
                        expected_token=record["attempt_token"])
        self.assertEqual(self.record()["state"], "blocked")

    def test_single_council_provider_cannot_supply_both_approvals(self):
        self.enqueue()
        scheduler.tick()
        self.finish()
        review = queue.snapshot()["task"]["review_id"]
        scheduler.tick()
        self.finish(review, "PASS")
        scheduler.tick()
        first, second = queue.snapshot()["task"]["council_ids"]
        self.finish(first, "PASS")
        other = self.record(second)
        state.job_event(other["job_id"], engine=self.record(first)["engine"])
        self.finish(second, "PASS")
        self.assertEqual(queue.snapshot()["task"]["status"], "council")

    def test_branch_changed_after_tests_cannot_reuse_old_review_receipts(self):
        self.enqueue(role="build", scope=["src/a"], test_commands=[[sys.executable, "-c", "pass"]])
        scheduler.tick()
        self.assertEqual(self.execute(answer=self.build_answer()), 0)
        review = queue.snapshot()["task"]["review_id"]
        scheduler.tick()
        self.finish(review, "PASS")
        scheduler.tick()
        record = self.record()
        workspaces.git(record["worktree"], "commit", "--allow-empty", "-m", "changed after tests")
        for member in queue.snapshot()["task"]["council_ids"]:
            self.finish(member, "PASS")
        self.assertEqual(queue.snapshot()["task"]["status"], "blocked")
        self.assertIn("branch changed after tests", queue.snapshot()["task"]["reason"])

    def test_sibling_conflict_check_uses_real_git_without_merging(self):
        self.enqueue("parent", parts=[{"goal": "First", "role": "build", "scope": ["src/a"],
                                        "test_commands": [[sys.executable, "-c", "pass"]]},
                                       {"goal": "Second", "role": "build", "scope": ["src/a"],
                                        "test_commands": [[sys.executable, "-c", "pass"]]}])
        source_head = workspaces.git(self.repo, "rev-parse", "HEAD")
        scheduler.tick()
        first, second = queue.snapshot()["parent"]["children"]
        self.assertIsNone(self.record(second))
        self.assertEqual(self.execute(first, self.build_answer(text="first\n")), 0)
        self.assertEqual(queue.snapshot()[first]["status"], "waiting-siblings")
        scheduler.tick()
        self.assertEqual(self.execute(second, self.build_answer(text="second\n")), 0)
        scheduler.reconcile()
        for identifier in (first, second):
            self.assertEqual(queue.snapshot()[identifier]["status"], "blocked")
            self.assertIn("sibling draft conflict", queue.snapshot()[identifier]["reason"])
        self.assertEqual(workspaces.git(self.repo, "rev-parse", "HEAD"), source_head)
        self.assertFalse(any(r["stage"] == "review" for r in queue.snapshot().values()))

    def test_disjoint_siblings_pass_conflict_gate_and_keep_separate_branches(self):
        self.enqueue("parent", parts=[{"goal": "First", "role": "build", "scope": ["src/a"],
                                        "test_commands": [[sys.executable, "-c", "pass"]]},
                                       {"goal": "Second", "role": "build", "scope": ["src/b"],
                                        "test_commands": [[sys.executable, "-c", "pass"]]}])
        scheduler.tick()
        first, second = queue.snapshot()["parent"]["children"]
        self.assertEqual(self.execute(first, self.build_answer()), 0)
        self.assertEqual(self.execute(second, self.build_answer("src/b")), 0)
        scheduler.reconcile()
        for identifier in (first, second):
            self.assertEqual(queue.snapshot()[identifier]["status"], "review")
            self.assertEqual(queue.snapshot()[identifier]["conflict_checks"][0]["returncode"], 0)
        self.assertNotEqual(self.record(first)["head_sha"], self.record(second)["head_sha"])

    def test_runner_calls_scheduler_and_status_board_reports_lane_evidence(self):
        self.enqueue()
        with patch.object(runtime, "schedule_pass"), patch.object(runtime, "run", wraps=runtime.run) as run:
            runtime.runner_cycle()
        self.assertFalse(any("run-tick.sh" in str(c.args) for c in run.call_args_list))
        status = (self.core / "STATUS.md").read_text()
        self.assertIn("## Lane board", status)
        self.assertIn("Heartbeat (UTC)", status)
        self.assertIn("| gemini | running | task |", status)
        self.assertIn("| mini |", status)

    def test_stop_and_maintenance_prevent_new_launches(self):
        self.enqueue()
        for name in ("MAINTENANCE", "STOP-WEBBOB"):
            path = self.core / name
            path.touch()
            scheduler.tick()
            path.unlink()
        self.launcher.assert_not_called()

    def test_legacy_webbob_index_is_imported_without_known_project(self):
        prompts = self.root / "next-prompts"
        prompts.mkdir()
        (prompts / "ask.md").write_text("Review the conductor result")
        (prompts / "INDEX.md").write_text("| 2 | `ask.md` | WebBob | non-coding | READY | requested |\n")
        scheduler.tick()
        self.assertEqual(queue.snapshot()["queue-ask"]["role"], "research")
        self.assertIsNotNone(self.record("queue-ask"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
