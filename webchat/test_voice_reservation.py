"""Delayed token requests stay reserved and never revive ended calls."""
import copy
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from unittest.mock import patch

from app import RequestError
from test_webchat import Fixture
from voice import VoiceError


class VoiceReservationTests(Fixture):
    def test_explicit_deferred_transport_stops_before_token_factory(self):
        import generation_budget
        with patch('generation_budget.transport_allowed',side_effect=generation_budget.AdmissionDenied('deferred')), \
                patch.object(self.chat.voice,'token_factory') as factory:
            with self.assertRaises(VoiceError) as error:self.chat.voice.start(self.identifier,'owner')
            self.assertEqual(error.exception.status,503)
            factory.assert_not_called()
            self.assertFalse(self.chat.voice.calls)
    def setUp(self):
        super().setUp()
        self.fake.snapshot = lambda **_: []
        self.owner = "reservation-owner"

    @contextmanager
    def pending(self):
        entered, release = threading.Event(), threading.Event()

        def mint(*_):
            entered.set()
            if not release.wait(5):
                raise AssertionError("Fixture token request was not released")
            return "auth_tokens/private-delayed-fixture"

        with patch.object(self.chat.voice, "token_factory", side_effect=mint) as factory:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(self.chat.voice.start, self.identifier, self.owner)
                try:
                    self.assertTrue(entered.wait(2))
                    call_id, call = next(iter(self.chat.voice.calls.items()))
                    yield future, release, call_id, call, factory
                finally:
                    release.set()

    def test_logout_during_token_request_never_returns_a_credential(self):
        with self.pending() as (future, release, call_id, call, factory):
            self.chat.voice.logout(self.owner)
            release.set()
            with self.assertRaises(VoiceError) as error:
                future.result(3)
            self.assertEqual(error.exception.status, 410)
            self.assertTrue(call["ended"])
            self.assertEqual(factory.call_count, 1)
        self.assertFalse(self.chat.voice.active(self.identifier))

    def test_expired_token_reservation_never_returns_a_credential(self):
        with self.pending() as (future, release, call_id, call, factory):
            call["lease_expires"] = time.time() - 1
            release.set()
            with self.assertRaises(VoiceError) as error:
                future.result(3)
            self.assertEqual(error.exception.status, 410)
            self.assertTrue(call["ended"])
        self.assertEqual(self.chat.history(self.identifier)["messages"], [])

    def test_ended_pending_token_still_blocks_overlapping_typed_work(self):
        before = copy.deepcopy(self.chat.get(self.identifier))
        with self.pending() as (future, release, call_id, call, factory):
            self.chat.voice.end(call_id, self.owner)
            with self.assertRaises(RequestError) as error:
                self.chat.submit(self.identifier, "What can you do?", str(uuid.uuid4()))
            self.assertEqual(error.exception.status, 409)
            self.assertEqual(self.chat.get(self.identifier), before)
            release.set()
            with self.assertRaises(VoiceError):
                future.result(3)
        self.chat.submit(self.identifier, "What can you do?", str(uuid.uuid4()))
        self.assertEqual(self.chat.history(self.identifier)["messages"][-1]["status"], "done")

    def test_expired_pending_token_cannot_be_replaced_by_another_call(self):
        with self.pending() as (future, release, call_id, call, factory):
            call["lease_expires"] = time.time() - 1
            with self.assertRaises(VoiceError) as error:
                self.chat.voice.start(self.identifier, "another-session")
            self.assertEqual(error.exception.status, 409)
            self.assertEqual(factory.call_count, 1)
            release.set()
            with self.assertRaises(VoiceError):
                future.result(3)

    def test_server_closing_discards_a_delayed_token(self):
        with self.pending() as (future, release, call_id, call, factory):
            self.chat.closing.set()
            release.set()
            with self.assertRaises(VoiceError):
                future.result(3)
            self.assertTrue(call["ended"])

    def test_pending_cancelled_request_defers_reminder_until_completion(self):
        self.chat.reminders.create(self.identifier, "fixture-reminder", "Fixture reminder", time.time() + 1)
        self.chat.reminders.clock = lambda: time.time() + 2
        with self.pending() as (future, release, call_id, call, factory):
            self.chat.voice.end(call_id, self.owner)
            self.chat.deliver_reminders()
            self.assertEqual(self.chat.reminders.listing()[0]["state"], "pending")
            self.assertEqual(self.chat.history(self.identifier)["messages"], [])
            release.set()
            with self.assertRaises(VoiceError):
                future.result(3)
        self.chat.deliver_reminders()
        self.assertEqual(self.chat.reminders.listing()[0]["state"], "fired")
        self.assertEqual(len(self.chat.history(self.identifier)["messages"]), 1)

    def test_pending_requests_count_toward_global_limit_after_expiry(self):
        entered, release = [threading.Event(), threading.Event()], threading.Event()
        second, third = self.chat.new_conversation()["id"], self.chat.new_conversation()["id"]
        counter = []

        def mint(*_):
            index = len(counter)
            counter.append(index)
            entered[index].set()
            if not release.wait(5):
                raise AssertionError("Fixture token requests were not released")
            return "auth_tokens/fixture"

        with patch.object(self.chat.voice, "token_factory", side_effect=mint):
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(self.chat.voice.start, self.identifier, self.owner)
                self.assertTrue(entered[0].wait(2))
                other = pool.submit(self.chat.voice.start, second, self.owner)
                try:
                    self.assertTrue(entered[1].wait(2))
                    for call in self.chat.voice.calls.values():
                        call["expires"] = time.time() - 4000
                        call["ended"] = True
                    with self.assertRaises(VoiceError) as error:
                        self.chat.voice.start(third, "another-owner")
                    self.assertEqual(error.exception.status, 429)
                    self.assertEqual(len(counter), 2)
                    self.assertEqual(len(self.chat.voice.calls), 2)
                finally:
                    release.set()
                for future in (first, other):
                    with self.assertRaises(VoiceError):
                        future.result(3)
        self.assertFalse(any(c.get("starting") for c in self.chat.voice.calls.values()))

    def test_failed_token_releases_reservation_without_refunding_attempt(self):
        with patch.object(self.chat.voice, "token_factory", side_effect=VoiceError(503, "Fixture failure")):
            with self.assertRaises(VoiceError):
                self.chat.voice.start(self.identifier, self.owner)
        self.assertFalse(self.chat.voice.busy(self.identifier))
        self.assertEqual(len(self.chat.voice.token_attempts[self.owner]), 1)
        with patch.object(self.chat.voice, "token_factory", return_value="auth_tokens/fixture"):
            self.assertIn("call_id", self.chat.voice.start(self.identifier, self.owner))

    def test_successful_delayed_start_gets_a_fresh_bounded_heartbeat_lease(self):
        with self.pending() as (future, release, call_id, call, factory):
            call["lease_expires"] = time.time() + 3
            release.set()
            result = future.result(3)
            self.assertEqual(result["call_id"], call_id)
            self.assertGreater(call["lease_expires"] - time.time(), 40)
            self.assertLessEqual(call["lease_expires"], call["expires"])
            self.assertFalse(call["starting"])

    def test_logout_while_context_loads_prevents_provider_request(self):
        entered, release = threading.Event(), threading.Event()

        def snapshot(**_):
            entered.set()
            if not release.wait(5):
                raise AssertionError("Fixture snapshot was not released")
            return []

        with patch.object(self.fake, "snapshot", side_effect=snapshot), \
                patch.object(self.chat.voice, "token_factory", return_value="auth_tokens/fixture") as mint:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(self.chat.voice.start, self.identifier, self.owner)
                try:
                    self.assertTrue(entered.wait(2))
                    self.chat.voice.logout(self.owner)
                finally:
                    release.set()
                with self.assertRaises(VoiceError):
                    future.result(3)
            mint.assert_not_called()
