"""Direct PR1 actions use local storage, never a report worker or send API."""
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch
import uuid

import actions_intent
from app import Chat
from reminders import Reminders, ZONE, parse
from task_dispatch import task_queue
from texting_fixture import OfflineProviders


class ActionIntentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.now = datetime(2026, 10, 10, 1, 47, tzinfo=ZONE).timestamp()
        self.store = Reminders(self.root, clock=lambda: self.now)

    def test_all_requested_verb_and_action_synonyms(self):
        due = datetime(2026, 10, 10, 2, tzinfo=ZONE).timestamp()
        for verb in ('Create', 'Set', 'Set up', 'Schedule'):
            for noun in ('a reminder', 'a timer', 'an alarm', 'reminder', 'timer', 'alarm'):
                text = f'{verb} {noun} for 2am to go to bed'
                with self.subTest(text=text):
                    self.assertEqual(parse(text, self.now), ('go to bed', due, None))
                    receipt = actions_intent.handle(self.store, text, 'chat', text)
                    self.assertIn('Reminder saved: go to bed', receipt)

    def test_supported_clause_orders_and_sensible_body_defaults(self):
        cases = [
            ('Set a timer for 10 minutes', 'Timer', self.now + 600),
            ('Set a timer in 10 seconds to check oven', 'check oven', self.now + 10),
            ('Create a reminder to check oven in 1 hour', 'check oven', self.now + 3600),
            ('Please set an alarm at 2am', 'Alarm', self.now + 780),
            ('Could you schedule a reminder for 2am to go to bed?', 'go to bed', self.now + 780),
            ('Set up a reminder for tomorrow at 2am to go to bed', 'go to bed', self.now + 86400 + 780),
            ('Schedule a reminder on 2026-10-10 at 02:00 to go to bed', 'go to bed', self.now + 780),
            ('Set a reminder at 2026-10-10T07:00:00Z to go to bed', 'go to bed', self.now + 780),
            ('Remind me to go to bed at 2am', 'go to bed', self.now + 780),
            ('Remind me at 2am to go to bed', 'go to bed', self.now + 780),
        ]
        for text, body, due in cases:
            with self.subTest(text=text):
                self.assertEqual(parse(text, self.now), (body, due, None))

    def test_missing_ambiguous_or_invalid_time_is_never_saved(self):
        for text in ('Create a reminder to go to bed', 'Set a timer', 'Schedule an alarm sometime soon',
                     'Set a reminder for next Tuesday to call Sam', 'Set an alarm for 2am tomorrow',
                     'Set an alarm for 2am UTC', 'Set an alarm for 2am every day',
                     'Set an alarm for 25:00', 'Set an alarm for 13pm', 'Set a timer for 0 seconds',
                     'Set a timer for 367 days', 'Set an alarm today at 1am',
                     'Create a reminder for 2026-11-01 at 01:30 to stretch',
                     'Create a reminder for 2027-03-14 at 02:30 to stretch'):
            with self.subTest(text=text):
                receipt = actions_intent.handle(self.store, text, 'chat', text)
                self.assertIsNotNone(receipt)
                self.assertNotIn('Reminder saved:', receipt)
        self.assertFalse(self.store.listing())

    def test_other_actions_questions_negation_and_quotes_do_not_match(self):
        for text in ('Create a calendar event at 2am', 'Create a reminder component in app.py',
                     'Text Sam at 2am', 'Delete my reminders', 'Buy a timer',
                     'Do not create a reminder for 2am', 'Explain how to create a timer',
                     '"Create a reminder for 2am"', 'Can you create reminders?',
                     'Create a file', 'Start a job: create a timer for 10 minutes'):
            with self.subTest(text=text):
                if text == 'Create a reminder component in app.py':
                    # Even a recognized noun cannot cause a guessed schedule.
                    self.assertIsNone(parse(text, self.now))
                else:
                    self.assertIsNone(actions_intent.handle(self.store, text, 'chat', text))
        self.assertFalse(self.store.listing())

    def test_incomplete_action_is_intercepted_before_generic_work(self):
        providers = OfflineProviders()
        chat = Chat(self.root / 'chat', self.root, providers, reminder_notifier=Mock())
        self.addCleanup(chat.close)
        cid = chat.new_conversation()['id']
        with patch('app.parse_work', side_effect=AssertionError('Entered job queue')):
            reply = chat.submit(cid, 'Create a reminder to go to bed', str(uuid.uuid4()))['messages'][-1]
        self.assertEqual(reply['provider'], 'reminders')
        self.assertNotIn('Reminder saved:', reply['content'])
        self.assertFalse(chat.reminders.listing())
        self.assertFalse(task_queue.tasks(self.root))
        self.assertFalse(providers.calls)

    def test_risky_body_is_only_reminder_text_never_a_send_or_job(self):
        providers = OfflineProviders()
        notify = Mock()
        chat = Chat(self.root / 'chat', self.root, providers, reminder_notifier=notify)
        self.addCleanup(chat.close)
        chat.reminders.clock = lambda: self.now
        cid = chat.new_conversation()['id']
        body = 'text Alex, delete a file, and spend money'
        chat.submit(cid, 'Create a reminder in 1 second to ' + body, str(uuid.uuid4()))
        self.now += 2
        chat.deliver_reminders()
        self.assertIn('Reminder: ' + body, chat.history(cid)['messages'][-1]['content'])
        self.assertFalse(chat.conversations[cid].get('_texting', {}).get('audit'))
        self.assertFalse(task_queue.tasks(self.root))
        self.assertFalse(providers.calls)
        notify.assert_called_once_with(body)


if __name__ == '__main__':
    unittest.main()
