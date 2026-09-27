"""End-to-end texting: HTTP server plus optional browser proof (mock Andrea/BlueBubbles only)."""
import json
import shutil
import subprocess
import tempfile
import threading
import unittest
import uuid
from pathlib import Path

import http.client

from app import Chat, Server
from texting import Andrea, BlueBubbles, Texting
from texting_fixture import MockMessaging, OfflineProviders

CODE = Path(__file__).resolve().parent
ROOT = CODE.parent


class TextingE2ETest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.mock = MockMessaging(self.root)
        self.mock.enable_web_bob_send = True
        self.providers = OfflineProviders()
        self.texting = Texting(BlueBubbles(self.mock.config_db), Andrea(self.mock.base, self.mock.token))
        self.chat = Chat(self.root / "conductor/webchat", self.root, self.providers, texting=self.texting)
        self.identifier = self.chat.new_conversation()["id"]
        token = self.chat.login(self.chat.password)
        self.cookie = "bob_session=" + token
        self.session = self.chat.authenticate(self.cookie)
        self.actor = self.session["digest"]
        self.server = Server(("127.0.0.1", 0), self.chat)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.origin = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(3)
        self.chat.close()
        self.mock.close()
        self.assertEqual(self.mock.unexpected_writes, [])
        self.temp.cleanup()

    def post(self, text):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        headers = {"Content-Type": "application/json", "Origin": self.origin,
                   "Cookie": self.cookie, "X-CSRF-Token": self.session["csrf"]}
        connection.request("POST", "/api/messages",
                           json.dumps({"conversation_id": self.identifier, "message": text,
                                       "request_id": str(uuid.uuid4()), "actor": self.actor}),
                           headers)
        response = connection.getresponse()
        body = json.loads(response.read())
        connection.close()
        return response.status, body

    def test_http_draft_shown_nothing_sent_until_separate_yes_then_mock_andrea(self):
        status, listed = self.post("texts")
        self.assertEqual(status, 202)
        self.assertIn("Alex Morgan", listed["messages"][-1]["content"])
        self.assertEqual(self.mock.sends, [])
        _, drafted = self.post("draft reply to Alex Morgan: Charts at 7 tonight.")
        card = drafted["messages"][-1]["text_draft"]
        self.assertEqual(card["state"], "pending")
        self.assertEqual(card["body"], "Charts at 7 tonight.")
        self.assertIn("+15550101010", json.dumps(card["recipient"]))
        self.assertEqual(self.mock.sends, [])
        _, bare = self.post("yes")
        self.assertIn("Nothing sent", bare["messages"][-1]["content"])
        self.assertEqual(self.mock.sends, [])
        status, confirmed = self.post(card["confirm_message"])
        self.assertEqual(status, 202)
        self.assertTrue(confirmed["messages"][-1]["content"].startswith("Sent via Andrea"))
        draft_messages = [m for m in confirmed["messages"] if m.get("text_draft")]
        self.assertEqual(draft_messages[-1]["text_draft"]["state"], "sent")
        self.assertEqual(len(self.mock.sends), 1)
        self.assertEqual(self.mock.sends[0]["text"], "Charts at 7 tonight.")
        self.assertIn(("POST", "/web-bob/send"), self.mock.calls)

    def test_browser_proof_when_playwright_available(self):
        if shutil.which("node") is None:
            self.skipTest("node is required for browser proof")
        probe = subprocess.run(["node", "-e", "require('playwright')"], capture_output=True, text=True, timeout=15)
        if probe.returncode != 0:
            self.skipTest("playwright is required for browser proof")
        result = subprocess.run(
            ["python3", str(CODE / "texting_proof.py")],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=ROOT,
        )
        self.assertEqual(result.returncode, 0, (result.stderr or "") + (result.stdout or ""))
        payload = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["mock_sends"], 1)


if __name__ == "__main__":
    unittest.main()
