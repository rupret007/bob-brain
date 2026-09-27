"""Exercise the server's exact-ref push against an isolated bare Git remote."""
import subprocess
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import command
import draft_publish


class DraftPublication(unittest.TestCase):
    def test_project_pr_is_created_once_as_draft_and_never_undrafted(self):
        sha, branch = "a" * 40, "draft/webchat-" + "a" * 32
        record = dict(url="https://github.com/owner/repo/pull/1", isDraft=True, headRefOid=sha)
        row = dict(id=branch.removeprefix("draft/"), publish_project="Fantasy Football")
        calls, prs = [], []
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            def fake(argv, **kwargs):
                calls.append(argv)
                if argv[1:3] == ["pr", "create"]:
                    self.assertIn("--draft", argv)
                    body = Path(argv[argv.index("--body-file") + 1]).read_text()
                    self.assertIn("\n\n", body)
                    self.assertIn(row["id"], body)
                    prs.append(record)
                return subprocess.CompletedProcess(argv, 0, json.dumps(prs), "")
            with patch.object(draft_publish, "run", side_effect=fake):
                for _ in range(2):
                    self.assertEqual(draft_publish.ensure_draft_pr(row, folder, folder, "owner/repo", branch, sha), record["url"])
                record["isDraft"] = False
                with self.assertRaisesRegex(RuntimeError, "remain a draft"):
                    draft_publish.ensure_draft_pr(row, folder, folder, "owner/repo", branch, sha)
            self.assertEqual(sum(call[1:3] == ["pr", "create"] for call in calls), 1)
            self.assertTrue(all(call[2] in ("list", "create") for call in calls))

    def test_real_push_verifies_remote_sha_and_rejects_wrong_branch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo, remote = root / "task", root / "remote.git"
            row = dict(id="webchat-" + "a" * 32, kind="coding", publish_project="WebJam")
            branch = "draft/" + row["id"]
            def git(*args):
                return subprocess.check_output(["git", *map(str, args)], text=True, stderr=subprocess.DEVNULL).strip()
            git("init", "-b", branch, repo)
            git("init", "--bare", remote)
            (repo / "fix.txt").write_text("verified draft work\n")
            git("-C", repo, "add", "fix.txt")
            git("-C", repo, "-c", "user.name=Test", "-c", "user.email=test@localhost", "commit", "-m", "Fix")
            sha = git("-C", repo, "rev-parse", "HEAD")
            hook = repo / ".git/hooks/pre-push"
            hook.write_text("#!/bin/sh\nexit 1\n")
            hook.chmod(0o700)
            requests = []
            def local_transport(argv, **kwargs):
                requests.append(argv)
                return command.run([str(remote) if arg == "https://github.com/owner/webjam.git" else arg for arg in argv], **kwargs)
            projects = dict(WebJam=dict(remote="owner/webjam"))
            with patch.object(draft_publish, "run", side_effect=local_transport):
                result = draft_publish.publish(row, repo, root / "job", projects)
            self.assertEqual(result["sha"], sha)
            self.assertEqual(git("--git-dir", remote, "rev-parse", "refs/heads/" + branch), sha)
            self.assertEqual(git("--git-dir", remote, "for-each-ref", "--format=%(refname)"), "refs/heads/" + branch)
            self.assertEqual(hook.read_text(), "#!/bin/sh\nexit 1\n")
            self.assertIn(sha + ":refs/heads/" + branch, requests[0])
            self.assertNotIn("--force", requests[0])
            git("-C", repo, "checkout", "-b", "main")
            with patch.object(draft_publish, "run") as network:
                with self.assertRaisesRegex(RuntimeError, "assigned, clean branch"):
                    draft_publish.publish(row, repo, root / "job", projects)
                network.assert_not_called()

    def test_no_saved_authorization_never_publishes(self):
        with patch.object(draft_publish, "run") as network:
            self.assertIsNone(draft_publish.publish({}, None, None, {}))
            network.assert_not_called()
