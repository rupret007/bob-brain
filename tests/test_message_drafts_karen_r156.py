"""Karen r156 repro scenarios for message draft gate (from karen-wbp1017/r156.py)."""
import asyncio
import tempfile
import time
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

from webbob.message_drafts import JeffDraftConsentVerifier, MessageDraftGate, MessageDraftError, present_draft


class KarenR156ReproTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.sent = []
        tmp = tempfile.mkdtemp()
        self.addCleanup(lambda: None)
        self.path = Path(tmp) / "o.sqlite"
        self.consent_path = Path(tmp) / "consent.sqlite"
        self.jeff = JeffDraftConsentVerifier(
            self.consent_path, "owner@example.org", "bob-chat", bob_chat="bob-chat"
        )

        async def dispatch(ch, p):
            self.sent.append((ch, p))
            await asyncio.sleep(0.05)
            return SimpleNamespace(isError=False, model_dump=lambda **k: {"id": "x"})

        self.dispatch = dispatch
        self.gate = MessageDraftGate(
            self.path,
            "owner@example.org",
            "bob-chat",
            verify_consent=self.jeff.verify_callback(),
            ownership=lambda _: nullcontext(),
            dispatch=self.dispatch,
        )

    def approve(self, dr):
        return self.jeff.issue(dr["id"], dr["digest"], "yes", source="jeff_chat")

    async def test_r1_execute_without_trigger_kwarg_forbidden(self):
        d = self.gate.prepare("text", {"chat_guid": "andrea-guid-0001", "body": "hi"})
        pr = self.approve(d)
        with self.assertRaises(MessageDraftError):
            await self.gate.execute(d["id"], d["digest"], pr, writes_enabled=True)
        self.assertEqual(self.sent, [])

    async def test_r2_cross_draft_replay_refused(self):
        a = self.gate.prepare("text", {"chat_guid": "andrea-guid-0001", "body": "A"})
        b = self.gate.prepare("text", {"chat_guid": "andrea-guid-0001", "body": "A"})
        pa = self.approve(a)
        with self.assertRaises(MessageDraftError):
            await self.gate.execute(b["id"], a["digest"], pa, writes_enabled=True, trigger="explicit_approval")
        self.assertEqual(self.sent, [])

    async def test_r3_confusable_recipients_refused(self):
        for to in ("andrea@gma\u0456l.com", "andrea@gmail.com\u200b", "jeff\u202e@moc.liamg.x", "andrea@gmail.com\u2060x"):
            with self.assertRaises(MessageDraftError):
                self.gate.prepare("email", {"to": to, "subject": "s", "body": "b"})

    async def test_r4_bidi_body_refused(self):
        with self.assertRaises(MessageDraftError):
            self.gate.prepare("text", {"chat_guid": "andrea-guid-0001", "body": "Lunch at 12\u202e ,yadot gnihtyreve leacnaC"})

    async def test_r5_concurrent_double_click_single_send(self):
        self.sent.clear()
        d = self.gate.prepare("text", {"chat_guid": "andrea-guid-0001", "body": "race"})
        pr = self.approve(d)
        g2 = MessageDraftGate(
            self.path,
            "owner@example.org",
            "bob-chat",
            verify_consent=self.jeff.verify_callback(),
            ownership=lambda _: nullcontext(),
            dispatch=self.dispatch,
        )
        rs = await asyncio.gather(
            self.gate.execute(d["id"], d["digest"], pr, writes_enabled=True, trigger="explicit_approval"),
            g2.execute(d["id"], d["digest"], pr, writes_enabled=True, trigger="explicit_approval"),
            return_exceptions=True,
        )
        self.assertEqual(len(self.sent), 1)
        states = [r.get("state") if isinstance(r, dict) else type(r).__name__ for r in rs]
        self.assertIn("submitted", states)

    async def test_r6_expired_approval_refused(self):
        d = self.gate.prepare("text", {"chat_guid": "andrea-guid-0001", "body": "late"})
        pr = self.approve(d)
        real = time.time
        import webbob.message_drafts as md

        md.time.time = lambda: real() + 901
        try:
            with self.assertRaises(MessageDraftError):
                await self.gate.execute(d["id"], d["digest"], pr, writes_enabled=True, trigger="explicit_approval")
        finally:
            md.time.time = real
        self.assertEqual(self.sent, [])

    async def test_r7_transport_error_uncertain_not_resendable(self):
        self.sent.clear()

        async def boom(ch, p):
            self.sent.append(1)
            raise TimeoutError()

        g3 = MessageDraftGate(
            self.path,
            "owner@example.org",
            "bob-chat",
            verify_consent=self.jeff.verify_callback(),
            ownership=lambda _: nullcontext(),
            dispatch=boom,
        )
        d = g3.prepare("text", {"chat_guid": "andrea-guid-0001", "body": "err"})
        pr = self.approve(d)
        r = await g3.execute(d["id"], d["digest"], pr, writes_enabled=True, trigger="explicit_approval")
        pr2 = self.approve(d)
        r2 = await g3.execute(d["id"], d["digest"], pr2, writes_enabled=True, trigger="explicit_approval")
        self.assertEqual(r["state"], "uncertain")
        self.assertEqual(r2["state"], "uncertain")
        self.assertEqual(len(self.sent), 1)

    async def test_r8_cross_conversation_refused(self):
        g4 = MessageDraftGate(
            self.path,
            "owner@example.org",
            "other-chat",
            verify_consent=self.jeff.verify_callback(),
            ownership=lambda _: nullcontext(),
            dispatch=self.dispatch,
        )
        d = self.gate.prepare("text", {"chat_guid": "andrea-guid-0001", "body": "x"})
        pr = self.approve(d)
        with self.assertRaises(MessageDraftError):
            await g4.execute(d["id"], d["digest"], pr, writes_enabled=True, trigger="explicit_approval")
        self.assertEqual(self.sent, [])

    async def test_r9_extra_fields_refused(self):
        for extra in ({"cc": "x@y.z"}, {"attachments": "/etc/passwd"}):
            with self.assertRaises(MessageDraftError):
                self.gate.prepare("email", dict({"to": "a@b.co", "subject": "s", "body": "b"}, **extra))


if __name__ == "__main__":
    unittest.main()
