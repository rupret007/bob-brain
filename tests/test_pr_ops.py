from contextlib import nullcontext
import copy
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

from webbob.pr_ops import DraftPublisher, GateDenied, ReviewGate, digest


class GateTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.signed = {}
        self.inbox = {}
        self.gate = ReviewGate(Path(self.temp.name) / "reviews.sqlite",
                               verify_karen=lambda d, r: self.signed.get(r) == d,
                               verify_jeff=lambda scope, proof: proof == "jeff-standing" and scope["repo"] == "a/b",
                               post_review=lambda ident, payload: self.inbox.setdefault(ident, payload))
        self.sha = "a" * 40
        self.request = self.gate.request_review("a/b", 7, self.sha, "ownership", ["tests:pass:123"])

    def verdict(self, value="PASS"):
        payload = {k: v for k, v in self.request.items() if k != "recipient"}
        payload.update(verdict=value, reviewer="karen", expires=time.time() + 600)
        self.signed["signature"] = digest(payload)
        self.gate.record_verdict(payload, "signature")
        return payload

    def readiness(self, sha=None, proof="jeff-standing"):
        return self.gate.merge_readiness("a/b", 7, sha or self.sha, self.request["request_id"], proof)

    async def test_current_commit_pass_and_jeff_required_new_commit_stales_review(self):
        self.assertFalse(self.readiness()["eligible_for_jeff_merge"])
        self.verdict()
        self.assertTrue(self.readiness()["eligible_for_jeff_merge"])
        self.assertFalse(self.readiness("b" * 40)["eligible_for_jeff_merge"])
        self.assertFalse(self.readiness(proof="missing")["eligible_for_jeff_merge"])
        self.assertTrue(self.readiness()["webbob_draft_only"])

    async def test_old_qa_file_cannot_approve_or_forge_karen_identity(self):
        payload = {k: v for k, v in self.request.items() if k != "recipient"}
        payload.update(verdict="PASS", reviewer="karen", expires=time.time() + 600)
        with self.assertRaises(GateDenied):
            self.gate.record_verdict(payload, "old-QA.md:PASS")
        payload["reviewer"] = "webbob"
        self.signed["fake"] = digest(payload)
        with self.assertRaises(GateDenied):
            self.gate.record_verdict(payload, "fake")

    async def test_verdict_binds_scope_evidence_and_latest_fail_supersedes_pass(self):
        payload = self.verdict()
        for field, value in [("scope", "different"), ("evidence", ["other"]), ("sha", "b" * 40)]:
            changed = dict(payload, **{field: value})
            self.signed["changed"] = digest(changed)
            with self.assertRaises(GateDenied):
                self.gate.record_verdict(changed, "changed")
        self.verdict("FAIL")
        self.assertFalse(self.readiness()["eligible_for_jeff_merge"])

    async def test_review_request_replay_keeps_one_addressed_message(self):
        self.gate.deliver_request(self.request["request_id"])
        self.assertEqual(len(self.inbox), 1)
        self.assertEqual(next(iter(self.inbox.values()))["recipient"], "karen")

    async def test_publication_current_ownership_approval_and_remote_sha(self):
        calls = AsyncMock(return_value=SimpleNamespace(isError=False))
        publisher = DraftPublisher(SimpleNamespace(call_tool=calls), ownership=lambda _: nullcontext(),
            verify_publish=lambda d, p: p == "approved", read_branch_sha=AsyncMock(return_value=self.sha),
            read_pr=AsyncMock(return_value={"head_sha": self.sha, "draft": True, "state": "open", "number": 7, "url": "https://github.com/a/b/pull/7"}))
        with self.assertRaises(GateDenied):
            await publisher.publish("a/b", "draft/test", self.sha, "Title", "Body", "missing")
        calls.assert_not_awaited()
        publisher.read_branch_sha.return_value = "b" * 40
        with self.assertRaises(GateDenied):
            await publisher.publish("a/b", "draft/test", self.sha, "Title", "Body", "approved")
        publisher.read_branch_sha.return_value = self.sha
        def expired(_):
            raise GateDenied("expired lease")
        publisher.ownership = expired
        with self.assertRaises(GateDenied):
            await publisher.publish("a/b", "draft/test", self.sha, "Title", "Body", "approved")
        calls.assert_not_awaited()
        publisher.ownership = lambda _: nullcontext()
        result = await publisher.publish("a/b", "draft/test", self.sha, "Title", "Body", "approved")
        self.assertEqual(result["state"], "draft")
        self.assertEqual(calls.call_args.args[0], "create_pull_request")
        self.assertTrue(calls.call_args.args[1]["draft"])
        self.assertFalse(hasattr(publisher, "merge"))
        self.assertFalse(hasattr(publisher, "undraft"))


if __name__ == "__main__":
    unittest.main()
