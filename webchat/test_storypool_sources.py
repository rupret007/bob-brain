"""Real status paths, bounded current evidence and unsafe-source refusal."""
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

from shared_chat import SharedChatContext, engine_snapshot, _stamp
from storypool_sources import status_sources


class StoryPoolSourcesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.now = time.time()

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.write_text(text)
        path.chmod(0o664)
        return path

    def test_direct_sources_work_without_prepared_chat_copies(self):
        self.write('MONITOR.md', 'old status\n' * 10000 + 'CURRENT: worker pushed verified fix\n')
        self.write('NEEDS_JEFF.md', 'Jeff approval needed\n')
        self.write('PARITY.md', 'Coverage: 12/20\n')
        self.write('conductor/digest-2026-10-18-am.md', 'Morning summary\n')
        digest = self.write('conductor/digest-2026-10-18-pm.md', 'Evening summary\n')
        old = self.now - 3600
        os.utime(digest, (old, old))
        context = SharedChatContext(self.root / 'chat', source_folder=self.root,
                                    clock=lambda: self.now)
        rows = {row['source']: row for row in context.snapshot(include_engines=False)['sources']}
        self.assertIn('CURRENT: worker pushed verified fix', rows['MONITOR.md']['text'])
        self.assertLessEqual(len(rows['MONITOR.md']['text']), 4000)
        self.assertTrue(rows['MONITOR.md']['truncated'])
        self.assertIn('Jeff approval needed', rows['NEEDS_JEFF.md']['text'])
        self.assertEqual(rows['MORNING_DIGEST.md']['text'], 'Evening summary\n')
        self.assertEqual(rows['MORNING_DIGEST.md']['source_path'], 'conductor/digest-2026-10-18-pm.md')
        self.assertEqual(rows['MORNING_DIGEST.md']['freshness'], 'stale')
        self.assertEqual(rows['Mini chat/HANDOFF.md']['state'], 'unavailable')
        self.assertTrue(all(row['execution_authority'] is False for row in rows.values() if 'execution_authority' in row))

    def test_symlink_secret_and_world_writable_sources_are_unavailable(self):
        target = self.write('target', 'private content\n')
        (self.root / 'MONITOR.md').symlink_to(target)
        self.write('NEEDS_JEFF.md', 'secret=do-not-expose\n')
        self.write('PARITY.md', 'unsafe source').chmod(0o666)
        self.write('conductor/digest-2026-10-18-pm.md', 'private digest').unlink()
        (self.root / 'conductor/digest-2026-10-18-pm.md').symlink_to(target)
        rows = status_sources(self.root, self.now)
        self.assertTrue(all(row['state'] == 'unavailable' for row in rows))
        self.assertNotIn('private', json.dumps(rows))
        self.assertNotIn('do-not-expose', json.dumps(rows))

    def test_stale_copy_cannot_mask_unsafe_direct_source(self):
        chat = self.root / 'chat'
        chat.mkdir(mode=0o700)
        copy = chat / 'MONITOR.md'
        copy.write_text('Old copy says everything green')
        copy.chmod(0o600)
        self.write('MONITOR.md', 'Unsafe canonical source').chmod(0o666)
        context = SharedChatContext(chat, source_folder=self.root)
        row = context.snapshot(include_engines=False)['sources'][0]
        self.assertEqual(row['state'], 'unavailable')
        self.assertNotIn('text', row)

    def test_missing_canonical_file_uses_dated_verified_sync_copy(self):
        chat = self.root / 'chat'
        chat.mkdir(mode=0o700)
        copy = chat / 'MONITOR.md'
        copy.write_text('NucBox dated observation')
        copy.chmod(0o600)
        old = self.now - 3600
        os.utime(copy, (old, old))
        context = SharedChatContext(chat, source_folder=self.root, clock=lambda: self.now)
        row = context.snapshot(include_engines=False)['sources'][0]
        self.assertEqual(row['state'], 'observed')
        self.assertEqual(row['text'], 'NucBox dated observation')
        self.assertEqual(row['freshness'], 'stale')
        self.assertEqual(row['observed_at'], _stamp(old))
        self.assertIn('synced source copy; canonical local source absent', row['provenance'])
        self.assertEqual(row['source_path'], 'chat/MONITOR.md')

    def test_missing_canonical_file_does_not_accept_unsafe_sync_copy(self):
        chat = self.root / 'chat'
        chat.mkdir(mode=0o700)
        copy = chat / 'MONITOR.md'
        copy.write_text('Public copy is not a verified sync source')
        copy.chmod(0o644)
        context = SharedChatContext(chat, source_folder=self.root)
        row = context.snapshot(include_engines=False)['sources'][0]
        self.assertEqual(row['state'], 'unavailable')
        self.assertNotIn('text', row)

    def test_freshness_uses_fetch_completion_time_for_new_engine_snapshot(self):
        clock = iter([100, 102, 104])
        times = iter([101, 103])
        context = SharedChatContext(self.root / 'chat', clock=lambda: next(clock),
            fetch_engine=lambda _: (json.dumps({'timestamp': _stamp(next(times))}), False))
        rows = context.snapshot()['sources'][-2:]
        self.assertEqual([row['freshness'] for row in rows], ['fresh', 'fresh'])
        self.assertEqual([row['fetched_at'] for row in rows], [_stamp(102), _stamp(104)])

    def test_nucbox_still_uses_fixed_read_only_transport(self):
        connection = MagicMock()
        connection.getresponse.return_value.status = 200
        connection.getresponse.return_value.read.return_value = b'{"timestamp":"2026-10-18T21:00:00Z","engine":{},"private":"excluded"}'
        with patch('shared_chat.http.client.HTTPConnection', return_value=connection) as connect:
            text, clipped = engine_snapshot('nucbox')
        connect.assert_called_once_with('100.93.165.1', 8790, timeout=1)
        connection.request.assert_called_once_with('GET', '/api/engine', headers={'Accept': 'application/json'})
        self.assertFalse(clipped)
        self.assertNotIn('private', text)


if __name__ == '__main__':
    unittest.main()
