"""Morning Calendar reads reuse the existing reminder scheduler and GoogleCalendar path."""
import copy
from datetime import datetime
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import uuid

from app import Chat
from calendar_actions import CalendarActions, CalendarError, NEEDS_AUTH, today_routine
from local_tasks import LocalFiles, LocalTasks
from reminders import ZONE
from task_dispatch import task_queue
from texting import Texting
from texting_fixture import OfflineProviders


class FakeCalendar:
    def __init__(self):
        self.creates = []
        self.reads = []
        self.response = {'items': []}
        self.error = None

    def configured(self):
        if self.error:
            raise CalendarError(self.error)

    def create(self, event):
        self.creates.append(copy.deepcopy(event))
        return dict(event, status='confirmed')

    def listing(self, start, end):
        self.reads.append((start, end))
        if self.error:
            raise CalendarError(self.error)
        return self.response


class CalendarRoutineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = self.root / 'home'
        (self.home / 'Documents').mkdir(parents=True)
        self.file = self.home / 'Documents/note.txt'
        self.file.write_text('original')
        self.now = datetime(2026, 10, 10, 1, 47, tzinfo=ZONE).timestamp()
        self.clock = lambda: self.now
        self.providers = OfflineProviders()
        self.notifier = Mock()
        self.client = FakeCalendar()
        self.calendar = CalendarActions(self.root / 'state', self.client, self.clock)
        self.search = Mock(return_value='Fixture search answer. Source: https://example.test/result')
        self.local = LocalTasks(self.root / 'state', LocalFiles(self.home, self.clock),
                                self.search, self.clock, root=self.root)
        self.chat = self.new_chat()
        self.cid = self.chat.new_conversation()['id']
        self.network = patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('Network forbidden'))
        self.network.start()
        self.addCleanup(self.network.stop)

    def new_chat(self):
        chat = Chat(self.root / 'chat', self.root, self.providers, texting=Texting(Mock(), Mock(), clock=self.clock),
                    reminder_notifier=self.notifier, calendar=self.calendar, local_tasks=self.local)
        chat.reminders.clock = self.clock
        self.addCleanup(chat.close)
        return chat

    def submit(self, text, chat=None):
        with patch('app.parse_work', side_effect=AssertionError('Personal action entered coding queue')):
            return (chat or self.chat).submit(self.cid, text, str(uuid.uuid4()), actor='owner')['messages'][-1]

    def save_calendar_routine(self, text='every morning do show my calendar today'):
        receipt = self.submit(text)
        self.assertIn('Read-only routine saved:', receipt['content'])
        row, = self.chat.reminders.listing()
        self.assertEqual(row['action'], 'show my calendar today')
        return row

    def test_today_routine_helper_is_exact(self):
        self.assertTrue(today_routine('show my calendar today'))
        self.assertTrue(today_routine('Please show my calendar today.'))
        for text in ('show my calendar tomorrow', 'calendar today', 'create a calendar event Dentist tomorrow at 2pm',
                     'show my calendar today and invite Alex', 'show my calendar today; send a text'):
            self.assertFalse(today_routine(text))

    def test_one_due_read_uses_existing_calendar_path(self):
        self.client.response = {'items': [
            {'summary': 'Standup', 'start': {'dateTime': '2026-10-10T14:00:00-05:00'}}]}
        row = self.save_calendar_routine()
        self.chat.deliver_reminders()
        self.assertFalse(self.client.reads)
        self.now = row['due_at']
        self.chat.deliver_reminders()
        notice = self.chat.history(self.cid)['messages'][-1]
        self.assertIn('Routine result', notice['content'])
        self.assertIn('Standup', notice['content'])
        self.assertEqual(notice['reminder_id'], row['id'])
        self.assertTrue(notice.get('reminder_notice'))
        self.assertEqual(len(self.client.reads), 1)
        self.assertFalse(self.client.creates)
        self.assertFalse(self.providers.calls)
        self.assertFalse(task_queue.tasks(self.root))
        self.notifier.assert_not_called()
        self.chat.deliver_reminders()
        self.assertEqual(len(self.client.reads), 1)
        self.assertEqual(self.chat.reminders.listing()[0]['occurrences'], 1)

    def test_restart_catchup_deduplicates_the_same_occurrence(self):
        row = self.save_calendar_routine()
        self.now = row['due_at'] + 3 * 86400
        self.chat.close()
        restored = self.new_chat()
        restored.deliver_reminders()
        restored.deliver_reminders()
        self.assertEqual(len(self.client.reads), 1)
        self.assertEqual(sum(1 for m in restored.history(self.cid)['messages']
                             if m.get('reminder_id') == row['id']), 1)
        self.assertEqual(restored.reminders.listing()[0]['occurrences'], 1)
        due = datetime.fromtimestamp(restored.reminders.listing()[0]['due_at'], ZONE)
        self.assertEqual((due.hour, due.minute), (9, 0))
        self.assertGreater(restored.reminders.listing()[0]['due_at'], self.now)

    def test_hold_is_checked_before_calendar_auth(self):
        row = self.save_calendar_routine()
        self.chat.submit(self.cid, 'Hold all work', str(uuid.uuid4()))
        before = copy.deepcopy(self.chat.get(self.cid)['intent_state'])
        self.now = row['due_at']
        with patch.object(self.client, 'configured') as configured, \
                patch.object(self.client, 'listing') as listing:
            self.chat.deliver_reminders()
            configured.assert_not_called()
            listing.assert_not_called()
        self.assertEqual(self.chat.get(self.cid)['intent_state'], before)
        self.assertEqual(self.chat.reminders.listing()[0]['occurrences'], 0)
        self.assertFalse(self.client.creates)

    def test_cancellation_prevents_the_scheduled_read(self):
        row = self.save_calendar_routine()
        self.submit('cancel routine ' + row['id'])
        self.now = row['due_at']
        self.chat.deliver_reminders()
        self.assertFalse(self.client.reads)
        self.assertFalse(self.client.creates)

    def test_auth_expiry_is_a_failed_read_not_an_empty_calendar(self):
        row = self.save_calendar_routine()
        self.client.error = NEEDS_AUTH
        self.now = row['due_at']
        self.chat.deliver_reminders()
        content = self.chat.history(self.cid)['messages'][-1]['content']
        self.assertIn('needs auth', content)
        self.assertNotIn('No events', content)
        self.assertNotIn('empty', content.lower())
        self.assertFalse(self.client.creates)
        self.assertEqual(self.chat.reminders.listing()[0]['occurrences'], 1)

    def test_busy_chat_defers_without_calling_calendar(self):
        row = self.save_calendar_routine()
        self.now = row['due_at']
        with patch.object(self.chat.voice, 'busy', return_value=True):
            self.chat.deliver_reminders()
        self.assertFalse(self.client.reads)
        self.assertEqual(self.chat.reminders.listing()[0]['occurrences'], 0)
        self.chat.deliver_reminders()
        self.assertEqual(len(self.client.reads), 1)

    def test_invalid_calendar_payload_is_disclosed_as_failure(self):
        row = self.save_calendar_routine()
        self.client.response = {'items': [{}]}
        self.now = row['due_at']
        self.chat.deliver_reminders()
        content = self.chat.history(self.cid)['messages'][-1]['content']
        self.assertIn('no listing was verified', content)
        self.assertNotIn('No events', content)
        self.assertFalse(self.client.creates)

    def test_create_invite_delete_and_send_routines_are_rejected(self):
        for body in ('create a calendar event Dentist tomorrow at 2pm',
                     'show my calendar today and invite Alex',
                     'delete file ~/Documents/note.txt',
                     'send a text to Alex: Hi',
                     'show my calendar today; send a text'):
            with self.subTest(body=body):
                reply = self.submit('every morning do ' + body)['content']
                self.assertNotIn('Read-only routine saved:', reply)
                self.assertNotIn('Reminder saved:', reply)
        self.assertFalse(self.chat.reminders.listing())
        self.assertEqual(self.file.read_text(), 'original')
        self.assertFalse(self.client.creates)
        self.assertFalse(self.client.reads)
        self.assertFalse(task_queue.tasks(self.root))

    def test_one_action_per_tick_still_applies_with_calendar_and_lookup(self):
        self.submit('every morning do show my calendar today')
        self.submit('every morning do look up Python')
        self.now += 86400
        self.chat.deliver_reminders()
        self.assertEqual(len(self.client.reads) + self.search.call_count, 1)
        self.chat.deliver_reminders()
        self.assertEqual(len(self.client.reads), 1)
        self.assertEqual(self.search.call_count, 1)
        self.assertFalse(self.client.creates)


if __name__ == '__main__':
    unittest.main()
