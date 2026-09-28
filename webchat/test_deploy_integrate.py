"""Integration gate fails closed and restores the previous release."""
import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from deploy_integrate import main
from integration_rubric import check_reply, style_errors, sessions
from task_dispatch import task_queue


class IntegrationGate(unittest.TestCase):
    def test_rubric_rejects_all_failed_deployment_promises(self):
        for text in ("I'll make sure they're utilized.", "The system is actively adding work for them.",
                     "I'll focus on getting everything running.", "All LLMs are healthy and ready."):
            self.assertTrue(style_errors(text), text)

    def test_rollback_fences_only_replay_claims_without_deleting_receipts(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            replay = task_queue.enqueue(root, "replay", "request", "audit Web Bob", worker="gemini", kind="audit")
            other = task_queue.enqueue(root, "jeff", "other-request", "audit WebJam", worker="gemini", kind="audit")
            waiting = task_queue.enqueue(root, "replay", "waiting", "Improve WebJam", worker="codex", kind="coding")
            claimed = task_queue.claim(root, "gemini", identifier=replay["id"])
            task_queue.transition(root, replay["id"], claimed["claim_token"], "running")
            cancelled = task_queue.cancel_replay(root, {"replay"}, "Release rollback")
            self.assertEqual({row["id"] for row in cancelled}, {replay["id"], waiting["id"]})
            self.assertIsNone(task_queue.tasks(root)[waiting["id"]]["claimed_at"])
            self.assertIsNone(task_queue.tasks(root)[waiting["id"]]["started_at"])
            self.assertFalse(task_queue.transition(root, replay["id"], claimed["claim_token"], "succeeded", result="too late"))
            self.assertEqual(task_queue.tasks(root)[other["id"]]["status"], "queued")
            self.assertEqual(task_queue.tasks(root)[replay["id"]]["created_at"], replay["created_at"])

    def test_wrong_live_version_rolls_back_local_and_public_endpoints(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ):
            root = Path(folder)
            candidate, old = root / "candidate", root / "old-code"
            for directory in (root / "conductor/state", root / "conductor/reviews", root / "conductor/webchat",
                              root / "rollbacks", candidate / "webchat/evidence", old):
                directory.mkdir(parents=True, exist_ok=True)
            (root / "conductor/webchat/.password").write_text("private-test-password")
            (root / "conductor/webchat/.public-origin").write_text("https://public.example")
            (old / "webbob-build.json").write_text('{"sha":"dff84e3"}')
            for name in ("webchat", "dispatch"):
                (root / "conductor/state" / (name + "-code-root")).write_text(str(old))
            (candidate / "webchat/evidence/integrate-tests.json").write_text(json.dumps(dict(
                sha="candidate-sha", suite_exit=0, eval_exit=0, eval=dict(passed=56, total=56))))
            def command(argv):
                if argv[0] == "gh":
                    return json.dumps(dict(isDraft=True, state="OPEN", headRefOid="candidate-sha", baseRefName="draft/webbob-clean-0927"))
                if "rev-parse" in argv: return "candidate-sha"
                if "branch" in argv: return "draft/webbob-integrate-2057"
                return ""
            versions = iter([dict(sha="dff84e3"), dict(sha="wrong-sha"), dict(sha="dff84e3"), dict(sha="dff84e3")])
            client = MagicMock()
            client.url = "http://127.0.0.1:8787"
            client.call.side_effect = lambda route: next(versions) if route == "/api/version" else {}
            with patch("sys.argv", ["deploy_integrate.py", "--root", str(root), "--candidate", str(candidate), "--draft-pr", "https://example.org/pr"]), \
                    patch("deploy_integrate.run", side_effect=command), \
                    patch("deploy_integrate.Client", return_value=client), \
                    patch("deploy_integrate.latest_sessions", return_value=[]), \
                    patch("deploy_integrate.restart", return_value=dict(other_screens_unchanged=True)) as restart, \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(), 1)
            self.assertEqual(restart.call_count, 2)
            report = (root / "conductor/reviews/WEBBOB-INTEGRATE-DEPLOYMENT-0927-attempt1.json").read_text()
            result = json.loads(report)
            self.assertTrue(result["rolled_back"])
            self.assertEqual(result["restored_public_version"]["sha"], "dff84e3")
            self.assertNotIn("private-test-password", report)
            self.assertEqual(set(restart.call_args.args[1]), {"webchat", "dispatch"})
