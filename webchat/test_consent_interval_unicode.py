"""Direct interval consent regressions through the actual Reminders handler."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from pathlib import Path
import re
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import chat_intent
from reminders import Reminders, ZONE


# Verbatim requests from codex-solo-consent-b5fe13a8d3d3.json. Keep the
# escaped characters as their actual Unicode values when passed to handle().
CODEX_REPROS = (
    'remind me every 10 minutes to stretch supposing the owner says yes',
    'remind me every 10 minutes to stretch should the owner concur',
    'remind me every 10 minutes to stretch: scheduling follows signoff',
    'remind me every 10 minutes to stretch: proofread beforehand',
    'remind me to stretch following signoff in 10 minutes',
    'remind me every 10 minutes to stretch dr\u200baft o\u200bnly',
    'remind me to stretch dr\u00adaft o\u00adnly in 10 minutes',
    'remind me every 10 minutes to stretch do\u200bn\u2019t act yet',
    'remind me every 10 minutes to stretch d.r.a.f.t o.n.l.y',
)

PHRASES = {
    'conditional': (
        'supposing the owner says yes',
        'suppose the owner agrees',
        'should the owner concur',
        'should the owner respond',
        'provided I agree',
        'if I decide to proceed',
    ),
    'deferred': (
        'scheduling follows signoff',
        'following signoff',
        'following sign-off',
        'following signoffs',
        'following sign-offs',
        'follow approval',
        'wait for my go-ahead',
        'after I give the green light',
        'execution disabled',
        'do not execute yet',
        'don\u2019t act yet',
    ),
    'draft_only': (
        'draft only',
        'just a draft',
        'keep it provisional',
        'this is hypothetical',
    ),
    'preview': (
        'preview first',
        'let me see it first',
        'show me first',
    ),
    'review': (
        'proofread beforehand',
        'review beforehand',
        'let me review it',
        'for my review',
    ),
}


def split_words(text, separator):
    return re.sub(r'[A-Za-z]{2,}', lambda word: separator.join(word[0]), text)


def fullwidth(text):
    return ''.join(chr(ord(char) + 0xFEE0) if '!' <= char <= '~'
                   else '\u3000' if char == ' ' else char for char in text)


TRANSFORMS = {
    'plain': lambda text: text,
    'zero_width_space': lambda text: split_words(text, '\u200b'),
    'soft_hyphen': lambda text: split_words(text, '\u00ad'),
    'zero_width_joiner': lambda text: split_words(text, '\u200d'),
    'byte_order_mark': lambda text: split_words(text, '\ufeff'),
    'word_joiner': lambda text: split_words(text, '\u2060'),
    'nonbreaking_space': lambda text: text.replace(' ', '\u00a0'),
    'fullwidth': fullwidth,
    'dotted_letters': lambda text: split_words(text, '.'),
    # A wider gap preserves the boundary between independently spelled words.
    'spaced_letters': lambda text: split_words(text.replace(' ', '  '), ' '),
}

FORMS = {
    'recurring': ('remind me every 10 minutes to {body}', 600),
    'one_shot': ('remind me to {body} in 10 minutes', None),
}
PLACEMENTS = (
    'body_prefix', 'body_middle', 'body_suffix', 'colon_suffix',
    'request_prefix', 'after_interval',
)


def request_with_constraint(form, phrase, placement):
    template, _ = FORMS[form]
    bodies = {
        'body_prefix': phrase + ' stretch gently',
        'body_middle': 'stretch ' + phrase + ' gently',
        'body_suffix': 'stretch gently ' + phrase,
        'colon_suffix': 'stretch gently: ' + phrase,
    }
    if placement in bodies:
        return template.format(body=bodies[placement])
    if placement == 'request_prefix':
        return phrase + ': ' + template.format(body='stretch gently')
    if placement == 'after_interval':
        # This is trailing after the one-shot time, and between the recurring
        # interval and its body; neither restriction may disappear in parsing.
        return template.format(body='stretch gently').replace(
            '10 minutes', '10 minutes ' + phrase)
    raise AssertionError('Unknown placement: ' + placement)


class MemoryStore:
    """Unsaved mutations never become persistence, including draft mutations."""

    def __init__(self, rows):
        self.rows = deepcopy(rows)
        self.writes = []

    @contextmanager
    def locked(self):
        yield deepcopy(self.rows)

    def save(self, rows):
        self.rows = deepcopy(rows)
        self.writes.append(deepcopy(rows))

    def reset(self):
        self.rows.clear()
        self.writes.clear()


class ConsentIntervalUnicodeTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory(prefix='.consent-interval-',
                                       dir=Path(__file__).resolve().parent)
        self.addCleanup(temporary.cleanup)
        self.now = datetime(2026, 10, 12, 13, 0, tzinfo=ZONE).timestamp()
        self.assertEqual(self.now, 1791828000)
        self.reminders = Reminders(temporary.name, clock=lambda: self.now)
        self.items = MemoryStore([])
        self.drafts = MemoryStore({})
        for store, lock, save in (
            (self.items, 'locked', 'save'),
            (self.drafts, 'draft_lock', 'save_drafts'),
        ):
            for method, replacement in ((lock, store.locked), (save, store.save)):
                guard = patch.object(self.reminders, method, replacement)
                guard.start()
                self.addCleanup(guard.stop)
        notification = patch('reminders.notify_macos',
                             side_effect=AssertionError('Unexpected notification'))
        self.notifications = notification.start()
        self.addCleanup(notification.stop)

    def say_fresh(self, text):
        # Every case exercises an unheld conversation without prior rows or
        # drafts. Reusing a request ID cannot mask an unauthorized save.
        self.items.reset()
        self.drafts.reset()
        state = chat_intent.new_state()
        self.assertEqual(chat_intent.blocked_scopes(
            state, chat_intent.projects(text), action_text=text), [])
        reply = self.reminders.handle(text, 'unheld', 'request', intent_state=state)
        self.notifications.assert_not_called()
        return reply

    def assert_asks_without_saving(self, text):
        reply = self.say_fresh(text)
        self.assertEqual(self.items.writes, [], reply)
        self.assertEqual(self.items.rows, [], reply)
        self.assertEqual(self.reminders.listing(), [], reply)
        self.assertIsInstance(reply, str, 'Handler fell through: ' + text)
        self.assertNotIn('Reminder saved', reply)
        # A silent fallthrough, a generic parsing error, or an unrelated hold
        # is not an ASK. Require a new request or separate exact confirmation.
        self.assertRegex(reply, r'Send a new reminder request|'
                                r'Reply `yes wbrem-[0-9a-f]{32}`')

    def assert_saves_immediately(self, text, body, interval):
        reply = self.say_fresh(text)
        self.assertIsInstance(reply, str)
        self.assertIn('Reminder saved', reply)
        self.assertIn(body, reply)
        self.assertEqual(len(self.items.writes), 1)
        row, = self.items.rows
        self.assertEqual((row['body'], row['due_at'], row['interval_seconds'], row['state']),
                         (body, 1791828600, interval, 'pending'))
        self.assertEqual(self.drafts.rows, {})

    def test_codex_repros_verbatim(self):
        for text in CODEX_REPROS:
            with self.subTest(text=text):
                self.assert_asks_without_saving(text)

    def test_execution_disabled_in_both_direct_interval_forms(self):
        for form, (template, _) in FORMS.items():
            with self.subTest(form=form):
                self.assert_asks_without_saving(template.format(body='stretch execution disabled'))

    def test_constraint_form_placement_unicode_matrix(self):
        for category, phrases in PHRASES.items():
            for phrase in phrases:
                for form in FORMS:
                    for placement in PLACEMENTS:
                        for transform, apply in TRANSFORMS.items():
                            text = request_with_constraint(form, apply(phrase), placement)
                            with self.subTest(category=category, phrase=phrase, form=form,
                                              placement=placement, transform=transform):
                                self.assert_asks_without_saving(text)

    def test_single_spelled_constraint_words(self):
        for form, (template, _) in FORMS.items():
            for phrase in ('d r a f t', 'd.r.a.f.t', 'd i s a b l e d',
                           'd r a f t o n l y', 'd.r.a.f.t.o.n.l.y',
                           's h o u l d t h e o w n e r c o n c u r',
                           'i f I a p p r o v e', 'd o n \u2019 t a c t y e t',
                           's t r e t c h g e n t l y'):
                with self.subTest(form=form, phrase=phrase):
                    self.assert_asks_without_saving(template.format(body='stretch ' + phrase))

    def test_format_characters_preserve_conditional_word_boundaries(self):
        # Removing a format character must not hide already-visible evidence
        # by merging "if" or "should" with the next word.
        for form, (template, _) in FORMS.items():
            for separator in ('\u200b', '\u00ad', '\u200d', '\ufeff', '\u2060'):
                for first, rest in (('if', 'the gate opens'),
                                    ('should', 'the owner respond')):
                    phrase = first + separator + rest
                    with self.subTest(form=form, separator=separator, phrase=phrase):
                        self.assert_asks_without_saving(template.format(body='stretch ' + phrase))

    def test_horizontal_whitespace_spelled_constraint_words(self):
        for form, (template, _) in FORMS.items():
            for separator in ('\t', '  ', '\t ', '\u00a0', '\u202f'):
                phrase = separator.join('draft')
                with self.subTest(form=form, separator=separator):
                    self.assert_asks_without_saving(template.format(body='stretch ' + phrase))

    def test_joining_letters_preserves_existing_personal_intent_evidence(self):
        # Joining these isolated letters must not erase the existing "I"
        # personal-intent signal and turn a prior ASK into authorization.
        for form, (template, _) in FORMS.items():
            for phrase in ('I-a', 'i.s'):
                with self.subTest(form=form, phrase=phrase):
                    self.assert_asks_without_saving(template.format(body='stretch ' + phrase))

    def test_unresolved_colon_clause_needs_no_known_consent_words(self):
        for form, (template, _) in FORMS.items():
            for colon in (':', '\uff1a'):
                with self.subTest(form=form, colon=colon):
                    self.assert_asks_without_saving(template.format(
                        body='stretch' + colon + ' the next move belongs to someone else'))

    def test_plain_direct_interval_forms_still_save_immediately(self):
        for form, (template, interval) in FORMS.items():
            with self.subTest(form=form):
                self.assert_saves_immediately(template.format(body='stretch'), 'stretch', interval)

    def test_detection_normalization_preserves_saved_body(self):
        # Only the detector may normalize these strings. Their exact original
        # content must still reach the actual create/save path and its receipt.
        # Spaced runs have unresolved word boundaries and are ASK cases above.
        for form, (template, interval) in FORMS.items():
            for transform in ('plain', 'zero_width_space', 'soft_hyphen',
                              'zero_width_joiner', 'byte_order_mark', 'word_joiner',
                              'nonbreaking_space', 'fullwidth', 'dotted_letters'):
                body = TRANSFORMS[transform]('stretch gently')
                with self.subTest(form=form, transform=transform, body=body):
                    if transform == 'plain':
                        self.assert_saves_immediately(template.format(body=body), body, interval)
                        continue
                    # Confirm when unsure (Jeff 2026-10-15): unusual characters
                    # never save in the request turn. The exact original body
                    # must still be what a later exact confirmation saves.
                    reply = self.say_fresh(template.format(body=body))
                    self.assertEqual(self.items.writes, [], reply)
                    token = re.search(r'yes (wbrem-[0-9a-f]{32})', reply)
                    self.assertIsNotNone(token, reply)
                    confirm = self.reminders.handle('yes ' + token[1], 'unheld', 'confirm',
                                                    intent_state=chat_intent.new_state())
                    self.assertIn('Reminder saved', confirm)
                    row, = self.items.rows
                    self.assertEqual((row['body'], row['due_at'], row['interval_seconds']),
                                     (body, 1791828600, interval))


if __name__ == '__main__':
    unittest.main()
