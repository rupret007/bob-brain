"""Dictionary membership and digits do not authorize reminder persistence.

Exercise real parsing, consent checks, drafts, and confirmation with only the
scheduled-item/draft stores and notification adapter replaced by the shared
interval fixture. A refusal or fallthrough is not the required exact-token ASK.
"""
import re
import unittest

import chat_intent
import test_consent_interval_unicode as interval_fixture


# Verbatim unresolved-blocker requests from codex-solo-consent-8c4bf647ec7d.json.
CODEX_REPROS = (
    'remind me to stretch reminder storage is off limits in 10 minutes',
    'remind me every 10 minutes to stretch reminder storage is off limits',
    'remind me to stretch reminder storage is off limits in 10 mins',
    'remind me to stretch reminder storage is off limits in 2 hrs',
    'remind me every 10 minutes to stretch reminders are interdicted',
)

PROHIBITIONS = (
    'reminder storage is off limits',
    'reminders are interdicted',
    'reminders are taboo',
    'interdict reminder storage',
    'interdicting reminders',
    'reminders face interdiction',
    'reminders are banned',
    'reminders are verboten',
    'reminders are not allowed',
    'no saving',
    'hold off',
    'reminder storage is prohibited',
    'saving is forbidden',
    'saving is disallowed',
    'saving is barred',
    'creation is suspended',
    'permission is withheld',
    'withhold permission',
    'postpone saving',
    'defer saving',
    'save later',
    'refuse storage',
    'storage is denied',
    'reminders are blocked',
    'refrain from saving',
    'do not save',
    'dont save',
    "don't save",
    'owner not ready',
    'must await me',
    'off limits',
    'reminders are proscribed',
    'blacklist reminders',
    'reminders face a moratorium',
    'reminders are outlawed',
    # An unfamiliar property/state clause is unresolved control language even
    # when its individual words are in the ordinary-language dictionary.
    'reminders are untouchable',
    'storage is sacrosanct',
    'shelve reminder storage',
    'reminders shelved',
    'eschew reminder storage',
    'preclude reminder storage',
    'inhibit reminder storage',
    'quash reminders',
    'desist',
    'forbear',
    'table reminders',
    'reminders tabled',
    'shun reminders',
    'squelch reminders',
    'repress reminders',
    'resist reminders',
    'scrap reminders',
    'scrub reminders',
    'discard reminders',
    'abandon reminders',
    'withdraw reminders',
    'reminder storage untouchable',
    'persistence sacrosanct',
)

# Supplementary digit-admission repros from the same review, verbatim bodies.
DIGIT_CONTROLS = ('ownernotready1', 'mustawaitme2', 'n0t n0w', 'd0nt s4ve')
DIGIT_SHAPED_CONTROLS = (
    'NOT1', 'DONT1', 'WAIT2', 'TABOO1', 'BAN1', 'OFF1 LIMITS', 'HANDS1 OFF',
) + tuple(phrase.upper() for phrase in DIGIT_CONTROLS)

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


