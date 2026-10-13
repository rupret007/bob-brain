"""Round-six regressions with private stores and inert transports.

Guidance tests inspect the assembled provider prompt, not sampled creative quality.
"""
import json
import re
import unittest

import test_h2h_round4 as fixtures
import ledger
from task_dispatch import task_queue


class RoundSixTests(unittest.TestCase):
    setUp = fixtures.RoundFourTests.setUp
    say = fixtures.RoundFourTests.say
    policy = fixtures.RoundFourTests.policy

    def test_empty_project_summary_offers_check_without_inventing_roster(self):
        for ask in ('How are the projects going?', 'How are the projects going? Short version.'):
            with self.subTest(ask=ask):
                answer = self.say(ask)['content']
                self.assertEqual(answer, 'The current status isn’t fetched. I can check active projects '
                                 'and give you one line each: status, blocker, next step.')
        self.assertFalse(self.providers.calls)
        self.assertFalse(task_queue.tasks(self.root))

    def test_partial_records_show_only_grounded_projects(self):
        state = ledger.default_state()
        state['jobs'] = [dict(job_id='one', plain_now='Web Bob: review pending')]
        ledger.save_state(self.root, state)
        answer = self.say('How are the projects going?')['content']
        self.assertEqual(answer.splitlines(), ['Here’s the latest I have saved (not a live check):',
                                              '• Web Bob: review pending'])

    def test_queue_projects_outside_old_roster_are_preserved(self):
        folder = self.root / 'conductor/state'
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'queue.jsonl').write_text(json.dumps(dict(id='one', status='succeeded',
                prompt='Review Lantern', projects=['Lantern'], updated_at=1)) + '\n')
        answer = self.say('How are the projects going? Short version.')['content']
        self.assertEqual(answer.splitlines(), ['Here’s the latest I have saved (not a live check):',
                '• Lantern: work completed; I haven’t confirmed deployment'])

    def test_saved_notes_preserve_actual_projects_without_padding(self):
        folder = self.root / 'conductor/handback'
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'BOB-STATE.md').write_text('## Projects\n- Lantern: review pending\n'
                                           '- Orchard: waiting for tests\n## Decisions\n- Keep drafts private\n')
        answer = self.say('How are the projects going?')['content']
        self.assertEqual(answer.splitlines(), ['Saved notes (not a live check):',
                '• Lantern: review pending', '• Orchard: waiting for tests'])
        self.assertFalse(self.providers.calls)

    def test_other_project_summary_wordings_receive_grounding_guidance(self):
        for ask in ('Give me a quick project rundown.', 'How is everything progressing?'):
            with self.subTest(ask=ask):
                rules = self.policy(ask)
                for part in ('project names grounded in the conversation or supplied records',
                             'never fill in a default roster', 'offer to check active projects',
                             'status, blocker, next step'):
                    self.assertIn(part, rules)

    def test_appointment_guidance_asks_preferences_without_forced_draft(self):
        for ask in ('Move my dentist appointment to next week sometime.',
                    'Reschedule my haircut for later this month.',
                    'Move my eye exam to Tuesday afternoon.'):
            with self.subTest(ask=ask):
                rules = self.policy(ask)
                for part in ('ask preferred days/times if missing', "check the calendar and the other party's availability",
                             'show the proposed change for OK before rescheduling',
                             'Wait for OK before sending or rescheduling',
                             'do not add a full message draft unless requested',
                             'An optional draft offer is at most one short line',
                             'Do not imply availability has been checked',
                             'do not append a repetitive evidence disclaimer'):
                    self.assertIn(part, rules)
                self.assertNotIn('AND offer a short ready draft', rules)
                self.assertNotIn('availability is unverified', rules)
        self.client.create.assert_not_called()
        self.bridge.deliver.assert_not_called()

    def test_relative_reminder_prose_and_full_token_for_different_tasks(self):
        for delay, body in (('20 minutes', 'check the oven'), ('5 minutes', 'stretch'),
                            ('1 hour', 'check the laundry')):
            with self.subTest(delay=delay):
                answer = self.say(f'Remind me in {delay} to {body}')['content']
                preview, footer = answer.splitlines()
                self.assertEqual(preview, f"Draft reminder: {body} in {delay}. OK to set it? "
                                 "It isn't running yet—use a phone or oven timer if you need it counting now.")
                self.assertRegex(footer, r'^Reply `yes wbrem-[a-f0-9]{32}` to set\.$')
                self.assertFalse(self.chat.reminders.listing())

    def test_natural_ok_question_does_not_relax_exact_approval(self):
        answer = self.say('Remind me in 5 minutes to stretch')['content']
        token = re.search(r'yes (wbrem-[a-f0-9]{32})', answer)[1]
        row = json.loads((self.chat.reminders.folder / 'drafts.json').read_text())[token]
        for approval in ('OK', 'yes', 'go ahead', 'yes ' + token[:12],
                         'please yes ' + token, 'yes ' + token + ' please'):
            self.chat.reminders.handle(approval, self.cid, 'later', actor='fixture')
            self.assertFalse(self.chat.reminders.listing())
        for cid, request in (('other-conversation', 'later'), (self.cid, row['request_id'])):
            self.chat.reminders.handle('yes ' + token, cid, request, actor='fixture')
            self.assertFalse(self.chat.reminders.listing())
        self.chat.reminders.handle('yes ' + token, self.cid, 'later', actor='fixture')
        self.assertEqual(len(self.chat.reminders.listing()), 1)
        self.chat.reminders.handle('yes ' + token, self.cid, 'replay', actor='fixture')
        self.assertEqual(len(self.chat.reminders.listing()), 1)

    def test_naming_guidance_blends_genre_and_humor_without_reference_answers(self):
        for ask in ('Give me 5 name ideas for our next EP, punk vibe, dad humor.',
                    'Suggest three jazz album titles with cat puns.',
                    'Name our sci-fi comedy podcast. Give me six options.'):
            with self.subTest(ask=ask):
                rules = self.policy(ask)
                for part in ('skip the preamble', 'requested number of names',
                             'recognizable references from the requested genre', 'requested humor or theme',
                             'puns and title parodies', 'concise and varied',
                             'omit explanations and closing offers unless requested',
                             'Do not invent facts about the real person, band or product'):
                    self.assertIn(part, rules)
                self.assertNotIn('Never Mind the Bedtime', rules)
                self.assertNotIn('Anarchy in the PTA', rules)

    def test_cleanup_guidance_inventory_then_review_before_changes(self):
        for ask in ('Clean up my Downloads folder.', 'Organize my Desktop.',
                    'Help tidy the shared recordings directory.'):
            with self.subTest(ask=ask):
                rules = self.policy(ask)
                for part in ('conditional plan: first inventory the files',
                             'propose categories such as documents, media, installers and archives',
                             'possible duplicates listed separately',
                             'show proposed moves and any deletions for OK before changing anything',
                             'Do not assume files are disposable from age or extension alone',
                             'claim an inventory was performed without evidence',
                             'Lead with this concrete plan instead of a script-or-plan questionnaire'):
                    self.assertIn(part, rules)
        self.assertFalse(task_queue.tasks(self.root))


if __name__ == '__main__':
    unittest.main()
