"""Capability ledger regressions using a temporary home and offline adapters."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import chat_intent
from local_tasks import LocalFiles, LocalTasks, LocalTaskError, SECRET_REFUSAL, safe_read


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

    def test_ledger_F1_pgpassword_assignment_bypasses_secret_filter(self):
        secret = 'SYNTHETIC_SECRET_1006'
        for index, content in enumerate(('export PGPASSWORD=' + secret + '\n',
                                         'DBPASSWORD=' + secret,
                                         'Login: Jeff\nPassword ' + secret)):
            with self.subTest(content=content):
                self.assert_secret_read_refused('Documents/note.txt', content, (secret,), f'F1-{index}')


if __name__ == '__main__':
    unittest.main()
