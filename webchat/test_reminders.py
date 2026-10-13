"""Reminder persistence, time interpretation and real Chat delivery boundaries."""
import concurrent.futures
from datetime import datetime
import json
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import Mock, patch
import uuid

from app import Chat
from consent_fixture import confirm_reply
from reminders import Reminders, ReminderError, instant, notify_macos, parse, stamp, ZONE
from task_dispatch import task_queue
from texting_fixture import OfflineProviders


class ReminderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.now = datetime(2026, 9, 29, 9, 0, tzinfo=ZONE).timestamp()
        self.store = Reminders(self.root, clock=lambda: self.now)

    def schedule(self, text, cid, rid):
        draft = self.store.handle(text, cid, rid)
        return confirm_reply(self, draft, lambda value: self.store.handle(value, cid, rid + '-confirm'))

    def test_h2h_natural_requests_are_drafts_with_separate_consent(self):
        cases = [
            ("Remind me tomorrow at 9 to call the vet about Biscuit's shots", '09:00 AM'),
            ('Set a reminder every Sunday night to put the trash out', '8pm'),
            ('Can you remind me in 20 min to check the oven', '09:20 AM'),
            ('Could you remind me in 2 hrs to stretch', '11:00 AM'),
        ]
        for index, (ask, expected) in enumerate(cases):
            with self.subTest(ask=ask):
                draft = self.store.handle(ask, 'chat', str(index))
                self.assertIn(expected, draft)
                self.assertIn('yes wbrem-', draft)
                self.assertFalse(self.store.listing())
        self.assertIn('Assuming AM', self.store.handle(cases[0][0], 'other', 'one'))

    def test_event_relative_is_durable_incomplete_draft_with_one_question(self):
        ask = 'remind me before band practice to restring the strat'
        reply = self.store.handle(ask, 'chat', 'one')
        self.assertIn('restring the strat', reply)
        self.assertIn('When is band practice?', reply)
        self.assertEqual(reply.count('?'), 1)
        row, = json.loads((self.store.folder / 'drafts.json').read_text()).values()
        self.assertEqual(row['state'], 'needs_time')
        restored = Reminders(self.root, clock=lambda: self.now)
        self.assertEqual(restored.handle(ask, 'chat', 'one'), reply)
        self.assertIn('When is band practice?', restored.handle('yes ' + row['token'], 'chat', 'two'))
        self.assertFalse(restored.listing())

    def test_weekly_schedule_preserves_local_time_across_dst(self):
        self.now = datetime(2026, 10, 25, 21, tzinfo=ZONE).timestamp()
        self.schedule('Set a reminder every Sunday night to put the trash out', 'chat', 'one')
        row, = self.store.listing()
        self.assertEqual(row['due_at'], datetime(2026, 11, 1, 20, tzinfo=ZONE).timestamp())
        self.now = row['due_at']
        self.store.deliver_due(Mock(return_value=True))
        self.assertEqual(self.store.listing()[0]['due_at'], datetime(2026, 11, 8, 20, tzinfo=ZONE).timestamp())

    def test_weekly_catchup_keeps_upcoming_same_day_and_rejects_dst_fold(self):
        from reminders import next_weekday
        now = datetime(2026, 11, 1, 10, tzinfo=ZONE).timestamp()
        self.assertEqual(next_weekday(now, dict(day=6, clock='8pm')),
                         datetime(2026, 11, 1, 20, tzinfo=ZONE).timestamp())
        self.now = datetime(2026, 11, 1, 0, tzinfo=ZONE).timestamp()
        reply = self.store.handle('remind me every Sunday at 1:30am to stretch', 'chat', 'fold')
        self.assertIn('daylight-saving', reply)
        self.assertFalse(self.store.listing())

    def test_model_extraction_of_literal_schedule_still_needs_fresh_consent(self):
        import chat_intent
        ask = 'remind me about stretching tomorrow at 9am'
        reply = self.store.extracted('{"body":"stretching","when":"tomorrow at 9am"}',
                                     ask, 'chat', 'one', 'owner', chat_intent.new_state())
        self.assertIn('Proposed reminder: stretching', reply)
        self.assertFalse(self.store.listing())
        confirmed = confirm_reply(self, reply, lambda text: self.store.handle(text, 'chat', 'two'))
        self.assertIn('Reminder saved', confirmed)
        self.assertEqual(len(self.store.listing()), 1)

    def test_extraction_cannot_invent_time_or_bypass_consent(self):
        import chat_intent
        for output in ('not json', '{"body":"stretch","when":"tomorrow at 9am"}',
                       '{"body":"invented","when":null}'):
            reply = self.store.extracted(output, 'remind me soon to stretch', 'chat', 'one', 'owner', chat_intent.new_state())
            self.assertNotIn('yes wbrem-', reply)
            self.assertFalse(self.store.listing())
        reply = self.store.extracted('{"body":"stretch","when":"soon"}',
                                    'remind me soon to stretch', 'chat', 'two', 'owner', chat_intent.new_state())
        self.assertIn('Draft reminder: stretch', reply)
        self.assertEqual(reply.count('?'), 1)

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

    def test_clock_defaults_to_next_local_occurrence(self):
        self.assertEqual(instant('10am', self.now), self.now + 3600)
        self.assertEqual(instant('at 09:00', self.now), self.now + 86400)
        self.assertEqual(instant('2am', self.now), datetime(2026, 9, 30, 2, tzinfo=ZONE).timestamp())
        midnight = datetime(2026, 12, 31, 23, 59, tzinfo=ZONE).timestamp()
        self.assertEqual(instant('12am', midnight), datetime(2027, 1, 1, tzinfo=ZONE).timestamp())

    def test_clock_dst_gaps_and_folds_are_not_guessed(self):
        for day, clock in ((datetime(2026, 11, 1, 0, tzinfo=ZONE), '1:30am'),
                           (datetime(2027, 3, 14, 0, tzinfo=ZONE), '2:30am')):
            with self.subTest(day=day), self.assertRaises(ReminderError):
                instant(clock, day.timestamp())

    def test_timer_receipt_shows_due_seconds(self):
        self.assertIn('09:00:10 AM CDT', stamp(self.now + 10))

    def test_duration_and_pending_caps_remain_enforced(self):
        self.assertEqual(instant('in 366 days', self.now), self.now + 366 * 86400)
        for delay in ('in 0 seconds', 'in 367 days'):
            with self.assertRaises(ReminderError):
                instant(delay, self.now)
        row = self.store.create('chat', 'request', 'Check oven', self.now + 60)
        self.store.save([dict(row, id=str(i)) for i in range(200)])
        reply = self.schedule('Set a timer for 10 minutes', 'chat', 'new-request')
        self.assertIn('limit', reply)
        self.assertNotIn('saved:', reply)
        self.assertEqual(len(self.store.listing()), 200)

    def test_timer_list_and_cancel_aliases(self):
        self.schedule('Set a timer for 10 minutes', 'chat', 'timer')
        row, = self.store.listing()
        self.assertIn(row['id'], self.store.handle('my timers', 'chat', 'list'))
        self.assertEqual(self.store.handle('cancel timer ' + row['id'], 'chat', 'cancel'), 'Reminder cancelled.')
        self.assertEqual(self.store.listing()[0]['state'], 'cancelled')

    def test_failed_create_never_returns_success_receipt(self):
        with patch.object(self.store, 'save', side_effect=OSError('disk full')):
            reply = self.schedule('Create a reminder for 2am to go to bed', 'chat', 'request')
        self.assertIn('requested change was not saved', reply)
        self.assertFalse(self.store.listing())

    def test_extra_schedule_clauses_require_clarification_without_saving(self):
        self.now = datetime(2026, 10, 10, 1, 47, tzinfo=ZONE).timestamp()
        for clause in ('for 2am to go to bed tomorrow', 'to go to bed at 2am tomorrow at 3am',
                       'for 2am to go to bed today', 'for 2am to go to bed on 2026-10-11',
                       'for 2am to go to bed at 3am', 'in 10 minutes to stretch in 20 minutes',
                       'for 2am to go to bed next week'):
            with self.subTest(clause=clause):
                reply = self.store.handle('create a reminder ' + clause, 'chat', str(uuid.uuid4()))
                self.assertIn('extra date or time clause', reply)
                self.assertFalse(self.store.listing())
        for clause, day in (('for 2am to go to bed', 10), ('for tomorrow at 2am to go to bed', 11),
                            ('to go to bed tomorrow at 2am', 11)):
            body, due, interval = parse('create a reminder ' + clause, self.now)
            self.assertEqual((body, due, interval),
                             ('go to bed', datetime(2026, 10, day, 2, tzinfo=ZONE).timestamp(), None))

    def test_recurring_extra_schedule_clauses_are_not_saved(self):
        self.now = datetime(2026, 10, 10, 10, tzinfo=ZONE).timestamp()
        for prefix in ('create a reminder', 'remind me', 'set a routine'):
            for suffix in ('starting tomorrow', 'starting today at noon',
                           'starting on 2026-10-11', 'until next week', 'at 3pm'):
                with self.subTest(prefix=prefix, suffix=suffix):
                    reply = self.store.handle(f'{prefix} every 2 hours to stretch {suffix}',
                                              'chat', str(uuid.uuid4()))
                    # Consent clauses and unresolved nonnumeric adjuncts are
                    # refused before the scheduling parser is reached.
                    expected = ('Send a new reminder request' if suffix.startswith('until ')
                                or suffix == 'starting today at noon'
                                else 'extra date or time clause')
                    self.assertIn(expected, reply)
                    self.assertIn('Nothing was saved', reply)
                    self.assertFalse(self.store.listing())
        reply = self.schedule('create a reminder every 2 hours to stretch', 'chat', 'valid')
        self.assertIn('Reminder saved: stretch', reply)
        row, = self.store.listing()
        self.assertEqual(row['due_at'], self.now + 7200)
        self.assertEqual(row['interval_seconds'], 7200)

    def test_morning_extra_schedule_clauses_are_not_saved(self):
        self.now = datetime(2026, 10, 10, 1, 47, tzinfo=ZONE).timestamp()
        for prefix in ('every morning remind me to', 'remind me every morning to',
                       'create a reminder every morning to', 'set a routine every morning to'):
            for suffix in ('tomorrow', 'today', 'on 2026-10-11', 'at 3pm', 'next week'):
                with self.subTest(prefix=prefix, suffix=suffix):
                    reply = self.store.handle(f'{prefix} stretch {suffix}', 'chat', str(uuid.uuid4()))
                    expected = ('Send a new reminder request' if prefix.startswith('every morning')
                                and suffix.startswith(('on ', 'at ')) else 'extra date or time clause')
                    self.assertIn(expected, reply)
                    self.assertIn('Nothing was saved', reply)
                    self.assertFalse(self.store.listing())
        reply = self.schedule('every morning remind me to stretch', 'chat', 'valid')
        self.assertIn('Reminder saved: stretch', reply)
        row, = self.store.listing()
        self.assertEqual(row['due_at'], datetime(2026, 10, 10, 9, tzinfo=ZONE).timestamp())
        self.assertEqual(row['daily_time'], '09:00')

    def test_write_then_error_is_uncertain_and_retry_does_not_duplicate(self):
        save = self.store.save
        def write_then_fail(rows):
            save(rows)
            raise OSError('failure after replacement')
        with patch.object(self.store, 'save', side_effect=write_then_fail):
            reply = self.schedule('set a timer for 10 minutes', 'chat', 'request')
        self.assertIn('unconfirmed', reply)
        self.assertNotIn('Reminder saved:', reply)
        restored = Reminders(self.root, clock=lambda: self.now)
        self.assertEqual(len(restored.listing()), 1)
        self.assertIn('unconfirmed', restored.handle('set a timer for 10 minutes', 'chat', 'request'))
        self.assertEqual(len(restored.listing()), 1)

    def test_failed_save_with_unreadable_outcome_is_uncertain(self):
        draft = self.store.handle('set a timer for 10 minutes', 'chat', 'request')
        original_read = Path.read_text
        def read(path, *args, **kwargs):
            if path == self.store.path:
                raise OSError('readback unavailable')
            return original_read(path, *args, **kwargs)
        with patch.object(self.store, 'save', side_effect=OSError('disk full')), \
                patch.object(Path, 'read_text', read):
            reply = confirm_reply(self, draft, lambda text: self.store.handle(text, 'chat', 'confirm'))
        self.assertIn('unconfirmed', reply)
        self.assertNotIn('was not saved', reply)

    def test_failed_cancel_keeps_pending_and_returns_not_done_receipt(self):
        row = self.store.create('chat', 'request', 'Check oven', self.now + 60)
        with patch.object(self.store, 'save', side_effect=OSError('disk full')):
            reply = self.store.handle('cancel reminder ' + row['id'], 'chat', 'cancel')
        self.assertIn('requested change was not saved', reply)
        self.assertEqual(self.store.listing()[0]['state'], 'pending')

    def test_storage_unavailable_returns_receipt_for_create_list_and_cancel(self):
        for command in ('set a timer for 10 minutes', 'my reminders', 'cancel reminder ' + 'a' * 16):
            with self.subTest(command=command), patch.object(self.store, 'locked', side_effect=OSError('unavailable')):
                reply = (self.schedule(command, 'chat', 'request') if command.startswith('set ')
                         else self.store.handle(command, 'chat', 'request'))
                self.assertIn('Reminder storage is unavailable', reply)
                self.assertIn('no successful change was verified', reply)

    def test_receipt_uses_persisted_recurrence_on_duplicate_request(self):
        self.schedule('Set a reminder every 2 hours to stretch', 'chat', 'request')
        reply = self.store.handle('Set a reminder in 10 minutes to something else', 'chat', 'request')
        self.assertIn('Request ID already used', reply)
        self.assertNotIn('something else', reply)

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
        notify = Mock()
        self.store.deliver_due(first, notify)
        notify.assert_not_called()
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

    def test_failed_notification_does_not_block_other_due_reminders(self):
        self.store.create('chat', 'one', 'One', self.now + 1)
        self.store.create('chat', 'two', 'Two', self.now + 1)
        self.now += 60
        notify = Mock(side_effect=[OSError('notification denied'), True])
        self.store.deliver_due(Mock(return_value=True), notify)
        self.assertEqual([c.args[0] for c in notify.call_args_list], ['One', 'Two'])
        self.assertTrue(all(row['state'] == 'fired' for row in self.store.listing()))

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
        notifier = patch('reminders.notify_macos', return_value=True)
        self.notify = notifier.start()
        self.addCleanup(notifier.stop)
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.providers = OfflineProviders()
        self.chat = Chat(self.root / 'conductor/webchat', self.root, self.providers,
                         reminder_notifier=self.notify)
        self.addCleanup(self.chat.close)
        self.cid = self.chat.new_conversation()['id']
        self.now = time.time()
        self.chat.reminders.clock = lambda: self.now

    def say(self, text, request_id=None):
        return self.chat.submit(self.cid, text, request_id or str(uuid.uuid4()))['messages'][-1]

    def schedule(self, text, request_id=None):
        return confirm_reply(self, self.say(text, request_id), self.say)

    def test_unknown_reminder_uses_structured_model_extraction_only(self):
        self.providers.reply = Mock(return_value=dict(content='{"body":"stretch","when":"soon"}', provider='fixture', attempts=[]))
        self.say('remind me soon to stretch')
        deadline = time.monotonic() + 3
        while self.cid in self.chat.workers and time.monotonic() < deadline:
            time.sleep(.01)
        reply = self.chat.history(self.cid)['messages'][-1]
        self.assertIn('Draft reminder: stretch', reply['content'])
        prompt = self.providers.reply.call_args.args[0]['messages'][-2]['content']
        self.assertIn('JSON only', prompt)
        self.assertIn('verbatim', prompt)
        self.assertFalse(task_queue.tasks(self.root))
        self.assertFalse(self.chat.reminders.listing())
        self.notify.assert_not_called()

    def test_ambiguous_schedule_stays_in_reminder_lane_without_saving(self):
        self.now = datetime(2026, 10, 10, 1, 47, tzinfo=ZONE).timestamp()
        for command in ('create a reminder for 2am to go to bed tomorrow',
                        'create a reminder to go to bed at 2am tomorrow at 3am'):
            reply = self.say(command)
            self.assertEqual(reply['provider'], 'reminders')
            self.assertIn('Nothing was saved', reply['content'])
        self.assertFalse(self.chat.reminders.listing())
        self.assertFalse(self.providers.calls)
        self.assertFalse(task_queue.tasks(self.root))
        self.notify.assert_not_called()

    def test_storage_failure_returns_direct_not_done_receipt_without_side_effects(self):
        with patch.object(self.chat.reminders, 'save', side_effect=OSError('disk full')):
            reply = self.schedule('set a timer for 10 minutes')
        self.assertEqual(reply['provider'], 'reminders')
        self.assertIn('requested change was not saved', reply['content'])
        self.assertFalse(self.chat.reminders.listing())
        self.assertFalse(self.providers.calls)
        self.assertFalse(task_queue.tasks(self.root))
        self.notify.assert_not_called()

    def test_real_chat_create_list_fire_and_cancel_without_models_or_jobs(self):
        reply = self.schedule('remind me to review Instinct in 1 minute')
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
        self.notify.assert_called_once_with('review Instinct')

    def test_idempotent_request_and_restart_deliver_only_once(self):
        rid = str(uuid.uuid4())
        first = self.say('remind me to check oven in 1 second', rid)
        self.assertEqual(self.say('remind me to check oven in 1 second', rid), first)
        confirm_reply(self, first, self.say)
        self.now += 2
        self.chat.deliver_reminders()
        restored = Chat(self.chat.folder, self.root, self.providers, reminder_notifier=self.notify)
        try:
            restored.deliver_reminders()
            notices = [m for m in restored.history(self.cid)['messages'] if m.get('reminder_notice')]
            self.assertEqual(len(notices), 1)
        finally:
            restored.close()
        self.notify.assert_called_once_with('check oven')

    def test_crash_after_saved_chat_before_store_update_cannot_duplicate(self):
        self.schedule('remind me to check oven in 1 second')
        self.now += 2
        with patch.object(self.chat.reminders, 'save', side_effect=OSError('disk')):
            with self.assertRaises(OSError):
                self.chat.deliver_reminders()
        self.notify.assert_not_called()
        self.chat.deliver_reminders()
        self.assertEqual(len([m for m in self.chat.history(self.cid)['messages'] if m.get('reminder_notice')]), 1)
        self.assertEqual(self.chat.reminders.listing()[0]['state'], 'fired')
        self.notify.assert_called_once_with('check oven')

    def test_overdue_timer_survives_restart_and_notifies_once_after_persistence(self):
        self.schedule('Set a timer for 1 second')
        folder = self.chat.folder
        self.chat.close()
        restored = Chat(folder, self.root, self.providers, reminder_notifier=self.notify)
        self.addCleanup(restored.close)
        restored.reminders.clock = lambda: self.now + 60
        observed = []
        def notify(body):
            saved = json.loads((restored.state / (self.cid + '.json')).read_text())
            observed.append((body, json.loads(restored.reminders.path.read_text())[0]['state'],
                             len([m for m in saved['messages'] if m.get('reminder_notice')])))
        self.notify.side_effect = notify
        restored.deliver_reminders()
        restored.deliver_reminders()
        self.notify.assert_called_once_with('Timer')
        self.assertEqual(observed, [('Timer', 'fired', 1)])

    def test_notification_failure_keeps_chat_and_fired_state(self):
        self.schedule('Set an alarm in 1 second to check oven')
        self.now += 2
        self.notify.side_effect = RuntimeError('notification unavailable')
        self.chat.deliver_reminders()
        self.assertEqual(self.chat.reminders.listing()[0]['state'], 'fired')
        notice = self.chat.history(self.cid)['messages'][-1]
        self.assertIn('Reminder: check oven', notice['content'])
        self.assertNotIn('notification sent', notice['content'])
        self.chat.deliver_reminders()
        self.notify.assert_called_once()

    def test_failed_chat_write_keeps_pending_and_never_notifies(self):
        self.schedule('Set a timer for 1 second')
        self.now += 2
        with patch.object(self.chat, 'save', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.chat.deliver_reminders()
        self.notify.assert_not_called()
        self.assertEqual(self.chat.reminders.listing()[0]['state'], 'pending')
        self.chat.deliver_reminders()
        self.notify.assert_called_once_with('Timer')

    def test_no_early_or_cancelled_notification_and_redacted_os_body(self):
        self.schedule('Set a timer for 10 seconds')
        self.chat.deliver_reminders()
        self.notify.assert_not_called()
        row, = self.chat.reminders.listing()
        self.say('cancel timer ' + row['id'])
        self.now += 20
        self.chat.deliver_reminders()
        self.notify.assert_not_called()
        self.chat.reminders.create(self.cid, 'secret-test', 'sk-' + 'a' * 25, self.now)
        self.chat.deliver_reminders()
        self.assertNotIn('sk-' + 'a' * 25, self.notify.call_args.args[0])

    def test_active_voice_defers_reminder_without_losing_it(self):
        self.schedule('remind me to check oven in 1 second')
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
        self.schedule('Set a timer for 1 second to check oven')
        self.chat.start_background()
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline and self.chat.reminders.listing()[0]['state'] == 'pending':
            time.sleep(.05)
        self.assertEqual(self.chat.reminders.listing()[0]['state'], 'fired')
        self.assertIn('Reminder: check oven', self.chat.history(self.cid)['messages'][-1]['content'])
        self.notify.assert_called_once_with('check oven')
        self.assertFalse(self.providers.calls)
        self.assertFalse(task_queue.tasks(self.root))

    def test_body_is_not_executed_as_text_or_work(self):
        self.say('remind me every 1 minute to start a job and text Alex: send now')
        self.assertFalse(self.chat.reminders.listing())
        self.assertIn('Nothing was saved', self.chat.history(self.cid)['messages'][-1]['content'])
        self.notify.assert_not_called()
        # Keep the original data-not-instructions assertion on a plain body.
        self.schedule('remind me every 1 minute to start a job')
        self.now += 60
        self.chat.deliver_reminders()
        self.assertIn('Reminder:', self.chat.history(self.cid)['messages'][-1]['content'])
        self.assertFalse(task_queue.tasks(self.root))
        self.assertFalse(self.providers.calls)


class MacNotificationTests(unittest.TestCase):
    def test_notification_body_is_data_not_applescript_or_shell(self):
        body = '" & do shell script "touch /tmp/never" & "\\\n$(touch /tmp/never)'
        with patch('reminders.sys.platform', 'darwin'), patch('reminders.subprocess.run') as run:
            run.return_value.returncode = 0
            self.assertTrue(notify_macos(body))
        argv = run.call_args.args[0]
        self.assertEqual(argv[0], '/usr/bin/osascript')
        self.assertNotIn(body, argv[2])
        self.assertEqual(argv[-2:], ['--', body])
        self.assertNotIn('shell', run.call_args.kwargs)
        self.assertEqual(run.call_args.kwargs['timeout'], 3)

    def test_unsupported_platform_and_failures_are_best_effort(self):
        with patch('reminders.sys.platform', 'linux'), patch('reminders.subprocess.run') as run:
            self.assertFalse(notify_macos('Timer'))
            run.assert_not_called()
        for error in (FileNotFoundError(), subprocess.TimeoutExpired('osascript', 3)):
            with self.subTest(error=error), patch('reminders.sys.platform', 'darwin'), \
                    patch('reminders.subprocess.run', side_effect=error):
                self.assertFalse(notify_macos('Timer'))
        with patch('reminders.sys.platform', 'darwin'), patch('reminders.subprocess.run') as run:
            run.return_value.returncode = 1
            self.assertFalse(notify_macos('Timer'))


if __name__ == '__main__':
    unittest.main()
