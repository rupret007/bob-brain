"""Real Chat draft refusal/privacy boundaries; no transport or model services."""
import copy
import json
import re
import stat
import threading
import uuid
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from app import Chat, Server
from personal_drafts import pending
from reply_delivery import rendering
from shared_chat import SharedChatContext
from test_webbob_replyq_1856 import FakeProviders
from texting import Texting


class OutboundDraftSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.folder = self.root / 'conductor/webchat'
        self.fake = FakeProviders()
        self.shared = SharedChatContext(self.root / 'shared', fetch_engine=lambda *a: {})
        for target in ('app.queue_once', 'urllib.request.OpenerDirector.open'):
            guard = patch(target, side_effect=AssertionError('Unexpected effect: ' + target))
            guard.start()
            self.addCleanup(guard.stop)
        for target in ('live_status_snapshot._screen_sessions', 'live_status_snapshot.process_table'):
            guard = patch(target, return_value={})
            guard.start()
            self.addCleanup(guard.stop)
        self.chat = self.new_chat()
        self.cid = self.chat.new_conversation()['id']
        self.chat.texting.resolve = Mock(return_value=dict(guid='iMessage;-;fixture',
            displayName='Andrea', participants=[dict(address='fixture@example.test')]))
        self.chat.texting.andrea.prepare = Mock(return_value=None)
        self.chat.texting.andrea.cancel = Mock()
        self.chat.texting.andrea.deliver = Mock(side_effect=AssertionError('Must not send'))
        self.chat.texting.instinct.is_target = Mock(return_value=False)
        self.chat.texting.instinct.prepare_body = Mock(side_effect=lambda target, body: body)

    def new_chat(self):
        chat = Chat(self.folder, self.root, self.fake, shared_context=self.shared)
        self.addCleanup(chat.close)
        return chat

    def say(self, text, rid=None):
        answer = self.chat.submit(self.cid, text, rid or str(uuid.uuid4()), actor='fixture')
        info = self.chat.workers.get(self.cid)
        if info:
            info['thread'].join(3)
            self.assertFalse(info['thread'].is_alive())
            answer = self.chat.history(self.cid)
        return answer['messages'][-1]

    def disk(self):
        return json.loads((self.chat.state / (self.cid + '.json')).read_text())

    def test_email_decline_is_final_after_restart_and_request_replay(self):
        self.say('Email Mike hello')
        rid = str(uuid.uuid4())
        answer = self.say("Don't send", rid)
        self.assertIn('declined', answer['content'].lower())
        self.assertEqual(self.disk()['_personal_action']['state'], 'declined')
        self.assertEqual(pending(self.chat, self.chat.get(self.cid)), [])
        self.chat.close()
        self.chat = self.new_chat()
        self.assertEqual(self.say("Don't send", rid), answer)
        for text in ('yes', 'send it', 'go ahead'):
            self.assertIn('declined', self.say(text)['content'].lower())
            self.assertEqual(self.disk()['_personal_action']['state'], 'declined')
        self.assertEqual(self.fake.calls, [])
        self.assertEqual(stat.S_IMODE((self.chat.state / (self.cid + '.json')).stat().st_mode), 0o600)

    def test_text_refusal_cancels_exact_token_and_never_reactivates(self):
        for phrase in ("don't send", 'do not send', 'no', 'do not send that', 'cancel text'):
            draft = self.say('Text Andrea that hello')
            token = re.search(r'yes (wbtxt-[a-f0-9]+)', draft['content'])[1]
            answer = self.say(phrase)
            self.assertIn('cancelled', answer['content'].lower())
            active = self.disk()['_texting']
            row = active['drafts'][active['active']]
            self.assertEqual(row['state'], 'cancelled')
            self.assertIsNone(row['token'])
            self.assertIn('Nothing sent', self.say('yes ' + token)['content'])
        self.chat.texting.andrea.deliver.assert_not_called()
        self.assertEqual(self.fake.calls, [])

    def test_private_email_stays_out_of_provider_coordination_and_reply_journal(self):
        request = str(uuid.uuid4())
        draft = self.say('Email private-person@example.org: private-copper-zebra', request)
        self.assertNotIn('reply_delivery', draft)
        view = Texting.provider_view(self.chat.get(self.cid))
        self.assertNotIn('_personal_action', view)
        self.assertNotIn('private-copper-zebra', json.dumps(view))
        self.assertEqual(self.chat.coordination_records(self.chat.get(self.cid)), [])
        journal = (self.shared.folder / 'HANDOFF.md').read_text()
        self.assertNotIn('private-copper-zebra', journal)
        self.assertNotIn('private-person@example.org', journal)
        self.say("Don't send")
        self.say('Describe an imaginary small purple cloud.')
        self.assertEqual(len(self.fake.calls), 1)
        self.assertNotIn('private-copper-zebra', json.dumps(self.fake.calls))
        self.assertNotIn('private-person@example.org', json.dumps(self.fake.calls))
        self.assertNotIn('_personal_action', json.dumps(self.fake.calls))
        # Private rows remain available to Jeff in authenticated history.
        self.assertIn('private-copper-zebra', json.dumps(self.chat.history(self.cid)))

    def test_missing_email_transport_cannot_collect_standing_send_authority(self):
        reply = self.say("Reply to Mike's email and tell him hello")
        self.assertIn('email sending is unavailable', reply['content'].lower())
        answer = self.say('go ahead')
        self.assertIn('fresh', answer['content'].lower())
        row = self.disk()['_personal_action']
        self.assertEqual(row['state'], 'draft')
        self.assertFalse(row.get('send_authorized', False))
        self.assertFalse(row.get('approval'))
        self.assertEqual(self.fake.calls, [])

    def test_decline_never_releases_hold_and_new_draft_needs_new_review(self):
        self.say('Email Mike hello')
        self.say('Hold all work')
        holds = copy.deepcopy(self.chat.get(self.cid)['intent_state']['holds'])
        self.assertTrue(holds)
        self.say("Don't send")
        self.assertEqual(self.chat.get(self.cid)['intent_state']['holds'], holds)
        self.assertEqual(self.disk()['_personal_action']['state'], 'declined')
        self.say('Email Mike a different body')
        self.assertEqual(self.disk()['_personal_action']['state'], 'declined')

    def test_inline_refusal_and_conditional_cues_only_draft(self):
        for ask in ('Email Mike: hello, draft only', 'Email Mike: hello, provided I agree',
                    'Email Mike: please do not send the old invoice'):
            reply = self.say(ask)
            self.assertTrue(reply['content'].startswith('Draft for '))
            self.assertEqual(self.disk()['_personal_action']['state'], 'draft')
            self.assertEqual(len(pending(self.chat, self.chat.get(self.cid))), 1)
        self.assertEqual(self.fake.calls, [])

    def test_ambiguous_decline_leaves_competing_drafts_unchanged(self):
        self.say('Email Mike hello')
        with patch.object(self.chat.calendar.client, 'configured'):
            self.chat.calendar.draft('create a calendar event Dentist tomorrow at 2pm', self.cid, 'older')
        answer = self.say("Don't send")
        self.assertIn('Which draft', answer['content'])
        self.assertEqual(len(pending(self.chat, self.chat.get(self.cid))), 2)
        self.say('cancel email draft')
        self.assertEqual(self.disk()['_personal_action']['state'], 'declined')
        self.assertEqual(len(pending(self.chat, self.chat.get(self.cid))), 1)
        self.assertEqual(self.fake.calls, [])

    def test_new_draft_does_not_reuse_declined_authority(self):
        first = str(uuid.uuid4())
        self.say('Email Mike hello', first)
        self.say("Don't send")
        self.say('Email Mike hello')
        row = self.disk()['_personal_action']
        self.assertNotEqual(row['request_id'], first)
        self.assertEqual(row['state'], 'draft')
        self.assertNotIn('declined_request_id', row)
        self.assertIn('fresh', self.say('yes')['content'])
        self.assertFalse(self.disk()['_personal_action'].get('approval'))
        self.assertEqual(self.fake.calls, [])

    def test_legacy_private_draft_rows_are_filtered_before_any_new_save(self):
        self.say('Email Mike: legacy-secret-body')
        legacy = copy.deepcopy(self.chat.get(self.cid))
        for message in legacy['messages']:
            message.pop('private_draft', None)
            self.assertIsNone(rendering(message))
        for value in (legacy, dict(legacy, _personal_action={})):
            view = Texting.provider_view(value)
            self.assertEqual(view['messages'], [])
            self.assertNotIn('_personal_action', view)
            self.assertNotIn('legacy-secret-body', json.dumps(view))


