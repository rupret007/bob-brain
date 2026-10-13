"""Round-three eval regressions using private stores and inert transports."""
from datetime import datetime
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import Mock, patch
import uuid

from app import Chat
from calendar_actions import CalendarActions
from reminders import ZONE
from reply_quality import check, creative_request
from task_dispatch import task_queue
from texting import Texting, fingerprint
from texting_fixture import OfflineProviders


class RoundThreeTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.providers = OfflineProviders()
        self.client = Mock()
        self.now = datetime(2026, 10, 12, 22, 1, 43, tzinfo=ZONE).timestamp()
        self.bb, self.bridge = Mock(), Mock()
        self.bridge.prepare.return_value = None
        self.bridge.deliver.side_effect = AssertionError('No delivery allowed')
        self.bb.chats.return_value = [
            dict(guid='iMessage;+;band', displayName='The Band', participants=[dict(address='band@example.test')]),
            dict(guid='iMessage;+;pops', displayName='Pops of Punk', participants=[dict(address='pops@example.test')]),
        ]
        self.bb.exact_chat.return_value = []
        self.chat = Chat(self.root / 'chat', self.root, self.providers,
                         texting=Texting(self.bb, self.bridge),
                         calendar=CalendarActions(self.root, self.client, lambda: self.now))
        self.addCleanup(self.chat.close)
        self.chat.reminders.clock = lambda: self.now
        self.cid = self.chat.new_conversation()['id']
        for target in ('urllib.request.OpenerDirector.open', 'reminders.notify_macos'):
            guard = patch(target, side_effect=AssertionError('External effects forbidden'))
            guard.start()
            self.addCleanup(guard.stop)

    def say(self, text):
        self.chat.submit(self.cid, text, str(uuid.uuid4()), actor='fixture')
        end = time.monotonic() + 5
        while self.cid in self.chat.workers and time.monotonic() < end:
            time.sleep(.01)
        self.assertNotIn(self.cid, self.chat.workers)
        return self.chat.history(self.cid)['messages'][-1]

    def test_band_hold_clauses_are_instructions_not_message_content(self):
        for suffix in (", but don't send it yet.", ", don't send yet.",
                       ', hold off sending.', ', hold off on sending for now.',
                       ', for now.', '; do not send it yet.',
                       ' — keep it as a draft for now.', '. Show me first.',
                       ', but don’t send it yet.', ", but don't send it yet, for now."):
            with self.subTest(suffix=suffix):
                reply = self.say('Draft a text to the band saying practice is moved to Thursday at 7' + suffix)
                card = reply['text_draft']
                self.assertEqual(card['body'], 'Practice is moved to Thursday at 7.')
                self.assertEqual(card['recipient']['guid'], 'iMessage;+;band')
                self.assertEqual(card['state'], 'pending')
                self.assertRegex(card['confirm_message'], r'^yes wbtxt-[a-f0-9]{32}$')
                stored = self.chat.get(self.cid)['_texting']['drafts'][card['id']]
                self.assertEqual(stored['body'], card['body'])
                self.assertEqual(stored['fingerprint'], fingerprint(stored))
                self.assertIn('exact', self.say('send it')['content'])
                self.bridge.deliver.assert_not_called()
        self.assertFalse(self.providers.calls)

    def test_quoted_and_meaningful_hold_words_remain_literal(self):
        for body in ('"Practice is moved, but don’t send it yet."',
                     'We need a drummer for now.', 'Tell Mike not to send the setlist yet.'):
            with self.subTest(body=body):
                reply = self.say('Draft a text to the band: ' + body)
                self.assertEqual(reply['text_draft']['body'], body)
        self.bridge.deliver.assert_not_called()

    def test_group_wrappers_resolve_with_exact_token_and_no_send(self):
        for target in ('the Pops of Punk group chat', 'POPS OF PUNK group',
                       'Pops of Punk chat', 'the pops of punk thread'):
            with self.subTest(target=target):
                reply = self.say('Tell ' + target + ' we need a setlist by Wednesday.')
                card = reply['text_draft']
                self.assertEqual(card['body'], 'We need a setlist by Wednesday.')
                self.assertEqual(card['recipient']['guid'], 'iMessage;+;pops')
                self.assertIn('Reply exactly', reply['content'])
                self.assertEqual(card['state'], 'pending')
                self.assertIn('exact', self.say('yes')['content'])
        self.bridge.deliver.assert_not_called()
        self.assertFalse(self.providers.calls)

    def test_normalized_ambiguous_groups_never_prepare_any_draft(self):
        self.bb.chats.return_value.append(dict(guid='SMS;+;other', displayName='THE POPS OF PUNK',
                                              participants=[dict(address='other@example.test')]))
        for target in ('the Pops of Punk group chat', 'Pops of Punk group',
                       'Pops of Punk chat', 'Pops of Punk thread'):
            with self.subTest(target=target):
                reply = self.say('Tell ' + target + ' we need a setlist by Wednesday.')
                self.assertIn('Several threads match', reply['content'])
                self.assertNotIn('text_draft', reply)
                saved = self.chat.get(self.cid)
                self.assertFalse(saved.get('_texting', {}).get('drafts'))
                self.assertNotIn('_personal_action', saved)
        self.bridge.prepare.assert_not_called()
        self.bridge.deliver.assert_not_called()
        self.assertFalse(self.providers.calls)

    def test_exact_thread_id_still_disambiguates_normalized_names(self):
        self.bb.chats.return_value.append(dict(guid='SMS;+;other', displayName='Pops of Punk',
                                              participants=[dict(address='other@example.test')]))
        reply = self.say('Draft a text to iMessage;+;pops: We need a setlist by Wednesday.')
        self.assertEqual(reply['text_draft']['recipient']['guid'], 'iMessage;+;pops')
        self.bridge.deliver.assert_not_called()

    def test_relative_oven_has_no_computed_clock_and_schedules_nothing(self):
        reply = self.say('Can you remind me in 20 min to check the oven')['content']
        self.assertEqual(reply.splitlines()[0], 'Reminder to check the oven in 20 minutes — OK to set it?')
        self.assertIn('Nothing was saved to your reminders yet.', reply)
        self.assertRegex(reply, r'reply exactly “yes wbrem-[a-f0-9]{32}”')
        self.assertNotRegex(reply, r'\d{1,2}:\d{2}|\b(?:AM|PM)\b')
        self.assertFalse(self.chat.reminders.listing())
        row, = json.loads((self.chat.reminders.folder / 'drafts.json').read_text()).values()
        self.assertEqual(row['due'], self.now + 1200)
        self.assertEqual(row['state'], 'draft')

    def test_venue_note_has_specific_warm_body_greeting_and_signature(self):
        reply = self.say('Write a quick thank-you note to the venue owner for having us last weekend.')
        body = self.chat.get(self.cid)['_personal_action']['body']
        self.assertTrue(body.startswith('Hi there,\n\n'))
        self.assertIn('Thanks for having us last weekend.', body)
        self.assertIn('our music at your venue', body)
        self.assertIn('come back for another show', body)
        self.assertTrue(body.endswith('Thanks again,\nJeff'))
        self.assertGreater(len(body.split()), 55)
        self.assertIn(body, reply['content'])
        self.assertIn('pending', self.say('go ahead')['content'])
        self.assertFalse(task_queue.tasks(self.root))
        self.bridge.deliver.assert_not_called()

    def test_full_punny_ep_names_take_model_path_and_survive_unchanged(self):
        ask = 'Give me 5 name ideas for our next EP, punk vibe, dad humor.'
        output = ('1. **Anarchy in the PTA** — Permission slips meet power chords.\n'
                  '2. **Never Mind the Bedtime** — A rebellion with a strict lights-out policy.\n'
                  '3. **No Sleep Till Costco** — Bulk-buy the snacks for the pit.\n'
                  '4. **New Balance of Power** — Lawn shoes, loud guitars.\n'
                  '5. **Rage Against the Receipt** — The handback is non-refundable.')
        self.providers.reply = Mock(return_value=dict(content=output, provider='fixture', attempts=[]))
        reply = self.say(ask)
        self.providers.reply.assert_called_once()
        self.assertEqual(reply['provider'], 'fixture')
        self.assertEqual(reply['content'], output)
        self.assertEqual(check(ask, output), output)
        self.assertNotIn('_personal_action', self.chat.get(self.cid))
        self.assertFalse(task_queue.tasks(self.root))

    def test_full_model_written_note_preserves_paragraphs_and_signoff(self):
        ask = 'Write a warm note to our fans about the EP.'
        body = ('Hey everyone,\n\nThanks for making room for our music in your day. '
                'This EP is for every dad who still has a little punk in him.\n\n'
                'Keep the receipt, turn up the volume, and tell us which song sticks with you.\n\n'
                'See you in the pit,\nJeff and the band')
        self.providers.reply = Mock(return_value=dict(content=json.dumps(dict(artifact=body, commentary='')),
                                                      provider='fixture', attempts=[]))
        reply = self.say(ask)
        self.providers.reply.assert_called_once()
        self.assertEqual(reply['content'], body)
        self.assertTrue(reply['artifact']['accepted'])
        self.bridge.deliver.assert_not_called()

    def test_dentist_spreadsheet_and_research_keep_their_routes(self):
        dentist = 'Move my dentist appointment to next week sometime.'
        self.providers.reply = Mock(return_value=dict(content='What days and times next week work for you?',
                                                      provider='fixture', attempts=[]))
        self.assertFalse(creative_request(dentist))
        self.assertEqual(self.say(dentist)['provider'], 'fixture')
        self.client.create.assert_not_called()
        reply = self.say('Make me a simple spreadsheet to track gig payments: date, venue, amount, paid yes/no.')
        self.assertEqual(reply['provider'], 'dispatcher')
        self.assertIn('date, venue, amount, paid yes/no', reply['content'])
        self.assertIn('No job has started', reply['content'])
        self.assertFalse(task_queue.tasks(self.root))
        from answer_intent import requires_research
        for ask in ('Research the latest Gemini pricing and cite sources',
                    'Research current venue prices online and write a report'):
            self.assertTrue(requires_research(ask))
            self.assertFalse(creative_request(ask))
        for ask in ("What's the difference between a Roth IRA and a traditional IRA, quickly?",
                    'Best budget in-ear monitors for a drummer under $200?',
                    'How long should I let a brisket rest after smoking?',
                    'Is it worth upgrading from an M1 Mac mini to the newest one for music production?',
                    'What are the rules for adopting a dog from a shelter in Illinois, generally?',
                    "Explain what a capo does like I'm a beginner.",
                    'What time is it in Tokyo right now?'):
            with self.subTest(ask=ask):
                self.assertFalse(creative_request(ask))
                # Capo explanations already use the read-only music helper.
                expected = 'state' if ask.startswith('Explain what a capo') else 'fixture'
                self.assertEqual(self.say(ask)['provider'], expected)


if __name__ == '__main__':
    unittest.main()
