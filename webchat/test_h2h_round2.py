"""Round-two presentation regressions, with isolated storage and no network."""
from datetime import datetime
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import Mock, patch
import uuid

from app import Chat
from calendar_actions import CalendarActions, CalendarError, NEEDS_AUTH
import chat_intent
import ledger
from reminders import Reminders, ZONE
from reply_quality import check, creative_request
from remaining_eval import approve_reminder
from task_dispatch import task_queue
from texting_fixture import OfflineProviders


class RoundTwoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.now = datetime(2026, 10, 12, 22, 1, 43, tzinfo=ZONE).timestamp()
        self.providers = OfflineProviders()
        self.client = Mock()
        self.calendar = CalendarActions(self.root, self.client, lambda: self.now)
        self.chat = Chat(self.root / 'chat', self.root, self.providers, calendar=self.calendar)
        self.addCleanup(self.chat.close)
        self.chat.reminders.clock = lambda: self.now
        self.cid = self.chat.new_conversation()['id']
        for target in ('urllib.request.OpenerDirector.open', 'reminders.notify_macos'):
            guard = patch(target, side_effect=AssertionError('External effects forbidden'))
            guard.start()
            self.addCleanup(guard.stop)

    def say(self, ask, request_id=None):
        self.chat.submit(self.cid, ask, request_id or str(uuid.uuid4()))
        end = time.monotonic() + 5
        while self.cid in self.chat.workers and time.monotonic() < end:
            time.sleep(.01)
        self.assertNotIn(self.cid, self.chat.workers)
        return self.chat.history(self.cid)['messages'][-1]

    def test_oven_delay_clock_and_separate_durable_consent(self):
        reply = self.say('Can you remind me in 20 min to check the oven')['content']
        self.assertEqual(reply.splitlines()[0], 'Reminder to check the oven in 20 minutes (10:21 PM) — OK to set it?')
        self.assertNotIn('Proposed reminder', reply)
        self.assertIn('Nothing was saved to your reminders yet.', reply)
        self.assertFalse(self.chat.reminders.listing())
        row, = json.loads((self.chat.reminders.folder / 'drafts.json').read_text()).values()
        # Chat owns the reminder storage location; reopening it must retain the draft.
        restored = Reminders(self.chat.reminders.folder.parent, clock=lambda: self.now)
        self.assertEqual(restored.draft_receipt(row), reply)
        token = re.search(r'yes wbrem-[a-f0-9]{32}', reply)[0]
        self.say(token)
        item, = self.chat.reminders.listing()
        self.assertEqual(item['due_at'], self.now + 1200)
        self.assertEqual(item['body'], 'check the oven')
        self.assertEqual(item['state'], 'pending')
        deliver = Mock(return_value=True)
        self.chat.reminders.deliver_due(deliver)
        deliver.assert_not_called()
        self.say(token)
        self.assertEqual(len(self.chat.reminders.listing()), 1)

    def test_weekday_without_clock_stays_pending_even_if_token_is_approved(self):
        for day in ('Sunday night', 'Friday evening', 'Monday'):
            with self.subTest(day=day):
                reply = self.say(f'Set a reminder every {day} to put the trash out')['content']
                self.assertIn('put the trash out', reply)
                self.assertEqual(reply.count('?'), 1)
                self.assertTrue(reply.endswith('What time should I use?'))
                self.assertNotIn('8pm', reply)
                self.assertNotIn('yes wbrem-', reply)
                rows = json.loads((self.chat.reminders.folder / 'drafts.json').read_text())
                row, = [r for r in rows.values() if r['state'] == 'needs_time']
                self.assertNotIn('due', row)
                self.assertEqual(self.say('yes ' + row['token'])['content'], reply)
                self.assertFalse(self.chat.reminders.listing())
        self.assertFalse(self.providers.calls)

    def test_extracted_night_asks_for_time_and_morning_keeps_default(self):
        ask = 'remind me about trash every Sunday night'
        reply = self.chat.reminders.extracted(json.dumps(dict(body='trash', when='every Sunday night')),
                    ask, self.cid, 'extract', 'owner', chat_intent.new_state())
        self.assertIn('What time should I use?', reply)
        self.assertNotIn('8pm', reply)
        self.assertFalse(self.chat.reminders.listing())
        ask = 'remind me about stretching every morning'
        reply = self.chat.reminders.extracted(json.dumps(dict(body='stretching', when='every morning')),
                    ask, self.cid, 'extract-morning', 'owner', chat_intent.new_state())
        self.assertIn('Assuming morning means 9am America/Chicago.', reply)
        self.assertIn('09:00 AM', reply)
        self.assertIn('yes wbrem-', reply)
        self.assertFalse(self.chat.reminders.listing())
        with self.chat.reminders.draft_lock() as rows:
            row, = [r for r in rows.values() if r['state'] == 'draft']
        self.assertEqual(row['daily_time'], '09:00')
        self.assertIsNone(row['action'])

    def test_morning_reminder_synonyms_keep_default_and_require_consent(self):
        for ask in ('every morning remind me to stretch',
                    'remind me every morning to read file ~/Documents/note.txt',
                    'create a reminder every morning do read file ~/Documents/note.txt',
                    'set an alarm every morning to read file ~/Documents/note.txt',
                    'set a routine every morning to stretch'):
            with self.subTest(ask=ask):
                reply = self.say(ask)['content']
                self.assertIn('Assuming morning means 9am America/Chicago.', reply)
                self.assertIn('09:00 AM', reply)
                self.assertIn('OK to set it?', reply)
                self.assertIn('yes wbrem-', reply)
                self.assertFalse(self.chat.reminders.listing())
                with self.chat.reminders.draft_lock() as rows:
                    row, = [r for r in rows.values() if r['state'] == 'draft']
                self.assertEqual(row['daily_time'], '09:00')
                self.assertIsNone(row['action'])
        reply = self.say('remind me every morning at 8am to stretch')['content']
        self.assertIn('08:00 AM', reply)
        self.assertFalse(self.chat.reminders.listing())
        self.assertFalse(task_queue.tasks(self.root))
        self.assertFalse(self.providers.calls)

    def test_weekday_time_followup_after_restart_still_needs_consent(self):
        self.say('Set a reminder every Sunday night to put the trash out.')
        self.chat.reminders = Reminders(self.chat.reminders.folder.parent, clock=lambda: self.now)
        resolved = self.say('8pm')['content']
        self.assertIn('put the trash out', resolved)
        self.assertIn('08:00 PM', resolved)
        self.assertIn('every Sunday', resolved)
        self.assertNotIn('Assuming', resolved)
        self.assertFalse(self.chat.reminders.listing())
        self.say(re.search(r'yes wbrem-[a-f0-9]{32}', resolved)[0])
        row, = self.chat.reminders.listing()
        self.assertEqual(row['weekly_time'], dict(day=6, clock='8pm'))

    def test_new_wording_retains_binding_hold_and_consumed_consent(self):
        store = self.chat.reminders
        reply = store.handle('remind me in 20 minutes to review WebBob', self.cid, 'draft', actor='owner')
        token = re.search(r'yes wbrem-[a-f0-9]{32}', reply)[0]
        with patch.object(store, 'create', wraps=store.create) as create:
            store.handle(token, 'other-chat', 'confirm', actor='owner')
            store.handle(token, self.cid, 'confirm', actor='other')
            store.handle(token, self.cid, 'draft', actor='owner')
            state = chat_intent.new_state()
            chat_intent.apply_turn(state, 'Hold WebBob', 'hold')
            self.assertIn('On hold:', store.handle(token, self.cid, 'held', actor='owner', intent_state=state))
            create.assert_not_called()
            with patch.object(store, 'create', side_effect=OSError('uncertain write')) as failed:
                store.handle(token, self.cid, 'approve', actor='owner')
                store.handle(token, self.cid, 'replay', actor='owner')
                failed.assert_called_once()
            create.assert_not_called()
        self.assertFalse(store.listing())

    def test_explicit_weekly_time_keeps_dst_behavior(self):
        self.now = datetime(2026, 10, 25, 21, tzinfo=ZONE).timestamp()
        reply = self.say('Set a reminder every Sunday at 8pm to put the trash out')['content']
        self.say(re.search(r'yes wbrem-[a-f0-9]{32}', reply)[0])
        row, = self.chat.reminders.listing()
        self.assertEqual(row['due_at'], datetime(2026, 11, 1, 20, tzinfo=ZONE).timestamp())
        self.now = row['due_at']
        self.chat.reminders.deliver_due(Mock(return_value=True))
        self.assertEqual(self.chat.reminders.listing()[0]['due_at'], datetime(2026, 11, 8, 20, tzinfo=ZONE).timestamp())

    def test_venue_note_is_full_warm_draft_without_transport_claim(self):
        reply = self.say('Write a quick thank-you note to the venue owner for having us last weekend.')['content']
        self.assertIn('Hi there,\n\nThanks for having us last weekend.', reply)
        self.assertIn('We really appreciate it', reply)
        self.assertIn('\nJeff', reply)
        self.assertTrue(reply.endswith('OK to send to the venue owner?'))
        self.assertIn('draft', reply)
        self.assertNotRegex(reply, r'(?i)transport|auth|config|sent|smoothly')
        self.assertIn('draft is still pending', self.say('go ahead')['content'])
        self.assertFalse(self.providers.calls)
        self.assertFalse(task_queue.tasks(self.root))

    def test_email_and_reminder_bodies_survive_quality_pass(self):
        body = 'The receipt is for the handback'
        reply = self.say('Email Mike ' + body)['content']
        self.assertIn(body, reply)
        self.assertNotIn('transport', reply)
        reply = self.say('remind me in 10 minutes to check the lifecycle stage')['content']
        self.assertIn('check the lifecycle stage', reply)

    def test_calendar_available_and_unavailable_keep_details_without_config_prose(self):
        for unavailable in (False, True):
            with self.subTest(unavailable=unavailable):
                self.client.configured.side_effect = CalendarError(NEEDS_AUTH) if unavailable else None
                reply = self.say('Put dinner with Andrea on the calendar Saturday at 7.')['content']
                self.assertIn('dinner with Andrea', reply)
                self.assertIn('07:00 PM', reply)
                self.assertNotRegex(reply, r'(?i)auth|config|transport|OAuth')
                self.assertTrue(reply.endswith('OK to add it to your calendar?'))
                self.client.create.assert_not_called()
        reply = self.say('create a calendar event Dentist tomorrow at 2pm')['content']
        self.assertIn('Dentist', reply)
        self.assertIn('pending your OK', reply)
        self.assertNotRegex(reply, r'(?i)auth|config|transport')
        self.assertIn('pending', self.say('go ahead')['content'])

    def test_ep_names_reach_model_and_survive_quality_pass_verbatim(self):
        ask = 'Give me 5 name ideas for our next EP, punk vibe, dad humor.'
        output = '1. No receipt\n2. The handback\n3. Dad’s lifecycle stage\n4. Lawn Order\n5. New Balance of Power'
        self.providers.reply = Mock(return_value=dict(content=output, provider='fixture', attempts=[]))
        self.assertEqual(check(ask, output), output)
        reply = self.say(ask)
        self.providers.reply.assert_called_once()
        self.assertEqual(reply['content'], output)
        self.assertEqual(reply['provider'], 'fixture')
        self.assertNotIn('_personal_action', self.chat.get(self.cid))
        self.assertFalse(task_queue.tasks(self.root))

    def test_creative_writing_skips_music_template_and_quality_substitution(self):
        ask = 'Write a punk verse about a dad losing his receipt.'
        output = 'Lost my receipt in the handback pile.'
        self.providers.reply = Mock(return_value=dict(content=json.dumps(dict(artifact=output, commentary='')),
                                                      provider='fixture', attempts=[]))
        reply = self.say(ask)
        self.providers.reply.assert_called_once()
        self.assertIn(output, reply['content'])
        self.assertEqual(check(ask, output), output)

    def test_saved_brief_is_plain_and_honest_about_its_source(self):
        ledger.record_decision(self.root, 'Keep deploys on hold.')
        reply = self.say('What did we decide?')['content']
        self.assertIn('Here’s what we decided, from the saved notes:', reply)
        self.assertIn('Keep deploys on hold.', reply)
        queue = self.root / 'conductor/state/queue.jsonl'
        queue.parent.mkdir(parents=True, exist_ok=True)
        queue.write_text(json.dumps(dict(id='one', status='succeeded', prompt='Fix Web Bob login',
                                        projects=['Web Bob'], updated_at=1)) + '\n')
        reply = self.say('How are the projects going? Short version')['content']
        self.assertIn('not a live check', reply)
        self.assertIn('I haven’t confirmed deployment', reply)
        self.assertFalse(self.providers.calls)

    def test_quality_rewrite_asks_for_concrete_limits_in_plain_language(self):
        reply = check('Push everything to the max until midnight.', 'Which projects should I work on?')
        self.assertIn('draft a focused plan for your OK', reply)
        self.assertIn('until midnight', reply)
        self.assertIn('Which projects should I focus on', reply)
        self.assertIn('time and spending limits', reply)
        self.assertNotIn('resource limits', reply)

    def test_creative_routing_does_not_take_over_operational_commands(self):
        for ask in ('Hold all work on EP name ideas', 'Cancel the name ideas task',
                    'Write a poem and then deploy Web Bob', 'Rewrite the server script'):
            with self.subTest(ask=ask):
                self.assertFalse(creative_request(ask))

    def test_parity_consent_helper_preserves_pending_and_due_delivery(self):
        fixture = Mock()
        fixture.answer = self.say
        draft = self.say('remind me to check the oven in 10 minutes')
        self.assertFalse(self.chat.reminders.listing())
        confirmed = approve_reminder(fixture, draft)
        self.assertIn('no text, email or job', confirmed['content'])
        row, = self.chat.reminders.listing()
        self.assertEqual(row['state'], 'pending')
        self.assertEqual(row['due_at'], self.now + 600)
        deliver = Mock(return_value=True)
        self.chat.reminders.deliver_due(deliver)
        deliver.assert_not_called()
        self.now += 600
        self.chat.reminders.deliver_due(deliver)
        deliver.assert_called_once()
        self.assertEqual(self.chat.reminders.listing()[0]['state'], 'fired')
        self.chat.reminders.deliver_due(deliver)
        deliver.assert_called_once()


if __name__ == '__main__':
    unittest.main()
