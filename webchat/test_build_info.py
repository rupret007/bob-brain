"""Exercise deployed code with a different, deliberately stale data directory."""
import json
import os
import subprocess
import tempfile
import threading
import unittest
import uuid
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from app import Server
import build_info
from build_info import BUILD, CODE_ROOT, STATIC, git_checkout_root, load_build, VERSION_QUESTION
from live_redeploy_check import Client
from test_webchat import Fixture
from live_status_snapshot import _screen_sessions


class CheckoutIdentity(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.repo = self.root / "repo"
        module = self.repo / "webchat/build_info.py"
        module.parent.mkdir(parents=True)
        module.write_text("# Tracked fixture identity module.\n")
        self.git("init", "-b", "main")
        self.git("add", ".")
        self.git("-c", "user.name=Test", "-c", "user.email=test@localhost", "commit", "-m", "Fixture")

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), *args], text=True,
                                       stderr=subprocess.STDOUT).strip()

    def test_running_identity_module_is_tracked_in_this_checkout(self):
        running = Path(__file__).resolve().parents[1]
        self.assertEqual(Path(build_info.__file__).resolve(), running / "webchat/build_info.py")
        self.assertEqual(CODE_ROOT, running)
        actual = Path(subprocess.check_output(["git", "-C", str(running), "rev-parse", "--show-toplevel"],
                                             text=True).strip()).resolve()
        self.assertEqual(git_checkout_root(), actual)
        self.assertEqual(actual, running)
        self.assertEqual(subprocess.check_output(["git", "-C", str(running), "cat-file", "-t",
                                                  "HEAD:webchat/build_info.py"], text=True).strip(), "blob")

    def test_normal_and_linked_worktrees_have_real_git_identity(self):
        self.assertTrue((self.repo / ".git").is_dir())
        self.assertEqual(git_checkout_root(self.repo), self.repo)
        linked = self.root / "linked"
        self.git("worktree", "add", "--detach", str(linked), "HEAD")
        self.assertTrue((linked / ".git").is_file())
        self.assertEqual(git_checkout_root(linked), linked)
        self.assertEqual(load_build(linked)["sha"], self.git("rev-parse", "HEAD"))

    def test_nested_code_must_be_committed_to_use_the_parent_git_identity(self):
        nested = self.repo / "apps/webbob"
        module = nested / "webchat/build_info.py"
        module.parent.mkdir(parents=True)
        module.write_text("# Nested identity fixture.\n")
        self.assertIsNone(git_checkout_root(nested))
        self.assertEqual(load_build(nested)["sha"], "unknown")
        self.git("add", ".")
        self.assertIsNone(git_checkout_root(nested))
        self.git("-c", "user.name=Test", "-c", "user.email=test@localhost", "commit", "-m", "Nested code")
        self.assertEqual(git_checkout_root(nested), self.repo)
        self.assertEqual(load_build(nested)["sha"], self.git("rev-parse", "HEAD"))

    def test_git_failures_return_no_checkout(self):
        for error in (OSError("git unavailable"), subprocess.TimeoutExpired("git", 5),
                      subprocess.CalledProcessError(128, "git")):
            with self.subTest(error=type(error).__name__), patch("build_info.subprocess.check_output", side_effect=error):
                self.assertIsNone(git_checkout_root(self.repo))

    def test_inherited_git_overrides_do_not_choose_the_repository(self):
        with patch.dict(os.environ, {"GIT_DIR": str(self.root / "wrong-git"), "GIT_WORK_TREE": str(self.root)}):
            self.assertEqual(git_checkout_root(self.repo), self.repo)

    def test_deleted_or_linked_identity_module_cannot_supply_context(self):
        module = self.repo / "webchat/build_info.py"
        module.unlink()
        self.assertIsNone(git_checkout_root(self.repo))
        other = self.root / "external.py"
        other.write_text("# Not the running checkout's module.\n")
        module.symlink_to(other)
        self.assertIsNone(git_checkout_root(self.repo))


class ReleaseIdentity(Fixture):
    def test_single_screen_and_temporarily_incomplete_screen_listing(self):
        complete = SimpleNamespace(stdout="123.lane-only (Detached)\n1 Socket in /tmp/screens.\n", stderr="")
        partial = SimpleNamespace(stdout="123.lane-only (Unreachable)\n1 Socket in /tmp/screens.\n", stderr="")
        with patch("live_status_snapshot.subprocess.run", side_effect=[partial, complete]):
            self.assertEqual(_screen_sessions(self.root), {"lane-only": "123.lane-only"})
        with patch("live_status_snapshot.subprocess.run", return_value=partial):
            self.assertIsNone(_screen_sessions(self.root))

    def test_assets_and_header_come_from_code_not_persistent_data(self):
        stale = self.folder / "static"
        stale.mkdir()
        for name in ("app.js", "style.css", "index.html", "login.html"):
            (stale / name).write_text("OLD UI")
        server = Server(("127.0.0.1", 0), self.chat)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        client = Client(f"http://127.0.0.1:{server.server_port}", self.folder / ".password")
        try:
            with patch("app.HERE", self.folder):
                self.assertEqual(client.call("/api/version"), BUILD)
                client.login()
                with client.opener.open(client.url + "/") as response:
                    index = response.read().decode()
                    self.assertIn("no-cache", response.headers["Cache-Control"])
                    self.assertIn("no-store", response.headers["Cache-Control"])
                for name in ("app.js", "style.css", "manifest.webmanifest"):
                    url = "/" + name + "?v=" + BUILD["short_sha"]
                    self.assertIn(url, index)
                    with client.opener.open(client.url + url) as response:
                        self.assertEqual(response.read(), (STATIC / name).read_bytes())
                self.assertIn('id="build-info"', index)
                self.assertIn(BUILD["built_at"], index)
                self.assertNotIn("__WEBBOB_", index)
                self.assertNotIn("OLD UI", index)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(3)

    def test_version_reply_is_only_own_sha_despite_other_project_history_and_hold(self):
        (self.root / "BOB-STATE.md").write_text("WebJam build deadbee. Web Bob is old1234.")
        self.chat.submit(self.identifier, "hold off", str(uuid.uuid4()))
        for prompt in ("what version/build are you", "What build are you running?", "What is your build number?",
                       "What version are you?", "What SHA are you running?"):
            reply = self.chat.submit(self.identifier, prompt, str(uuid.uuid4()))
            self.assertEqual(reply["messages"][-1]["content"], BUILD["short_sha"])
        self.assertFalse(self.fake.calls)
        self.assertFalse(VERSION_QUESTION.search("What version is WebJam?"))

    def test_archive_identity_uses_release_manifest_and_never_parent_git(self):
        self.assertEqual(load_build(self.root)["sha"], "unknown")
        manifest = dict(sha="a" * 40, built_at="2026-09-27T22:00:00+00:00")
        (self.root / "webbob-build.json").write_text(json.dumps(manifest))
        self.assertEqual(load_build(self.root)["short_sha"], "a" * 7)
        self.assertEqual(load_build(self.root)["built_at"], manifest["built_at"])
