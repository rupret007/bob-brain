"""Read-only queue snapshots and writer-owned crash repair, using private journals."""
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'state'))
import task_queue as queue


class QueueReadTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = self.root / 'conductor/state/queue.jsonl'

    def enqueue(self, request='one'):
        return queue.enqueue(self.root, 'private-conversation', request, 'Explain a private fixture cloud.')

    def test_empty_read_creates_no_directories_or_lock(self):
        self.assertEqual(queue.tasks(self.root), {})
        self.assertEqual(list(self.root.iterdir()), [])

    def test_torn_tail_is_observed_without_truncation_then_repaired_by_writer(self):
        row = self.enqueue()
        committed = self.path.read_bytes()
        self.path.write_bytes(committed + b'{"id":')
        before = self.path.read_bytes()
        self.assertEqual(queue.tasks(self.root), {row['id']: row})
        self.assertEqual(self.path.read_bytes(), before)
        next_row = self.enqueue('two')
        self.assertEqual(set(queue.tasks(self.root)), {row['id'], next_row['id']})
        self.assertTrue(self.path.read_bytes().startswith(committed))
        self.assertEqual(len(self.path.read_bytes().splitlines()), 2)

    def test_missing_newline_is_preserved_by_read_and_separated_by_writer(self):
        row = self.enqueue()
        self.path.write_bytes(self.path.read_bytes().rstrip(b'\n'))
        before = self.path.read_bytes()
        self.assertEqual(queue.tasks(self.root), {row['id']: row})
        self.assertEqual(self.path.read_bytes(), before)
        second = self.enqueue('two')
        self.assertEqual(set(queue.tasks(self.root)), {row['id'], second['id']})
        self.assertTrue(self.path.read_bytes().startswith(before + b'\n'))

    def test_legacy_journal_without_lock_remains_byte_identical(self):
        row = self.enqueue()
        lock = self.path.with_name('.queue.lock')
        lock.unlink()  # Fixture has no writer; only simulate an old imported journal.
        before = self.path.read_bytes()
        self.assertEqual(queue.tasks(self.root), {row['id']: row})
        self.assertEqual(self.path.read_bytes(), before)
        self.assertFalse(lock.exists())

    def test_read_only_files_and_directory_support_inspection(self):
        row = self.enqueue()
        lock = self.path.with_name('.queue.lock')
        self.path.chmod(0o400)
        lock.chmod(0o400)
        self.path.parent.chmod(0o500)
        try:
            self.assertEqual(queue.tasks(self.root), {row['id']: row})
        finally:
            self.path.parent.chmod(0o700)
            self.path.chmod(0o600)
            lock.chmod(0o600)

    def test_committed_corruption_fails_without_modifying_bytes(self):
        self.enqueue()
        for data in (b'broken\n', b'broken\n' + self.path.read_bytes(), b'[]\n', b'{}\n'):
            with self.subTest(data=data[:10]):
                self.path.write_bytes(data)
                with self.assertRaises(ValueError):
                    queue.tasks(self.root)
                self.assertEqual(self.path.read_bytes(), data)

    def test_reader_waits_for_writer_and_writer_death_releases_lock(self):
        row = self.enqueue()
        script = '''
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import task_queue as queue
with queue.locked(Path(sys.argv[2])) as path:
    with path.open('ab') as handle:
        handle.write(b'{"id":')
        handle.flush()
    print('locked', flush=True)
    sys.stdin.read()
'''
        process = subprocess.Popen([sys.executable, '-c', script,
            str(Path(queue.__file__).parent), str(self.root)], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        result, errors = [], []
        entered, finished = threading.Event(), threading.Event()
        def read():
            entered.set()
            try:
                result.append(queue.tasks(self.root))
            except Exception as exc:
                errors.append(type(exc).__name__)
            finally:
                finished.set()
        reader = threading.Thread(target=read, daemon=True)
        try:
            self.assertEqual(process.stdout.readline().strip(), 'locked')
            reader.start()
            self.assertTrue(entered.wait(2))
            self.assertFalse(finished.wait(.1))
            process.kill()  # Private synthetic writer; never an application service.
            process.wait(timeout=3)
            self.assertTrue(finished.wait(3))
            self.assertEqual(errors, [])
            self.assertEqual(result, [{row['id']: row}])
            self.assertTrue(self.path.read_bytes().endswith(b'{"id":'))
            self.enqueue('two')
            self.assertEqual(len(queue.tasks(self.root)), 2)
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=3)
            if reader.ident:
                reader.join(3)
