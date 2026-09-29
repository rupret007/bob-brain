"""Local Git/HTTP/sandbox regression checks; no model calls or live services."""
import copy
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


class SessionAndProofTests(unittest.TestCase):
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
