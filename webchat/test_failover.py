#!/usr/bin/env python3
"""Failure/breaker tests plus real subprocess and durable-queue regressions."""
import json
import fcntl
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from app import Chat, RequestError
from failover import AllDown, Circuit, ORDER, ProviderError, classify, reset_time
from providers import Cancelled, Providers, clean_env, parse_codex, parse_cursor, run
from actions import queue_once


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.provider = Providers(self.root, lambda s: s)
        self.turn = {"messages": [{"role": "user", "status": "done", "content": "Debug this connection; remember violet kite.", "request_id": str(uuid.uuid4())}]}
        self.cancel = threading.Event()

    def tearDown(self):
        self.provider.close()
        self.temp.cleanup()

    def reply(self):
        return self.provider.reply(self.turn, self.cancel, lambda *_: None)


class FailoverTests(Fixture):
    def test_all_failure_classes_for_each_provider_and_sanitized_audit(self):
        cases = [(1, "not logged in", "not_logged_in"), (0, "Rate limit 429 retry-after: 40", "rate_limit"),
                 (1, "operation timed out", "timeout"), (19, "fatal process exit", "nonzero_exit"),
                 (0, "empty or garbage answer", "invalid_output"), (1, "connection reset by peer", "network")]
        for name in ORDER:
            for code, detail, kind in cases:
                with self.subTest(provider=name, kind=kind):
                    for row in self.provider.circuit.entries.values():
                        row.update(failures=0, retry_at=0)
                    seen = []
                    def call(provider, *_):
                        seen.append(provider)
                        if provider == name:
                            raise ProviderError(detail + " private-output", code=code)
                        if ORDER.index(provider) < ORDER.index(name):
                            raise ProviderError(kind="busy")
                        return "Next provider answered.", None
                    with patch.object(self.provider, "call", side_effect=call):
                        if name == ORDER[-1]:
                            with self.assertRaises(AllDown) as error:
                                self.reply()
                            attempts = error.exception.attempts
                        else:
                            answer = self.reply()
                            attempts = answer["attempts"]
                            self.assertEqual(answer["provider"], ORDER[ORDER.index(name) + 1])
                    self.assertEqual(next(a for a in attempts if a["provider"] == name)["kind"], kind)
                    self.assertNotIn("claude", seen)
        data = self.provider.circuit.log_path.read_text()
        self.assertNotIn("private-output", data)
        self.assertNotIn("violet kite", data)
        self.assertTrue(all(isinstance(json.loads(line), dict) for line in data.splitlines()))
        self.assertEqual(self.provider.circuit.log_path.stat().st_mode & 0o777, 0o600)

    def test_breaker_backoff_persistence_half_open_exclusion_and_recovery(self):
        now = [1000]
        c = self.provider.circuit
        c.clock = lambda: now[0]
        for delay in (300, 600, 1200, 1800, 1800):
            self.assertEqual(c.failed("codex", ProviderError(kind="timeout")), now[0] + delay)
            self.assertFalse(c.acquire("codex"))
            now[0] += delay
            self.assertEqual(c.snapshot()["codex"]["state"], "half_open")
            self.assertTrue(c.acquire("codex"))
            self.assertFalse(c.acquire("codex"))
            c.release("codex")
        restored = Circuit(c.path, c.log_path, clock=lambda: now[0])
        self.assertEqual(restored.entries["codex"]["failures"], 5)
        restored.succeeded("codex")
        self.assertEqual(restored.snapshot()["codex"]["state"], "ready")
        self.assertEqual(restored.failed("codex", ProviderError(kind="timeout")), now[0] + 300)

    def test_rate_reset_and_probe_does_not_clear_quota(self):
        now = datetime(2026, 9, 27, tzinfo=timezone.utc).timestamp()
        for detail, delay in [("retry-after: 90", 90), ('"retryDelay": "45s"', 45), ("try again in 2 minutes", 120),
                              ("reset_at: " + str(int(now + 4000)), 4000), ("resets 2026-09-27T01:00:00Z", 3600),
                              ("retry-after: Sun, 27 Sep 2026 01:00:00 GMT", 3600)]:
            self.assertEqual(reset_time(detail, now), now + delay, detail)
        self.assertIsNone(reset_time("quota exhausted", now))
        c = self.provider.circuit
        c.clock = lambda: now
        c.failed("codex", ProviderError(kind="rate_limit", retry_at=now + 7200))
        c.probed("codex")
        self.assertEqual(c.entries["codex"]["retry_at"], now + 7200)
        self.assertEqual(c.snapshot()["codex"]["state"], "cooldown")

    def test_background_probes_do_not_generate_or_invoke_claude(self):
        with patch.object(self.provider, "run", return_value=(0, "configured", "")) as runner:
            self.provider.probe_once()
        self.assertEqual(runner.call_count, 4)
        for args in runner.call_args_list:
            self.assertNotIn("prompt", args.kwargs)
            self.assertNotIn("claude", args.args[0])
        self.assertTrue(all(self.provider.circuit.entries[n]["probed_at"] for n in ORDER))

    def test_mid_answer_failure_discards_partial_and_reuses_exact_context(self):
        prompts = []
        def call(name, prompt, *_):
            prompts.append(prompt)
            if name == "codex":
                return parse_codex('\n'.join(map(json.dumps, [
                    {"type": "item.completed", "item": {"type": "agent_message", "text": "Partial must not appear"}},
                    {"type": "turn.failed", "error": {"message": "network disconnected"}}])))
            return "Full recovered answer", None
        with patch.object(self.provider, "call", side_effect=call):
            answer = self.reply()
        self.assertEqual(answer["content"], "Full recovered answer")
        self.assertEqual(prompts[0], prompts[1])
        self.assertEqual(answer["attempts"][0]["kind"], "network")
        self.assertTrue(answer["attempts"][0]["partial_discarded"])
        self.assertNotIn("Partial must not appear", json.dumps(answer))

    def test_structured_errors_with_zero_exit_and_malformed_output(self):
        for parser, value, kind in [(parse_cursor, '{"is_error":true,"result":"Usage limit reached"}', "rate_limit"),
                                    (parse_codex, '{"type":"error","message":"not logged in"}', "not_logged_in"),
                                    (parse_codex, '{"type":"item.completed","item":42}', "invalid_output"),
                                    (parse_cursor, '{"result":"<html>bad gateway</html>"}', "invalid_output")]:
            with self.assertRaises(ProviderError) as error:
                parser(value)
            self.assertEqual(error.exception.kind, kind)

    def test_all_down_queues_no_fake_answer_and_skips_until_cooldown(self):
        with patch.object(self.provider, "call", side_effect=ProviderError(kind="network")) as call:
            with self.assertRaises(AllDown) as error:
                self.reply()
            self.assertEqual(call.call_count, 4)
            self.assertIn("queued", str(error.exception))
            with self.assertRaises(AllDown):
                self.reply()
            self.assertEqual(call.call_count, 4)

    def test_drill_mode_pins_explicit_provider(self):
        self.turn["preferred_provider"] = "cursor"
        with patch.dict(os.environ, {"BOB_WEBCHAT_DRILLS": "1"}):
            other = Providers(self.root, lambda s: s)
            with patch.object(other, "drill", return_value={"force_fail": {}}), \
                    patch.object(other, "call", return_value=("Pinned", None)) as call:
                other.reply(self.turn, self.cancel, lambda *_: None)
                self.assertEqual(call.call_args.args[0], "cursor")
                self.assertEqual(call.call_count, 1)

    def test_claude_only_when_selected_and_stop_never_falls_through(self):
        self.turn["preferred_provider"] = "claude"
        with patch.object(self.provider, "call", return_value=("A short critique", None)) as call:
            self.assertEqual(self.reply()["provider"], "claude")
            self.assertEqual(call.call_count, 1)
        self.turn["preferred_provider"] = "auto"
        with patch.object(self.provider, "call", side_effect=Cancelled("Reply stopped")) as call:
            with self.assertRaises(Cancelled):
                self.reply()
            self.assertEqual(call.call_count, 1)
            self.assertEqual(self.provider.circuit.entries["codex"]["failures"], 0)

    def test_minimax_uses_metered_helper_and_per_provider_timeouts(self):
        with patch.object(self.provider, "run", return_value=(0, "<bob-webchat-reply>Fine</bob-webchat-reply>", "")) as call:
            self.provider.call("minimax", "context", None, self.cancel)
        self.assertTrue(call.call_args.args[0][1].endswith("api_call.py"))
        self.assertIn("minimax", call.call_args.args[0])
        self.assertEqual(call.call_args.kwargs["timeout"], 120)
        self.assertEqual(classify(1, "BudgetExceeded: MiniMax $48 cap"), "budget")
        with patch.dict(os.environ, {"BOB_WEBCHAT_TIMEOUT_CODEX": "33", "BOB_WEBCHAT_TIMEOUT_CURSOR": "44"}):
            other = Providers(self.root, lambda s: s)
        self.assertEqual(other.timeouts["codex"], 33)
        self.assertEqual(other.timeouts["cursor"], 44)

    def test_prompt_stdin_reaches_eof(self):
        code, out, _ = run([sys.executable, "-c", "import sys; print(repr(sys.stdin.read()))"], cwd=self.root, env=clean_env(), cancel=self.cancel, prompt="private context", timeout=3)
        self.assertEqual((code, out.strip()), (0, "'private context'"))
        code, out, _ = run([sys.executable, "-c", "import sys; print(repr(sys.stdin.read()))"], cwd=self.root, env=clean_env(), cancel=self.cancel, timeout=3)
        self.assertEqual((code, out.strip()), (0, "''"))

    def test_real_timeout_and_stop_kill_children_including_nested_groups(self):
        for mode in ("timeout", "stop"):
            with self.subTest(mode=mode):
                marker = self.root / (mode + ".json")
                cancel = threading.Event()
                if mode == "stop":
                    threading.Timer(.7, cancel.set).start()
                with self.assertRaises(Cancelled if mode == "stop" else ProviderError):
                    run([sys.executable, str(Path(__file__).with_name("drill_child.py")), str(marker)], cwd=self.root,
                        env=dict(clean_env(), BOB_WEBCHAT_DRILLS="1"), cancel=cancel, timeout=.6 if mode == "timeout" else 5)
                pids = json.loads(marker.read_text())
                for pid in [pids["parent"], *pids["children"]]:
                    result = subprocess.run(["/bin/ps", "-p", str(pid), "-o", "stat="], capture_output=True, text=True)
                    self.assertTrue(not result.stdout.strip() or result.stdout.strip().startswith("Z"), (pid, result.stdout))

    def test_drill_file_requires_startup_opt_in(self):
        path = self.root / "conductor/webchat/.drill.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"force_fail":{"codex":"network"}}')
        with patch.dict(os.environ, {"BOB_WEBCHAT_DRILLS": "0", "BOB_WEBCHAT_FORCE_FAIL": ""}):
            self.assertEqual(self.provider.drill()["force_fail"], {})

    def test_scoped_drill_does_not_change_real_chat_health(self):
        cid = str(uuid.uuid4())
        self.turn["id"] = cid
        path = self.root / "conductor/webchat/.drill.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"conversation_ids": [cid], "force_fail": {n: "network" for n in ORDER}}))
        with patch.dict(os.environ, {"BOB_WEBCHAT_DRILLS": "1"}), patch.object(self.provider, "call", return_value=("Healthy real chat", None)) as call:
            with self.assertRaises(AllDown):
                self.reply()
            call.assert_not_called()
            self.assertTrue(all(row["failures"] == 0 for row in self.provider.circuit.entries.values()))
            self.turn["id"] = str(uuid.uuid4())
            self.assertEqual(self.reply()["content"], "Healthy real chat")

    def test_api_concurrency_and_single_half_open_probe(self):
        c = self.provider.circuit
        for name in ("gemini", "minimax"):
            self.assertTrue(c.acquire(name))
            self.assertTrue(c.acquire(name))
            c.release(name)
            self.assertEqual(c.snapshot()[name]["state"], "busy")
            c.release(name)
            c.failed(name, ProviderError(kind="network"))
            c.entries[name]["retry_at"] = 0
            self.assertTrue(c.acquire(name))
            self.assertFalse(c.acquire(name))
            c.release(name)

    def test_concurrent_turns_do_not_change_each_others_timeouts(self):
        barrier = threading.Barrier(2)
        observed = []
        def call(*_):
            barrier.wait(timeout=3)
            observed.append(self.provider.current_call.timeout)
            return "Answer", None
        with patch.object(self.provider, "call", side_effect=call):
            threads = [threading.Thread(target=self.provider._call_timed, args=("gemini", "prompt", None, self.cancel, duration)) for duration in (7, 29)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(4)
        self.assertEqual(sorted(observed), [7, 29])
        self.assertEqual(self.provider.timeouts["gemini"], 120)


class QueueTests(Fixture):
    def setUp(self):
        super().setUp()
        self.chat = Chat(self.root / "conductor/webchat", self.root, self.provider)
        self.identifier = next(iter(self.chat.conversations))

    def tearDown(self):
        self.chat.close()
        super().tearDown()

    def wait(self):
        deadline = time.monotonic() + 5
        while self.chat.worker_info(self.identifier) and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertFalse(self.chat.worker_info(self.identifier))

    def submit(self, text="Debug a safe memory question", request_id=None):
        self.chat.submit(self.identifier, text, request_id or str(uuid.uuid4()))
        self.wait()

    def test_queue_persists_and_retries_original_turn_once(self):
        request_id = str(uuid.uuid4())
        with patch.object(self.provider, "call", side_effect=ProviderError(kind="network")):
            self.submit(request_id=request_id)
        value = self.chat.history(self.identifier)
        self.assertEqual(value["messages"][-1]["status"], "waiting")
        self.assertNotIn("retry_prompt", value)
        frozen = self.chat.conversations[self.identifier]["retry_prompt"]
        self.chat.close()
        self.chat = Chat(self.chat.folder, self.root, self.provider)
        self.assertEqual(self.chat.history(self.identifier)["messages"][-1]["status"], "waiting")
        self.chat.submit(self.identifier, "Debug a safe memory question", request_id)
        self.assertEqual(len(self.chat.history(self.identifier)["messages"]), 2)
        with self.assertRaises(RequestError):
            self.chat.submit(self.identifier, "Different turn", str(uuid.uuid4()))
        self.chat.conversations[self.identifier]["messages"][-1]["retry_at"] = 0
        for row in self.provider.circuit.entries.values():
            row["retry_at"] = 0
        with patch.object(self.provider, "call", return_value=("Recovered", None)) as call:
            self.chat.retry_queued()
            self.wait()
        self.assertEqual(call.call_count, 1)
        self.assertEqual(call.call_args.args[1], frozen)
        result = self.chat.history(self.identifier)
        self.assertEqual(len(result["messages"]), 2)
        self.assertEqual(result["messages"][-1]["content"], "Recovered")
        self.assertEqual(result["messages"][-1]["status"], "done")

    def test_cancel_waiting_request_prevents_replay(self):
        with patch.object(self.provider, "call", side_effect=ProviderError(kind="network")):
            self.submit()
        self.chat.stop(self.identifier)
        with patch.object(self.provider, "call") as call:
            self.chat.retry_queued()
        call.assert_not_called()
        self.assertEqual(self.chat.history(self.identifier)["messages"][-1]["status"], "cancelled")

    def test_prohibited_action_is_refused_and_duplicate_card_is_once_only(self):
        request_id = str(uuid.uuid4())
        with patch.object(self.provider, "call") as call:
            self.submit("merge #158", request_id)
            self.submit("merge #158", request_id)
        call.assert_not_called()
        result = self.chat.history(self.identifier)
        self.assertEqual(len(result["messages"]), 2)
        self.assertEqual(result["messages"][-1]["action_card"]["state"], "refused")
        self.assertFalse(result["messages"][-1]["action_card"]["executable"])

    def test_confirmation_receipt_survives_failed_conversation_save(self):
        self.submit("start a job: review the draft UI")
        request_id = str(uuid.uuid4())
        result = {"ok": True, "file": "one-job.md", "path": "next-prompts/one-job.md"}
        with patch("actions.queue_draft", return_value=result) as queue:
            with patch.object(self.chat, "save", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    self.chat.submit(self.identifier, "yes, start job", request_id)
            self.chat.submit(self.identifier, "yes, start job", request_id)
            self.chat.submit(self.identifier, "yes, start job", request_id)
            self.assertEqual(queue.call_count, 1)
        self.assertEqual(self.chat.history(self.identifier)["messages"][-1]["action_card"]["state"], "queued")

    def test_ambiguous_action_and_crash_after_effect_never_execute_twice(self):
        action_id = str(uuid.uuid4())
        with patch("actions.queue_draft", side_effect=OSError("failed after external effect")) as queue:
            self.assertFalse(queue_once(self.root, action_id, "review draft")["ok"])
            self.assertFalse(queue_once(self.root, action_id, "review draft")["ok"])
            self.assertEqual(queue.call_count, 1)
        with patch("actions.queue_draft") as queue:
            self.assertFalse(queue_once(self.root, action_id, "changed task")["ok"])
            queue.assert_not_called()

    def test_handback_failure_preserves_completed_answer(self):
        with patch("app.append_turn", side_effect=OSError("unavailable")), patch.object(self.provider, "call", return_value=("Completed answer", None)):
            self.submit()
        self.assertEqual(self.chat.history(self.identifier)["messages"][-1]["status"], "done")
        self.assertEqual(self.chat.history(self.identifier)["messages"][-1]["content"], "Completed answer")

    def test_action_queue_uses_scheduler_lock_before_writing(self):
        from job_queue import queue_draft
        folder = self.root / "conductor/locks"
        folder.mkdir(parents=True)
        with (folder / "queue.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = queue_draft(self.root, "review a draft")
            self.assertFalse(result["ok"])
            self.assertFalse((self.root / "next-prompts/INDEX.md").exists())
        result = queue_draft(self.root, "review a draft")
        self.assertTrue(result["ok"])
        self.assertIn(result["file"], (self.root / "next-prompts/INDEX.md").read_text())


class BillingTests(Fixture):
    def test_chat_cap_blocks_shared_transport_after_background_cap_increase(self):
        ledger = self.root / "conductor/ledger"
        ledger.mkdir(parents=True)
        (ledger / "minimax.jsonl").write_text(json.dumps({"call_id": "existing", "cost_usd": 59}) + "\n")
        services = Path(__file__).resolve().parents[1] / "services"
        script = """
import sys
sys.path.insert(0, sys.argv[1])
sys.path.insert(0, sys.argv[2])
import api, budget
from billing import enforce_chat_cap
budget.CAP_USD = 96
enforce_chat_cap(budget)
assert budget.CAP_USD == 59
def no_http(*a, **kw):
    raise AssertionError('transport must never run')
api.run = no_http
try:
    api.model_call('minimax', 'test', max_tokens=1)
except budget.BudgetExceeded:
    print('PASS: reservation rejected before transport')
else:
    raise AssertionError('cap bypassed')
"""
        result = subprocess.run([sys.executable, "-c", script, str(services), str(Path(__file__).parent)],
            env=dict(os.environ, BOB_ROOT=str(self.root), MINIMAX_API_KEY="fixture-only"), capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("reservation rejected", result.stdout)
        self.assertEqual(len((ledger / "minimax.jsonl").read_text().splitlines()), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
