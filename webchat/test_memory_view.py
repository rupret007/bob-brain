"""Private deterministic memory inspection; no provider or outbound side effects."""
import json
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest.mock import patch

from app import Chat
from memory_store import append_memory
from memory_view import inspect, matches
from texting import Texting
from texting_fixture import OfflineProviders


class MemoryViewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.provider = OfflineProviders()
        self.chat = Chat(self.root / 'conductor/webchat', self.root, self.provider)
        self.cid = self.chat.new_conversation()['id']

    def tearDown(self):
        self.chat.close()
        self.tmp.cleanup()

    def ask(self, text='show my saved memories', request=None):
        return self.chat.submit(self.cid, text, request or str(uuid.uuid4()))

    def test_saved_notes_are_read_directly_and_do_not_enter_model_history(self):
        note = '[2026-09-29] Private fixture copper-puffin-739.\n'
        append_memory(self.root, note)
        profile = self.root / 'conductor/webchat/memory/profile.md'
        before = profile.read_bytes()
        request = str(uuid.uuid4())
        result = self.ask(request=request)
        answer = result['messages'][-1]
        self.assertEqual(answer['provider'], 'memory')
        self.assertIn(note.strip(), answer['content'])
        self.assertTrue(answer['private_memory'])
        self.assertIn('not all profile or chat context', answer['content'])
        self.assertNotIn('copper-puffin', json.dumps(Texting.provider_view(self.chat.conversations[self.cid])))
        self.assertEqual(self.ask(request=request), result)
        self.assertEqual(profile.read_bytes(), before)
        self.assertEqual(self.provider.calls, [])

    def test_empty_error_and_truncated_reads_are_distinct_and_redacted(self):
        self.assertIn('No saved Web Bob notes', self.ask()['messages'][-1]['content'])
        with patch('memory_view.read_memory', side_effect=OSError('/private/path/detail')):
            reply = self.ask()['messages'][-1]['content']
            self.assertIn('may still exist', reply)
            self.assertNotIn('/private/path', reply)
            self.assertNotIn('No saved', reply)
        append_memory(self.root, '[2026-09-29] ' + self.chat.password + '\n')
        reply = self.ask()['messages'][-1]['content']
        self.assertNotIn(self.chat.password, reply)
        self.assertIn('[secret removed]', reply)
        with patch('memory_view.read_memory', return_value=dict(text='[2026-09-29] Latest excerpt\n', truncated=True)) as read:
            self.assertIn('older notes are not shown', self.ask()['messages'][-1]['content'])
            self.assertEqual(read.call_args.kwargs['budget'], 16000)

    def test_identical_entries_collapse_only_in_display(self):
        first, second = '[2026-09-28] same fact\n', '[2026-09-29] same fact\n'
        append_memory(self.root, first + first + second)
        reply = inspect(self.root, lambda text: text)
        self.assertEqual(reply.count(first.strip()), 1)
        self.assertEqual(reply.count(second.strip()), 1)
        self.assertIn('shown once', reply)
        self.assertEqual((self.root / 'conductor/webchat/memory/profile.md').read_text(), first + first + second)

    def test_base_profile_and_text_threads_are_not_read(self):
        base = self.root / 'bob-brain/memory/profile.md'
        base.parent.mkdir(parents=True)
        base.write_text('Private baseline fixture')
        with patch.object(self.chat.texting.bluebubbles, 'chats') as read:
            reply = self.ask('what do you remember about me?')['messages'][-1]['content']
            read.assert_not_called()
        self.assertNotIn('Private baseline fixture', reply)
        self.assertIn('Other profile or chat context may still exist', reply)

    def test_inspection_revokes_pending_approvals_without_saving(self):
        self.ask('remember that this pending fact must not be saved')
        conv = self.chat.conversations[self.cid]
        conv.update(pending_job='do work', pending_job_id='job', pending_council='review', pending_council_id='council')
        self.ask()
        conv = self.chat.conversations[self.cid]
        for key in ('pending_memory', 'pending_memory_id', 'pending_job', 'pending_job_id', 'pending_council', 'pending_council_id'):
            self.assertNotIn(key, conv)
        self.assertFalse((self.root / 'conductor/webchat/memory/profile.md').exists())
        self.assertEqual(self.provider.calls, [])

    def test_exact_questions_do_not_capture_actions_quotes_or_prefixes(self):
        self.assertTrue(matches('Show my saved memories!'))
        for text in ('remember that my saved memories are private', 'send a text to Alex: show my memory',
                     '"show my memory"', 'show my memory and send it to Alex', 'delete my saved memories'):
            self.assertFalse(matches(text))

    def test_private_notes_do_not_follow_links(self):
        target = self.root / 'outside.txt'
        target.write_text('Do not follow this private fixture')
        folder = self.root / 'conductor/webchat/memory'
        folder.mkdir()
        (folder / 'profile.md').symlink_to(target)
        reply = self.ask()['messages'][-1]['content']
        self.assertIn('could not read', reply)
        self.assertNotIn(target.read_text(), reply)
