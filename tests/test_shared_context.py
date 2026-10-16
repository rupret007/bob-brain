import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from webbob.shared_context import AcceptedWriter, BOTS, ContextError, SharedContext, digest, import_day_one


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "shared.sqlite"
        self.stores = {bot: SharedContext(self.path, bot) for bot in BOTS}
        self.receipts = {}
        self.writer = AcceptedWriter(self.stores["webbob"], lambda payload, receipt: self.receipts.get(receipt) == payload)
        self.fact = {"id": "preference", "body": "Use Chicago time.", "classification": "accepted_fact",
                     "audience": sorted(BOTS), "provenance": {"kind": "reviewed_fact", "uri": "review:123",
                     "sha256": "a" * 64, "accepted_by": "jeff", "accepted_at": "2026-10-16"}}

    def accept(self, fact=None, revision=0):
        fact = fact or self.fact
        receipt = str(len(self.receipts))
        self.receipts[receipt] = digest({"operation": "put", "fact": fact, "expected_revision": revision})
        return self.writer.put(fact, revision, receipt)

    def test_correction_through_one_bot_visible_to_all_after_restart(self):
        self.accept()
        updated = copy.deepcopy(self.fact)
        updated["body"] = "Use America/Chicago time."
        self.accept(updated, 1)
        for bot in BOTS:
            rows = SharedContext(self.path, bot).read_context()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["body"], updated["body"])
            self.assertEqual(rows[0]["revision"], 2)
            self.assertEqual(rows[0]["provenance"], updated["provenance"])
            self.assertFalse(rows[0]["execution_authority"])

    def test_proposed_and_stale_approval_never_enter_shared_facts(self):
        self.stores["bob"].propose_fact(self.fact)
        self.assertEqual(self.stores["karen"].read_context(), [])
        with self.assertRaises(ContextError):
            self.writer.put(self.fact, 0, "made-up")
        self.accept()
        changed = copy.deepcopy(self.fact)
        changed["body"] = "Different body"
        with self.assertRaises(ContextError):
            self.writer.put(changed, 1, "0")
        with self.assertRaises(ContextError):
            self.accept(changed, 0)

    def test_forget_does_not_resurrect_old_revision_or_inbox_body(self):
        self.accept()
        self.stores["webbob"].post_message("notice", "bob", "context_updated", [self.fact["id"]])
        self.receipts["forget"] = digest({"operation": "forget", "id": self.fact["id"], "expected_revision": 1})
        self.writer.forget(self.fact["id"], 1, "forget")
        self.assertEqual(self.stores["bob"].read_context(), [])
        self.assertEqual(self.stores["bob"].read_inbox()[0]["facts"], [])
        with self.stores["bob"].transaction() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM facts WHERE body IS NOT NULL").fetchone()[0], 0)

    def test_private_texting_raw_voice_credentials_and_nonfacts_excluded(self):
        for kind in ("private_text", "raw_voice", "credential", "conversation", "texting"):
            fact = copy.deepcopy(self.fact)
            fact["provenance"]["kind"] = kind
            with self.assertRaises(ContextError):
                self.accept(fact)
        for body in ("api_key=not-a-real-key", "password=fake", "Bearer: fake"):
            fact = copy.deepcopy(self.fact)
            fact["body"] = body
            with self.assertRaises(ContextError):
                self.accept(fact)
        fact = copy.deepcopy(self.fact)
        fact["classification"] = "private"
        with self.assertRaises(ContextError):
            self.accept(fact)
        self.assertEqual(self.stores["bob"].read_context(), [])

    def test_visibility_checked_on_fact_read_and_message_send(self):
        fact = copy.deepcopy(self.fact)
        fact["audience"] = ["webbob"]
        self.accept(fact)
        self.assertEqual(self.stores["bob"].read_context(), [])
        with self.assertRaises(ContextError):
            self.stores["webbob"].post_message("notice", "bob", "context_updated", [fact["id"]])

    def test_restart_replays_unacked_without_repeating_completed_effects(self):
        self.accept()
        sender = self.stores["webbob"]
        sender.post_message("notice", "bob", "context_updated", [self.fact["id"]])
        sender.post_message("notice", "bob", "context_updated", [self.fact["id"]])
        receiver = SharedContext(self.path, "bob")
        self.assertEqual(len(receiver.read_inbox()), 1)
        effects = []
        if receiver.begin_effect("notice"):
            effects.append("effect")
            receiver.complete_effect("notice", "receipt:one")
        receiver = SharedContext(self.path, "bob")
        self.assertEqual(receiver.read_inbox()[0]["effect_state"], "complete")
        if receiver.begin_effect("notice"):
            effects.append("duplicate")
        self.assertEqual(effects, ["effect"])
        receiver.ack_message("notice")
        self.assertEqual(SharedContext(self.path, "bob").read_inbox(), [])

    def test_crash_after_effect_admission_is_uncertain_never_automatic_retry(self):
        self.accept()
        self.stores["webbob"].post_message("notice", "bob", "context_updated", [self.fact["id"]])
        self.assertTrue(self.stores["bob"].begin_effect("notice"))
        receiver = SharedContext(self.path, "bob")
        self.assertEqual(receiver.read_inbox()[0]["effect_state"], "uncertain")
        self.assertFalse(receiver.begin_effect("notice"))

    def test_only_recipient_can_ack_or_record_effect(self):
        self.accept()
        self.stores["webbob"].post_message("notice", "bob", "context_updated", [self.fact["id"]])
        for operation in (lambda: self.stores["karen"].ack_message("notice"),
                          lambda: self.stores["andrea"].begin_effect("notice"),
                          lambda: self.stores["webbob"].complete_effect("notice", "forged")):
            with self.assertRaises(ContextError):
                operation()

    def test_inbox_resolves_older_references_and_current_visibility(self):
        self.accept()
        self.stores["webbob"].post_message("older", "bob", "context_updated", [self.fact["id"]])
        for index in range(101):
            fact = copy.deepcopy(self.fact)
            fact["id"] = f"newer-{index}"
            self.accept(fact)
        self.assertNotIn(self.fact["id"], {f["id"] for f in self.stores["bob"].read_context(100)})
        self.assertEqual(self.stores["bob"].read_inbox()[0]["facts"][0]["body"], self.fact["body"])
        changed = copy.deepcopy(self.fact)
        changed["audience"] = ["webbob"]
        self.accept(changed, 1)
        self.assertEqual(self.stores["bob"].read_inbox()[0]["facts"], [])

    def test_exact_line_day_one_import_from_both_memory_roots(self):
        root = Path(__file__).resolve().parents[1]
        manifest = json.loads((root / "config/day-one-facts.json").read_text())
        self.assertEqual({Path(i["path"]).parts[0] for i in manifest}, {"memory", "user-memory"})
        imported = import_day_one(self.stores["webbob"], root, manifest)
        self.assertEqual(len(imported), 2)
        self.assertEqual(import_day_one(self.stores["webbob"], root, manifest), [])
        for bot in BOTS:
            rows = self.stores[bot].read_context()
            self.assertEqual(len(rows), 2)
            self.assertTrue(all(r["provenance"]["sha256"] for r in rows))
        bad = copy.deepcopy(manifest)
        bad[0]["line_sha256"] = "0" * 64
        with self.assertRaises(ContextError):
            import_day_one(self.stores["bob"], root, bad)

    def test_mcp_surface_does_not_expose_acceptance_or_effect_execution(self):
        from webbob.context_mcp import build_server
        import asyncio
        tools = asyncio.run(build_server(self.path, "bob").list_tools())
        self.assertEqual({t.name for t in tools}, {"read_context", "propose_fact", "post_message", "read_inbox", "ack_message"})


if __name__ == "__main__":
    unittest.main()
