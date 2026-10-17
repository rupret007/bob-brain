"""Karen repro r158 — must stay green on the Web Bob chat reply journal."""
import asyncio
import inspect
import sys
import tempfile
import unittest
from pathlib import Path

from webbob import chat_reply
from webbob.chat_reply import ChatReplyJournal


class KarenR158Repro(unittest.TestCase):
    def test_r158_script_expectations(self):
        visible = []

        async def send_delivered_then_timeout(reply_id, body):
            visible.append(body)
            raise asyncio.TimeoutError()

        async def send_5xx_after_commit(reply_id, body):
            visible.append(body)
            raise RuntimeError("502 Bad Gateway from proxy after upstream commit")

        async def ok(reply_id, body):
            visible.append(body)
            return "rcpt"

        async def main():
            for name, first_send in (
                ("timeout", send_delivered_then_timeout),
                ("5xx", send_5xx_after_commit),
            ):
                visible.clear()
                journal = ChatReplyJournal(Path(tempfile.mkdtemp()) / "r.sqlite", "bob-chat:conv-1")
                a = await journal.deliver("reply-1", "hello Jeff", first_send, now=0)
                b = await journal.deliver("reply-1", "hello Jeff", ok, now=a["next_retry_at"] or 999_999)
                self.assertEqual(a["state"], "uncertain", name)
                self.assertEqual(b["state"], "uncertain", name)
                self.assertEqual(len(visible), 1, name)

            visible.clear()
            shared = Path(tempfile.mkdtemp()) / "r.sqlite"
            j1 = ChatReplyJournal(shared, "bob-chat:conv-1")
            j2 = ChatReplyJournal(shared, "bob-chat:conv-1")

            async def slow(reply_id, body):
                visible.append(body)
                await asyncio.sleep(0.05)
                return "r"

            rs = await asyncio.gather(
                j1.deliver("reply-2", "x", slow, now=0),
                j2.deliver("reply-2", "x", slow, now=0),
            )
            self.assertEqual(len(visible), 1)
            self.assertEqual(sum(r["state"] == "delivered" for r in rs), 1)

            visible.clear()
            journal = ChatReplyJournal(shared, "bob-chat:conv-1")
            journal.prepare("reply-3", "y")
            with journal.db() as db:
                db.execute("UPDATE replies SET state='in_flight', attempts=1, updated_at=0 WHERE id='reply-3'")
            r = await journal.deliver("reply-3", "y", ok, now=999_999)
            self.assertEqual(r["state"], "uncertain")
            self.assertEqual(len(visible), 0)

            source = inspect.getsource(chat_reply.ChatReplyJournal.deliver)
            self.assertIn("guarded_send(reply_id, body)", source)

        asyncio.run(main())


if __name__ == "__main__":
    unittest.main()