class ConsentIntervalProhibitionTests(unittest.TestCase):
    # Reuse the fixture without importing its TestCase into this module or
    # inheriting its tests, either of which would duplicate unittest discovery.
    setUp = interval_fixture.ConsentIntervalUnicodeTests.setUp
    say_fresh = interval_fixture.ConsentIntervalUnicodeTests.say_fresh

    def assert_exact_draft(self, text, *, body=None, delay=None, interval=None):
        reply = self.say_fresh(text)
        self.assertEqual(self.items.writes, [], reply)
        self.assertEqual(self.items.rows, [], reply)
        self.assertEqual(self.reminders.listing(), [], reply)
        self.assertIsInstance(reply, str, 'Handler fell through: ' + text)
        self.assertNotIn('Reminder saved', reply)
        token = re.search(r'Reply `yes (wbrem-[0-9a-f]{32})`', reply)
        self.assertIsNotNone(token, reply)
        self.assertEqual(len(self.drafts.writes), 1, reply)
        self.assertEqual(set(self.drafts.rows), {token[1]}, reply)
        draft = self.drafts.rows[token[1]]
        self.assertEqual((draft['state'], draft['text']), ('draft', text))
        if body is not None:
            self.assertEqual(draft['body'], body)
        if delay is not None:
            self.assertEqual((draft['due'], draft['interval']),
                             (self.now + delay, interval))
        return token[1]

    def assert_immediate(self, text, body, delay, interval):
        reply = self.say_fresh(text)
        self.assertIsInstance(reply, str)
        self.assertIn('Reminder saved', reply)
        self.assertEqual(len(self.items.writes), 1, reply)
        row, = self.items.rows
        self.assertEqual((row['body'], row['due_at'], row['interval_seconds'], row['state']),
                         (body, self.now + delay, interval, 'pending'))
        self.assertEqual(self.drafts.rows, {})
        self.assertEqual(self.drafts.writes, [])

    def assert_control_matrix(self, phrases):
        for phrase in phrases:
            for form, template in FORMS.items():
                for unit, quantity, delay in UNITS:
                    for placement, body_template in PLACEMENTS.items():
                        body = body_template.format(phrase=phrase)
                        text = template.format(quantity=quantity, unit=unit, body=body)
                        with self.subTest(phrase=phrase, form=form, unit=unit,
                                          placement=placement):
                            self.assert_exact_draft(text, body=body, delay=delay,
                                                    interval=delay if form == 'recurring' else None)

    def test_review_repros_verbatim(self):
        for text in CODEX_REPROS:
            with self.subTest(text=text):
                self.assert_exact_draft(text)

    def test_dictionary_prohibitions_both_forms_all_placements_and_units(self):
        self.assert_control_matrix(PROHIBITIONS)

    def test_digit_controls_both_forms_all_placements_and_units(self):
        self.assert_control_matrix(DIGIT_CONTROLS + DIGIT_SHAPED_CONTROLS)

    def test_supplementary_digit_repros_verbatim(self):
        for phrase in DIGIT_CONTROLS:
            for template in (
                'remind me every 10 minutes to stretch {phrase}',
                'remind me to stretch {phrase} in 10 minutes',
                'remind me to stretch {phrase} in 2 hrs',
            ):
                text = template.format(phrase=phrase)
                with self.subTest(text=text):
                    self.assert_exact_draft(text)

    def test_unconditional_controls_preserve_direct_save_and_abbreviation_drafts(self):
        for body in ('stretch', 'call mom', 'drink 2 cups water',
                     'inspect ticket 12345'):
            for form, template in FORMS.items():
                for unit, quantity, delay in UNITS:
                    text = template.format(quantity=quantity, unit=unit, body=body)
                    interval = delay if form == 'recurring' else None
                    with self.subTest(body=body, form=form, unit=unit):
                        # Recurring abbreviations have always required a draft;
                        # a consent fix must preserve that existing boundary.
                        if form == 'recurring' and unit != 'minutes':
                            self.assert_exact_draft(text, body=body, delay=delay,
                                                    interval=interval)
                        else:
                            self.assert_immediate(text, body, delay, interval)

    def test_mixed_ticket_operands_require_exact_confirmation_without_an_exemption(self):
        # These formerly asserted immediate saves under the ticket-ID exemption.
        # The owner-approved mixed-token rule requires ASK for these operands too.
        for body in ('inspect ticket AB123', 'inspect ticket b87cbc78207a5c2c'):
            for form, template in FORMS.items():
                for unit, quantity, delay in UNITS:
                    text = template.format(quantity=quantity, unit=unit, body=body)
                    interval = delay if form == 'recurring' else None
                    with self.subTest(body=body, form=form, unit=unit):
                        self.assert_exact_draft(text, body=body, delay=delay,
                                                interval=interval)

    def test_exact_confirmation_saves_original_body_once(self):
        for phrase in PROHIBITIONS[:3] + DIGIT_CONTROLS:
            body = 'stretch ' + phrase
            for form, template in FORMS.items():
                for unit, quantity, delay in UNITS:
                    text = template.format(quantity=quantity, unit=unit, body=body)
                    interval = delay if form == 'recurring' else None
                    with self.subTest(phrase=phrase, form=form, unit=unit):
                        token = self.assert_exact_draft(text, body=body, delay=delay,
                                                       interval=interval)
                        reply = self.reminders.handle(
                            'yes ' + token, 'unheld', 'confirm',
                            intent_state=chat_intent.new_state())
                        self.assertIn('Reminder saved', reply)
                        self.assertEqual(len(self.items.writes), 1)
                        row, = self.items.rows
                        self.assertEqual((row['body'], row['due_at'], row['interval_seconds']),
                                         (body, self.now + delay, interval))
                        self.assertEqual(self.drafts.rows[token]['state'], 'done')
                        replay = self.reminders.handle(
                            'yes ' + token, 'unheld', 'replay',
                            intent_state=chat_intent.new_state())
                        self.assertEqual(replay, reply)
                        self.assertEqual(len(self.items.writes), 1)
                        self.notifications.assert_not_called()

    def test_invalid_confirmations_never_save_then_later_exact_token_does(self):
        for phrase in ('reminder storage is off limits', 'ownernotready1'):
            for form, template in FORMS.items():
                for unit, quantity, _ in UNITS:
                    text = template.format(quantity=quantity, unit=unit,
                                           body='stretch ' + phrase)
                    with self.subTest(phrase=phrase, form=form, unit=unit):
                        token = self.assert_exact_draft(text)
                        wrong = 'wbrem-' + ('f' if token[-1] != 'f' else 'e') * 32
                        invalid = (
                            ('yes', 'unheld', 'bare', 'owner'),
                            ('yes ' + wrong, 'unheld', 'wrong', 'owner'),
                            ('yes ' + token + ' please', 'unheld', 'extra', 'owner'),
                            ('yes ' + token + ' hold off', 'unheld', 'withheld', 'owner'),
                            ('yes ' + token, 'unheld', 'request', 'owner'),
                            ('yes ' + token, 'other-conversation', 'other', 'owner'),
                            ('yes ' + token, 'unheld', 'other-actor', 'guest'),
                        )
                        for confirmation, cid, request_id, actor in invalid:
                            with self.subTest(confirmation=confirmation, cid=cid,
                                              request_id=request_id, actor=actor):
                                self.reminders.handle(
                                    confirmation, cid, request_id, actor=actor,
                                    intent_state=chat_intent.new_state())
                                self.assertEqual(self.items.writes, [])
                                self.assertEqual(self.items.rows, [])
                                self.assertEqual(self.drafts.rows[token]['state'], 'draft')
                        reply = self.reminders.handle(
                            'yes ' + token, 'unheld', 'valid-later-confirmation',
                            intent_state=chat_intent.new_state())
                        self.assertIn('Reminder saved', reply)
                        self.assertEqual(len(self.items.writes), 1)
                        self.notifications.assert_not_called()


if __name__ == '__main__':
    unittest.main()
