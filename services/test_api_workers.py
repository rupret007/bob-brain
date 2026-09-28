"""Offline API job execution through the real scheduler, transport and ledger."""
import hashlib
import json
import os
import sys
import time
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import api
import api_worker
import budget
import dispatch_worker
import lanes
import state
import worker
import workspaces
import web_dispatch
from api_tasks import MODELS
import test_dispatch as dispatch_fixture
from web_dispatch import task_queue as queue


class APIWorkerTests(unittest.TestCase):
    setUp = dispatch_fixture.DispatchTests.setUp
    tearDown = dispatch_fixture.DispatchTests.tearDown

    def repo(self):
        repo = self.root / "repo"
        repo.mkdir(exist_ok=True)
        workspaces.git(repo, "init", "-b", "main")
        (repo / "queue.py").write_text("def enqueue(job):\n    return job\n")
        (repo / "keys.env").write_text("GEMINI_API_KEY=fixture-must-not-be-sent\n")
        (repo / "webchat").mkdir(exist_ok=True)
        (repo / "webchat/.password").write_text("fixture-password-never-read")
        (repo / "linked.py").symlink_to(repo / "webchat/.password")
        workspaces.git(repo, "add", "queue.py", "keys.env", "webchat/.password", "linked.py")
        workspaces.git(repo, "-c", "user.name=Test", "-c", "user.email=test@localhost", "commit", "-m", "Fixture")
        return repo

    def test_frozen_turn_one_reaches_both_api_transports_and_delivers_reports(self):
        # Real chat -> queue -> scheduler -> worker -> metered API transport.
        # Only HTTP responses, lane health and semantic acceptance are fixtures.
        with patch.object(sys, "path", [str(Path(__file__).resolve().parents[1] / "webchat"), *sys.path]):
            from app import Chat
            from dispatch_receipts import receipt_errors
            from integration_rubric import sessions

            repo = self.repo()
            (self.core / "services").mkdir()
            (self.core / "services/projects.json").write_text(json.dumps({"Web Bob": {"repo": str(repo)}}))
            (self.core / "keys.env").write_text("GEMINI_API_KEY=gemini-fixture-key\nMINIMAX_API_KEY=minimax-fixture-key\n")
            providers = Mock(spec=["reply"])
            providers.reply.side_effect = AssertionError("Assignments must bypass conversational models")
            chat = Chat(self.core / "webchat", self.root, providers)
            self.addCleanup(chat.close)
            cid = chat.conversation_list()["conversations"][0]["id"]
            request = str(uuid.uuid4())
            started = time.time()
            with patch("live_status_snapshot._screen_sessions", return_value={"lane-webbob-llm-reviews": "29817.lane-webbob-llm-reviews"}), \
                    patch("live_status_snapshot.process_table", return_value={}):
                receipt = chat.submit(cid, sessions()[0]["exchanges"][0]["message"], request)["messages"][-1]
            rows = queue.tasks(self.root)
            self.assertEqual(len(rows), 2)
            self.assertEqual(receipt_errors(receipt, rows, cid, request, started), [])
            self.assertEqual([rows[key]["requested_worker"] for key in receipt["task_ids"]], ["gemini", "minimax"])
            self.assertEqual([rows[key]["kind"] for key in receipt["task_ids"]], ["audit", "test-writing"])
            providers.reply.assert_not_called()

            called = []
            def transport(argv, **kwargs):
                config = Path(argv[argv.index("--config") + 1]).read_text()
                payload = json.loads(Path(argv[argv.index("--data-binary") + 1][1:]).read_text())
                lane = "gemini" if "generativelanguage" in config else "minimax"
                current = next(row for row in queue.tasks(self.root).values() if row["status"] == "running")
                self.assertEqual(current["worker"], lane)
                self.assertEqual(current["model"], MODELS[lane])
                self.assertIsNone(current["source_job_id"])
                self.assertIn("FILE queue.py", json.dumps(payload))
                self.assertIn("worker activity is unverified", json.dumps(payload))
                self.assertNotIn("fixture-must-not-be-sent", json.dumps(payload))
                answer = lane + ": queue.py needs a duplicate-enqueue regression. Tests were not run."
                if lane == "gemini":
                    self.assertIn("gemini-2.5-pro:generateContent", config)
                    result = dict(candidates=[dict(finishReason="STOP", content=dict(parts=[dict(text=answer)]))],
                                  usageMetadata=dict(promptTokenCount=100, candidatesTokenCount=30))
                else:
                    self.assertIn("https://api.minimax.io/v1/text/chatcompletion_v2", config)
                    self.assertEqual(payload["model"], "MiniMax-M2.7")
                    result = dict(choices=[dict(finish_reason="stop", message=dict(content=answer))],
                                  usage=dict(prompt_tokens=100, completion_tokens=30), base_resp=dict(status_code=0))
                Path(argv[argv.index("-o") + 1]).write_text(json.dumps(result))
                called.append(lane)
                return SimpleNamespace(returncode=0, stdout="200", stderr="")

            def launch(row):
                self.assertEqual(dispatch_worker.execute(row["id"], row["claim_token"]), 0)

            with patch.object(lanes, "refresh", return_value={lane: dict(state="ready") for lane in MODELS}), \
                    patch.object(web_dispatch, "launch", side_effect=launch), \
                    patch.object(api, "CONDUCTOR", self.core), patch.object(api, "run", side_effect=transport), \
                    patch.dict(os.environ, {"GEMINI_API_KEY": "gemini-fixture-key", "MINIMAX_API_KEY": "minimax-fixture-key"}), \
                    patch.object(dispatch_worker, "prepare_task") as prepare, \
                    patch.object(dispatch_worker.draft_publish, "publish") as publish:
                self.assertEqual(web_dispatch.tick(), 2)
            self.assertEqual(called, ["gemini", "minimax"])
            prepare.assert_not_called()
            publish.assert_not_called()
            for row in queue.tasks(self.root).values():
                self.assertEqual(row["status"], "succeeded")
                self.assertEqual(Path(row["repo"]), repo)
                self.assertIn(row["result"], Path(row["result_path"]).read_text())
                self.assertEqual(row["result_sha256"], hashlib.sha256(row["result"].encode()).hexdigest())
                self.assertEqual(row["acceptance"]["result_sha256"], row["result_sha256"])
                self.assertTrue(row["evidence"]["files"])
                self.assertIsNone(row["branch"])
                self.assertIsNone(row["worktree"])
            chat.reconcile_tasks()
            chat.reconcile_tasks()
            messages = chat.history(cid)["messages"]
            saved = next(message for message in messages if message["id"] == receipt["id"])
            self.assertEqual(saved["content"], receipt["content"])
            self.assertEqual(saved["task_ids"], receipt["task_ids"])
            completed = [message for message in messages if message.get("task_status")]
            self.assertEqual(len(completed), 1)
            self.assertIn("Worker assignments completed: 2/2", completed[0]["content"])
            for identifier in receipt["task_ids"]:
                self.assertIn(identifier, completed[0]["content"])

    def test_both_workers_execute_real_claims_with_repo_evidence_and_reports(self):
        repo = self.repo()
        source = queue.enqueue(self.root, "conversation", "source", "Improve Web Bob", kind="coding")
        claim = queue.claim(self.root, "codex")
        queue.transition(self.root, source["id"], claim["claim_token"], "running", project="Web Bob", worktree=str(repo))
        for lane, task, kind in (("gemini", "Audit the whole repo", "audit"),
                                 ("minimax", "Write test cases for queue recovery", "test-writing")):
            with self.subTest(lane=lane):
                job = queue.enqueue(self.root, "conversation", lane, task, worker=lane, source_job_id=source["id"])
                self.assertEqual(job["kind"], kind)
                row = queue.claim(self.root, lane)
                def response(model, prompt, **kwargs):
                    self.assertEqual(model, lane)
                    self.assertEqual(kwargs["model_id"], MODELS[lane])
                    self.assertIn("FILE queue.py", prompt)
                    self.assertNotIn("fixture-must-not-be-sent", prompt)
                    self.assertNotIn("fixture-password-never-read", prompt)
                    self.assertNotIn("FILE linked.py", prompt)
                    current = queue.tasks(self.root)[job["id"]]
                    self.assertEqual(current["model"], MODELS[lane])
                    self.assertEqual(current["status"], "running")
                    return "queue.py: Add regression coverage for duplicate claims. Tests were not run.\n```diff\n+assert enqueue(job) == job\n```"
                with patch.object(api, "model_call", side_effect=response), \
                        patch.object(dispatch_worker, "prepare_task") as prepare, \
                        patch.object(dispatch_worker.draft_publish, "publish") as publish:
                    self.assertEqual(dispatch_worker.execute(job["id"], row["claim_token"]), 0)
                prepare.assert_not_called()
                publish.assert_not_called()
                result = queue.tasks(self.root)[job["id"]]
                self.assertEqual(result["status"], "succeeded")
                report = Path(result["result_path"])
                self.assertTrue(report.is_relative_to(self.core / "reviews"))
                self.assertIn("```diff", report.read_text())
                self.assertEqual((repo / "queue.py").read_text(), "def enqueue(job):\n    return job\n")
                self.assertIsNone(result["branch"])
                self.assertIsNone(result["worktree"])
                self.assertTrue(result["evidence"]["files"])

    def test_transport_loads_keys_uses_exact_models_and_search_without_secret_logs(self):
        (self.core / "keys.env").write_text("export GEMINI_API_KEY='gemini-fixture-key'\nMINIMAX_API_KEY=minimax-fixture-key\n")
        calls = []
        def transport(argv, **kwargs):
            config = Path(argv[argv.index("--config") + 1]).read_text()
            payload = json.loads(Path(argv[argv.index("--data-binary") + 1][1:]).read_text())
            self.assertNotIn("fixture-key", " ".join(argv))
            self.assertNotIn("?key=", config)
            if "generativelanguage" in config:
                self.assertIn("gemini-2.5-pro:generateContent", config)
                self.assertIn("x-goog-api-key: gemini-fixture-key", config)
                self.assertEqual(payload["tools"], [{"google_search": {}}])
                self.assertGreater(payload["generationConfig"]["thinkingConfig"]["thinkingBudget"], 0)
                result = dict(candidates=[dict(finishReason="STOP", content=dict(parts=[dict(text="Research answer with concrete evidence.")]),
                                              groundingMetadata=dict(groundingChunks=[dict(web=dict(uri="https://example.org/source"))]))],
                              usageMetadata=dict(promptTokenCount=100, candidatesTokenCount=200, thoughtsTokenCount=50))
            else:
                self.assertIn("https://api.minimax.io/v1/text/chatcompletion_v2", config)
                self.assertIn("Authorization: Bearer minimax-fixture-key", config)
                self.assertEqual(payload["model"], "MiniMax-M2.7")
                self.assertNotIn("tools", payload)
                result = dict(choices=[dict(finish_reason="stop", message=dict(content="Useful review with specific test cases."))],
                              usage=dict(prompt_tokens=100, completion_tokens=200))
            Path(argv[argv.index("-o") + 1]).write_text(json.dumps(result))
            calls.append(payload)
            return SimpleNamespace(stdout="200", stderr="", returncode=0)
        with patch.object(api, "CONDUCTOR", self.core), patch.dict(os.environ, {}, clear=True), \
                patch.object(api, "run", side_effect=transport), patch.object(api, "log") as log:
            research = lanes.ask("gemini", "Research queue designs", purpose="api-worker-research", locked=True)
            lanes.ask("minimax", "Review queue designs", purpose="api-worker", locked=True)
        self.assertIn("https://example.org/source", research)
        self.assertEqual(len(calls), 2)
        log.assert_not_called()
        for path in (self.core / "ledger").glob("*.jsonl"):
            self.assertNotIn("fixture-key", path.read_text())
        self.assertAlmostEqual(budget.totals("gemini")["spent_usd"], .035 + .000125 + .0025)

    def test_pro_reservation_and_search_charge_stop_before_http(self):
        with patch.object(budget, "GEMINI_CAP_USD", .04), patch.object(api, "CONDUCTOR", self.core), \
                patch.dict(os.environ, {"GEMINI_API_KEY": "offline-test-key"}), patch.object(api, "run") as transport:
            with self.assertRaises(budget.BudgetExceeded):
                api.model_call("gemini", "research", model_id=MODELS["gemini"], google_search=True)
        transport.assert_not_called()

    def test_snapshot_reports_truncation_and_never_opens_private_files(self):
        repo = self.repo()
        (repo / "queue.py").write_text("x" * 60000)
        real_open = Path.open
        def safe_open(path, *args, **kwargs):
            self.assertNotIn(path.name, ("keys.env", ".password", "linked.py"))
            return real_open(path, *args, **kwargs)
        with patch.object(Path, "open", safe_open):
            body, metadata = api_worker.evidence(repo, "gemini", "audit", lambda text: text)
        self.assertIn("queue.py", metadata["truncated"])
        self.assertIn("not proof of complete coverage", body)

    def test_snapshot_refuses_a_link_swapped_after_validation(self):
        repo = self.repo()
        reader = api_worker.read_source
        def swap(repo, name, limit):
            if name == "queue.py":
                (repo / name).unlink()
                (repo / name).symlink_to(repo / "webchat/.password")
            return reader(repo, name, limit)
        with patch.object(api_worker, "read_source", side_effect=swap):
            with self.assertRaisesRegex(RuntimeError, "could not be read"):
                api_worker.evidence(repo, "gemini", "audit", lambda text: text)

    def test_reports_redact_secrets_and_refuse_linked_output(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "private-api-test-value"}):
            path = api_worker.save_report(self.core, "job", "claim", "gemini", "Found private-api-test-value", dispatch_worker.redact)
        self.assertNotIn("private-api-test-value", path.read_text())
        other = self.root / "other"
        other.mkdir()
        linked = other / "reviews"
        linked.symlink_to(self.core / "reviews")
        with self.assertRaisesRegex(RuntimeError, "linked"):
            api_worker.save_report(other, "job", "claim", "gemini", "answer", dispatch_worker.redact)

    def test_no_grok_or_xai_transport_or_claims(self):
        for provider in ("grok", "xai"):
            with self.assertRaises(ValueError), patch.object(api, "run") as run:
                api.model_call(provider, "task")
            run.assert_not_called()
            with self.assertRaises(ValueError):
                queue.claim(self.root, provider)

    def test_legacy_api_worker_writes_report_without_worktree_or_publication(self):
        repo = self.repo()
        folder = self.root / "job"
        folder.mkdir()
        (folder / "PROMPT.txt").write_text("Audit the whole repo")
        state.job_event("legacy-api", "launched", job_dir=str(folder), repo=str(repo), engine="gemini", kind="non-coding")
        with patch.object(worker, "CONDUCTOR", self.core), patch.object(worker, "setup_record") as setup, \
                patch.object(worker, "ask", side_effect=["queue.py lacks duplicate job tests; add regression coverage.", '{"accepted":true,"reason":"Specific findings supplied"}']):
            self.assertEqual(worker.execute("legacy-api"), 0)
        setup.assert_not_called()
        result = state.jobs()["legacy-api"]
        self.assertTrue(result["verified"])
        self.assertTrue(Path(result["report_path"]).is_file())
