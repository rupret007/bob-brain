"""Private memory inspection retains its literal source and existing redaction."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import uuid

from app import Chat
from memory_store import append_memory
from texting import Texting
from texting_fixture import OfflineProviders


class PrivateMemorySourceTextTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        network = patch('urllib.request.OpenerDirector.open',
                        side_effect=AssertionError('Memory inspection must not use the network'))
        network.start()
        self.addCleanup(network.stop)
        self.providers = OfflineProviders()
        self.chat = Chat(self.root / 'conductor/webchat', self.root, self.providers)
        self.addCleanup(self.chat.close)
        self.cid = self.chat.new_conversation()['id']
        self.profile = self.root / 'conductor/webchat/memory/profile.md'

    def say(self, text, request_id=None):
        return self.chat.submit(self.cid, text, request_id or str(uuid.uuid4()),
                                actor='fixture')['messages'][-1]

    def test_confirmed_note_is_inspected_literally_without_model_or_storage_changes(self):
        note = 'Keep the original receipt for the lifecycle stage handback'
        proposal = self.say('remember that ' + note)['action_card']['proposal_id']
        self.assertFalse(self.profile.exists())
        saved = self.say('yes, save memory proposal ' + proposal)
        self.assertIn('Saved to durable memory', saved['content'])
        original = self.profile.read_bytes()
        self.assertIn(note, original.decode())

        request_id = str(uuid.uuid4())
        inspected = self.say('show my saved memories', request_id)
        self.assertEqual(inspected['provider'], 'memory')
        self.assertTrue(inspected['private_memory'])
        self.assertIn(note, inspected['content'])
        self.assertEqual(self.say('show my saved memories', request_id), inspected)
        self.assertEqual(self.profile.read_bytes(), original)
        model_history = Texting.provider_view(self.chat.get(self.cid))
        self.assertNotIn(inspected['id'], json.dumps(model_history))
        self.assertEqual(self.providers.calls, [])

    def test_literal_inspection_still_redacts_secrets_and_excludes_private_model_context(self):
        note = 'Receipt: lifecycle stage unverified because no test results were supplied'
        append_memory(self.root, '[2026-10-13] ' + note + ' ' + self.chat.password + '\n')
        original = self.profile.read_bytes()
        inspected = self.say('show my saved memories')
        self.assertIn(note, inspected['content'])
        self.assertNotIn(self.chat.password, inspected['content'])
        self.assertIn('[secret removed]', inspected['content'])
        self.assertTrue(inspected['private_memory'])
        self.assertEqual(self.profile.read_bytes(), original)
        self.assertNotIn(note, json.dumps(Texting.provider_view(self.chat.get(self.cid))))
        self.assertEqual(self.providers.calls, [])


if __name__ == '__main__':
    unittest.main()
