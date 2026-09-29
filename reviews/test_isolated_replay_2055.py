"""Local Git/HTTP/sandbox regression checks; no model calls or live services."""
import copy
import contextlib
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import isolated_replay_2055 as replay
import draft_publish


class LocalTransportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir="/private/tmp")
        self.root = Path(self.temporary.name).resolve()
        self.private = self.root / "private"
        self.private.mkdir()
        (self.private / "remotes").mkdir()
        (self.private / "workspaces").mkdir()
        self.identifier = "webchat-" + "a" * 32
        self.branch = "draft/" + self.identifier
        self.repo = self.private / "workspaces" / self.identifier
        self.bare = self.private / "remotes/0.git"
        replay.git(self.private, "init", "-b", self.branch, str(self.repo))
        replay.git(self.private, "init", "--bare", str(self.bare))
        (self.repo / "result.txt").write_text("initial\n")
        replay.git(self.repo, "add", ".")
        replay.git(self.repo, "-c", "user.name=Fixture", "-c", "user.email=fixture@localhost", "commit", "-m", "Initial")
        self.base = replay.git(self.repo, "rev-parse", "HEAD")
        (self.repo / "result.txt").write_text("accepted change\n")
        replay.git(self.repo, "add", ".")
        replay.git(self.repo, "-c", "user.name=Fixture", "-c", "user.email=fixture@localhost", "commit", "-m", "Bounded change")
        self.sha = replay.git(self.repo, "rev-parse", "HEAD")
        self.manifest = dict(private_root=str(self.private), candidate=str(replay.CODE), real_root=str(self.root),
            projects={"WebJam": dict(repo=str(self.repo), remote="isolated2055/project0")},
            sources={"WebJam": dict(path=str(self.root / "original"), before=dict(common=str(self.root / "original/.git")),
                                      remote=str(self.bare))})
        self.transport = replay.LocalPublication(self.manifest)
        self.folder = self.private / "conductor/state/task-runs" / self.identifier
        self.folder.mkdir(parents=True)
        self.row = dict(id=self.identifier, kind="coding", publish_project="WebJam", draft_pr=True)

    def tearDown(self):
        self.temporary.cleanup()

    def publish(self):
        with patch.object(draft_publish, "run", side_effect=self.transport.run):
            return draft_publish.publish(self.row, self.repo, self.folder, self.manifest["projects"])

    def test_actual_guard_pushes_exact_local_ref_and_creates_only_local_draft(self):
        hook = self.repo / ".git/hooks/pre-push"
        hook.write_text("#!/bin/sh\nexit 1\n")
        hook.chmod(0o700)
        publication = self.publish()
        self.assertEqual(replay.git(self.bare, "rev-parse", "refs/heads/" + self.branch), self.sha)
        self.assertEqual(replay.git(self.bare, "for-each-ref", "--format=%(refname)"), "refs/heads/" + self.branch)
        self.assertTrue(publication["pr_url"].startswith("file://"))
        self.assertEqual(hook.read_text(), "#!/bin/sh\nexit 1\n")
        path = self.transport.receipt_path("isolated2055/project0", self.branch)
        receipt = json.loads(path.read_text())
        self.assertTrue(receipt["isDraft"])
        self.assertEqual(receipt["headRefOid"], self.sha)
        self.assertEqual(receipt["transport"], "local-draft-pr-adapter")
        self.assertEqual(self.publish()["pr_url"], publication["pr_url"])

    def test_existing_non_draft_or_wrong_sha_is_rejected_without_repair(self):
        self.publish()
        path = self.transport.receipt_path("isolated2055/project0", self.branch)
        original = json.loads(path.read_text())
        for updates in (dict(isDraft=False), dict(headRefOid="1" * 40)):
            path.write_text(json.dumps(dict(original, **updates)))
            with self.subTest(updates=updates), self.assertRaisesRegex(RuntimeError, "SHA or draft state"):
                self.publish()
            self.assertEqual(json.loads(path.read_text()), dict(original, **updates))

    def test_dirty_checkout_and_wrong_branch_keep_original_publication_gate(self):
        (self.repo / "result.txt").write_text("uncommitted\n")
        with self.assertRaisesRegex(RuntimeError, "assigned, clean branch"):
            self.publish()
        self.assertEqual(replay.git(self.bare, "for-each-ref", "--format=%(refname)"), "")

    def test_transport_rejects_external_destinations_force_and_unsupported_gh(self):
        rejected = (["git", "push", "https://github.com/rupret007/WebJam.git", self.sha + ":refs/heads/" + self.branch],
                    ["git", "-C", str(self.repo), "push", "--force", "https://github.com/isolated2055/project0.git", self.sha + ":refs/heads/" + self.branch],
                    ["gh", "pr", "merge", "--repo", "isolated2055/project0", "--head", self.branch],
                    ["git", "push", str(self.bare), "main"],
                    ["curl", "https://github.com"])
        for argv in rejected:
            with self.subTest(argv=argv), self.assertRaises(RuntimeError):
                self.transport.run(argv)

    def test_transport_rejects_checkout_outside_private_workspaces(self):
        with self.assertRaisesRegex(RuntimeError, "checkout escaped"):
            self.transport.run(["git", "-C", str(self.root), "push", "https://github.com/isolated2055/project0.git",
                                self.sha + ":refs/heads/" + self.branch])

    def test_source_state_reads_do_not_refresh_index_and_sandbox_denies_originals(self):
        before = replay.source_state(self.repo)
        self.assertEqual(replay.source_state(self.repo), before)
        policy = replay.extra_policy(self.manifest)
        for path in (self.root / "original", self.root / "original/.git", self.private / "remotes", self.private / "sources"):
            self.assertIn(json.dumps(str(path)), policy)

    def test_artifact_hash_and_private_boundary_are_enforced(self):
        path = self.private / "result.json"
        path.write_text("{}")
        receipt = replay.artifact(path)
        self.assertEqual(replay.checked_artifact(receipt, self.private), path)
        path.write_text("[]")
        with self.assertRaisesRegex(RuntimeError, "artifact changed"):
            replay.checked_artifact(receipt, self.private)
        external = self.root / "outside.json"
        external.write_text("{}")
        with self.assertRaisesRegex(RuntimeError, "escapes"):
            replay.checked_artifact(replay.artifact(external), self.private)

    def test_committed_result_verifier_rejects_tampered_acceptance_hash_and_remote(self):
        # Synthetic UNIT fixture only: real commits/local push, no claim of a
        # model run or private release proof is created by this test.
        publication = self.publish()
        publication.update(transport=replay.SCOPE, url=self.bare.as_uri())
        answer = "Changed result.txt and committed " + self.sha + ". Local fixture test: 1 passed, exit 0."
        result_hash = hashlib.sha256(answer.encode()).hexdigest()
        coding = dict(sha=self.sha, base_sha=self.base, changed_paths=["result.txt"],
                      diff=replay.git(self.repo, "diff", "--no-ext-diff", self.base, self.sha), validation=None)
        self.manifest.update(shared_meter=str(self.root / "conductor/ledger"), shared_locks=str(self.root / "conductor/locks"))
        runtime = dict(imports={name: dict(path=str(replay.CODE / path), sha256=replay.digest(replay.CODE / path))
                                for name, path in replay.WORKER_IMPORTS.items()},
                       shared_root=str(self.root), shared_meter=self.manifest["shared_meter"],
                       shared_locks=self.manifest["shared_locks"],
                       model_invocations=[dict(executable="codex", model="OpenAI Codex CLI")])
        runtime["cli_outputs"] = [replay.capture_cli_output(self.folder,
            result=subprocess.CompletedProcess([], 0, "synthetic unit fixture", ""))]
        local = dict(job_id=self.identifier, scope=replay.SCOPE, publication=publication,
                     local_remote=str(self.bare), actual_ref="refs/heads/" + self.branch, actual_sha=self.sha,
                     github_receipt=False, draft_pr=replay.artifact(self.transport.receipt_path("isolated2055/project0", self.branch)))
        artifacts = {}
        for name, value in (("coding", coding), ("runtime", runtime), ("publication", local)):
            path = self.folder / (name + ".json")
            path.write_text(json.dumps(value))
            artifacts[name] = replay.artifact(path)
        for name, value in (("result", answer), ("prompt", "Improve WebJam")):
            path = self.folder / (name + ".md")
            path.write_text(value)
            artifacts[name] = replay.artifact(path)
        row = dict(self.row, status="succeeded", execution_started_at=1, worker="codex", requested_worker="codex",
                   project="WebJam", prompt="Improve WebJam", result=answer, result_sha256=result_hash,
                   worktree=str(self.repo), branch=self.branch, publication=publication,
                   acceptance=dict(accepted=True, result_sha256=result_hash, coding_evidence=coding))
        replay.verify_job(row, self.manifest, artifacts)
        for changed in (dict(status="running"), dict(result_sha256="0" * 64),
                        dict(acceptance=dict(row["acceptance"], accepted=False))):
            with self.subTest(changed=changed), self.assertRaises(RuntimeError):
                replay.verify_job(dict(row, **changed), self.manifest, artifacts)
        replay.git(self.bare, "update-ref", "refs/heads/" + self.branch, self.base)
        with self.assertRaisesRegex(RuntimeError, "ref proof mismatch"):
            replay.verify_job(row, self.manifest, artifacts)


