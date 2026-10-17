"""A release must reject weak replies, queued-only work, and wrong build identity."""
import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from deploy_replyq import main, style_errors, verify_executions
from task_dispatch import task_queue


class ReplyGateTests(unittest.TestCase):
    def test_style_rejects_original_failures_but_allows_fact_links(self):
        for reply in ("Okay, I'll focus on getting everything running.",
                      "Codex: job webchat-1234567890abcdef.\nlogs/review.log; last: raw text.",
                      "One. Two. Three. Four. Five.", ""):
            self.assertTrue(style_errors(reply), reply)
        self.assertFalse(style_errors("Codex pushed WebJam's draft at [abc1234](https://example.com/draft/webchat-1234567890abcdef)."))

    def test_queue_receipts_cannot_pass_as_execution(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            row = task_queue.enqueue(root, "conversation", "request", "Fix WebJam login", worker="codex", kind="coding")
            rows, started = verify_executions(root, [row["id"]])
            self.assertEqual(len(rows), 1)
            self.assertEqual(started, [])
            claim = task_queue.claim(root, "codex")
            task_queue.transition(root, row["id"], claim["claim_token"], "running")
            self.assertEqual(verify_executions(root, [row["id"]])[1], [])
            task_queue.transition(root, row["id"], claim["claim_token"], "executing")
            self.assertEqual(len(verify_executions(root, [row["id"]])[1]), 1)

    def test_wrong_live_version_restores_snapshot_and_verifies_old_sha(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ):
            root = Path(folder)
            candidate, old = root / "candidate", root / "old-code"
            for directory in (root / "conductor/state", root / "conductor/reviews", root / "conductor/webchat",
                              root / "rollbacks", candidate / "webchat/evidence", candidate / "reviews", old):
                directory.mkdir(parents=True, exist_ok=True)
            (root / "conductor/webchat/.password").write_text("private-test-password")
            (old / "webbob-build.json").write_text('{"sha":"dff84e3"}')
            for name in ("webchat", "dispatch"):
                (root / "conductor/state" / (name + "-code-root")).write_text(str(old))
            (candidate / "webchat/evidence/replyq-tests.json").write_text(json.dumps(dict(
                sha="candidate-sha", suite_exit=0, eval_exit=0, eval=dict(passed=33, total=33))))
            def command(argv):
                if argv[0] == "gh":
                    return json.dumps(dict(isDraft=True, state="OPEN", headRefOid="candidate-sha"))
                if "rev-parse" in argv:
                    return "candidate-sha"
                if "branch" in argv:
                    return "draft/webbob-replyq-1856"
                return ""
            versions = iter([dict(sha="dff84e3"), dict(sha="wrong-sha"), dict(sha="dff84e3")])
            client = MagicMock()
            client.url = "http://127.0.0.1:8787"
            client.call.side_effect = lambda route: next(versions) if route == "/api/version" else {}
            with patch("sys.argv", ["deploy_replyq.py", "--root", str(root), "--candidate", str(candidate)]), \
                    patch("deploy_replyq.run", side_effect=command), \
                    patch("deploy_replyq.Client", return_value=client), \
                    patch("deploy_replyq.latest_sessions", return_value=[]), \
                    patch("deploy_replyq.restart", return_value=dict(other_screens_unchanged=True)) as restart, \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(), 1)
            self.assertEqual(restart.call_count, 2)
            restored = restart.call_args.args[1]
            self.assertEqual(set(restored), {"webchat", "dispatch"})
            self.assertIn("rollbacks/webbob-replyq-", str(restored["webchat"]))
            self.assertEqual((restored["webchat"] / "webbob-build.json").read_text(), '{"sha":"dff84e3"}')
            report = (root / "conductor/reviews/WEBBOB-REPLYQ-DEPLOYMENT-0927.json").read_text()
            self.assertTrue(json.loads(report)["rolled_back"])
            self.assertNotIn("private-test-password", report)
            self.assertTrue((candidate / "reviews/WEBBOB-REPLYQ-DEPLOY-FAIL-0927.md").exists())
