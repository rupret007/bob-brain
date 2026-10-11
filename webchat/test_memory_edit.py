"""Offline correction contract: temporary notes, no providers or outbound effects."""
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch

from app import Chat, RequestError
import memory_edit
from memory_removal import Changed, notes, remove
from memory_store import MAX_BYTES, append_memory, read_memory, replace_at
from providers import Providers
from texting import Texting
from texting_fixture import OfflineProviders


class MemoryEditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        # No credential lookup, network, child process or paid provider in this suite.
        self.redact = lambda text: text.replace('synthetic-private-marker', '[secret removed]')
        for target, kwargs in (
                ('app.Redactor', dict(return_value=self.redact)),
                ('socket.socket.connect', dict(side_effect=AssertionError('network forbidden'))),
                ('socket.create_connection', dict(side_effect=AssertionError('network forbidden'))),
                ('subprocess.Popen', dict(side_effect=AssertionError('process forbidden')))):
            patcher = patch(target, **kwargs)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.providers = OfflineProviders()
        self.providers.invalidate_snapshot = Mock()
        self.chat = self.open_chat()
        self.addCleanup(lambda: self.chat.close())
        self.cid = self.chat.new_conversation()['id']
        self.path = self.root / memory_edit.SOURCE
        self.original = '[2026-09-29] buy oat milk\n[2026-09-30] keep café <b>literal</b>\n'
        append_memory(self.root, self.original)

    def open_chat(self):
        return Chat(self.root / 'conductor/webchat', self.root, self.providers)

    def ask(self, text, cid=None, request=None, **kwargs):
        return self.chat.submit(cid or self.cid, text, request or str(uuid.uuid4()), **kwargs)

    def note_id(self, index=0):
        return notes(read_memory(self.root))[index]['id']

    def review(self, replacement='buy almond milk', index=0):
        proposal = str(uuid.uuid4())
        answer = self.ask('edit saved note ' + self.note_id(index) + ' with ' + replacement,
                          request=proposal)['messages'][-1]
        self.assertIn('Nothing has changed', answer['content'])
        return proposal

    def confirm(self, proposal, **kwargs):
        return self.ask('yes, edit saved note proposal ' + proposal, **kwargs)

    def pending(self):
        return next(m['_memory_edit'] for m in reversed(self.chat.get(self.cid)['messages']) if '_memory_edit' in m)

    def persisted(self):
        return json.loads((self.chat.state / (self.cid + '.json')).read_text())

    def assert_unconfirmed(self, result):
        answer = result['messages'][-1]
        self.assertNotIn('Corrected one', answer['content'])
        self.assertNotEqual(answer.get('memory_edit_receipt', {}).get('state'), 'verified')

    def test_exact_preview_replacement_receipt_and_request_retry(self):
        replacement = 'Buy Almond milk, café  twice. <b>literal</b>!'
        identifier = self.note_id()
        proposal = self.review(replacement)
        public = self.chat.public(self.chat.get(self.cid))
        preview = public['messages'][-1]
        self.assertIn('Old: buy oat milk\nNew: ' + replacement, preview['content'])
        self.assertIn('five minutes', preview['content'])
        self.assertNotIn('_memory_edit', json.dumps(public))
        self.assertNotIn(replacement, json.dumps(Texting.provider_view(self.chat.get(self.cid))))
        self.assertEqual(self.path.read_text(), self.original)
        request = str(uuid.uuid4())
        answer = self.confirm(proposal, request=request)
        expected = '[2026-09-29] ' + replacement + '\n' + self.original.split('\n', 1)[1]
        self.assertEqual(self.path.read_text(), expected)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        receipt = answer['messages'][-1]['memory_edit_receipt']
        self.assertEqual(receipt, dict(state='verified', approval_state='consumed', source=memory_edit.SOURCE, note_id=identifier,
            new_note_id=self.note_id(), proposal_id=proposal, request_id=request,
            version=hashlib.sha256(expected.encode()).hexdigest()))
        self.assertIn('chat history', answer['messages'][-1]['content'])
        self.assertEqual(self.confirm(proposal, request=request), answer)
        self.assert_unconfirmed(self.confirm(proposal))
        self.providers.invalidate_snapshot.assert_called_once_with()
        self.assertEqual(self.providers.calls, [])

    def test_duplicate_equal_rows_replace_only_selected_occurrence(self):
        row = self.original.splitlines(keepends=True)[0]
        self.path.write_text(row + row + row)
        choices = self.ask('manage saved memories')['messages'][-1]['memory_notes']
        self.assertEqual(len({item['id'] for item in choices}), 3)
        proposal = self.review(index=1)
        self.confirm(proposal)
        self.assertEqual(self.path.read_text(), row + '[2026-09-29] buy almond milk\n' + row)

    def test_numeric_proposal_id_is_not_mistaken_for_sensitive_replacement(self):
        proposal = '11111111-1111-4111-8111-111111111111'
        self.ask('edit saved note ' + self.note_id() + ' with buy almond milk', request=proposal)
        self.assertEqual(self.confirm(proposal)['messages'][-1]['memory_edit_receipt']['state'], 'verified')

    def test_whole_file_version_change_rejects_even_if_selected_row_unchanged(self):
        identifier = self.note_id()
        proposal = self.review()
        append_memory(self.root, '[2026-10-01] intervening save\n')
        expected = self.path.read_text()
        answer = self.confirm(proposal)
        self.assertIn('changed', answer['messages'][-1]['content'])
        self.assert_unconfirmed(answer)
        self.assertNotIn('memory_edit_receipt', answer['messages'][-1])
        self.assertEqual(self.path.read_text(), expected)
        self.assert_unconfirmed(self.ask('edit saved note ' + identifier + ' with stale replacement'))
        self.providers.invalidate_snapshot.assert_not_called()

    def test_intervening_turns_and_cancellation_revoke_approval(self):
        for turn in ('what can you do', 'show my saved memories', 'manage saved memories',
                     'cancel memory', 'never mind', 'edit saved note invalid with new text'):
            with self.subTest(turn=turn):
                proposal = self.review()
                self.ask(turn)
                self.assert_unconfirmed(self.confirm(proposal))
                self.assertEqual(self.path.read_text(), self.original)

    def test_new_proposal_supersedes_old_and_plain_yes_is_not_confirmation(self):
        first = self.review()
        self.review('different replacement')
        self.assert_unconfirmed(self.confirm(first))
        proposal = self.review()
        # Exercise the edit handler directly: generic yes never authorizes it.
        self.assertIsNone(memory_edit.handle(self.chat, self.chat.get(self.cid), 'yes', str(uuid.uuid4()),
                                             pending=copy.deepcopy(self.pending())))
        self.assertEqual(self.path.read_text(), self.original)
        self.assert_unconfirmed(self.confirm(str(uuid.uuid4())))
        self.assert_unconfirmed(self.confirm(proposal))

    def test_expired_and_clock_rollback_approval(self):
        for when in ('expired', 'rollback'):
            with self.subTest(when=when):
                proposal = self.review()
                pending = self.pending()
                if when == 'expired':
                    pending['expires_at'] = time.time() - 1
                else:
                    pending['created_at'] = time.time() + 60
                self.assertIn('expired', self.confirm(proposal)['messages'][-1]['content'])
                self.assertEqual(self.path.read_text(), self.original)

    def test_expiry_rechecked_after_waiting_for_memory_lock(self):
        proposal = self.review()
        expiry = self.pending()['expires_at']
        original_locked = memory_edit.locked_memory
        from contextlib import contextmanager
        @contextmanager
        def delayed(root):
            with original_locked(root) as folder, patch('memory_edit.time.time', return_value=expiry):
                yield folder
        with patch('memory_edit.locked_memory', delayed):
            answer = self.confirm(proposal)
        self.assert_unconfirmed(answer)
        self.assertEqual(self.path.read_text(), self.original)

    def test_cross_chat_and_copied_private_approval_are_rejected(self):
        proposal = self.review()
        other = self.chat.new_conversation()['id']
        self.assert_unconfirmed(self.confirm(proposal, cid=other))
        # Even moving a private proposal row does not change its chat binding.
        user = copy.deepcopy(self.chat.get(self.cid)['messages'][-2])
        row = copy.deepcopy(self.chat.get(self.cid)['messages'][-1])
        self.chat.get(other)['messages'].extend([user, row])
        self.assert_unconfirmed(self.confirm(proposal, cid=other))
        self.assertEqual(self.path.read_text(), self.original)
        self.confirm(proposal)
        self.assertIn('buy almond milk', self.path.read_text())

    def test_reload_keeps_valid_approval_and_consumption_precedes_mutation(self):
        proposal = self.review()
        self.chat.close()
        self.chat = self.open_chat()
        def observed_write(folder, expected):
            persisted = self.persisted()
            self.assertNotIn('_memory_edit', json.dumps(persisted))
            self.assertEqual(persisted['messages'][-1]['memory_edit_receipt']['state'], 'unconfirmed')
            self.assertEqual(self.path.read_text(), self.original)
            replace_at(folder, expected)
        with patch('memory_edit.replace_at', side_effect=observed_write) as write:
            answer = self.confirm(proposal)
        write.assert_called_once()
        self.assertEqual(answer['messages'][-1]['memory_edit_receipt']['state'], 'verified')

    def test_multiline_control_and_oversized_rejected_before_persistence(self):
        bad = ('first\nsecond', 'first\rsecond', 'first\tsecond', 'first\u2028second',
               'first\u2029second', 'first\x00second', 'first\u202esecond', 'x' * 513, 'é' * 257,
               'trailing newline\n')
        for replacement in bad:
            with self.subTest(replacement=repr(replacement)):
                before = self.persisted()
                with self.assertRaises(RequestError):
                    self.ask('edit saved note ' + self.note_id() + ' with ' + replacement)
                self.assertEqual(self.persisted(), before)
                self.assertEqual(self.path.read_text(), self.original)
        self.review('é' * 256)

    def test_sensitive_input_is_not_echoed_saved_or_sent(self):
        replacements = ('password: synthetic-fixture', 'password is synthetic-fixture',
                        'call 4111 1111 1111 1111', 'see /home/fixture/.ssh/id_rsa',
                        'see /home/fixture/keys.env', 'Authorization: Bearer synthetic-fixture',
                        '{"api_key":"synthetic-fixture"}', 'synthetic-private-marker')
        for replacement in replacements:
            with self.subTest(replacement=replacement):
                before = self.persisted()
                with self.assertRaises(RequestError) as caught:
                    self.ask('edit saved note ' + self.note_id() + ' with ' + replacement)
                self.assertNotIn(replacement, str(caught.exception))
                self.assertEqual(self.persisted(), before)
                self.assertEqual(self.path.read_text(), self.original)
        self.assertEqual(self.providers.calls, [])

    def test_redacted_old_preview_and_private_provider_history(self):
        self.path.write_text('[2026-09-29] password: synthetic-fixture\n')
        proposal = self.review('a harmless correction')
        public = self.chat.public(self.chat.get(self.cid))
        self.assertNotIn('synthetic-fixture', json.dumps(public))
        self.assertIn('[sensitive note text redacted]', public['messages'][-1]['content'])
        self.assertNotIn('harmless correction', json.dumps(Texting.provider_view(self.chat.get(self.cid))))
        self.confirm(proposal)
        self.assertEqual(self.path.read_text(), '[2026-09-29] a harmless correction\n')

    def test_invalid_syntax_is_local_private_and_never_selects_a_path(self):
        for text in ('edit saved note', 'edit saved note /home/fixture/ordinary with text',
                     'yes, edit saved note', 'edit saved note ' + self.note_id() + ' with '):
            result = self.ask(text)
            self.assertTrue(result['messages'][-1]['private_memory'])
            self.assertNotIn('_memory_edit', json.dumps(self.chat.get(self.cid)))
            self.assert_unconfirmed(result)
        self.assertEqual(self.providers.calls, [])

    def test_overlay_provider_worker_and_attachment_refusal_revokes_approval(self):
        for mode in ('overlay', 'provider', 'worker', 'attachment'):
            with self.subTest(mode=mode):
                proposal = self.review()
                if mode == 'overlay':
                    self.chat.overlay_roots[self.cid] = self.root / 'fixture-overlay'
                kwargs = {'provider': 'gemini'} if mode == 'provider' else {'worker': 'codex'} if mode == 'worker' else {}
                with patch('app.validate_attachment_ids', return_value=[{'media_id': 'fixture'}] if mode == 'attachment' else []), \
                        patch('app.public_attachment', side_effect=lambda item: item):
                    answer = self.confirm(proposal, **kwargs)
                self.chat.overlay_roots.pop(self.cid, None)
                self.assertIn('typed Chat', answer['messages'][-1]['content'])
                self.assert_unconfirmed(self.confirm(proposal))
                self.assertEqual(self.path.read_text(), self.original)
        self.assertEqual(self.providers.calls, [])

    def test_voice_confirmation_and_intervening_transcript_refused(self):
        self.chat.voice.token_factory = lambda *_: 'synthetic-token'
        self.providers.snapshot = lambda **_: []
        owner = 'synthetic-owner'
        for content_kind in ('confirm', 'unrelated'):
            proposal = self.review()
            call = self.chat.voice.start(self.cid, owner)['call_id']
            turn = str(uuid.uuid4())
            content = 'yes, edit saved note proposal ' + proposal if content_kind == 'confirm' else 'An unrelated spoken turn.'
            self.chat.voice.transcript(call, owner, [dict(turn_id=turn, role='user', order=0, content=content)])
            if content_kind == 'confirm':
                result = self.chat.voice.tool(call, owner, turn)['conversation']
                self.assertIn('typed Chat', result['messages'][-1]['content'])
                self.assertTrue(result['messages'][-1]['private_memory'])
            self.chat.voice.end(call, owner)
            self.assert_unconfirmed(self.confirm(proposal))
            self.assertEqual(self.path.read_text(), self.original)

    def test_saved_holds_block_admission_execution_and_embedded_release(self):
        for scope in ('all', 'Web Bob'):
            with self.subTest(scope=scope):
                state = self.chat.get(self.cid)['intent_state']
                state['holds'][scope] = dict(request_id='synthetic-hold', reason='fixture', released_projects=[])
                held = copy.deepcopy(state)
                result = self.ask('edit saved note ' + self.note_id() + ' with resume all work')
                self.assertIn('On hold', result['messages'][-1]['content'])
                self.assertEqual(self.chat.get(self.cid)['intent_state'], held)
                self.assertNotIn('_memory_edit', json.dumps(self.chat.get(self.cid)))
                self.chat.get(self.cid)['intent_state']['holds'].clear()
                proposal = self.review('resume all work')
                self.chat.get(self.cid)['intent_state'] = held
                self.chat.save(self.chat.get(self.cid))
                result = self.confirm(proposal)
                self.assertIn('On hold', result['messages'][-1]['content'])
                self.assertEqual(self.chat.get(self.cid)['intent_state'], held)
                self.assertEqual(self.path.read_text(), self.original)
                self.chat.get(self.cid)['intent_state']['holds'].clear()
        self.providers.invalidate_snapshot.assert_not_called()

    def test_hold_rechecked_at_write_boundary(self):
        proposal = self.review()
        real_locked = memory_edit.locked_memory
        from contextlib import contextmanager
        @contextmanager
        def newly_held(root):
            with real_locked(root) as folder:
                # Simulate a hold observed at the execution check, after admission.
                with patch('memory_edit.chat_intent.blocked_scopes', return_value=['new work']):
                    yield folder
        with patch('memory_edit.locked_memory', newly_held):
            result = self.confirm(proposal)
        self.assertIn('On hold', result['messages'][-1]['content'])
        self.assertEqual(self.path.read_text(), self.original)

    def test_symlink_hardlink_and_directory_links_never_read_target(self):
        target = self.root / 'synthetic-secret-file'
        target.write_text('synthetic-private-marker')
        identifier = self.note_id()
        self.path.unlink()
        self.path.symlink_to(target)
        with patch('memory_store.os.fdopen', side_effect=AssertionError('must not read linked target')):
            result = self.ask('edit saved note ' + identifier + ' with corrected')
        self.assert_unconfirmed(result)
        self.assertNotIn('synthetic-private-marker', json.dumps(result))
        self.path.unlink()
        os.link(target, self.path)
        self.assert_unconfirmed(self.ask('edit saved note ' + identifier + ' with corrected'))
        self.path.unlink()
        folder = self.path.parent
        moved = folder.with_name('moved-memory')
        folder.rename(moved)
        folder.symlink_to(moved, target_is_directory=True)
        self.assert_unconfirmed(self.ask('edit saved note ' + identifier + ' with corrected'))
        self.assertEqual(target.read_text(), 'synthetic-private-marker')

    def test_link_swap_after_preview_is_rejected(self):
        proposal = self.review()
        target = self.root / 'other-note-file'
        target.write_text(self.original)
        self.path.unlink()
        self.path.symlink_to(target)
        self.assert_unconfirmed(self.confirm(proposal))
        self.assertEqual(target.read_text(), self.original)
        self.providers.invalidate_snapshot.assert_not_called()

    def test_ambiguous_missing_invalid_or_oversized_memory_is_unavailable(self):
        identifier = self.note_id()
        for body in ('[2026-09-29] note\ncontinuation\n', '[2026-09-29] no newline',
                     '[2026-09-29] note\n' * 40000):
            self.path.write_text(body)
            result = self.ask('edit saved note ' + identifier + ' with corrected')
            self.assert_unconfirmed(result)
            self.assertNotIn('_memory_edit', json.dumps(self.chat.get(self.cid)))
            self.assertEqual(self.path.read_text(), body)
        self.path.write_bytes(b'\xff')
        self.assert_unconfirmed(self.ask('edit saved note ' + identifier + ' with corrected'))
        self.path.unlink()
        result = self.ask('edit saved note ' + identifier + ' with corrected')
        self.assert_unconfirmed(result)
        self.assertFalse(self.path.exists())

    def test_growth_past_store_limit_does_not_drop_other_rows(self):
        row = '[2026-09-29] x\n'
        body = row * (MAX_BYTES // len(row))
        self.path.write_text(body)
        proposal = self.review('x' * 512)
        self.assert_unconfirmed(self.confirm(proposal))
        self.assertEqual(self.path.read_text(), body)

    def test_failure_to_persist_consumption_never_writes_memory(self):
        proposal = self.review()
        with patch.object(self.chat, 'save', side_effect=OSError('synthetic-disk-error')), \
                patch('memory_edit.replace_at') as write:
            with self.assertRaises(OSError):
                self.confirm(proposal)
        write.assert_not_called()
        self.assertEqual(self.path.read_text(), self.original)
        self.providers.invalidate_snapshot.assert_not_called()

    def test_write_failure_is_unconfirmed_consumed_and_does_not_echo_exception(self):
        proposal = self.review()
        with patch('memory_edit.replace_at', side_effect=OSError('/synthetic/private/path')):
            result = self.confirm(proposal)
        self.assert_unconfirmed(result)
        self.assertNotIn('/synthetic/private/path', json.dumps(result))
        self.assertNotIn('_memory_edit', json.dumps(self.persisted()))
        self.assertEqual(self.path.read_text(), self.original)
        self.assert_unconfirmed(self.confirm(proposal))
        self.providers.invalidate_snapshot.assert_not_called()

    def test_atomic_rename_failure_preserves_file_and_cleans_temporary(self):
        proposal = self.review()
        real_replace = os.replace
        def fail_profile(source, target, **kwargs):
            if target == 'profile.md':
                raise OSError('synthetic-rename-failure')
            return real_replace(source, target, **kwargs)
        with patch('memory_store.os.replace', side_effect=fail_profile):
            self.assert_unconfirmed(self.confirm(proposal))
        self.assertEqual(self.path.read_text(), self.original)
        self.assertFalse(list(self.path.parent.glob('.profile-*')))

    def test_readback_failure_or_mismatch_remains_unconfirmed_and_cannot_replay(self):
        for mismatch in (False, True):
            with self.subTest(mismatch=mismatch):
                self.path.write_text(self.original)
                proposal = self.review()
                initial = read_memory(self.root)
                second = dict(initial, text=initial['text'] + '[2026-09-29] unexpected\n') if mismatch else OSError('synthetic-read-error')
                with patch('memory_edit.read_at', side_effect=[initial, second]):
                    result = self.confirm(proposal)
                self.assert_unconfirmed(result)
                self.assertIn('buy almond milk', self.path.read_text())
                self.providers.invalidate_snapshot.assert_not_called()
                self.path.write_text(self.original)
                self.chat.close()
                self.chat = self.open_chat()
                self.assert_unconfirmed(self.confirm(proposal))
                self.assertEqual(self.path.read_text(), self.original)

    def test_lost_final_receipt_after_verified_write_cannot_replay(self):
        proposal = self.review()
        request = str(uuid.uuid4())
        save = self.chat.save
        def consumed_only(value):
            if value['messages'][-1]['content'].startswith('Correction outcome not yet verified.'):
                return save(value)
            raise OSError('synthetic receipt failure')
        with patch.object(self.chat, 'save', side_effect=consumed_only):
            with self.assertRaises(OSError):
                self.confirm(proposal, request=request)
        self.assertIn('buy almond milk', self.path.read_text())
        self.path.write_text(self.original)
        self.chat.close()
        self.chat = self.open_chat()
        result = self.confirm(proposal, request=request)
        self.assertIn('outcome not yet verified', result['messages'][-1]['content'])
        self.assert_unconfirmed(result)
        self.assert_unconfirmed(self.confirm(proposal))
        self.assertEqual(self.path.read_text(), self.original)

    def test_busy_lock_is_unconfirmed_without_mutation(self):
        proposal = self.review()
        with (self.path.parent / 'profile.lock').open('r+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            with patch('memory_store.LOCK_SECONDS', .01):
                self.assert_unconfirmed(self.confirm(proposal))
        self.assertEqual(self.path.read_text(), self.original)

    def test_concurrent_confirmations_edit_at_most_once(self):
        proposal = self.review()
        with ThreadPoolExecutor(max_workers=5) as pool:
            results = list(pool.map(lambda _: self.confirm(proposal), range(5)))
        self.assertEqual(sum(result['messages'][-1].get('memory_edit_receipt', {}).get('state') == 'verified'
                             for result in results), 1)
        self.providers.invalidate_snapshot.assert_called_once()

    def test_append_and_removal_share_correction_lock_and_version_check(self):
        for operation in ('append', 'remove'):
            for _ in range(5):
                self.path.write_text(self.original)
                identifier, other = self.note_id(), self.note_id(1)
                appended = '[2026-10-01] concurrent addition\n'
                with ThreadPoolExecutor(max_workers=2) as pool:
                    edit = pool.submit(memory_edit.replace, self.root, identifier, 'buy almond milk', lambda: None)
                    competing = pool.submit(append_memory, self.root, appended) if operation == 'append' else \
                        pool.submit(remove, self.root, other)
                    edited, removed = False, False
                    try:
                        edit.result(timeout=5)
                        edited = True
                    except Changed:
                        pass
                    try:
                        competing.result(timeout=5)
                        removed = operation == 'remove'
                    except Changed:
                        self.assertEqual(operation, 'remove')
                        self.assertTrue(edited)
                expected = self.original.replace('buy oat milk', 'buy almond milk') if edited else self.original
                if operation == 'append':
                    expected += appended
                elif removed:
                    self.assertFalse(edited)
                    expected = self.original.splitlines(keepends=True)[0]
                self.assertEqual(self.path.read_text(), expected)

    def test_unavailable_invalidation_does_not_claim_success_or_mutate(self):
        proposal = self.review()
        self.providers.invalidate_snapshot = None
        self.assert_unconfirmed(self.confirm(proposal))
        self.assertEqual(self.path.read_text(), self.original)

    def test_fresh_full_and_lite_provider_snapshots_reflect_correction(self):
        provider = Providers(self.root, self.redact, runner=Mock(side_effect=AssertionError('no provider')))
        self.chat.providers = provider
        with patch('handback.compact_digest', return_value=''), \
                patch('live_status_snapshot.build_live_status_snapshot', side_effect=OSError('offline')), \
                patch('music_notebook.snapshot_for_prompt', return_value=''), \
                patch('providers.time.monotonic', return_value=1234):
            for lite in (False, True):
                before = provider.snapshot(lite=lite)
                self.assertIn('buy oat milk', json.dumps(before))
                self.assertIs(before, provider.snapshot(lite=lite))
            proposal = self.review()
            self.confirm(proposal)
            self.assertIsNone(provider._snapshot_cache)
            self.assertIsNone(provider._snapshot_cache_lite)
            for lite in (False, True):
                after = provider.snapshot(lite=lite)
                self.assertNotIn('buy oat milk', json.dumps(after))
                self.assertIn('buy almond milk', json.dumps(after))
        provider.run.assert_not_called()

    def test_edit_and_removal_revoke_each_other_without_changing_removal(self):
        identifier = self.note_id()
        remove = self.ask('remove saved note ' + identifier)['messages'][-1]['action_card']['proposal_id']
        edit = self.review()
        self.assertNotIn('pending_memory_removal', self.chat.get(self.cid))
        self.assert_unconfirmed(self.ask('yes, remove saved note proposal ' + remove))
        self.assertEqual(self.path.read_text(), self.original)
        self.assert_unconfirmed(self.confirm(edit))
        edit = self.review()
        remove = self.ask('remove saved note ' + identifier)['messages'][-1]['action_card']['proposal_id']
        self.assertNotIn('_memory_edit', json.dumps(self.chat.get(self.cid)))
        result = self.ask('yes, remove saved note proposal ' + remove)
        self.assertIn('Removed one', result['messages'][-1]['content'])
        self.assertEqual(self.path.read_text(), self.original.split('\n', 1)[1])
        self.assert_unconfirmed(self.confirm(edit))


if __name__ == '__main__':
    unittest.main()
