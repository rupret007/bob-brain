"""Exercise the server's exact-ref push against an isolated bare Git remote."""
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import command
import draft_publish


class DraftPublication(unittest.TestCase):
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
