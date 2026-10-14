"""Fail-closed Andrea pin-change, receipt-path, and score-only strictness."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pin_change
import score_only
import solo


OLD_SHA = '83623dd8e6815dc1a95baa87a9f1e44d8e1fbf3e'
NEW_SHA = 'aa' * 20
OTHER_SHA = 'bb' * 20
CONFIG = b'{"suite":"andrea-exact-tip","n":3}'
OLD_PIN = dict(repo='rupret007/Andrea_NanoBot', sha=OLD_SHA,
               worktree='andrea-webbob-older-thread-1002', protocol=1)
NEW_PIN = dict(OLD_PIN, sha=NEW_SHA, worktree='andrea-webbob-pin-new')


def _write_readonly(path, data, mode=0o444):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o755)
    path.write_bytes(data if isinstance(data, bytes) else data.encode())
    os.chmod(path, mode)
    return path


def _lock_tree(path, file_mode=0o444, dir_mode=0o555):
    path = Path(path)
    for child in sorted(path.rglob('*'), reverse=True):
        os.chmod(child, file_mode if child.is_file() else dir_mode)
    os.chmod(path, dir_mode)


class ReceiptFixtures:
    def __init__(self, root, sha, *, current=True):
        self.root = Path(root)
        self.sha = sha
        self.folder = (pin_change.current_receipt_dir(root, sha) if current
                       else pin_change.historical_receipt_dir(root, sha))
        self.folder.mkdir(parents=True)
        (self.folder / 'blobs').mkdir()
        self.config_sha = hashlib.sha256(CONFIG).hexdigest()
        _write_readonly(self.folder / 'blobs' / self.config_sha, CONFIG)
        self.rows = {}
        for name in pin_change.RECEIPT_NAMES:
            log = ('%s log for %s\n' % (name, sha)).encode()
            log_sha = hashlib.sha256(log).hexdigest()
            _write_readonly(self.folder / 'blobs' / log_sha, log)
            row = dict(sha=sha, exit=0, log='blobs/' + log_sha, log_sha256=log_sha,
                       config_sha256=self.config_sha)
            path = self.folder / (name + '.json')
            _write_readonly(path, json.dumps(row, sort_keys=True))
            self.rows[name] = dict(row, path=path, receipt_sha256=pin_change.digest(path))
        _lock_tree(self.folder)

    def hashes(self):
        return {name: self.rows[name]['receipt_sha256'] for name in pin_change.RECEIPT_NAMES}

    def unlock(self):
        os.chmod(self.folder, 0o755)
        os.chmod(self.folder / 'blobs', 0o755)


def write_pin_ack(root, sha, hashes, *, in_log=True):
    ack = dict(sha=sha, receipt_sha256=hashes)
    path = pin_change.pin_ack_path(root, sha)
    os.makedirs(path.parent, exist_ok=True)
    if path.exists():
        os.chmod(path, 0o644)
    _write_readonly(path, json.dumps(ack, sort_keys=True))
    log = pin_change.protected_ack_log(root)
    row = dict(sha=sha, ack_sha256=pin_change.digest(path), receipt_sha256=hashes)
    if log.exists():
        os.chmod(log, 0o644)
    body = (json.dumps(row, sort_keys=True) + '\n') if in_log else ''
    _write_readonly(log, body)
    return path


class PinChangeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.receipts = ReceiptFixtures(self.root, NEW_SHA)
        write_pin_ack(self.root, NEW_SHA, self.receipts.hashes())

    def verify(self, **kw):
        defaults = dict(
            changed_files=[pin_change.PIN_PATH], old_pin=OLD_PIN, new_pin=NEW_PIN,
            on_main=lambda sha: sha == NEW_SHA, baseline_sha=OLD_SHA, environ={})
        defaults.update(kw)
        return pin_change.verify_pin_change(self.root, **defaults)

    def test_attested_pin_change_is_allowed(self):
        row = self.verify()
        self.assertEqual(row['status'], pin_change.ALLOWED)
        self.assertEqual(row['sha'], NEW_SHA)
        self.assertEqual(row['receipt_sha256'], self.receipts.hashes())

    def test_unsigned_pin_is_needs_jeff(self):
        pin_change.pin_ack_path(self.root, NEW_SHA).unlink()
        row = self.verify()
        self.assertEqual(row['status'], pin_change.NEEDS_JEFF)
        self.assertEqual(row['reason'], 'unsigned pin')

    def test_ack_not_in_protected_log_is_unsigned(self):
        write_pin_ack(self.root, NEW_SHA, self.receipts.hashes(), in_log=False)
        row = self.verify()
        self.assertEqual(row['status'], pin_change.NEEDS_JEFF)
        self.assertEqual(row['reason'], 'unsigned pin')

    def test_receipt_hash_mismatch_is_needs_jeff(self):
        self.receipts.unlock()
        blob = self.receipts.folder / self.receipts.rows['major']['log']
        os.chmod(blob, 0o644)
        blob.write_bytes(blob.read_bytes() + b'tampered')
        os.chmod(blob, 0o444)
        _lock_tree(self.receipts.folder)
        row = self.verify()
        self.assertEqual(row['status'], pin_change.NEEDS_JEFF)
        self.assertEqual(row['reason'], 'receipt hash mismatch')

    def test_writable_receipts_are_needs_jeff(self):
        self.receipts.unlock()
        os.chmod(self.receipts.folder / 'major.json', 0o644)
        row = self.verify()
        self.assertEqual(row['status'], pin_change.NEEDS_JEFF)
        self.assertIn('writable', row['reason'])

    def test_non_main_sha_is_needs_jeff(self):
        row = self.verify(on_main=lambda sha: False)
        self.assertEqual(row['status'], pin_change.NEEDS_JEFF)
        self.assertEqual(row['reason'], 'non-main sha')

    def test_short_sha_is_needs_jeff(self):
        row = self.verify(new_pin=dict(NEW_PIN, sha='abc'))
        self.assertEqual(row['status'], pin_change.NEEDS_JEFF)
        self.assertIn('40-char', row['reason'])

    def test_extra_release_file_change_is_needs_jeff(self):
        row = self.verify(changed_files=[pin_change.PIN_PATH, 'release/solo.py'])
        self.assertEqual(row['status'], pin_change.NEEDS_JEFF)
        self.assertIn('extra release/ file change', row['reason'])

    def test_only_non_pin_release_file_is_needs_jeff(self):
        row = self.verify(changed_files=['release/solo.py'])
        self.assertEqual(row['status'], pin_change.NEEDS_JEFF)
        self.assertIn('extra release/ file change', row['reason'])

    def test_extra_keys_are_needs_jeff(self):
        row = self.verify(new_pin=dict(NEW_PIN, protocol=2))
        self.assertEqual(row['status'], pin_change.NEEDS_JEFF)
        self.assertIn('extra keys', row['reason'])

    def test_added_pin_key_is_needs_jeff(self):
        row = self.verify(new_pin=dict(NEW_PIN, extra='nope'))
        self.assertEqual(row['status'], pin_change.NEEDS_JEFF)
        self.assertIn('extra keys', row['reason'])

    def test_env_overrides_are_needs_jeff(self):
        for name in ('RECEIPT_GUARD_SKIP', 'ANDREA_SHA', 'WEBBOB_PIN_CHANGE_ALLOW', 'PIN_CHANGE_ALLOW'):
            with self.subTest(name=name):
                row = self.verify(environ={name: '1'})
                self.assertEqual(row['status'], pin_change.NEEDS_JEFF)
                self.assertIn('env overrides', row['reason'])

    def test_unchanged_release_tree_is_allowed_without_ack(self):
        row = self.verify(changed_files=[])
        self.assertEqual(row['status'], pin_change.ALLOWED)

    def test_missing_receipts_are_needs_jeff(self):
        empty = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: os.rmdir(empty) if empty.exists() else None)
        row = pin_change.verify_pin_change(
            empty, changed_files=[pin_change.PIN_PATH], old_pin=OLD_PIN,
            new_pin=NEW_PIN, on_main=lambda sha: sha == NEW_SHA,
            baseline_sha=OLD_SHA, environ={})
        self.assertEqual(row['status'], pin_change.NEEDS_JEFF)
        self.assertIn('receipts missing', row['reason'])

    def test_new_pin_cannot_use_historical_receipt_path(self):
        historical = ReceiptFixtures(self.root, OTHER_SHA, current=False)
        write_pin_ack(self.root, OTHER_SHA, historical.hashes())
        row = pin_change.verify_pin_change(
            self.root, changed_files=[pin_change.PIN_PATH], old_pin=OLD_PIN,
            new_pin=dict(NEW_PIN, sha=OTHER_SHA), on_main=lambda sha: sha == OTHER_SHA,
            baseline_sha=OLD_SHA, environ={})
        self.assertEqual(row['status'], pin_change.NEEDS_JEFF)
        self.assertIn('receipts missing', row['reason'])


class AndreaGatesPathTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def run_gates(self, sha):
        with patch.object(solo, 'andrea_pin', return_value=dict(OLD_PIN, sha=sha)):
            return solo.andrea_gates(self.root, baseline_sha=OLD_SHA)

    def test_current_receipt_path_is_the_source_of_truth(self):
        current = ReceiptFixtures(self.root, NEW_SHA)
        ReceiptFixtures(self.root, NEW_SHA, current=False)
        row = self.run_gates(NEW_SHA)
        self.assertEqual(row['sha'], NEW_SHA)
        self.assertEqual(row['source'], 'current')
        self.assertEqual(Path(row['folder']), current.folder)

    def test_historical_path_only_for_baseline_pin(self):
        historical = ReceiptFixtures(self.root, OLD_SHA, current=False)
        row = self.run_gates(OLD_SHA)
        self.assertEqual(row['source'], 'historical')
        self.assertEqual(Path(row['folder']), historical.folder)

    def test_historical_path_uses_the_same_receipt_guard(self):
        ReceiptFixtures(self.root, OLD_SHA, current=False)
        folder = pin_change.historical_receipt_dir(self.root, OLD_SHA)
        os.chmod(folder, 0o755)
        blob = folder / json.loads((folder / 'major.json').read_text())['log']
        os.chmod(folder / 'blobs', 0o755)
        os.chmod(blob, 0o644)
        blob.write_bytes(blob.read_bytes() + b'x')
        os.chmod(blob, 0o444)
        _lock_tree(folder)
        with self.assertRaisesRegex(Exception, 'failed or changed'):
            self.run_gates(OLD_SHA)

    def test_new_pin_does_not_fall_back_to_historical_path(self):
        ReceiptFixtures(self.root, NEW_SHA, current=False)
        with self.assertRaisesRegex(Exception, 'failed or changed'):
            self.run_gates(NEW_SHA)

    def test_andrea_gates_rejects_env_overrides(self):
        ReceiptFixtures(self.root, NEW_SHA)
        with patch.object(solo, 'andrea_pin', return_value=dict(OLD_PIN, sha=NEW_SHA)), \
                patch.dict(os.environ, {'RECEIPT_GUARD_SKIP': '1'}, clear=False):
            with self.assertRaisesRegex(Exception, 'env overrides'):
                solo.andrea_gates(self.root, baseline_sha=OLD_SHA)


class ScoreOnlyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        receipts = ReceiptFixtures(self.root, NEW_SHA)
        write_pin_ack(self.root, NEW_SHA, receipts.hashes())
        _write_readonly(score_only.score_lock_path(self.root),
                        json.dumps(dict(holder='score-only', exclusive=True)))
        oneshot = dict(kind=score_only.ONESHOT_KIND, sha=NEW_SHA, used=False)
        oneshot_path = score_only.oneshot_ack_path(self.root, NEW_SHA)
        _write_readonly(oneshot_path, json.dumps(oneshot, sort_keys=True))
        log = pin_change.protected_ack_log(self.root)
        os.chmod(log, 0o644)
        log.write_text(log.read_text() + json.dumps(dict(
            kind=score_only.ONESHOT_KIND, sha=NEW_SHA,
            ack_sha256=pin_change.digest(oneshot_path)), sort_keys=True) + '\n')
        os.chmod(log, 0o444)
        self.pin_ok = dict(status=pin_change.ALLOWED, reason='release/ unchanged versus gate base')

    def plan(self, **kw):
        defaults = dict(rounds=score_only.PREREGISTERED_ROUNDS,
                        retries={'class': 'transport', 'max': 2},
                        environ={}, pin_verdict=self.pin_ok)
        defaults.update(kw)
        return score_only.score_only_plan(self.root, NEW_SHA, **defaults)

    def test_clean_fixed_commit_plans_nine_transport_retries(self):
        row = self.plan()
        self.assertEqual(row['status'], 'planned')
        self.assertTrue(row['readonly'])
        self.assertEqual(row['n'], 9)
        self.assertEqual(row['rounds'], list(score_only.PREREGISTERED_ROUNDS))
        self.assertEqual(row['retries'], {'class': 'transport', 'max': 2})

    def test_n_not_nine_is_needs_jeff(self):
        row = self.plan(rounds=score_only.PREREGISTERED_ROUNDS[:-1])
        self.assertEqual(row['status'], pin_change.NEEDS_JEFF)
        self.assertEqual(row['reason'], 'N!=9')

    def test_reordered_or_substituted_rounds_are_needs_jeff(self):
        extra = score_only.PREREGISTERED_ROUNDS[:-1] + ('invented',)
        row = self.plan(rounds=extra)
        self.assertEqual(row['status'], pin_change.NEEDS_JEFF)
        self.assertEqual(row['reason'], 'N!=9')

    def test_extra_retries_are_needs_jeff(self):
        for retries in (
            {'class': 'transport', 'max': 3},
            {'class': 'logic', 'max': 1},
            {'class': 'transport', 'max': 2, 'extra': 1},
            {'class': 'transport', 'max': 2, 'bonus': True},
        ):
            with self.subTest(retries=retries):
                row = self.plan(retries=retries)
                self.assertEqual(row['status'], pin_change.NEEDS_JEFF)
                self.assertEqual(row['reason'], 'extra retries')

    def test_env_overrides_are_needs_jeff(self):
        row = self.plan(environ={'SCORE_ONLY_N': '8'})
        self.assertEqual(row['status'], pin_change.NEEDS_JEFF)
        self.assertIn('env overrides', row['reason'])

    def test_parked_without_oneshot_ack_is_needs_jeff(self):
        score_only.oneshot_ack_path(self.root, NEW_SHA).unlink()
        row = self.plan()
        self.assertEqual(row['status'], pin_change.NEEDS_JEFF)
        self.assertIn('parked', row['reason'])

    def test_used_oneshot_ack_stays_parked(self):
        path = score_only.oneshot_ack_path(self.root, NEW_SHA)
        os.chmod(path, 0o644)
        path.write_text(json.dumps(dict(kind=score_only.ONESHOT_KIND, sha=NEW_SHA, used=True)))
        os.chmod(path, 0o444)
        row = self.plan()
        self.assertEqual(row['status'], pin_change.NEEDS_JEFF)
        self.assertIn('parked', row['reason'])

    def test_unclean_pin_blocks_score_only(self):
        row = self.plan(pin_verdict=dict(status=pin_change.NEEDS_JEFF, reason='extra release/ file change'))
        self.assertEqual(row['status'], pin_change.NEEDS_JEFF)
        self.assertIn('extra release/ file change', row['reason'])


if __name__ == '__main__':
    unittest.main()
