import json
from pathlib import Path
import unittest

from instinct_fixture import InstinctFixture
from teammates import band_mappings, status
from texting import Texting
from task_dispatch import task_queue


class TeammateTests(unittest.TestCase):
    def setUp(self):
        self.f = InstinctFixture()
        self.addCleanup(self.f.close)
        path = self.f.root / 'bin/band_messages_watch_run.py'
        path.parent.mkdir()
        path.write_text("CHATS = [{'name': 'Stalemate', 'chat_guid': 'fixture-band'}]\nraise RuntimeError('must never execute')\n")
        self.mapping = path
        self.f.mock.chats.append(dict(guid='fixture-band', displayName='Stalemate', participants=[]))

    def test_mapping_is_read_as_data_without_executing_watch(self):
        self.assertEqual(band_mappings(self.f.root), [dict(name='Stalemate', guid='fixture-band')])
        self.mapping.write_text('CHATS = run_a_program()')
        self.assertEqual(band_mappings(self.f.root), [])

    def test_unknown_karen_is_not_an_approval(self):
        reply = self.f.answer('Karen QA status')
        self.assertEqual(reply['provider'], 'teammates')
        self.assertIn('unverified', reply['content'])
        self.assertFalse(self.f.providers.calls)

    def test_saved_qa_is_attributed_and_does_not_claim_fresh_review(self):
        path = self.f.root / 'wt-webjam-polish/PRE_KAREN_QA.md'
        path.parent.mkdir()
        path.write_text('Independent Karen review\nremain incomplete.\nKaren\nremains pending.')
        text = self.f.answer('Karen status')['content']
        self.assertIn('pending', text)
        self.assertIn('not a new review or approval', text)
        self.assertIn('PRE_KAREN_QA.md', text)

    def test_band_digest_uses_exact_existing_mapping_and_is_private(self):
        reply = self.f.answer('band desk digest for Stalemate')
        self.assertEqual(reply['provider'], 'teammates')
        self.assertIn('4 messages read', reply['content'])
        self.assertIn(('GET', '/api/v1/chat/fixture-band/message'), self.f.mock.calls)
        self.assertEqual(Texting.provider_view(self.f.chat.conversations[self.f.identifier])['messages'], [])
        self.assertFalse(self.f.providers.calls)
        self.assertFalse(self.f.mock.sends)
        self.assertFalse(task_queue.tasks(self.f.root))

    def test_unknown_band_never_selects_a_different_thread(self):
        reply = self.f.answer('band desk digest for Unknown')
        self.assertIn('No verified band mapping', reply['content'])
        self.assertFalse(self.f.mock.calls)

    def test_symlink_mapping_is_not_read(self):
        self.mapping.unlink()
        self.mapping.symlink_to(self.f.chat.folder / '.password')
        self.assertEqual(band_mappings(self.f.root), [])


if __name__ == '__main__':
    unittest.main()
