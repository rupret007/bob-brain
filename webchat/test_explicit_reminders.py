"""Explicit personal reminders through the same Chat path as solo staging."""
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import Mock, patch
import uuid

from app import Chat
from reminders import Reminders
from task_dispatch import task_queue
from texting_fixture import OfflineProviders


class ExplicitReminderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.providers = OfflineProviders()
        self.providers.reply = Mock(side_effect=AssertionError('No model calls'))
        self.providers.start_probes = Mock()
        self.providers.circuit = Mock()
        for target in ('urllib.request.OpenerDirector.open', 'socket.socket.connect',
                       'reminders.notify_macos'):
            guard = patch(target, side_effect=AssertionError('No external effects'))
            blocked = guard.start()
            self.addCleanup(guard.stop)
            self.addCleanup(blocked.assert_not_called)
        self.chat = Chat(self.root / 'conductor/webchat', self.root, self.providers)
        self.addCleanup(self.chat.close)
        self.cid = self.chat.new_conversation()['id']

    def say(self, text, request_id=None):
        return self.chat.submit(self.cid, text, request_id or str(uuid.uuid4()))['messages'][-1]

    def test_release_replay_saves_and_background_loop_delivers_exactly_once(self):
        body = 'Web Bob local reminder replay ' + uuid.uuid4().hex[:8]
        message = 'remind me to ' + body + ' in 1 second'
        request_id = str(uuid.uuid4())
        answer = self.say(message, request_id)
        self.assertEqual(answer['provider'], 'reminders')
        self.assertIn('Reminder saved', answer['content'])
        self.assertEqual(self.say(message, request_id), answer)
        row, = self.chat.reminders.listing()
        self.assertEqual(row['body'], body)
        self.assertEqual(row['state'], 'pending')

        self.chat.start_background()
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            notices = [m for m in self.chat.history(self.cid)['messages']
                       if m.get('reminder_notice') and body in m['content']]
            if notices:
                break
            time.sleep(.05)
        self.assertEqual(len(notices), 1, 'Background loop must deliver the due reminder')
        self.assertEqual(notices[0]['provider'], 'reminders')
        self.assertIn('Reminder: ' + body, notices[0]['content'])
        self.chat.close()

        restored = Chat(self.chat.folder, self.root, self.providers)
        self.addCleanup(restored.close)
        restored.deliver_reminders()
        durable = json.loads((restored.state / (self.cid + '.json')).read_text())
        self.assertEqual([m for m in durable['messages'] if m.get('reminder_notice')], notices)
        self.assertEqual(restored.reminders.listing()[0]['state'], 'fired')
        self.assertFalse(task_queue.tasks(self.root))
        self.assertFalse(durable.get('_texting', {}).get('audit'))
        self.providers.reply.assert_not_called()

    def test_release_recurring_followup_saves_and_cancels_durably(self):
        body = 'Web Bob local reminder replay ' + uuid.uuid4().hex[:8] + ' recurring'
        answer = self.say('remind me every 1 minute to ' + body)
        self.assertEqual(answer['provider'], 'reminders')
        self.assertIn('Reminder saved', answer['content'])
        identifier = re.search(r'ID ([0-9a-f]{16})', answer['content'])[1]
        row, = self.chat.reminders.listing()
        self.assertEqual(row['id'], identifier)
        self.assertEqual(row['body'], body)
        self.assertEqual(row['interval_seconds'], 60)
        self.assertIn('cancelled', self.say('cancel reminder ' + identifier)['content'])
        restored = Reminders(self.chat.folder)
        self.assertEqual(restored.listing()[0]['state'], 'cancelled')
        self.providers.reply.assert_not_called()

    def test_other_bodies_and_delays_use_the_same_explicit_request_path(self):
        for message, body, delay in (
            ('remind me to move the laundry in 2 minutes', 'move the laundry', 120),
            ('Please remind me to water the plants in 1 hour', 'water the plants', 3600),
            ('Remind me to stretch in 2 hrs', 'stretch', 7200),
        ):
            with self.subTest(message=message):
                now = time.time()
                answer = self.say(message)
                self.assertEqual(answer['provider'], 'reminders')
                self.assertIn('Reminder saved', answer['content'])
                row, = [r for r in self.chat.reminders.listing() if r['body'] == body]
                self.assertAlmostEqual(row['due_at'] - now, delay, delta=2)
        self.providers.reply.assert_not_called()

    def test_explicit_request_replaces_older_confirmation_authority(self):
        draft = self.say('Could you remind me in 1 hour to water the plants')
        confirmation = re.search(r'yes wbrem-[0-9a-f]{32}', draft['content'])[0]
        self.assertFalse(self.chat.reminders.listing())
        self.assertIn('Reminder saved', self.say('remind me to water the plants in 2 hours')['content'])
        self.assertIn('replaced', self.say(confirmation)['content'])
        self.assertEqual(len(self.chat.reminders.listing()), 1)
        self.providers.reply.assert_not_called()

    def test_explicit_request_still_honors_constraints_and_saved_holds(self):
        for suffix in (', but ask me before saving it', ', draft only', ', wait for my OK'):
            with self.subTest(suffix=suffix):
                self.say('remind me to water the plants in 1 second' + suffix)
                self.assertFalse(self.chat.reminders.listing())
        self.say('Hold all work')
        self.say('remind me to water the plants in 1 second')
        self.assertFalse(self.chat.reminders.listing())
        self.assertFalse(task_queue.tasks(self.root))
        self.providers.reply.assert_not_called()


if __name__ == '__main__':
    unittest.main()
