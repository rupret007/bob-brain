"""Round-seven presentation regressions with private state and inert transports.

Prompt checks verify delivered guidance, not sampled model quality or H2H scores.
"""
import copy
import unittest
from unittest.mock import Mock

import test_h2h_round4 as fixtures
import chat_intent
from calendar_actions import CalendarError, NEEDS_AUTH
from personal_drafts import handle, pending
from task_dispatch import task_queue
from texting import fingerprint


class RoundSevenTests(unittest.TestCase):
    setUp = fixtures.RoundFourTests.setUp
    say = fixtures.RoundFourTests.say
    policy = fixtures.RoundFourTests.policy

    def test_thread_replies_have_no_invented_subject_and_conditional_approval(self):
        for person, pronoun, content in (
            ('Mike', 'him', "we're in for the gig on the 24th"),
            ('Sam', 'them', 'the revised plan looks good'),
            ('Mary Jane', 'her', 'we received the invoice'),
        ):
            with self.subTest(person=person):
                answer = self.say(f"Could you reply to {person}'s email and tell {pronoun} {content}.")['content']
                self.assertIn(f'Hi {person},', answer)
                self.assertIn(content[0].upper() + content[1:] + '.', answer)
                self.assertNotIn('Subject:', answer)
                self.assertIn('Thanks,\nJeff', answer)
                self.assertEqual(answer.splitlines()[-1],
                                 'I’d verify the email thread and recipient first. OK to send once those match?')
                self.assertEqual(answer.count('OK'), 1)
                before = copy.deepcopy(self.chat.get(self.cid)['_personal_action'])
                self.assertEqual(before['state'], 'draft')
                self.assertIn('still pending', self.say('go ahead')['content'])
                self.assertEqual(self.chat.get(self.cid)['_personal_action'], before)
        self.bridge.deliver.assert_not_called()
        self.assertFalse(task_queue.tasks(self.root))

    def test_new_email_keeps_topic_subject_and_waits_for_approval(self):
        for ask, subject in (
            ('Email my accountant asking if the quarterly estimate is due this month. Show me first.',
             'Quarterly estimate due date'),
            ('Email Sam the rehearsal plan looks good.', 'The rehearsal plan looks good'),
        ):
            with self.subTest(ask=ask):
                answer = self.say(ask)['content']
                self.assertIn('Subject: ' + subject, answer)
                self.assertTrue(answer.endswith('I’ll wait for your OK before sending.'))
        self.bridge.deliver.assert_not_called()

    def test_held_text_acknowledges_hold_and_displays_actual_full_token(self):
        for fact in ('practice is moved to Thursday at 7', 'the rehearsal room has changed'):
            with self.subTest(fact=fact):
                answer = self.say(f"Draft a text to the band saying {fact}, but don't send it yet.")
                card = answer['text_draft']
                row = self.chat.get(self.cid)['_texting']['drafts'][card['id']]
                self.assertEqual(answer['content'].splitlines()[0], 'Draft to The Band (not sent):')
                self.assertIn(fact[0].upper() + fact[1:], card['body'])
                self.assertNotIn("don't send", card['body'])
                self.assertEqual(row['body'], card['body'])
                self.assertEqual(row['fingerprint'], fingerprint(row))
                self.assertRegex(row['token'], r'^wbtxt-[a-f0-9]{32}$')
                self.assertEqual(card['confirm_message'], 'yes ' + row['token'])
                self.assertEqual(answer['content'].splitlines()[-1],
                                 f"When ready, reply `yes {row['token']}` to send.")
                self.assertEqual(row['state'], 'pending')
        self.bridge.deliver.assert_not_called()

    def test_held_text_validation_still_binds_full_token_actor_conversation_and_request(self):
        answer = self.say("Draft a text to the band: Check the charts, but don't send it yet.")
        conversation = self.chat.get(self.cid)
        row = conversation['_texting']['drafts'][answer['text_draft']['id']]
        for text in ('yes', 'go ahead', 'yes ' + row['token'][:12],
                     'please yes ' + row['token'], 'yes ' + row['token'] + ' please'):
            self.assertIn('Nothing sent', self.chat.texting.confirm(
                copy.deepcopy(conversation), text, 'fixture', 'later', Mock()))
        for change in ('actor', 'conversation', 'request', 'body'):
            with self.subTest(change=change):
                draft = copy.deepcopy(conversation)
                if change == 'conversation':
                    draft['id'] = 'another-conversation'
                if change == 'body':
                    draft['_texting']['drafts'][row['id']]['body'] += ' Changed.'
                result = self.chat.texting.confirm(draft, 'yes ' + row['token'],
                    'other' if change == 'actor' else 'fixture',
                    row['request_id'] if change == 'request' else 'later', Mock())
                self.assertIn('Nothing sent', result)
        self.bridge.deliver.assert_not_called()
        self.bridge.deliver.side_effect = None
        self.bridge.deliver.return_value = 'delivery_unconfirmed'
        reply = self.say('yes ' + row['token'])['content']
        self.assertIn('unconfirmed', reply.lower())
        self.assertNotRegex(reply, r'(?i)^sent\b|successfully sent')
        self.say('yes ' + row['token'])
        self.bridge.deliver.assert_called_once()

    def test_contextless_approval_does_not_assume_message_or_destination(self):
        for approval in ('Sounds good, go ahead with that.', 'OK', 'do it'):
            with self.subTest(approval=approval):
                reply = self.say(approval)['content']
                self.assertEqual(reply, 'Which action or draft do you mean? I’m missing the context for that approval.')
                self.assertFalse(pending(self.chat, self.chat.get(self.cid)))
        self.client.create.assert_not_called()
        self.bridge.deliver.assert_not_called()
        self.assertFalse(task_queue.tasks(self.root))

    def test_multiple_pending_actions_require_identification(self):
        self.say('Email Sam the plan looks good.')
        self.chat.calendar.draft('create a calendar event Review tomorrow at 2pm', self.cid, 'older')
        conversation = self.chat.get(self.cid)
        before = copy.deepcopy(pending(self.chat, conversation))
        self.assertEqual(len(before), 2)
        reply = handle(self.chat, conversation, 'go ahead', 'new')
        self.assertEqual(reply, 'Which action do you want to approve? There’s more than one pending draft or proposal.')
        self.assertEqual(pending(self.chat, conversation), before)
        self.client.create.assert_not_called()
        self.bridge.deliver.assert_not_called()

    def test_single_pending_calendar_still_requires_exact_token(self):
        answer = self.say('Put dinner with Andrea on the calendar Saturday at 7.')['content']
        self.assertIn('Assuming a one-hour event.', answer)
        self.assertIn('07:00 PM', answer)
        with self.chat.calendar.locked() as rows:
            row, = rows.values()
            row = copy.deepcopy(row)
        self.assertRegex(row['token'], r'^wbcal-[a-f0-9]{32}$')
        for approval in ('go ahead', 'yes ' + row['token'][:12]):
            self.say(approval)
        self.chat.calendar.handle('yes ' + row['token'], 'other', 'later', chat_intent.new_state())
        self.chat.calendar.handle('yes ' + row['token'], self.cid, row['request_id'], chat_intent.new_state())
        self.client.create.assert_not_called()
        with self.chat.calendar.locked() as rows:
            self.assertEqual(rows[row['token']]['state'], 'draft')

    def test_unavailable_calendar_preview_keeps_date_zone_assumption_and_pending_state(self):
        self.client.configured.side_effect = CalendarError(NEEDS_AUTH)
        answer = self.say('Put dinner with Andrea on the calendar Saturday at 7.')['content']
        self.assertEqual(answer.splitlines()[0], 'Draft for your calendar: dinner with Andrea — '
                         'Oct 17, 2026 at 07:00 PM CDT, for one hour (assumed).')
        self.assertEqual(answer.splitlines()[-1], 'OK to add it to your calendar?')
        self.assertNotIn('wbcal-', answer)
        self.assertIn('still pending', self.say('OK')['content'])
        self.assertEqual(self.chat.get(self.cid)['_personal_action']['state'], 'draft')
        self.client.create.assert_not_called()

    def test_focus_advice_is_concise_and_busy_does_not_prevent_invites(self):
        for ask in ("What's a good way to block off Friday afternoon for focus time without moving my 2pm?",
                    'How should I protect writing time around my morning standup?'):
            with self.subTest(ask=ask):
                rules = self.policy(ask)
                for phrase in ('two short sentences', 'preserving the meeting',
                               "meeting's end time and other commitments", 'Busy signals unavailability',
                               'does not prevent invitations or guarantee uninterrupted time',
                               'do not ask dates for general advice'):
                    self.assertIn(phrase, rules)
        self.client.create.assert_not_called()

    def test_bios_prioritize_usable_copy_without_inferred_performance_details(self):
        for ask in ('Write a 2-sentence bio for Rad Dad Band for a venue listing.',
                    'Write a three-sentence venue bio for Midnight Owls.',
                    'Write a brief profile for the Red Shoes quartet.'):
            with self.subTest(ask=ask):
                rules = self.policy(ask)
                for phrase in ('invented genre, repertoire', 'audience response',
                               'keep the bio centered on the band and music',
                               'restrained humor only if requested',
                               'wardrobe, habits, stage banter, schedules or musical style',
                               'disparaging jokes and ticket-demand claims', 'Honor exact sentence counts',
                               'naming guidance applies to invented titles, not factual bios or descriptions'):
                    self.assertIn(phrase, rules)
                self.assertNotIn('dad-themed names can inspire', rules)


if __name__ == '__main__':
    unittest.main()
