import asyncio
import inspect
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from webbob.chat_reply import (
    ChatReplyError,
    ChatReplyJournal,
    MAX_ATTEMPTS,
    ReplyNotSentError,
    SEND_TIMEOUT_SECONDS,
)


class ChatReplyTests(unittest.IsolatedAsyncioTestCase):
    CONV = "bob-chat:conv-1"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "replies.sqlite"
        self.journal = ChatReplyJournal(self.path, self.CONV)

    def test_non_bob_chat_conversation_rejected(self):
        with self.assertRaises(ChatReplyError):
            ChatReplyJournal(self.path, "conv-1")
        with self.assertRaises(ChatReplyError):
            ChatReplyJournal(self.path, "bob-chat:")

    def test_invalid_reply_id_rejected(self):
        with self.assertRaises(ChatReplyError):
            self.journal.prepare("", "hello")
        with self.assertRaises(ChatReplyError):
            self.journal.prepare("has spaces", "hello")

    def test_oversized_body_rejected(self):
        with self.assertRaises(ChatReplyError):
            self.journal.prepare("reply-1", "x" * 32_001)

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
        send.assert_awaited_once_with("reply-1", "visible answer")
        replay = await self.journal.deliver("reply-1", "visible answer", send, now=100.0)
        self.assertEqual(replay["state"], "delivered")
        self.assertEqual(replay["receipt"], "transport:abc")
        send.assert_awaited_once()

    def test_deliver_passes_reply_id_to_transport(self):
        source = inspect.getsource(ChatReplyJournal.deliver)
        self.assertIn("guarded_send(reply_id, body)", source)

    async def test_transient_not_sent_surfaces_failed_retry_then_backoff(self):
        send = AsyncMock(side_effect=[ReplyNotSentError("offline"), "transport:ok"])
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
        send = AsyncMock(side_effect=ReplyNotSentError("down"))
        now = 5_000.0
        last = None
        for _ in range(MAX_ATTEMPTS):
            last = await self.journal.deliver("reply-1", "still down", send, now=now)
            now += 60.0
        self.assertEqual(last["state"], "failed")
        self.assertIsNone(last["next_retry_at"])
        self.assertEqual(send.await_count, MAX_ATTEMPTS)
        again = await self.journal.deliver("reply-1", "still down", send, now=now)
        self.assertEqual(again["state"], "failed")
        self.assertEqual(send.await_count, MAX_ATTEMPTS)

    async def test_failed_state_never_calls_transport(self):
        self.journal.prepare("reply-1", "halt")
        with self.journal.db() as db:
            db.execute("UPDATE replies SET state='failed', attempts=1 WHERE id=?", ("reply-1",))
        send = AsyncMock(return_value="transport:late")
        result = await self.journal.deliver("reply-1", "halt", send, now=100.0)
        self.assertEqual(result["state"], "failed")
        send.assert_not_awaited()

    async def test_terminal_failed_after_three_reply_not_sent_attempts(self):
        send = AsyncMock(side_effect=ReplyNotSentError("down"))
        now = 1_000.0
        states = []
        for _ in range(3):
            snap = await self.journal.deliver("reply-1", "x", send, now=now)
            states.append(snap["state"])
            now += 120.0
        self.assertEqual(states, ["failed_retry", "failed_retry", "failed"])
        self.assertEqual(send.await_count, 3)

    async def test_max_attempts_exhausted_without_calling_transport(self):
        self.journal.prepare("reply-1", "cap")
        with self.journal.db() as db:
            db.execute(
                "UPDATE replies SET attempts=?, state='failed_retry', next_retry_at=? WHERE id=?",
                (MAX_ATTEMPTS, 0.0, "reply-1"),
            )
        send = AsyncMock(return_value="transport:late")
        result = await self.journal.deliver("reply-1", "cap", send, now=10_000.0)
        self.assertEqual(result["state"], "failed")
        send.assert_not_awaited()

    async def test_in_flight_recorded_before_transport_runs(self):
        seen = []

        async def send(reply_id, body):
            with self.journal.db() as db:
                row = db.execute("SELECT state FROM replies WHERE id=?", (reply_id,)).fetchone()
                seen.append(row["state"])
            return "transport:ok"

        await self.journal.deliver("reply-1", "ordering", send, now=1.0)
        self.assertEqual(seen, ["in_flight"])

    async def test_fresh_in_flight_blocks_duplicate_send_during_lease(self):
        self.journal.prepare("reply-1", "uncertain")
        with self.journal.db() as db:
            db.execute(
                "UPDATE replies SET state='in_flight', attempts=1, updated_at=? WHERE id=?",
                (50.0, "reply-1"),
            )
        send = AsyncMock(return_value="transport:late")
        result = await self.journal.deliver("reply-1", "uncertain", send, now=50.0)
        self.assertEqual(result["state"], "in_flight")
        send.assert_not_awaited()

    async def test_stale_in_flight_surfaces_uncertain_without_resend(self):
        self.journal.prepare("reply-3", "y")
        with self.journal.db() as db:
            db.execute(
                "UPDATE replies SET state='in_flight', attempts=1, updated_at=? WHERE id=?",
                (0.0, "reply-3"),
            )
        send = AsyncMock(return_value="transport:recovered")
        result = await self.journal.deliver("reply-3", "y", send, now=999_999.0)
        self.assertEqual(result["state"], "uncertain")
        self.assertEqual(result["receipt"], "uncertain:reply-3")
        send.assert_not_awaited()

    async def test_uncertain_transport_failure_does_not_retry_visible_reply(self):
        visible = []

        async def send_delivered_then_timeout(reply_id, body):
            visible.append(body)
            raise asyncio.TimeoutError()

        async def ok(reply_id, body):
            visible.append(body)
            return "transport:ok"

        first = await self.journal.deliver("reply-1", "hello Jeff", send_delivered_then_timeout, now=0.0)
        self.assertEqual(first["state"], "uncertain")
        self.assertEqual(first["receipt"], "uncertain:reply-1")
        second = await self.journal.deliver("reply-1", "hello Jeff", ok, now=999_999.0)
        self.assertEqual(second["state"], "uncertain")
        self.assertEqual(len(visible), 1)

    async def test_proxy_error_after_commit_treated_as_delivered_without_resend(self):
        visible = []

        async def send_5xx_after_commit(reply_id, body):
            visible.append(body)
            raise RuntimeError("502 Bad Gateway from proxy after upstream commit")

        first = await self.journal.deliver("reply-1", "hello Jeff", send_5xx_after_commit, now=0.0)
        self.assertEqual(first["state"], "uncertain")
        send = AsyncMock(return_value="transport:dup")
        again = await self.journal.deliver("reply-1", "hello Jeff", send, now=999_999.0)
        self.assertEqual(again["state"], "uncertain")
        self.assertEqual(len(visible), 1)
        send.assert_not_awaited()

    async def test_concurrent_deliver_single_visible_send(self):
        visible = []
        path = Path(self.temp.name) / "shared.sqlite"
        j1 = ChatReplyJournal(path, self.CONV)
        j2 = ChatReplyJournal(path, self.CONV)

        async def slow(reply_id, body):
            visible.append(body)
            await asyncio.sleep(0.05)
            return "transport:r"

        results = await asyncio.gather(
            j1.deliver("reply-2", "x", slow, now=0.0),
            j2.deliver("reply-2", "x", slow, now=0.0),
        )
        self.assertEqual(len(visible), 1)
        self.assertEqual(sum(r["state"] == "delivered" for r in results), 1)

    async def test_empty_transport_receipt_surfaces_uncertain_without_resend(self):
        visible = []

        async def post_empty_receipt(reply_id, body):
            visible.append(body)
            return ""

        first = await self.journal.deliver("reply-1", "body", post_empty_receipt, now=1.0)
        self.assertEqual(first["state"], "uncertain")
        replay = await self.journal.deliver("reply-1", "body", AsyncMock(return_value="transport:late"), now=999.0)
        self.assertEqual(replay["state"], "uncertain")
        self.assertEqual(len(visible), 1)

    async def test_hung_transport_times_out(self):
        async def hang(reply_id, body):
            await asyncio.sleep(5.0)

        with patch("webbob.chat_reply.SEND_TIMEOUT_SECONDS", 0.2):
            started = asyncio.get_event_loop().time()
            result = await self.journal.deliver("reply-1", "body", hang, now=1.0)
            elapsed = asyncio.get_event_loop().time() - started
        self.assertLess(elapsed, 2.0)
        self.assertEqual(result["state"], "failed_retry")
        self.assertIsNone(result["receipt"])

    async def test_restart_preserves_delivered_receipt_without_resend(self):
        send = AsyncMock(return_value="transport:persist")
        await self.journal.deliver("reply-1", "stable", send, now=20.0)
        restarted = ChatReplyJournal(self.path, self.CONV)
        again = await restarted.deliver("reply-1", "stable", send, now=21.0)
        self.assertEqual(again["state"], "delivered")
        self.assertEqual(again["receipt"], "transport:persist")
        send.assert_awaited_once()

    def test_conversation_mismatch_rejected(self):
        self.journal.prepare("reply-1", "hello")
        other = ChatReplyJournal(self.path, "bob-chat:conv-2")
        with self.assertRaises(ChatReplyError):
            other.status("reply-1")

    def test_store_file_permissions(self):
        mode = self.path.stat().st_mode & 0o777
        self.assertEqual(mode, 0o600)

    def test_symlink_reply_store_rejected(self):
        link = self.path.parent / "linked.sqlite"
        link.symlink_to(self.path)
        with self.assertRaises(ChatReplyError):
            ChatReplyJournal(link, self.CONV)

    async def test_chat_reply_error_after_post_surfaces_uncertain_without_retry(self):
        visible = []

        async def post_then_error(reply_id, body):
            visible.append(body)
            raise ChatReplyError("adapter validation")

        first = await self.journal.deliver("reply-1", "body", post_then_error, now=1.0)
        self.assertEqual(first["state"], "uncertain")
        self.assertNotEqual(first["state"], "failed_retry")
        send = AsyncMock(return_value="transport:late")
        again = await self.journal.deliver("reply-1", "body", send, now=999.0)
        self.assertEqual(again["state"], "uncertain")
        self.assertEqual(len(visible), 1)
        send.assert_not_awaited()

    async def test_cancelled_error_surfaces_uncertain_and_propagates(self):
        visible = []

        async def post_cancel(reply_id, body):
            visible.append(body)
            raise asyncio.CancelledError()

        with self.assertRaises(asyncio.CancelledError):
            await self.journal.deliver("reply-1", "body", post_cancel, now=1.0)
        self.assertEqual(self.journal.status("reply-1")["state"], "uncertain")
        send = AsyncMock(return_value="transport:late")
        again = await self.journal.deliver("reply-1", "body", send, now=999.0)
        self.assertEqual(again["state"], "uncertain")
        self.assertEqual(len(visible), 1)
        send.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
