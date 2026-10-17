"""Untrusted text must reject the entire Tags block before normalization."""
import copy
from contextlib import nullcontext
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from webbob.ai_capacity import sanitize_capacity_snapshot, validate_document
from webbob.backup import validate as validate_backup
from webbob.fallback import fallback_notice
from webbob.ownership import Gate, GateError, norm_id, toks
from webbob.parity_gate import CAPABILITIES, RECOVERY, GoLiveDenied, ParityGate
from webbob.phone_access import REQUIRED, evaluate_phone_access
from webbob.pr_ops import DraftPublisher, GateDenied, ReviewGate
from webbob.release_board import validate_release_record
from webbob.restricted_fetch import FetchDenied, fetch_page, validate_url
from webbob.shared_context import ContextError, safe_fact, validate_fact
from webbob.spend_cap import SpendCap, match_capacity_row, provider_quota_check
from webbob.status_view import capacity_rows, status_rows
from webbob.tool_host import ToolHost, ToolUnavailable
from webbob.trial_tracker import record_result, trial_template
from webbob.voice_memo_policy import VoiceMemoPolicyError, reject_voice_content
from webbob.workspace import Drafts, Workspace, WorkspaceError


BOUNDARIES = (0xE0000, 0xE0001, 0xE007F)
NEIGHBORS = (0xE0080, 0xDFFFF)
SURROGATES = (0xD800, 0xDB40, 0xDC01, 0xDFFF)


def samples(points):
    for point in points:
        char = chr(point)
        for value in (char, char + "Chicago", "Chi" + char + "cago", "Chicago" + char):
            yield point, value


def capacity(value):
    return {"schema": "ai-capacity/v1", "generated_ts": 1, "host": value,
            "rows": [{"provider": "codex", "note": "ready"}]}


def fact(value):
    return {"id": "preference", "body": value, "classification": "accepted_fact",
            "audience": ["bob"], "provenance": {"kind": "reviewed_fact", "uri": "review:123",
            "sha256": "a" * 64, "accepted_by": "jeff", "accepted_at": "2026-10-16"}}


def release(value):
    return {"repo": "rupret007/bob-brain", "owner": "webbob", "claim_id": value, "pr": 7,
            "sha": "a" * 40, "status": "PROPOSED", "evidence": ["tests:pending"],
            "karen_receipt": None, "jeff_receipt": None, "handoff": "BOB-HANDOFF.md"}


class UnicodeTagTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.drafts = Drafts(self.root / "drafts.sqlite", "owner@example.org", "chat1",
                             verify_consent=lambda *_: False, ownership=lambda _: nullcontext())
        self.spend = SpendCap(self.root / "spend.sqlite", {"brave": 100})
        self.post_review = Mock()
        self.review = ReviewGate(self.root / "review.sqlite", post_review=self.post_review,
                                 verify_karen=lambda *_: False, verify_jeff=lambda *_: False)

    def validators(self):
        return (
            ("fact", ContextError, safe_fact),
            ("fact record", ContextError, lambda s: validate_fact(fact(s))),
            ("capacity validation", ValueError, lambda s: validate_document(capacity(s))),
            ("capacity sanitization", ValueError, lambda s: sanitize_capacity_snapshot(capacity(s))),
            ("voice value", VoiceMemoPolicyError, reject_voice_content),
            ("voice key", VoiceMemoPolicyError, lambda s: reject_voice_content({s: "Chicago"})),
            ("nested voice key", VoiceMemoPolicyError, lambda s: reject_voice_content({"settings": {s: "Chicago"}})),
            ("URL", FetchDenied, lambda s: validate_url("https://example.org/" + s)),
            ("email body", WorkspaceError, lambda s: self.drafts.prepare("email", {
                "to": "recipient@example.org", "subject": "Subject", "body": s})),
            ("release record", ValueError, lambda s: validate_release_record(release(s))),
            ("provider model", ValueError, lambda s: provider_quota_check(s, None)),
            ("capacity row matching", ValueError, lambda s: match_capacity_row("codex", [{"provider": s}])),
            ("capacity rendering", ValueError, lambda s: capacity_rows({"rows": [{"provider": s}]})),
            ("status rendering", ValueError, lambda s: status_rows({"bob": {"state": s}})),
            ("fallback status", ValueError, lambda s: fallback_notice({"webbob": {"status": s}})),
            ("phone evidence", ValueError, lambda s: evaluate_phone_access("a" * 40, {
                name: {"sha": "a" * 40, "result": "PASS", "receipt": s} for name in REQUIRED})),
            ("parity evidence", GoLiveDenied, lambda s: ParityGate(
                lambda *_: True, lambda *_: True, lambda *_: True).require("a" * 40, {
                    name: {"sha": "a" * 40, "result": "PASS", "receipt": s}
                    for name in (*CAPABILITIES, *RECOVERY)}, "karen", "jeff")),
            ("claim identity", GateError, norm_id),
            ("claim title", GateError, toks),
            ("spend call ID", ValueError, lambda s: self.spend.reserve(s, "brave", 1)),
            ("review evidence", GateDenied, lambda s: self.review.request_review(
                "rupret007/bob-brain", 7, "a" * 40, "scope", [s])),
            ("trial receipt", ValueError, lambda s: record_result(
                trial_template("2026-10-16", "a" * 40), "2026-10-16", "daily_brief", "webbob",
                result="PASS", receipt=s, latency_ms=None, cost_microdollars=None, build="a" * 40)),
        )

    def test_boundaries_and_mixed_text_rejected_at_every_boundary(self):
        for name, error, validate in self.validators():
            for point, value in samples(BOUNDARIES):
                with self.subTest(boundary=name, point=hex(point), value=ascii(value)):
                    with self.assertRaises(error):
                        validate(value)
        self.post_review.assert_not_called()
        with self.drafts.db() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM drafts").fetchone()[0], 0)
        with self.spend.db() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM spend").fetchone()[0], 0)

    def test_entire_tags_block_rejected_in_facts(self):
        for point in range(0xE0000, 0xE0080):
            with self.subTest(point=hex(point)):
                with self.assertRaises(ContextError):
                    safe_fact("Chicago" + chr(point))

    def _assert_safe_fact_context_error(self, body, message_fragment):
        with self.assertRaises(Exception) as caught:
            safe_fact(body)
        self.assertIsInstance(caught.exception, ContextError)
        self.assertIn(message_fragment, str(caught.exception).lower())

    def test_lone_surrogates_rejected_with_context_error(self):
        for point in SURROGATES:
            char = chr(point)
            with self.subTest(point=hex(point)):
                self._assert_safe_fact_context_error("Release notes ready" + char, "surrogate")
        self._assert_safe_fact_context_error("Release notes ready\udb40\udc01", "surrogate")

    def test_tag_rejection_uses_context_error(self):
        self._assert_safe_fact_context_error("Release notes ready" + chr(0xE0001), "unicode tag")

    def test_u_e0080_allowed_in_facts(self):
        body = "Release notes ready" + chr(0xE0080)
        self.assertEqual(safe_fact(body), body)

    def test_ownership_claim_rejects_tag_before_coordination(self):
        claims = self.root / "claims"
        claims.mkdir()
        with patch("webbob.ownership.CLAIMS", str(claims)):
            tag = chr(0xE0001)
            with self.assertRaises(GateError) as caught:
                Gate("karen").claim(
                    "rupret007/bob-brain", "work-one",
                    ["repo:rupret007/bob-brain/webbob/text_validation.py"],
                    branch="draft/example", title="title" + tag)
            self.assertIn("Unicode tag", str(caught.exception))
            self.assertEqual(list(claims.glob("*.json")), [])

    def test_neighbors_remain_valid_at_free_text_boundaries(self):
        # Existing ASCII-only identity schemas retain their own restrictions.
        for point, value in samples(NEIGHBORS):
            for name, _, validate in self.validators():
                with self.subTest(boundary=name, point=hex(point), value=ascii(value)):
                    validate(value)
            self.assertEqual(safe_fact(value), value)
            self.assertEqual(sanitize_capacity_snapshot(capacity(value))["host"], value)
            self.assertEqual(validate_url("https://example.org/" + value).path, "/" + value)

    def test_capacity_checks_all_fields_and_keys_before_dropping_any(self):
        for point in BOUNDARIES:
            value = "ready" + chr(point)
            documents = []
            for key in ("host", "snapshot_note", "generated_ct", "extra"):
                documents.append(dict(capacity("host"), **{key: value}))
            for key in ("provider", "source", "note", "reset_ct", "status", "freshness", "extra"):
                doc = capacity("host")
                doc["rows"][0][key] = value
                documents.append(doc)
            documents.append(dict(capacity("host"), **{value: "safe"}))
            documents.append(dict(capacity("host"), extra={"nested": [value]}))
            for doc in documents:
                for validate in (validate_document, sanitize_capacity_snapshot):
                    with self.subTest(point=hex(point), document=ascii(doc), validator=validate.__name__):
                        before = copy.deepcopy(doc)
                        with self.assertRaises(ValueError):
                            validate(doc)
                        self.assertEqual(doc, before)

    def test_provenance_and_backup_reject_tags(self):
        config = {"timezone": "America/Chicago", "release_sha": "a" * 40,
                  "model_caps_microdollars": {}, "routines_paused": True}
        for point in BOUNDARIES + NEIGHBORS:
            for field in ("uri", "accepted_by", "accepted_at"):
                record = fact("Chicago")
                record["provenance"][field] += chr(point)
                backup = {k: v for k, v in record.items() if k != "audience"}
                backup.update(revision=1, at=1, execution_authority=False)
                for validate in (lambda: validate_fact(record), lambda: validate_backup([backup], config)):
                    with self.subTest(point=hex(point), field=field):
                        if point in BOUNDARIES:
                            with self.assertRaises(ValueError):
                                validate()
                        else:
                            validate()


