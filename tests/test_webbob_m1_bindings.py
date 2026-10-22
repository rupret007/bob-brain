"""Host binding inventory uses actual readers without service effects or content leaks."""
import json
import os
from pathlib import Path
import tempfile
import stat
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.webbob_m1_bindings import inventory, _authority_file
from shared_chat import SharedChatContext


class BindingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='webbob-bindings-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.chat, self.state = self.root / 'chat', self.root / 'state'
        self.chat.mkdir(mode=0o700)
        self.state.mkdir(mode=0o700)
        (self.state / 'conductor').mkdir(mode=0o700)
        self.context = SharedChatContext(self.chat, source_folder=self.state,
            fetch_engine=lambda _: self.fail('network must not be called'))
        self.write(self.chat / 'HANDOFF.md', 'Private conversation summary\n')
        self.write(self.state / 'MONITOR.md', 'Private operational details\n')
        self.write(self.state / 'NEEDS_JEFF.md', 'Private escalation details\n')
        self.write(self.state / 'conductor/digest-2026-10-18-am.md', 'Private dated digest\n')

    def write(self, path, text):
        path.write_text(text)
        path.chmod(0o600)

    def read(self):
        with patch('tools.webbob_m1_bindings._git', side_effect=['a'*40, '']), \
             patch('tools.webbob_m1_bindings.load_build', return_value={'sha': 'a'*40}):
            return inventory('a'*40, context=self.context, install=self.root / 'absent')

    def test_actual_canonical_journal_and_dated_digest_paths_no_contents_or_effects(self):
        result = self.read()
        self.assertTrue(result['required_sources_readable'])
        self.assertTrue(result['candidate_matches'])
        self.assertNotIn('Private', json.dumps(result))
        paths = {r['source']: r['path'] for r in result['sources']}
        self.assertEqual(paths['Mini chat/HANDOFF.md'], str(self.chat / 'HANDOFF.md'))
        self.assertEqual(paths['MORNING_DIGEST.md'], str(self.state / 'conductor/digest-2026-10-18-am.md'))
        for field in ('activation_authorized', 'action_authority_verified', 'actions_exercised', 'cluster_claims_exercised'):
            self.assertFalse(result[field])
        self.assertTrue(all(r['state'] == 'unavailable' for r in result['action_components']))

    def test_missing_canonical_records_actual_custom_sync_path(self):
        (self.state / 'MONITOR.md').unlink()
        self.write(self.chat / 'MONITOR.md', 'Private synced observation\n')
        result = self.read()
        monitor = next(r for r in result['sources'] if r['source'] == 'MONITOR.md')
        self.assertEqual(monitor['path'], str(self.chat / 'MONITOR.md'))
        self.assertIn('synced source copy', monitor['provenance'])

    def test_unsafe_canonical_does_not_fall_back_and_staleness_is_preserved(self):
        self.write(self.chat / 'MONITOR.md', 'Old sync must not mask unsafe canonical\n')
        (self.state / 'MONITOR.md').chmod(0o666)
        os.utime(self.chat / 'HANDOFF.md', (0, 0))
        result = self.read()
        self.assertFalse(result['required_sources_readable'])
        rows = {r['source']: r for r in result['sources']}
        self.assertEqual(rows['MONITOR.md']['state'], 'unavailable')
        self.assertEqual(rows['Mini chat/HANDOFF.md']['freshness'], 'stale')

    def test_mismatched_build_or_dirty_checkout_is_not_selected_candidate(self):
        for head, build, dirty in [('b'*40, 'a'*40, ''), ('a'*40, 'b'*40, ''), ('a'*40, 'a'*40, ' M source.py')]:
            with patch('tools.webbob_m1_bindings._git', side_effect=[head, dirty]), \
                 patch('tools.webbob_m1_bindings.load_build', return_value={'sha': build}):
                self.assertFalse(inventory('a'*40, context=self.context)['candidate_matches'])

    def test_full_sha_required(self):
        for value in ('abc1234', 'A'*40, None):
            with self.assertRaises(ValueError):
                inventory(value, context=self.context)

    def test_installation_presence_cannot_establish_contract_or_execution_authority(self):
        component = self.root / 'cluster/control_plane/owner_task_scheduler.py'
        component.parent.mkdir(parents=True)
        component.write_text('raise AssertionError("must never import")\n')
        real_stat = Path.stat
        def trusted_parent(path, *args, **kwargs):
            info = real_stat(path, *args, **kwargs)
            # Simulate an owner-controlled installation hierarchy. The sandbox
            # maps root ownership and /tmp is intentionally world-writable.
            return SimpleNamespace(st_uid=os.getuid(), st_mode=info.st_mode & ~0o022)
        with patch('tools.webbob_m1_bindings._git', side_effect=['a'*40, '']), \
             patch('tools.webbob_m1_bindings.load_build', return_value={'sha': 'a'*40}), \
             patch.object(Path, 'stat', trusted_parent):
            result = inventory('a'*40, context=self.context, install=self.root)
        self.assertEqual(result['action_components'][-1]['state'], 'present_not_verified')
        self.assertFalse(result['action_authority_verified'])
        self.assertFalse(result['actions_exercised'])

    def test_missing_and_symlink_authorities_have_precise_safe_reasons(self):
        self.assertEqual(_authority_file(self.root, 'absent')['unavailable_reason'], 'missing')
        target = self.root / 'authority.py'
        target.write_text('raise AssertionError("do not import")\n')
        (self.root / 'linked.py').symlink_to(target)
        row = _authority_file(self.root, 'linked.py')
        self.assertEqual(row['state'], 'unavailable')
        self.assertEqual(row['unavailable_reason'], 'symlink_or_noncanonical_path')
