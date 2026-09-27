"""Exercise deployed code with a different, deliberately stale data directory."""
import json
import threading
import uuid
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from app import Server
from build_info import BUILD, STATIC, load_build, VERSION_QUESTION
from live_redeploy_check import Client
from test_webchat import Fixture
from live_status_snapshot import _screen_sessions


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
