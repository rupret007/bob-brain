"""Capability ledger regressions using a temporary home and offline adapters."""
from consent_fixture import confirm_reply, confirm_chat

import json
from contextlib import contextmanager, nullcontext
from datetime import datetime
import fcntl
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
import uuid
from unittest.mock import Mock, patch

import chat_intent
from local_tasks import LocalFiles, LocalTasks, LocalTaskError, LOCK_TIMEOUT, SECRET_REFUSAL, safe_read


class CapabilityLedgerTests(unittest.TestCase):
    @contextmanager
    def isolated_chat(self, now=None):
        from app import Chat
        from reminders import ZONE
        providers, texting, calendar, notifier = Mock(), Mock(), Mock(), Mock()
        providers.timeouts = {}
        providers.reply.side_effect = AssertionError('Unexpected provider call')
        texting.handle.return_value = False
        texting.public.side_effect = dict
        calendar.handle.return_value = None
        if now is None:
            now = datetime(2026, 10, 11, 1, 47, tzinfo=ZONE).timestamp()
        with tempfile.TemporaryDirectory(dir=self.root) as folder, \
                patch('app.load_live_ops', return_value={}), \
                patch('time.time', return_value=now):
            root = Path(folder)
            home = root / 'home'
            (home / 'Documents').mkdir(parents=True)
            actions = LocalTasks(root / 'local', files=LocalFiles(home, clock=lambda: now),
                                 search=self.search, clock=lambda: now)
            chat = Chat(root / 'webchat', root, providers, texting=texting,
                        calendar=calendar, reminder_notifier=notifier, local_tasks=actions)
            chat.reminders.clock = lambda: now
            cid = chat.conversation_list()['conversations'][0]['id']
            try:
                yield chat, cid, home
                providers.reply.assert_not_called()
                notifier.assert_not_called()
                self.search.assert_not_called()
            finally:
                chat.close()

    DEFERRED_CONSTRAINTS = (
        '; after I give the green light.', '; let me see it first.',
        '; AFTER I GIVE THE GREEN LIGHT.', '; after I give the green-light.',
        '; once I give a green light.', '; when I give you the green light.',
        '; pending the green light.', '; green light required.',
        '; after I give the go-ahead.', '; once I give you the go ahead.',
        '; let me see this first.', '; LET ME SEE IT FIRST.',
        '; let me see the result first.', '; let me look at it first.',
        '; let me check it first.', '; let me inspect it first.',
    )

    def test_ledger_B9_deferred_and_preview_requests_never_schedule_through_chat(self):
        from reminders import ZONE
        now = datetime(2026, 10, 12, 13, tzinfo=ZONE).timestamp()
        constraints = self.DEFERRED_CONSTRAINTS
        prefixes = ('Create a reminder for 2am to go to bed',
                    'Set a timer for 10 minutes to stretch',
                    'remind me every 2 hours to stretch',
                    'every morning remind me to stretch')
        for prefix in prefixes:
            for constraint in constraints:
                with self.subTest(prefix=prefix, constraint=constraint), \
                        self.isolated_chat(now=now) as (chat, cid, home):
                    rows = []
                    with patch.object(chat.reminders, 'locked', side_effect=lambda: nullcontext(rows)), \
                            patch.object(chat.reminders, 'save') as save, \
                            patch.object(chat.reminders, 'create', wraps=chat.reminders.create) as create:
                        reply = chat.submit(cid, prefix + constraint, str(uuid.uuid4()))['messages'][-1]
                        self.assertEqual(chat.reminders.listing(), [])
                        create.assert_not_called()
                        save.assert_not_called()
                        self.assertEqual(reply['provider'], 'reminders')
                        self.assertIn('Nothing was saved', reply['content'])
                        self.assertNotIn('Reminder saved:', reply['content'])
        for command, body, due in (
                (prefixes[0], 'go to bed', datetime(2026, 10, 13, 2, tzinfo=ZONE).timestamp()),
                (prefixes[1], 'stretch', now + 600)):
            with self.subTest(control=command), self.isolated_chat(now=now) as (chat, cid, home):
                reply = chat.submit(cid, command, str(uuid.uuid4()))['messages'][-1]
                self.assertFalse(chat.reminders.listing())
                reply = confirm_chat(self, chat, cid, reply)
                self.assertIn('Reminder saved:', reply['content'])
                row, = chat.reminders.listing()
                self.assertEqual((row['body'], row['state'], row['due_at']), (body, 'pending', due))

    def test_ledger_B7_draft_and_conditional_requests_never_schedule_through_chat(self):
        from reminders import ZONE
        now = datetime(2026, 10, 12, 13, tzinfo=ZONE).timestamp()
        constraints = (
            '; draft only.', ', provided I agree.',
            '; DRAFT ONLY.', '; draft-only.', '; just a draft.',
            '; keep this as a draft.', '; draft it first.', '; for drafting.',
            ', if I agree.', ', when I agree.', ', once I agree.',
            ', subject to my agreement.', ', agreement required.',
            ', PROVIDED I AGREE.', ', provided I accept.',
            ', conditional on my decision.',
        )
        prefixes = ('Create a reminder for 2am to go to bed',
                    'Set a timer for 10 minutes to stretch',
                    'remind me every 2 hours to stretch',
                    'every morning remind me to stretch')
        for prefix in prefixes:
            for constraint in constraints:
                with self.subTest(prefix=prefix, constraint=constraint), \
                        self.isolated_chat(now=now) as (chat, cid, home):
                    rows = []
                    with patch.object(chat.reminders, 'locked', side_effect=lambda: nullcontext(rows)), \
                            patch.object(chat.reminders, 'save') as save, \
                            patch.object(chat.reminders, 'create', wraps=chat.reminders.create) as create:
                        reply = chat.submit(cid, prefix + constraint, str(uuid.uuid4()))['messages'][-1]
                        self.assertEqual(chat.reminders.listing(), [])
                        create.assert_not_called()
                        save.assert_not_called()
                        self.assertEqual(reply['provider'], 'reminders')
                        self.assertIn('Nothing was saved', reply['content'])
                        self.assertNotIn('Reminder saved:', reply['content'])
        for command, body, due in (
                (prefixes[0], 'go to bed', datetime(2026, 10, 13, 2, tzinfo=ZONE).timestamp()),
                (prefixes[1], 'stretch', now + 600)):
            with self.subTest(control=command), self.isolated_chat(now=now) as (chat, cid, home):
                reply = chat.submit(cid, command, str(uuid.uuid4()))['messages'][-1]
                self.assertFalse(chat.reminders.listing())
                reply = confirm_chat(self, chat, cid, reply)
                self.assertIn('Reminder saved:', reply['content'])
                row, = chat.reminders.listing()
                self.assertEqual((row['body'], row['state'], row['due_at']), (body, 'pending', due))

    def test_ledger_B10_deferred_and_preview_creation_requires_exact_yes_through_chat(self):
        from reminders import ZONE
        now = datetime(2026, 10, 12, 13, tzinfo=ZONE).timestamp()
        constraints = self.DEFERRED_CONSTRAINTS
        for constraint in constraints:
            with self.subTest(constraint=constraint), self.isolated_chat(now=now) as (chat, cid, home):
                target = home / 'Documents/result.txt'
                command = 'Create file ~/Documents/result.txt: hello' + constraint
                rows = {}
                with patch.object(chat.local_tasks, 'locked', side_effect=lambda: nullcontext(rows)), \
                        patch.object(chat.local_tasks, 'save') as save, \
                        patch.object(chat.local_tasks.files, 'execute',
                                  return_value='File created: ' + str(target)) as execute:
                    reply = chat.submit(cid, command, str(uuid.uuid4()))['messages'][-1]
                    execute.assert_not_called()
                    self.assertFalse(target.exists())
                    self.assertEqual(reply['provider'], 'local-tasks')
                    self.assertIn('Draft file:', reply['content'])
                    with chat.local_tasks.locked() as rows:
                        row, = rows.values()
                    save.assert_called_once()
                    self.assertEqual(row['state'], 'draft')
                    self.assertEqual(row['expires'], now + 3600)
                    self.assertIn('yes ' + row['token'], reply['content'])
                    chat.submit(cid, 'yes', str(uuid.uuid4()))
                    execute.assert_not_called()
                    reply = chat.submit(cid, 'yes ' + row['token'], str(uuid.uuid4()))['messages'][-1]
                    self.assertIn('File created:', reply['content'])
                    execute.assert_called_once_with(row['spec'])
                    self.assertEqual(row['state'], 'done')
                    self.assertEqual(row['spec']['content'], 'hello' + constraint)
                    chat.submit(cid, 'yes ' + row['token'], str(uuid.uuid4()))
                    execute.assert_called_once()
        with self.isolated_chat(now=now) as (chat, cid, home):
            target = home / 'Documents/result.txt'
            with patch.object(chat.local_tasks.files, 'execute',
                              return_value='File created: ' + str(target)) as execute:
                reply = chat.submit(cid, 'Create file ~/Documents/result.txt: hello',
                                    str(uuid.uuid4()))['messages'][-1]
                execute.assert_not_called()
                reply = confirm_chat(self, chat, cid, reply)
                self.assertIn('File created:', reply['content'])
                execute.assert_called_once()
                self.assertEqual(execute.call_args.args[0]['content'], 'hello')

    def test_ledger_B8_draft_and_conditional_creation_requires_exact_yes_through_chat(self):
        from reminders import ZONE
        now = datetime(2026, 10, 12, 13, tzinfo=ZONE).timestamp()
        constraints = (
            '; draft only.', ', provided I agree.',
            '; DRAFT ONLY.', '; draft-only.', '; just a draft.',
            '; keep this as a draft.', '; draft it first.', '; for drafting.',
            ', if I agree.', ', when I agree.', ', once I agree.',
            ', subject to my agreement.', ', agreement required.',
            ', PROVIDED I AGREE.', ', provided I accept.',
            ', conditional on my decision.',
        )
        for constraint in constraints:
            with self.subTest(constraint=constraint), self.isolated_chat(now=now) as (chat, cid, home):
                target = home / 'Documents/result.txt'
                command = 'Create file ~/Documents/result.txt: hello' + constraint
                with patch.object(chat.local_tasks.files, 'execute',
                                  return_value='File created: ' + str(target)) as execute:
                    reply = chat.submit(cid, command, str(uuid.uuid4()))['messages'][-1]
                    execute.assert_not_called()
                    self.assertFalse(target.exists())
                    self.assertEqual(reply['provider'], 'local-tasks')
                    self.assertIn('Draft file:', reply['content'])
                    with chat.local_tasks.locked() as rows:
                        row, = rows.values()
                    self.assertEqual(row['state'], 'draft')
                    self.assertEqual(row['expires'], now + 3600)
                    self.assertIn('yes ' + row['token'], reply['content'])
                    chat.submit(cid, 'yes', str(uuid.uuid4()))
                    execute.assert_not_called()
                    reply = chat.submit(cid, 'yes ' + row['token'], str(uuid.uuid4()))['messages'][-1]
                    self.assertIn('File created:', reply['content'])
                    execute.assert_called_once_with(row['spec'])
                    self.assertEqual(row['spec']['content'], 'hello' + constraint)
                    chat.submit(cid, 'yes ' + row['token'], str(uuid.uuid4()))
                    execute.assert_called_once()
        with self.isolated_chat(now=now) as (chat, cid, home):
            target = home / 'Documents/result.txt'
            with patch.object(chat.local_tasks.files, 'execute',
                              return_value='File created: ' + str(target)) as execute:
                reply = chat.submit(cid, 'Create file ~/Documents/result.txt: hello',
                                    str(uuid.uuid4()))['messages'][-1]
                execute.assert_not_called()
                reply = confirm_chat(self, chat, cid, reply)
                self.assertIn('File created:', reply['content'])
                execute.assert_called_once()
                self.assertEqual(execute.call_args.args[0]['content'], 'hello')

    def test_ledger_B4_review_and_dry_run_never_schedule_through_chat(self):
        constraints = (
            'but I need to review it first', 'but run this as a dry run',
            'review first', 'REVIEW FIRST', 'for my review', 'needs reviewing',
            'send it for review', 'review-only', 'let me review it',
            'I want to review this', 'dry-run', 'DRY RUN', 'a dry run please',
            'perform a dry-run first', 'dry run only', 'this is a dry run',
        )
        for constraint in constraints:
            with self.subTest(constraint=constraint), self.isolated_chat() as (chat, cid, home):
                reply = chat.submit(cid, 'Create a reminder for 2am to stretch, ' + constraint,
                                    str(uuid.uuid4()))['messages'][-1]
                self.assertEqual(chat.reminders.listing(), [])
                self.assertEqual(reply['provider'], 'reminders')
                self.assertIn('Nothing was saved', reply['content'])
                self.assertNotIn('Reminder saved:', reply['content'])
                reply = chat.submit(cid, 'remind me at 2am to stretch', str(uuid.uuid4()))['messages'][-1]
                self.assertFalse(chat.reminders.listing())
                reply = confirm_chat(self, chat, cid, reply)
                self.assertIn('Reminder saved:', reply['content'])
                row, = chat.reminders.listing()
                self.assertEqual((row['body'], row['state'], row['due_at']),
                                 ('stretch', 'pending', self.clock() + 86400 + 780))

    def test_ledger_B5_preview_creation_requires_exact_yes_through_chat(self):
        constraints = (
            'just show me a preview', 'preview only', 'PREVIEW ONLY',
            'preview first', 'a preview please', 'send me a preview',
            'I need a preview', 'let me preview it', 'preview this',
            'preview-only', 'for preview', 'show the preview',
            'give me a preview', 'preview before proceeding',
            'run this as a dry run', 'I need to review it first',
        )
        for constraint in constraints:
            with self.subTest(constraint=constraint), self.isolated_chat() as (chat, cid, home):
                target = home / 'Documents/note.txt'
                command = 'create file ~/Documents/note.txt: hello; ' + constraint
                with patch.object(chat.local_tasks.files, 'execute',
                                  wraps=chat.local_tasks.files.execute) as execute:
                    reply = chat.submit(cid, command, str(uuid.uuid4()))['messages'][-1]
                    self.assertFalse(target.exists())
                    execute.assert_not_called()
                    self.assertEqual(reply['provider'], 'local-tasks')
                    self.assertIn('Draft file:', reply['content'])
                    with chat.local_tasks.locked() as rows:
                        row, = rows.values()
                    self.assertEqual(row['state'], 'draft')
                    self.assertIn('yes ' + row['token'], reply['content'])
                    chat.submit(cid, 'yes', str(uuid.uuid4()))
                    self.assertFalse(target.exists())
                    execute.assert_not_called()
                    reply = chat.submit(cid, 'yes ' + row['token'], str(uuid.uuid4()))['messages'][-1]
                    self.assertIn('File created:', reply['content'])
                    self.assertEqual(target.read_text(), 'hello; ' + constraint)
                    execute.assert_called_once()
        with self.isolated_chat() as (chat, cid, home):
            reply = chat.submit(cid, 'create file ~/Documents/note.txt: hello',
                                str(uuid.uuid4()))['messages'][-1]
            reply = confirm_chat(self, chat, cid, reply)
            self.assertIn('File created:', reply['content'])
            self.assertEqual((home / 'Documents/note.txt').read_text(), 'hello')

    def test_ledger_B6_word_duration_qualifiers_need_clarification_through_chat(self):
        qualifiers = (
            'in two days', 'in one day', 'in three days', 'in four days',
            'in five days', 'in six days', 'in seven days', 'in eight days',
            'in nine days', 'in ten days', 'in eleven days', 'in twelve days',
            'in twenty-one days', 'in a couple of days', 'in a few days',
            'IN TWO DAYS', 'in two hours', 'in thirty minutes', 'in two weeks',
            'in 2 days',
        )
        prefixes = ('Create a reminder for 2am to stretch',
                    'remind me every 2 hours to stretch',
                    'every morning remind me to stretch')
        for prefix in prefixes:
            for qualifier in qualifiers:
                with self.subTest(prefix=prefix, qualifier=qualifier), \
                        self.isolated_chat() as (chat, cid, home):
                    reply = chat.submit(cid, prefix + ' ' + qualifier,
                                        str(uuid.uuid4()))['messages'][-1]
                    self.assertEqual(chat.reminders.listing(), [])
                    self.assertEqual(reply['provider'], 'reminders')
                    # Numeric extra times reach the time parser; unresolved
                    # word quantities now ask at the earlier intent boundary.
                    expected = ('extra date or time clause' if qualifier == 'in 2 days'
                                and not prefix.startswith('every morning')
                                else 'Send a new reminder request')
                    self.assertIn(expected, reply['content'])
                    self.assertIn('Nothing was saved', reply['content'])
        from reminders import ZONE
        for command, body, day in (
                ('Create a reminder for 2am to stretch', 'stretch', 11),
                ('Create a reminder for 2026-10-13 at 2am to stretch', 'stretch', 13),
                ('Create a reminder for 2am to stretch outdoors', 'stretch outdoors', 11)):
            with self.subTest(command=command), self.isolated_chat() as (chat, cid, home):
                reply = chat.submit(cid, command, str(uuid.uuid4()))['messages'][-1]
                self.assertFalse(chat.reminders.listing())
                reply = confirm_chat(self, chat, cid, reply)
                self.assertIn('Reminder saved:', reply['content'])
                row, = chat.reminders.listing()
                self.assertEqual((row['body'], row['state'], row['due_at']),
                                 (body, 'pending', datetime(2026, 10, day, 2, tzinfo=ZONE).timestamp()))
        # Scope of "in" can describe either content or execution mode; ask.
        with self.isolated_chat() as (chat, cid, home):
            with patch.object(chat.reminders, 'create') as create, \
                    patch.object(chat.reminders, 'save') as save:
                reply = chat.submit(cid, 'Create a reminder for 2am to stretch in the garden',
                                    str(uuid.uuid4()))['messages'][-1]
                self.assertIn('Nothing was saved', reply['content'])
                create.assert_not_called()
                save.assert_not_called()
                self.assertFalse(chat.reminders.listing())

    B3_CONTENTS = (
        '<property name="password" value="SYNTHETIC_ONLY_123"/>',
        '<entry name="api_key">SYNTHETIC_ONLY_123</entry>',
    ) + tuple('<item label="' + label + '">SYNTHETIC_ONLY_123</item>' for label in (
        'PASSWORD', 'passwd', 'pwd', 'passphrase', 'secret', 'client_secret',
        'token', 'bearer', 'api-key', 'apikey', 'access_key', 'private key',
        'private_key', 'credential', 'credentials', 'auth',
    )) + (
        '{"name":"password","value":"SYNTHETIC_ONLY_123"}',
        '["api_key", "SYNTHETIC_ONLY_123"]',
        'password -> SYNTHETIC_ONLY_123',
        '## passphrase\nSYNTHETIC_ONLY_123',
        'SYNTHETIC_ONLY_123\n<!-- AUTH -->',
        '<entry NAME=\'ToKeN\'>SYNTHETIC_ONLY_123</entry>',
        'Remember to change your password tomorrow. SYNTHETIC_ONLY_123',
    )

    def test_ledger_B3_labels_in_any_syntax_refuse_entire_read(self):
        for index, content in enumerate(self.B3_CONTENTS):
            with self.subTest(content=content):
                self.assert_secret_read_refused('Documents/export.txt', content,
                                                ('SYNTHETIC_ONLY_123',), f'B3-read-{index}')
        self.assertIn('pattern match', SECRET_REFUSAL)
        self.assertIn('not a guarantee', SECRET_REFUSAL)

    def test_ledger_B3_labelled_writes_never_echo_or_persist(self):
        target = self.home / 'Documents/note.txt'
        target.write_text('original')
        for index, content in enumerate(self.B3_CONTENTS):
            for kind, name in (('create', 'new.txt'), ('write', 'note.txt')):
                with self.subTest(content=content, kind=kind):
                    (target.parent / 'new.txt').unlink(missing_ok=True)
                    target.write_text('original')
                    command = f'{kind} file ~/Documents/{name}: {content}'
                    with patch.object(self.actions, 'save') as save, \
                            patch.object(self.files, 'execute', wraps=self.files.execute) as execute:
                        reply = self.actions.handle(command, 'chat', f'B3-{kind}-{index}', self.state)
                        self.assertEqual(reply, SECRET_REFUSAL)
                        self.assertNotIn('SYNTHETIC_ONLY_123', reply)
                        save.assert_not_called()
                        execute.assert_not_called()
                    self.assertFalse((target.parent / 'new.txt').exists())
                    self.assertEqual(target.read_text(), 'original')
                    with self.assertRaises(LocalTaskError):
                        self.files.execute(dict(kind=kind, path=str(target.parent / name), content=content))
                    # Previously saved draft previews must also use the guard.
                    with self.assertRaises(LocalTaskError):
                        self.actions.receipt(dict(state='draft', token='wblocal-' + 'a' * 32,
                                                  spec=dict(kind=kind, path=str(target), content=content)))
        with self.actions.locked() as rows:
            self.assertEqual(rows, {})

    def test_ledger_B3_benign_xml_json_and_text_still_read(self):
        target = self.home / 'Documents/export.txt'
        for index, content in enumerate((
                '<property name="title" value="Morning notes"/>',
                '<entry name="color">blue</entry>',
                '{"title":"Morning notes","tasks":["water plants"]}',
                'Remember to water the plants tomorrow.')):
            with self.subTest(content=content):
                target.write_text(content)
                self.assertEqual(safe_read(content.encode()), content)
                self.assertEqual(self.actions.handle('read file ~/Documents/export.txt', 'chat',
                                                     f'B3-benign-{index}', self.state),
                                 'File read: ' + str(target) + '\n' + content)

    def test_ledger_B3_read_does_not_leak_into_chat_or_memory(self):
        import uuid
        from app import Chat
        target = self.home / 'Documents/export.xml'
        target.write_text(self.B3_CONTENTS[0])
        providers, texting, calendar = Mock(), Mock(), Mock()
        providers.timeouts = {}
        providers.reply.side_effect = AssertionError('Unexpected provider call')
        texting.handle.return_value = False
        texting.public.side_effect = dict
        calendar.handle.return_value = None
        chat_root = self.root / 'B3-chat'
        with patch('app.load_live_ops', return_value={}):
            chat = Chat(chat_root / 'webchat', chat_root, providers, texting=texting,
                        calendar=calendar, local_tasks=self.actions)
            self.addCleanup(chat.close)
            cid = chat.conversation_list()['conversations'][0]['id']
            result = chat.submit(cid, 'read file ~/Documents/export.xml', str(uuid.uuid4()))
        self.assertEqual(result['messages'][-1]['content'], SECRET_REFUSAL)
        self.assertNotIn('SYNTHETIC_ONLY_123', json.dumps(result))
        for folder in (chat_root, self.actions.folder):
            for path in folder.rglob('*'):
                if path.is_file():
                    self.assertNotIn(b'SYNTHETIC_ONLY_123', path.read_bytes(), str(path))
        providers.reply.assert_not_called()

    def test_ledger_B2_approval_language_never_saves_or_schedules(self):
        from reminders import Reminders, ReminderError, parse
        constraints = (
            'but ask me whether to schedule it first', 'only with my permission',
            'CONFIRM with me', 'approval needed', 'permission needed', 'with consent',
            'ask first', 'ask whether this is ready', 'ask before proceeding',
            'check with me', 'my ok is needed', 'my okay is needed',
            'my go-ahead is needed', 'my say-so is needed', 'say go to proceed',
            'say yes to proceed', 'say ok to proceed', 'wait for me',
            'wait until tomorrow', 'hold off', 'not yet', "don't do this yet",
            'until I return', 'before you proceed', 'before saving', 'before creating',
            'before writing', 'before scheduling', 'only if ready', 'only after review',
            'only when ready', 'only with my agreement',
        )
        refusal = 'Nothing was saved. Send a new reminder request when you want it scheduled.'
        for index, constraint in enumerate(constraints):
            for prefix in ('create a reminder for 2am to stretch',
                           'remind me at 2am to stretch',
                           'remind me every 2 hours to stretch',
                           'every morning remind me to stretch'):
                with self.subTest(constraint=constraint, prefix=prefix):
                    command = prefix + ', ' + constraint
                    folder = self.root / f'B2-{index}'
                    reminders = Reminders(folder, clock=self.clock)
                    with patch.object(reminders, 'save', wraps=reminders.save) as save, \
                            patch.object(reminders, 'create', wraps=reminders.create) as create:
                        self.assertEqual(reminders.handle(command, 'chat', command), refusal)
                        save.assert_not_called()
                        create.assert_not_called()
                    with self.assertRaisesRegex(ReminderError, 'Nothing was saved'):
                        parse(command, self.clock())
                    self.assertEqual(Reminders(folder, clock=self.clock).listing(), [])

    def test_ledger_B2_plain_reminder_still_schedules(self):
        from reminders import Reminders
        reminders = Reminders(self.root / 'B2-plain', clock=self.clock)
        draft = reminders.handle('remind me at 2am to stretch', 'chat', 'plain')
        self.assertFalse(reminders.listing())
        receipt = confirm_reply(self, draft, lambda text: reminders.handle(text, 'chat', 'confirmed'))
        self.assertIn('Reminder saved:', receipt)
        row, = reminders.listing()
        self.assertEqual(row['body'], 'stretch')
        self.assertEqual(row['state'], 'pending')

    def test_ledger_B1_approval_language_requires_saved_exact_yes(self):
        constraints = (
            'but first ask for my confirmation', 'only after I approve',
            'CONFIRM with me', 'approval needed', 'with permission', 'with consent',
            'ask me whether to proceed', 'ask first', 'ask whether this is ready',
            'ask before proceeding', 'check with me', 'my ok is needed',
            'my okay is needed', 'my go-ahead is needed', 'my say-so is needed',
            'say go to proceed', 'say yes to proceed', 'say ok to proceed',
            'wait for me', 'wait until tomorrow', 'hold off', 'not yet',
            "don't do this yet", 'until I return', 'before you proceed',
            'before saving', 'before creating', 'before writing', 'before scheduling',
            'only if ready', 'only when ready', 'only with my agreement',
        )
        target = self.home / 'Documents/note.txt'
        for index, constraint in enumerate(constraints):
            with self.subTest(constraint=constraint):
                target.unlink(missing_ok=True)
                command = 'create file ~/Documents/note.txt: hello, ' + constraint
                actions = LocalTasks(self.root / f'B1-{index}', files=self.files, clock=self.clock)
                with patch.object(self.files, 'execute', wraps=self.files.execute) as execute:
                    reply = actions.handle(command, 'chat', 'request', self.state)
                    self.assertFalse(target.exists())
                    execute.assert_not_called()
                    self.assertIn('Draft file:', reply)
                    with actions.locked() as rows:
                        row, = rows.values()
                    self.assertEqual(row['state'], 'draft')
                    self.assertRegex(row['token'], r'^wblocal-[0-9a-f]{32}$')
                    self.assertIn('yes ' + row['token'], reply)
                    restored = LocalTasks(self.root / f'B1-{index}', files=self.files, clock=self.clock)
                    self.assertEqual(restored.handle(command, 'chat', 'request', self.state), reply)
                    restored.handle('yes', 'chat', 'bare-yes', self.state)
                    self.assertFalse(target.exists())
                    result = restored.handle('yes ' + row['token'], 'chat', 'confirmed', self.state)
                    self.assertIn('File created:', result)
                    self.assertEqual(target.read_text(), 'hello, ' + constraint)
                    restored.handle('yes ' + row['token'], 'chat', 'replay', self.state)
                    execute.assert_called_once()
                target.unlink()

    def test_ledger_B1_plain_create_and_destructive_approval_controls(self):
        target = self.home / 'Documents/note.txt'
        draft = self.actions.handle('create file ~/Documents/note.txt: hello', 'chat', 'plain', self.state)
        self.assertFalse(target.exists())
        receipt = confirm_reply(self, draft, lambda text: self.actions.handle(text, 'chat', 'confirmed', self.state))
        self.assertIn('File created:', receipt)
        self.assertEqual(target.read_text(), 'hello')
        for index, command in enumerate((
                'write file ~/Documents/note.txt: replacement, with my consent',
                'delete file ~/Documents/note.txt, only with my permission')):
            with self.subTest(command=command), patch.object(self.files, 'execute') as execute:
                self.actions.handle(command, 'chat', f'B1-control-{index}', self.state)
                execute.assert_not_called()
                self.assertEqual(target.read_text(), 'hello')

    def setUp(self):
        # Load the real secret patterns without invoking git for build metadata.
        with patch('subprocess.check_output', side_effect=OSError('Offline build metadata')):
            import providers
        temporary = tempfile.TemporaryDirectory(dir='/private/tmp')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.home = self.root / 'home'
        for directory in ('Documents', 'Downloads'):
            (self.home / directory).mkdir(parents=True)
        self.clock = lambda: 1791614820
        self.files = LocalFiles(self.home, clock=self.clock)
        self.search = Mock(side_effect=AssertionError('Unexpected web search'))
        self.actions = LocalTasks(self.root / 'state', files=self.files,
                                  search=self.search, clock=self.clock)
        self.state = chat_intent.new_state()
        for target in ('urllib.request.OpenerDirector.open', 'socket.socket.connect',
                       'subprocess.run', 'subprocess.Popen', 'reminders.notify_macos'):
            guard = patch(target, side_effect=AssertionError('Forbidden side effect: ' + target))
            guard.start()
            self.addCleanup(guard.stop)

    def assert_secret_read_refused(self, relative_path, content, secrets, request_id):
        target = self.home / relative_path
        target.write_text(content)
        command = 'read file ~/' + relative_path
        reply = self.actions.handle(command, 'chat', request_id, self.state)
        self.assertEqual(reply, SECRET_REFUSAL)
        persisted = (self.actions.folder / 'receipts.json').read_text()
        rows = json.loads(persisted)
        receipt, = (row for row in rows.values() if row['request_id'] == request_id)
        self.assertEqual(receipt['receipt'], SECRET_REFUSAL)
        for secret in secrets:
            self.assertNotIn(secret, reply)
            self.assertNotIn(secret, persisted)
        for operation in (lambda: safe_read(content.encode('utf-8')),
                          lambda: self.files.execute(dict(kind='read', path=str(target)))):
            with self.assertRaises(LocalTaskError) as raised:
                operation()
            self.assertEqual(str(raised.exception), SECRET_REFUSAL)
        restored = LocalTasks(self.root / 'state', files=self.files,
                              search=self.search, clock=self.clock)
        self.assertEqual(restored.handle(command, 'chat', request_id, self.state), SECRET_REFUSAL)
        self.assertEqual(target.read_text(), content)
        self.search.assert_not_called()

    def test_ledger_F9_calendar_read_bypasses_hold(self):
        from calendar_actions import CalendarActions, GoogleCalendar
        client = Mock(spec=GoogleCalendar)
        client.configured.return_value = None
        client.listing.return_value = {'items': []}
        actions = CalendarActions(self.root / 'state', client=client, clock=self.clock)
        chat_intent.apply_turn(self.state, 'Hold all work', 'hold')
        scopes = chat_intent.blocked_scopes(self.state, chat_intent.projects('show my calendar today'))
        self.assertTrue(scopes)
        self.assertEqual(actions.handle('show my calendar today', 'chat', 'F9', self.state),
                         chat_intent.hold_reply(scopes))
        client.configured.assert_not_called()
        client.listing.assert_not_called()
        client.create.assert_not_called()

    def test_ledger_F22_qualification_allpass_false_despite_scoped_pass(self):
        import hashlib
        from release import qualification_scope as scope

        def evidence(name, value):
            path = self.root / name
            path.write_text(json.dumps(value))
            return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())

        admission = evidence('admission.json', dict(id='F22', adopted=True))
        steer = evidence('steer.json', dict(authority_source='Owner defers live voice.',
                                           limits_unchanged=True, clock_unchanged=True))
        ref = evidence('scope.json', dict(schema=1, continuation_id='F22', scope_name='nonvoice',
                                         deferred_checks=scope.DEFERRED,
                                         admission=admission, owner_steer=steer))
        self.assertEqual(scope.validate(ref), ref)
        groups = ('webchat', 'services', 'reviews', 'release', 'bridge-contract', 'eval',
                  'browser', 'media-browser', 'voice-js', 'instinct-browser',
                  'remaining-browser', 'cold-browser', 'startup-recovery-browser',
                  'voice-availability-browser', 'jobs-results-browser', 'memory-removal-browser',
                  'project-handoffs-browser', 'reply-lifecycle-browser', 'test_job_results_js',
                  'test_quiet_hours_js', 'test_startup_recovery')
        for attempt in ('attempt-0001', 'attempt-0002'):
            with self.subTest(attempt=attempt):
                results = {name: dict(exit=0, skipped=0) for name in groups}
                included_pass = all(r['exit'] == 0 and r['skipped'] == 0 for r in results.values())
                record = dict(sha='899c2a5fc5f5', results=results, staging=dict(all_pass=True),
                              **scope.outcome(included_pass, ref))
                path = self.root / attempt / 'checks.json'
                path.parent.mkdir()
                path.write_text(json.dumps(record))
                loaded = json.loads(path.read_text())
                self.assertEqual(len(loaded['results']), 21)
                self.assertTrue(loaded['staging']['all_pass'])
                self.assertFalse(loaded['all_pass'])
                self.assertTrue(loaded['scope_passed'])
                self.assertEqual(loaded['live_voice'], scope.VOICE)
                self.assertTrue(scope.historical_passed(loaded))
                self.assertFalse(scope.passed(loaded))
                self.assertFalse(scope.passed(loaded, dict(ref, sha256='0' * 64)))
                self.assertEqual(loaded.get('qualification_status'), 'SCOPED_PASS')

        for bad_receipt in (dict(exit=1, skipped=0), dict(exit=0, skipped=1)):
            with self.subTest(receipt=bad_receipt):
                results['webchat'] = bad_receipt
                failed = scope.outcome(all(r['exit'] == 0 and r['skipped'] == 0
                                          for r in results.values()), ref)
                self.assertEqual(failed['qualification_status'], 'FAIL')
                self.assertFalse(failed['all_pass'])
                self.assertFalse(failed['scope_passed'])
                self.assertFalse(scope.historical_passed(failed))
        self.assertEqual(scope.outcome(True, None), dict(all_pass=True))
        self.assertEqual(scope.outcome(False, None), dict(all_pass=False))
        Path(steer['path']).write_text('{}')
        with self.assertRaisesRegex(RuntimeError, 'evidence changed'):
            scope.historical_passed(loaded)

    def test_ledger_A1L6_legacy_remind_me_bypasses_hold(self):
        import copy
        import uuid
        from app import Chat
        from reminders import ZONE
        from task_dispatch import task_queue

        commands = (
            'remind me in 10 minutes to check the oven',
            'remind me to call Sam on 2026-10-01 at 14:00',
            'remind me every 2 hours to stretch',
        )
        for index, (hold, scope) in enumerate((('Hold all work', 'new work'),
                                               ('Hold Web Bob', 'Web Bob'))):
            for number, command in enumerate(commands):
                with self.subTest(hold=hold, command=command):
                    root = self.root / f'A1L6-{index}-{number}'
                    providers, texting, calendar = Mock(), Mock(), Mock()
                    providers.timeouts = {}
                    providers.reply.side_effect = AssertionError('Unexpected provider call')
                    texting.handle.return_value = False
                    texting.public.side_effect = dict
                    calendar.handle.return_value = None
                    with patch('app.load_live_ops', return_value={}):
                        chat = Chat(root / 'webchat', root, providers, texting=texting,
                                    calendar=calendar, local_tasks=self.actions)
                        self.addCleanup(chat.close)
                        chat.reminders.clock = lambda: datetime(2026, 9, 29, 9, tzinfo=ZONE).timestamp()
                        cid = chat.conversation_list()['conversations'][0]['id']
                        chat.submit(cid, hold, str(uuid.uuid4()))
                        before = copy.deepcopy(chat.get(cid)['intent_state'])
                        self.assertEqual(chat_intent.blocked_scopes(before, chat_intent.projects(command)),
                                         [scope])
                        with patch.object(chat.reminders, 'create', wraps=chat.reminders.create) as create:
                            result = chat.submit(cid, command, str(uuid.uuid4()))
                            self.assertEqual(result['messages'][-1]['content'],
                                             chat_intent.hold_reply([scope]))
                            create.assert_not_called()
                        self.assertEqual(chat.reminders.listing(), [])
                        self.assertEqual(chat.get(cid)['intent_state'], before)
                        self.assertEqual(task_queue.tasks(root), {})
                        providers.reply.assert_not_called()

    def test_ledger_F10_reminder_ignores_wait_for_approval_phrasing(self):
        from reminders import Reminders, ReminderError, ZONE, parse
        now = datetime(2026, 10, 10, 1, 47, tzinfo=ZONE).timestamp()
        refusal = 'Nothing was saved. Send a new reminder request when you want it scheduled.'
        for index, command in enumerate((
                'Set a reminder for 2am to go to bed, but wait for my approval before saving it',
                'Set a timer for 10 minutes to stretch, but ask for confirmation before setting it')):
            with self.subTest(command=command):
                folder = self.root / ('F10-' + str(index))
                reminders = Reminders(folder, clock=lambda: now)
                with patch.object(reminders, 'save', wraps=reminders.save) as save:
                    self.assertEqual(reminders.handle(command, 'chat', 'request'), refusal)
                    save.assert_not_called()
                with self.assertRaises(ReminderError) as raised:
                    parse(command, now)
                self.assertEqual(str(raised.exception), refusal)
                self.assertEqual(Reminders(folder, clock=lambda: now).listing(), [])

    def test_ledger_F10r6_reminder_ignores_get_my_approval_first_and_pending_confirmation(self):
        from reminders import Reminders, ReminderError, ZONE, parse
        now = datetime(2026, 10, 10, 1, 47, tzinfo=ZONE).timestamp()
        refusal = 'Nothing was saved. Send a new reminder request when you want it scheduled.'
        for index, constraint in enumerate(('get my approval first', 'pending my confirmation.')):
            with self.subTest(constraint=constraint):
                command = 'Create a reminder for 2am to go to bed, but ' + constraint
                reminders = Reminders(self.root / ('F10r6-' + str(index)), clock=lambda: now)
                rows = []
                with patch.object(reminders, 'locked', side_effect=lambda: nullcontext(rows)), \
                        patch.object(reminders, 'save') as save:
                    self.assertEqual(reminders.handle(command, 'chat', 'request'), refusal)
                    save.assert_not_called()
                    self.assertEqual(reminders.listing(), [])
                with self.assertRaises(ReminderError) as raised:
                    parse(command, now)
                self.assertEqual(str(raised.exception), refusal)

    def test_ledger_F10r6r7_reminder_ignores_only_after_my_approval_and_do_not_execute_yet(self):
        from reminders import Reminders, ReminderError, ZONE, parse
        now = datetime(2026, 10, 10, 1, 47, tzinfo=ZONE).timestamp()
        refusal = 'Nothing was saved. Send a new reminder request when you want it scheduled.'
        for index, constraint in enumerate(('only after my approval', 'do not execute this yet.')):
            with self.subTest(constraint=constraint):
                command = 'Create a reminder for 2am to go to bed, but ' + constraint
                reminders = Reminders(self.root / ('F10r6r7-' + str(index)), clock=lambda: now)
                rows = []
                with patch.object(reminders, 'locked', side_effect=lambda: nullcontext(rows)), \
                        patch.object(reminders, 'save') as save:
                    self.assertEqual(reminders.handle(command, 'chat', 'request'), refusal)
                    save.assert_not_called()
                    self.assertEqual(reminders.listing(), [])
                with self.assertRaises(ReminderError) as raised:
                    parse(command, now)
                self.assertEqual(str(raised.exception), refusal)

    def test_ledger_F11_file_create_ignores_confirm_constraint(self):
        from local_tasks import parse
        command = 'create file ~/Documents/new.txt: hello\nDo not create this file until I confirm.'
        target = self.home / 'Documents/new.txt'
        refusal = 'No file changed. Send a new file request when you want it performed.'
        with patch.object(self.files, 'prepare', wraps=self.files.prepare) as prepare, \
                patch.object(self.files, 'execute', wraps=self.files.execute) as execute:
            reply = self.actions.handle(command, 'chat', 'F11', self.state)
            self.assertFalse(target.exists())
            self.assertEqual(reply, refusal)
            prepare.assert_not_called()
            execute.assert_not_called()
        with self.assertRaises(LocalTaskError) as raised:
            parse(command)
        self.assertEqual(str(raised.exception), refusal)
        with self.actions.locked() as rows:
            self.assertEqual(rows, {})
        self.search.assert_not_called()

    def test_ledger_F11r6_file_create_ignores_only_if_confirm_and_ask_me_phrasings(self):
        from local_tasks import parse
        refusal = 'No file changed. Send a new file request when you want it performed.'
        for index, constraint in enumerate(('only if I confirm.', 'ask me before saving it.',
                                             'do not actually create it.')):
            with self.subTest(constraint=constraint):
                command = 'create file ~/Documents/review-note.txt: hello, but ' + constraint
                target = self.home / 'Documents/review-note.txt'
                files = Mock(spec=LocalFiles)
                files.prepare.side_effect = lambda spec: spec
                files.execute.return_value = 'File created: ' + str(target)
                actions = LocalTasks(self.root / ('F11r6-' + str(index)), files=files,
                                     search=self.search, clock=self.clock)
                with patch.object(actions, 'save') as save:
                    reply = actions.handle(command, 'chat', 'request', self.state)
                    self.assertEqual(reply, refusal)
                    files.prepare.assert_not_called()
                    files.execute.assert_not_called()
                    save.assert_not_called()
                self.assertFalse(target.exists())
                with self.assertRaises(LocalTaskError) as raised:
                    parse(command)
                self.assertEqual(str(raised.exception), refusal)
                with actions.locked() as rows:
                    self.assertEqual(rows, {})
        self.search.assert_not_called()

    def test_ledger_F11r6r7_file_create_ignores_get_my_approval_and_do_not_execute_yet(self):
        from local_tasks import parse
        refusal = 'No file changed. Send a new file request when you want it performed.'
        for index, constraint in enumerate(('get my approval first.', 'only after my approval.',
                                             'do not execute this yet.')):
            with self.subTest(constraint=constraint):
                command = 'create file ~/Documents/review-note.txt: hello, but ' + constraint
                target = self.home / 'Documents/review-note.txt'
                files = Mock(spec=LocalFiles)
                files.prepare.side_effect = lambda spec: spec
                files.execute.return_value = 'File created: ' + str(target)
                actions = LocalTasks(self.root / ('F11r6r7-' + str(index)), files=files,
                                     search=self.search, clock=self.clock)
                with patch.object(actions, 'save') as save:
                    reply = actions.handle(command, 'chat', 'request', self.state)
                    self.assertEqual(reply, refusal)
                    files.prepare.assert_not_called()
                    files.execute.assert_not_called()
                    save.assert_not_called()
                self.assertFalse(target.exists())
                with self.assertRaises(LocalTaskError) as raised:
                    parse(command)
                self.assertEqual(str(raised.exception), refusal)
                with actions.locked() as rows:
                    self.assertEqual(rows, {})
        self.search.assert_not_called()

    def test_ledger_F12_reminder_ignores_do_not_save_yet(self):
        from reminders import Reminders, ReminderError, ZONE, parse
        now = datetime(2026, 10, 10, 1, 47, tzinfo=ZONE).timestamp()
        refusal = 'Nothing was saved. Send a new reminder request when you want it scheduled.'
        for index, constraint in enumerate(('do not save it yet', 'ask me before saving it')):
            with self.subTest(constraint=constraint):
                command = 'Create a reminder for 2am to go to bed, but ' + constraint
                folder = self.root / ('F12-' + str(index))
                reminders = Reminders(folder, clock=lambda: now)
                with patch.object(reminders, 'save', wraps=reminders.save) as save:
                    self.assertEqual(reminders.handle(command, 'chat', 'request'), refusal)
                    save.assert_not_called()
                with self.assertRaises(ReminderError) as raised:
                    parse(command, now)
                self.assertEqual(str(raised.exception), refusal)
                self.assertEqual(Reminders(folder, clock=lambda: now).listing(), [])

    def test_ledger_F13_reminder_ignores_only_if_i_confirm(self):
        from reminders import Reminders, ReminderError, ZONE, parse
        now = datetime(2026, 10, 10, 10, 0, tzinfo=ZONE).timestamp()
        command = 'set a timer for 10 minutes to stretch, but only if I confirm'
        refusal = 'Nothing was saved. Send a new reminder request when you want it scheduled.'
        folder = self.root / 'F13'
        reminders = Reminders(folder, clock=lambda: now)
        with patch.object(reminders, 'save', wraps=reminders.save) as save:
            self.assertEqual(reminders.handle(command, 'chat', 'request'), refusal)
            save.assert_not_called()
        with self.assertRaises(ReminderError) as raised:
            parse(command, now)
        self.assertEqual(str(raised.exception), refusal)
        self.assertEqual(Reminders(folder, clock=lambda: now).listing(), [])

    def test_ledger_F14_reminder_ignores_ask_for_my_confirmation(self):
        from reminders import Reminders, ReminderError, ZONE, parse
        now = datetime(2026, 10, 10, 1, 47, tzinfo=ZONE).timestamp()
        refusal = 'Nothing was saved. Send a new reminder request when you want it scheduled.'
        for index, command in enumerate((
                'Create a reminder for 2am to go to bed, but first ask for my confirmation.',
                'Create a reminder for 2am to go to bed, but only if I say go.',
                'Create a reminder for 2am to go to bed, do not actually schedule anything.')):
            with self.subTest(command=command):
                folder = self.root / ('F14-' + str(index))
                reminders = Reminders(folder, clock=lambda: now)
                with patch.object(reminders, 'save', wraps=reminders.save) as save:
                    self.assertEqual(reminders.handle(command, 'chat', 'request'), refusal)
                    save.assert_not_called()
                with self.assertRaises(ReminderError) as raised:
                    parse(command, now)
                self.assertEqual(str(raised.exception), refusal)
                self.assertEqual(Reminders(folder, clock=lambda: now).listing(), [])

    def test_ledger_F15_trailing_date_qualifier_swallowed(self):
        from reminders import Reminders, ReminderError, ZONE, parse, reminder_body
        now = datetime(2026, 10, 10, 1, 47, tzinfo=ZONE).timestamp()
        refusal = ('The reminder has an extra date or time clause. Nothing was saved. '
                   'Please use one schedule, such as “create a reminder for tomorrow at 2am to go to bed”.')
        for index, (command, body) in enumerate((
                ('create a reminder for 2am to go to bed tomorrow', 'go to bed tomorrow'),
                ('create a reminder to go to bed at 2am tomorrow at 3am', 'go to bed at 2am'))):
            with self.subTest(command=command):
                folder = self.root / ('F15-' + str(index))
                reminders = Reminders(folder, clock=lambda: now)
                with patch.object(reminders, 'save', wraps=reminders.save) as save:
                    self.assertEqual(reminders.handle(command, 'chat', 'request'), refusal)
                    save.assert_not_called()
                for operation in (lambda: parse(command, now), lambda: reminder_body(body)):
                    with self.assertRaises(ReminderError) as raised:
                        operation()
                    self.assertEqual(str(raised.exception), refusal)
                self.assertEqual(Reminders(folder, clock=lambda: now).listing(), [])

    def test_ledger_F15r6_named_month_and_slash_date_swallowed(self):
        from reminders import Reminders, ReminderError, ZONE, parse, reminder_body
        now = datetime(2026, 10, 10, 1, 47, tzinfo=ZONE).timestamp()
        refusal = ('The reminder has an extra date or time clause. Nothing was saved. '
                   'Please use one schedule, such as “create a reminder for tomorrow at 2am to go to bed”.')
        intent_refusal = 'Nothing was saved. Send a new reminder request when you want it scheduled.'
        for index, date in enumerate(('October 11', '10/11')):
            with self.subTest(date=date):
                body = 'go to bed on ' + date
                command = 'Create a reminder for 2am to ' + body
                reminders = Reminders(self.root / ('F15r6-' + str(index)), clock=lambda: now)
                rows = []
                with patch.object(reminders, 'locked', side_effect=lambda: nullcontext(rows)), \
                        patch.object(reminders, 'save') as save:
                    self.assertEqual(reminders.handle(command, 'chat', 'request'), intent_refusal)
                    save.assert_not_called()
                    self.assertEqual(reminders.listing(), [])
                for operation, expected in ((lambda: parse(command, now), intent_refusal),
                                            (lambda: reminder_body(body), refusal)):
                    with self.assertRaises(ReminderError) as raised:
                        operation()
                    self.assertEqual(str(raised.exception), expected)

    def test_ledger_F15r6r7_abbreviated_and_day_first_month_date_swallowed(self):
        from reminders import Reminders, ReminderError, ZONE, parse, reminder_body
        now = datetime(2026, 10, 10, 1, 47, tzinfo=ZONE).timestamp()
        refusal = ('The reminder has an extra date or time clause. Nothing was saved. '
                   'Please use one schedule, such as “create a reminder for tomorrow at 2am to go to bed”.')
        clause_refusal = ('Nothing was saved. Send a new reminder request when you want it scheduled.')
        for index, date in enumerate(('Oct 11', '11 October.')):
            with self.subTest(date=date):
                body = 'go to bed, on ' + date
                command = 'Create a reminder for 2am to ' + body
                reminders = Reminders(self.root / ('F15r6r7-' + str(index)), clock=lambda: now)
                rows = []
                with patch.object(reminders, 'locked', side_effect=lambda: nullcontext(rows)), \
                        patch.object(reminders, 'save') as save:
                    self.assertEqual(reminders.handle(command, 'chat', 'request'), clause_refusal)
                    save.assert_not_called()
                    self.assertEqual(reminders.listing(), [])
                # The full request now stops at the earlier clause guard;
                # direct body validation must still reject the extra date.
                for operation, expected in ((lambda: parse(command, now), clause_refusal),
                                            (lambda: reminder_body(body), refusal)):
                    with self.assertRaises(ReminderError) as raised:
                        operation()
                    self.assertEqual(str(raised.exception), expected)

    def test_ledger_F16_trailing_timezone_qualifier_swallowed(self):
        from reminders import Reminders, ReminderError, ZONE, parse
        now = datetime(2026, 10, 10, 1, 47, tzinfo=ZONE).timestamp()
        command = 'Create a reminder for 2am to go to bed PST'
        refusal = ('The reminder timezone needs clarification. Nothing was saved. '
                   'Use America/Chicago local clock times without a timezone qualifier, '
                   'or an ISO date/time with an explicit UTC offset.')
        folder = self.root / 'F16'
        reminders = Reminders(folder, clock=lambda: now)
        with patch.object(reminders, 'save', wraps=reminders.save) as save:
            self.assertEqual(reminders.handle(command, 'chat', 'request'), refusal)
            save.assert_not_called()
        with self.assertRaises(ReminderError) as raised:
            parse(command, now)
        self.assertEqual(str(raised.exception), refusal)
        self.assertEqual(Reminders(folder, clock=lambda: now).listing(), [])

    def test_ledger_F17_recurring_reminder_skips_extra_date_check(self):
        from reminders import Reminders, ReminderError, ZONE, parse
        now = datetime(2026, 10, 10, 10, 0, tzinfo=ZONE).timestamp()
        command = 'create a reminder every 2 hours to stretch starting tomorrow'
        refusal = ('The reminder has an extra date or time clause. Nothing was saved. '
                   'Please use one schedule, such as “create a reminder for tomorrow at 2am to go to bed”.')
        folder = self.root / 'F17'
        reminders = Reminders(folder, clock=lambda: now)
        with patch.object(reminders, 'save', wraps=reminders.save) as save:
            self.assertEqual(reminders.handle(command, 'chat', 'request'), refusal)
            save.assert_not_called()
        with self.assertRaises(ReminderError) as raised:
            parse(command, now)
        self.assertEqual(str(raised.exception), refusal)
        self.assertEqual(Reminders(folder, clock=lambda: now).listing(), [])

    def test_ledger_F18_morning_routine_skips_extra_date_check(self):
        from reminders import Reminders, ReminderError, ZONE, parse
        now = datetime(2026, 10, 10, 1, 47, tzinfo=ZONE).timestamp()
        command = 'every morning remind me to stretch tomorrow'
        refusal = ('The reminder has an extra date or time clause. Nothing was saved. '
                   'Please use one schedule, such as “create a reminder for tomorrow at 2am to go to bed”.')
        folder = self.root / 'F18'
        reminders = Reminders(folder, clock=lambda: now)
        with patch.object(reminders, 'save', wraps=reminders.save) as save:
            self.assertEqual(reminders.handle(command, 'chat', 'request'), refusal)
            save.assert_not_called()
        with self.assertRaises(ReminderError) as raised:
            parse(command, now)
        self.assertEqual(str(raised.exception), refusal)
        self.assertEqual(Reminders(folder, clock=lambda: now).listing(), [])

    def test_ledger_F19_reminder_save_oserror_no_receipt(self):
        from reminders import Reminders, ReminderError
        folder = self.root / 'F19'
        reminders = Reminders(folder, clock=self.clock)
        refusal = 'Reminder storage failed. The requested change was not saved.'
        with patch.object(reminders, 'save', side_effect=OSError('disk full')) as save:
            draft = reminders.handle('set a timer for 10 minutes', 'chat', 'request')
            receipt = confirm_reply(self, draft, lambda text: reminders.handle(text, 'chat', 'confirmed'))
            self.assertEqual(receipt, refusal)
            save.assert_called_once()
            attempted, = save.call_args.args[0]
            self.assertEqual(attempted['body'], 'Timer')
            self.assertEqual(attempted['due_at'], self.clock() + 600)
            with self.assertRaises(ReminderError) as raised:
                reminders.create('chat', 'request', 'Timer', self.clock() + 600)
            self.assertEqual(str(raised.exception), refusal)
        self.assertEqual(Reminders(folder, clock=self.clock).listing(), [])

    def test_ledger_F20_default_notifier_fires_live_notification(self):
        from app import Chat
        from reminders import notify_macos
        from task_dispatch import task_queue
        from texting_fixture import OfflineProviders
        providers = OfflineProviders()
        providers.start_probes = Mock()
        providers.circuit = Mock()
        texting, calendar = Mock(), Mock()
        texting.public.side_effect = dict
        with patch('reminders.sys.platform', 'darwin'), patch('subprocess.run') as run:
            chat = Chat(self.root / 'F20', self.root, providers, texting=texting,
                        calendar=calendar, local_tasks=self.actions)
            self.addCleanup(chat.close)
            try:
                cid = chat.conversation_list()['conversations'][0]['id']
                draft = chat.reminders.handle('set a timer for 1 second', cid, 'request')
                receipt = confirm_reply(self, draft, lambda text: chat.reminders.handle(text, cid, 'confirmed'))
                self.assertIn('Reminder saved:', receipt)
                row, = chat.reminders.listing()
                self.assertEqual(row['state'], 'pending')
                chat.start_background()
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    if chat.reminders.listing()[0]['state'] == 'fired':
                        break
                    time.sleep(.05)
            finally:
                chat.close()
            self.assertFalse(chat.queue_thread.is_alive())
            fired, = chat.reminders.listing()
            self.assertEqual(fired['state'], 'fired')
            self.assertEqual(fired['occurrences'], 1)
            notices = [m for m in chat.history(cid)['messages'] if m.get('reminder_notice')]
            self.assertEqual(len(notices), 1)
            self.assertEqual(notices[0]['reminder_id'], row['id'])
            self.assertIn('Reminder: Timer', notices[0]['content'])
            run.assert_not_called()
            notify_macos.assert_not_called()
            self.assertIs(chat.reminder_notifier('Timer'), False)
            self.assertEqual(providers.calls, [])
            self.assertEqual(task_queue.tasks(self.root), {})
            self.assertEqual(calendar.mock_calls, [])
            self.search.assert_not_called()

    def test_ledger_F21_local_lock_has_no_timeout(self):
        refusal = 'Local receipt storage is busy; no action ran. Try again later.'
        self.assertEqual(LOCK_TIMEOUT, 1)
        self.actions.folder.mkdir(parents=True)
        with patch.object(self.files, 'prepare') as prepare, \
                patch.object(self.files, 'execute') as execute, \
                patch.object(self.actions, 'save') as save:
            for entry in ('locked', 'handle'):
                with self.subTest(entry=entry), (self.actions.folder / 'receipts.lock').open('a') as lock:
                    # An independent descriptor holds the real lock. Release it
                    # after the deadline so a blocking-flock regression fails
                    # instead of hanging the suite indefinitely.
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    watchdog = threading.Timer(3, fcntl.flock, args=(lock, fcntl.LOCK_UN))
                    watchdog.start()
                    try:
                        started = time.monotonic()
                        if entry == 'locked':
                            with self.assertRaises(LocalTaskError) as raised:
                                with self.actions.locked():
                                    self.fail('Contended receipt lock was acquired')
                            self.assertEqual(str(raised.exception), refusal)
                        else:
                            self.assertEqual(self.actions.handle(
                                'terminal: pwd', 'chat', 'request', self.state), refusal)
                        elapsed = time.monotonic() - started
                        self.assertGreaterEqual(elapsed, LOCK_TIMEOUT)
                        # Allow polling and scheduler overhead around the 1s limit.
                        self.assertLess(elapsed, LOCK_TIMEOUT + .5)
                    finally:
                        watchdog.cancel()
                        watchdog.join()
                    prepare.assert_not_called()
                    execute.assert_not_called()
                    save.assert_not_called()
                    self.assertFalse((self.actions.folder / 'receipts.json').exists())
        with self.actions.locked() as rows:
            self.assertEqual(rows, {})
        self.search.assert_not_called()

    def test_ledger_F8_generation_budget_file_writable_via_chat(self):
        runtime = self.home / 'Documents/bob-runtime'
        folder = runtime / 'conductor/webchat'
        accounting = self.root / 'accounting'
        policy = runtime / 'conductor/state/generation-policy.json'
        budget = runtime / 'conductor/state/generation-budgets/owner.json'
        budget.parent.mkdir(parents=True)
        originals = {
            policy: json.dumps(dict(budget_id='owner', purpose='product', accounting_root=str(accounting))),
            budget: json.dumps(dict(limit=1)),
        }
        for target, content in originals.items():
            target.write_text(content)
        refusal = 'Web Bob storage is outside the local file allowlist.'
        with patch('pathlib.Path.home', return_value=self.home), patch.dict(
                os.environ, HOME=str(self.home), BOB_ROOT=str(runtime),
                BOB_GENERATION_BUDGET_ROOT=str(accounting), BOB_GOOGLE_CALENDAR_CREDENTIALS=''):
            actions = self.production_actions(folder)
            self.assertIn(runtime, actions.protected_paths())
            for index, (target, original) in enumerate(originals.items()):
                with self.subTest(path=target):
                    command = f'write file {target}: {{"limit":999999}}'
                    self.assertEqual(actions.handle(command, 'chat', f'F8-direct-{index}', self.state),
                                     refusal)
                    with self.assertRaises(LocalTaskError) as raised:
                        actions.files.parts(str(target))
                    self.assertEqual(str(raised.exception), refusal)

                    # A pre-protection draft must also be refused after restart.
                    legacy = LocalTasks(folder, files=self.files, search=self.search, clock=self.clock)
                    self.assertIn('Local draft', legacy.handle(
                        command, 'chat', f'F8-legacy-{index}', self.state))
                    with legacy.locked() as rows:
                        row, = (r for r in rows.values() if r['state'] == 'draft')
                    restored = self.production_actions(folder)
                    self.assertEqual(restored.handle('yes ' + row['token'], 'chat',
                                                     f'F8-confirm-{index}', self.state), refusal)
                    self.assertEqual(target.read_text(), original)
            self.search.assert_not_called()

    def test_ledger_F1_pgpassword_assignment_bypasses_secret_filter(self):
        secret = 'SYNTHETIC_SECRET_1006'
        for index, content in enumerate(('export PGPASSWORD=' + secret + '\n',
                                         'DBPASSWORD=' + secret,
                                         'Login: Jeff\nPassword ' + secret)):
            with self.subTest(content=content):
                self.assert_secret_read_refused('Documents/note.txt', content, (secret,), f'F1-{index}')

    def test_ledger_F2_generic_json_secret_fields_bypass_path_filter(self):
        password = 'synthetic-owner-password-123'
        refresh_token = 'synthetic-refresh-token-123'
        content = json.dumps(dict(password=password, refresh_token=refresh_token))
        self.assert_secret_read_refused('Documents/export.json', content,
                                        (password, refresh_token), 'F2')

    def test_ledger_F3_csv_xml_credential_content_disclosed(self):
        secret = 'synthetic-review-password'
        for extension, content in (
                ('csv', 'name,url,username,password\nExample,https://example.test,jeff,' + secret),
                ('xml', '<credentials><password>' + secret + '</password></credentials>')):
            with self.subTest(extension=extension):
                self.assert_secret_read_refused('Downloads/export.' + extension, content,
                                                (secret,), 'F3-' + extension)

    def test_ledger_F3r6_xml_plist_keyvalue_credential_disclosed(self):
        secret = 'synthetic-review-secret'
        for index, key in enumerate(('password', 'refresh_token', 'api_key')):
            with self.subTest(key=key):
                content = ('<?xml version="1.0"?><plist version="1.0"><dict><key>' + key +
                           '</key><string>' + secret + '</string></dict></plist>')
                # Keep the real prepare/execute/safe_read path while supplying
                # file bytes through the adapter's mocked read boundary.
                with patch.object(self.files, 'snapshot', return_value=({}, content.encode('utf-8'))):
                    self.assert_secret_read_refused('Documents/export.plist', content,
                                                    (secret,), 'F3r6-' + str(index))
        ordinary = '<plist><dict><key>title</key><string>Review note</string></dict></plist>'
        self.assertEqual(safe_read(ordinary.encode('utf-8')), ordinary)

    def test_ledger_F3r6r7_xml_attribute_labelled_credential_disclosed(self):
        secret = 'synthetic-review-secret'
        contents = (
            '<?xml version="1.0"?><properties><entry key="password">' + secret + '</entry></properties>',
            '<config><add key="password" value="' + secret + '" /></config>',
        )
        for index, content in enumerate(contents):
            with self.subTest(content=content):
                # Exercise real prepare/execute/safe_read with mocked file reads.
                with patch.object(self.files, 'snapshot', return_value=({}, content.encode('utf-8'))):
                    self.assert_secret_read_refused('Documents/export.xml', content,
                                                    (secret,), 'F3r6r7-' + str(index))
        ordinary = '<config><add key="title" value="Review note" /></config>'
        self.assertEqual(safe_read(ordinary.encode('utf-8')), ordinary)

    def test_ledger_F4_netrc_credential_record_disclosed(self):
        secret = 'SYNTHETIC-ONLY'
        content = 'machine example.invalid login alice password ' + secret
        self.assert_secret_read_refused('Documents/export.txt', content, (secret, content), 'F4')

    def test_ledger_F5_pgp_private_key_block_armor_disclosed(self):
        secret = 'synthetic-armored-key-data'
        content = ('-----BEGIN PGP PRIVATE KEY BLOCK-----\n' + secret +
                   '\n-----END PGP PRIVATE KEY BLOCK-----')
        self.assert_secret_read_refused('Documents/backup.asc', content,
                                        (secret, '-----BEGIN PGP PRIVATE KEY BLOCK-----', content), 'F5')

    def production_actions(self, folder):
        from local_task_worker import run
        actions = LocalTasks(folder, search=self.search, clock=self.clock)

        # Mock process creation while running the actual production worker boundary.
        def worker(method, args, kwargs):
            return run(dict(folder=str(folder), root=str(actions.root), home=str(self.home),
                            now=self.clock(), method=method, args=args, kwargs=kwargs))

        guard = patch.object(actions, 'file_worker', side_effect=worker)
        guard.start()
        self.addCleanup(guard.stop)
        return actions

    def test_ledger_F6_calendar_credential_path_outside_protected_roots(self):
        from reminders import Reminders
        runtime = self.home / 'Documents/bob-runtime'
        folder = runtime / 'conductor/webchat'
        target = self.home / 'Documents/google-calendar.json'
        command = 'read file ~/Documents/google-calendar.json'
        refusal = 'Web Bob storage is outside the local file allowlist.'
        content = json.dumps(dict(type='authorized_user', client_id='synthetic-client',
                                 client_secret='synthetic-client-secret',
                                 refresh_token='synthetic-refresh-token'))
        with patch('pathlib.Path.home', return_value=self.home), patch.dict(
                os.environ, HOME=str(self.home), BOB_ROOT=str(runtime),
                BOB_GENERATION_BUDGET_ROOT=str(self.root / 'accounting'),
                BOB_GOOGLE_CALENDAR_CREDENTIALS=''):
            actions = self.production_actions(folder)
            target.write_text('ordinary calendar notes')
            target.chmod(0o600)
            self.assertIn('Local draft', actions.handle(
                'write file ~/Documents/google-calendar.json: x', 'chat', 'F6-draft', self.state))
            with actions.locked() as rows:
                token, = rows
            reminders = Reminders(folder, clock=self.clock)
            draft = reminders.handle('every morning do ' + command, 'chat', 'F6-save-routine', local_tasks=actions)
            receipt = confirm_reply(self, draft, lambda text: reminders.handle(
                text, 'chat', 'F6-confirm-routine', local_tasks=actions))
            self.assertIn('Read-only routine saved:', receipt)
            target.write_text(content)
            with patch.dict(os.environ, BOB_GOOGLE_CALENDAR_CREDENTIALS='~/Documents/google-calendar.json'):
                restored = self.production_actions(folder)
                self.assertIn(target, restored.protected_paths())
                for index, text in enumerate((command, 'write file ~/Documents/google-calendar.json: x',
                                              'yes ' + token)):
                    self.assertEqual(restored.handle(text, 'chat', f'F6-{index}', self.state), refusal)
                with self.assertRaises(LocalTaskError) as raised:
                    restored.validate_routine(command)
                self.assertEqual(str(raised.exception), refusal)
                routine, = Reminders(folder, clock=self.clock).listing()
                self.assertEqual(routine['action'], command)
                self.assertEqual(restored.handle(routine['action'], 'chat', 'F6-routine',
                                                 self.state, routine=True), refusal)
            self.assertEqual(target.read_text(), content)
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            persisted = (actions.folder / 'receipts.json').read_text()
            for secret in ('synthetic-client-secret', 'synthetic-refresh-token', content):
                self.assertNotIn(secret, persisted)
            self.search.assert_not_called()

    def test_ledger_F7_write_delete_missing_credential_content_guard(self):
        target = self.home / 'Documents/auth.json'
        secret = 'synthetic-review-password'
        content = json.dumps(dict(password=secret))
        target.write_text(content)
        for kind in ('write', 'delete'):
            with self.subTest(kind=kind):
                spec = dict(kind=kind, path=str(target))
                suffix = ': erased' if kind == 'write' else ''
                if kind == 'write':
                    spec['content'] = 'erased'
                command = kind + ' file ~/Documents/auth.json' + suffix
                with self.assertRaises(LocalTaskError) as raised:
                    self.files.prepare(spec)
                self.assertEqual(str(raised.exception), SECRET_REFUSAL)
                self.assertEqual(self.actions.handle(command, 'chat', 'F7-direct-' + kind,
                                                     self.state), SECRET_REFUSAL)

                # Seed a pre-fix draft with the exact current file fingerprint;
                # consent must still recheck content, not just reject a stale file.
                with patch('local_tasks.safe_read', return_value=''):
                    self.assertIn('Local draft', self.actions.handle(
                        command, 'chat', 'F7-legacy-' + kind, self.state))
                with self.actions.locked() as rows:
                    row, = (r for r in rows.values() if r['state'] == 'draft')
                with patch('local_tasks.os.dup') as duplicate, \
                        patch('local_tasks.os.ftruncate') as truncate, \
                        patch('local_tasks.os.unlink') as unlink:
                    with self.assertRaises(LocalTaskError) as raised:
                        self.files.execute(row['spec'])
                    self.assertEqual(str(raised.exception), SECRET_REFUSAL)
                    restored = LocalTasks(self.root / 'state', files=self.files,
                                          search=self.search, clock=self.clock)
                    for attempt in range(2):
                        self.assertEqual(restored.handle('yes ' + row['token'], 'chat',
                                                         f'F7-confirm-{kind}-{attempt}', self.state),
                                         SECRET_REFUSAL)
                    duplicate.assert_not_called()
                    truncate.assert_not_called()
                    unlink.assert_not_called()
                self.assertEqual(target.read_text(), content)
                self.assertNotIn(secret, (self.actions.folder / 'receipts.json').read_text())
        self.search.assert_not_called()


if __name__ == '__main__':
    unittest.main()
