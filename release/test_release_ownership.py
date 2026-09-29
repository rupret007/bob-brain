"""Private release races: no production service, model, or transport is used."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

import solo
from release_ownership import controller


class ReleaseOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.state = self.root / 'conductor/state'
        self.state.mkdir(parents=True)
        self.folder = self.root / 'rollbacks/release-a'
        self.folder.mkdir(parents=True)
        self.record = dict(previous='b' * 40, sha='c' * 40, rollback=str(self.folder),
                           snapshots={}, original_pins={})
        for name in ('webchat', 'dispatch'):
            prior = self.root / ('original-' + name)
            snapshot = self.folder / ('previous-' + name)
            for path in (prior, snapshot):
                self.code(path, 'b' * 40)
            self.record['snapshots'][name] = str(snapshot)
            self.record['original_pins'][name] = str(prior)
        self.code(self.folder / 'candidate', 'c' * 40)
        self.pins(self.folder / 'candidate')

    def code(self, path, sha):
        path.mkdir(parents=True, exist_ok=True)
        (path / 'webbob-build.json').write_text(json.dumps(dict(sha=sha)))

    def pins(self, code):
        for name in ('webchat', 'dispatch'):
            (self.state / (name + '-code-root')).write_text(str(code) + '\n')

    def test_concurrent_transaction_refused_before_activation_or_evidence_write(self):
        entered, finish = threading.Event(), threading.Event()
        errors = []
        def live():
            entered.set()
            if not finish.wait(5):
                raise RuntimeError('fixture timed out')
            return dict(all_pass=True)
        def first():
            try:
                solo.transaction(self.root, copy.deepcopy(self.record), self.folder / 'first.json', Mock(), live)
            except BaseException as exc:
                errors.append(exc)
        with patch.object(solo, 'require_disk_space'), patch.object(solo, 'release_recovery'):
            thread = threading.Thread(target=first)
            thread.start()
            try:
                self.assertTrue(entered.wait(5))
                activate = Mock()
                second = self.folder / 'second.json'
                with self.assertRaisesRegex(RuntimeError, 'release.*running'):
                    solo.transaction(self.root, copy.deepcopy(self.record), second, activate,
                                     Mock(return_value=dict(all_pass=True)))
                activate.assert_not_called()
                self.assertFalse(second.exists())
            finally:
                finish.set()
                thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(json.loads((self.folder / 'first.json').read_text())['status'], 'LIVE_PASS')

    def test_stale_rollback_refused_before_reserve_release_restart_or_record_mutation(self):
        newer = self.root / 'rollbacks/release-b/candidate'
        self.code(newer, 'd' * 40)
        self.pins(newer)
        before = copy.deepcopy(self.record)
        with patch.object(solo, 'versions', side_effect=RuntimeError('unexpected version')), \
                patch.object(solo, 'restart') as restart, patch.object(solo, 'release_recovery') as reserve:
            with self.assertRaisesRegex(RuntimeError, 'unrelated release'):
                solo.recover(self.root, self.record)
        restart.assert_not_called()
        reserve.assert_not_called()
        self.assertEqual(self.record, before)

    def test_same_sha_in_a_newer_release_is_still_an_unrelated_rollback(self):
        newer = self.root / 'rollbacks/release-b/candidate'
        self.code(newer, self.record['sha'])
        self.pins(newer)
        with self.assertRaisesRegex(RuntimeError, 'unrelated release'):
            solo.verify_recovery_pins(self.root, self.record)

    def test_changed_or_missing_build_and_missing_pin_refuse_recovery(self):
        for case in ('changed-build', 'missing-build', 'missing-pin'):
            with self.subTest(case=case), patch.object(solo, 'restart') as restart, \
                    patch.object(solo, 'release_recovery') as reserve:
                self.pins(self.folder / 'candidate')
                build = self.folder / 'candidate/webbob-build.json'
                build.write_text(json.dumps(dict(sha=self.record['sha'])))
                if case == 'changed-build':
                    build.write_text(json.dumps(dict(sha='d' * 40)))
                elif case == 'missing-build':
                    build.unlink()
                else:
                    (self.state / 'dispatch-code-root').unlink()
                with self.assertRaises((RuntimeError, OSError)):
                    solo.recover(self.root, self.record)
                restart.assert_not_called()
                reserve.assert_not_called()

    def test_partial_activation_and_partial_rollback_recover_both_pins(self):
        for other in (self.record['original_pins']['dispatch'], self.record['snapshots']['dispatch']):
            with self.subTest(other=other):
                self.pins(self.folder / 'candidate')
                (self.state / 'dispatch-code-root').write_text(other + '\n')
                record = copy.deepcopy(self.record)
                with patch.object(solo, 'release_recovery') as reserve, \
                        patch.object(solo, 'restart') as restart, \
                        patch.object(solo, 'versions', side_effect=[RuntimeError('candidate'), {'local': {}, 'public': {}}]):
                    solo.recover(self.root, record)
                reserve.assert_called_once()
                restart.assert_called_once_with(self.root, record['snapshots'])
                self.assertEqual(record['status'], 'ROLLED_BACK')

    def test_activation_failure_before_pin_change_can_restore_originals(self):
        for name, path in self.record['original_pins'].items():
            (self.state / (name + '-code-root')).write_text(path + '\n')
        with patch.object(solo, 'release_recovery'), patch.object(solo, 'restart') as restart, \
                patch.object(solo, 'versions', return_value={'local': {}, 'public': {}}):
            solo.recover(self.root, self.record)
        restart.assert_not_called()
        self.assertFalse(self.record['rollback_restart_needed'])

    def test_legacy_record_current_candidate_and_restored_snapshot_are_supported(self):
        self.record.pop('original_pins')
        solo.verify_recovery_pins(self.root, self.record)
        for name, path in self.record['snapshots'].items():
            (self.state / (name + '-code-root')).write_text(path + '\n')
        solo.verify_recovery_pins(self.root, self.record)

    def test_corrupt_snapshot_refuses_before_reserve_release(self):
        self.record['snapshot_hashes'] = {'webchat': 'not-the-source-hash'}
        with patch.object(solo, 'release_recovery') as reserve, patch.object(solo, 'restart') as restart:
            with self.assertRaisesRegex(RuntimeError, 'snapshot changed'):
                solo.recover(self.root, self.record)
        reserve.assert_not_called()
        restart.assert_not_called()

    def child(self, body):
        script = 'import sys\nfrom pathlib import Path\nsys.path.insert(0, sys.argv[1])\n' + body
        process = subprocess.Popen([sys.executable, '-u', '-c', script, str(solo.CODE / 'release'), str(self.root)],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        def cleanup():
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
            for stream in (process.stdin, process.stdout, process.stderr):
                stream.close()
        self.addCleanup(cleanup)
        return process

    def test_os_exclusion_and_controller_death_release_without_unlinking(self):
        child = self.child('from release_ownership import controller\n'
                          'with controller(Path(sys.argv[2])):\n'
                          ' print("owned", flush=True)\n sys.stdin.read()\n')
        self.assertEqual(child.stdout.readline().strip(), 'owned')
        path = self.root / 'conductor/locks/webbob-release.lock'
        inode = path.stat().st_ino
        with self.assertRaisesRegex(RuntimeError, 'release.*running'):
            with controller(self.root):
                self.fail('Competing controller admitted')
        child.kill()
        child.wait(timeout=5)
        with controller(self.root):
            self.assertEqual(path.stat().st_ino, inode)
        self.assertEqual(path.stat().st_ino, inode)

    def test_deploy_and_manual_rollback_refuse_before_reading_or_writing(self):
        child = self.child('from release_ownership import controller\n'
                          'with controller(Path(sys.argv[2])):\n'
                          ' print("owned", flush=True)\n sys.stdin.read()\n')
        self.assertEqual(child.stdout.readline().strip(), 'owned')
        with patch.object(solo, 'identity') as identity, patch.object(solo, 'recover') as recover:
            for action in (lambda: solo.deploy(Mock(root=self.root)),
                           lambda: solo.rollback(self.root, self.folder / 'nonexistent.json')):
                with self.assertRaisesRegex(RuntimeError, 'release.*running'):
                    action()
        identity.assert_not_called()
        recover.assert_not_called()

    def test_nested_ownership_and_exception_release_keep_one_private_inode(self):
        path = self.root / 'conductor/locks/webbob-release.lock'
        with self.assertRaisesRegex(ValueError, 'fixture'):
            with controller(self.root) as outer:
                with controller(self.root) as inner:
                    self.assertIs(outer, inner)
                    self.assertFalse(os.get_inheritable(outer.fd))
                    self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                    inode = path.stat().st_ino
                    raise ValueError('fixture')
        with controller(self.root):
            self.assertEqual(path.stat().st_ino, inode)

    def test_exec_child_does_not_inherit_controller_lock(self):
        # close_fds=False intentionally exercises O_CLOEXEC instead of relying
        # on subprocess's default descriptor cleanup.
        with controller(self.root):
            process = subprocess.Popen([sys.executable, '-u', '-c',
                'import sys; print("ready", flush=True); sys.stdin.read()'],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, close_fds=False, text=True)
            self.assertEqual(process.stdout.readline().strip(), 'ready')
        try:
            with controller(self.root):
                self.assertIsNone(process.poll())
        finally:
            process.communicate('', timeout=5)

    def test_parent_or_lock_directory_symlink_cannot_create_a_foreign_lock(self):
        target = self.root / 'foreign'
        target.mkdir()
        for case in ('conductor', 'locks'):
            with self.subTest(case=case):
                isolated = self.root / ('symlink-' + case)
                isolated.mkdir()
                if case == 'conductor':
                    (isolated / 'conductor').symlink_to(target, target_is_directory=True)
                else:
                    (isolated / 'conductor').mkdir()
                    (isolated / 'conductor/locks').symlink_to(target, target_is_directory=True)
                with self.assertRaises(OSError):
                    with controller(isolated):
                        self.fail('Symlink parent admitted')
                self.assertEqual(list(target.iterdir()), [])

    def test_recovery_and_final_publication_keep_transaction_ownership(self):
        for fails in (False, True):
            with self.subTest(fails=fails):
                attempts = []
                def other_controller():
                    try:
                        with controller(self.root):
                            attempts.append('admitted')
                    except RuntimeError:
                        attempts.append('refused')
                def race():
                    thread = threading.Thread(target=other_controller)
                    thread.start()
                    thread.join(5)
                    self.assertFalse(thread.is_alive())
                def publish(path, value):
                    if value.get('all_pass'):
                        race()
                    solo.atomic_json(path, value)
                with patch.object(solo, 'require_disk_space'), patch.object(solo, 'release_recovery'), \
                        patch.object(solo, 'restart', side_effect=lambda *_: race()), \
                        patch.object(solo, 'versions', side_effect=[RuntimeError('candidate'), {}]):
                    live = Mock(return_value=dict(all_pass=not fails))
                    args = (self.root, copy.deepcopy(self.record), self.folder / ('proof-' + str(fails)), Mock(), live)
                    if fails:
                        with self.assertRaisesRegex(RuntimeError, 'Live replay failed'):
                            solo.transaction(*args, publish=publish)
                    else:
                        solo.transaction(*args, publish=publish)
                self.assertEqual(attempts, ['refused'])

    def test_symlink_hardlink_public_and_nonregular_lock_paths_refused(self):
        folder = self.root / 'conductor/locks'
        folder.mkdir()
        path = folder / 'webbob-release.lock'
        target = self.root / 'private-fixture'
        target.write_text('preserve these bytes')
        target.chmod(0o600)
        for case in ('symlink', 'hardlink', 'public', 'fifo'):
            with self.subTest(case=case):
                if case == 'symlink':
                    path.symlink_to(target)
                elif case == 'hardlink':
                    os.link(target, path)
                elif case == 'fifo':
                    os.mkfifo(path, 0o600)
                else:
                    path.write_text('')
                    path.chmod(0o644)
                try:
                    with self.assertRaises((RuntimeError, OSError)):
                        with controller(self.root):
                            self.fail('Unsafe lock admitted')
                    self.assertEqual(target.read_text(), 'preserve these bytes')
                finally:
                    path.unlink()

    def test_replaced_lock_or_directory_cannot_be_reused_by_nested_operation(self):
        for case in ('file', 'directory'):
            with self.subTest(case=case):
                with controller(self.root):
                    folder = self.root / 'conductor/locks'
                    path = folder / 'webbob-release.lock'
                    if case == 'file':
                        path.rename(folder / 'old-lock')
                        path.touch(mode=0o600)
                    else:
                        folder.rename(self.root / 'conductor/old-locks')
                        folder.mkdir()
                    with self.assertRaisesRegex(RuntimeError, 'unsafe or has changed'):
                        with controller(self.root):
                            self.fail('Changed lock admitted')


if __name__ == '__main__':
    unittest.main()
