import copy
from contextlib import nullcontext
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

from webbob.workspace import Drafts, NEEDS_JEFF, Workspace, WorkspaceError


class WorkspaceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "private.sqlite"
        self.approvals = {}
        self.verify = lambda digest, proof: self.approvals.pop(proof, None) == digest
        self.drafts = Drafts(self.path, "owner@example.org", "chat1", verify_consent=self.verify, ownership=lambda _: nullcontext())
        self.email = {"to": "recipient@example.org", "subject": "Subject", "body": "Exact body"}
        self.event = {"calendar_id": "primary", "summary": "Review", "start_time": "2026-10-17T10:00:00-05:00",
                      "end_time": "2026-10-17T11:00:00-05:00", "timezone": "America/Chicago"}
        self.response = SimpleNamespace(isError=False, content=[SimpleNamespace(type="text", text="source evidence")],
                                        model_dump=lambda **kw: {"receipt": "provider1"})
        self.session = SimpleNamespace(call_tool=AsyncMock(return_value=self.response))

    def approve(self, draft):
        proof = "proof" + draft["digest"]
        self.approvals[proof] = draft["digest"]
        return proof

    async def test_no_oauth_no_network_before_jeff_consent(self):
        workspace = Workspace(self.session, account="owner@example.org")
        with self.assertRaisesRegex(WorkspaceError, NEEDS_JEFF):
            await workspace.read("search_gmail_messages", {"query": "today"})
        self.session.call_tool.assert_not_awaited()

    async def test_read_first_sourced_brief_document_search_and_read(self):
        workspace = Workspace(self.session, account="owner@example.org", consent_verified=True)
        brief = await workspace.daily_brief("2026-10-16T00:00:00-05:00", "2026-10-17T00:00:00-05:00")
        self.assertEqual([r["source_tool"] for r in brief], ["search_gmail_messages", "get_events"])
        self.assertTrue(all(r["text"] == "source evidence" and r["retrieved_at"] for r in brief))
        await workspace.locate_document("name contains 'plan'")
        await workspace.read("get_drive_file_content", {"file_id": "selected-id"})
        await workspace.read("get_gmail_message_content", {"message_id": "selected-message"})
        for tool, args in [call.args for call in self.session.call_tool.call_args_list]:
            self.assertEqual(args["user_google_email"], "owner@example.org")
        with self.assertRaises(WorkspaceError):
            await workspace.read("send_gmail_message", self.email)

    async def test_recipient_body_and_event_time_edits_invalidate_prior_approval(self):
        for kind, payload, field, value in [("email", self.email, "to", "different@example.org"),
                                           ("email", self.email, "body", "Changed body"),
                                           ("event", self.event, "start_time", "2026-10-17T10:30:00-05:00")]:
            original = self.drafts.prepare(kind, payload)
            proof = self.approve(original)
            changed = dict(payload, **{field: value})
            revised = self.drafts.prepare(kind, changed, original["id"])
            self.assertNotEqual(original["digest"], revised["digest"])
            with self.assertRaises(WorkspaceError):
                await self.drafts.execute(original["id"], original["digest"], proof, self.session, writes_enabled=True)
        self.session.call_tool.assert_not_awaited()

    async def test_writes_disabled_by_default_and_forged_consent_denied(self):
        draft = self.drafts.prepare("email", self.email)
        with self.assertRaises(WorkspaceError):
            await self.drafts.execute(draft["id"], draft["digest"], self.approve(draft), self.session)
        with self.assertRaises(WorkspaceError):
            await self.drafts.execute(draft["id"], draft["digest"], "forged", self.session, writes_enabled=True)
        self.session.call_tool.assert_not_awaited()

    async def test_lost_response_uncertain_persists_and_does_not_duplicate(self):
        draft = self.drafts.prepare("email", self.email)
        proof = self.approve(draft)
        self.session.call_tool.side_effect = TimeoutError("lost response")
        receipt = await self.drafts.execute(draft["id"], draft["digest"], proof, self.session, writes_enabled=True)
        self.assertEqual(receipt["state"], "uncertain")
        restarted = Drafts(self.path, "owner@example.org", "chat1", verify_consent=self.verify, ownership=lambda _: nullcontext())
        receipt = await restarted.execute(draft["id"], draft["digest"], proof, self.session, writes_enabled=True)
        self.assertEqual(receipt["state"], "uncertain")
        self.assertEqual(self.session.call_tool.await_count, 1)

    async def test_approved_draft_exact_payload_and_receipt_reuse(self):
        draft = self.drafts.prepare("email", self.email)
        proof = self.approve(draft)
        receipt = await self.drafts.execute(draft["id"], draft["digest"], proof, self.session, writes_enabled=True)
        self.assertEqual(receipt["state"], "submitted")
        self.assertEqual(self.session.call_tool.call_args.args,
                         ("send_gmail_message", dict(self.email, user_google_email="owner@example.org",
                          body_format="plain", include_signature=False, quote_original=False, reply_all=False)))
        await self.drafts.execute(draft["id"], draft["digest"], proof, self.session, writes_enabled=True)
        self.assertEqual(self.session.call_tool.await_count, 1)

    async def test_other_conversation_and_expired_ownership_cannot_send(self):
        draft = self.drafts.prepare("email", self.email)
        other = Drafts(self.path, "owner@example.org", "chat2", verify_consent=self.verify, ownership=lambda _: nullcontext())
        with self.assertRaises(WorkspaceError):
            other.receipt(draft["id"])
        def denied(_):
            raise WorkspaceError("lease expired")
        self.drafts.ownership = denied
        with self.assertRaises(WorkspaceError):
            await self.drafts.execute(draft["id"], draft["digest"], self.approve(draft), self.session, writes_enabled=True)
        self.session.call_tool.assert_not_awaited()

    async def test_scope_manifest_read_first_and_oauth_pending(self):
        config = json.loads((Path(__file__).resolve().parents[1] / "config/workspace.json").read_text())
        self.assertEqual(config["status"], NEEDS_JEFF)
        self.assertFalse(config["writes_enabled"])
        self.assertEqual(set(config["scopes"]), {"openid", "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile", "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/calendar.readonly", "https://www.googleapis.com/auth/drive.readonly"})


if __name__ == "__main__":
    unittest.main()
