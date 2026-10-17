"""Reminder persistence, time interpretation and real Chat delivery boundaries."""
import concurrent.futures
from contextlib import contextmanager
import copy
from datetime import datetime
import json
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import threading
import unittest
from unittest.mock import Mock, patch
import uuid

from app import Chat
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
        reply = self.store.handle('Set a timer for 10 minutes', 'chat', 'new-request')
        self.assertIn('limit', reply)
        self.assertNotIn('saved:', reply)
        self.assertEqual(len(self.store.listing()), 200)

    def test_timer_list_and_cancel_aliases(self):
        self.store.handle('Set a timer for 10 minutes', 'chat', 'timer')
        row, = self.store.listing()
        self.assertIn(row['id'], self.store.handle('my timers', 'chat', 'list'))
        self.assertEqual(self.store.handle('cancel timer ' + row['id'], 'chat', 'cancel'), 'Reminder cancelled.')
        self.assertEqual(self.store.listing()[0]['state'], 'cancelled')

    def test_failed_create_never_returns_success_receipt(self):
        with patch.object(self.store, 'save', side_effect=OSError('disk full')):
            reply = self.store.handle('Create a reminder for 2am to go to bed', 'chat', 'request')
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
                    self.assertIn('extra date or time clause', reply)
                    self.assertIn('Nothing was saved', reply)
                    self.assertFalse(self.store.listing())
        reply = self.store.handle('create a reminder every 2 hours to stretch', 'chat', 'valid')
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
                    self.assertIn('extra date or time clause', reply)
                    self.assertIn('Nothing was saved', reply)
                    self.assertFalse(self.store.listing())
        reply = self.store.handle('every morning remind me to stretch', 'chat', 'valid')
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
            reply = self.store.handle('set a timer for 10 minutes', 'chat', 'request')
        self.assertIn('unconfirmed', reply)
        self.assertNotIn('Reminder saved:', reply)
        restored = Reminders(self.root, clock=lambda: self.now)
        self.assertEqual(len(restored.listing()), 1)
        self.assertIn('Reminder saved:', restored.handle('set a timer for 10 minutes', 'chat', 'request'))
        self.assertEqual(len(restored.listing()), 1)

    def test_failed_save_with_unreadable_outcome_is_uncertain(self):
        with patch.object(self.store, 'save', side_effect=OSError('disk full')), \
                patch.object(Path, 'read_text', side_effect=OSError('readback unavailable')):
            reply = self.store.handle('set a timer for 10 minutes', 'chat', 'request')
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
                reply = self.store.handle(command, 'chat', 'request')
                self.assertIn('Reminder storage is unavailable', reply)
                self.assertIn('no successful change was verified', reply)

    def test_receipt_uses_persisted_recurrence_on_duplicate_request(self):
        self.store.handle('Set a reminder every 2 hours to stretch', 'chat', 'request')
        reply = self.store.handle('Set a reminder in 10 minutes to something else', 'chat', 'request')
        self.assertIn('stretch', reply)
        self.assertIn('Repeats every 120 minutes', reply)
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


class RoutineControlTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.now = datetime(2026, 10, 10, 7, tzinfo=ZONE).timestamp()
        self.store = Reminders(self.root, clock=lambda: self.now)
        self.row = self.store.create('chat', 'routine', 'Private action body',
                                     datetime(2026, 10, 10, 9, tzinfo=ZONE).timestamp(),
                                     86400, daily_time='09:00', action='look up fixture')
        self.identifier = self.row['id']
        self.deliver = Mock(return_value=True)
        self.notify = Mock()

    def control(self, command, cid='chat', identifier=None):
        return self.store.handle(f'{command} routine {identifier or self.identifier}', cid, str(uuid.uuid4()))

    def saved(self):
        return next(r for r in self.store.listing() if r['id'] == self.identifier)

    def test_pause_before_due_survives_restart_and_lists_separately(self):
        active = self.store.create('chat', 'other', 'Still active', self.now + 60)
        reply = self.control('pause')
        self.assertIn('Paused routine ' + self.identifier, reply)
        self.assertNotIn(self.row['body'], reply)
        self.assertEqual(self.saved(), dict(self.row, state='paused', paused_at=self.now))
        self.now += 4 * 86400
        self.store = Reminders(self.root, clock=lambda: self.now)
        # Cancel the unrelated one-shot to isolate execution suppression.
        self.store.cancel(active['id'], 'chat')
        self.store.deliver_due(self.deliver, self.notify)
        self.deliver.assert_not_called()
        self.notify.assert_not_called()
        reply = self.store.handle('list routines', 'chat', 'list')
        self.assertIn('Paused routines (no runs while paused):', reply)
        self.assertIn(self.identifier, reply)
        self.assertNotIn(stamp(self.row['due_at']), reply)
        self.assertNotIn(active['id'], reply)

    def test_resume_skips_missed_runs_and_retains_occurrence_identity(self):
        self.now = self.row['due_at']
        self.store.deliver_due(self.deliver)
        prior_notice = self.deliver.call_args.args[1]
        self.control('pause')
        paused = self.saved()
        self.now += 5 * 86400 + 3600
        reply = self.control('resume')
        resumed = self.saved()
        self.assertIn('Resumed routine ' + self.identifier, reply)
        self.assertIn('Missed runs will not be replayed', reply)
        self.assertEqual(resumed['due_at'], datetime(2026, 10, 16, 9, tzinfo=ZONE).timestamp())
        for key in ('id', 'action', 'body', 'daily_time', 'interval_seconds', 'occurrences', 'last_fired_at'):
            self.assertEqual(resumed[key], paused[key])
        self.assertNotIn('paused_at', resumed)
        self.deliver.reset_mock()
        self.store.deliver_due(self.deliver)
        self.deliver.assert_not_called()
        self.now = resumed['due_at']
        self.store.deliver_due(self.deliver)
        expected = uuid.uuid5(uuid.NAMESPACE_URL, 'reminder-notice:' + self.identifier + ':1').hex
        self.assertEqual(self.deliver.call_args.args[1], expected)
        self.assertNotEqual(expected, prior_notice)

    def test_repeated_controls_do_not_write_or_move_the_schedule(self):
        self.control('pause')
        paused = self.saved()
        self.now += 60
        with patch.object(self.store, 'save', side_effect=AssertionError('No-op wrote storage')):
            self.assertIn('already paused', self.control('pause'))
        self.assertEqual(self.saved(), paused)
        self.control('resume')
        resumed = self.saved()
        self.now += 3 * 86400
        with patch.object(self.store, 'save', side_effect=AssertionError('No-op wrote storage')):
            self.assertIn('already scheduled', self.control('resume'))
        self.assertEqual(self.saved(), resumed)
        self.control('pause')
        self.assertEqual(self.saved()['paused_at'], self.now)
        self.assertEqual(len(self.store.listing()), 1)

    def test_resume_before_at_and_after_daily_time_and_dst(self):
        cases = (
            (datetime(2026, 10, 10, 8, tzinfo=ZONE), datetime(2026, 10, 10, 9, tzinfo=ZONE)),
            (datetime(2026, 10, 10, 9, tzinfo=ZONE), datetime(2026, 10, 11, 9, tzinfo=ZONE)),
            (datetime(2026, 10, 31, 9, tzinfo=ZONE), datetime(2026, 11, 1, 9, tzinfo=ZONE)),
            (datetime(2027, 3, 13, 9, tzinfo=ZONE), datetime(2027, 3, 14, 9, tzinfo=ZONE)),
            (datetime(2027, 3, 14, 10, tzinfo=ZONE), datetime(2027, 3, 15, 9, tzinfo=ZONE)),
        )
        for now, due in cases:
            with self.subTest(now=now):
                self.control('pause')
                self.now = now.timestamp()
                reply = self.control('resume')
                self.assertEqual(self.saved()['due_at'], due.timestamp())
                self.assertGreater(self.saved()['due_at'], self.now)
                self.assertIn(stamp(due.timestamp()), reply)
        # Existing morning grammar deliberately excludes DST gap/fold hours.
        reply = self.store.handle('every morning at 2:30am do look up fixture', 'chat', 'gap')
        self.assertIn('3:00am through 11:59am', reply)
        self.assertEqual(len(self.store.listing()), 1)

    def test_interval_resume_preserves_phase_without_catchup(self):
        row = self.store.create('chat', 'interval', 'Stretch', self.now + 60, 60)
        self.control('pause', identifier=row['id'])
        self.now += 3700
        self.control('resume', identifier=row['id'])
        resumed = next(r for r in self.store.listing() if r['id'] == row['id'])
        self.assertEqual(resumed['due_at'], row['due_at'] + 61 * 60)
        self.assertEqual(resumed['occurrences'], 0)
        self.assertGreater(resumed['due_at'], self.now)

    def test_cross_chat_controls_and_listing_do_not_disclose_or_mutate(self):
        for command in ('pause', 'resume', 'cancel'):
            reply = self.control(command, cid='other')
            self.assertIn('No ', reply)
            for private in (self.row['body'], self.row['action'], '09:00'):
                self.assertNotIn(private, reply)
            self.assertEqual(self.saved(), self.row)
        self.assertNotIn(self.identifier, self.store.handle('my routines', 'other', 'list'))
        self.control('pause')
        self.assertNotIn(self.identifier, self.store.handle('my routines', 'other', 'list-paused'))

    def test_cancel_paused_cannot_be_resumed_and_one_shots_are_not_routines(self):
        self.control('pause')
        self.assertEqual(self.control('cancel'), 'Reminder cancelled.')
        for command in ('pause', 'resume'):
            self.assertIn('is cancelled', self.control(command))
        one_shot = self.store.create('chat', 'timer', 'Timer', self.now + 1)
        for command in ('pause', 'resume'):
            self.assertIn('No routine', self.control(command, identifier=one_shot['id']))
        self.store.cancel(one_shot['id'])
        self.now += 86400
        self.store.deliver_due(self.deliver)
        self.deliver.assert_not_called()

    def test_failed_persistence_never_confirms_pause_or_resume(self):
        for command in ('pause', 'resume'):
            with self.subTest(command=command):
                if command == 'resume':
                    self.control('pause')
                before = self.saved()
                with patch.object(self.store, 'save', side_effect=OSError('disk full')):
                    reply = self.control(command)
                self.assertIn('requested change was not saved', reply)
                self.assertNotIn(command.capitalize() + 'd routine', reply)
                self.assertEqual(self.saved(), before)
                self.now = before['due_at']
                self.deliver.reset_mock()
                self.store.deliver_due(self.deliver)
                self.assertEqual(self.deliver.call_count, 1 if command == 'pause' else 0)

    def test_write_then_error_is_unconfirmed_and_readback_retry_is_noop(self):
        save = self.store.save
        def write_then_fail(rows):
            save(rows)
            raise OSError('after replacement')
        for command, state, no_op in (('pause', 'paused', 'already paused'),
                                     ('resume', 'pending', 'already scheduled')):
            with self.subTest(command=command):
                with patch.object(self.store, 'save', side_effect=write_then_fail):
                    reply = self.control(command)
                self.assertIn('unconfirmed', reply)
                self.assertNotIn(command.capitalize() + 'd routine', reply)
                self.store = Reminders(self.root, clock=lambda: self.now)
                self.assertEqual(self.saved()['state'], state)
                self.assertIn(no_op, self.control(command))

    def test_unreadable_write_outcome_and_unavailable_storage_stay_unconfirmed(self):
        for command in ('pause', 'resume'):
            if command == 'resume':
                self.control('pause')
            read = Path.read_text
            calls = []
            def readback(path, *args, **kwargs):
                calls.append(path)
                if len(calls) > 1:
                    raise OSError('unreadable')
                return read(path, *args, **kwargs)
            with patch.object(self.store, 'save', side_effect=OSError('unknown')), \
                    patch.object(Path, 'read_text', readback):
                reply = self.control(command)
            self.assertIn('unconfirmed', reply)
            self.assertNotIn('was not saved', reply)
            with patch.object(self.store, 'locked', side_effect=OSError('unavailable')):
                self.assertIn('no successful change was verified', self.control(command))

    def test_pause_wins_before_tick_execution_lock(self):
        self.now = self.row['due_at']
        arrived, proceed = threading.Event(), threading.Event()
        locked = self.store.locked
        @contextmanager
        def delayed_tick_lock():
            if threading.current_thread().name.startswith('tick'):
                arrived.set()
                if not proceed.wait(3):
                    raise AssertionError('Tick was not released')
            with locked() as rows:
                yield rows
        with patch.object(self.store, 'locked', delayed_tick_lock), \
                concurrent.futures.ThreadPoolExecutor(1, thread_name_prefix='tick') as pool:
            tick = pool.submit(self.store.deliver_due, self.deliver)
            try:
                self.assertTrue(arrived.wait(3))
                self.assertIn('Paused routine', self.control('pause'))
            finally:
                proceed.set()
            tick.result(timeout=3)
        self.deliver.assert_not_called()
        self.assertEqual(self.saved()['state'], 'paused')

    def test_already_running_tick_finishes_before_pause_and_receipt_names_delivery(self):
        self.now = self.row['due_at']
        started, finish, pause_started = threading.Event(), threading.Event(), threading.Event()
        notices = []
        def execute(row, notice):
            notices.append(notice)
            started.set()
            if not finish.wait(3):
                raise AssertionError('Action was not released')
            return True
        def pause():
            pause_started.set()
            return self.control('pause')
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            tick = pool.submit(self.store.deliver_due, execute)
            try:
                self.assertTrue(started.wait(3))
                control = pool.submit(pause)
                self.assertTrue(pause_started.wait(3))
                with self.assertRaises(concurrent.futures.TimeoutError):
                    control.result(timeout=.05)
            finally:
                finish.set()
            tick.result(timeout=3)
            reply = control.result(timeout=3)
        self.assertIn('does not undo an action that started before the pause', reply)
        self.assertIn('Last recorded delivery:', reply)
        self.assertIn(notices[0], reply)
        self.assertEqual(self.saved()['occurrences'], 1)
        self.now += 86400
        self.store.deliver_due(self.deliver)
        self.deliver.assert_not_called()

    def test_pause_after_ambiguous_delivery_never_claims_no_action_ran(self):
        self.now = self.row['due_at']
        with patch.object(self.store, 'save', side_effect=OSError('after action')):
            with self.assertRaises(OSError):
                self.store.deliver_due(self.deliver)
        self.deliver.assert_called_once()
        reply = self.control('pause')
        self.assertIn('does not undo an action that started before the pause', reply)
        self.assertNotIn('Last recorded delivery:', reply)
        self.assertNotIn('no action ran', reply)
        self.deliver.reset_mock()
        self.now += 86400
        self.store.deliver_due(self.deliver)
        self.deliver.assert_not_called()

    def test_concurrent_ticks_after_resume_deliver_only_one_occurrence(self):
        self.control('pause')
        self.now += 3 * 86400
        self.control('resume')
        self.now = self.saved()['due_at']
        with concurrent.futures.ThreadPoolExecutor(4) as pool:
            ticks = [pool.submit(self.store.deliver_due, self.deliver) for _ in range(4)]
            for tick in ticks:
                tick.result(timeout=3)
        self.deliver.assert_called_once()
        self.assertEqual(self.saved()['occurrences'], 1)

    def test_paused_routines_count_toward_capacity_and_are_never_pruned(self):
        self.control('pause')
        paused = self.saved()
        self.store.save([dict(paused, id=str(i)) for i in range(200)])
        with self.assertRaisesRegex(ReminderError, 'limit'):
            self.store.create('chat', 'new', 'New', self.now + 60)
        self.store.save([paused] + [dict(self.row, id=str(i), state='cancelled') for i in range(399)])
        self.store.create('chat', 'new', 'New', self.now + 60)
        self.assertEqual(self.saved(), paused)


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
            reply = self.say('set a timer for 10 minutes')
        self.assertEqual(reply['provider'], 'reminders')
        self.assertIn('requested change was not saved', reply['content'])
        self.assertFalse(self.chat.reminders.listing())
        self.assertFalse(self.providers.calls)
        self.assertFalse(task_queue.tasks(self.root))
        self.notify.assert_not_called()

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
        self.notify.assert_called_once_with('review Instinct')

    def test_idempotent_request_and_restart_deliver_only_once(self):
        rid = str(uuid.uuid4())
        first = self.say('remind me to check oven in 1 second', rid)
        self.assertEqual(self.say('remind me to check oven in 1 second', rid), first)
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
        self.say('remind me to check oven in 1 second')
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
        self.say('Set a timer for 1 second')
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
        self.say('Set an alarm in 1 second to check oven')
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
        self.say('Set a timer for 1 second')
        self.now += 2
        with patch.object(self.chat, 'save', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.chat.deliver_reminders()
        self.notify.assert_not_called()
        self.assertEqual(self.chat.reminders.listing()[0]['state'], 'pending')
        self.chat.deliver_reminders()
        self.notify.assert_called_once_with('Timer')

    def test_no_early_or_cancelled_notification_and_redacted_os_body(self):
        self.say('Set a timer for 10 seconds')
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
        self.say('Set a timer for 1 second to check oven')
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
        self.now += 60
        self.chat.deliver_reminders()
        self.assertIn('Reminder:', self.chat.history(self.cid)['messages'][-1]['content'])
        self.assertFalse(task_queue.tasks(self.root))
        self.assertFalse(self.providers.calls)


class RoutineControlChatTests(unittest.TestCase):
    def setUp(self):
        from texting import Texting
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.now = datetime(2026, 10, 10, 7, tzinfo=ZONE).timestamp()
        self.providers = OfflineProviders()
        self.actions = Mock()
        self.actions.validate_routine.side_effect = lambda text: text
        self.actions.handle.side_effect = lambda *args, **kwargs: 'Fixture read result' if kwargs.get('routine') else None
        self.notify = Mock()
        self.calendar = Mock()
        self.calendar.handle.return_value = None
        self.texting = Texting(Mock(), Mock(), clock=lambda: self.now)
        for target in ('urllib.request.OpenerDirector.open', 'socket.getaddrinfo', 'socket.socket',
                       'subprocess.run', 'reminders.notify_macos', 'app.parse_work'):
            guard = patch(target, side_effect=AssertionError('Unexpected side effect: ' + target))
            guard.start()
            self.addCleanup(guard.stop)
        self.chat = self.new_chat()
        self.cid = self.chat.new_conversation()['id']
        self.say('every morning do look up fixture')
        self.row, = self.chat.reminders.listing()

    def new_chat(self):
        chat = Chat(self.root / 'chat', self.root, self.providers, texting=self.texting,
                    reminder_notifier=self.notify, calendar=self.calendar, local_tasks=self.actions)
        chat.reminders.clock = lambda: self.now
        self.addCleanup(chat.close)
        return chat

    def say(self, text, cid=None, request_id=None):
        return self.chat.submit(cid or self.cid, text, request_id or str(uuid.uuid4()), actor='owner')['messages'][-1]

    def control(self, command, **kwargs):
        return self.say(command + ' routine ' + self.row['id'], **kwargs)

    def assert_no_external_effects(self):
        self.assertFalse(self.providers.calls)
        self.assertFalse(task_queue.tasks(self.root))
        self.texting.andrea.deliver.assert_not_called()
        self.notify.assert_not_called()

    def test_chat_pause_restart_resume_and_list_routes_are_deterministic(self):
        self.say('every morning do look up another fixture')
        reply = self.control('pause')
        self.assertEqual(reply['provider'], 'reminders')
        self.assertIn('Paused routine', reply['content'])
        self.assertFalse(self.chat.get(self.cid)['intent_state']['holds'])
        listed = self.say('my routines')['content']
        active, paused = listed.split('Paused routines')
        self.assertIn('look up another fixture', active)
        self.assertIn(self.row['id'], paused)
        self.assertNotIn(self.row['id'], active)
        other = next(r for r in self.chat.reminders.listing() if r['id'] != self.row['id'])
        self.say('cancel routine ' + other['id'])
        self.chat.close()
        self.chat = self.new_chat()
        self.now = self.row['due_at'] + 2 * 86400 + 60
        self.chat.deliver_reminders()
        self.actions.handle.assert_not_called()
        resumed = self.control('resume')
        self.assertEqual(resumed['provider'], 'reminders')
        self.assertIn('Resumed routine', resumed['content'])
        self.chat.deliver_reminders()
        self.actions.handle.assert_not_called()
        row = next(r for r in self.chat.reminders.listing() if r['id'] == self.row['id'])
        self.now = row['due_at']
        self.chat.deliver_reminders()
        self.chat.deliver_reminders()
        self.actions.handle.assert_called_once()
        self.assertTrue(self.actions.handle.call_args.kwargs['routine'])
        self.assertIn('Fixture read result', self.chat.history(self.cid)['messages'][-1]['content'])
        self.assert_no_external_effects()

    def test_global_hold_survives_pause_resume_restart_and_due_tick(self):
        self.say('Hold all work')
        held = copy.deepcopy(self.chat.get(self.cid)['intent_state'])
        self.control('pause')
        resumed = self.control('resume')
        self.assertIn('Saved holds still apply', resumed['content'])
        self.assertEqual(self.chat.get(self.cid)['intent_state'], held)
        self.chat.close()
        self.chat = self.new_chat()
        self.now = self.row['due_at'] + 86400
        self.actions.handle.reset_mock()
        self.chat.deliver_reminders()
        self.actions.handle.assert_not_called()
        self.assertEqual(self.chat.get(self.cid)['intent_state'], held)
        self.assertEqual(self.chat.reminders.listing()[0]['occurrences'], 0)
        self.assert_no_external_effects()

    def test_chat_cross_conversation_control_cancel_and_listing(self):
        other = self.chat.new_conversation()['id']
        for command in ('pause', 'resume', 'cancel'):
            reply = self.control(command, cid=other)
            self.assertEqual(reply['provider'], 'reminders')
            self.assertIn('No ', reply['content'])
            self.assertNotIn(self.row['body'], reply['content'])
        self.assertNotIn(self.row['id'], self.say('my routines', cid=other)['content'])
        self.assertEqual(self.chat.reminders.listing()[0], self.row)
        self.assert_no_external_effects()

    def test_retry_of_same_chat_request_does_not_toggle_state(self):
        request = str(uuid.uuid4())
        paused = self.control('pause', request_id=request)
        self.control('resume')
        before = copy.deepcopy(self.chat.history(self.cid))
        self.control('pause', request_id=request)
        self.assertEqual(self.chat.history(self.cid), before)
        self.assertEqual(self.chat.reminders.listing()[0]['state'], 'pending')
        self.assertIn('Paused routine', paused['content'])
        self.assertEqual(len(self.chat.reminders.listing()), 1)
        self.assert_no_external_effects()

    def test_control_receipts_exclude_action_body_and_failures_stay_honest(self):
        # Synthetic stored content only; controls never execute or echo it.
        marker = 'SYNTHETIC-PRIVATE-ACTION-CONTENT'
        with self.chat.reminders.locked() as rows:
            rows[0]['body'] = marker
            rows[0]['action'] = marker
            self.chat.reminders.save(rows)
        for command in ('pause', 'resume'):
            with patch.object(self.chat.reminders, 'save', side_effect=OSError('disk full')):
                reply = self.control(command)
            self.assertIn('requested change was not saved', reply['content'])
            self.assertNotIn(marker, reply['content'])
            saved = self.control(command)
            self.assertNotIn(marker, saved['content'])
            self.assertEqual(saved['provider'], 'reminders')
        self.actions.handle.assert_not_called()
        self.assert_no_external_effects()

    def test_malformed_controls_do_not_change_global_hold_or_enter_model_lane(self):
        for command in ('pause routine', 'resume routine bad-id', 'pause routine ' + self.row['id'] + ' then resume all'):
            reply = self.say(command)
            self.assertEqual(reply['provider'], 'reminders')
            self.assertIn('Nothing changed', reply['content'])
            self.assertFalse(self.chat.get(self.cid)['intent_state']['holds'])
        self.assertEqual(self.chat.reminders.listing()[0], self.row)
        self.assert_no_external_effects()


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
