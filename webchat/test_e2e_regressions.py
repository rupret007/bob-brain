"""Regressions discovered by the 0927 phone-to-mini end-to-end audit."""
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from app import Chat
from failover import ORDER, ProviderError
from mini_tools import command, parse_tool
from providers import FAST_ORDER, Providers
from job_queue import queue_draft, parse_start


class PhoneRegressions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.core = self.root / "conductor"
        self.core.mkdir()
        subprocess.run(["git", "init", "-q", str(self.core)], check=True)
        self.providers = Providers(self.root, lambda s: s)
        self.chat = Chat(self.core / "webchat", self.root, self.providers)
        self.cid = self.chat.new_conversation()["id"]

    def tearDown(self):
        self.chat.close()
        self.temp.cleanup()

    def wait(self):
        until = time.monotonic() + 5
        while self.chat.workers and time.monotonic() < until:
            time.sleep(.01)
        self.assertFalse(self.chat.workers)
        return self.chat.history(self.cid)["messages"][-1]

    def test_real_command_receipt_persistence_and_duplicate(self):
        rid = str(uuid.uuid4())
        with patch.object(self.providers, "reply", side_effect=AssertionError("must execute on mini")):
            self.chat.submit(self.cid, "run command: pwd", rid)
            result = self.wait()
        self.assertEqual(result["status"], "done")
        self.assertEqual(result["provider"], "mini")
        self.assertIn(str(self.core), result["content"])
        self.assertNotIn("tool_request", self.chat.history(self.cid))
        with patch("app.execute_tool", side_effect=AssertionError("duplicate ran")):
            self.chat.submit(self.cid, "run command: pwd", rid)
            self.assertEqual(len(self.chat.history(self.cid)["messages"]), 2)
        restored = Chat(self.core / "webchat", self.root, self.providers)
        try:
            self.assertEqual(restored.history(self.cid)["messages"][-1], result)
        finally:
            restored.close()

    def test_repo_status_reads_current_working_tree(self):
        (self.core / "visible-change.txt").write_text("a real working-tree change")
        self.chat.submit(self.cid, "repo status: conductor", str(uuid.uuid4()))
        result = self.wait()
        self.assertEqual(result["provider"], "mini")
        self.assertIn("visible-change.txt", result["content"])
        self.assertIn("exit 0", result["content"])

    def test_shell_operators_credentials_and_git_mutations_are_not_executed(self):
        for raw in ("pwd; touch owned", "pwd\nwhoami", "cat webchat/.password", "env", "git push --force", "git -c alias.p=!sh p", "git -C /tmp status", "echo $(whoami)"):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                command(self.root, raw)
        self.assertEqual(parse_tool("run uptime on the mini"), {"kind": "command", "value": "uptime"})
        self.assertIsNone(parse_tool("How do I run a command?"))

    def test_all_five_primary_choices_fail_over_with_same_context(self):
        for primary in ORDER:
            with self.subTest(primary=primary):
                for row in self.providers.circuit.entries.values():
                    row.update(failures=0, retry_at=0)
                seen = []
                def call(name, prompt, *_):
                    seen.append((name, prompt))
                    if name == primary:
                        raise ProviderError(kind="network")
                    return "Recovered useful answer", None
                turn = {"preferred_provider": primary, "messages": [{"role": "user", "content": "Explain how checksums detect a changed file.", "status": "done"}]}
                with patch.object(self.providers, "call", side_effect=call):
                    reply = self.providers.reply(turn, threading.Event(), lambda *_: None)
                self.assertEqual(seen[0][0], primary)
                self.assertNotEqual(reply["provider"], primary)
                self.assertEqual(seen[0][1], seen[1][1])
                self.assertEqual(reply["attempts"][0]["provider"], primary)

    def test_expired_fast_budget_attempts_each_provider_once(self):
        turn = {"messages": [{"role": "user", "content": "Hello", "status": "done"}]}
        seen = []
        def call(name, *_):
            seen.append(name)
            if name != FAST_ORDER[-1]:
                raise ProviderError(kind="network")
            return "Recovered", None
        with patch("providers.FAST_BUDGET_SECONDS", -1), patch.object(self.providers, "call", side_effect=call):
            result = self.providers.reply(turn, threading.Event(), lambda *_: None)
        self.assertEqual(seen, list(FAST_ORDER))
        self.assertEqual(result["provider"], "claude")

    def test_claude_prompt_stays_off_process_arguments(self):
        with patch.object(self.providers, "run", return_value=(0, '{"result":"A useful response"}', "")) as call:
            self.providers.call("claude", "private conversation", None, threading.Event())
        self.assertNotIn("private conversation", " ".join(call.call_args.args[0]))
        self.assertEqual(call.call_args.kwargs["prompt"], "private conversation")

    def test_phone_jobs_have_one_consumer_and_lane_is_honored(self):
        text = "start lane gemini: E2E read-only review of retry behavior"
        self.chat.submit(self.cid, text, str(uuid.uuid4()))
        # Even a matching legacy row must not launch a second execution.
        self.assertTrue(queue_draft(self.root, parse_start(text))["ok"])
        services = Path(__file__).resolve().parents[1] / "services"
        script = """import jobs,web_dispatch
assert jobs.queue_specs()==[], 'legacy scheduler duplicated a phone job'
queue=web_dispatch.task_queue
rows=queue.tasks(jobs.ROOT)
assert len(rows)==1
row=next(iter(rows.values()))
assert row['requested_worker']=='gemini'
assert queue.claim(jobs.ROOT,'codex') is None
claim=queue.claim(jobs.ROOT,'gemini')
assert claim['id']==row['id'] and claim['status']=='claimed'
assert queue.claim(jobs.ROOT,'gemini') is None
print('dispatcher accepted one claim')
"""
        env = dict(os.environ, BOB_ROOT=str(self.root), PYTHONPATH=str(services))
        check = subprocess.run([sys.executable, "-c", script], env=env, capture_output=True, text=True)
        self.assertEqual(check.returncode, 0, check.stderr)
        self.assertIn("dispatcher accepted one claim", check.stdout)

    def test_incompatible_coding_lane_is_blocked_before_queue_write(self):
        result = queue_draft(self.root, parse_start("start lane minimax: implement a new widget"))
        self.assertFalse(result["ok"])
        self.assertFalse((self.root / "next-prompts/INDEX.md").exists())

    def test_production_launcher_keeps_drills_off(self):
        import start
        with patch.object(start, "healthy", side_effect=[False, True]), patch.object(start.subprocess, "run") as run_mock, patch.dict(os.environ, {}, clear=True), patch.object(start, "HERE", self.core):
            run_mock.return_value.stdout = ""
            self.assertEqual(start.main(), 0)
        calls = [c for c in run_mock.call_args_list if "-dmS" in c.args[0]]
        self.assertEqual(calls[0].kwargs["env"]["BOB_WEBCHAT_DRILLS"], "0")

    def test_slow_health_probe_never_kills_existing_chat_service(self):
        import start
        with patch.object(start, "healthy", return_value=False), patch.object(start.subprocess, "run") as run_mock, patch.object(start, "HERE", self.core):
            run_mock.return_value.stdout = "\t123.svc-webchat\t(Detached)\n"
            self.assertEqual(start.main(), 1)
        self.assertEqual(run_mock.call_count, 1)
        self.assertEqual(run_mock.call_args.args[0], ["/usr/bin/screen", "-ls"])

    def test_start_lane_routes_the_actual_dispatcher(self):
        from task_dispatch import task_queue
        value = self.chat.submit(self.cid, "start lane gemini: E2E review of retry behavior", str(uuid.uuid4()))
        row = task_queue.tasks(self.root)[value["messages"][-1]["task_id"]]
        self.assertEqual(row["requested_worker"], "gemini")
        self.assertEqual(row["prompt"], "E2E review of retry behavior")

    def test_readonly_review_does_not_become_coding_from_no_change_instruction(self):
        from task_dispatch import task_queue
        prompt = "start lane gemini: E2E read-only review of the queue. Do not change files or run commands."
        value = self.chat.submit(self.cid, prompt, str(uuid.uuid4()))
        row = task_queue.tasks(self.root)[value["messages"][-1]["task_id"]]
        self.assertEqual(row["kind"], "analysis")
        self.assertEqual(row["requested_worker"], "gemini")

    def test_unexpected_errors_are_audited_without_private_exception_text(self):
        self.chat.audit_error("request_error", RuntimeError("private conversation and credentials"))
        data = self.providers.circuit.log_path.read_text()
        self.assertIn('"event": "request_error"', data)
        self.assertIn('"reason": "RuntimeError"', data)
        self.assertNotIn("private conversation", data)

    def test_restart_requires_authenticated_idle_status(self):
        from deploy_restart import authenticated_verdict
        for panel in ({}, {"error": "Please log in."}, {"in_flight_replies": 1, "deploy_restart": {"allowed": True}}):
            self.assertFalse(authenticated_verdict(panel)["allowed"])
        panel = {"in_flight_replies": 0, "read_at": time.time(), "deploy_restart": {"allowed": True, "defer_reasons": []}}
        self.assertTrue(authenticated_verdict(panel)["allowed"])


if __name__ == "__main__":
    unittest.main()
