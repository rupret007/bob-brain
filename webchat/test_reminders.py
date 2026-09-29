"""Reminder persistence, time interpretation and real Chat delivery boundaries."""
import concurrent.futures
from datetime import datetime
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import Mock, patch
import uuid

from app import Chat
from reminders import Reminders, ReminderError, instant, parse, ZONE
from task_dispatch import task_queue
from texting_fixture import OfflineProviders


class ReminderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.now = datetime(2026, 9, 29, 9, 0, tzinfo=ZONE).timestamp()
        self.store = Reminders(self.root, clock=lambda: self.now)

    def test_relative_absolute_and_explicit_timezone(self):
        self.assertEqual(instant('in 10 minutes', self.now), self.now + 600)
        self.assertEqual(instant('tomorrow at 9am', self.now), self.now + 86400)
        self.assertEqual(instant('on 2026-09-29 at 10:00', self.now), self.now + 3600)
        self.assertEqual(instant('at 2026-09-29T15:00:00Z', self.now), self.now + 3600)

    def test_past_ambiguous_and_invalid_times_are_not_guessed(self):
        for text in ('on 2026-09-29 at 08:00', 'sometime soon', '2026-09-30T09:00', 'in 0 minutes',
                     'on 2026-11-01 at 01:30', 'on 2027-03-14 at 02:30'):
            with self.subTest(text=text), self.assertRaises(ReminderError):
                instant(text, self.now)

    def test_recurring_routine_is_an_interval(self):
        self.assertEqual(parse('set a routine every 2 hours to stretch', self.now), ('stretch', self.now + 7200, 7200))
        self.assertEqual(parse('remind me to check the oven in 10 minutes', self.now), ('check the oven', self.now + 600, None))

    def test_idempotent_concurrent_creation_survives_restart(self):
        def create(_):
            return self.store.create('chat', 'request', 'Check oven', self.now + 10)['id']
        with concurrent.futures.ThreadPoolExecutor(8) as pool:
            ids = list(pool.map(create, range(16)))
        self.assertEqual(len(set(ids)), 1)
        restored = Reminders(self.root)
        self.assertEqual(len(restored.listing()), 1)
        self.assertEqual(self.store.path.stat().st_mode & 0o777, 0o600)

    def test_cancelled_reminder_never_delivers(self):
        row = self.store.create('chat', 'request', 'Check oven', self.now + 10)
        self.store.cancel(row['id'])
        self.now += 100
        deliver = Mock()
        self.store.deliver_due(deliver)
        deliver.assert_not_called()

    def test_delivery_failure_keeps_stable_notice_for_retry(self):
        self.store.create('chat', 'request', 'Check oven', self.now + 10)
        self.now += 10
        first = Mock(return_value=False)
        self.store.deliver_due(first)
        self.assertEqual(self.store.listing()[0]['state'], 'pending')
        second = Mock(return_value=True)
        self.store.deliver_due(second)
        self.assertEqual(first.call_args.args[1], second.call_args.args[1])
        self.assertEqual(self.store.listing()[0]['state'], 'fired')
        third = Mock()
        self.store.deliver_due(third)
        third.assert_not_called()

    def test_repeating_catches_up_once_after_downtime(self):
        self.store.create('chat', 'request', 'Stretch', self.now + 60, 60)
        self.now += 3600
        deliver = Mock(return_value=True)
        self.store.deliver_due(deliver)
        deliver.assert_called_once()
        self.assertEqual(self.store.listing()[0]['due_at'], self.now + 60)
        self.assertEqual(self.store.listing()[0]['occurrences'], 1)

    def test_symlink_or_corrupt_store_is_not_overwritten(self):
        external = self.root / 'external'
        external.write_text('keep')
        self.store.path.symlink_to(external)
        with self.assertRaises(ReminderError):
            self.store.listing()
        self.assertEqual(external.read_text(), 'keep')
        self.store.path.unlink()
        self.store.path.write_text('invalid')
        with self.assertRaises(ValueError):
            self.store.create('a', 'b', 'C', self.now)
        self.assertEqual(self.store.path.read_text(), 'invalid')


class ReminderChatTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.providers = OfflineProviders()
        self.chat = Chat(self.root / 'conductor/webchat', self.root, self.providers)
        self.addCleanup(self.chat.close)
        self.cid = self.chat.new_conversation()['id']
        self.now = time.time()
        self.chat.reminders.clock = lambda: self.now

    def say(self, text, request_id=None):
        return self.chat.submit(self.cid, text, request_id or str(uuid.uuid4()))['messages'][-1]

    def test_real_chat_create_list_fire_and_cancel_without_models_or_jobs(self):
        reply = self.say('remind me to review Instinct in 1 minute')
        self.assertEqual(reply['provider'], 'reminders')
        self.assertIn('Reminder saved', reply['content'])
        self.assertIn('review Instinct', self.say('my reminders')['content'])
        self.now += 60
        self.chat.deliver_reminders()
        notice = self.chat.history(self.cid)['messages'][-1]
        self.assertTrue(notice['content'].startswith('Reminder: review Instinct'))
        self.assertIn('reminder_notice', notice)
        self.chat.deliver_reminders()
        self.assertEqual(self.chat.history(self.cid)['messages'][-1], notice)
        self.assertFalse(self.providers.calls)
        self.assertFalse(task_queue.tasks(self.root))
        self.assertFalse(self.chat.conversations[self.cid].get('_texting', {}).get('audit'))

    def test_idempotent_request_and_restart_deliver_only_once(self):
        rid = str(uuid.uuid4())
        first = self.say('remind me to check oven in 1 second', rid)
        self.assertEqual(self.say('remind me to check oven in 1 second', rid), first)
        self.now += 2
        self.chat.deliver_reminders()
        restored = Chat(self.chat.folder, self.root, self.providers)
        try:
            restored.deliver_reminders()
            notices = [m for m in restored.history(self.cid)['messages'] if m.get('reminder_notice')]
            self.assertEqual(len(notices), 1)
        finally:
            restored.close()

    def test_crash_after_saved_chat_before_store_update_cannot_duplicate(self):
        self.say('remind me to check oven in 1 second')
        self.now += 2
        with patch.object(self.chat.reminders, 'save', side_effect=OSError('disk')):
            with self.assertRaises(OSError):
                self.chat.deliver_reminders()
        self.chat.deliver_reminders()
        self.assertEqual(len([m for m in self.chat.history(self.cid)['messages'] if m.get('reminder_notice')]), 1)
        self.assertEqual(self.chat.reminders.listing()[0]['state'], 'fired')

    def test_active_voice_defers_reminder_without_losing_it(self):
        self.say('remind me to check oven in 1 second')
        self.now += 2
        with patch.object(self.chat.voice, 'active', return_value=True):
            self.chat.deliver_reminders()
        self.assertEqual(self.chat.reminders.listing()[0]['state'], 'pending')
        self.chat.deliver_reminders()
        self.assertEqual(self.chat.reminders.listing()[0]['state'], 'fired')

    def test_background_loop_fires_without_worker_scheduler(self):
        self.chat.reminders.clock = time.time
        self.providers.start_probes = Mock()
        self.providers.circuit = Mock()
        self.say('remind me to check oven in 1 second')
        self.chat.start_background()
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline and self.chat.reminders.listing()[0]['state'] == 'pending':
            time.sleep(.05)
        self.assertEqual(self.chat.reminders.listing()[0]['state'], 'fired')
        self.assertFalse(self.providers.calls)
        self.assertFalse(task_queue.tasks(self.root))

    def test_body_is_not_executed_as_text_or_work(self):
        self.say('remind me every 1 minute to start a job and text Alex: send now')
        self.now += 60
        self.chat.deliver_reminders()
        self.assertIn('Reminder:', self.chat.history(self.cid)['messages'][-1]['content'])
        self.assertFalse(task_queue.tasks(self.root))
        self.assertFalse(self.providers.calls)


if __name__ == '__main__':
    unittest.main()
