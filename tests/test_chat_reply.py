import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

from webbob.chat_reply import ChatReplyError, ChatReplyJournal, MAX_ATTEMPTS


class ChatReplyTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "replies.sqlite"
        self.journal = ChatReplyJournal(self.path, "conv-1")

    def test_invalid_reply_id_rejected(self):
        with self.assertRaises(ChatReplyError):
            self.journal.prepare("", "hello")
        with self.assertRaises(ChatReplyError):
            self.journal.prepare("has spaces", "hello")

    def test_prepare_same_id_and_body_is_idempotent(self):
        first = self.journal.prepare("reply-1", "hello Jeff")
        second = self.journal.prepare("reply-1", "hello Jeff")
        self.assertEqual(first, second)
        self.assertEqual(self.journal.status("reply-1")["state"], "queued")

    def test_reply_id_reused_with_different_body_rejected(self):
        self.journal.prepare("reply-1", "first body")
        with self.assertRaises(ChatReplyError):
            self.journal.prepare("reply-1", "second body")

    async def test_successful_deliver_records_receipt_without_duplicate_send(self):
        send = AsyncMock(return_value="transport:abc")
        result = await self.journal.deliver("reply-1", "visible answer", send, now=100.0)
        self.assertEqual(result["state"], "delivered")
        self.assertEqual(result["receipt"], "transport:abc")
        send.assert_awaited_once_with("visible answer")
        replay = await self.journal.deliver("reply-1", "visible answer", send, now=100.0)
        self.assertEqual(replay["state"], "delivered")
        self.assertEqual(replay["receipt"], "transport:abc")
        send.assert_awaited_once()

    async def test_transient_failure_surfaces_failed_retry_then_backoff(self):
        send = AsyncMock(side_effect=[RuntimeError("timeout"), "transport:ok"])
        first = await self.journal.deliver("reply-1", "retry me", send, now=1_000.0)
        self.assertEqual(first["state"], "failed_retry")
        self.assertGreater(first["next_retry_at"], 1_000.0)
        self.assertEqual(send.await_count, 1)
        blocked = await self.journal.deliver("reply-1", "retry me", send, now=1_000.5)
        self.assertEqual(blocked["state"], "failed_retry")
        self.assertEqual(send.await_count, 1)
        done = await self.journal.deliver("reply-1", "retry me", send, now=first["next_retry_at"])
        self.assertEqual(done["state"], "delivered")
        self.assertEqual(send.await_count, 2)

    async def test_bounded_retries_end_in_terminal_failed(self):
        send = AsyncMock(side_effect=RuntimeError("down"))
        now = 5_000.0
        last = None
        for _ in range(MAX_ATTEMPTS):
            last = await self.journal.deliver("reply-1", "still down", send, now=now)
            now += 60.0
        self.assertEqual(last["state"], "failed")
        self.assertEqual(send.await_count, MAX_ATTEMPTS)
        again = await self.journal.deliver("reply-1", "still down", send, now=now)
        self.assertEqual(again["state"], "failed")
        self.assertEqual(send.await_count, MAX_ATTEMPTS)

    async def test_in_flight_reply_is_not_retried_automatically(self):
        self.journal.prepare("reply-1", "uncertain")
        with self.journal.db() as db:
            db.execute("UPDATE replies SET state='in_flight', attempts=1 WHERE id=?", ("reply-1",))
        send = AsyncMock(return_value="transport:late")
        result = await self.journal.deliver("reply-1", "uncertain", send, now=50.0)
        self.assertEqual(result["state"], "in_flight")
        send.assert_not_awaited()

    async def test_restart_preserves_delivered_receipt_without_resend(self):
        send = AsyncMock(return_value="transport:persist")
        await self.journal.deliver("reply-1", "stable", send, now=20.0)
        restarted = ChatReplyJournal(self.path, "conv-1")
        again = await restarted.deliver("reply-1", "stable", send, now=21.0)
        self.assertEqual(again["state"], "delivered")
        self.assertEqual(again["receipt"], "transport:persist")
        send.assert_awaited_once()

    def test_conversation_mismatch_rejected(self):
        self.journal.prepare("reply-1", "hello")
        other = ChatReplyJournal(self.path, "conv-2")
        with self.assertRaises(ChatReplyError):
            other.status("reply-1")


if __name__ == "__main__":
    unittest.main()
