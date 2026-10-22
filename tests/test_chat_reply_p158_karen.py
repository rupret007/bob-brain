"""Karen p158 repro — stale lease, empty receipt, ChatReplyError, cancel, hung timeout."""
import asyncio
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from webbob.chat_reply import ChatReplyError, ChatReplyJournal, ReplyNotSentError


class KarenP158Repro(unittest.IsolatedAsyncioTestCase):
    def journal(self):
        return ChatReplyJournal(Path(tempfile.mkdtemp()) / "r.sqlite", "bob-chat:t1")

    async def test_p158_scenarios(self):
        visible = []

        async def ok(reply_id, body):
            visible.append(body)
            return "rcpt"

        # P1 stale in_flight after crash must not resend
        visible.clear()
        journal = self.journal()
        journal.prepare("r1", "hi")
        stamped = time.time()
        with journal.db() as db:
            db.execute(
                "UPDATE replies SET state='in_flight', attempts=1, updated_at=? WHERE id='r1'",
                (stamped,),
            )
        visible.append("hi")
        first = await journal.deliver("r1", "hi", ok, now=stamped + 31)
        self.assertEqual(first["state"], "uncertain")
        self.assertEqual(len(visible), 1)

        # P2 posted + empty receipt
        visible.clear()
        journal = self.journal()

        async def post_noreceipt(reply_id, body):
            visible.append(body)
            return ""

        first = await journal.deliver("r2", "hi", post_noreceipt, now=0)
        second = await journal.deliver("r2", "hi", ok, now=first["next_retry_at"] or 0)
        self.assertEqual(first["state"], "uncertain")
        self.assertNotEqual(first["state"], "failed_retry")
        self.assertEqual(second["state"], "uncertain")
        self.assertEqual(len(visible), 1)

        # P3 posted + ChatReplyError
        visible.clear()
        journal = self.journal()

        async def post_then_cre(reply_id, body):
            visible.append(body)
            raise ChatReplyError("adapter validation")

        first = await journal.deliver("r3", "hi", post_then_cre, now=0)
        second = await journal.deliver("r3", "hi", ok, now=first["next_retry_at"] or 0)
        self.assertEqual(first["state"], "uncertain")
        self.assertEqual(second["state"], "uncertain")
        self.assertEqual(len(visible), 1)

        # P4 CancelledError
        visible.clear()
        journal = self.journal()

        async def post_cancel(reply_id, body):
            visible.append(body)
            raise asyncio.CancelledError()

        with self.assertRaises(asyncio.CancelledError):
            await journal.deliver("r4", "hi", post_cancel)
        self.assertEqual(journal.status("r4")["state"], "uncertain")
        again = await journal.deliver("r4", "hi", ok, now=time.time() + 31)
        self.assertEqual(again["state"], "uncertain")
        self.assertEqual(len(visible), 1)

        # P5 transport timeout after post surfaces uncertain, never delivered
        visible.clear()
        journal = self.journal()

        async def post_timeout(reply_id, body):
            visible.append(body)
            raise TimeoutError()

        result = await journal.deliver("r5", "hi", post_timeout)
        self.assertEqual(result["state"], "uncertain")
        self.assertNotEqual(result["state"], "delivered")

        visible.clear()
        journal = self.journal()

        async def hang(reply_id, body):
            await asyncio.sleep(5.0)

        with patch("webbob.chat_reply.SEND_TIMEOUT_SECONDS", 0.2):
            hung = await journal.deliver("r5b", "hi", hang)
        self.assertEqual(hung["state"], "failed_retry")
        self.assertNotEqual(hung["state"], "delivered")

        # P6 ReplyNotSentError still retries to terminal failed
        journal = self.journal()

        async def not_sent(reply_id, body):
            raise ReplyNotSentError("no")

        states = []
        now = 0.0
        for _ in range(5):
            snap = await journal.deliver("r6", "hi", not_sent, now=now)
            states.append(snap["state"])
            now = snap["next_retry_at"] or now + 60
        self.assertEqual(states[:3], ["failed_retry", "failed_retry", "failed"])
        self.assertEqual(states[3:], ["failed", "failed"])


if __name__ == "__main__":
    unittest.main()
