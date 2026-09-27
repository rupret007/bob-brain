#!/usr/bin/env python3
"""Recovery/failure tests in a disposable workspace; no live API or screen calls."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parents[1]
sys.path.insert(0, str(HERE))
import state
import api
import jobs
import runtime
import conductor_pass


class ServicesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="bob-services-test-")
        self.root = Path(self.temp.name)
        self.conductor = self.root / "conductor"
        self.conductor.mkdir()
        (self.root / "next-prompts").mkdir()
        (self.root / "next-prompts/INDEX.md").write_text("| Pri | File | Project | Kind | Status | Notes |\n")
        self.patches = []
        for module in (state, api, jobs, runtime, conductor_pass):
            for name, value in (("ROOT", self.root), ("CONDUCTOR", self.conductor)):
                if hasattr(module, name):
                    self.patches.append(patch.object(module, name, value))
        self.patches += [patch.object(runtime, "HEARTBEATS", self.conductor / "heartbeats"),
                         patch.object(runtime, "SERVICES", self.conductor / "services"),
                         patch.dict(os.environ, {"BOB_ROOT": str(self.root)})]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.temp.cleanup()

    def harvest_helper(self):
        (self.root / "bin").mkdir(exist_ok=True)
        shutil.copy2(SOURCE / "bin/auto_harvest.py", self.root / "bin/auto_harvest.py")
        return jobs.load_helper("auto_harvest")

    def test_journal_repairs_interrupted_append_without_losing_job(self):
        state.job_event("a", "launched", job_dir="a", pri="1")
        with (self.conductor / "jobs.jsonl").open("ab") as out:
            out.write(b'{"job_id":"b", "sta')
        state.job_event("a", "running", recovery="resumed")
        self.assertEqual(state.jobs()["a"]["pri"], "1")
        self.assertEqual(state.jobs()["a"]["state"], "running")
        self.assertTrue((self.conductor / "jobs.jsonl.interrupted-tail").exists())

    def test_journal_refuses_middle_corruption_and_terminal_regression(self):
        state.job_event("a", "harvested")
        with self.assertRaises(ValueError):
            state.job_event("a", "running")
        path = self.conductor / "jobs.jsonl"
        path.write_text("broken\n" + path.read_text())
        with self.assertRaises(ValueError):
            state.jobs()

    def test_harvest_twice_does_not_duplicate_queue_or_deliverables(self):
        helper = self.harvest_helper()
        folder = self.root / "job-a"
        (folder / "queue-ready").mkdir(parents=True)
        (folder / "RESULT.txt").write_text("Result with concrete evidence and one follow-on prompt.\n")
        (folder / "queue-ready/01-audit.md").write_text("Audit the existing rehearsal receipt with specific evidence and do not invent coding work.\n")
        state.job_event("job-a", "launched", job_dir=str(folder))
        helper.harvest_job("job-a")
        first_index = (self.root / "next-prompts/INDEX.md").read_text()
        first_files = sorted(p.name for p in (self.root / "next-prompts/_inbox").iterdir())
        helper.harvest_job("job-a")
        self.assertEqual(first_index, (self.root / "next-prompts/INDEX.md").read_text())
        self.assertEqual(first_files, sorted(p.name for p in (self.root / "next-prompts/_inbox").iterdir()))
        self.assertEqual(state.jobs()["job-a"]["state"], "harvested")

    def test_harvest_failure_does_not_mark_complete(self):
        helper = self.harvest_helper()
        folder = self.root / "job-b"
        folder.mkdir()
        (folder / "RESULT.txt").write_text("result")
        (folder / "PROMOTE.json").write_text('[{"file":"missing.md"}]')
        state.job_event("job-b", "running", job_dir=str(folder))
        with self.assertRaises(ValueError):
            helper.harvest_job("job-b")
        self.assertEqual(state.jobs()["job-b"]["state"], "running")

    def fake_refill(self):
        return SimpleNamespace(screen_ls=lambda: "No Sockets found", parse_running_rows=lambda: [],
                               screen_alive=lambda *a: False, copy_tmp_closeout=lambda *a: [],
                               job_dir_looks_coding=lambda *a: False)

    def test_restart_resumes_journaled_launch_before_screen_was_started(self):
        folder = self.root / "job-c"
        folder.mkdir()
        (folder / "run.sh").write_text("#!/bin/bash\nexit 0\n")
        state.write_json(self.conductor / "jobs-imported.json", {"done": True})
        state.job_event("job-c", "launched", job_dir=str(folder), legacy=False)
        with patch.object(jobs.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as launch:
            self.assertEqual(jobs.recover(self.fake_refill()), [])
        self.assertEqual(launch.call_count, 1)
        self.assertEqual(state.jobs()["job-c"]["state"], "running")
        self.assertEqual(state.jobs()["job-c"]["resume_count"], 1)

    def test_live_job_is_adopted_without_duplicate_launch(self):
        folder = self.root / "job-d"
        folder.mkdir()
        state.write_json(self.conductor / "jobs-imported.json", {"done": True})
        state.job_event("job-d", "launched", job_dir=str(folder))
        refill = self.fake_refill()
        refill.screen_alive = lambda *a: True
        with patch.object(jobs.subprocess, "run") as launch:
            jobs.recover(refill)
        launch.assert_not_called()
        self.assertEqual(state.jobs()["job-d"]["state"], "running")

    def test_recovery_reharvests_result_after_previous_result_changed(self):
        helper = self.harvest_helper()
        folder = self.root / "job-e"
        folder.mkdir()
        (folder / "BLOCKER.txt").write_text("BLOCKER first")
        state.job_event("job-e", "running", job_dir=str(folder))
        helper.harvest_job("job-e")
        (folder / "RESULT.txt").write_text("Recovered final result")
        state.write_json(self.conductor / "jobs-imported.json", {"done": True})
        refill = self.fake_refill()
        refill.harvest_on_reap = helper.harvest_job
        jobs.recover(refill)
        self.assertEqual(state.jobs()["job-e"]["outcome"], "result")
        self.assertTrue(state.jobs()["job-e"]["result_path"].endswith("RESULT.txt"))

    def test_watchdog_caps_three_restarts_and_start_all_cannot_bypass(self):
        now = time.time()
        runtime.HEARTBEATS.mkdir()
        sessions = {"svc-" + n: "123.svc-" + n for n in runtime.INTERVALS}
        for n in runtime.INTERVALS:
            (runtime.HEARTBEATS / n).touch()
        state.write_json(self.conductor / "supervisor.json", {n: {"ever_started": True, "started_at": now} for n in runtime.INTERVALS})
        with patch.object(runtime, "screen_sessions", return_value=sessions), patch.object(runtime.subprocess, "run", return_value=SimpleNamespace(returncode=0)), patch.object(runtime.time, "sleep"):
            for count in range(4):
                entries = state.read_json(self.conductor / "supervisor.json")
                entries["reviewer"]["started_at"] = now - 4000
                state.write_json(self.conductor / "supervisor.json", entries)
                os.utime(runtime.HEARTBEATS / "reviewer", (now - 4000, now - 4000))
                runtime.ensure_services(check_stale=True, self_name="watchdog")
            self.assertEqual(len(state.read_json(self.conductor / "supervisor.json")["reviewer"]["restarts"]), 3)
            sessions.pop("svc-reviewer")
            runtime.ensure_services(check_stale=False)
        self.assertEqual(len(state.read_json(self.conductor / "supervisor.json")["reviewer"]["restarts"]), 3)
        self.assertIn("JEFF:", (self.conductor / "STATUS.md").read_text())

    def test_external_guard_can_restart_stale_watchdog(self):
        runtime.HEARTBEATS.mkdir()
        for n in runtime.INTERVALS:
            (runtime.HEARTBEATS / n).touch()
        os.utime(runtime.HEARTBEATS / "watchdog", (1, 1))
        sessions = {"svc-" + n: "123.svc-" + n for n in runtime.INTERVALS}
        with patch.object(runtime, "screen_sessions", return_value=sessions), patch.object(runtime.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as command, patch.object(runtime.time, "sleep"):
            runtime.ensure_services(check_stale=True)
        self.assertEqual(command.call_count, 2)
        self.assertIn("watchdog", str(command.call_args))

    def test_http_backoff_and_curl_timeout_without_key_in_argv(self):
        calls = []
        def transport(command, **kwargs):
            calls.append((command, kwargs))
            Path(command[command.index("-o") + 1]).write_text('{"ok":true}')
            return SimpleNamespace(returncode=0, stdout="503" if len(calls) < 3 else "200")
        with patch.object(api.subprocess, "run", side_effect=transport), patch.object(api.time, "sleep") as sleep:
            self.assertTrue(api.http_json("https://example.invalid/?key=secret")['ok'])
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [2, 4])
        for cmd, kwargs in calls:
            self.assertIn("-m", cmd)
            self.assertNotIn("secret", " ".join(cmd))
            self.assertIn("secret", kwargs["input"])

    def test_rejects_reasoning_only_and_truncated_model_answers(self):
        for response in ({"choices": [{"finish_reason": "length", "message": {"content": "long response"}}]},
                         {"choices": [{"finish_reason": "stop", "message": {"content": "<think>hidden only</think>"}}]}):
            with self.assertRaises(RuntimeError):
                api.extract("minimax", response)
        with self.assertRaises(RuntimeError):
            api.extract("gemini", {"candidates": [{"finishReason": "MAX_TOKENS"}]})

    def test_missing_key_failure_and_cached_success_resume_independently(self):
        output = self.root / "RESULT.txt.gemini.md"
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            self.assertFalse(api.critique("gemini", "evidence", output))
        self.assertIn("need GEMINI_API_KEY", (self.conductor / "STATUS.md").read_text())
        with patch.dict(os.environ, {"GEMINI_API_KEY": "fixture"}), patch.object(api, "http_json", return_value="A complete critique with a concrete check.") as http:
            self.assertTrue(api.critique("gemini", "evidence", output))
            self.assertTrue(api.critique("gemini", "evidence", output))
            self.assertEqual(http.call_count, 1)

    def test_api_failure_stays_pending_and_cools_down(self):
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "fixture"}), patch.object(api, "http_json", side_effect=RuntimeError("HTTP 402")) as http:
            self.assertFalse(api.critique("minimax", "evidence", self.root / "out.md"))
            self.assertFalse(api.critique("minimax", "evidence", self.root / "out.md"))
        self.assertEqual(http.call_count, 1)
        self.assertFalse(state.journal_rows("model-runs")[0]["ok"])

    def test_dashboard_failure_writes_local_snapshot_and_advances_heartbeat(self):
        with patch.object(runtime, "snapshot", return_value={"generated_at": "fixture"}), patch.object(runtime, "push_dashboard", side_effect=RuntimeError("no auth")):
            runtime.cycle("dashboard-updater")
        self.assertTrue((runtime.HEARTBEATS / "dashboard-updater").exists())
        self.assertFalse(state.read_json(self.conductor / "dashboard.json")["publication"]["ok"])
        self.assertIn("JEFF:", (self.conductor / "STATUS.md").read_text())

    def test_failed_cycle_does_not_forge_heartbeat(self):
        with patch.object(runtime, "runner_cycle", side_effect=RuntimeError("broken queue")):
            with self.assertRaises(RuntimeError):
                runtime.cycle("job-runner")
        self.assertFalse((runtime.HEARTBEATS / "job-runner").exists())

    def test_real_bash_once_and_lifetime_lock(self):
        shutil.copytree(HERE, self.conductor / "services", ignore=shutil.ignore_patterns("__pycache__"))
        script = str(self.conductor / "services/reviewer.sh")
        env = dict(os.environ, BOB_ROOT=str(self.root))
        once = subprocess.run(["/bin/bash", script, "--once"], env=env, capture_output=True, timeout=10)
        self.assertEqual(once.returncode, 0, once.stderr)
        self.assertTrue((runtime.HEARTBEATS / "reviewer").exists())
        process = subprocess.Popen(["/bin/bash", script], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            time.sleep(0.4)
            second = subprocess.run(["/bin/bash", script, "--once"], env=env, capture_output=True, text=True, timeout=10)
            self.assertIn("already running", second.stdout)
        finally:
            process.terminate()
            process.communicate(timeout=10)


if __name__ == "__main__":
    unittest.main(verbosity=2)
