"""Release gating must fail closed on authentication and individual HTTP failures."""
import contextlib
import io
import json
import threading
from unittest.mock import patch

from app import Server
from live_redeploy_check import CHECKS, CheckFailure, Client, verify_four, follow_through
from build_info import BUILD
from task_dispatch import task_queue
from test_webchat import Fixture


class ReleaseChecks(Fixture):
    def setUp(self):
        super().setUp()
        self.server = Server(("127.0.0.1", 0), self.chat)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.client = Client(self.url, self.folder / ".password")
        self.output = self.root / "result.json"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        super().tearDown()

    def verify(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return verify_four(self.client, self.root, self.output)

    def test_login_failure_marks_all_four_failed_and_writes_no_jobs(self):
        password = self.folder / "wrong-password"
        password.write_text("deliberately-invalid")
        self.client.password_file = password
        result = self.verify()
        self.assertFalse(result["all_pass"])
        self.assertEqual(set(result["checks"]), set(CHECKS))
        for check in result["checks"].values():
            self.assertFalse(check["pass_check"])
            self.assertIn("HTTP 401", check["error"])
        self.assertFalse((self.root / "conductor/state/queue.jsonl").exists())
        self.assertNotIn("deliberately-invalid", self.output.read_text())

    def test_authenticated_four_checks_use_real_http_and_durable_jobs(self):
        result = self.verify()
        self.assertTrue(result["all_pass"], json.dumps(result))
        self.assertFalse(self.fake.calls)
        self.assertNotIn(self.chat.password, self.output.read_text())
        self.assertEqual(len(result["checks"]["push2"]["jobs"]), 2)

    def test_go_http_error_cannot_be_mistaken_for_cleared_hold(self):
        original = self.client.call
        def expired_session(route, data=None):
            if data and data.get("message") == "go":
                raise CheckFailure("HTTP 401 at /api/messages")
            return original(route, data)
        with patch.object(self.client, "call", side_effect=expired_session):
            result = self.verify()
        self.assertFalse(result["all_pass"])
        self.assertFalse(result["checks"]["go"]["pass_check"])
        self.assertEqual(result["checks"]["go"]["error"], "HTTP 401 at /api/messages")
        self.assertTrue(all(result["checks"][name]["pass_check"] for name in CHECKS if name != "go"))

    def test_async_failed_review_cannot_pass_on_its_queue_receipt(self):
        result = self.verify()
        job_id = result["checks"]["claude161"]["jobs"][0]["id"]
        claim = task_queue.claim(self.root, "claude")
        self.assertEqual(claim["id"], job_id)
        task_queue.transition(self.root, job_id, claim["claim_token"], "rejected", error="session limit; no review")
        result = follow_through(self.client, self.root, self.output, result, BUILD["sha"], timeout=0)
        self.assertFalse(result["all_pass"])
        self.assertIn("claude161:", result["failure"])
        self.assertIn("session limit", result["failure"])
