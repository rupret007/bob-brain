"""Capability ledger regressions using a temporary home and offline adapters."""
import json
from contextlib import nullcontext
from datetime import datetime
import fcntl
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

import chat_intent
from local_tasks import LocalFiles, LocalTasks, LocalTaskError, LOCK_TIMEOUT, SECRET_REFUSAL, safe_read


class CapabilityLedgerTests(unittest.TestCase):
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
            self.assertEqual(reminders.handle('set a timer for 10 minutes', 'chat', 'request'),
                             refusal)
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
                self.assertIn('Reminder saved:', chat.reminders.handle(
                    'set a timer for 1 second', cid, 'request'))
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
            self.assertIn('Read-only routine saved:', reminders.handle(
                'every morning do ' + command, 'chat', 'F6-save-routine', local_tasks=actions))
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
