"""Exact consent and original-body repros from codex-solo-consent-64ded6eb2f7a.

Exercise the real handlers, parsers, allowlist/preparation, and reminder create
method. Only persistence and external effects are replaced by memory adapters.
"""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch
import uuid

from app import Chat
import chat_intent
from local_tasks import LocalFiles, LocalTasks
from reminders import Reminders, ZONE
from texting_fixture import OfflineProviders


EPOCH = 1791828000
FILE_REQUEST = 'Create file ~/Documents/proposal.txt: hello'
RECURRING_REQUEST = 'remind me every 10 minutes to stretch'

# Every structured CONSENT-NONEXACT-CONFIRMATION reproduction, including its
# literal issued token and submitted message. Escapes become the report's actual
# control/Unicode characters when passed to handle(). No report file is needed.
CONFIRMATION_REPROS = (
    ('reminder', RECURRING_REQUEST,
     'yes wbrem-241793d00bba4f9d85ac89d20c33b8ac',
     '\u00a0yes wbrem-241793d00bba4f9d85ac89d20c33b8ac\u00a0'),
    ('reminder', RECURRING_REQUEST,
     'yes wbrem-d2f0b9b48f5e425885042960af2492f2',
     '\u001cyes wbrem-d2f0b9b48f5e425885042960af2492f2\u001c'),
    ('file', FILE_REQUEST,
     'yes wblocal-51cc1292497144f2856d28b5af7470e7',
     'yes WBLOCAL-51CC1292497144F2856D28B5AF7470E7'),
    ('file', FILE_REQUEST,
     'yes wblocal-233751a4aa0a42d78cbfac01f8eacdeb',
     'ye\u017f wblocal-233751a4aa0a42d78cbfac01f8eacdeb'),
    ('file', FILE_REQUEST,
     'yes wblocal-fbf8d3959156411bbd8550f5e668d09b',
     'yes\twblocal-fbf8d3959156411bbd8550f5e668d09b'),
    ('file', FILE_REQUEST,
     'yes wblocal-69229b7dbf124e71b211ce269ab28b01',
     'yes\nwblocal-69229b7dbf124e71b211ce269ab28b01'),
    ('file', FILE_REQUEST,
     'yes wblocal-e1894a26cb9c4da08daf22d33ff8607c',
     'yes\u00a0wblocal-e1894a26cb9c4da08daf22d33ff8607c'),
)

# Every structured CONSENT-ORIGINAL-BODY reproduction, with original body,
# issued token, and the original absolute due time/interval from the report.
BODY_REPROS = (
    ('remind me to take 2 mins rest in 10 minutes', 'take 2 mins rest',
     'yes wbrem-2daaa50cf091493d8300e2d5298176b0', 1791828600, None),
    ('remind me every 10 minutes to take 2 mins rest', 'take 2 mins rest',
     'yes wbrem-143548e98c3441a4acb264ad6a7d6f81', 1791828600, 600),
    ('please remind me to record 2 hrs of sleep in 2 hrs', 'record 2 hrs of sleep',
     'yes wbrem-c39d3c01223d4d2e8437762e82909917', 1791835200, None),
    ('Create a reminder for 2am to take 2 mins rest', 'take 2 mins rest',
     'yes wbrem-863051d3e777465384712a8e552ae06b', 1791874800, None),
    ('Set a timer for 10 minutes to take 2 mins rest', 'take 2 mins rest',
     'yes wbrem-654f27d14c474479a55fb30e7896968f', 1791828600, None),
)

REMINDER_REQUESTS = (
    RECURRING_REQUEST,
    'remind me to stretch in 10 minutes',
    'remind me to stretch draft only in 10 minutes',
    'remind me to stretch dra\u200bft only in 10 minutes',
    'remind me to inspect ticket cea5e12345678901 in 10 minutes',
    'Create a reminder for 2am to go to bed',
    'Set a timer for 10 minutes to stretch',
)
FILE_REQUESTS = (
    FILE_REQUEST,
    'Create file ~/Documents/proposal.txt: hello; draft only.',
    'Create file ~/Documents/proposal.txt: hello; dra\u200bft only.',
)
REQUESTS = tuple(('reminder', text) for text in REMINDER_REQUESTS) + tuple(
    ('file', text) for text in FILE_REQUESTS)
