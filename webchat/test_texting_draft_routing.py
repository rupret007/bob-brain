"""Socket-free regressions for texting's interaction with personal drafts."""
import copy
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError
import uuid

from app import Chat
from texting import Andrea, DELIVERY_UNCONFIRMED, SENT_VIA_ANDREA, Texting, TextingError
from texting_fixture import OfflineProviders


class TextingDraftRoutingTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.providers = OfflineProviders()
        self.texting = Texting(bluebubbles=Mock(),
                              andrea=Andrea('http://127.0.0.1:4316', 'fixture-secret'))
        self.texting.resolve = Mock(return_value=dict(guid='iMessage;-;fixture',
            displayName='Andrea', participants=[dict(address='fixture@example.test')]))
        self.texting.instinct.is_target = Mock(return_value=False)
        self.texting.instinct.prepare_body = Mock(side_effect=lambda target, body: body)
        self.texting.andrea.prepare = Mock(side_effect=lambda draft: dict(
            draftId='a' * 64, digest=Andrea.scope_digest(Andrea.scope(draft)),
            actionId='fixture-action', challenge=draft['token'], expiresAt=draft['expires_at'] * 1000))
        self.texting.andrea.cancel = Mock()
        self.network = patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('network forbidden'))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.chat = Chat(root / 'chat', root, self.providers, texting=self.texting)
        self.addCleanup(self.chat.close)
        self.cid = self.chat.new_conversation()['id']

    def say(self, text):
        return self.chat.submit(self.cid, text, str(uuid.uuid4()), actor='fixture')['messages'][-1]

    def disk(self):
        return json.loads((self.chat.state / (self.cid + '.json')).read_text())

    def test_bare_approvals_use_texting_and_clear_stale_work_in_one_save(self):
        self.say('Email Mike hello')
        for phrase in ('draft reply to Andrea: Hello', 'yes', 'ok', 'send it', 'send it now', 'do it'):
            with self.subTest(phrase=phrase):
                pending = dict(pending_job='old work', pending_job_id='job',
                               pending_council='old council', pending_council_id='council')
                self.chat.conversations[self.cid].update(pending)
                with patch.object(self.chat, 'save', wraps=self.chat.save) as save:
                    answer = self.say(phrase)
                self.assertEqual(save.call_count, 1)
                self.assertEqual(answer['provider'], 'texting')
                if phrase.startswith('draft'):
                    self.assertTrue(answer['content'].endswith('OK to send this to Andrea?'))
                else:
                    self.assertIn('Nothing sent', answer['content'])
                    self.assertIn('exact', answer['content'])
                disk = self.disk()
                self.assertEqual(disk, self.chat.conversations[self.cid])
                self.assertTrue(pending.keys().isdisjoint(disk))
                self.assertNotIn('_personal_action', disk)
        self.assertFalse(self.providers.calls)

    def test_unavailable_text_replaces_previous_draft_in_one_save(self):
        self.say('Email Mike hello')
        self.texting.resolve.side_effect = TextingError('Text transport is not configured.')
        with patch.object(self.chat, 'save', wraps=self.chat.save) as save:
            answer = self.say('Text Andrea that hello')
        self.assertEqual(save.call_count, 1)
        self.assertIn('pending your OK', answer['content'])
        self.assertEqual(self.disk()['_personal_action']['kind'], 'text')
        self.assertEqual(self.disk()['_personal_action']['state'], 'draft')
        self.assertEqual(self.disk(), self.chat.conversations[self.cid])

    def test_recipient_resolution_errors_never_become_personal_drafts(self):
        threads = [dict(guid='iMessage;-;alex-one', displayName='Alex unavailable',
                        participants=[dict(address='one@example.test')]),
                   dict(guid='SMS;-;alex-two', displayName='Alex not configured',
                        participants=[dict(address='two@example.test')]),
                   dict(guid='iMessage;-;unverified', displayName='Unverified', participants=[])]
        self.texting.bluebubbles.chats.return_value = threads
        self.texting.bluebubbles.exact_chat.return_value = []
        cases = [('Alex', 'Several threads match'), ('Nobody', 'No matching thread'),
                 ('iMessage;-;missing', 'No matching thread'),
                 ('Unverified', 'could not verify')]
        with patch.object(self.texting, 'resolve', Texting.resolve.__get__(self.texting)), \
                patch.object(self.texting.andrea, 'deliver') as deliver:
            for target, error in cases:
                for command in (f'draft reply to {target}: Hello', f'Text {target} that Hello'):
                    with self.subTest(command=command):
                        answer = self.say(command)
                        self.assertIn(error, answer['content'])
                        self.assertNotIn('text_draft', answer)
                        saved = self.disk()
                        self.assertNotIn('_personal_action', saved)
                        self.assertFalse(saved.get('_texting', {}).get('drafts'))
            self.texting.andrea.prepare.assert_not_called()
            deliver.assert_not_called()
        self.assertFalse(self.providers.calls)

    def test_consumed_consent_is_saved_before_delivery_and_bare_yes_keeps_outcome(self):
        for delivered, expected in ((None, 'Delivery remains unconfirmed'), ('sent', SENT_VIA_ANDREA)):
            with self.subTest(delivered=delivered):
                card = self.say('Text Andrea that hello')['text_draft']

                def handoff(*args):
                    saved = self.disk()
                    draft = saved['_texting']['drafts'][card['id']]
                    self.assertEqual(draft['state'], 'delivery_unconfirmed')
                    self.assertIsNone(draft['token'])
                    self.assertEqual(saved['messages'][-1]['content'], DELIVERY_UNCONFIRMED)
                    return delivered

                with patch.object(self.texting.andrea, 'deliver', side_effect=handoff) as deliver:
                    with patch.object(self.chat, 'save', wraps=self.chat.save) as save:
                        self.say(card['confirm_message'])
                    self.assertEqual(save.call_count, 2)
                    recorded = copy.deepcopy(self.disk()['_texting'])
                    for command in ('cancel text', 'yes wbtxt-invalid', 'yes'):
                        answer = self.say(command)
                        self.assertEqual(answer['provider'], 'texting')
                        self.assertIn(expected, answer['content'])
                        self.assertNotIn('Nothing sent', answer['content'])
                        self.assertEqual(self.disk()['_texting'], recorded)
                    deliver.assert_called_once()

    def test_invalid_receipts_and_unavailable_refresh_keep_exact_reply(self):
        for receipt in ({}, {'ok': False}, {'ok': True}, {'ok': True, 'messageGuid': ''},
                        {'ok': True, 'messageGuid': ' '}, {'ok': True, 'messageGuid': 1}):
            with self.subTest(receipt=receipt):
                card = self.say('Text Andrea that hello')['text_draft']
                with patch('texting.request_json', return_value=receipt) as request:
                    answer = self.say(card['confirm_message'])
                request.assert_called_once()
                self.assertEqual(answer['content'], DELIVERY_UNCONFIRMED)
                self.assertEqual(self.disk()['messages'][-1]['content'], DELIVERY_UNCONFIRMED)
                with patch.object(self.texting.andrea, 'check_delivery', return_value=None):
                    answer = self.say('check text delivery ' + card['id'])
                self.assertIn(DELIVERY_UNCONFIRMED, answer['content'])

    def test_http_500_preserves_unconfirmed_reply_without_leaking_response(self):
        card = self.say('Text Andrea that hello')['text_draft']
        error = HTTPError('http://127.0.0.1:4316/?secret=fixture-secret', 500,
                          'fixture-secret', {}, io.BytesIO(b'private server response'))
        with patch('urllib.request.OpenerDirector.open', side_effect=error):
            answer = self.say(card['confirm_message'])
        self.assertEqual(answer['content'], DELIVERY_UNCONFIRMED)
        saved = json.dumps(self.disk())
        self.assertNotIn('fixture-secret', saved)
        self.assertNotIn('private server response', saved)


if __name__ == '__main__':
    unittest.main()