class OutboundDraftHTTPTests(unittest.TestCase):
    # Reuse only the existing harness methods; no inherited test duplication.
    from test_webchat import HTTPTests as _Harness
    request = _Harness.request
    login = _Harness.login

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.fake = FakeProviders()
        root = Path(self.tmp.name)
        self.chat = Chat(root / 'chat', root, self.fake)
        self.cid = self.chat.new_conversation()['id']
        self.server = Server(('127.0.0.1', 0), self.chat)
        self.port = self.server.server_port
        self.origin = 'http://127.0.0.1:' + str(self.port)
        self.cookie = self.csrf = ''
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)
        self.chat.close()
        self.tmp.cleanup()

    def test_http_requires_auth_csrf_and_replays_decline_without_any_sender(self):
        payload = dict(conversation_id=self.cid, message='Email Mike hello', request_id=str(uuid.uuid4()))
        self.assertEqual(self.request('POST', '/api/messages', payload, auth=False)[0], 401)
        self.login()
        self.assertEqual(self.request('POST', '/api/messages', payload,
                                      headers={'X-CSRF-Token': 'wrong'})[0], 403)
        self.assertNotIn('_personal_action', self.chat.get(self.cid))
        with patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('Network forbidden')), \
                patch('app.queue_once', side_effect=AssertionError('Dispatch forbidden')):
            self.assertEqual(self.request('POST', '/api/messages', payload)[0], 202)
            decline = dict(payload, message="Don't send", request_id=str(uuid.uuid4()))
            status, _, body = self.request('POST', '/api/messages', decline)
            self.assertEqual(status, 202)
            self.assertIn('declined', json.loads(body)['messages'][-1]['content'])
            for _ in range(2):
                self.assertEqual(self.request('POST', '/api/messages', decline)[2], body)
            saved = json.loads((self.chat.state / (self.cid + '.json')).read_text())
            self.assertEqual(saved['_personal_action']['state'], 'declined')
            history = json.loads(self.request('GET', '/api/conversations/' + self.cid)[2])
            self.assertNotIn('_personal_action', history)
            self.assertTrue(all('reply_delivery' not in m for m in history['messages']))
            self.assertEqual(self.fake.calls, [])
