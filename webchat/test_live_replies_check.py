"""The new live gate must reject queue receipts without real execution."""
import contextlib
import io
import threading

from app import Server
from live_redeploy_check import Client
from live_replies_check import verify_replies
from test_webchat import Fixture


class RepliesGate(Fixture):
    def test_authenticated_exact_replay_cannot_pass_on_four_queued_jobs(self):
        server = Server(("127.0.0.1", 0), self.chat)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            client = Client(f"http://127.0.0.1:{server.server_port}", self.folder / ".password")
            output = self.root / "proof.json"
            with contextlib.redirect_stdout(io.StringIO()):
                proof = verify_replies(client, self.root, output, timeout=0)
            self.assertFalse(proof["all_pass"])
            self.assertEqual(len(proof["task_ids"]), 4)
            self.assertEqual(len(proof["exchanges"]), 6)
            self.assertIn("four actual executions", proof["failure"])
            self.assertFalse(proof["started_jobs"])
            self.assertNotIn(self.chat.password, output.read_text())
            self.assertFalse(self.fake.calls)
        finally:
            server.shutdown()
            server.server_close()
