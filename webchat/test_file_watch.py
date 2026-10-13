"""File-watch notices: fake clock/file adapter, no OS watcher or model calls."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import uuid

from app import Chat
import chat_intent
from file_watch import CHANGED, CHECK_INTERVAL, FileWatch, MISSING, NEED_FILE, UNAVAILABLE, parse
from local_tasks import LocalFiles, LocalTaskError, SECRET_REFUSAL
from texting import Texting
from texting_fixture import OfflineProviders


class FakeFiles:
    def __init__(self):
        self.snapshots = {}
        self.calls = []

    def observe(self, path):
        self.calls.append(path)
        value = self.snapshots[path]
        if isinstance(value, Exception):
            raise value
        return copy.deepcopy(value)

    def fingerprint(self, digest, **extra):
        row = dict(device=1, inode=1, modified=1, size=4, digest=digest)
        row.update(extra)
        return row


class WatchFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.now = 1_000_000.0
        self.files = FakeFiles()
        self.watch = FileWatch(self.root / 'chat', self.files, clock=lambda: self.now)
        self.state = chat_intent.new_state()
        self.network = patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('Network forbidden'))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.popen = patch('subprocess.Popen', side_effect=AssertionError('Process spawn forbidden'))
        self.popen.start()
        self.addCleanup(self.popen.stop)

    def say(self, text, cid='chat', rid=None):
        return self.watch.handle(text, cid, rid or str(uuid.uuid4()), self.state)

    def register(self, path='~/Documents/note.txt', digest='aaaa'):
        self.files.snapshots[path] = self.files.fingerprint(digest)
        reply = self.say('watch file ' + path)
        self.assertIn('File watch registered', reply)
        self.assertIn('no notice was posted', reply.lower())
        return reply

    def notices(self):
        delivered = []
        def deliver(row, notice, content):
            delivered.append((row['id'], notice, content, copy.deepcopy(row.get('path'))))
            return True
        self.watch.poll(deliver)
        return delivered


class FileWatchTests(WatchFixture):
    def test_baseline_on_registration_does_not_notify(self):
        self.register()
        self.assertEqual(self.notices(), [])
        self.assertEqual(self.files.calls, ['~/Documents/note.txt'])

    def test_change_posts_one_notice_without_file_body(self):
        self.register(digest='base')
        self.files.snapshots['~/Documents/note.txt'] = self.files.fingerprint('changed')
        self.now += CHECK_INTERVAL
        first = self.notices()
        self.assertEqual(len(first), 1)
        self.assertEqual(first[0][2], CHANGED.format(path='~/Documents/note.txt'))
        self.assertNotIn('secret-body', first[0][2])
        self.assertNotIn('File read:', first[0][2])
        self.now += CHECK_INTERVAL
        self.assertEqual(self.notices(), [])

    def test_unchanged_file_is_silent(self):
        self.register(digest='same')
        self.now += CHECK_INTERVAL
        self.assertEqual(self.notices(), [])

    def test_restart_keeps_baseline_and_pending_notice(self):
        self.register(digest='base')
        self.files.snapshots['~/Documents/note.txt'] = self.files.fingerprint('later')
        self.now += CHECK_INTERVAL
        pending = []
        self.watch.poll(lambda *_: pending.append(1) or False)
        self.assertTrue(pending)
        restored = FileWatch(self.root / 'chat', self.files, clock=lambda: self.now)
        delivered = []
        restored.poll(lambda row, notice, content: delivered.append(content) or True)
        self.assertEqual(delivered, [CHANGED.format(path='~/Documents/note.txt')])
        restored.poll(lambda *_: delivered.append('dup') or True)
        self.assertEqual(delivered, [CHANGED.format(path='~/Documents/note.txt')])

    def test_failed_notice_persists_with_stable_id(self):
        self.register(digest='base')
        self.files.snapshots['~/Documents/note.txt'] = self.files.fingerprint('new')
        self.now += CHECK_INTERVAL
        first, second = [], []
        self.watch.poll(lambda row, notice, content: first.append(notice) or False)
        self.watch.poll(lambda row, notice, content: second.append(notice) or True)
        self.assertEqual(first, second)
        self.watch.poll(lambda *_: self.fail('already delivered'))

    def test_cancellation_stops_later_changes(self):
        reply = self.register(digest='base')
        identifier = reply.split('ID ', 1)[1].split('.', 1)[0]
        self.assertIn('cancelled', self.say('cancel file watch ' + identifier))
        self.files.snapshots['~/Documents/note.txt'] = self.files.fingerprint('after-cancel')
        self.now += CHECK_INTERVAL
        self.assertEqual(self.notices(), [])
        self.assertIn('No active file watches', self.say('list file watches'))

    def test_deleted_or_replaced_file_notifies_without_content(self):
        self.register(digest='base')
        self.files.snapshots['~/Documents/note.txt'] = FileNotFoundError('gone')
        self.now += CHECK_INTERVAL
        missing = self.notices()
        self.assertEqual(missing[0][2], MISSING.format(path='~/Documents/note.txt'))
        self.files.snapshots['~/Documents/note.txt'] = LocalTaskError('symlink refused')
        self.now += CHECK_INTERVAL
        again = self.notices()
        self.assertEqual(again[0][2], MISSING.format(path='~/Documents/note.txt'))
        self.assertNotIn('symlink', again[0][2])

    def test_saved_hold_blocks_notice_and_is_not_lifted(self):
        self.register(digest='base')
        chat_intent.apply_turn(self.state, 'Hold all work', 'hold')
        before = copy.deepcopy(self.state)
        self.files.snapshots['~/Documents/note.txt'] = self.files.fingerprint('held')
        self.now += CHECK_INTERVAL
        delivered = []
        self.watch.poll(lambda *_: delivered.append(1) or True,
                        intent_state_for=lambda _cid: self.state)
        self.assertEqual(delivered, [])
        self.assertEqual(self.state, before)
        with self.watch.locked() as state:
            row = next(iter(state['watches'].values()))
            self.assertIsNotNone(row['pending_notice'])

    def test_burst_coalesces_to_one_notice(self):
        self.register(digest='0')
        for digest in ('1', '2', '3', '4'):
            self.files.snapshots['~/Documents/note.txt'] = self.files.fingerprint(digest)
        self.now += CHECK_INTERVAL
        notices = self.notices()
        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0][2], CHANGED.format(path='~/Documents/note.txt'))

    def test_once_per_minute_skips_observe(self):
        self.register(digest='base')
        self.files.calls.clear()
        self.files.snapshots['~/Documents/note.txt'] = self.files.fingerprint('early')
        self.now += CHECK_INTERVAL - 1
        self.assertEqual(self.notices(), [])
        self.assertEqual(self.files.calls, [])
        self.now += 1
        self.assertEqual(len(self.notices()), 1)

    def test_injection_and_unrelated_requests_are_rejected_or_ignored(self):
        self.assertEqual(self.say('watch file ~/Documents/note.txt; rm -rf /'), NEED_FILE)
        self.assertIsNone(parse('read file ~/Documents/note.txt'))
        self.assertIsNone(parse('review the draft PR'))
        self.assertIsNone(parse('push WebJam'))
        self.assertFalse(self.files.calls)


class RealPathRefusalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / 'home'
        self.home.mkdir()
        (self.home / 'Documents').mkdir()
        self.file = self.home / 'Documents/note.txt'
        self.file.write_text('visible-body-must-not-appear')
        self.files = LocalFiles(self.home)
        self.watch = FileWatch(Path(self.tmp.name) / 'state', self.files, clock=lambda: 10)
        self.state = chat_intent.new_state()

    def test_symlink_and_secret_path_are_refused(self):
        outside = Path(self.tmp.name) / 'outside'
        outside.write_text('secret')
        (self.home / 'link').symlink_to(outside)
        (self.home / 'Documents/credentials.txt').write_text('nope')
        for path in ('~/link', str(outside), '~/Documents/credentials.txt', '~/.ssh/id_rsa'):
            reply = self.watch.handle('watch file ' + path, 'chat', str(uuid.uuid4()), self.state)
            self.assertNotIn('registered', reply.lower())
            self.assertTrue(
                SECRET_REFUSAL in reply or 'allowlist' in reply or UNAVAILABLE in reply
                or 'home directory' in reply or 'Private' in reply or 'No watch was saved' in reply,
                reply)

    def test_observe_returns_fingerprint_not_bytes(self):
        snapshot = self.files.observe('~/Documents/note.txt')
        self.assertIn('digest', snapshot)
        self.assertNotIn(b'visible-body-must-not-appear', snapshot.values())
        self.assertNotIn('visible-body-must-not-appear', snapshot.values())


class ChatRoutingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.now = 2_000_000.0
        self.files = FakeFiles()
        self.watch = FileWatch(self.root / 'chat', self.files, clock=lambda: self.now)
        self.chat = Chat(self.root / 'chat', self.root, OfflineProviders(),
                         texting=Texting(Mock(), Mock()), reminder_notifier=Mock(),
                         calendar=Mock(handle=Mock(return_value=None)), file_watch=self.watch)
        self.addCleanup(self.chat.close)
        self.cid = self.chat.new_conversation()['id']

    def submit(self, text):
        with patch('app.parse_work', side_effect=AssertionError('Entered generic queue')):
            return self.chat.submit(self.cid, text, str(uuid.uuid4()), actor='owner')['messages'][-1]

    def test_register_change_and_hold_through_chat(self):
        path = '~/Documents/inbox.txt'
        self.files.snapshots[path] = self.files.fingerprint('one')
        reply = self.submit('notify this chat when ' + path + ' changes')
        self.assertEqual(reply['provider'], 'file-watch')
        self.assertIn('Baseline fingerprint recorded', reply['content'])
        self.files.snapshots[path] = self.files.fingerprint('two')
        self.now += CHECK_INTERVAL
        self.chat.deliver_file_watches()
        notice = self.chat.history(self.cid)['messages'][-1]
        self.assertEqual(notice['provider'], 'file-watch')
        self.assertIn('Watched file changed', notice['content'])
        self.assertTrue(notice.get('file_watch_notice'))
        self.chat.submit(self.cid, 'Hold all work', str(uuid.uuid4()))
        before = copy.deepcopy(self.chat.get(self.cid)['intent_state'])
        self.files.snapshots[path] = self.files.fingerprint('three')
        self.now += CHECK_INTERVAL
        self.chat.deliver_file_watches()
        self.assertEqual(self.chat.get(self.cid)['intent_state'], before)
        notices = [m for m in self.chat.history(self.cid)['messages'] if m.get('file_watch_notice')]
        self.assertEqual([m['file_watch_notice'] for m in notices], [notice['file_watch_notice']])


if __name__ == '__main__':
    unittest.main()
