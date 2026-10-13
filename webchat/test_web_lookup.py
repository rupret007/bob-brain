"""Honest DuckDuckGo Instant Answer receipts. Injected HTTP only; no live fetch."""
import json
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import URLError

from app import Chat
from bob_gaps import format_web_search_reply, lookup_web, web_lookup_receipt, web_search


FORBIDDEN_CLAIMS = (
    "i searched the web",
    "full search",
    "full web search",
    "opened the page",
    "opened the source",
    "read the page",
    "pages were opened",
    "visited the page",
    "verified the page",
    "crawled",
    "scraped",
)


class FakeProviders:
    def health(self, conversation_id=None):
        return {"providers": {}, "order": [], "fast_order": []}


def _response(payload, raw=None):
    body = raw if raw is not None else json.dumps(payload).encode()
    handle = MagicMock()
    handle.__enter__.return_value = handle
    handle.read.return_value = body
    return handle


class WebLookupHonestyTests(unittest.TestCase):
    def setUp(self):
        self.network = patch(
            "urllib.request.OpenerDirector.open",
            side_effect=AssertionError("Network forbidden"),
        )
        self.network.start()
        self.addCleanup(self.network.stop)

    def assert_honest(self, text, *, secret=None):
        lowered = text.lower()
        for claim in FORBIDDEN_CLAIMS:
            self.assertNotIn(claim, lowered, claim)
        self.assertIn("source pages were not opened", lowered)
        if secret:
            self.assertNotIn(secret, text)

    def test_abstract_identifies_instant_answer_and_keeps_unopened_link(self):
        result = web_search(
            "Python",
            opener=lambda *args, **kwargs: _response(dict(
                AbstractText="Python is a language.",
                AbstractURL="https://www.python.org/",
                Heading="Python",
            )),
        )
        reply = web_lookup_receipt("Python", result)
        self.assertEqual(result["status"], "ok")
        self.assertIn("DuckDuckGo Instant Answer", reply)
        self.assertIn("Python is a language.", reply)
        self.assertIn("https://www.python.org/", reply)
        self.assertIn("not verified page evidence", reply)
        self.assert_honest(reply)

    def test_related_topic_keeps_firsturl_without_page_read_claim(self):
        result = web_search(
            "Python",
            opener=lambda *args, **kwargs: _response(dict(
                AbstractText="",
                AbstractURL="https://unused.example/abstract",
                RelatedTopics=[dict(Text="Related topic about Python.", FirstURL="https://en.wikipedia.org/wiki/Python")],
            )),
        )
        reply = web_lookup_receipt("Python", result)
        self.assertEqual(result["status"], "ok")
        self.assertIn("Related topic about Python.", reply)
        self.assertIn("https://en.wikipedia.org/wiki/Python", reply)
        self.assertNotIn("https://unused.example/abstract", reply)
        self.assert_honest(reply)

    def test_empty_is_no_answer_not_a_transport_failure(self):
        result = web_search("obscure-query", opener=lambda *args, **kwargs: _response({}))
        reply = web_lookup_receipt("obscure-query", result)
        self.assertEqual(result["status"], "empty")
        self.assertIn("no instant answer", reply.lower())
        self.assertIn("obscure-query", reply)
        self.assertNotIn("lookup failed", reply.lower())
        self.assertNotIn("http_error", reply)
        self.assert_honest(reply)

    def test_empty_does_not_cite_unused_abstract_url(self):
        result = web_search(
            "empty-cite",
            opener=lambda *args, **kwargs: _response(dict(
                AbstractText="",
                AbstractURL="https://invented.example/citation",
                Heading="Unused",
            )),
        )
        reply = web_lookup_receipt("empty-cite", result)
        self.assertEqual(result["status"], "empty")
        self.assertNotIn("https://invented.example/citation", reply)
        self.assertNotIn("Unused —", reply)
        self.assert_honest(reply)

    def test_malformed_object_is_unreadable_not_an_answer(self):
        opener = lambda *args, **kwargs: _response(None, raw=b"[]")
        with self.assertRaises(ValueError):
            web_search("bad", opener=opener)
        reply = lookup_web("bad", opener=opener)
        self.assertIn("malformed or unreadable", reply.lower())
        self.assertNotIn("no instant answer", reply.lower())
        self.assert_honest(reply)

    def test_failed_http_is_transport_failure_without_exception_text(self):
        secret = "token=SUPER_SECRET_LOOKUP_VALUE"
        opener = MagicMock(side_effect=URLError(secret))
        reply = lookup_web("Python", opener=opener)
        self.assertIn("lookup failed", reply.lower())
        self.assertIn("http_error", reply)
        self.assertNotIn("no instant answer", reply.lower())
        self.assert_honest(reply, secret=secret)
        opener.assert_called_once()

    def test_timeout_is_transport_failure_without_exception_text(self):
        secret = "timed out contacting api.internal/secret-path"
        opener = MagicMock(side_effect=TimeoutError(secret))
        reply = lookup_web("Python", opener=opener)
        self.assertIn("lookup failed", reply.lower())
        self.assertIn("timeout", reply)
        self.assert_honest(reply, secret=secret)
        opener.assert_called_once()

    def test_formatter_injects_abstract_related_empty_malformed_and_failed(self):
        abstract = web_lookup_receipt("q", dict(
            status="ok", answer="An instant answer.", source="https://example.com/a"))
        related = web_lookup_receipt("q", dict(
            status="ok", answer="A related topic.", source="https://example.com/r"))
        empty = web_lookup_receipt("lonely query", dict(status="empty"))
        malformed = web_lookup_receipt("q", ["not", "an", "object"])
        failed = web_lookup_receipt("q", dict(status="http_error", error="secret=LEAKED_TOKEN"))
        self.assertIn("An instant answer.", abstract)
        self.assertIn("https://example.com/a", abstract)
        self.assertIn("A related topic.", related)
        self.assertIn("no instant answer for lonely query", empty.lower())
        self.assertIn("malformed or unreadable", malformed.lower())
        self.assertIn("lookup failed (http_error)", failed)
        self.assertNotIn("LEAKED_TOKEN", failed)
        self.assertNotIn("secret=", failed)
        for reply in (abstract, related, empty, malformed, failed):
            self.assert_honest(reply)

    def test_single_urlopen_and_no_followup_fetch(self):
        opener = MagicMock(return_value=_response(dict(
            AbstractText="One call only.", AbstractURL="https://example.com/")))
        reply = lookup_web("Python", opener=opener)
        self.assertIn("One call only.", reply)
        self.assertEqual(opener.call_count, 1)
        self.assert_honest(reply)

    def test_javascript_and_non_http_sources_are_dropped(self):
        result = web_search(
            "x",
            opener=lambda *args, **kwargs: _response(dict(
                RelatedTopics=[dict(Text="Result", FirstURL="javascript:bad")])),
        )
        reply = web_lookup_receipt("x", result)
        self.assertIn("Result", reply)
        self.assertNotIn("javascript:", reply)
        self.assert_honest(reply)

    def test_format_web_search_reply_delegates_to_honest_receipt(self):
        reply = format_web_search_reply(dict(
            answer="Legacy shape.", source="https://www.python.org/", heading="Python"))
        self.assertIn("DuckDuckGo Instant Answer", reply)
        self.assertIn("Legacy shape.", reply)
        self.assertIn("https://www.python.org/", reply)
        self.assert_honest(reply)


class WebLookupChatTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.folder = self.root / "conductor/webchat"
        self.folder.mkdir(parents=True)
        self.chat = Chat(self.folder, self.root, FakeProviders())
        self.identifier = self.chat.conversation_list()["conversations"][0]["id"]
        guard = patch("urllib.request.OpenerDirector.open", side_effect=AssertionError("Network forbidden"))
        guard.start()
        self.addCleanup(guard.stop)
        for name in ("_screen_sessions", "process_table"):
            sampler = patch("live_status_snapshot." + name, return_value={})
            sampler.start()
            self.addCleanup(sampler.stop)

    def tearDown(self):
        self.chat.close()
        self.tmp.cleanup()

    def submit(self, text):
        return self.chat.submit(self.identifier, text, str(uuid.uuid4()))["messages"][-1]

    def assert_honest(self, text, *, secret=None):
        lowered = text.lower()
        for claim in FORBIDDEN_CLAIMS:
            self.assertNotIn(claim, lowered, claim)
        self.assertIn("source pages were not opened", lowered)
        if secret:
            self.assertNotIn(secret, text)

    def test_local_tasks_lookup_uses_instant_answer_receipt(self):
        payload = dict(
            status="ok",
            answer="Python is a programming language.",
            source="https://www.python.org/",
            heading="Python",
        )
        with patch("app.web_search", return_value=payload) as search, \
                patch("app.parse_work", side_effect=AssertionError("Lookup entered coding route")):
            reply = self.submit("look up Python programming language")
        self.assertEqual(reply["provider"], "state")
        self.assertIn("DuckDuckGo Instant Answer", reply["content"])
        self.assertIn(payload["answer"], reply["content"])
        self.assertIn(payload["source"], reply["content"])
        self.assertIn("not verified page evidence", reply["content"])
        self.assert_honest(reply["content"])
        search.assert_called_once_with("Python programming language")

    def test_direct_research_reply_uses_same_receipt(self):
        payload = dict(
            status="ok",
            answer="Mets beat the Phillies 4-2.",
            source="https://example.com/mets-score",
            heading="Mets",
        )
        with patch("app.web_search", return_value=payload):
            reply = self.submit("what was the score of the Mets game last night?")
        self.assertIn("DuckDuckGo Instant Answer", reply["content"])
        self.assertIn("4-2", reply["content"])
        self.assertIn("https://example.com/mets-score", reply["content"])
        self.assert_honest(reply["content"])

    def test_empty_and_failed_chat_paths_stay_distinct(self):
        with patch("app.web_search", return_value=dict(status="empty", answer="", source="")):
            empty = self.submit("look up totally-unknown-widget")
        self.assertIn("no instant answer", empty["content"].lower())
        self.assertNotIn("lookup failed", empty["content"].lower())
        self.assert_honest(empty["content"])
        secret = "credential=CHAT_LOOKUP_SECRET"
        with patch("app.web_search", side_effect=URLError(secret)):
            failed = self.submit("look up Python programming language")
        self.assertIn("lookup failed", failed["content"].lower())
        self.assertNotIn("no instant answer", failed["content"].lower())
        self.assert_honest(failed["content"], secret=secret)


if __name__ == "__main__":
    unittest.main()
