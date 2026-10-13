"""Round-eight regressions: private stores, inert transports, no model calls.

Prompt assertions verify delivered guidance, not generated quality or H2H gains.
"""
import copy

import unittest

import test_h2h_round4 as fixtures
from personal_drafts import handle, pending
from task_dispatch import task_queue


class RoundEightTests(unittest.TestCase):
    setUp = fixtures.RoundFourTests.setUp
    say = fixtures.RoundFourTests.say
    policy = fixtures.RoundFourTests.policy

    def test_missing_send_target_requests_recipient_and_exact_review(self):
        for ask in ('send it', 'SEND IT NOW!', 'yeah whatever you think, send it'):
            with self.subTest(ask=ask):
                reply = self.say(ask)['content']
                self.assertIn('draft and recipient', reply)
                self.assertIn('exact message', reply)
                self.assertIn('for your OK before sending', reply)
                self.assertFalse(pending(self.chat, self.chat.get(self.cid)))
        self.bridge.deliver.assert_not_called()
        self.client.create.assert_not_called()
        self.assertFalse(task_queue.tasks(self.root))

    def test_generic_approval_keeps_round7_context_question(self):
        for ask in ('OK', 'do it', 'Sounds good, go ahead with that.'):
            self.assertEqual(self.say(ask)['content'],
                             'Which action or draft do you mean? I’m missing the context for that approval.')
        self.bridge.deliver.assert_not_called()

    def test_send_with_existing_draft_still_requires_full_token(self):
        card = self.say('Draft a text to the band: Please bring the charts.')['text_draft']
        conversation = self.chat.get(self.cid)
        before = copy.deepcopy(conversation['_texting']['drafts'])
        row = before[card['id']]
        self.assertRegex(row['token'], r'^wbtxt-[a-f0-9]{32}$')
        for ask in ('send it', 'send it now', 'yeah whatever you think, send it'):
            reply = handle(self.chat, conversation, ask, 'later')
            # Texting owns this state; returning None delegates to its unchanged validation.
            if reply is not None:
                self.assertIn(row['token'], reply)
            self.say(ask)
        self.assertEqual(self.chat.get(self.cid)['_texting']['drafts'], before)
        rejected = self.say('yes ' + row['token'][:12])['content']
        self.assertIn('Nothing sent', rejected)
        invalidated = self.chat.get(self.cid)['_texting']['drafts'][card['id']]
        self.assertEqual(invalidated['state'], 'superseded')
        self.assertIsNone(invalidated['token'])
        self.bridge.deliver.assert_not_called()

    def test_send_with_multiple_pending_actions_does_not_pick_one(self):
        self.say('Email Sam the plan looks good.')
        self.chat.calendar.draft('create a calendar event Review tomorrow at 2pm', self.cid, 'older')
        conversation = self.chat.get(self.cid)
        before = copy.deepcopy(pending(self.chat, conversation))
        self.assertEqual(len(before), 2)
        reply = handle(self.chat, conversation, 'send it', 'later')
        self.assertEqual(reply, 'Which action do you want to approve? There’s more than one pending draft or proposal.')
        self.assertEqual(pending(self.chat, conversation), before)
        self.bridge.deliver.assert_not_called()
        self.client.create.assert_not_called()

    def test_thank_you_note_preserves_identical_recorded_answer(self):
        reply = self.say('Write a quick thank-you note to the venue owner for having us last weekend.')['content']
        self.assertEqual(reply, 'Draft for the venue owner:\n\nHi there,\n\n'
                         'Thanks for having us last weekend. We really appreciate it and would love to come back.\n\n'
                         'Thanks again,\nJeff\n\nI’ll wait for your OK before sending.')
        self.assertEqual(self.chat.get(self.cid)['_personal_action']['state'], 'draft')
        self.bridge.deliver.assert_not_called()

    def test_missing_document_guidance_requests_content_and_useful_summary(self):
        for ask in ('Summarize the PDF I sent you yesterday.',
                    'Give me the key takeaways from the report I shared last week.',
                    'What decisions are in the attached meeting notes?'):
            with self.subTest(ask=ask):
                rules = self.policy(ask)
                for part in ('ask for an attachment or pasted text',
                             'main points, plus decisions and action items if present',
                             'do not invent file-retention or session-storage policies',
                             'A filename alone is not document contents',
                             'Use supplied document contents when available',
                             'Version comparisons apply only when selecting the latest version'):
                    self.assertIn(part, rules)

    def test_batch_rename_guidance_resolves_semantic_date_and_collisions(self):
        for ask in ('Rename all the demo mp3s so they start with the date.',
                    'Put a date prefix on the photos in my archive.',
                    'Prefix every recording with its recording date.',
                    'Use 2026-09-01 as the prefix for all files in this folder.'):
            with self.subTest(ask=ask):
                rules = self.policy(ask)
                for part in ('ask which date the user means',
                             'recording/content date, file creation date, or one date for the batch',
                             'Do not substitute modification time for the intended date',
                             'Honor an explicitly supplied date or date source without asking again',
                             'old-to-new filename preview', 'collisions and existing prefixes',
                             'wait for OK before renaming'):
                    self.assertIn(part, rules)
        self.assertFalse(task_queue.tasks(self.root))

    def test_clock_guidance_offers_conversion_without_invented_now(self):
        for ask in ('What time is it in Tokyo right now?',
                    'What time is it in Lisbon?',
                    'It is 11:30 pm on July 4 in Chicago; what time is that in Tokyo?'):
            with self.subTest(ask=ask):
                rules = self.policy(ask)
                for part in ('use only a supplied clock reading or dated reference time',
                             'ask for the local date and time, and timezone if unknown',
                             'known timezone offsets, date-dependent daylight saving and day rollover',
                             'Never invent a session timestamp or assume the user’s location',
                             'If an anchor is already supplied, convert it without asking again'):
                    self.assertIn(part, rules)

    def test_conflict_guidance_uses_one_natural_evidence_statement(self):
        for ask in ('Do I have anything conflicting with the show night on the 24th?',
                    'Does the afternoon workshop overlap anything on my calendar?'):
            with self.subTest(ask=ask):
                rules = self.policy(ask)
                for part in ('missing month/date and start/end times',
                             'including travel and preparation time', 'conflicts remain unchecked',
                             'natural first-person wording once',
                             'Do not repeat a calendar-fetch disclaimer',
                             'do not assume a load-in requirement'):
                    self.assertIn(part, rules)

    def test_short_social_drafts_avoid_unrequested_email_templates(self):
        for ask in ('Help me word a polite no to playing a free benefit show next month.',
                    'Help us politely decline a dinner invitation.',
                    'Write a short reply declining the panel invitation.'):
            with self.subTest(ask=ask):
                rules = self.policy(ask)
                for part in ('short social wording, give a ready-to-use message body',
                             'Add a subject only when the user requests a new email',
                             'omit optional name/signature placeholders',
                             'Preserve supplied singular or group voice',
                             'do not add future-contact commitments',
                             'I’ll wait for your OK before sending.'):
                    self.assertIn(part, rules)

    def test_naming_quality_check_preserves_factual_bio_boundary(self):
        for ask in ('Give me 5 name ideas for our next EP, punk vibe, dad humor.',
                    'Suggest three jazz album titles with cat puns.',
                    'Name our sci-fi comedy podcast. Give me six options.'):
            with self.subTest(ask=ask):
                rules = self.policy(ask)
                for part in ('requested number of names', 'recognizable references from the requested genre',
                             'Check each option for both a recognizable genre cue and the requested joke/theme',
                             'Vary reference sources and joke subjects',
                             'compact standalone title', 'remove accidental markup',
                             'naming guidance applies to invented titles, not factual bios or descriptions',
                             'restrained humor only if requested'):
                    self.assertIn(part, rules)
                self.assertNotIn('Never Mind the Bedtime', rules)
                self.assertNotIn('Anarchy in the PTA', rules)


if __name__ == '__main__':
    unittest.main()
