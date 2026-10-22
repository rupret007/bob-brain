"""Proof verification must select preserved receipts and reject absent overlap."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import live_maxmode_proof as proof


class ProofTests(unittest.TestCase):
    def verify(self, overlap=True, duplicate=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipt = root / "preserved-proof.json"
            rows = [dict(id=lane, group_id="group", worker=lane, requested_worker=lane,
                         status="succeeded", attempts=1, execution_started_at=1,
                         finished_at=10, delivered_at=11) for lane in (*sorted(proof.MODELS), "mini")]
            data = dict(conversation_id="conversation", group_id="group", snapshots=[])
            if overlap:
                data["all_five_running"] = {"at": "previous observation"}
            receipt.write_text(json.dumps(data))
            result = dict(id="answer", group_id="group", task_status="succeeded", content="One combined answer")
            def call(path):
                if path == "/api/jobs":
                    return dict(dispatch=rows, read_at=12)
                return dict(messages=[result] * (2 if duplicate else 1))
            with patch.object(proof, "Client") as client, patch.object(sys, "argv", ["proof", "verify", "--root", str(root), "--receipt", str(receipt)]), patch("builtins.print"):
                client.return_value.call.side_effect = call
                proof.main()
            return json.loads(receipt.read_text())

    def test_verify_preserved_receipt_without_resubmitting_request(self):
        data = self.verify()
        self.assertEqual(data["overlap"]["seconds"], 9)
        self.assertEqual(data["answer"]["id"], "answer")

    def test_rejects_missing_live_simultaneous_execution_observation(self):
        with self.assertRaisesRegex(AssertionError, "No proven overlap"):
            self.verify(overlap=False)

    def test_rejects_duplicate_group_answers(self):
        with self.assertRaisesRegex(AssertionError, "exactly one"):
            self.verify(duplicate=True)
