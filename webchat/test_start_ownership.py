"""Private startup/controller races; no real screen, HTTP, provider or service."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).with_name('start.py').resolve()
spec = importlib.util.spec_from_file_location('webbob_start_ownership', SOURCE)
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)
from release_ownership import controller
import activation_journal as journal


CHILD = '''
import importlib.util, os, subprocess, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location('private_start', sys.argv[1])
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)
launcher.HERE = Path(os.environ['BOB_ROOT']) / 'other code' / 'webchat'
launcher.HERE.mkdir(parents=True)
calls = 0
def health():
    global calls
    calls += 1
    if sys.argv[2] == 'readiness' and calls == 1:
        return False
    print('READY', flush=True)
    if sys.stdin.readline().strip() != 'finish':
        raise RuntimeError('Fixture input ended')
    return True
def screen(command, **kwargs):
    if command == ['/usr/bin/screen', '-ls']:
        return subprocess.CompletedProcess(command, 1, 'No Sockets found in /fixture.', '')
    expected = ['/usr/bin/screen', '-dmS', 'svc-webchat', '/bin/bash', str(launcher.HERE / 'run.sh')]
    if command != expected:
        raise RuntimeError('Unexpected fixture subprocess')
    return subprocess.CompletedProcess(command, 0, '', '')
launcher.healthy = health
launcher.subprocess.run = screen
raise SystemExit(launcher.main())
'''


class StartupOwnershipTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='webbob-start-ownership-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.here = self.root / 'selected code' / 'webchat'
        self.here.mkdir(parents=True)
        self.addCleanup(os.umask, os.umask(0o077))
        contexts = contextlib.ExitStack()
        self.addCleanup(contexts.close)
        self.output = contexts.enter_context(contextlib.redirect_stdout(io.StringIO()))
        contexts.enter_context(patch.dict(os.environ, {'BOB_ROOT': str(self.root)}, clear=True))
        contexts.enter_context(patch.object(launcher, 'HERE', self.here))
        self.health = contexts.enter_context(patch.object(launcher, 'healthy', return_value=True))
        self.run = contexts.enter_context(patch.object(launcher.subprocess, 'run'))
        self.journal_path = self.root / 'conductor/locks' / journal.NAME

    def assert_refused_before_probes(self):
        self.assertEqual(launcher.main(), 1)
        self.health.assert_not_called()
        self.run.assert_not_called()

    def create_pending(self):
        folder = self.root / 'rollback'
        record = dict(sha='a' * 40, previous='b' * 40, rollback=str(folder),
                      snapshots={k: str(folder / ('previous-' + k)) for k in ('webchat', 'dispatch')},
                      snapshot_hashes={k: 'c' * 64 for k in ('webchat', 'dispatch')},
                      original_pins={})
        return journal.begin(self.root, record, folder / 'release.json')

    def child(self, phase):
        process = subprocess.Popen([sys.executable, '-B', '-c', CHILD, str(SOURCE), phase],
                                   env=dict(os.environ), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True)
        def cleanup():
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=5)
        self.addCleanup(cleanup)
        ready, _, _ = select.select([process.stdout], [], [], 5)
        self.assertTrue(ready, 'Private startup fixture did not reach the held health probe')
        self.assertEqual(process.stdout.readline().strip(), 'READY')
        return process

    def test_pending_activation_blocks_even_healthy_startup_without_altering_evidence(self):
        self.create_pending()
        before = self.journal_path.read_bytes()
        self.assert_refused_before_probes()
        self.assertEqual(self.journal_path.read_bytes(), before)
        self.assertIn('explicit recovery', self.output.getvalue())

    def test_invalid_journal_remains_untouched_and_refuses(self):
        with controller(self.root):
            pass
        for raw in (b'{', b'[]', b'{"schema":1,"state":"pending","id":"bad"}',
                    json.dumps(dict(schema=1, state='pending',
                                    id='00000000-0000-0000-0000-000000000000')).encode()):
            with self.subTest(raw=raw):
                self.journal_path.write_bytes(raw)
                self.assert_refused_before_probes()
                self.assertEqual(self.journal_path.read_bytes(), raw)

    def test_dangling_journal_symlink_does_not_look_like_no_journal(self):
        with controller(self.root):
            pass
        target = self.root / 'missing-private-target'
        self.journal_path.symlink_to(target)
        self.assert_refused_before_probes()
        self.assertTrue(self.journal_path.is_symlink())
        self.assertFalse(target.exists())
        self.assertNotIn(str(target), self.output.getvalue())

    def test_nonregular_journal_refuses_without_blocking(self):
        with controller(self.root):
            pass
        os.mkfifo(self.journal_path, 0o600)
        before = self.journal_path.lstat()
        self.assert_refused_before_probes()
        self.assertEqual(self.journal_path.lstat().st_ino, before.st_ino)

    def test_unsafe_controller_inode_refuses_without_network_or_screen(self):
        with controller(self.root):
            pass
        path = self.journal_path.with_name('webbob-release.lock')
        path.chmod(0o644)
        self.assert_refused_before_probes()
        self.assertEqual(path.stat().st_mode & 0o777, 0o644)

    def test_replaced_lock_during_inventory_refuses_before_launch(self):
        self.health.return_value = False
        path = self.journal_path.with_name('webbob-release.lock')
        def inventory(command, **kwargs):
            path.rename(path.with_suffix('.old'))
            path.touch(mode=0o600)
            return subprocess.CompletedProcess(command, 1, 'No Sockets found in /fixture.', '')
        self.run.side_effect = inventory
        self.assertEqual(launcher.main(), 1)
        self.assertEqual(self.run.call_count, 1)
        self.assertEqual(self.run.call_args.args[0], ['/usr/bin/screen', '-ls'])

    def test_default_installation_root_uses_shared_lock(self):
        os.environ.pop('BOB_ROOT')
        here = self.root / 'conductor/webchat'
        here.mkdir(parents=True)
        with patch.object(launcher, 'HERE', here):
            self.assertEqual(launcher.main(), 0)
        self.assertTrue(self.journal_path.with_name('webbob-release.lock').is_file())
        self.run.assert_not_called()

    def test_controller_owned_by_other_process_blocks_start_before_probe(self):
        process = self.child('initial')
        self.assert_refused_before_probes()
        process.stdin.write('finish\n')
        process.stdin.flush()
        process.communicate(timeout=5)
        self.assertEqual(process.returncode, 0)
        self.assertEqual(launcher.main(), 0)

    def test_readiness_wait_excludes_other_code_roots_and_release_controllers(self):
        process = self.child('readiness')
        self.assert_refused_before_probes()
        with self.assertRaises(RuntimeError):
            with controller(self.root):
                self.fail('Release entered before startup readiness finished')
        process.stdin.write('finish\n')
        process.stdin.flush()
        process.communicate(timeout=5)
        self.assertEqual(process.returncode, 0)
        with controller(self.root):
            pass

    def test_killed_startup_releases_kernel_ownership_without_unlinking(self):
        process = self.child('readiness')
        path = self.journal_path.with_name('webbob-release.lock')
        before = path.stat().st_ino
        process.kill()
        process.communicate(timeout=5)
        self.assertEqual(launcher.main(), 0)
        self.assertEqual(path.stat().st_ino, before)
        self.assertFalse(self.journal_path.exists())


if __name__ == '__main__':
    unittest.main()
