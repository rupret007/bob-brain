"""Round-five presentation and consent regressions; private stores, inert transports.

Provider tests inspect actual assembled guidance, not sampled model behavior.
"""
import copy
import json
import re
import unittest
from unittest.mock import Mock

import test_h2h_round4 as fixtures
import ledger
from task_dispatch import task_queue
from texting import fingerprint


class RoundFiveTests(unittest.TestCase):
    setUp = fixtures.RoundFourTests.setUp
    say = fixtures.RoundFourTests.say
    policy = fixtures.RoundFourTests.policy

    def test_T04_exact_answer_and_one_approval_line(self):
        answer = self.say('Can you remind me in 20 min to check the oven')['content']
        preview, footer = answer.splitlines()
        self.assertEqual(preview, "Draft reminder: check the oven in 20 minutes. It isn't running yet—use a phone or oven timer if you need it counting now.")
        self.assertRegex(footer, r'^Reply `yes wbrem-[a-f0-9]{32}` to set\.$')
        self.assertFalse(self.chat.reminders.listing())
        self.assertNotIn('Nothing was saved', answer)

    def test_T05_advice_is_not_a_conflict_check_questionnaire(self):
        rules = self.policy("What's a good way to block off Friday afternoon for focus time without moving my 2pm?")
        for part in ('Lead with the useful answer', 'focus blocks before the existing meeting starts and after it ends, marked Busy',
                     'preserving the meeting', 'do not ask dates for general advice', 'Only for actual calendar conflict checks'):
            self.assertIn(part, rules)

    def test_T08_preferences_and_ready_office_message_wait_for_ok(self):
        rules = self.policy('Move my dentist appointment to next week sometime.')
        for part in ('first ask preferred days/times AND offer a short ready draft', 'a greeting, the requested move',
                     'question about available slots', 'Wait for OK before sending or rescheduling',
                     "other party's availability", 'availability is unverified'):
            self.assertIn(part, rules)
        self.client.create.assert_not_called()

    def test_no_disclaimer_opening_instruction_and_no_false_checks(self):
        rules = self.policy('Find the latest setlist file and tell me how many songs are on it.')
        for phrase in ('nothing has been checked or changed', 'with no calendar data in this turn'):
            self.assertNotIn(phrase, rules.lower())
        self.assertIn('one short trailing clause', rules)
        self.assertIn('never as already performed or promised background work', rules)
        self.assertIn('Never claim a file was found, opened or counted without inspected contents', rules)

    def test_natural_text_has_greeting_fact_and_relevant_cta(self):
        self.bb.chats.return_value.append(dict(guid='iMessage;+;andrea', displayName='Andrea',
                                              participants=[dict(address='andrea@example.test')]))
        for ask, body in (
            ("Text Andrea that I'm running 15 minutes late.", "Hey! I'm running 15 minutes late. Let me know if that creates a conflict."),
            ('Tell the Pops of Punk group chat we need a setlist by Wednesday.',
             'Hey! We need a setlist by Wednesday. Please share your song picks.'),
        ):
            with self.subTest(ask=ask):
                answer = self.say(ask)
                self.assertEqual(answer['text_draft']['body'], body)
                row = self.chat.get(self.cid)['_texting']['drafts'][answer['text_draft']['id']]
                self.assertEqual(row['body'], body)
                self.assertEqual(row['fingerprint'], fingerprint(row))
                self.assertEqual(answer['content'].splitlines()[-1], f"Reply `yes {row['token']}` to send.")
                self.assertNotIn('Not sent.', answer['content'])
        self.bridge.deliver.assert_not_called()

    def test_held_text_uses_polished_body_and_later_approval(self):
        answer = self.say("Draft a text to the band saying practice is moved to Thursday at 7, but don't send it yet.")
        self.assertEqual(answer['text_draft']['body'], 'Hey! Practice is moved to Thursday at 7. Let me know if that creates a conflict.')
        self.assertRegex(answer['content'].splitlines()[-1], r'^When ready, reply `yes wbtxt-[a-f0-9]{32}` to send\.$')
        self.assertNotIn('7 p.m.', answer['content'])
        self.bridge.deliver.assert_not_called()

    def test_explicit_and_quoted_text_are_not_polished(self):
        for ask, body in (
            ('Draft a text to the band: We need that setlist.', 'We need that setlist.'),
            ('Draft a text to the band saying "Practice moved, but don’t send it yet."', '"Practice moved, but don’t send it yet."'),
            ('Text the band: Tell Mike that practice moved.', 'Tell Mike that practice moved.'),
        ):
            with self.subTest(ask=ask):
                self.assertEqual(self.say(ask)['text_draft']['body'], body)

    def test_T16_specific_subject_without_invented_amount_or_date(self):
        answer = self.say('Email my accountant asking if the quarterly estimate is due this month. Show me first.')['content']
        self.assertIn('Subject: Quarterly estimate due date', answer)
        self.assertIn('Hi,', answer)
        self.assertIn('Could you let me know if the quarterly estimate is due this month?', answer)
        self.assertIn('confirm the due date and amount', answer)
        self.assertNotRegex(answer, r'\$\d|April|January|October')
        self.assertEqual(answer.count('OK'), 1)
        self.assertTrue(answer.endswith('I’ll wait for your OK before sending.'))
        self.assertIn('still pending', self.say('yes')['content'])
        self.bridge.deliver.assert_not_called()

    def test_email_subject_tracks_supplied_topic(self):
        answer = self.say('Email Mike the rehearsal plan looks good.')['content']
        self.assertIn('Subject: The rehearsal plan looks good', answer)
        self.assertNotIn('Follow-up', answer)
        self.assertIn('Hi Mike,', answer)

    def test_T29_one_open_question_without_scenario(self):
        for person in ('Mike', 'Sam', 'Mary Jane'):
            self.assertEqual(self.say(f'Can you handle the thing with {person}?')['content'],
                             f'What do you need handled with {person}?')
        self.assertFalse(self.providers.calls)
        self.assertFalse(task_queue.tasks(self.root))
        self.bridge.deliver.assert_not_called()

    def test_T34_known_projects_without_fetched_status(self):
        answer = self.say('How are the projects going? Short version.')['content']
        for project in ('Web Bob', 'WebJam', 'AdoptIQ', 'StoryBoard', 'Turdanoid'):
            self.assertIn(project, answer)
        self.assertIn('current status isn’t fetched', answer)
        self.assertIn('one line each', answer)
        self.assertNotIn('Which project', answer)
        self.assertFalse(self.providers.calls)

    def test_partial_project_records_do_not_hide_other_projects(self):
        state = ledger.default_state()
        state['jobs'] = [dict(job_id='one', plain_now='Web Bob: review pending')]
        ledger.save_state(self.root, state)
        answer = self.say('How are the projects going? Short version.')['content']
        self.assertIn('Web Bob: review pending', answer)
        self.assertIn('not a live check', answer)
        for project in ('WebJam', 'AdoptIQ', 'StoryBoard', 'Turdanoid'):
            self.assertIn(project + ': current status isn’t fetched', answer)

    def test_T40_decline_guidance_no_excuses_and_waits_for_ok(self):
        rules = self.policy('Help me word a polite no to playing a free benefit show next month.')
        self.assertIn('decline without inventing excuses, schedule conflicts, policies or commitments', rules)
        self.assertIn('End with one line: I’ll wait for your OK before sending.', rules)

    def test_spreadsheet_template_precedes_single_exact_approval_footer(self):
        answer = self.say('Make me a simple spreadsheet to track gig payments: date, venue, amount, paid yes/no.')['content']
        self.assertIn('```csv\ndate, venue, amount, paid yes/no\n```', answer)
        proposal = self.chat.get(self.cid)['pending_job_id']
        self.assertEqual(answer.splitlines()[-1], f'Reply `yes, start job proposal {proposal}` to create the file.')
        self.assertNotIn('No job has started', answer)
        self.say('yes')
        self.assertFalse(task_queue.tasks(self.root))

    def test_full_text_token_still_required_and_body_tampering_rejected(self):
        answer = self.say('Draft a text to the band saying practice is moved to Thursday at 7.')
        conversation = self.chat.get(self.cid)
        row = conversation['_texting']['drafts'][answer['text_draft']['id']]
        for approval in ('yes', 'go ahead', 'yes ' + row['token'][:12], 'please yes ' + row['token'],
                         'yes ' + row['token'] + ' please', 'yes wbtxt-' + '0' * 32):
            with self.subTest(approval=approval):
                reply = self.chat.texting.confirm(copy.deepcopy(conversation), approval, 'fixture', 'later', Mock())
                self.assertIn('Nothing sent', reply)
        tampered = copy.deepcopy(conversation)
        tampered['_texting']['drafts'][row['id']]['body'] += ' Changed.'
        self.assertIn('Nothing sent', self.chat.texting.confirm(tampered, 'yes ' + row['token'], 'fixture', 'later', Mock()))
        self.bridge.deliver.assert_not_called()

    def test_compact_reminder_footer_does_not_change_consent(self):
        answer = self.say('remind me in 20 minutes to check the oven')['content']
        token = re.search(r'yes (wbrem-[a-f0-9]{32})', answer)[1]
        row = json.loads((self.chat.reminders.folder / 'drafts.json').read_text())[token]
        for approval in ('yes', 'yes ' + token[:12], 'yes ' + token + ' please', 'please yes ' + token):
            self.chat.reminders.handle(approval, self.cid, 'later', actor='fixture')
            self.assertFalse(self.chat.reminders.listing())
        self.chat.reminders.handle('yes ' + token, self.cid, row['request_id'], actor='fixture')
        self.assertFalse(self.chat.reminders.listing())
        self.chat.reminders.handle('yes ' + token, self.cid, 'later', actor='fixture')
        self.assertEqual(len(self.chat.reminders.listing()), 1)
        self.chat.reminders.handle('yes ' + token, self.cid, 'replay', actor='fixture')
        self.assertEqual(len(self.chat.reminders.listing()), 1)

    def test_ambiguous_recipient_never_gets_a_send_token(self):
        self.bb.chats.return_value.append(dict(guid='SMS;+;other', displayName='THE BAND',
                                              participants=[dict(address='other@example.test')]))
        answer = self.say('Draft a text to the band saying practice is moved to Thursday at 7.')
        self.assertIn('Several threads match', answer['content'])
        self.assertNotIn('text_draft', answer)
        self.assertNotIn('wbtxt-', answer['content'])
        self.bridge.prepare.assert_not_called()
        self.bridge.deliver.assert_not_called()


if __name__ == '__main__':
    unittest.main()