class LaneReadinessTests(unittest.TestCase):
    def test_cooldown_never_claims_or_consumes_attempts_and_does_not_change_cooldown(self):
        import lanes
        import budget
        from task_dispatch import task_queue
        with tempfile.TemporaryDirectory(dir="/private/tmp") as folder:
            root = Path(folder)
            shared, private = root / "shared/conductor", root / "private"
            shared.mkdir(parents=True)
            path = shared / "lane-cooldowns.json"
            path.write_text(json.dumps(dict(cursor=dict(retry_at=1000, detail="actual provider rate limit"))))
            before = path.read_bytes()
            row = task_queue.enqueue(private, "test", "request", "Improve WebJam", worker="cursor", kind="coding")
            with patch.object(lanes, "CONDUCTOR", shared), patch.object(budget, "check") as meter, \
                 patch.object(task_queue, "claim", wraps=task_queue.claim) as claim:
                for now in (100, 200, 999):
                    job, readiness = replay.claim_when_ready(private, "cursor", now=now)
                    self.assertIsNone(job)
                    self.assertEqual(readiness, dict(ready=False, reason="shared cooldown", retry_at=1000))
                claim.assert_not_called()
                meter.assert_not_called()
            saved = task_queue.tasks(private)[row["id"]]
            self.assertEqual(saved["attempts"], 0)
            self.assertEqual(saved["status"], "queued")
            self.assertEqual(path.read_bytes(), before)

    def test_budget_or_shared_lease_prevents_claim(self):
        import lanes
        import budget
        import state
        from task_dispatch import task_queue
        with tempfile.TemporaryDirectory(dir="/private/tmp") as folder:
            for reason in ("budget", "lease"):
                with self.subTest(reason=reason), patch.object(lanes, "CONDUCTOR", Path(folder) / "conductor"), \
                     patch.object(budget, "check", side_effect=budget.BudgetExceeded("synthetic") if reason == "budget" else None,
                                  return_value=dict(tier="normal")), \
                     patch.object(state, "jobs", return_value={}), \
                     patch.object(task_queue, "tasks", return_value={}), \
                     patch.object(task_queue, "claim") as claim, \
                     patch.object(lanes, "slot", side_effect=BlockingIOError("synthetic held lease")):
                    row, readiness = replay.claim_when_ready(Path(folder) / "private", "cursor")
                    self.assertIsNone(row)
                    self.assertFalse(readiness["ready"])
                    self.assertIn(reason, readiness["reason"])
                    claim.assert_not_called()

    def test_worker_cooldown_race_uses_real_busy_transition_and_refunds_attempt(self):
        import dispatch_worker
        from task_dispatch import task_queue
        with tempfile.TemporaryDirectory(dir="/private/tmp") as folder:
            private = Path(folder)
            row = task_queue.enqueue(private, "test", "request", "Improve WebJam", worker="cursor", kind="coding")
            claim = task_queue.claim(private, "cursor", identifier=row["id"])
            self.assertEqual(claim["attempts"], 1)
            with patch.object(dispatch_worker, "ROOT", private), \
                 patch.object(dispatch_worker, "lock", side_effect=lambda *a, **k: contextlib.nullcontext()), \
                 patch.object(dispatch_worker, "slot", side_effect=lambda lane: replay.ready_worker_slot(lane, lambda lane: contextlib.nullcontext())), \
                 patch.object(replay, "lane_availability", return_value=dict(ready=False, reason="shared cooldown")), \
                 patch.object(dispatch_worker, "ask") as provider:
                self.assertEqual(dispatch_worker.execute(row["id"], claim["claim_token"]), 0)
                provider.assert_not_called()
            saved = task_queue.tasks(private)[row["id"]]
            self.assertEqual(saved["status"], "queued")
            self.assertEqual(saved["attempts"], 0)
            self.assertFalse(saved.get("execution_started_at"))

    def test_cli_diagnostics_are_bounded_redacted_and_immutable(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as folder:
            result = subprocess.CompletedProcess([], 1, "credential-value" + "x" * 50000,
                                                 "provider error credential-value")
            receipt = replay.capture_cli_output(Path(folder), result=result,
                                               redact=lambda text: text.replace("credential-value", "[removed]"))
            path = replay.checked_artifact(receipt, Path(folder))
            self.assertNotIn("credential-value", path.read_text())
            saved = json.loads(path.read_text())
            self.assertEqual(saved["exit"], 1)
            self.assertTrue(saved["stdout"]["truncated"])
            self.assertEqual(len(saved["stdout"]["tail"].encode()), 32768)
            self.assertEqual(saved["stdout"]["sha256"], hashlib.sha256(("[removed]" + "x" * 50000).encode()).hexdigest())
            second = replay.capture_cli_output(Path(folder), result=result, redact=lambda text: "redacted")
            self.assertNotEqual(receipt["path"], second["path"])
            self.assertEqual(path.read_bytes(), Path(receipt["path"]).read_bytes())


class SessionAndProofTests(unittest.TestCase):
    def test_private_prompt_context_keeps_real_provider_transport_and_meter_root(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as folder:
            real, private = Path(folder) / "real", Path(folder) / "private"
            for root, text in ((real, "production_context_must_not_leak"), (private, "private_context_expected")):
                state = root / "conductor/state"
                state.mkdir(parents=True)
                (state / "NOW.md").write_text(text)
            calls = []
            def transport(argv, **kwargs):
                calls.append((argv, kwargs))
                return 0, "<bob-webchat-reply>Hi Jeff!</bob-webchat-reply>", ""
            providers = replay.private_context_providers(real, private, runner=transport)
            try:
                self.assertEqual(providers.root, real)
                self.assertEqual(providers.context_root("private-conversation"), private)
                context = json.dumps(providers.snapshot(lite=True, conversation_id="private-conversation"))
                self.assertIn("private_context_expected", context)
                self.assertNotIn("production_context_must_not_leak", context)
                answer, _ = providers.call("gemini", "Hi", None, threading.Event())
                self.assertEqual(answer, "Hi Jeff!")
                self.assertEqual(calls[0][1]["env"]["BOB_ROOT"], str(real))
                self.assertEqual(calls[0][1]["cwd"], real)
                self.assertEqual(providers.circuit.path.parent, real / "conductor/webchat/sessions")
            finally:
                providers.close()

    def test_ten_original_messages_over_private_http_create_six_real_queue_rows(self):
        from app import Chat, Server
        from live_redeploy_check import Client
        from integration_rubric import check_reply
        from live_status_snapshot import build_live_status_snapshot
        from task_dispatch import task_queue
        class NoModels:
            def health(self, conversation_id=None):
                return dict(providers={}, order=[], fast_order=[])
            def reply(self, conversation, *args):
                prompt = next(m["content"] for m in reversed(conversation["messages"]) if m["role"] == "user")
                if prompt != "Hi":
                    raise AssertionError("Routing/status must not call model generation")
                # Unit-test greeting stub only. The actual harness uses the
                # real metered Providers implementation with no answer stub.
                return dict(content="Hi Jeff!", provider="gemini", attempts=[])
        with tempfile.TemporaryDirectory(dir="/private/tmp") as folder:
            root = Path(folder)
            chat = Chat(root / "conductor/webchat", root, NoModels())
            server = Server(("127.0.0.1", 0), chat)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            client = Client("http://127.0.0.1:" + str(server.server_port), chat.folder / ".password")
            try:
                client.login()
                turns = 0
                for source in replay.private_sessions():
                    cid = client.new()
                    for exchange in source["exchanges"]:
                        before = build_live_status_snapshot(root)
                        started = time.time()
                        _, answer = client.submit(cid, exchange["message"])
                        errors = check_reply(answer, exchange, cid, started, before,
                                             build_live_status_snapshot(root), task_queue.tasks(root))
                        self.assertEqual(errors, [], exchange["message"])
                        turns += 1
                rows = task_queue.tasks(root)
                self.assertEqual(turns, 10)
                self.assertEqual(len(rows), 6)
                self.assertEqual({r["status"] for r in rows.values()}, {"queued"})
                self.assertEqual({r["id"] for r in client.call("/api/jobs")["dispatch"]}, set(rows))
            finally:
                server.shutdown()
                server.server_close()
                chat.close()

    def test_cursor_uses_verified_openai_model_without_account_default(self):
        argv = replay.explicit_cursor_model(["/Users/example/.local/bin/cursor-agent", "-p", "prompt"])
        self.assertEqual(argv[1:3], ["--model", "gpt-5.6-sol-high"])
        with self.assertRaisesRegex(RuntimeError, "model override"):
            replay.explicit_cursor_model(["cursor-agent", "--model", "auto", "-p", "prompt"])
        self.assertEqual(replay.explicit_cursor_model(["codex", "exec", "prompt"]), ["codex", "exec", "prompt"])

    def test_exact_original_ten_turn_selection(self):
        from integration_rubric import sessions
        source = sessions()
        selected = replay.private_sessions(source)
        self.assertEqual(selected, source[1:])
        self.assertEqual(sum(len(s["exchanges"]) for s in selected), 10)
        self.assertEqual([x["message"] for s in selected for x in s["exchanges"] if x["expected"].startswith("projects")],
                         [source[1]["exchanges"][5]["message"], "push WebJam and AdoptIQ"])
        selected[0]["exchanges"].pop()
        self.assertEqual(len(source[1]["exchanges"]), 9)
        with self.assertRaises(RuntimeError):
            replay.private_sessions(selected)

    def test_self_asserted_success_without_candidate_identity_cannot_pass(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as folder:
            path = Path(folder) / "proof.json"
            path.write_text(json.dumps(dict(scope=replay.SCOPE, all_pass=True, sha="1" * 40,
                                            candidate=str(replay.CODE))))
            with patch.object(replay, "git", side_effect=lambda repo, *args: "2" * 40 if "rev-parse" in args else ""):
                with self.assertRaisesRegex(RuntimeError, "SHA mismatch"):
                    replay.verify_proof(path, replay.CODE, [])

    def test_failed_proof_cannot_pass(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as folder:
            path = Path(folder) / "proof.json"
            path.write_text(json.dumps(dict(scope=replay.SCOPE, all_pass=False)))
            with self.assertRaisesRegex(RuntimeError, "did not pass"):
                replay.verify_proof(path, replay.CODE, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