class AsyncUnicodeTagTests(unittest.IsolatedAsyncioTestCase):
    def session(self, text):
        return SimpleNamespace(call_tool=AsyncMock(return_value=SimpleNamespace(
            isError=False, content=[SimpleNamespace(type="text", text=text)])))

    async def test_research_inputs_and_decoded_outputs(self):
        for point in BOUNDARIES + NEIGHBORS:
            value = "Chicago" + chr(point)
            session = self.session(json.dumps({"text": value}))  # Escaped JSON tags must also fail.
            host = ToolHost({"fetch": session}, spend_cap=Mock(), daily_cap=Mock())
            if point in BOUNDARIES:
                with self.assertRaises(ValueError):
                    await host.research(value)
                with self.assertRaises(ToolUnavailable):
                    await host.call("fetch", {"url": "https://example.org/" + value})
                session.call_tool.assert_not_awaited()
                with self.assertRaises(ToolUnavailable):
                    await host.call("fetch", {"url": "https://example.org/"})
            else:
                self.assertEqual((await host.research(value))["query"], value)
                self.assertEqual(await host.call("fetch", {"url": "https://example.org/"}), [{"text": value}])

    async def test_workspace_inputs_and_outputs_before_truncation(self):
        for point in BOUNDARIES + NEIGHBORS:
            value = "Chicago" + chr(point)
            session = self.session("x" * 16000 + value)
            workspace = Workspace(session, account="owner@example.org", consent_verified=True)
            if point in BOUNDARIES:
                with self.assertRaises(WorkspaceError):
                    await workspace.read("search_gmail_messages", {"query": value})
                session.call_tool.assert_not_awaited()
                with self.assertRaises(WorkspaceError):
                    await workspace.read("search_gmail_messages", {"query": "Chicago"})
            else:
                result = await workspace.read("search_gmail_messages", {"query": value})
                self.assertTrue(result["truncated"])
                self.assertEqual(result["source_arguments"]["query"], value)

    async def test_fetch_rejects_before_html_extraction_or_truncation(self):
        for point in BOUNDARIES + NEIGHBORS:
            for content_type in ("text/plain", "text/html"):
                body = ("<p>Chicago</p>" + " " * 8000 + "<!--" + chr(point) + "-->").encode()
                with patch("webbob.restricted_fetch.download", new=AsyncMock(return_value=(
                        200, "https://example.org/", content_type, body))):
                    with self.subTest(point=hex(point), content_type=content_type):
                        if point in BOUNDARIES:
                            with self.assertRaises(FetchDenied):
                                await fetch_page("https://example.org/")
                        else:
                            self.assertTrue((await fetch_page("https://example.org/"))["text"])

    async def test_draft_publication_rejects_before_callbacks(self):
        with tempfile.TemporaryDirectory() as directory:
            session = self.session("ok")
            ownership = Mock(return_value=nullcontext())
            publisher = DraftPublisher(session, ownership=ownership, verify_publish=Mock(return_value=True),
                                       read_branch_sha=AsyncMock(return_value="a" * 40), read_pr=AsyncMock(),
                                       receipt_path=Path(directory) / "publish.sqlite")
            for point, value in samples(BOUNDARIES):
                for title, body in ((value, "body"), ("title", value)):
                    with self.subTest(point=hex(point), title=ascii(title), body=ascii(body)):
                        with self.assertRaises(GateDenied):
                            await publisher.publish("rupret007/bob-brain", "draft/example", "a" * 40,
                                                    title, body, "approval")
            ownership.assert_not_called()
            session.call_tool.assert_not_awaited()
