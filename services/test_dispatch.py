"""Dispatch failure regressions; isolated roots, real locks, no paid calls."""
import concurrent.futures
import fcntl
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dispatch_worker
import web_dispatch
import lanes
import budget
import mini_worker
import runtime
import state
import command
import workspaces
import result_acceptance
from web_dispatch import task_queue as queue


class DispatchTests(unittest.TestCase):
    def test_pending_activation_fences_both_chat_and_legacy_runner_admission(self):
        self.enqueue()
        marker = self.core / 'locks/webbob-activation.json'
        marker.parent.mkdir(exist_ok=True)
        marker.write_text('{pending')
        with patch.object(web_dispatch, 'launch') as launch, patch.object(lanes, 'refresh') as refresh, \
                patch.object(runtime, 'schedule_pass') as legacy:
            self.assertEqual(web_dispatch.tick(), 0)
            runtime.runner_cycle()
            launch.assert_not_called()
            refresh.assert_not_called()
            legacy.assert_not_called()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="webbob-dispatch-test-")
        self.root = Path(self.tmp.name)
        self.core = self.root / "conductor"
        self.core.mkdir()
        self.patches = []
        for module in (dispatch_worker, web_dispatch, lanes, runtime, state, budget):
            for name, value in (("ROOT", self.root), ("CONDUCTOR", self.core)):
                if hasattr(module, name):
                    self.patches.append(patch.object(module, name, value))
        for item in self.patches:
            item.start()
        # Most tests exercise queue/lease behavior. Acceptance has its own
        # task/answer cases below, without paid model calls in the unit suite.
        self.acceptance = patch.object(result_acceptance, "accept", return_value={"accepted": True, "method": "test-review"})
        self.acceptance.start()
        self.addCleanup(self.acceptance.stop)
        self.validation = patch.object(mini_worker, "verify_coding", return_value=None)
        self.validation.start()
        self.addCleanup(self.validation.stop)

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

    def test_attempt_limit_is_durable_at_admission_and_part_of_request_identity(self):
        args = (self.root, 'conversation', 'bounded', 'Run webchat/test_answer_intent.py')
        row = queue.enqueue(*args, worker='mini', attempt_limit=1)
        first = json.loads((self.core / 'state/queue.jsonl').read_text().splitlines()[0])
        self.assertEqual((first['attempt_limit'], first['max_attempts'], first['attempts']), (1, 1, 0))
        self.assertEqual(queue.enqueue(*args, worker='mini', attempt_limit=1), row)
        before = (self.core / 'state/queue.jsonl').read_bytes()
        for limit in (None, 2):
            with self.assertRaisesRegex(ValueError, 'different attempt limit'):
                queue.enqueue(*args, worker='mini', attempt_limit=limit)
        self.assertEqual((self.core / 'state/queue.jsonl').read_bytes(), before)

    def test_attempt_limit_rejects_invalid_values_without_admitting_work(self):
        for limit in (True, False, 0, -1, 1.0, '1', [], {}):
            with self.subTest(limit=limit), self.assertRaisesRegex(ValueError, 'positive integer'):
                queue.enqueue(self.root, 'conversation', 'invalid', 'Run tests', worker='mini', attempt_limit=limit)
        self.assertFalse(queue.tasks(self.root))

    def test_unlimited_argument_preserves_existing_and_legacy_retry_policy(self):
        local = self.enqueue('local', worker='mini')
        ordinary = self.enqueue('ordinary')
        self.assertEqual(local['max_attempts'], 3)
        self.assertEqual(ordinary['max_attempts'], 5)
        with queue.locked(self.root) as path:
            local.pop('attempt_limit')
            local.pop('max_attempts')
            local = queue._append(path, local, 'legacy_fixture')
        self.assertEqual(self.enqueue('local', worker='mini'), local)
        claim = queue.claim(self.root, 'mini', identifier=local['id'])
        retried = queue.transition(self.root, local['id'], claim['claim_token'], 'retry', error='fixture failure')
        self.assertEqual(retried['status'], 'queued')

    def test_single_attempt_failure_and_timeout_are_terminal_in_real_dispatcher(self):
        for index, error in enumerate((RuntimeError('Mini tests failed'), subprocess.TimeoutExpired(['unittest'], 300))):
            row = queue.enqueue(self.root, 'conversation', 'failed-' + str(index),
                                'Run webchat/test_answer_intent.py', worker='mini', attempt_limit=1)
            claim = queue.claim(self.root, 'mini', identifier=row['id'])
            with patch.object(mini_worker, 'execute', side_effect=error) as execute, \
                    patch.object(dispatch_worker, 'ask') as ask:
                dispatch_worker.execute(row['id'], claim['claim_token'])
                execute.assert_called_once()
                ask.assert_not_called()
            result = queue.tasks(self.root)[row['id']]
            self.assertEqual((result['status'], result['attempts'], result['max_attempts']), ('failed', 1, 1))
            self.assertIsNone(queue.claim(self.root, 'mini', identifier=row['id'], now=time.time() + 1000))
            self.assertEqual(queue.recover(self.root, lambda _: False, now=time.time() + 1000), [])

    def test_single_attempt_lost_worker_cannot_restart_after_recovery(self):
        for running in (False, True):
            row = queue.enqueue(self.root, 'conversation', 'lost-' + str(running), 'Run tests', worker='mini', attempt_limit=1)
            claim = queue.claim(self.root, 'mini', identifier=row['id'], now=100)
            if running:
                queue.transition(self.root, row['id'], claim['claim_token'], 'running', now=101)
            recovered = queue.recover(self.root, lambda _: False, now=300)
            self.assertEqual([(r['status'], r['attempts']) for r in recovered], [('failed', 1)])
            self.assertIsNone(queue.claim(self.root, 'mini', identifier=row['id'], now=301))
            self.assertIsNone(queue.transition(self.root, row['id'], claim['claim_token'], 'succeeded', now=301, result='Stale'))

    def test_single_attempt_busy_lane_does_not_consume_execution(self):
        row = queue.enqueue(self.root, 'conversation', 'busy', 'Run tests', worker='mini', attempt_limit=1)
        claim = queue.claim(self.root, 'mini', identifier=row['id'], now=100)
        busy = queue.transition(self.root, row['id'], claim['claim_token'], 'busy', now=101)
        self.assertEqual((busy['status'], busy['attempts'], busy['max_attempts']), ('queued', 0, 1))
        claim = queue.claim(self.root, 'mini', identifier=row['id'], now=107)
        self.assertEqual(claim['attempts'], 1)
        failed = queue.transition(self.root, row['id'], claim['claim_token'], 'retry', now=108)
        self.assertEqual(failed['status'], 'failed')

    def permission(self, cid='conversation', holds=None):
        path = self.core / 'webchat/sessions' / (cid + '.json')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(dict(id=cid, intent_state=dict(holds=holds or {}))))
        return path

    def test_activation_admission_preserves_existing_request_but_refuses_new_bound_rows(self):
        permission = self.permission()
        old = queue.enqueue(self.root, 'conversation', 'one', 'Explain queues', permission_file=permission)
        marker = self.core / 'locks/webbob-activation.json'
        marker.parent.mkdir(exist_ok=True)
        marker.write_text('{}')
        self.assertEqual(queue.enqueue(self.root, 'conversation', 'one', 'Explain queues',
                                       permission_file=permission)['id'], old['id'])
        with self.assertRaises(queue.AdmissionPaused):
            queue.enqueue(self.root, 'conversation', 'two', 'Explain queues', permission_file=permission)
        self.assertEqual(list(queue.tasks(self.root)), [old['id']])

    def test_rollback_refuses_active_rows_before_changing_any_pending_task(self):
        permission = self.permission()
        queued = queue.enqueue(self.root, 'conversation', 'pending', 'Explain queues', permission_file=permission)
        active = self.enqueue('active')
        queue.claim(self.root, 'codex', identifier=active['id'])
        path = self.core / 'state/queue.jsonl'
        before = path.read_bytes()
        with self.assertRaisesRegex(RuntimeError, 'drained'):
            queue.cancel_for_rollback(self.root, queued['created_at'])
        self.assertEqual(path.read_bytes(), before)

    def test_rollback_cancels_new_and_held_pending_rows_but_preserves_unrelated_old_work(self):
        permission = self.permission()
        old = queue.enqueue(self.root, 'conversation', 'old', 'Explain queues', permission_file=permission)
        start = time.time()
        new = queue.enqueue(self.root, 'conversation', 'new', 'Explain queues', permission_file=permission)
        held_permission = self.permission('held', {'Web Bob': {}})
        held = queue.enqueue(self.root, 'held', 'old-held', 'Review Web Bob', permission_file=held_permission,
                             project_scopes=['Web Bob'])
        with queue.locked(self.root) as path:
            held['created_at'] = start - 1
            queue._append(path, held, 'fixture_old')
        legacy = queue.enqueue(self.root, 'standalone', 'legacy', 'Explain queues')
        changed = queue.cancel_for_rollback(self.root, start)
        self.assertEqual({r['id'] for r in changed}, {new['id'], held['id']})
        rows = queue.tasks(self.root)
        for row in (old, legacy):
            self.assertEqual(rows[row['id']]['status'], 'queued')
        for row in changed:
            self.assertEqual(row['status'], 'failed')
            self.assertIn('original request is preserved', row['error'])
        self.assertEqual(queue.cancel_for_rollback(self.root, start), [])

    def test_partial_admission_cleanup_is_scoped_and_refuses_active_group_atomically(self):
        first = self.enqueue('group:0')
        second = self.enqueue('group:1')
        unrelated = self.enqueue('group-other')
        queue.claim(self.root, 'codex', identifier=second['id'])
        path = self.core / 'state/queue.jsonl'
        before = path.read_bytes()
        with self.assertRaisesRegex(RuntimeError, 'active admission'):
            queue.abort_admission(self.root, 'conversation', 'group')
        self.assertEqual(path.read_bytes(), before)
        queue.cancel_user_task(self.root, 'conversation', second['id'])
        queue.abort_admission(self.root, 'conversation', 'group')
        rows = queue.tasks(self.root)
        self.assertEqual(rows[first['id']]['status'], 'failed')
        self.assertEqual(rows[unrelated['id']]['status'], 'queued')
        self.assertTrue(rows[second['id']]['cancelled_at'])

    def test_project_workers_persist_separate_repositories_and_draft_branches_before_execution(self):
        catalog = {}
        names = ("WebJam", "AdoptIQ", "StoryBoard", "Fantasy Football")
        def git(repo, *args):
            return subprocess.check_output(["git", "-C", str(repo), *args], text=True, stderr=subprocess.DEVNULL).strip()
        for name in names:
            repo = self.root / name
            repo.mkdir()
            git(repo, "init", "-b", "main")
            (repo / "project.txt").write_text(name)
            git(repo, "add", "project.txt")
            git(repo, "-c", "user.name=Test", "-c", "user.email=test@localhost", "commit", "-m", "Initial")
            catalog[name] = dict(repo=str(repo), remote="owner/project")
        (self.core / "services").mkdir()
        (self.core / "services/projects.json").write_text(json.dumps(catalog))
        seen = []
        def work(worker, prompt, **kwargs):
            current = next(row for row in queue.tasks(self.root).values() if row["status"] == "running")
            self.assertTrue(current["execution_started_at"])
            self.assertEqual(current["worktree"], str(kwargs["cwd"]))
            self.assertEqual(current["branch"], "draft/" + current["id"])
            self.assertEqual(Path(current["repo"]), Path(catalog[current["project"]]["repo"]).resolve())
            self.assertEqual((kwargs["cwd"] / "project.txt").read_text(), current["project"])
            seen.append(current["worktree"])
            return "Inspected the isolated fixture and verified the requested project."
        with patch.object(dispatch_worker, "ask", side_effect=work), \
                patch("jobs.external_webjam_lease", return_value=False):
            for i, name in enumerate(names):
                row = queue.enqueue(self.root, "conversation", name, "Improve " + name, kind="coding")
                claim = queue.claim(self.root, ("codex", "cursor")[i % 2], identifier=row["id"])
                self.assertEqual(dispatch_worker.execute(row["id"], claim["claim_token"]), 0,
                                 queue.tasks(self.root)[row["id"]].get("error"))
                self.assertEqual(queue.tasks(self.root)[row["id"]]["status"], "succeeded")
        self.assertEqual(len(set(seen)), 4)

    def test_queue_replay_cannot_add_publication_authority(self):
        queue.enqueue(self.root, "conversation", "one", "Improve WebJam", kind="coding")
        with self.assertRaises(ValueError):
            queue.enqueue(self.root, "conversation", "one", "Improve WebJam", kind="coding", publish_project="WebJam")
        self.assertIsNone(next(iter(queue.tasks(self.root).values()))["publish_project"])

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

    def test_failure_backoff_terminal_after_all_provider_attempts(self):
        self.enqueue()
        for attempt in range(5):
            now = 100 + attempt * 100
            row = queue.claim(self.root, "gemini", now=now)
            result = queue.transition(self.root, row["id"], row["claim_token"], "retry", now=now+1, error="HTTP failure")
            self.assertIsNone(queue.claim(self.root, "gemini", now=now+2))
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["attempts"], 5)

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
            return "**BLOCKER: none — completed.**\nThe evidence shows a missing consumer; add a durable result outbox."
        with patch.object(dispatch_worker, "prepare_task", return_value=self.root), patch.object(dispatch_worker, "ask", side_effect=answer):
            self.assertEqual(dispatch_worker.execute(row["id"], row["claim_token"]), 0)
        result = queue.tasks(self.root)[row["id"]]
        self.assertEqual(result["status"], "succeeded")
        self.assertLessEqual(result["claimed_at"], result["started_at"])
        self.assertLessEqual(result["started_at"], result["finished_at"])
        self.assertTrue((self.core / "state/task-runs" / row["id"] / "RESULT.md").exists())

    def test_blocker_none_is_not_a_provider_failure(self):
        for text in ("BLOCKER: none", "**BLOCKER:** no blockers", "## BLOCKER: not blocked"):
            self.assertFalse(dispatch_worker.blocked_answer(text))
        for text in ("## BLOCKER: Ask mode", "Progress\n**BLOCKER:** permission denied",
                     "BLOCKER: none\n## BLOCKER: cannot read the requested file"):
            self.assertTrue(dispatch_worker.blocked_answer(text))

    def test_small_file_worker_must_actually_write_before_success(self):
        target = Path('/tmp') / ('webbob-unit-' + __import__('uuid').uuid4().hex + '.txt')
        self.addCleanup(lambda: target.unlink(missing_ok=True))
        row = queue.enqueue(self.root, 'conversation', 'artifact', 'write hello to ' + str(target), worker='claude', kind='artifact')
        claim = queue.claim(self.root, 'claude')
        def answer(*args, **kwargs):
            self.assertTrue(kwargs['coding'])
            self.assertEqual(kwargs['purpose'], 'small-file')
            target.write_text('hello\n')
            return 'Wrote the file.'
        with patch.object(dispatch_worker, 'prepare_task', return_value=self.root), \
                patch.object(dispatch_worker, 'ask', side_effect=answer), \
                patch.object(dispatch_worker, 'git', side_effect=['draft/' + row['id'], '']):
            self.assertEqual(dispatch_worker.execute(claim['id'], claim['claim_token']), 0)
        result = queue.tasks(self.root)[row['id']]
        self.assertEqual(result['status'], 'succeeded')
        self.assertIn('Server verified file:', result['result'])
        row = queue.enqueue(self.root, 'conversation', 'false-artifact', 'write hello to ' + str(target), worker='claude', kind='artifact')
        claim = queue.claim(self.root, 'claude')
        with patch.object(dispatch_worker, 'prepare_task', return_value=self.root), patch.object(dispatch_worker, 'ask', return_value='Wrote the file.'):
            self.assertEqual(dispatch_worker.execute(claim['id'], claim['claim_token']), 1)
        self.assertEqual(queue.tasks(self.root)[row['id']]['status'], 'failed')

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
        self.assertEqual(result["status"], "failed")
        self.assertNotIn("private-test-credential", (self.core / "state/queue.jsonl").read_text())

    def test_coding_without_commit_is_not_success(self):
        self.enqueue(worker="codex", kind="coding")
        row = queue.claim(self.root, "codex")
        with patch.object(dispatch_worker, "prepare_task", return_value=self.root), patch.object(dispatch_worker, "ask", return_value="I made changes"), patch.object(dispatch_worker, "git", side_effect=["base-sha", "draft/" + row["id"], " M file.py"]):
            dispatch_worker.execute(row["id"], row["claim_token"])
        self.assertEqual(queue.tasks(self.root)[row["id"]]["status"], "failed")

    def test_required_coding_checks_precede_acceptance_publication_and_success(self):
        self.validation.stop()
        row = queue.enqueue(self.root, "conversation", "incomplete-api", "Improve StoryBoard", kind="coding",
                            worker="cursor", publish_project="StoryBoard")
        claim = queue.claim(self.root, "cursor")
        branch = "draft/" + row["id"]
        def git(cwd, *args):
            if args[0] == "rev-parse": return "a" * 40
            if args[0] == "branch": return branch
            return ""
        with patch.object(dispatch_worker, "prepare_task", return_value=self.root), \
                patch.object(dispatch_worker, "git", side_effect=git), \
                patch.object(dispatch_worker, "ask", return_value="Fixed API install. Tests: shared 106 pass. Status: Pass.") as ask, \
                patch.object(mini_worker, "verify_coding", side_effect=result_acceptance.ResultRejected("Required coding check failed: pnpm test")) as verify, \
                patch.object(dispatch_worker.draft_publish, "publish") as publish, \
                patch.object(result_acceptance, "accept") as accept:
            self.assertEqual(dispatch_worker.execute(row["id"], claim["claim_token"]), 1)
        verify.assert_called_once()
        publish.assert_not_called()
        accept.assert_not_called()
        self.assertEqual(ask.call_count, 1)
        self.assertIn("After the final code edit", ask.call_args.args[1])
        self.assertIn('["pnpm", "test"]', ask.call_args.args[1])
        result = queue.tasks(self.root)[row["id"]]
        self.assertEqual(result["status"], "failed")
        self.assertNotIn("result", result)
        self.assertFalse((self.core / "state/task-runs" / row["id"] / "RESULT.md").exists())

    def test_api_only_prompt_has_no_workspace_framing_in_either_call(self):
        import api
        self.acceptance.stop()
        for worker in queue.API_WORKERS:
            with self.subTest(worker=worker):
                prompt = "Write one sentence confirming you ran. Include the exact phrase 'proof " + worker + "'."
                answer = "I ran and confirm proof " + worker + "."
                task = queue.enqueue(self.root, "conversation", worker, prompt, worker=worker)
                row = queue.claim(self.root, worker)
                with patch.object(dispatch_worker, "prepare_task") as prepare, \
                        patch.object(dispatch_worker, "task_repository") as repository, \
                        patch.object(api, "model_call", side_effect=[answer, '{"accepted": true, "reason": "Confirms execution with the requested phrase."}']) as call:
                    self.assertEqual(dispatch_worker.execute(row["id"], row["claim_token"]), 0)
                prepare.assert_not_called()
                repository.assert_not_called()
                self.assertEqual(call.call_count, 2)
                for invocation in call.call_args_list:
                    instructions = invocation.args[1]
                    self.assertNotIn("worktree", instructions.lower())
                    self.assertNotIn("filesystem", instructions.lower())
                    self.assertNotIn(str(self.root), instructions)
                    self.assertNotIn("draft/", instructions)
                result = queue.tasks(self.root)[task["id"]]
                self.assertEqual(result["status"], "succeeded")
                self.assertIsNone(result["worktree"])
                self.assertIsNone(result["branch"])
                self.assertEqual(result["acceptance"]["result_sha256"], result["result_sha256"])

    def test_refusal_with_verification_phrase_is_terminal_without_review(self):
        prompt = "Write one sentence confirming you ran. Include the exact phrase 'WEBBOB-VERIFY5-0927-d8f5a3e9 minimax'."
        row = queue.enqueue(self.root, "conversation", "refusal", prompt, worker="minimax")
        claim = queue.claim(self.root, "minimax")
        answer = ("I cannot access or work with the Git worktree at `/private/workspaces/job` "
                  "or perform the described actions, as I don't have access to external file systems.\n\n"
                  "However, I can help you with answering questions.\n\n"
                  "**Verification phrase (as requested):** `WEBBOB-VERIFY5-0927-d8f5a3e9 minimax`")
        with patch.object(dispatch_worker, "ask", return_value=answer) as call:
            self.assertEqual(dispatch_worker.execute(row["id"], claim["claim_token"]), 1)
        self.assertEqual(call.call_count, 1)
        result = queue.tasks(self.root)[row["id"]]
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["attempts"], 1)
        self.assertEqual(result["rejected_result"], answer)
        self.assertFalse(result["acceptance"]["accepted"])
        self.assertFalse((self.core / "state/task-runs" / row["id"] / "RESULT.md").exists())
        self.assertIsNone(queue.claim(self.root, "minimax", now=time.time() + 1000))
        self.assertIsNone(queue.transition(self.root, row["id"], claim["claim_token"], "succeeded", result=answer))

    def test_off_topic_answer_or_unverifiable_review_cannot_succeed(self):
        self.acceptance.stop()
        for index, review in enumerate((
                '{"accepted": false, "reason": "Answer describes gardening instead of reviewing queue evidence."}',
                "Not JSON", '{"accepted": "true", "reason": "wrong type"}', RuntimeError("review unavailable"))):
            with self.subTest(review=review):
                self.enqueue("rejected-" + str(index), worker="minimax")
                row = queue.claim(self.root, "minimax")
                answer = "Tomatoes grow best with enough sunlight and regular watering."
                with patch.object(dispatch_worker, "ask", side_effect=[answer, review]) as ask:
                    self.assertEqual(dispatch_worker.execute(row["id"], row["claim_token"]), 1)
                self.assertEqual(ask.call_count, 3 if review == "Not JSON" else 2)
                self.assertEqual(ask.call_args.kwargs["purpose"], "result-acceptance")
                result = queue.tasks(self.root)[row["id"]]
                self.assertEqual(result["status"], "failed")
                self.assertNotIn("result", result)
                self.assertEqual(result["rejected_result"], answer)
                self.assertFalse((self.core / "state/task-runs" / row["id"] / "RESULT.md").exists())

    def test_file_inspection_routes_to_tools_and_named_api_produces_report(self):
        prompt = "Read services/dispatch_worker.py and summarize the failure path."
        row = queue.enqueue(self.root, "conversation", "inspection", prompt)
        self.assertEqual(row["kind"], "inspection")
        for worker in ("gemini", "minimax", "claude"):
            self.assertIsNone(queue.claim(self.root, worker))
        self.assertIsNotNone(queue.claim(self.root, "codex"))
        for worker in queue.API_WORKERS:
            report = queue.enqueue(self.root, "conversation", worker, prompt, worker=worker)
            self.assertEqual(report["kind"], "review")
            self.assertIsNotNone(queue.claim(self.root, worker))

    def test_old_misclassified_file_task_fails_before_an_api_call(self):
        task = self.enqueue(worker="minimax")
        claim = queue.claim(self.root, "minimax")
        queue.transition(self.root, task["id"], claim["claim_token"], "running",
                         prompt="Read /tmp/evidence.txt and summarize it.")
        with patch.object(dispatch_worker, "ask") as ask, patch.object(dispatch_worker, "prepare_task") as prepare:
            self.assertEqual(dispatch_worker.execute(task["id"], claim["claim_token"]), 1)
        ask.assert_not_called()
        prepare.assert_not_called()
        result = queue.tasks(self.root)[task["id"]]
        self.assertEqual(result["status"], "failed")
        self.assertIn("API-only", result["error"])

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

    def test_claim_allows_concurrent_gemini_tasks_but_serializes_codex(self):
        for worker in ("gemini", "minimax", "codex", "cursor", "claude", "mini"):
            for index in range(4):
                self.enqueue(worker + str(index), worker=worker)
            claims = [queue.claim(self.root, worker) for _ in range(4)]
            self.assertEqual(sum(row is not None for row in claims), queue.capacity(worker))

    def test_auto_analysis_task_prefers_claude_when_multiple_lanes_ready(self):
        self.enqueue()
        with patch.object(lanes, "refresh", return_value={lane: {"state": "ready"} for lane in queue.WORKERS}), patch.object(web_dispatch, "launch") as launch:
            self.assertEqual(web_dispatch.tick(), 1)
            self.assertEqual(launch.call_args.args[0]["worker"], "claude")

    def test_every_provider_failure_routes_to_an_untried_compatible_worker(self):
        health = {lane: {"state": "ready"} for lane in queue.WORKERS}
        for worker in queue.MODEL_WORKERS:
            with self.subTest(worker=worker):
                row = self.enqueue(worker, worker=worker)
                claim = queue.claim(self.root, worker, now=100)
                queue.transition(self.root, row["id"], claim["claim_token"], "retry", now=101, error="Provider failed")
                with patch.object(lanes, "refresh", return_value=health), patch.object(web_dispatch, "launch"):
                    web_dispatch.tick()
                result = queue.tasks(self.root)[row["id"]]
                self.assertNotEqual(result["worker"], worker)
                self.assertIn(worker, result["tried_workers"])
                queue.transition(self.root, result["id"], result["claim_token"], "succeeded", result="Recovered")

    def test_budget_warning_runs_and_exhausted_lane_shifts_to_headroom(self):
        self.enqueue(worker="gemini")
        health = {"gemini": {"state": "budget_warning"}, "minimax": {"state": "ready"}}
        with patch.object(lanes, "refresh", return_value=health), patch.object(web_dispatch, "launch") as launch:
            self.assertEqual(web_dispatch.tick(), 1)
            self.assertEqual(launch.call_args.args[0]["worker"], "gemini")
        row = next(iter(queue.tasks(self.root).values()))
        queue.transition(self.root, row["id"], row["claim_token"], "succeeded", result="done")
        self.enqueue("next", worker="gemini")
        health["gemini"]["state"] = "budget_exhausted"
        with patch.object(lanes, "refresh", return_value=health), patch.object(web_dispatch, "launch") as launch:
            self.assertEqual(web_dispatch.tick(), 1)
            self.assertEqual(launch.call_args.args[0]["worker"], "minimax")

    def test_retry_waits_for_untried_busy_worker_without_spending_attempt(self):
        row = self.enqueue(worker="gemini")
        claim = queue.claim(self.root, "gemini", now=100)
        queue.transition(self.root, row["id"], claim["claim_token"], "retry", now=101, error="Provider failed")
        health = {"gemini": {"state": "ready"}, "minimax": {"state": "busy"}}
        with patch.object(lanes, "refresh", return_value=health), patch.object(web_dispatch, "launch") as launch:
            self.assertEqual(web_dispatch.tick(), 0)
            self.assertEqual(queue.tasks(self.root)[row["id"]]["attempts"], 1)
            health["minimax"]["state"] = "ready"
            self.assertEqual(web_dispatch.tick(), 1)
            self.assertEqual(launch.call_args.args[0]["worker"], "minimax")

    def test_group_membership_and_replayed_metadata_are_immutable(self):
        def enqueue(request, index, size=2):
            return queue.enqueue(self.root, "conversation", request, "Independent evidence", worker="gemini",
                                 group_id="group", group_size=size, group_index=index)
        first = enqueue("first", 0)
        with self.assertRaises(ValueError):
            enqueue("first", 0, 3)
        with self.assertRaises(ValueError):
            enqueue("second", 0)
        self.assertIsNone(queue.claim(self.root, "gemini"))
        enqueue("second", 1)
        self.assertIsNotNone(queue.claim(self.root, "gemini"))
        rows = list(queue.tasks(self.root).values())
        rows[1]["group_index"] = rows[0]["group_index"]
        self.assertFalse(queue.group_complete(rows))

    def test_health_capacity_cannot_raise_the_configured_ceiling(self):
        for index in range(4):
            self.enqueue(str(index), worker="gemini")
        claims = [queue.claim(self.root, "gemini", limit=99) for _ in range(4)]
        self.assertEqual(sum(row is not None for row in claims), 3)

    def test_api_slots_allow_three_real_locks_and_refill_after_release(self):
        import contextlib
        with contextlib.ExitStack() as stack:
            for _ in range(3):
                stack.enter_context(lanes.slot("gemini"))
            with self.assertRaises(BlockingIOError):
                with lanes.slot("gemini"):
                    pass
        with lanes.slot("gemini"):
            pass

    def test_group_executes_all_five_providers_concurrently_and_refills(self):
        for index, worker in enumerate(queue.MODEL_WORKERS):
            queue.enqueue(self.root, "conversation", worker, "Independent supplied evidence for " + worker,
                          worker=worker, group_id="group", group_size=5, group_index=index)
        health = {lane: {"state": "ready"} for lane in queue.WORKERS}
        with patch.object(lanes, "refresh", return_value=health), patch.object(web_dispatch, "launch"):
            self.assertEqual(web_dispatch.tick(), 5)
        claims = list(queue.tasks(self.root).values())
        barrier = threading.Barrier(5)
        def answer(worker, *_args, **_kwargs):
            barrier.wait(timeout=5)
            return worker + " supplied a completed independent result."
        with patch.object(dispatch_worker, "prepare_task", return_value=self.root), patch.object(dispatch_worker, "ask", side_effect=answer):
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
                result = list(pool.map(lambda row: dispatch_worker.execute(row["id"], row["claim_token"]), claims))
        self.assertEqual(result, [0] * 5)
        rows = list(queue.tasks(self.root).values())
        self.assertLess(max(r["execution_started_at"] for r in rows), min(r["finished_at"] for r in rows))
        self.enqueue("refill", worker="codex")
        with patch.object(lanes, "refresh", return_value=health), patch.object(web_dispatch, "launch") as launch:
            self.assertEqual(web_dispatch.tick(), 1)
            self.assertEqual(launch.call_args.args[0]["request_id"], "refill")

    def test_coding_failover_never_uses_an_analysis_or_local_worker(self):
        row = self.enqueue(worker="codex", kind="coding")
        health = {lane: {"state": "ready"} for lane in queue.WORKERS}
        health["codex"]["state"] = "budget_exhausted"
        with patch.object(lanes, "refresh", return_value=health), patch.object(web_dispatch, "launch"):
            self.assertEqual(web_dispatch.tick(), 1)
        self.assertEqual(queue.tasks(self.root)[row["id"]]["worker"], "cursor")

    def test_mini_worker_runs_local_test_suite_and_reports_result(self):
        import shutil
        from source_identity import PATHS
        source = mini_worker.CODE_ROOT
        for relative in PATHS:
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / relative, target)
        suite = self.root / "services"
        suite.mkdir(exist_ok=True)
        (suite / "test_cpu.py").write_text("import unittest\nclass CPU(unittest.TestCase):\n def test_sum(self):\n  self.assertEqual(sum(range(100)),4950)\n")
        row = queue.enqueue(self.root, "conversation", "mini", "Run services/test_cpu.py", worker="mini")
        claim = queue.claim(self.root, "mini")
        with patch.object(mini_worker, "CODE_ROOT", self.root), patch.object(dispatch_worker, "ask") as ask:
            self.assertEqual(dispatch_worker.execute(row["id"], claim["claim_token"]), 0)
            ask.assert_not_called()
        result = queue.tasks(self.root)[row["id"]]
        self.assertEqual(result["status"], "succeeded")
        self.assertIn("Ran 1 test", result["result"])
        self.assertIn("OK", result["result"])
        identity = result['acceptance']['execution_identity']
        self.assertEqual(identity['suite'], 'services/test_cpu.py')
        self.assertEqual(identity['source_hashes']['services/test_cpu.py'],
                         __import__('hashlib').sha256((suite / 'test_cpu.py').read_bytes()).hexdigest())
