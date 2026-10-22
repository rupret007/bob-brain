"""Exercise the fixed remote reader and the Mini's real synced-source path."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from shared_chat import MAX_SOURCE, MONITOR_EXCERPT, SharedChatContext, _stamp
from shared_chat_cli import NUCBOX_READ, sync_sources


class SharedSourceSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='webbob-source-sync-')
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name).resolve()
        self.state = self.home / '.local/share/storypool'
        self.state.mkdir(mode=0o700, parents=True)
        self.folder = self.home / 'mini-chat'
        self.now = time.time()

    def write(self, name, text):
        path = self.state / name
        path.write_text(text, encoding='utf-8')
        path.chmod(0o664)
        return path

    def remote_rows(self):
        # Execute exactly the program sent over SSH, against a fixture HOME.
        # No SSH, model, owner source file or messaging service is contacted.
        env = {key: value for key, value in os.environ.items()
               if not any(part in key.upper() for part in ('KEY', 'TOKEN', 'SECRET', 'PASSWORD'))}
        env['HOME'] = str(self.home)
        result = subprocess.run([sys.executable, '-I', '-c', NUCBOX_READ],
                                env=env, capture_output=True, check=True, timeout=5)
        self.assertLessEqual(len(result.stdout), 4 * MAX_SOURCE)
        return json.loads(result.stdout)

    def snapshot(self):
        context = SharedChatContext(self.folder, source_folder=self.home / 'absent-local-state',
                                    clock=lambda: self.now)
        return {row['source']: row for row in context.snapshot(include_engines=False)['sources']}

    def test_growing_remote_monitor_reaches_mini_with_newest_lines_and_original_date(self):
        text = 'HISTORICAL: old decision\n' * 5000 + 'CURRENT: M1 is the priority; wait for exact approval.\n'
        monitor = self.write('MONITOR.md', text)
        original = monitor.read_bytes()
        old = self.now - 3600
        os.utime(monitor, (old, old))
        rows = self.remote_rows()
        remote = next(row for row in rows if row['name'] == 'MONITOR.md')
        self.assertEqual(remote['state'], 'observed')
        self.assertLessEqual(len(remote['text'].encode('utf-8')), MAX_SOURCE)
        self.assertIn('CURRENT: M1', remote['text'])
        sync_sources(self.folder, rows)
        row = self.snapshot()['MONITOR.md']
        self.assertEqual(row['state'], 'observed')
        self.assertIn('CURRENT: M1', row['text'])
        self.assertLessEqual(len(row['text']), 4000)
        self.assertTrue(row['truncated'])
        self.assertEqual(row['observed_at'], _stamp(old))
        self.assertEqual(row['freshness'], 'stale')
        self.assertIn('synced source copy', row['provenance'])
        self.assertFalse(SharedChatContext(self.folder).snapshot(include_engines=False)['execution_authority'])
        self.assertFalse((self.folder / 'HANDOFF.md').exists())
        self.assertEqual(monitor.read_bytes(), original)
        self.assertEqual(monitor.stat().st_mtime, old)

    def test_small_synced_monitor_exposes_newest_utf8_lines_without_refreshing_mtime(self):
        old = self.now - 3600
        text = 'HISTORICAL: résumé 🎵\n' * 500 + 'CURRENT: newest result stays visible.\n'
        sync_sources(self.folder, [dict(name='MONITOR.md', state='observed', text=text, modified=old)])
        row = self.snapshot()['MONITOR.md']
        self.assertIn('CURRENT: newest result', row['text'])
        self.assertNotIn('\ufffd', row['text'])
        self.assertTrue(row['truncated'])
        self.assertEqual(row['freshness'], 'stale')
        self.assertEqual(row['observed_at'], _stamp(old))

    def test_short_remote_excerpt_still_identifies_omitted_history(self):
        self.write('MONITOR.md', 'x' * (MAX_SOURCE + 1) + '\nCURRENT: bounded complete line\n')
        rows = self.remote_rows()
        remote = rows[0]
        self.assertEqual(remote['state'], 'observed')
        self.assertTrue(remote['text'].startswith(MONITOR_EXCERPT))
        sync_sources(self.folder, rows)
        row = self.snapshot()['MONITOR.md']
        self.assertLess(len(row['text']), 4000)
        self.assertIn('CURRENT: bounded complete line', row['text'])
        self.assertTrue(row['truncated'])

    def test_remote_reader_refuses_links_public_files_and_oversized_nonlog_sources(self):
        target = self.write('target', 'must not enter synced observations\n')
        (self.state / 'MONITOR.md').symlink_to(target)
        self.write('NEEDS_JEFF.md', 'unsafe public source\n').chmod(0o666)
        self.write('PARITY.md', 'x' * (MAX_SOURCE + 1))
        rows = self.remote_rows()
        self.assertTrue(all(row['state'] == 'unavailable' for row in rows))
        self.assertNotIn('text', json.dumps(rows))
        (self.state / 'MONITOR.md').unlink()
        os.link(target, self.state / 'MONITOR.md')
        self.assertEqual(self.remote_rows()[0]['state'], 'unavailable')

    def test_remote_log_with_no_complete_bounded_line_is_unavailable(self):
        for ending in ('', '\n'):
            with self.subTest(ending=ending):
                self.write('MONITOR.md', 'x' * (MAX_SOURCE + 1) + ending)
                self.assertEqual(self.remote_rows()[0]['state'], 'unavailable')

    def test_copy_with_no_complete_bounded_line_is_unavailable(self):
        sync_sources(self.folder, [dict(name='MONITOR.md', state='observed',
            text='x' * 5000 + '\n', modified=self.now)])
        row = self.snapshot()['MONITOR.md']
        self.assertEqual(row['state'], 'unavailable')
        self.assertNotIn('text', row)


if __name__ == '__main__':
    unittest.main()
