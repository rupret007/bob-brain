import ast
import asyncio
import inspect
import threading
import uuid
import time
from contextlib import contextmanager, nullcontext
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from webbob.message_drafts import (
    ALLOWED_SEND_TRIGGERS,
    JeffDraftConsentVerifier,
    MessageDraftGate,
    MessageDraftError,
    normalize_jeff_approval_text,
    present_draft,
)


class MessageDraftGateTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "outbound.sqlite"
        self.consent_path = Path(self.temp.name) / "consent.sqlite"
        self.jeff = JeffDraftConsentVerifier(
            self.consent_path, "owner@example.org", "bob-chat", bob_chat="bob-chat"
        )
        self.sent = []
        self._execute_lock = threading.Lock()
        self.dispatch = AsyncMock(side_effect=self._record_dispatch)
        self.gate = MessageDraftGate(
            self.path,
            "owner@example.org",
            "bob-chat",
            jeff_consent=self.jeff,
            ownership=self._ownership,
            dispatch=self.dispatch,
        )
        self.text = {"chat_guid": "band-thread-guid", "body": "Exact text body"}
        self.email = {"to": "recipient@example.org", "subject": "Subject", "body": "Exact email body"}

    @contextmanager
    def _ownership(self, _draft_id):
        if not self._execute_lock.acquire(blocking=False):
            raise MessageDraftError("concurrent ownership denied")
        try:
            yield
        finally:
            self._execute_lock.release()

    async def _record_dispatch(self, channel, payload):
        self.sent.append((channel, payload))
        return SimpleNamespace(isError=False, model_dump=lambda **kw: {"channel": channel, "id": "provider-1"})

    def approve(self, draft, *, text="yes", message_id=None):
        message_id = message_id or f"jeff-msg-{uuid.uuid4().hex}"
        self.jeff.ingest_bob_chat_message(message_id, "jeff", text)
        return self.jeff.issue(draft["id"], draft["digest"], message_id)

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
        with self.assertRaises(MessageDraftError):
            await self.gate.execute(
                forged_card["id"],
                forged_card["digest"],
                proof[:-1] + ("0" if proof[-1] != "0" else "1"),
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
        with self.assertRaises(MessageDraftError):
            await self.gate.execute(
                draft["id"],
                draft["digest"],
                proof,
                writes_enabled=True,
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
                self.assertIn("user_google_email", body)
                self.assertEqual(body["user_google_email"], "owner@example.org")
            replay = await self.gate.execute(
                draft["id"],
                draft["digest"],
                proof,
                writes_enabled=True,
                trigger="explicit_approval",
            )
            self.assertEqual(replay["state"], "submitted")
            self.assertEqual(self.dispatch.await_count, 1)

    def test_a_draft_binding_carries_id_for_digest(self):
        draft = self.gate.prepare("text", self.text)
        self.assertIn("id", draft)
        self.assertTrue(draft["id"])

    def test_digest_binds_unique_draft_id(self):
        first = self.gate.prepare("text", self.text)
        second = self.gate.prepare("text", self.text)
        self.assertIn("id", first)
        self.assertIn("id", second)
        self.assertNotEqual(first["id"], second["id"])
        self.assertNotEqual(first["digest"], second["digest"])

    def test_execute_holds_ownership_lease(self):
        source = inspect.getsource(MessageDraftGate.execute)
        self.assertIn("with self.ownership(draft_id):", source)

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

    def test_jeff_approval_text_must_be_exact_yes(self):
        for text in ("YES", "y\u0435s", "ye\u200bs", "y\u202es", "no"):
            with self.assertRaises(MessageDraftError):
                normalize_jeff_approval_text(text)
        self.assertEqual(normalize_jeff_approval_text("yes"), "yes")

    def test_agent_and_inbound_approval_refused(self):
        draft = self.gate.prepare("text", self.text)
        for author in ("agent", "tool", "routine", "inbound"):
            mid = f"forged-{author}-msg-01"
            with self.assertRaises(MessageDraftError):
                self.jeff.ingest_bob_chat_message(mid, author, "yes")
            with self.assertRaises(MessageDraftError):
                self.jeff.issue(draft["id"], draft["digest"], mid)

    async def test_cross_draft_replay_rejected(self):
        same = {"chat_guid": "andrea-guid-0001", "body": "A"}
        a = self.gate.prepare("text", same)
        b = self.gate.prepare("text", same)
        self.assertNotEqual(a["id"], b["id"])
        proof = self.approve(a)
        with self.assertRaises(MessageDraftError):
            await self.gate.execute(b["id"], a["digest"], proof, writes_enabled=True, trigger="explicit_approval")
        self.dispatch.assert_not_awaited()

    def test_confusable_and_invisible_recipients_rejected(self):
        for to in (
            "andrea@gma\u0456l.com",
            "andrea@gmail.com\u200b",
            "jeff\u202e@moc.liamg.x",
            "andrea@gmail.com\u2060x",
        ):
            with self.assertRaises(MessageDraftError):
                self.gate.prepare("email", {"to": to, "subject": "s", "body": "b"})

    def test_bidi_body_rejected_and_card_flags_hygiene(self):
        with self.assertRaises(MessageDraftError):
            self.gate.prepare("text", dict(self.text, body="Lunch at 12\u202e evil"))
        draft = self.gate.prepare("text", self.text)
        self.assertNotIn("hygiene_warnings", present_draft(draft))

    def test_extra_email_fields_rejected(self):
        for extra in ({"cc": "x@y.z"}, {"attachments": "/etc/passwd"}):
            with self.assertRaises(MessageDraftError):
                self.gate.prepare("email", dict(self.email, **extra))

    def test_subject_crlf_rejected(self):
        with self.assertRaises(MessageDraftError):
            self.gate.prepare("email", dict(self.email, subject="bad\r\nheader"))

    def test_invalid_chat_guid_rejected(self):
        with self.assertRaises(MessageDraftError):
            self.gate.prepare("text", {"chat_guid": "short", "body": "hello there"})

    async def test_cross_conversation_execute_rejected(self):
        other = MessageDraftGate(
            self.path,
            "owner@example.org",
            "other-chat",
            jeff_consent=self.jeff,
            ownership=lambda _: nullcontext(),
            dispatch=self.dispatch,
        )
        draft = self.gate.prepare("text", self.text)
        proof = self.approve(draft)
        with self.assertRaises(MessageDraftError):
            await other.execute(draft["id"], draft["digest"], proof, writes_enabled=True, trigger="explicit_approval")

    async def test_expired_draft_rejected(self):
        draft = self.gate.prepare("text", self.text)
        proof = self.approve(draft)
        real = time.time
        import webbob.message_drafts as md

        md.time.time = lambda: real() + 901
        try:
            with self.assertRaises(MessageDraftError):
                await self.gate.execute(
                    draft["id"], draft["digest"], proof, writes_enabled=True, trigger="explicit_approval"
                )
        finally:
            md.time.time = real
        self.dispatch.assert_not_awaited()

    async def test_draft_row_expiry_independent_of_jeff_ttl(self):
        gate = MessageDraftGate(
            self.path,
            "owner@example.org",
            "bob-chat",
            jeff_consent=self.jeff,
            ownership=lambda _: nullcontext(),
            dispatch=self.dispatch,
        )
        draft = gate.prepare("text", self.text)
        proof = self.approve(draft, message_id="jeff-msg-expiry-row-01")
        real = time.time
        import webbob.message_drafts as md

        md.time.time = lambda: real() + 901
        try:
            with self.assertRaises(MessageDraftError) as ctx:
                await gate.execute(
                    draft["id"], draft["digest"], proof, writes_enabled=True, trigger="explicit_approval"
                )
            self.assertIn("stale", str(ctx.exception).lower())
        finally:
            md.time.time = real
        self.dispatch.assert_not_awaited()

    async def test_transport_error_leaves_uncertain_not_resendable(self):
        calls = []

        async def boom(channel, payload):
            calls.append(1)
            raise TimeoutError()

        gate = MessageDraftGate(
            self.path,
            "owner@example.org",
            "bob-chat",
            jeff_consent=self.jeff,
            ownership=lambda _: nullcontext(),
            dispatch=boom,
        )
        draft = gate.prepare("text", self.text)
        proof = self.approve(draft)
        first = await gate.execute(draft["id"], draft["digest"], proof, writes_enabled=True, trigger="explicit_approval")
        self.assertEqual(first["state"], "uncertain")
        proof2 = self.approve(draft)
        second = await gate.execute(
            draft["id"], draft["digest"], proof2, writes_enabled=True, trigger="explicit_approval"
        )
        self.assertEqual(second["state"], "uncertain")
        self.assertEqual(len(calls), 1)

    async def test_non_draft_edit_rejected(self):
        draft = self.gate.prepare("text", self.text)
        proof = self.approve(draft)
        await self.gate.execute(draft["id"], draft["digest"], proof, writes_enabled=True, trigger="explicit_approval")
        with self.assertRaises(MessageDraftError):
            self.gate.prepare("text", dict(self.text, body="new body text"), draft["id"])

    async def test_concurrent_double_execute_sends_once(self):
        self.sent.clear()
        draft = self.gate.prepare("text", dict(self.text, body="race body text"))
        proof = self.approve(draft, message_id="jeff-msg-race-body-01")

        gate = MessageDraftGate(
            self.path,
            "owner@example.org",
            "bob-chat",
            jeff_consent=self.jeff,
            ownership=self._ownership,
            dispatch=self.dispatch,
        )
        gate2 = MessageDraftGate(
            self.path,
            "owner@example.org",
            "bob-chat",
            jeff_consent=self.jeff,
            ownership=self._ownership,
            dispatch=self.dispatch,
        )
        results = await asyncio.gather(
            gate.execute(draft["id"], draft["digest"], proof, writes_enabled=True, trigger="explicit_approval"),
            gate2.execute(draft["id"], draft["digest"], proof, writes_enabled=True, trigger="explicit_approval"),
            return_exceptions=True,
        )
        self.assertEqual(len(self.sent), 1)
        states = [r["state"] if isinstance(r, dict) else type(r).__name__ for r in results]
        self.assertIn("submitted", states)


if __name__ == "__main__":
    unittest.main()
