"""Bounded terminal head/wc/df: fixture home only, no shell or extra binaries."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import uuid

from app import Chat
import chat_intent
from local_tasks import (
    HEAD_BYTES, HEAD_LINES, LIMIT, LocalFiles, LocalTaskError, LocalTasks, SECRET_REFUSAL,
    TIMED_OUT, parse,
)
from reminders import ZONE
from texting import Texting
from texting_fixture import OfflineProviders


class InspectFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = self.root / 'home'
        self.home.mkdir()
        (self.home / 'Documents').mkdir()
        self.file = self.home / 'Documents/note.txt'
        self.file.write_text('one two\nthree\n')
        self.files = LocalFiles(self.home)
        self.actions = LocalTasks(self.root / 'state', self.files, Mock(side_effect=AssertionError('search')),
                                 clock=lambda: 1)
        self.state = chat_intent.new_state()
        for target in ('urllib.request.OpenerDirector.open', 'subprocess.run', 'subprocess.Popen',
                       'reminders.notify_macos'):
            guard = patch(target, side_effect=AssertionError('Forbidden real side-effect: ' + target))
            guard.start()
            self.addCleanup(guard.stop)

    def say(self, text):
        return self.actions.handle(text, 'chat', str(uuid.uuid4()), self.state)


class TerminalInspectTests(InspectFixture):
    def test_head_and_wc_caps_and_structured_receipts(self):
        lines = [f'line-{i} extra words' for i in range(HEAD_LINES + 5)]
        self.file.write_text('\n'.join(lines) + '\n')
        head = self.say('terminal: head ~/Documents/note.txt')
        self.assertIn('Terminal head', head)
        self.assertIn('path=', head)
        self.assertIn('1: line-0 extra words', head)
        self.assertIn(f'{HEAD_LINES}: line-{HEAD_LINES - 1} extra words', head)
        self.assertNotIn(f'line-{HEAD_LINES} extra', head)
        self.assertIn('truncated=true', head)
        wc = self.say('terminal: wc ~/Documents/note.txt')
        self.assertIn('Terminal wc', wc)
        self.assertIn('lines=25', wc)
        self.assertIn('truncated=false', wc)
        self.assertIn('binary=false', wc)
        self.file.write_bytes(b'x' * (HEAD_BYTES + 20))
        big = self.say('terminal: head ~/Documents/note.txt')
        self.assertIn('truncated=true', big)
        self.assertLessEqual(len(big.encode()), HEAD_BYTES + 400)

    def test_empty_and_binary_input(self):
        self.file.write_text('')
        empty_head = self.say('terminal: head ~/Documents/note.txt')
        self.assertIn('empty=true', empty_head)
        empty_wc = self.say('terminal: wc ~/Documents/note.txt')
        self.assertIn('lines=0', empty_wc)
        self.assertIn('bytes=0', empty_wc)
        self.file.write_bytes(b'hello\x00world')
        binary = self.say('terminal: head ~/Documents/note.txt')
        self.assertIn('binary=true', binary)
        self.assertNotIn('hello', binary)
        wc = self.say('terminal: wc ~/Documents/note.txt')
        self.assertIn('binary=true', wc)
        self.assertIn('bytes=11', wc)
        self.assertIn('lines=0', wc)

    def test_paths_with_spaces(self):
        path = self.home / 'Documents/my file.txt'
        path.write_text('spaced\n')
        self.assertIn('1: spaced', self.say('terminal: head "~/Documents/my file.txt"'))
        self.assertIn('words=1', self.say('terminal: wc "~/Documents/my file.txt"'))
        disk = self.say('terminal: df "~/Documents/my file.txt"')
        self.assertIn('Terminal disk free', disk)
        self.assertIn('free_bytes=', disk)
        self.assertIn('total_bytes=', disk)
        self.assertNotIn('File read:', disk)

    def test_secret_files_are_refused(self):
        secret = self.home / 'Documents/credentials.txt'
        secret.write_text('password = synthetic-secret')
        for command in ('terminal: head ~/Documents/credentials.txt',
                        'terminal: wc ~/Documents/credentials.txt',
                        'terminal: df ~/Documents/credentials.txt'):
            reply = self.say(command)
            self.assertIn(SECRET_REFUSAL.split('.')[0], reply)
            self.assertNotIn('synthetic-secret', reply)

    def test_symlinks_hardlinks_and_fifos_are_blocked(self):
        outside = self.root / 'outside'
        outside.write_text('secret')
        (self.home / 'link').symlink_to(outside)
        os.link(outside, self.home / 'Documents/hardlink.txt')
        os.mkfifo(self.home / 'Documents/pipe')
        for path in ('~/link', '~/Documents/hardlink.txt', '~/Documents/pipe'):
            for tool in ('head', 'wc', 'df'):
                reply = self.say(f'terminal: {tool} {path}')
                self.assertNotIn('1: secret', reply)
                self.assertNotIn('File read:', reply)
                self.assertNotIn('free_bytes=', reply)

    def test_holds_block_inspection(self):
        chat_intent.apply_turn(self.state, 'Hold all work', 'hold')
        before = dict(self.state)
        for command in ('terminal: head ~/Documents/note.txt', 'terminal: wc ~/Documents/note.txt',
                        'terminal: df ~/Documents'):
            self.assertIn('On hold:', self.say(command))
        self.assertEqual(self.state, before)

    def test_timeout_is_honest_and_does_not_launch_a_shell(self):
        with patch.object(self.files, 'inspect_read', side_effect=TimeoutError('slow')):
            reply = self.say('terminal: head ~/Documents/note.txt')
        self.assertEqual(reply, TIMED_OUT)
        self.assertNotIn('File read:', reply)

    def test_shell_metacharacters_flags_and_pipes_never_launch(self):
        for command in (
            'head ~/Documents/note.txt | wc',
            'head -n 5 ~/Documents/note.txt',
            'wc -l ~/Documents/note.txt',
            'df -h ~/Documents',
            'head ~/Documents/note.txt; rm -rf /',
            'wc $(pwd)/Documents/note.txt',
            'df ~/Documents && date',
            'head `id`',
            'wc ~/Documents/note.txt > out',
        ):
            with self.subTest(command=command):
                reply = self.say('terminal: ' + command)
                self.assertTrue('allowlist' in reply or 'home directory' in reply, reply)
        self.assertEqual(self.file.read_text(), 'one two\nthree\n')
        self.assertFalse((self.home / 'out').exists())

    def test_does_not_duplicate_pwd_date_ls_cat(self):
        self.assertEqual(parse('terminal: pwd'), dict(kind='pwd'))
        self.assertEqual(parse('terminal: date'), dict(kind='date'))
        self.assertEqual(parse('terminal: ls ~/Documents')['kind'], 'list')
        self.assertEqual(parse('terminal: cat ~/Documents/note.txt')['kind'], 'read')
        self.assertEqual(parse('terminal: head ~/Documents/note.txt')['kind'], 'head')
        self.assertEqual(parse('terminal: wc ~/Documents/note.txt')['kind'], 'wc')
        self.assertEqual(parse('terminal: df ~/Documents')['kind'], 'df')

    def test_df_uses_local_statvfs_not_df_binary(self):
        with patch('os.fstatvfs', wraps=os.fstatvfs) as statvfs:
            reply = self.say('terminal: df ~/Documents')
        self.assertIn('free_bytes=', reply)
        self.assertIn('total_bytes=', reply)
        statvfs.assert_called()


class InspectChatTests(InspectFixture):
    def test_direct_route_before_coding_queue(self):
        chat = Chat(self.root / 'chat', self.root, OfflineProviders(),
                    texting=Texting(Mock(), Mock()), reminder_notifier=Mock(),
                    calendar=Mock(handle=Mock(return_value=None)), local_tasks=self.actions)
        self.addCleanup(chat.close)
        cid = chat.new_conversation()['id']
        with patch('app.parse_work', side_effect=AssertionError('Entered generic queue')):
            reply = chat.submit(cid, 'terminal: head ~/Documents/note.txt', str(uuid.uuid4()),
                                actor='owner')['messages'][-1]
        self.assertEqual(reply['provider'], 'local-tasks')
        self.assertIn('1: one two', reply['content'])


if __name__ == '__main__':
    unittest.main()
