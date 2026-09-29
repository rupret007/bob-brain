"""Killed release controllers, using private pins and synthetic restarts only."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import solo
import activation_journal as journal


class ActivationRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.state = self.root / 'conductor/state'
        self.state.mkdir(parents=True)
        self.folder = self.root / 'rollbacks/release-a'
        self.folder.mkdir(parents=True)
        self.path = self.folder / 'release.json'
        self.final = self.root / 'conductor/latest.json'
        self.record = dict(previous='b' * 40, sha='c' * 40, rollback=str(self.folder),
                           snapshots={}, original_pins={})
        for name in ('webchat', 'dispatch'):
            for kind in ('original', 'previous'):
                code = self.folder / (kind + '-' + name)
                code.mkdir()
                solo.atomic_json(code / 'webbob-build.json', dict(sha='b' * 40))
                self.record['original_pins' if kind == 'original' else 'snapshots'][name] = str(code)
            solo.atomic_text(self.state / (name + '-code-root'), self.record['original_pins'][name] + '\n')
        candidate = self.folder / 'candidate'
        candidate.mkdir()
        solo.atomic_json(candidate / 'webbob-build.json', dict(sha='c' * 40))
        self.record['snapshot_hashes'] = {name: solo.source_digest(path) for name, path in self.record['snapshots'].items()}
        solo.atomic_json(self.path, self.record)

    def kill_at(self, phase='first-pin'):
        script = '''
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import solo
root, path, final = map(Path, sys.argv[2:5])
phase = sys.argv[5]
record = json.loads(path.read_text())
solo.require_disk_space = lambda *_: None
solo.release_recovery = lambda *_: None
def pause(point):
    if point == phase:
        print(point, flush=True)
        sys.stdin.read()
def activate():
    pause('before-pins')
    for name in ('webchat', 'dispatch'):
        solo.atomic_text(root / 'conductor/state' / (name + '-code-root'), str(path.parent / 'candidate') + '\\n')
        pause('first-pin' if name == 'webchat' else 'both-pins')
def live():
    pause('live')
    return {'all_pass': True}
def publish(target, value):
    solo.atomic_json(target, value)
    if target == final:
        pause('published')
solo.transaction(root, record, path, activate, live, publish=publish, final_path=final)
'''
        process = subprocess.Popen([sys.executable, '-u', '-c', script, str(solo.CODE / 'release'),
                                    str(self.root), str(self.path), str(self.final), phase],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(process.stdout.readline().strip(), phase)
        finally:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
            for stream in (process.stdin, process.stdout, process.stderr):
                stream.close()

    def test_killed_activation_refuses_a_new_transaction_before_effects(self):
        self.kill_at()
        activate = Mock()
        next_path = self.folder / 'other.json'
        with patch.object(solo, 'require_disk_space'), patch.object(solo, 'release_recovery'):
            with self.assertRaisesRegex(RuntimeError, 'unfinished'):
                solo.transaction(self.root, copy.deepcopy(self.record), next_path, activate,
                                 Mock(return_value=dict(all_pass=True)))
        activate.assert_not_called()
        self.assertFalse(next_path.exists())

    def test_killed_activation_refuses_deploy_before_preflight_or_snapshot(self):
        self.kill_at()
        with patch.object(solo, 'identity', side_effect=AssertionError('reached preflight')):
            with self.assertRaisesRegex(RuntimeError, 'unfinished'):
                solo.deploy(Mock(root=self.root))

    def synthetic_restart(self, root, pins):
        for name, code in pins.items():
            solo.atomic_text(self.state / (name + '-code-root'), str(code) + '\n')

    def synthetic_versions(self, root, expected):
        for name in ('webchat', 'dispatch'):
            code = Path((self.state / (name + '-code-root')).read_text().strip())
            if json.loads((code / 'webbob-build.json').read_text())['sha'] != expected:
                raise RuntimeError('Fixture version differs')
        return {name: dict(sha=expected) for name in ('local', 'public')}

    def recovery(self):
        with patch.object(solo, 'restart', side_effect=self.synthetic_restart) as restart, \
                patch.object(solo, 'versions', side_effect=self.synthetic_versions), \
                patch.object(solo, 'release_recovery'):
            solo.recover_pending(self.root)
        return restart

    def test_kill_before_pins_and_after_each_activation_stage_restores_predecessor(self):
        for phase in ('before-pins', 'first-pin', 'both-pins', 'live', 'published'):
            with self.subTest(phase=phase):
                solo.atomic_json(self.path, self.record)
                self.synthetic_restart(self.root, self.record['original_pins'])
                self.kill_at(phase)
                intent = journal.pending(self.root)
                self.assertEqual(intent['record']['sha'], self.record['sha'])
                self.assertEqual((self.root / 'conductor/locks' / journal.NAME).stat().st_mode & 0o777, 0o600)
                restart = self.recovery()
                self.assertEqual(restart.call_count, int(phase != 'before-pins'))
                for path in (self.path, self.final):
                    outcome = json.loads(path.read_text())
                    self.assertEqual(outcome['status'], 'ROLLED_BACK')
                    self.assertFalse(outcome['all_pass'])
                    self.assertEqual(outcome['restored']['public']['sha'], self.record['previous'])
                self.assertIsNone(journal.pending(self.root))
                journal.require_clear(self.root)

    def test_missing_progress_receipt_recovers_using_durable_journal(self):
        self.kill_at()
        self.path.unlink()
        self.recovery()
        self.assertTrue(json.loads(self.path.read_text())['recovered_from_journal'])

    def test_recovery_failure_keeps_obligation_and_can_be_retried_without_activation(self):
        self.kill_at()
        intent = journal.pending(self.root)
        with patch.object(solo, 'versions', side_effect=self.synthetic_versions), \
                patch.object(solo, 'restart', side_effect=RuntimeError('startup fixture failure')):
            with self.assertRaisesRegex(RuntimeError, 'startup fixture failure'):
                solo.recover_pending(self.root)
        self.assertEqual(journal.pending(self.root)['id'], intent['id'])
        self.recovery()
        self.assertIsNone(journal.pending(self.root))

    def test_failed_recovery_publication_retains_obligation_even_after_pins_restore(self):
        self.kill_at()
        original = solo.atomic_json
        def publish(path, value):
            if Path(path) == self.final:
                raise OSError('recovery alias failed')
            original(path, value)
        with patch.object(solo, 'atomic_json', side_effect=publish):
            with self.assertRaisesRegex(OSError, 'recovery alias failed'):
                self.recovery()
        self.assertIsNotNone(journal.pending(self.root))
        self.recovery().assert_not_called()
        self.assertIsNone(journal.pending(self.root))

    def test_changed_receipt_snapshot_or_unrelated_pins_refuses_recovery(self):
        for fault in ('receipt', 'snapshot', 'pin'):
            with self.subTest(fault=fault):
                self.kill_at()
                intent = journal.pending(self.root)
                if fault == 'receipt':
                    changed = json.loads(self.path.read_text())
                    changed['previous'] = 'd' * 40
                    solo.atomic_json(self.path, changed)
                elif fault == 'snapshot':
                    (Path(self.record['snapshots']['webchat']) / 'tampered.txt').write_text('changed')
                else:
                    other = self.folder / 'other'
                    other.mkdir()
                    solo.atomic_json(other / 'webbob-build.json', dict(sha=self.record['sha']))
                    solo.atomic_text(self.state / 'webchat-code-root', str(other) + '\n')
                with patch.object(solo, 'restart') as restart, patch.object(solo, 'release_recovery') as reserve:
                    with self.assertRaises(RuntimeError):
                        solo.recover_pending(self.root)
                restart.assert_not_called()
                reserve.assert_not_called()
                self.assertEqual(journal.pending(self.root)['id'], intent['id'])
                # Restore only synthetic fixture damage for the next case.
                solo.atomic_json(self.path, intent['record'])
                (Path(self.record['snapshots']['webchat']) / 'tampered.txt').unlink(missing_ok=True)
                solo.atomic_text(self.state / 'webchat-code-root', str(self.folder / 'candidate') + '\n')
                self.recovery()
                solo.atomic_json(self.path, self.record)

    def test_unrelated_manual_rollback_or_restart_cannot_bypass_pending_activation(self):
        self.kill_at()
        with self.assertRaisesRegex(RuntimeError, 'unfinished'):
            solo.rollback(self.root, self.folder / 'not-this-release.json')
        with self.assertRaisesRegex(RuntimeError, 'unfinished'):
            solo.restart(self.root, dict(webchat=self.folder / 'other', dispatch=self.folder / 'other'))

    def test_journal_failure_happens_before_activation_and_blocks_if_intent_was_written(self):
        activate = Mock()
        with patch.object(solo, 'require_disk_space'), patch.object(solo, 'release_recovery'), \
                patch.object(journal.os, 'rename', side_effect=OSError('journal write failed')):
            with self.assertRaisesRegex(OSError, 'journal write failed'):
                solo.transaction(self.root, copy.deepcopy(self.record), self.path, activate, Mock())
        activate.assert_not_called()
        self.assertIsNone(journal.pending(self.root))
        # Directory durability failure may leave a journal, but still cannot activate.
        original = journal.os.fsync
        def fsync(fd):
            import stat
            if stat.S_ISDIR(os.fstat(fd).st_mode):
                raise OSError('directory durability failed')
            original(fd)
        with patch.object(solo, 'require_disk_space'), patch.object(solo, 'release_recovery'), \
                patch.object(journal.os, 'fsync', side_effect=fsync):
            with self.assertRaisesRegex(OSError, 'directory durability failed'):
                solo.transaction(self.root, copy.deepcopy(self.record), self.path, activate, Mock())
        activate.assert_not_called()
        self.assertIsNotNone(journal.pending(self.root))
        self.recovery().assert_not_called()

    def test_unsafe_or_malformed_journal_cannot_admit_a_release(self):
        from release_ownership import controller
        with controller(self.root):
            pass
        path = self.root / 'conductor/locks' / journal.NAME
        target = self.root / 'private-target'
        solo.atomic_json(target, {'untouched': True})
        original = target.read_bytes()
        for fault in ('symlink', 'hardlink', 'public', 'fifo', 'malformed', 'oversized', 'wrong-schema'):
            with self.subTest(fault=fault):
                if fault == 'symlink':
                    path.symlink_to(target)
                elif fault == 'hardlink':
                    os.link(target, path)
                elif fault == 'fifo':
                    os.mkfifo(path, 0o600)
                else:
                    path.write_bytes(b'{' if fault == 'malformed' else b'x' * (journal.LIMIT + 1)
                                     if fault == 'oversized' else b'{}')
                    path.chmod(0o644 if fault == 'public' else 0o600)
                try:
                    with self.assertRaises((RuntimeError, OSError, ValueError)):
                        journal.require_clear(self.root)
                    self.assertEqual(target.read_bytes(), original)
                finally:
                    path.unlink()

    def test_success_and_verified_failure_remove_only_their_journal(self):
        for passed in (True, False):
            with self.subTest(passed=passed), patch.object(solo, 'require_disk_space'), \
                    patch.object(solo, 'release_recovery'), \
                    patch.object(solo, 'restart', side_effect=self.synthetic_restart), \
                    patch.object(solo, 'versions', side_effect=self.synthetic_versions):
                def activate():
                    self.assertIsNotNone(journal.pending(self.root))
                    self.synthetic_restart(self.root, {n: self.folder / 'candidate' for n in ('webchat', 'dispatch')})
                def transaction():
                    solo.transaction(self.root, copy.deepcopy(self.record), self.path, activate,
                                     Mock(return_value={'all_pass': passed}), final_path=self.final)
                if passed:
                    transaction()
                else:
                    with self.assertRaisesRegex(RuntimeError, 'Live replay failed'):
                        transaction()
                self.assertIsNone(journal.pending(self.root))
                self.assertEqual(json.loads(self.path.read_text())['status'], 'LIVE_PASS' if passed else 'ROLLED_BACK')

    def test_manual_rollback_also_creates_intent_until_both_versions_are_verified(self):
        self.synthetic_restart(self.root, {n: self.folder / 'candidate' for n in ('webchat', 'dispatch')})
        def restart(root, pins):
            self.assertIsNotNone(journal.pending(root))
            self.synthetic_restart(root, pins)
        with patch.object(solo, 'restart', side_effect=restart), \
                patch.object(solo, 'versions', side_effect=self.synthetic_versions):
            solo.rollback(self.root, self.path)
        self.assertIsNone(journal.pending(self.root))

    def test_failed_journal_removal_durability_restores_obligation_before_rollback(self):
        original = journal.os.fsync
        failed = []
        path = self.root / 'conductor/locks' / journal.NAME
        def fsync(fd):
            import stat
            if stat.S_ISDIR(os.fstat(fd).st_mode) and not path.exists() and not failed:
                failed.append(True)
                raise OSError('completion durability failed')
            original(fd)
        def activate():
            self.synthetic_restart(self.root, {n: self.folder / 'candidate' for n in ('webchat', 'dispatch')})
        def restart(root, pins):
            self.assertIsNotNone(journal.pending(root))
            self.synthetic_restart(root, pins)
        with patch.object(solo, 'require_disk_space'), patch.object(solo, 'release_recovery'), \
                patch.object(journal.os, 'fsync', side_effect=fsync), \
                patch.object(solo, 'restart', side_effect=restart), \
                patch.object(solo, 'versions', side_effect=self.synthetic_versions):
            with self.assertRaisesRegex(OSError, 'completion durability failed'):
                solo.transaction(self.root, copy.deepcopy(self.record), self.path, activate,
                                 Mock(return_value=dict(all_pass=True)), final_path=self.final)
        self.assertEqual(failed, [True])
        self.assertIsNone(journal.pending(self.root))
        self.assertEqual(json.loads(self.final.read_text())['status'], 'ROLLED_BACK')

    def test_process_killed_halfway_through_recovery_resumes_without_candidate_activation(self):
        self.kill_at('both-pins')
        script = '''
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import solo
root = Path(sys.argv[2])
def versions(root, expected):
    for name in ('webchat', 'dispatch'):
        code = Path((root / 'conductor/state' / (name + '-code-root')).read_text().strip())
        if json.loads((code / 'webbob-build.json').read_text())['sha'] != expected:
            raise RuntimeError('fixture candidate still pinned')
    return {'local': {'sha': expected}, 'public': {'sha': expected}}
def restart(root, pins):
    solo.atomic_text(root / 'conductor/state/webchat-code-root', pins['webchat'] + '\\n')
    print('partial-recovery', flush=True)
    sys.stdin.read()
solo.versions, solo.restart = versions, restart
solo.recover_pending(root)
'''
        process = subprocess.Popen([sys.executable, '-u', '-c', script, str(solo.CODE / 'release'), str(self.root)],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(process.stdout.readline().strip(), 'partial-recovery')
        finally:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
            for stream in (process.stdin, process.stdout, process.stderr):
                stream.close()
        self.assertIsNotNone(journal.pending(self.root))
        self.recovery().assert_called_once_with(self.root, self.record['snapshots'])
        self.assertIsNone(journal.pending(self.root))

    def test_missing_snapshot_authority_and_escaped_paths_are_refused_before_activation(self):
        for fault in ('missing-hash', 'foreign-path', 'foreign-reserve'):
            with self.subTest(fault=fault), patch.object(solo, 'require_disk_space'), \
                    patch.object(solo, 'release_recovery'):
                record = copy.deepcopy(self.record)
                if fault == 'missing-hash':
                    del record['snapshot_hashes']
                elif fault == 'foreign-path':
                    record['snapshots']['webchat'] = '/private/not-this-installation'
                else:
                    record['recovery_reserve'] = str(self.root / 'unrelated-file')
                activate = Mock()
                with self.assertRaises(RuntimeError):
                    solo.transaction(self.root, record, self.path, activate, Mock())
                activate.assert_not_called()
                self.assertIsNone(journal.pending(self.root))


if __name__ == '__main__':
    unittest.main()
