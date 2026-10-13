"""Draft presentation and ambiguity checks without any outbound transport."""
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch
import uuid

from app import Chat
from calendar_actions import CalendarActions
from reminders import ZONE
from personal_drafts import pending
from texting import TextingError
from texting_fixture import OfflineProviders
from task_dispatch import task_queue


class PersonalDraftTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.providers = OfflineProviders()
        self.client = Mock()
        self.calendar = CalendarActions(self.root, self.client,
                                        lambda: datetime(2026, 10, 12, 10, tzinfo=ZONE).timestamp())
        self.chat = Chat(self.root / 'chat', self.root, self.providers, calendar=self.calendar)
        self.addCleanup(self.chat.close)
        self.cid = self.chat.new_conversation()['id']
        self.chat.texting.resolve = Mock(return_value=dict(guid='iMessage;-;fixture',
                                           displayName='Andrea', participants=[dict(address='fixture')]))
        self.chat.texting.andrea.prepare = Mock(return_value=None)
        self.chat.texting.andrea.cancel = Mock()
        self.chat.texting.andrea.deliver = Mock(side_effect=AssertionError('must not send'))
        self.chat.texting.instinct.is_target = Mock(return_value=False)
        self.chat.texting.instinct.prepare_body = Mock(side_effect=lambda target, body: body)
        self.net = patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('network forbidden'))
        self.net.start()
        self.addCleanup(self.net.stop)

    def say(self, text):
        return self.chat.submit(self.cid, text, str(uuid.uuid4()), actor='fixture')['messages'][-1]['content']

    def test_natural_text_has_concrete_body_and_bound_question(self):
        reply = self.say("Text Andrea that I'm running 15 minutes late.")
        self.assertIn("I'm running 15 minutes late.", reply)
        self.assertRegex(reply, r'Not sent\. To send, reply: yes wbtxt-[a-f0-9]{32}$')
        self.assertIn('yes wbtxt-', reply)
        self.assertIn('exact', self.say('send it'))
        self.chat.texting.andrea.deliver.assert_not_called()

    def test_missing_channel_keeps_concrete_draft_and_no_job(self):
        for ask, body in [
            ("Reply to Mike's email and tell him we're in for the gig on the 24th.", "We're in for the gig on the 24th"),
            ('Email my accountant asking if the quarterly estimate is due this month. Show me first.', 'Could you let me know if'),
            ('Write a quick thank-you note to the venue owner for having us last weekend.', 'Thanks for having us last weekend'),
            ('Book a table for two at 7pm Friday', 'Proposed booking:'),
        ]:
            with self.subTest(ask=ask):
                reply = self.say(ask)
                self.assertIn(body, reply)
                self.assertTrue(reply.endswith('I’ll wait for your OK before sending.') if 'email' in ask.lower() else reply.endswith('?'))
                self.assertEqual(len(pending(self.chat, self.chat.get(self.cid))), 1)
                self.assertIn('pending', self.say('go ahead'))
        self.assertFalse(self.providers.calls)
        self.assertFalse(task_queue.tasks(self.root))

    def test_unresolved_text_transport_keeps_draft(self):
        self.chat.texting.resolve.side_effect = TextingError('Text transport is not configured.')
        reply = self.say('Tell the Pops of Punk group chat we need a setlist by Wednesday.')
        self.assertIn('we need a setlist by Wednesday', reply)
        self.assertIn('pending', reply)
        self.assertEqual(len(pending(self.chat, self.chat.get(self.cid))), 1)

    def test_calendar_natural_language_uses_native_separate_consent(self):
        reply = self.say('Put dinner with Andrea on the calendar Saturday at 7.')
        self.assertIn('07:00 PM', reply)
        self.assertIn('one-hour', reply)
        self.assertTrue(reply.endswith('OK to add it to your calendar?'))
        self.assertIn('yes wbcal-', reply)
        self.client.create.assert_not_called()
        self.say('Email Mike hello')
        self.assertEqual(len(pending(self.chat, self.chat.get(self.cid))), 1)
        with self.calendar.locked() as rows:
            self.assertTrue(all(row['state'] == 'replaced' for row in rows.values()))

    def test_missing_calendar_auth_keeps_draft_without_attempting_create(self):
        from calendar_actions import CalendarError, NEEDS_AUTH
        self.client.configured.side_effect = CalendarError(NEEDS_AUTH)
        reply = self.say('create a calendar event Dentist tomorrow at 2pm')
        self.assertIn('Dentist', reply)
        self.assertIn('pending', reply)
        self.assertIn('OK to add it', reply)
        self.assertEqual(len(pending(self.chat, self.chat.get(self.cid))), 1)
        self.client.create.assert_not_called()

    def test_native_text_replaces_email_in_memory_and_on_disk(self):
        import json
        self.say('Email Mike hello')
        self.say('Text Andrea that hello')
        self.assertEqual(len(pending(self.chat, self.chat.get(self.cid))), 1)
        self.assertNotIn('_personal_action', self.chat.get(self.cid))
        saved = json.loads((self.chat.state / (self.cid + '.json')).read_text())
        self.assertNotIn('_personal_action', saved)
        self.assertIn('exact', self.say('send it'))
        self.chat.texting.andrea.deliver.assert_not_called()

    def test_new_email_draft_revokes_prior_text_token(self):
        import re
        draft = self.say('Text Andrea that hello')
        token = re.search(r'yes (wbtxt-[a-f0-9]+)', draft)[1]
        self.say('Email Mike hello')
        reply = self.say('yes ' + token)
        self.assertIn('Nothing sent', reply)
        self.chat.texting.andrea.deliver.assert_not_called()

    def test_zero_and_multiple_pending_actions_need_identification(self):
        self.assertIn('Which action', self.say('Sounds good, go ahead with that.'))
        self.say('Text Andrea that hello')
        self.calendar.draft('create a calendar event Dentist tomorrow at 2pm', self.cid, 'older')
        self.assertIn('Which action', self.say('send it'))
        self.client.create.assert_not_called()
        self.chat.texting.andrea.deliver.assert_not_called()

    def test_unavailable_draft_persists_across_restart(self):
        self.say('Email Mike hello')
        restored = Chat(self.chat.folder, self.root, self.providers, calendar=self.calendar)
        self.addCleanup(restored.close)
        reply = restored.submit(self.cid, 'go ahead', str(uuid.uuid4()))['messages'][-1]['content']
        self.assertIn('draft is still pending', reply)
        self.assertNotIn('_personal_action', restored.history(self.cid))


if __name__ == '__main__':
    unittest.main()
