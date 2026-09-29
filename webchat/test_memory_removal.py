"""Exact-note removal never deletes real owner data in tests."""
import fcntl
import json
import os
from pathlib import Path
import tempfile
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from app import Chat
from memory_store import append_memory
from texting import Texting
from texting_fixture import OfflineProviders


class MemoryRemovalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.providers = OfflineProviders()
        self.chat = Chat(self.root / 'conductor/webchat', self.root, self.providers)
        self.cid = self.chat.new_conversation()['id']
        self.path = self.root / 'conductor/webchat/memory/profile.md'
        self.original = '[2026-09-29] private copper-puffin\n[2026-09-29] keep café <b>literal</b>\n'
        append_memory(self.root, self.original)

    def tearDown(self):
        self.chat.close()
        self.tmp.cleanup()

    def ask(self, text, cid=None, request=None, **kwargs):
        return self.chat.submit(cid or self.cid, text, request or str(uuid.uuid4()), **kwargs)

    def review(self):
        answer = self.ask('manage saved memories')['messages'][-1]
        note = answer['memory_notes'][0]
        answer = self.ask('remove saved note ' + note['id'])['messages'][-1]
        return answer['action_card']['proposal_id']

    def test_review_confirmation_scope_privacy_and_retry(self):
        base = self.root / 'bob-brain/memory/profile.md'
        base.parent.mkdir(parents=True)
        base.write_text('base profile must remain')
        proposal = self.review()
        self.assertEqual(self.path.read_text(), self.original)
        self.assertNotIn('pending_memory_removal', self.chat.public(self.chat.get(self.cid)))
        self.assertNotIn('copper-puffin', json.dumps(Texting.provider_view(self.chat.get(self.cid))))
        request = str(uuid.uuid4())
        with patch.object(self.providers, 'invalidate_snapshot', create=True) as invalidate:
            result = self.ask('yes, remove saved note proposal ' + proposal, request=request)
            invalidate.assert_called_once()
        self.assertIn('Removed one saved Web Bob note', result['messages'][-1]['content'])
        self.assertIn('chat history', result['messages'][-1]['content'])
        self.assertEqual(self.path.read_text(), self.original.split('\n', 1)[1])
        self.assertEqual(self.ask('yes, remove saved note proposal ' + proposal, request=request), result)
        self.ask('yes, remove saved note proposal ' + proposal)
        self.assertEqual(self.path.read_text(), self.original.split('\n', 1)[1])
        self.assertEqual(base.read_text(), 'base profile must remain')
        self.assertEqual(self.providers.calls, [])

    def test_changed_store_or_other_conversation_cannot_use_approval(self):
        proposal = self.review()
        other = self.chat.new_conversation()['id']
        self.ask('yes, remove saved note proposal ' + proposal, cid=other)
        self.assertEqual(self.path.read_text(), self.original)
        append_memory(self.root, '[2026-09-29] newly added\n')
        result = self.ask('yes, remove saved note proposal ' + proposal)
        self.assertIn('changed', result['messages'][-1]['content'])
        self.assertEqual(self.path.read_text(), self.original + '[2026-09-29] newly added\n')

    def test_interruptions_cancel_and_stale_buttons_do_not_remove(self):
        for interruption in ('never mind memory', 'what can you do', 'my saved memories', 'yes, remove saved note'):
            with self.subTest(interruption=interruption):
                proposal = self.review()
                self.ask(interruption)
                self.ask('yes, remove saved note proposal ' + proposal)
                self.assertEqual(self.path.read_text(), self.original)
        self.review()
        self.ask('yes, remove saved note proposal ' + str(uuid.uuid4()))
        self.assertEqual(self.path.read_text(), self.original)

    def test_duplicate_rows_require_distinct_reviews(self):
        self.path.write_text(self.original + self.original.splitlines(keepends=True)[0])
        proposal = self.review()
        self.ask('yes, remove saved note proposal ' + proposal)
        self.assertEqual(self.path.read_text().count('copper-puffin'), 1)
        self.ask('yes, remove saved note proposal ' + proposal)
        self.assertEqual(self.path.read_text().count('copper-puffin'), 1)

    def test_unsafe_ambiguous_or_oversized_storage_is_not_offered_for_removal(self):
        for body in ('[2026-09-29] a note\ncontinuation\n', '[2026-09-29] no newline',
                     '[2026-09-29] x\n' * 50000):
            self.path.write_text(body)
            result = self.ask('manage saved memories')['messages'][-1]
            self.assertFalse(result.get('memory_notes'))
            self.assertEqual(self.path.read_text(), body)
        self.path.unlink()
        target = self.root / 'outside'
        target.write_text(self.original)
        self.path.symlink_to(target)
        self.assertFalse(self.ask('manage saved memories')['messages'][-1].get('memory_notes'))
        self.assertEqual(target.read_text(), self.original)

    def test_lock_and_atomic_failure_preserve_notes_and_hide_error_details(self):
        proposal = self.review()
        with (self.path.parent / 'profile.lock').open('r+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            with patch('memory_store.LOCK_SECONDS', .01):
                answer = self.ask('yes, remove saved note proposal ' + proposal)['messages'][-1]
        self.assertIn('could not verify', answer['content'])
        self.assertEqual(self.path.read_text(), self.original)
        proposal = self.review()
        real_replace = os.replace
        def fail_profile(source, target, **kwargs):
            if target == 'profile.md':
                raise OSError('/private/secret/path')
            return real_replace(source, target, **kwargs)
        with patch('memory_store.os.replace', side_effect=fail_profile):
            answer = self.ask('yes, remove saved note proposal ' + proposal)['messages'][-1]
        self.assertNotIn('/private', answer['content'])
        self.assertEqual(self.path.read_text(), self.original)
        self.assertFalse(list(self.path.parent.glob('.profile-*')))

    def test_old_selection_after_save_is_refused_and_confirmation_survives_reload(self):
        note = self.ask('manage saved memories')['messages'][-1]['memory_notes'][0]
        append_memory(self.root, '[2026-09-29] concurrent note\n')
        answer = self.ask('remove saved note ' + note['id'])['messages'][-1]
        self.assertNotIn('action_card', answer)
        proposal = self.review()
        self.chat.close()
        self.chat = Chat(self.root / 'conductor/webchat', self.root, self.providers)
        answer = self.ask('yes, remove saved note proposal ' + proposal)['messages'][-1]
        self.assertIn('Removed one', answer['content'])
        self.assertIn('concurrent note', self.path.read_text())

    def test_repeated_concurrent_confirmations_remove_at_most_one(self):
        proposal = self.review()
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(lambda _: self.ask('yes, remove saved note proposal ' + proposal), range(6)))
        self.assertEqual(sum('Removed one' in r['messages'][-1]['content'] for r in results), 1)
        self.assertEqual(self.path.read_text(), self.original.split('\n', 1)[1])

    def test_management_revokes_other_approvals_and_redacts_note_choices(self):
        conv = self.chat.get(self.cid)
        conv.update(pending_job='job', pending_job_id='job', pending_council='council', pending_council_id='council')
        self.ask('remember that an unsaved fixture')
        append_memory(self.root, '[2026-09-29] ' + self.chat.password + '\n')
        result = self.ask('manage saved memories')
        self.assertNotIn(self.chat.password, json.dumps(result))
        for key in ('pending_job', 'pending_job_id', 'pending_council', 'pending_council_id', 'pending_memory'):
            self.assertNotIn(key, self.chat.get(self.cid))
        self.assertEqual(self.providers.calls, [])

    def test_voice_and_explicit_provider_cannot_authorize_removal(self):
        proposal = self.review()
        self.ask('yes, remove saved note proposal ' + proposal, provider='gemini')
        self.assertEqual(self.path.read_text(), self.original)
        proposal = self.review()
        self.chat.voice.token_factory = lambda *_: 'private-fixture-token'
        self.providers.snapshot = lambda **_: []
        owner = 'private-fixture-owner'
        call = self.chat.voice.start(self.cid, owner)['call_id']
        turn = str(uuid.uuid4())
        self.chat.voice.transcript(call, owner, [dict(turn_id=turn, role='user', order=0,
            content='yes, remove saved note proposal ' + proposal)])
        result = self.chat.voice.tool(call, owner, turn)['conversation']['messages'][-1]
        self.assertTrue(result['private_memory'])
        self.assertIn('typed Chat', result['content'])
        self.assertEqual(self.path.read_text(), self.original)
        self.assertEqual(self.providers.calls, [])

    def test_removal_and_append_share_one_cross_process_lock(self):
        from memory_removal import notes, remove, Changed
        from memory_store import read_memory
        from concurrent.futures import ProcessPoolExecutor
        for _ in range(8):
            self.path.write_text(self.original)
            key = notes(read_memory(self.root))[0]['id']
            with ProcessPoolExecutor(max_workers=2) as pool:
                deleted = pool.submit(remove, self.root, key)
                appended = pool.submit(append_memory, self.root, '[2026-09-29] competing save\n')
                appended.result(timeout=5)
                try:
                    deleted.result(timeout=5)
                    expected = self.original.split('\n', 1)[1]
                except Changed:
                    expected = self.original
            self.assertEqual(self.path.read_text(), expected + '[2026-09-29] competing save\n')
            self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_direct_voice_turn_invalidates_typed_removal_approval(self):
        proposal = self.review()
        self.chat.voice.token_factory = lambda *_: 'private-fixture-token'
        self.providers.snapshot = lambda **_: []
        owner = 'private-fixture-owner'
        call = self.chat.voice.start(self.cid, owner)['call_id']
        self.chat.voice.transcript(call, owner, [dict(turn_id=str(uuid.uuid4()), role='user', order=0,
            content='An unrelated spoken turn.')])
        self.chat.voice.end(call, owner)
        answer = self.ask('yes, remove saved note proposal ' + proposal)['messages'][-1]
        self.assertIn('stale', answer['content'])
        self.assertEqual(self.path.read_text(), self.original)

    def test_prior_confirm_button_is_disabled_after_intervening_turn(self):
        proposal = self.review()
        result = self.ask('what can you do')
        card = next(m['action_card'] for m in result['messages'] if m.get('action_card', {}).get('proposal_id') == proposal)
        self.assertFalse(card['executable'])
        self.assertEqual(card['state'], 'superseded')
