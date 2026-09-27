"""Dispatch failure regressions; isolated roots, real locks, no paid calls."""
import concurrent.futures
import fcntl
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dispatch_worker
import web_dispatch
import lanes
import runtime
import state
import command
import workspaces
from web_dispatch import task_queue as queue


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="webbob-dispatch-test-")
        self.root = Path(self.tmp.name)
        self.core = self.root / "conductor"
        self.core.mkdir()
        self.patches = []
        for module in (dispatch_worker, web_dispatch, lanes, runtime, state):
            for name, value in (("ROOT", self.root), ("CONDUCTOR", self.core)):
                if hasattr(module, name):
                    self.patches.append(patch.object(module, name, value))
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.tmp.cleanup()

    def enqueue(self, request="one", worker="auto", kind="analysis"):
        return queue.enqueue(self.root, "conversation", request, "Review this supplied task evidence.", worker=worker, kind=kind)

    def test_enqueue_idempotency_and_conflict(self):
        row = self.enqueue()
        self.assertEqual(row, self.enqueue())
        with self.assertRaises(ValueError):
            queue.enqueue(self.root, "conversation", "one", "Different request")
        self.assertEqual(len(queue.tasks(self.root)), 1)

    def test_only_allowed_workers_and_tool_routing(self):
        for worker in ("grok", "unknown", "Grok"):
            with self.assertRaises(ValueError):
                self.enqueue(worker=worker)
        with self.assertRaises(ValueError):
            self.enqueue(worker="gemini", kind="coding")
        self.enqueue(kind="coding")
        self.assertIsNone(queue.claim(self.root, "gemini"))
        self.assertIsNotNone(queue.claim(self.root, "cursor-agent"))

    def test_concurrent_claims_execute_once_and_reserve_lane(self):
        self.enqueue()
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
            claims = list(pool.map(lambda _: queue.claim(self.root, "codex"), range(16)))
        self.assertEqual(sum(r is not None for r in claims), 1)
        self.enqueue("two")
        self.assertIsNone(queue.claim(self.root, "codex"))
        self.assertIsNotNone(queue.claim(self.root, "minimax"))

    def test_expired_claim_requeues_and_old_worker_is_fenced(self):
        self.enqueue()
        first = queue.claim(self.root, "codex", now=100)
        self.assertEqual(queue.recover(self.root, lambda _: False, now=101), [])
        queue.recover(self.root, lambda _: False, now=191)
        second = queue.claim(self.root, "codex", now=192)
        self.assertNotEqual(first["claim_token"], second["claim_token"])
        self.assertIsNone(queue.transition(self.root, first["id"], first["claim_token"], "succeeded", now=193, result="Stale"))
        self.assertIsNotNone(queue.transition(self.root, second["id"], second["claim_token"], "succeeded", now=193, result="Actual answer"))

    def test_dead_running_worker_recovered_before_lease_deadline(self):
        self.enqueue()
        row = queue.claim(self.root, "codex", now=100)
        queue.transition(self.root, row["id"], row["claim_token"], "running", now=101)
        queue.recover(self.root, lambda _: False, now=102)
        self.assertEqual(queue.tasks(self.root)[row["id"]]["status"], "queued")

    def test_live_worker_is_not_duplicated_and_heartbeat_renews(self):
        self.enqueue()
        row = queue.claim(self.root, "gemini", now=100)
        queue.transition(self.root, row["id"], row["claim_token"], "running", now=101)
        renewed = queue.transition(self.root, row["id"], row["claim_token"], "heartbeat", now=180)
        self.assertEqual(renewed["lease_until"], 270)
        self.assertEqual(queue.recover(self.root, lambda _: True, now=300), [])
        self.assertIsNone(queue.claim(self.root, "gemini", now=301))
        self.assertIsNone(queue.transition(self.root, row["id"], row["claim_token"], "succeeded", now=301, result="late"))

    def test_failure_backoff_terminal_after_three_attempts(self):
        self.enqueue()
        for attempt in range(3):
            now = 100 + attempt * 100
            row = queue.claim(self.root, "gemini", now=now)
            result = queue.transition(self.root, row["id"], row["claim_token"], "retry", now=now+1, error="HTTP failure")
            self.assertIsNone(queue.claim(self.root, "gemini", now=now+2))
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["attempts"], 3)

    def test_interrupted_append_repair_and_middle_corruption(self):
        row = self.enqueue()
        path = self.core / "state/queue.jsonl"
        with path.open("ab") as handle:
            handle.write(b'{"id":')
        self.assertEqual(queue.tasks(self.root)[row["id"]], row)
        path.write_text("broken\n" + path.read_text())
        with self.assertRaises(ValueError):
            queue.tasks(self.root)

    def test_real_task_lock_detects_worker_death(self):
        row = self.enqueue()
        with state.lock("dispatch-" + row["id"]):
            self.assertTrue(web_dispatch.worker_alive(row))
        self.assertFalse(web_dispatch.worker_alive(row))

    def test_expired_worker_reaper_fences_pid_reuse_and_kills_only_owned_tree(self):
        row = dict(id="webchat-task", claim_token="claim-token", pid=101)
        processes = "101 10 10 python dispatch_worker.py webchat-task claim-token\n102 101 102 codex\n103 102 102 child\n999 1 999 bystander\n"
        with patch.object(web_dispatch, "run", return_value=SimpleNamespace(returncode=0, stdout=processes)), patch.object(web_dispatch.os, "kill") as kill, patch.object(web_dispatch.os, "killpg") as killpg:
            self.assertTrue(web_dispatch.reap_expired_worker(row))
            self.assertEqual({call.args[0] for call in kill.call_args_list}, {101, 102, 103})
            self.assertEqual(killpg.call_args.args[0], 102)
            kill.reset_mock()
            self.assertFalse(web_dispatch.reap_expired_worker(dict(row, claim_token="old-token")))
            kill.assert_not_called()

    def test_real_process_death_releases_lock_and_requeues_task(self):
        self.enqueue(worker="gemini")
        row = queue.claim(self.root, "gemini")
        ready = self.root / "ready"
        script = "import sys,time; from pathlib import Path; sys.path.insert(0,sys.argv[1]); sys.path.insert(0,str(Path(sys.argv[1]).parent/'state')); import state; import task_queue; root=Path(sys.argv[2]);\nwith state.lock('dispatch-'+sys.argv[3]):\n task_queue.transition(root,sys.argv[3],sys.argv[4],'running'); Path(sys.argv[5]).touch(); time.sleep(60)\n"
        process = subprocess.Popen([sys.executable, "-c", script, str(Path(__file__).resolve().parent), str(self.root), row["id"], row["claim_token"], str(ready)], env=dict(os.environ, BOB_ROOT=str(self.root)))
        try:
            deadline = time.monotonic() + 5
            while not ready.exists() and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertTrue(ready.exists())
            self.assertTrue(web_dispatch.worker_alive(row))
            process.kill()
            process.wait(timeout=5)
            queue.recover(self.root, web_dispatch.worker_alive)
            self.assertEqual(queue.tasks(self.root)[row["id"]]["status"], "queued")
            replacement = queue.claim(self.root, "gemini")
            self.assertNotEqual(replacement["claim_token"], row["claim_token"])
        finally:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)

    def test_idle_lanes_refilled_and_failed_launch_retried(self):
        self.enqueue("one", worker="gemini")
        self.enqueue("two", worker="minimax")
        health = {lane: {"state": "ready"} for lane in queue.WORKERS}
        with patch.object(lanes, "refresh", return_value=health), patch.object(web_dispatch, "launch") as launch:
            self.assertEqual(web_dispatch.tick(), 2)
            self.assertEqual({call.args[0]["worker"] for call in launch.call_args_list}, {"gemini", "minimax"})
        row = next(r for r in queue.tasks(self.root).values() if r["worker"] == "gemini")
        queue.transition(self.root, row["id"], row["claim_token"], "succeeded", result="Completed result")
        self.enqueue("three", worker="gemini")
        with patch.object(lanes, "refresh", return_value=health), patch.object(web_dispatch, "launch", side_effect=OSError):
            web_dispatch.tick()
        third = next(r for r in queue.tasks(self.root).values() if r["request_id"] == "three")
        self.assertEqual(third["status"], "queued")
        self.assertIn("launch failed", third["error"])

    def test_worker_executes_and_persists_answer_before_releasing_lane(self):
        self.enqueue(worker="gemini")
        row = queue.claim(self.root, "gemini")
        def answer(*args, **kwargs):
            active = queue.tasks(self.root)[row["id"]]
            self.assertEqual(active["status"], "running")
            self.assertTrue(web_dispatch.worker_alive(row))
            with self.assertRaises(BlockingIOError):
                with state.lock("lane-gemini", blocking=False):
                    pass
            return "The evidence shows a missing consumer; add a durable result outbox."
        with patch.object(dispatch_worker, "prepare_task", return_value=self.root), patch.object(dispatch_worker, "ask", side_effect=answer):
            self.assertEqual(dispatch_worker.execute(row["id"], row["claim_token"]), 0)
        result = queue.tasks(self.root)[row["id"]]
        self.assertEqual(result["status"], "succeeded")
        self.assertLessEqual(result["claimed_at"], result["started_at"])
        self.assertLessEqual(result["started_at"], result["finished_at"])
        self.assertTrue((self.core / "state/task-runs" / row["id"] / "RESULT.md").exists())

    def test_busy_lane_does_not_spend_attempt_or_run_model(self):
        self.enqueue(worker="gemini")
        row = queue.claim(self.root, "gemini")
        with state.lock("lane-gemini"), patch.object(dispatch_worker, "ask") as ask:
            dispatch_worker.execute(row["id"], row["claim_token"])
            ask.assert_not_called()
        self.assertEqual(queue.tasks(self.root)[row["id"]]["attempts"], 0)

    def test_duplicate_worker_process_cannot_requeue_the_actual_owner(self):
        self.enqueue(worker="gemini")
        row = queue.claim(self.root, "gemini")
        with state.lock("dispatch-" + row["id"]), patch.object(dispatch_worker, "ask") as ask:
            dispatch_worker.execute(row["id"], row["claim_token"])
            ask.assert_not_called()
        current = queue.tasks(self.root)[row["id"]]
        self.assertEqual(current["status"], "claimed")
        self.assertEqual(current["claim_token"], row["claim_token"])

    def test_private_coding_checkout_can_commit_without_writing_source_refs(self):
        def git(path, *args):
            return subprocess.check_output(["git", "-C", str(path), *args], text=True, stderr=subprocess.DEVNULL).strip()
        git(self.core, "init", "-b", "draft/source")
        git(self.core, "-c", "user.name=Test", "-c", "user.email=test@localhost", "commit", "--allow-empty", "-m", "Source")
        head = git(self.core, "rev-parse", "HEAD")
        record = dict(repo=str(self.core), worktree=str(self.root / "workspaces/task"), branch="draft/task", job_dir=str(self.root / "job"))
        folder = dispatch_worker.prepare_task(record, True)
        (folder / "answer.txt").write_text("Private change\n")
        git(folder, "add", "answer.txt")
        git(folder, "-c", "user.name=Test", "-c", "user.email=test@localhost", "commit", "-m", "Task result")
        self.assertNotEqual(git(folder, "rev-parse", "HEAD"), head)
        self.assertEqual(git(self.core, "rev-parse", "HEAD"), head)
        self.assertEqual(git(folder, "remote"), "")
        self.assertEqual(git(self.core, "branch", "--list", "draft/task"), "")

    def test_blocker_never_counts_as_success_and_secret_redacted(self):
        self.enqueue(worker="gemini")
        row = queue.claim(self.root, "gemini")
        with patch.object(dispatch_worker, "prepare_task", return_value=self.root), patch.dict(os.environ, {"GEMINI_API_KEY": "private-test-credential"}), patch.object(dispatch_worker, "ask", return_value="BLOCKER: private-test-credential"):
            self.assertEqual(dispatch_worker.execute(row["id"], row["claim_token"]), 1)
        result = queue.tasks(self.root)[row["id"]]
        self.assertEqual(result["status"], "queued")
        self.assertNotIn("private-test-credential", (self.core / "state/queue.jsonl").read_text())

    def test_coding_without_commit_is_not_success(self):
        self.enqueue(worker="codex", kind="coding")
        row = queue.claim(self.root, "codex")
        with patch.object(dispatch_worker, "prepare_task", return_value=self.root), patch.object(dispatch_worker, "ask", return_value="I made changes"), patch.object(dispatch_worker, "git", side_effect=["draft/" + row["id"], " M file.py"]):
            dispatch_worker.execute(row["id"], row["claim_token"])
        self.assertEqual(queue.tasks(self.root)[row["id"]]["status"], "queued")

    def test_runner_dispatches_on_every_cycle_despite_legacy_cadence(self):
        state.write_json(self.core / "dispatch-schedule.json", {"next_legacy_tick": time.time() + 60})
        with patch.object(web_dispatch, "tick") as tick, patch.object(runtime, "run") as run:
            runtime.runner_cycle()
            runtime.runner_cycle()
            self.assertEqual(tick.call_count, 2)
            run.assert_not_called()

    def test_bootstrap_transient_validation_cannot_restore_old_scheduler(self):
        spec = importlib.util.spec_from_file_location("dispatch_bootstrap", Path(__file__).resolve().parents[1] / "bootstrap.py")
        bootstrap = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bootstrap)
        with patch.object(bootstrap, "HERE", self.core), patch.object(bootstrap, "validate", side_effect=[["services/dispatch-worker.sh"], []]), patch.object(bootstrap, "files", return_value=[]), patch.object(bootstrap, "bounded") as commands:
            bootstrap.gate()
            commands.assert_not_called()

    def test_bootstrap_refuses_to_discard_local_changes_on_persistent_failure(self):
        spec = importlib.util.spec_from_file_location("dispatch_bootstrap", Path(__file__).resolve().parents[1] / "bootstrap.py")
        bootstrap = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bootstrap)
        with patch.object(bootstrap, "HERE", self.core), patch.object(bootstrap, "validate", return_value=["services/dispatch-worker.sh"]), patch.object(bootstrap, "bounded", return_value=(1, b"", b"")) as commands:
            with self.assertRaisesRegex(RuntimeError, "without rollback"):
                bootstrap.gate()
            self.assertEqual(commands.call_count, 1)
            self.assertIn("diff", commands.call_args.args[0])

    @unittest.skipUnless(sys.platform == "darwin", "macOS sandbox boundary")
    def test_analysis_sandbox_reads_files_but_denies_writes_without_nested_sandbox(self):
        workspace = self.root / "workspace"
        workspace.mkdir()
        subprocess.run(["git", "init", "-q", str(workspace)], check=True)
        evidence = workspace / "evidence.txt"
        evidence.write_text("actual source evidence")
        argv = workspaces.sandbox_command([sys.executable, "-c", "from pathlib import Path; print(Path('evidence.txt').read_text())"], workspace, read_only=True)
        result = command.run(argv, cwd=workspace, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("actual source evidence", result.stdout)
        argv = workspaces.sandbox_command([sys.executable, "-c", "from pathlib import Path; Path('evidence.txt').write_text('overwrite')"], workspace, read_only=True)
        result = command.run(argv, cwd=workspace, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(evidence.read_text(), "actual source evidence")

    def test_codex_uses_one_outer_boundary_for_analysis(self):
        response = '{"item":{"type":"agent_message","text":"Reviewed the actual file."}}'
        with patch.object(lanes, "run", return_value=SimpleNamespace(returncode=0, stdout=response, stderr="")) as run, patch.object(lanes, "sandbox_command", side_effect=lambda argv, cwd, **kw: argv) as boundary, patch.object(lanes.budget, "record_cli"):
            lanes.cli("codex", "Review evidence", self.root, False, 30)
        self.assertTrue(boundary.call_args.kwargs["read_only"])
        self.assertNotIn("-s", run.call_args.args[0])
        self.assertIn("--dangerously-bypass-approvals-and-sandbox", run.call_args.args[0])

    def test_pinned_webchat_launcher_keeps_existing_data_and_loads_keys(self):
        folder = self.core / "webchat"
        folder.mkdir()
        (self.core / "state").mkdir()
        deployment = self.root / "tested-code"
        (self.core / "state/dispatch-code-root").write_text(str(deployment) + "\n")
        (self.core / "keys.env").write_text("GEMINI_API_KEY=private-test-value\n")
        source = (Path(__file__).resolve().parents[1] / "webchat/run.sh").read_text()
        probe = self.root / "probe.py"
        probe.write_text("import os,sys,pathlib\nroot=pathlib.Path(os.environ['BOB_ROOT'])\nassert pathlib.Path(os.environ['BOB_WEBCHAT_DIR']) == root/'conductor/webchat'\nassert sys.argv[1] == str(root/'tested-code/webchat/app.py')\nassert os.environ['GEMINI_API_KEY']=='private-test-value'\n(root/'pinned-ok').touch()\n")
        source = source.replace('python3 -u', sys.executable + ' "' + str(probe) + '"')
        runner = folder / "run.sh"
        runner.write_text(source)
        result = subprocess.run(["bash", str(runner)], env=dict(os.environ, BOB_ROOT=str(self.root)), capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.root / "pinned-ok").exists())
        self.assertNotIn("private-test-value", result.stdout + result.stderr)

    def test_worker_launcher_sources_rotated_keys_without_printing_them(self):
        # Use a fake python on the normal inherited PATH; the script's fixed
        # prefixes may contain python3, so replace only the executable in a copy.
        script = Path(__file__).with_name("dispatch-worker.sh").read_text()
        probe = self.root / "probe.py"
        probe.write_text("import os,pathlib\nassert os.environ['GEMINI_API_KEY']=='private-test-value'\npathlib.Path(os.environ['BOB_ROOT'],'credential-loaded').touch()\n")
        script = script.replace('python3 "$BOB_CODE_ROOT/services/dispatch_worker.py"', sys.executable + ' "' + str(probe) + '"')
        runner = self.root / "runner.sh"
        runner.write_text(script)
        (self.core / "keys.env").write_text("GEMINI_API_KEY='private-test-value'\n")
        result = subprocess.run(["bash", str(runner), "task", "claim"], env=dict(os.environ, BOB_ROOT=str(self.root), GEMINI_API_KEY="stale"), capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertTrue((self.root / "credential-loaded").exists())
        self.assertNotIn("private-test-value", result.stdout + result.stderr)