BODY_FORMS = (
    ('remind me every 10 minutes to {body}', 600, 600),
    ('remind me every 2 hrs to {body}', 7200, 7200),
    ('remind me to {body} in 10 minutes', 600, None),
    ('please remind me to {body} in 2 hrs', 7200, None),
    ('Create a reminder for 2am to {body}', 46800, None),
    ('Set a timer for 10 minutes to {body}', 600, None),
)

# Every literal CONSENT-ORIGINAL-BODY reproduction and additional observed
# variant from codex-solo-consent-9bb4a67a2edd, including the issued tokens.
PUNCTUATION_BODY_REPROS = (
    ('remind me every 10 minutes to print the literal string .?!',
     'print the literal string .?!',
     'yes wbrem-643e1faf517e425399fc7500a4f301b5', 1791828600, 600),
    ('Create a reminder for 2am to print the literal string .?!',
     'print the literal string .?!',
     'yes wbrem-234e6a3d23f24d0cad3c0103a5ac7ac6', 1791874800, None),
    ('Set a timer for 10 minutes to print the literal string .?!',
     'print the literal string .?!',
     'yes wbrem-841972742644420dbe0521cb4691cf37', 1791828600, None),
    ('remind me in 10 mins to print the literal string .?!',
     'print the literal string .?!',
     'yes wbrem-8ba23d953bd9402d8d278e6afb59443c', 1791828600, None),
    ('remind me every 10 minutes to inspect path ..',
     'inspect path ..', None, 1791828600, 600),
    ('remind me every 10 minutes to review the operator ?',
     'review the operator ?', None, 1791828600, 600),
    ('remind me every 10 minutes to check U.S.',
     'check U.S.', None, 1791828600, 600),
)
PUNCTUATION_BODY_FORMS = (
    ('remind me every 10 minutes to {body}', 600, 600),
    ('please remind me every 10 mins to {body}', 600, 600),
    ('remind me in 10 mins to {body}', 600, None),
    ('remind me for 10 minutes to {body}', 600, None),
    ('Create a reminder for 2am to {body}', 46800, None),
    ('Set a timer for 10 minutes to {body}', 600, None),
    ('remind me to {body} in 10 minutes', 600, None),
    ('please remind me to {body} in 2 hrs', 7200, None),
)


