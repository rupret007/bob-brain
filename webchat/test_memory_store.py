"""Private memory boundaries: links, bounded reads, durable failure and model context."""
import os
import fcntl
from pathlib import Path
import stat
import tempfile
import time
import unittest
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from unittest.mock import patch

from bob_gaps import append_profile_memory
from memory_store import MAX_BYTES, append_memory, read_memory
from providers import Providers


class MemoryStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / 'conductor/webchat/memory/profile.md'
        self.path.parent.mkdir(parents=True)
        self.outside = self.root / 'other-checkout'
        self.outside.mkdir()
        self.target = self.outside / 'profile.md'
        self.target.write_text('private outside fact\n')

    def test_repeated_same_date_fact_preserves_bytes_inode_and_modified_time(self):
        when = datetime(2026, 9, 29, 12, tzinfo=timezone.utc)
        saved = append_profile_memory(self.root, 'café preference', when)
        original = self.path.read_bytes()
        info = self.path.stat()
        with patch('memory_store.os.replace', side_effect=AssertionError('duplicate rewrite')):
            self.assertEqual(append_profile_memory(self.root, 'café preference', when), saved)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual((self.path.stat().st_ino, self.path.stat().st_mtime_ns),
                         (info.st_ino, info.st_mtime_ns))

    def test_only_exact_complete_dated_rows_are_duplicates(self):
        original = '[2026-09-28] coffee\n[2026-09-29] coffee beans\n[2026-09-29] Coffee\n'
        self.path.write_text(original)
        append_memory(self.root, '[2026-09-29] coffee\n')
        self.assertEqual(self.path.read_text(), original + '[2026-09-29] coffee\n')

    def test_multiline_facts_and_prefixes_are_not_silently_dropped(self):
        original = '[2026-09-29] coffee\nonly after lunch\n'
        self.path.write_text(original)
        append_memory(self.root, '[2026-09-29] coffee\n')
        append_memory(self.root, '[2026-09-29] coffee\nonly with breakfast\n')
        self.assertEqual(self.path.read_text(), original + '[2026-09-29] coffee\n' +
                         '[2026-09-29] coffee\nonly with breakfast\n')

    def test_duplicate_noop_preserves_existing_duplicates_and_oversized_history(self):
        line = '[2026-09-29] retained fact\n'
        original = ('[2026-09-28] old fact\n' * 30000 + line * 2).encode()
        self.path.write_bytes(original)
        append_memory(self.root, line)
        self.assertEqual(self.path.read_bytes(), original)

    def test_duplicate_save_still_restricts_legacy_file_permissions(self):
        line = '[2026-09-29] retained fact\n'
        self.path.write_text(line)
        self.path.chmod(0o644)
        append_memory(self.root, line)
        self.assertEqual(self.path.read_text(), line)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)

    def test_concurrent_duplicate_saves_across_processes_keep_one_copy(self):
        line = '[2026-09-29] simultaneous fact\n'
        with ProcessPoolExecutor(max_workers=4) as pool:
            list(pool.map(append_memory, [self.root] * 12, [line] * 12))
        self.assertEqual(self.path.read_text(), line)

    def test_unterminated_existing_note_keeps_its_own_line(self):
        self.path.write_text('[2026-09-28] previous fact')
        append_memory(self.root, '[2026-09-29] new fact\n')
        self.assertEqual(self.path.read_text(), '[2026-09-28] previous fact\n[2026-09-29] new fact\n')

    def test_profile_and_lock_symlinks_never_import_or_change_the_target(self):
        for name in ('profile.md', 'profile.lock'):
            with self.subTest(name=name):
                link = self.path.parent / name
                if link.exists():
                    link.unlink()
                link.symlink_to(self.target)
                with self.assertRaises(OSError):
                    append_profile_memory(self.root, 'new fact')
                self.assertEqual(self.target.read_text(), 'private outside fact\n')
                self.assertTrue(link.is_symlink())
                link.unlink()

    def test_symlink_memory_directory_never_writes_outside_overlay(self):
        self.path.parent.rmdir()
        self.path.parent.symlink_to(self.outside, target_is_directory=True)
        with self.assertRaises(OSError):
            append_profile_memory(self.root, 'new fact')
        with self.assertRaises(OSError):
            read_memory(self.root)
        self.assertEqual(list(self.outside.iterdir()), [self.target])
        self.assertEqual(self.target.read_text(), 'private outside fact\n')

    def test_fifo_and_hardlinked_memory_are_refused_without_blocking(self):
        os.mkfifo(self.path)
        with self.assertRaises(OSError):
            append_profile_memory(self.root, 'new fact')
        self.path.unlink()
        os.link(self.target, self.path)
        with self.assertRaises(OSError):
            read_memory(self.root)
        with self.assertRaises(OSError):
            append_profile_memory(self.root, 'new fact')
        self.assertEqual(self.target.read_text(), 'private outside fact\n')

    def test_profile_and_directory_permissions_are_private(self):
        self.path.parent.chmod(0o755)
        append_profile_memory(self.root, 'ordinary fact')
        self.assertEqual(stat.S_IMODE(self.path.parent.stat().st_mode), 0o700)
        for path in (self.path, self.path.parent / 'profile.lock'):
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_oversized_read_is_bounded_and_keeps_whole_recent_utf8_facts(self):
        self.path.write_text('old fact\n' * 100000 + 'newest café\n')
        value = read_memory(self.root, budget=40)
        self.assertTrue(value['truncated'])
        self.assertTrue(value['text'].endswith('newest café\n'))
        self.assertLessEqual(len(value['text'].encode()), 40)
        append_profile_memory(self.root, 'new confirmed fact')
        self.assertLessEqual(self.path.stat().st_size, MAX_BYTES)
        self.assertIn('newest café', self.path.read_text())

    def test_atomic_replace_failure_preserves_existing_memory_and_removes_temp(self):
        self.path.write_text('previous fact\n')
        with patch('memory_store.os.replace', side_effect=OSError('fixture disk failure')):
            with self.assertRaises(OSError):
                append_profile_memory(self.root, 'new fact')
        self.assertEqual(self.path.read_text(), 'previous fact\n')
        self.assertFalse(list(self.path.parent.glob('.profile-*')))

    def test_model_snapshots_never_read_a_linked_private_overlay(self):
        self.path.symlink_to(self.target)
        providers = Providers(self.root, lambda text: text)
        for lite in (True, False):
            parts = providers.snapshot(lite=lite)
            row = next(r for r in parts if r['path'] == 'conductor/webchat/memory/profile.md')
            self.assertTrue(row['unavailable'])
            self.assertNotIn('private outside fact', str(parts))

    def test_invalid_utf8_is_unavailable_in_model_context(self):
        self.path.write_bytes(b'\xff\xfe')
        providers = Providers(self.root, lambda text: text)
        row = next(r for r in providers.snapshot(lite=True) if r['path'] == 'conductor/webchat/memory/profile.md')
        self.assertTrue(row['unavailable'])

    def test_busy_memory_lock_is_bounded_and_does_not_change_memory(self):
        self.path.write_text('previous fact\n')
        with (self.path.parent / 'profile.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            started = time.monotonic()
            with patch('memory_store.LOCK_SECONDS', .03):
                with self.assertRaisesRegex(OSError, 'busy'):
                    append_profile_memory(self.root, 'new fact')
            self.assertLess(time.monotonic() - started, .5)
            self.assertEqual(self.path.read_text(), 'previous fact\n')

    def test_negative_budget_cannot_trigger_an_unbounded_read(self):
        self.path.write_text('previous fact\n')
        with self.assertRaises(OSError):
            read_memory(self.root, -1)
