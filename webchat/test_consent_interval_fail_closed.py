"""Rev6 interval blockers must create resolved exact-token drafts, never save.

Run the actual Reminders handler with memory persistence adapters and rejected
notifications. Unknown cancellation vocabulary and isolated mixed tokens test
the structural gates independently of the existing prohibition vocabulary.
"""
from datetime import datetime
import re
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import approval_language
import chat_intent
import reminders
import test_consent_interval_unicode as interval_fixture


# All twelve requests in unresolved_blockers[*].reproductions from
# codex-solo-consent-7dedfc1966ae.json, with their resolved schedules/content.
REV6_REPROS = (
    ('remind me every 10 minutes to stretch call off reminders',
     'stretch call off reminders', 600, 600),
    ('remind me to stretch call off reminders in 10 minutes',
     'stretch call off reminders', 600, None),
    ('remind me to stretch call off reminders in 10 mins',
     'stretch call off reminders', 600, None),
    ('remind me to stretch call off reminders in 2 hrs',
     'stretch call off reminders', 7200, None),
    ('remind me every 10 minutes to forgo reminders stretch gently',
     'forgo reminders stretch gently', 600, 600),
    ('remind me to stretch discontinue reminders gently in 10 mins',
     'stretch discontinue reminders gently', 600, None),
    ('remind me to stretch gently decline reminders in 2 hrs',
     'stretch gently decline reminders', 7200, None),
    ('remind me to stretch reminders unwelcome in 10 minutes',
     'stretch reminders unwelcome', 600, None),
    ('remind me every 10 minutes to stretch CEA5E123 reminders',
     'stretch CEA5E123 reminders', 600, 600),
    ('remind me to stretch CEA5E123 reminders in 10 minutes',
     'stretch CEA5E123 reminders', 600, None),
    ('remind me to stretch CEA5E123 reminders in 10 mins',
     'stretch CEA5E123 reminders', 600, None),
    ('remind me to stretch CEA5E123 reminders in 2 hrs',
     'stretch CEA5E123 reminders', 7200, None),
)

REV6_NEARBY_PHRASES = (
    'call off reminders', 'forgo reminders', 'discontinue reminders',
    'decline reminders', 'reminders unwelcome', 'reminders untouchable',
    'reminders sacrosanct', 'CEA5E123 reminders', 'DEC1DE12 reminders',
    'NAH1 reminders',
)
OWNER_GENERALIZATIONS = (
    'abandon reminders', 'scrap reminders', 'nix reminders',
    'reminders unneeded', 'B4N reminders', '5T0P reminders',
)
# These dictionary verbs were absent from all prohibition/control patterns at
# rev6. Keep that property explicit so expanding a word list cannot make this
# structural regression pass accidentally.
HELD_OUT_VERBS = ('abolish', 'annul', 'erase', 'retract', 'kill', 'repudiate')
BARE_UNRESOLVED = (
    'call off', 'forgo', 'discontinue', 'decline', 'unwelcome',
    'untouchable', 'sacrosanct',
) + HELD_OUT_VERBS
MIXED_TOKENS = (
    'CEA5E123', 'DEC1DE12', 'NAH1', 'B4N', '5T0P', 'CA11',
    'AB123', 'b87cbc78207a5c2c', '123ABC', 'A1B2C3D4',
)
SELF_REFERENCES = (
    'reminder', 'reminders', 'remind', 'saving', 'save', 'storage', 'store',
    'persist', 'schedule', 'alert', 'notification', 'this', 'it',
    'approval', 'permission',
)
FORMS = {
    'recurring': 'remind me every {quantity} {unit} to {body}',
    'one_shot': 'remind me to {body} in {quantity} {unit}',
}
UNITS = (('minutes', 10, 600), ('mins', 10, 600), ('hrs', 2, 7200))
PLACEMENTS = {
    'body_leading': '{phrase} stretch gently',
    'body_middle': 'stretch {phrase} gently',
    'body_trailing': 'stretch gently {phrase}',
}


class ConsentIntervalFailClosedTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory(prefix='consent-fail-closed-')
        self.addCleanup(temporary.cleanup)
        self.now = datetime(2026, 10, 12, 13, 0,
                            tzinfo=reminders.ZONE).timestamp()
        self.assertEqual(self.now, 1791828000)
        self.reminders = reminders.Reminders(temporary.name, clock=lambda: self.now)
        self.items = interval_fixture.MemoryStore([])
        self.drafts = interval_fixture.MemoryStore({})
        for store, lock, save in (
            (self.items, 'locked', 'save'),
            (self.drafts, 'draft_lock', 'save_drafts'),
        ):
            for method, replacement in ((lock, store.locked), (save, store.save)):
                guard = patch.object(self.reminders, method, replacement)
                guard.start()
                self.addCleanup(guard.stop)
        notification = patch('reminders.notify_macos', side_effect=AssertionError(
            'Unexpected notification'))
        self.notifications = notification.start()
        self.addCleanup(notification.stop)

    say_fresh = interval_fixture.ConsentIntervalUnicodeTests.say_fresh

    def assert_exact_draft(self, text, body, delay, interval):
        reply = self.say_fresh(text)
        self.assertEqual(self.items.writes, [], reply)
        self.assertEqual(self.items.rows, [], reply)
        self.assertEqual(self.reminders.listing(), [], reply)
        self.assertIsInstance(reply, str, 'Handler fell through: ' + text)
        token = re.search(r'Reply `yes (wbrem-[0-9a-f]{32})`', reply)
        self.assertIsNotNone(token, reply)
        self.assertNotIn('Reminder saved', reply)
        self.assertEqual(len(self.drafts.writes), 1, reply)
        self.assertEqual(set(self.drafts.rows), {token[1]}, reply)
        draft = self.drafts.rows[token[1]]
        self.assertEqual((draft['state'], draft['text'], draft['body']),
                         ('draft', text, body))
        self.assertEqual((draft['due'], draft['interval']),
                         (self.now + delay, interval))
        return token[1]

    def assert_immediate(self, text, body, delay, interval):
        reply = self.say_fresh(text)
        self.assertIsInstance(reply, str)
        self.assertIn('Reminder saved', reply)
        self.assertEqual(len(self.items.writes), 1, reply)
        row, = self.items.rows
        self.assertEqual((row['body'], row['due_at'], row['interval_seconds'],
                          row['state']), (body, self.now + delay, interval, 'pending'))
        self.assertEqual(self.drafts.rows, {})
        self.assertEqual(self.drafts.writes, [])

    def assert_ask_matrix(self, phrases):
        for phrase in phrases:
            for form, template in FORMS.items():
                for unit, quantity, delay in UNITS:
                    for placement, body_template in PLACEMENTS.items():
                        body = body_template.format(phrase=phrase)
                        text = template.format(quantity=quantity, unit=unit, body=body)
                        with self.subTest(phrase=phrase, form=form, unit=unit,
                                          placement=placement):
                            self.assert_exact_draft(text, body, delay,
                                                    delay if form == 'recurring' else None)

    def assert_complete_bodies_ask(self, bodies):
        for body in bodies:
            for form, template in FORMS.items():
                for unit, quantity, delay in UNITS:
                    text = template.format(quantity=quantity, unit=unit, body=body)
                    with self.subTest(body=body, form=form, unit=unit):
                        self.assert_exact_draft(text, body, delay,
                                                delay if form == 'recurring' else None)

    def test_every_rev6_reproduction_verbatim(self):
        for text, body, delay, interval in REV6_REPROS:
            with self.subTest(text=text):
                self.assert_exact_draft(text, body, delay, interval)

    def test_rev6_nearby_phrases_all_forms_placements_and_aliases(self):
        self.assert_ask_matrix(REV6_NEARBY_PHRASES)

    def test_owner_generalization_examples_all_forms_placements_and_aliases(self):
        self.assert_ask_matrix(OWNER_GENERALIZATIONS)

    def test_held_out_dictionary_verbs_require_no_new_prohibition_vocabulary(self):
        for verb in HELD_OUT_VERBS:
            with self.subTest(verb=verb):
                self.assertTrue(reminders._dictionary_token(verb))
                self.assertIsNone(approval_language._INHIBITION.search(verb))
                self.assertIsNone(reminders._CONTROL_WORDS.fullmatch(verb))
                self.assertIsNone(reminders._CONTROL_ROOTS.search(verb))
        self.assert_ask_matrix(tuple(verb + ' reminders' for verb in HELD_OUT_VERBS))

    def test_mixed_tokens_are_unresolved_without_reminder_or_save_words(self):
        self.assert_ask_matrix(MIXED_TOKENS)

    def test_bare_predicates_are_unresolved_without_reminder_or_save_words(self):
        self.assert_ask_matrix(BARE_UNRESOLVED)
        self.assert_complete_bodies_ask(BARE_UNRESOLVED)

    def test_self_referential_objects_do_not_need_a_known_cancellation_verb(self):
        self.assert_ask_matrix(tuple('erase ' + noun for noun in SELF_REFERENCES))

    def test_unrecognized_dictionary_tasks_require_exact_confirmation(self):
        # These may be ordinary tasks, but dictionary membership alone cannot
        # resolve them as an admitted immediate-save task grammar.
        self.assert_complete_bodies_ask(('polish silver', 'mend socks', 'fold linen'))

    def test_id_operand_requires_the_entire_recognized_task(self):
        self.assert_complete_bodies_ask((
            'inspect ticket CEA5E123',
            'inspect ticket DEC1DE12',
            'inspect ticket NAH1',
            'inspect ticket ABC123',
            'inspect ticket ab123',
            'inspect ticket AB123a',
            'inspect tickets AB123',
            'inspect ticket AB123 extra',
            'extra inspect ticket AB123',
            'inspect ticket AB123 456',
            'inspect ticket b87cbc78207a5c2c extra',
            'extra inspect ticket b87cbc78207a5c2c',
            'inspect ticket 12345 extra',
        ))

    def test_possessive_task_slot_never_discards_control_modifiers(self):
        for phrase in ('forgo', 'call off', 'CEA5E123', 'reminders unwelcome',
                       'permission'):
            with self.subTest(phrase=phrase):
                self.assert_complete_bodies_ask((
                    phrase + ' take my pills',
                    'take ' + phrase + ' my pills',
                    'take my ' + phrase + ' pills',
                    'take my pills ' + phrase,
                ))

    def test_owner_unconditional_controls_save_immediately(self):
        for text, body, delay, interval in (
            ('remind me every 10 minutes to stretch', 'stretch', 600, 600),
            ('remind me to call mom in 2 hrs', 'call mom', 7200, None),
            ('remind me to take my pills in 30 mins', 'take my pills', 1800, None),
            ('REMIND ME TO TAKE MY PILLS IN 30 MINS', 'TAKE MY PILLS', 1800, None),
            ('remind me every 2 hours to drink water', 'drink water', 7200, 7200),
        ):
            with self.subTest(text=text):
                self.assert_immediate(text, body, delay, interval)

    def test_ordinary_numbers_keep_existing_save_and_recurring_alias_behavior(self):
        for body in ('stretch', 'call mom', 'drink 2 cups water',
                     'take 2 pills', 'inspect ticket 12345'):
            for form, template in FORMS.items():
                for unit, quantity, delay in UNITS:
                    text = template.format(quantity=quantity, unit=unit, body=body)
                    interval = delay if form == 'recurring' else None
                    with self.subTest(body=body, form=form, unit=unit):
                        if form == 'recurring' and unit != 'minutes':
                            self.assert_exact_draft(text, body, delay, interval)
                        else:
                            self.assert_immediate(text, body, delay, interval)

    def test_later_exact_confirmation_saves_unchanged_body_and_schedule_once(self):
        for body in ('stretch call off reminders', 'stretch CEA5E123 reminders',
                     'stretch CEA5E123'):
            for form, template in FORMS.items():
                for unit, quantity, delay in UNITS:
                    text = template.format(quantity=quantity, unit=unit, body=body)
                    interval = delay if form == 'recurring' else None
                    with self.subTest(body=body, form=form, unit=unit):
                        token = self.assert_exact_draft(text, body, delay, interval)
                        reply = self.reminders.handle(
                            'yes ' + token, 'unheld', 'later-confirmation',
                            intent_state=chat_intent.new_state())
                        self.assertIn('Reminder saved', reply)
                        self.assertEqual(len(self.items.writes), 1)
                        row, = self.items.rows
                        self.assertEqual((row['body'], row['due_at'],
                                          row['interval_seconds'], row['state']),
                                         (body, self.now + delay, interval, 'pending'))
                        self.assertEqual(self.drafts.rows[token]['state'], 'done')
                        replay = self.reminders.handle(
                            'yes ' + token, 'unheld', 'replay',
                            intent_state=chat_intent.new_state())
                        self.assertEqual(replay, reply)
                        self.assertEqual(len(self.items.writes), 1)
                        self.notifications.assert_not_called()


if __name__ == '__main__':
    unittest.main()
