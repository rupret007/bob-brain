"""Confirm-when-unsure (Jeff 2026-10-15): direct interval reminders save
immediately only for plain ASCII word bodies with no control words."""
import unittest

import test_consent_interval_unicode as _base_module

_Base = _base_module.ConsentIntervalUnicodeTests

# codex-solo-consent-74773f17bd82.json repros, verbatim, plus new families.
CODEX_REPROS_74773F1 = (
    'remind me every 10 minutes to stretch / scheduling prohibited',
    'remind me to stretch / scheduling forbidden in 10 minutes',
    'remind me to stretch scheduling prohibited in 10 mins',
    'remind me every 10 minutes to stretch dr\u034faft o\u034fnly',
    'remind me to stretch dr\ufe0faft o\ufe0fnly in 10 minutes',
    'remind me every 10 minutes to stretch a.f.t.e.r.a.p.p.r.o.v.a.l',
    'remind me to stretch rev\u200biew\u200bfi\u200brst in 10 minutes',
    'remind me to stretch dr\u034faft o\u034fnly in 2 hrs',
)
TAILS = ('scheduling prohibited', 'scheduling forbidden', 'prohibited', 'forbidden',
         'not allowed', 'do not schedule', 'blocked until approved', 'vetoed',
         'reviewfirst', 'draftonly', 'afterapproval', 'pleaseapprove', 'pendingconsent',
         'a f t e r a p p r o v a l', 'd r a f t', 'a.f.t.e.r', 'r.e.v.i.e.w',
         'dr\u034faft', 'dr\ufe0eaft', 'dr\ufe0faft', 'dr\u200daft', 'dr\u2060aft',
         'dr\u00adaft', 'dr\ufeffaft', 'dr\u0301aft', 'stretch\u00a0now',
         '\uff44\uff52\uff41\uff46\uff54', 'it, draft', '(draft)', '"draft"', 'x-ray', 'mom\'s')
FORMS = ('remind me every 10 minutes to stretch {t}', 'remind me to stretch {t} in 10 minutes',
         'remind me to stretch {t} in 10 mins', 'remind me every 10 minutes to {t} stretch')


class ConfirmWhenUnsureTests(_base_module.ConsentIntervalUnicodeTests):
    def test_codex_74773f1_repros_verbatim(self):
        for text in CODEX_REPROS_74773F1:
            with self.subTest(text=text):
                self.assert_asks_without_saving(text)

    def test_unusual_or_control_bodies_confirm(self):
        for form in FORMS:
            for tail in TAILS:
                text = form.format(t=tail)
                with self.subTest(text=text):
                    self.assert_asks_without_saving(text)

    def test_simple_reminders_stay_instant(self):
        self.assert_saves_immediately('remind me to stretch in 10 minutes', 'stretch', None)
        self.assert_saves_immediately('remind me every 10 minutes to stretch', 'stretch', 600)
        self.assert_saves_immediately('Remind me to drink water in 10 mins', 'drink water', None)

    def test_two_hour_reminder_stays_instant(self):
        reply = self.say_fresh('remind me to stretch in 2 hrs')
        self.assertIn('Reminder saved', reply)
        self.assertEqual(len(self.items.rows), 1)


# Inherit only the fixture; base tests run in their own module.
for _name in [n for n in dir(_Base) if n.startswith('test_')]:
    if _name not in ConfirmWhenUnsureTests.__dict__:
        setattr(ConfirmWhenUnsureTests, _name, None)
del _Base

if __name__ == '__main__':
    unittest.main()
