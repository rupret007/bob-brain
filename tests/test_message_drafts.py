import ast
import inspect
from contextlib import nullcontext
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from webbob.message_drafts import (
    ALLOWED_SEND_TRIGGERS,
    MessageDraftGate,
    MessageDraftError,
    present_draft,
)


class MessageDraftGateTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "outbound.sqlite"
        self.approvals = {}
        self.verify = lambda digest, proof: self.approvals.pop(proof, None) == digest
        self.sent = []
        self.dispatch = AsyncMock(side_effect=self._record_dispatch)
        self.gate = MessageDraftGate(
            self.path,
            "owner@example.org",
            "bob-chat",
            verify_consent=self.verify,
            ownership=lambda _: nullcontext(),
            dispatch=self.dispatch,
        )
        self.text = {"chat_guid": "band-thread-guid", "body": "Exact text body"}
        self.email = {"to": "recipient@example.org", "subject": "Subject", "body": "Exact email body"}

    async def _record_dispatch(self, channel, payload):
        self.sent.append((channel, payload))
        return SimpleNamespace(isError=False, model_dump=lambda **kw: {"channel": channel, "id": "provider-1"})

    def approve(self, draft):
        proof = "proof-" + draft["digest"]
        self.approvals[proof] = draft["digest"]
        return proof

    def test_present_shows_exact_draft_without_dispatch(self):
        draft = self.gate.prepare("text", self.text)
        card = present_draft(draft)
        self.assertEqual(card["channel"], "text")
        self.assertEqual(card["preview"]["body"], self.text["body"])
        self.assertEqual(card["digest"], draft["digest"])
        self.assertEqual(card["state"], "draft")
        self.assertFalse(card["send_authorized"])
        self.dispatch.assert_not_awaited()

    async def test_no_send_path_without_approval(self):
        blocked = self.gate.prepare("email", self.email)
        with self.assertRaises(MessageDraftError):
            await self.gate.execute(
                blocked["id"], blocked["digest"], self.approve(blocked), trigger="explicit_approval"
            )
        still_blocked = self.gate.prepare("email", dict(self.email, body="Second draft body"))
        with self.assertRaises(MessageDraftError):
            await self.gate.execute(
                still_blocked["id"],
                still_blocked["digest"],
                self.approve(still_blocked),
                writes_enabled=False,
                trigger="explicit_approval",
            )
        forged_card = self.gate.prepare("email", dict(self.email, body="Third draft body"))
        proof = self.approve(forged_card)
        self.approvals[proof] = "deadbeef"
        with self.assertRaises(MessageDraftError):
            await self.gate.execute(
                forged_card["id"],
                forged_card["digest"],
                proof,
                writes_enabled=True,
                trigger="explicit_approval",
            )
        self.dispatch.assert_not_awaited()
        self.assertEqual(self.sent, [])

    async def test_stale_or_edited_draft_rejects_prior_approval(self):
        for channel, payload, field, value in [
            ("text", self.text, "body", "Changed body"),
            ("email", self.email, "to", "other@example.org"),
            ("email", self.email, "subject", "Other subject"),
        ]:
            original = self.gate.prepare(channel, payload)
            proof = self.approve(original)
            revised = self.gate.prepare(channel, dict(payload, **{field: value}), original["id"])
            self.assertNotEqual(original["digest"], revised["digest"])
            with self.assertRaises(MessageDraftError):
                await self.gate.execute(
                    original["id"],
                    original["digest"],
                    proof,
                    writes_enabled=True,
                    trigger="explicit_approval",
                )
        self.dispatch.assert_not_awaited()

    async def test_routine_and_timer_triggers_never_send_even_with_approval(self):
        draft = self.gate.prepare("text", self.text)
        proof = self.approve(draft)
        for trigger in ("routine", "timer", "background", "automation"):
            with self.assertRaises(MessageDraftError):
                await self.gate.execute(
                    draft["id"],
                    draft["digest"],
                    proof,
                    writes_enabled=True,
                    trigger=trigger,
                )
        self.dispatch.assert_not_awaited()
        self.assertEqual(ALLOWED_SEND_TRIGGERS, frozenset({"explicit_approval"}))

    async def test_approved_exact_draft_sends_once_per_channel(self):
        for channel, payload in (("text", self.text), ("email", self.email)):
            self.sent.clear()
            self.dispatch.reset_mock()
            draft = self.gate.prepare(channel, payload)
            proof = self.approve(draft)
            receipt = await self.gate.execute(
                draft["id"],
                draft["digest"],
                proof,
                writes_enabled=True,
                trigger="explicit_approval",
            )
            self.assertEqual(receipt["state"], "submitted")
            self.assertEqual(self.dispatch.await_count, 1)
            channel_sent, body = self.sent[0]
            self.assertEqual(channel_sent, channel)
            if channel == "text":
                self.assertEqual(body["chat_guid"], payload["chat_guid"])
            else:
                self.assertEqual(body["to"], payload["to"])
            replay = await self.gate.execute(
                draft["id"],
                draft["digest"],
                proof,
                writes_enabled=True,
                trigger="explicit_approval",
            )
            self.assertEqual(replay["state"], "submitted")
            self.assertEqual(self.dispatch.await_count, 1)

    def test_module_has_no_timer_or_routine_auto_send_path(self):
        source = inspect.getsource(MessageDraftGate)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in {"call_later", "call_at", "Timer", "create_task"}:
                    self.fail("automatic delayed send path is forbidden")
        lowered = source.lower()
        self.assertNotIn("asyncio.sleep", lowered)
        self.assertNotIn("threading.timer", lowered)


if __name__ == "__main__":
    unittest.main()