def nonexact_messages(command, token):
    """Include all report transformations plus exact-format boundary cases."""
    exact = command + ' ' + token
    prefix, hexadecimal = token.split('-')
    variants = {
        'uppercase_command': command.upper() + ' ' + token,
        'titlecase_command': command.title() + ' ' + token,
        'uppercase_token': command + ' ' + token.upper(),
        'uppercase_prefix': command + ' ' + prefix.upper() + '-' + hexadecimal,
        'uppercase_hex': command + ' ' + prefix + '-' + hexadecimal.upper(),
        'fullwidth_command': ''.join(chr(ord(c) + 0xFEE0) for c in command) + ' ' + token,
        'wrong_prefix': command + ' ' + ('wbrem' if prefix == 'wblocal' else 'wblocal') + '-' + hexadecimal,
        'missing_hyphen': command + ' ' + prefix + hexadecimal,
        'unicode_hyphen': command + ' ' + prefix + '\u2010' + hexadecimal,
        'short_hex': command + ' ' + token[:-1],
        'long_hex': exact + '0',
        'nonhex': command + ' ' + token[:-1] + 'g',
        'wrong_hex': command + ' ' + token[:-1] + ('0' if token[-1] != '0' else '1'),
        'unicode_hex': command + ' ' + prefix + '-\uff10' + hexadecimal[1:],
        'token_zero_width': command + ' ' + prefix + '-\u200b' + hexadecimal,
        'trailing_text': exact + ' please',
        'punctuation': exact + '.',
        'quoted': '"' + exact + '"',
        'no_separator': command + token,
    }
    if command == 'yes':
        variants['long_s'] = 'ye\u017f ' + token
    else:
        variants['cyrillic_a'] = 'c\u0430ncel ' + token
    for name, separator in (
        ('double_space', '  '), ('many_spaces', '   '), ('tab', '\t'),
        ('newline', '\n'), ('carriage_return', '\r'), ('CRLF', '\r\n'),
        ('vertical_tab', '\v'), ('form_feed', '\f'), ('NBSP', '\u00a0'),
        ('narrow_NBSP', '\u202f'), ('line_separator', '\u2028'),
        ('paragraph_separator', '\u2029'), ('U001C', '\u001c'),
        ('zero_width_space', '\u200b'),
    ):
        variants['separator_' + name] = command + separator + token
    for name, padding in (
        ('space', ' '), ('tab', '\t'), ('newline', '\n'), ('CRLF', '\r\n'),
        ('NBSP', '\u00a0'), ('narrow_NBSP', '\u202f'),
        ('line_separator', '\u2028'), ('paragraph_separator', '\u2029'),
        ('U001C', '\u001c'), ('NUL', '\x00'), ('BOM', '\ufeff'),
    ):
        variants['leading_' + name] = padding + exact
        variants['trailing_' + name] = exact + padding
        variants['outer_' + name] = padding + exact + padding
    return variants


class MemoryStore:
    def __init__(self, rows):
        self.rows = deepcopy(rows)
        self.writes = []
        self.before_save = lambda rows: None

    @contextmanager
    def locked(self):
        yield deepcopy(self.rows)

    def save(self, rows):
        self.before_save(rows)
        self.rows = deepcopy(rows)
        self.writes.append(deepcopy(rows))

    def reset(self):
        self.rows.clear()
        self.writes.clear()


class RecordingFiles(LocalFiles):
    def __init__(self, home, clock):
        super().__init__(home, clock)
        self.executions = []
        self.before_execute = lambda spec: None

    def execute(self, spec):
        self.before_execute(spec)
        if spec['kind'] != 'create':
            raise AssertionError('Unexpected file effect: ' + repr(spec))
        self.executions.append(deepcopy(spec))
        return 'File created: ' + spec['path']


class ConsentExactConfirmationTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory(prefix='.consent-exact-',
                                       dir=Path(__file__).resolve().parent)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.home = self.root / 'home'
        (self.home / 'Documents').mkdir(parents=True)
        self.target = self.home / 'Documents/proposal.txt'
        self.now = datetime(2026, 10, 12, 13, 0, tzinfo=ZONE).timestamp()
        self.assertEqual(self.now, EPOCH)
        self.state = chat_intent.new_state()
        self.items, self.drafts, self.receipts = MemoryStore([]), MemoryStore({}), MemoryStore({})
        self.reminders = Reminders(self.root, clock=lambda: self.now)
        self.files = RecordingFiles(self.home, clock=lambda: self.now)
        self.search = Mock(side_effect=AssertionError('Unexpected search'))
        self.local = LocalTasks(self.root, files=self.files, search=self.search,
                                clock=lambda: self.now)
        for handler, store, lock, save in (
            (self.reminders, self.items, 'locked', 'save'),
            (self.reminders, self.drafts, 'draft_lock', 'save_drafts'),
            (self.local, self.receipts, 'locked', 'save'),
        ):
            for method, replacement in ((lock, store.locked), (save, store.save)):
                guard = patch.object(handler, method, replacement)
                guard.start()
                self.addCleanup(guard.stop)
        # An effect must observe already-consumed, durably stored consent.
        self.items.before_save = lambda rows: self.assertEqual(
            [row['state'] for row in self.drafts.rows.values()], ['unconfirmed'])
        self.files.before_execute = lambda spec: self.assertEqual(
            [row['state'] for row in self.receipts.rows.values()], ['claimed'])
        for target in ('urllib.request.OpenerDirector.open', 'socket.socket.connect',
                       'subprocess.run', 'reminders.notify_macos'):
            guard = patch(target, side_effect=AssertionError('Unexpected external effect: ' + target))
            blocked = guard.start()
            self.addCleanup(blocked.assert_not_called)
            self.addCleanup(guard.stop)

    def reset(self):
        self.now = EPOCH
        self.state = chat_intent.new_state()
        for store in (self.items, self.drafts, self.receipts):
            store.reset()
        self.files.executions.clear()
        self.assertFalse(self.target.exists())

    def say(self, kind, text, request_id='request', cid='unheld', actor='owner'):
        if kind == 'file':
            return self.local.handle(text, cid, request_id, self.state)
        return self.reminders.handle(text, cid, request_id, intent_state=self.state, actor=actor)

    def store(self, kind):
        return self.receipts if kind == 'file' else self.drafts

    def assert_no_effect(self):
        self.assertEqual(self.items.rows, [])
        self.assertEqual(self.items.writes, [])
        self.assertEqual(self.files.executions, [])
        self.assertFalse(self.target.exists())
        self.search.assert_not_called()

    def draft(self, kind, request, issued=None):
        self.reset()
        self.assertEqual(chat_intent.blocked_scopes(
            self.state, chat_intent.projects(request), action_text=request), [])
        if issued:
            token = issued.split(' ')[1]
            module = 'local_tasks' if kind == 'file' else 'reminders'
            with patch(module + '.uuid.uuid4', return_value=uuid.UUID(hex=token.split('-')[1])):
                reply = self.say(kind, request)
        else:
            reply = self.say(kind, request)
        self.assert_no_effect()
        self.assertIsInstance(reply, str, request)
        self.assertEqual(len(self.store(kind).rows), 1, reply)
        token, = self.store(kind).rows
        self.assertIn('Reply `yes ' + token + '`', reply)
        if issued:
            self.assertEqual('yes ' + token, issued)
        row = self.store(kind).rows[token]
        self.assertEqual((row['state'], row['text']), ('draft', request))
        self.assertEqual(len(self.store(kind).writes), 1)
        return token

    def assert_nonconfirmation(self, kind, message, request_id='later'):
        stores = (self.items, self.drafts, self.receipts)
        before = deepcopy([(store.rows, store.writes) for store in stores])
        self.say(kind, message, request_id)
        self.assert_no_effect()
        self.assertEqual([(store.rows, store.writes) for store in stores], before,
                         'Nonexact control changed persisted state: ' + repr(message))

    def confirm_once(self, kind, token):
        draft = deepcopy(self.store(kind).rows[token])
        self.now += 30
        reply = self.say(kind, 'yes ' + token, 'exact-later')
        self.assertEqual(self.store(kind).rows[token]['state'], 'done', reply)
        if kind == 'file':
            self.assertIn('File created:', reply)
            self.assertEqual(self.files.executions, [draft['spec']])
            self.assertEqual(self.files.executions[0]['path'], str(self.target))
            self.assertEqual(self.items.writes, [])
        else:
            self.assertIn('Reminder saved:', reply)
            self.assertEqual(len(self.items.writes), 1)
            row, = self.items.rows
            self.assertEqual((row['body'], row['due_at'], row['interval_seconds'], row['state']),
                             (draft['body'], draft['due'], draft['interval'], 'pending'))
            self.assertEqual(row['created_at'], self.now)
            self.assertEqual(self.files.executions, [])
        before = deepcopy((self.items.writes, self.files.executions,
                           self.drafts.writes, self.receipts.writes))
        for request_id in ('exact-later', 'replay'):
            self.say(kind, 'yes ' + token, request_id)
            self.assertEqual((self.items.writes, self.files.executions,
                              self.drafts.writes, self.receipts.writes), before)
        self.assertFalse(self.target.exists())

    def assert_original_body(self, request, body, due, interval, issued=None):
        token = self.draft('reminder', request, issued)
        row = self.drafts.rows[token]
        self.assertEqual((row['body'], row['due'], row['interval']), (body, due, interval))
        self.assertIn('Draft reminder: ' + body, self.reminders.draft_receipt(row))
        self.confirm_once('reminder', token)
        self.assertEqual(self.items.rows[0]['body'], body)

    def test_codex_nonexact_confirmation_reproductions_verbatim(self):
        for kind, request, issued, submitted in CONFIRMATION_REPROS:
            with self.subTest(kind=kind, submitted=submitted):
                token = self.draft(kind, request, issued)
                self.assert_nonconfirmation(kind, submitted)
                self.confirm_once(kind, token)

    def test_codex_original_body_reproductions_verbatim(self):
        for request, body, issued, due, interval in BODY_REPROS:
            with self.subTest(request=request):
                self.assert_original_body(request, body, due, interval, issued)

    def test_codex_trailing_body_punctuation_reproductions_verbatim(self):
        for request, body, issued, due, interval in PUNCTUATION_BODY_REPROS:
            with self.subTest(request=request):
                self.assert_original_body(request, body, due, interval, issued)

    def test_literal_body_punctuation_survives_all_schedule_placements(self):
        bodies = ('print the literal string .?!', 'inspect path ..',
                  'review the operator ?', 'check U.S.',
                  'print the literal string .', 'print the literal string !',
                  'stretch.', 'stretch?', 'stretch!', '.?!', '?')
        for body in bodies:
            for template, delay, interval in PUNCTUATION_BODY_FORMS:
                request = template.format(body=body)
                with self.subTest(request=request):
                    self.assert_original_body(request, body, EPOCH + delay, interval)

    def test_schedule_final_punctuation_preserves_the_separate_body(self):
        for suffix in ('.', '?', '!', '..', '.?!'):
            for template, body, delay in (
                ('remind me to {body} in 10 minutes{suffix}',
                 'print the literal string .?!', 600),
                ('please remind me to {body} in 2 hrs{suffix}',
                 'inspect path ..', 7200),
                ('Create a reminder to {body} at 2am{suffix}', 'stretch', 46800),
                ('Create a reminder to {body} at 2026-10-13T07:00:00Z{suffix}',
                 'stretch', 46800),
            ):
                request = template.format(body=body, suffix=suffix)
                with self.subTest(request=request):
                    self.assert_original_body(request, body, EPOCH + delay, None)

    def test_schedule_only_punctuation_keeps_default_reminder_and_timer_bodies(self):
        for suffix in ('.', '?', '!', '..', '.?!'):
            for template, body, delay in (
                ('Create a reminder for 2am{suffix}', 'Reminder', 46800),
                ('Set a timer for 10 minutes{suffix}', 'Timer', 600),
                ('Set a timer at 2026-10-13T07:00:00Z{suffix}', 'Timer', 46800),
            ):
                request = template.format(suffix=suffix)
                with self.subTest(request=request):
                    self.assert_original_body(request, body, EPOCH + delay, None)

    def test_legacy_interrogative_sentence_boundary_matches_draft_and_save(self):
        # test_actions_intent preserves this existing parser expectation.
        # Its narrow question-mark exception must be visible before consent.
        for request, body in (
            ('Could you schedule a reminder for 2am to go to bed?', 'go to bed'),
            ('schedule a reminder for 2am to go to bed?', 'go to bed?'),
            ('Could you schedule a reminder for 2am to review the operator ?',
             'review the operator ?'),
            ('Could you schedule a reminder for 2am to check U.S.', 'check U.S.'),
            ('Could you schedule a reminder for 2am to print the literal string .?!',
             'print the literal string .?!'),
            ('Could you schedule a reminder for 2am to go to bed.', 'go to bed.'),
            ('Could you schedule a reminder for 2am to inspect path ..', 'inspect path ..'),
            ('Could you schedule a reminder for 2am to go to bed??', 'go to bed??'),
        ):
            with self.subTest(request=request):
                self.assert_original_body(request, body, 1791874800, None)

    def test_weekday_clock_followup_preserves_body_before_exact_confirmation(self):
        for body in ('print the literal string .?!', 'inspect path ..', 'check U.S.'):
            request = 'remind me every Monday to ' + body
            with self.subTest(request=request):
                self.reset()
                reply = self.say('reminder', request)
                self.assert_no_effect()
                original_token, = self.drafts.rows
                incomplete = self.drafts.rows[original_token]
                self.assertEqual((incomplete['body'], incomplete['state']), (body, 'needs_time'))
                self.assertIn('Draft reminder: ' + body, reply)

                reply = self.say('reminder', 'at 2pm', 'clock-followup')
                self.assert_no_effect()
                self.assertEqual(self.drafts.rows[original_token]['state'], 'replaced')
                token, = [key for key, row in self.drafts.rows.items() if row['state'] == 'draft']
                row = self.drafts.rows[token]
                self.assertEqual((row['body'], row['due'], row['interval']),
                                 (body, EPOCH + 3600, None))
                self.assertEqual(row['weekly_time'], {'day': 0, 'clock': '2pm'})
                self.assertIn('Draft reminder: ' + body, reply)
                self.assertIn('Reply `yes ' + token + '`', reply)

                # The old incomplete draft remains replaced when the later
                # exact confirmation durably consumes its completed draft.
                def consumed_with_replaced_draft(rows):
                    self.assertEqual(sorted(row['state'] for row in self.drafts.rows.values()),
                                     ['replaced', 'unconfirmed'])

                with patch.object(self.items, 'before_save', consumed_with_replaced_draft):
                    self.confirm_once('reminder', token)
                self.assertEqual(self.items.rows[0]['body'], body)
                self.assertEqual(self.items.rows[0]['weekly_time'], {'day': 0, 'clock': '2pm'})

    def test_nonexact_yes_and_cancel_leave_every_request_draft_untouched(self):
        for kind, request in REQUESTS:
            for command in ('yes', 'cancel'):
                # Fixed letters/digits make token casing probes deterministic.
                prefix = 'wblocal' if kind == 'file' else 'wbrem'
                issued = 'yes ' + prefix + '-0123456789abcdef0123456789abcdef'
                for variant, submitted in nonexact_messages(command, issued.split(' ')[1]).items():
                    with self.subTest(request=request, command=command, variant=variant):
                        token = self.draft(kind, request, issued)
                        self.assert_nonconfirmation(kind, submitted)
                        self.confirm_once(kind, token)

    def test_exact_cancel_prevents_confirmation_and_replay(self):
        for kind, request in REQUESTS:
            with self.subTest(request=request):
                token = self.draft(kind, request)
                reply = self.say(kind, 'cancel ' + token, 'cancel-later')
                self.assertIn('cancelled', reply)
                self.assertEqual(self.store(kind).rows[token]['state'], 'cancelled')
                before = deepcopy(self.store(kind).writes)
                for message in ('cancel ' + token, 'yes ' + token):
                    self.say(kind, message, 'replay')
                    self.assert_no_effect()
                    self.assertEqual(self.store(kind).writes, before)

    def test_exact_yes_keeps_request_conversation_and_actor_binding(self):
        for kind, request in REQUESTS:
            with self.subTest(request=request):
                token = self.draft(kind, request)
                self.assert_nonconfirmation(kind, 'yes ' + token, request_id='request')
                self.say(kind, 'yes ' + token, 'later', cid='another-unheld')
                self.assert_no_effect()
                if kind == 'reminder':
                    self.say(kind, 'yes ' + token, 'later', actor='another-actor')
                    self.assert_no_effect()
                self.assertEqual(self.store(kind).rows[token]['state'], 'draft')
                self.confirm_once(kind, token)

    def test_original_min_mins_hr_hrs_bodies_across_six_forms(self):
        bodies = ('take 2 min rest', 'take 2 mins rest',
                  'record 2 hr of sleep', 'record 2 hrs of sleep')
        for body in bodies:
            for template, delay, interval in BODY_FORMS:
                request = template.format(body=body)
                with self.subTest(request=request):
                    self.assert_original_body(request, body, EPOCH + delay, interval)

    def test_body_casing_and_spacing_survive_independent_schedule_abbreviations(self):
        body = 'Track 2 MIN  rest 3 Mins sleep 4 HR exercise 5 hRs recovery'
        for unit, delay in (('min', 60), ('mins', 60), ('hr', 3600), ('hrs', 3600)):
            for template, interval in (
                ('remind me every 1 {unit} to {body}', delay),
                ('please remind me to {body} in 1 {unit}', None),
                ('Create a reminder in 1 {unit} to {body}', None),
                ('Set a timer for 1 {unit} to {body}', None),
            ):
                request = template.format(unit=unit, body=body)
                with self.subTest(request=request):
                    self.assert_original_body(request, body, EPOCH + delay, interval)

    def test_competing_abbreviated_schedule_in_body_still_requires_clarification(self):
        for unit in ('min', 'mins', 'hr', 'hrs'):
            body = 'stretch in 2 ' + unit
            for template, _, _ in BODY_FORMS:
                request = template.format(body=body)
                with self.subTest(request=request):
                    self.reset()
                    reply = self.say('reminder', request)
                    self.assertIsInstance(reply, str)
                    self.assert_no_effect()
                    self.assertEqual(self.drafts.rows, {}, reply)
                    self.assertEqual(self.drafts.writes, [], reply)

    def test_chat_submit_preserves_padding_for_actual_consent_handlers(self):
        providers = OfflineProviders()
        providers.reply = Mock(side_effect=AssertionError('Unexpected model call'))
        chat = Chat(self.root / 'conductor/webchat', self.root, providers,
                    local_tasks=self.local)
        self.addCleanup(chat.close)
        chat.reminders = self.reminders
        with patch.object(chat, 'launch', side_effect=AssertionError('Unexpected model launch')):
            for kind, request in (('reminder', RECURRING_REQUEST), ('file', FILE_REQUEST)):
                for padding in (' ', '\t', '\n', '\u00a0', '\u001c', '\u2028'):
                    with self.subTest(kind=kind, padding=repr(padding)):
                        self.reset()
                        cid = chat.new_conversation()['id']

                        def submit(text):
                            return chat.submit(cid, text, str(uuid.uuid4()))['messages'][-1]

                        drafted = submit(request)
                        self.assert_no_effect()
                        token, = self.store(kind).rows
                        self.assertIn('Reply `yes ' + token + '`', drafted['content'])
                        before = deepcopy(self.store(kind).writes)
                        for command in ('yes', 'cancel'):
                            submit(padding + command + ' ' + token + padding)
                            self.assert_no_effect()
                            self.assertEqual(self.store(kind).writes, before)
                        self.now += 30
                        confirmed = submit('yes ' + token)
                        self.assertIn('File created:' if kind == 'file' else 'Reminder saved:',
                                      confirmed['content'])
                        effects = deepcopy((self.items.writes, self.files.executions))
                        self.assertEqual(len(self.items.writes) + len(self.files.executions), 1)
                        submit('yes ' + token)
                        self.assertEqual((self.items.writes, self.files.executions), effects)
        providers.reply.assert_not_called()


if __name__ == '__main__':
    unittest.main()
