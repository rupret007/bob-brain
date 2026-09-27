"""The live proof must tolerate completion between its queue and chat reads."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from live_integration_proof import Proof


class ProofTests(unittest.TestCase):
    def test_resume_refreshes_queue_after_terminal_chat_without_resubmitting(self):
        with tempfile.TemporaryDirectory() as directory:
            proof = Proof.__new__(Proof)
            proof.root = Path(directory)
            proof.save = Mock()
            proof.call = Mock(side_effect=AssertionError("Must not submit a duplicate task"))
            entry = dict(provider="codex", conversation_id="conversation", task=dict(task_id="task-1"))
            proof.data = {"providers": [entry]}
            running = dict(id="task-1", status="running", attempts=1)
            finished = dict(running, status="succeeded", worker="codex", created_at=1,
                            claimed_at=2, started_at=3, finished_at=4, result="Real answer",
                            result_sha256=hashlib.sha256(b"Real answer").hexdigest())
            proof.history = Mock(return_value={"messages": [dict(
                id="answer-1", task_id="task-1", task_status="succeeded", provider="codex",
                created_at=5, content="codex finished:\n\nReal answer")]})
            journal = proof.root / "conductor/state/queue.jsonl"
            journal.parent.mkdir(parents=True)
            journal.write_text("\n".join(json.dumps(dict(id="task-1", event=event,
                status=event, updated_at=i)) for i, event in enumerate(("claimed", "running", "succeeded"), 2)))
            with patch("live_integration_proof.task_queue.tasks", side_effect=[{"task-1": running}, {"task-1": finished}]):
                proof.resume("codex")
            proof.call.assert_not_called()
            self.assertEqual(entry["task"]["status"], "succeeded")
            self.assertEqual(entry["task"]["result_message_id"], "answer-1")
            self.assertIn("completed_at", entry)


if __name__ == "__main__":
    unittest.main()
