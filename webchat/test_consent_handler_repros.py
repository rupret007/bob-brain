"""Consent repros through real handlers; only persistence/effects are fixtures."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

import chat_intent
from local_tasks import LocalFiles, LocalTasks
from reminders import Reminders, ZONE


REQUESTS = {
    'reminder': 'Create a reminder for 2am to go to bed',
    'timer': 'Set a timer for 10 minutes to stretch',
    'file': 'Create file ~/Documents/proposal.txt: hello',
}
CODEX_REPROS = (
    ('reminder', 'Create a reminder for 2am to go to bed; draft only.'),
    ('timer', 'Set a timer for 10 minutes to stretch; draft only.'),
    ('file', 'Create file ~/Documents/proposal.txt: hello; draft only.'),
    ('reminder', 'Create a reminder for 2am to go to bed, provided I agree.'),
    ('timer', 'Set a timer for 10 minutes to stretch, provided I agree.'),
    ('file', 'Create file ~/Documents/proposal.txt: hello, provided I agree.'),
    ('reminder', 'Create a reminder for 2am to go to bed; after I give the green light.'),
    ('timer', 'Set a timer for 10 minutes to stretch; after I give the green light.'),
    ('file', 'Create file ~/Documents/proposal.txt: hello; after I give the green light.'),
    ('reminder', 'Create a reminder for 2am to go to bed; let me see it first.'),
    ('timer', 'Set a timer for 10 minutes to stretch; let me see it first.'),
    ('file', 'Create file ~/Documents/proposal.txt: hello; let me see it first.'),
)
SUFFIXES = (
    'draft only', 'just a draft', 'only draft it', 'preview first',
    'show me first', 'let me review it', 'for my review', 'if I approve',
    'once I approve', 'after I approve', 'after I say yes', 'pending my OK',
    'wait for my go-ahead', "don't do it yet", 'not yet', 'hold off',
    'unless I object', 'assuming I agree', 'subject to my approval',
    'when I confirm', 'only after I confirm', 'maybe', 'dry run',
    'just propose it', 'suggest one', 'provided I agree',
    'after I give the green light', 'let me see it first', 'ask me first',
    'await my permission', 'only with my consent', 'pending my decision',
    'keep it provisional', 'do not execute yet', 'wait until I decide',
    'after my approval', 'if I confirm', 'do not create it yet',
)


class MemoryStore:
    """Copy on load/save so an unsaved mutation cannot look like persistence."""

    def __init__(self, rows):
        self.rows = rows
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


class RecordingFiles(LocalFiles):
    """Use the real allowlist/preparation; record execution without writing."""

    def __init__(self, home, clock):
        super().__init__(home, clock)
        self.executions = []
        self.created = {}

    def execute(self, spec):
        self.executions.append(deepcopy(spec))
        if spec['kind'] != 'create':
            raise AssertionError('Unexpected file effect: ' + repr(spec))
        self.created[spec['path']] = spec['content']
        return 'File created: ' + spec['path']


class ConsentHandlerRepros(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.home = self.root / 'home'
        (self.home / 'Documents').mkdir(parents=True)
        self.target = self.home / 'Documents/proposal.txt'
        self.now = datetime(2026, 10, 12, 13, 0, tzinfo=ZONE).timestamp()
        self.state = chat_intent.new_state()
        self.reminders = Reminders(self.root, clock=lambda: self.now)
        self.files = RecordingFiles(self.home, clock=lambda: self.now)
        self.search = Mock(side_effect=AssertionError('Unexpected search'))
        self.local = LocalTasks(self.root, files=self.files, search=self.search,
                                clock=lambda: self.now)
        self.items = MemoryStore([])
        self.drafts = MemoryStore({})
        self.receipts = MemoryStore({})
        for handler, store, lock, save in (
            (self.reminders, self.items, 'locked', 'save'),
            (self.reminders, self.drafts, 'draft_lock', 'save_drafts'),
            (self.local, self.receipts, 'locked', 'save'),
        ):
            for method, replacement in ((lock, store.locked), (save, store.save)):
                guard = patch.object(handler, method, replacement)
                guard.start()
                self.addCleanup(guard.stop)

    def say(self, kind, text, request_id='request'):
        if kind == 'file':
            return self.local.handle(text, 'unheld', request_id, self.state)
        return self.reminders.handle(text, 'unheld', request_id, intent_state=self.state)

    def assert_asks_without_effect(self, kind, text):
        # Each subTest starts with an absent, allowed target and no saved holds
        # or previous drafts that could accidentally prevent the repro effect.
        for store in (self.items, self.drafts, self.receipts):
            store.reset()
        self.files.executions.clear()
        self.files.created.clear()
        self.assertFalse(self.target.exists())
        self.assertEqual(chat_intent.blocked_scopes(
            self.state, chat_intent.projects(text), action_text=text), [])
        prepared = self.files.prepare(dict(kind='create', path='~/Documents/proposal.txt', content='hello'))
        self.assertEqual(prepared['kind'], 'create')
        reply = self.say(kind, text)
        self.assertEqual(self.items.rows, [], reply)
        self.assertEqual(self.items.writes, [], reply)
        self.assertEqual(self.reminders.listing(), [], reply)
        self.assertEqual(self.files.executions, [], reply)
        self.assertEqual(self.files.created, {}, reply)
        self.assertFalse(self.target.exists(), reply)
        self.search.assert_not_called()
        self.assertIsInstance(reply, str, 'Handler fell through: ' + text)
        self.assertNotRegex(reply, r'(?i)Reminder saved|File created')
        # Existing clarification replies request a fresh scheduling instruction;
        # file drafts instead request the separate, exact approval token.
        self.assertRegex(reply, r'Send a new (?:reminder|file) request|'
                                r'Reply `yes (?:wbrem|wblocal)-[0-9a-f]{32}`')

    def test_codex_repros_verbatim(self):
        for kind, text in CODEX_REPROS:
            with self.subTest(kind=kind, text=text):
                self.assert_asks_without_effect(kind, text)

    def test_suffix_matrix(self):
        self.assertGreaterEqual(len(set(SUFFIXES)), 30)
        for suffix in SUFFIXES:
            for kind, request in REQUESTS.items():
                for separator in ('; ', ', ', ' ', ' — ', '\n'):
                    with self.subTest(kind=kind, suffix=suffix, separator=separator):
                        self.assert_asks_without_effect(kind, request + separator + suffix + '.')

    def test_casing_and_curly_apostrophes(self):
        for suffix in SUFFIXES:
            for kind, request in REQUESTS.items():
                for variant in (suffix.upper(), suffix.title(), suffix.replace("'", '’')):
                    with self.subTest(kind=kind, suffix=variant):
                        self.assert_asks_without_effect(kind, request + '; ' + variant + '.')

    def test_leading_constraints(self):
        for prefix in SUFFIXES:
            for kind, request in REQUESTS.items():
                for separator in (': ', ' — ', '\n', ' '):
                    text = prefix.capitalize() + separator + request[0].lower() + request[1:]
                    with self.subTest(kind=kind, text=text):
                        self.assert_asks_without_effect(kind, text)

    def test_unconditional_timer_still_schedules(self):
        reply = self.say('timer', 'Set a timer for 10 minutes to stretch')
        # Preserve the existing exact-confirmation flow for this timer syntax.
        self.assertEqual(self.items.rows, [])
        self.assertRegex(reply, r'Reply `yes wbrem-[0-9a-f]{32}`')
        token, = self.drafts.rows
        reply = self.say('timer', 'yes ' + token, 'confirmation')
        self.assertIn('Reminder saved', reply)
        row, = self.items.rows
        self.assertEqual((row['body'], row['due_at'], row['state']),
                         ('stretch', self.now + 600, 'pending'))
        self.assertEqual(len(self.items.writes), 1)

    def test_explicit_interval_saves_after_confirmation(self):
        drafted_at = self.now
        reply = self.say('reminder', 'remind me to stretch in 10 minutes')
        self.assertEqual(self.items.rows, [], reply)
        self.assertEqual(self.items.writes, [], reply)
        self.assertNotIn('Reminder saved', reply)
        self.assertRegex(reply, r'Reply `yes wbrem-[0-9a-f]{32}`')
        token, = self.drafts.rows
        self.assertIn('Reply `yes ' + token + '`', reply)
        self.now += 30
        reply = self.say('reminder', 'yes ' + token, 'confirmation')
        self.assertIn('Reminder saved', reply)
        row, = self.items.rows
        self.assertEqual((row['body'], row['due_at']), ('stretch', drafted_at + 600))
        self.assertEqual((row['interval_seconds'], row['state']), (None, 'pending'))
        self.assertEqual(len(self.items.writes), 1)

    def test_plain_file_requires_separate_exact_confirmation(self):
        reply = self.say('file', 'Create file ~/Documents/proposal.txt: hello')
        self.assertRegex(reply, r'Reply `yes wblocal-[0-9a-f]{32}` to create\.$')
        self.assertNotIn('File created', reply)
        self.assertEqual(self.files.executions, [])
        self.assertFalse(self.target.exists())
        token, = self.receipts.rows
        for confirmation in ('yes', 'yes ' + token + ' please', 'yes ' + token):
            with self.subTest(confirmation=confirmation):
                # Even the exact token cannot approve in the original turn.
                self.say('file', confirmation)
                self.assertEqual(self.files.executions, [])
        reply = self.say('file', 'yes ' + token, 'confirmation')
        self.assertIn('File created', reply)
        self.assertEqual(len(self.files.executions), 1)
        self.assertEqual(self.files.created, {str(self.target): 'hello'})
        self.say('file', 'yes ' + token, 'replay')
        self.assertEqual(len(self.files.executions), 1)


if __name__ == '__main__':
    unittest.main()
