"""Saved-history delivery observations through real Chat and authenticated HTTP."""
import copy
import json
import sqlite3
import stat
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

from app import Chat, RequestError, Server
import test_webchat as harness


class ReplyDeliveryRuntimeTests(harness.Fixture):
    def completed(self):
        request = str(uuid.uuid4())
        self.chat.submit(self.identifier, 'Describe an imaginary small purple cloud.', request)
        self.wait()
        message = self.chat.history(self.identifier)['messages'][-1]
        return request, message, dict(message_id=message['id'], **message['reply_delivery'])

    def test_read_only_history_exposes_stable_exact_identity_without_receipt_write(self):
        _, message, _ = self.completed()
        saved = (self.chat.state / (self.identifier + '.json')).read_bytes()
        for _ in range(3):
            self.assertEqual(self.chat.history(self.identifier)['messages'][-1], message)
        self.assertFalse((self.chat.state / 'reply-receipts.sqlite').exists())
        self.assertEqual((self.chat.state / (self.identifier + '.json')).read_bytes(), saved)
        self.assertNotIn('reply_delivery', self.chat.get(self.identifier)['messages'][-1])

    def test_observation_survives_restart_and_duplicate_submissions_without_sender(self):
        request, message, row = self.completed()
        first = self.chat.acknowledge_replies(self.identifier, [row])
        self.chat.close()
        self.chat = Chat(self.folder, self.root, self.fake)
        replay = self.chat.submit(self.identifier, 'Describe an imaginary small purple cloud.', request)
        self.assertEqual(replay['messages'][-1], message)
        self.assertEqual(self.chat.acknowledge_replies(self.identifier, [row]), first)
        self.assertEqual(len(self.fake.calls), 1)
        self.assertEqual(len(replay['messages']), 2)
        path = self.chat.state / 'reply-receipts.sqlite'
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertNotIn(message['content'].encode(), path.read_bytes())
        self.assertEqual(first['replies'][0]['state'], 'delivered')
        self.assertEqual(first['replies'][0]['attempts'], 0)

    def test_changed_body_artifact_and_foreign_batch_are_rejected_before_any_write(self):
        _, message, row = self.completed()
        foreign = copy.deepcopy(row)
        foreign['message_id'] = str(uuid.uuid4())
        for rows in ([row, foreign], [dict(row, sha256='0' * 64)]):
            with self.assertRaises(RequestError) as error:
                self.chat.acknowledge_replies(self.identifier, rows)
            self.assertEqual(error.exception.status, 409)
            self.assertFalse((self.chat.state / 'reply-receipts.sqlite').exists())
        live = self.chat.get(self.identifier)['messages'][-1]
        live['artifact'] = dict(accepted=True, kind='writing', text='An edited artifact.')
        with self.assertRaises(RequestError):
            self.chat.acknowledge_replies(self.identifier, [row])
        changed = self.chat.history(self.identifier)['messages'][-1]
        self.assertEqual(changed['id'], message['id'])
        self.assertNotEqual(changed['reply_delivery'], message['reply_delivery'])
        self.assertEqual(len(self.fake.calls), 1)

    def test_private_voice_pending_and_cross_conversation_cannot_acknowledge(self):
        _, message, row = self.completed()
        other = self.chat.new_conversation()['id']
        with self.assertRaises(RequestError):
            self.chat.acknowledge_replies(other, [row])
        live = self.chat.get(self.identifier)['messages'][-1]
        for field, value in (('private_memory', True), ('texting', True),
                             ('voice_call_id', 'call-1'), ('status', 'running'),
                             ('reminder_notice', 'occurrence-1'), ('request_id', None)):
            original = copy.deepcopy(live)
            live[field] = value
            self.assertNotIn('reply_delivery', self.chat.history(self.identifier)['messages'][-1])
            with self.assertRaises(RequestError):
                self.chat.acknowledge_replies(self.identifier, [row])
            live.clear(); live.update(original)
        self.assertFalse((self.chat.state / 'reply-receipts.sqlite').exists())

    def test_current_status_cards_do_not_change_the_text_observation(self):
        _, message, row = self.completed()
        self.chat.acknowledge_replies(self.identifier, [row])
        self.chat.get(self.identifier)['messages'][-1]['action_card'] = {'state': 'running'}
        current = self.chat.history(self.identifier)['messages'][-1]
        self.assertEqual(current['reply_delivery'], message['reply_delivery'])
        self.chat.acknowledge_replies(self.identifier, [row])

    def test_long_writing_receipt_stays_private_and_binds_full_artifact(self):
        self.completed()
        live = self.chat.get(self.identifier)['messages'][-1]
        live['content'] = 'A long private writing draft. ' * 2000
        live['artifact'] = dict(text=live['content'], commentary='Review the ending.')
        current = self.chat.history(self.identifier)['messages'][-1]
        row = dict(message_id=current['id'], **current['reply_delivery'])
        self.assertEqual(self.chat.acknowledge_replies(self.identifier, [row])['replies'][0]['state'], 'delivered')
        live['artifact']['commentary'] = 'A different ending.'
        with self.assertRaises(RequestError): self.chat.acknowledge_replies(self.identifier, [row])
        self.assertNotIn(b'A long private writing draft', (self.chat.state/'reply-receipts.sqlite').read_bytes())

    def test_observation_is_not_permission_and_store_failure_preserves_answer(self):
        self.chat.submit(self.identifier, 'Hold all work', str(uuid.uuid4()))
        _, message, row = self.completed()
        holds = copy.deepcopy(self.chat.get(self.identifier)['intent_state']['holds'])
        target = self.root / 'do-not-touch'
        target.write_text('unchanged')
        (self.chat.state / 'reply-receipts.sqlite').symlink_to(target)
        with self.assertRaises(RequestError) as error:
            self.chat.acknowledge_replies(self.identifier, [row])
        self.assertEqual(error.exception.status, 503)
        self.assertEqual(target.read_text(), 'unchanged')
        self.assertEqual(self.chat.history(self.identifier)['messages'][-1], message)
        self.assertEqual(self.chat.get(self.identifier)['intent_state']['holds'], holds)
        self.assertFalse(self.chat.workers)


class ReplyDeliveryHTTPTests(harness.Fixture):
    # Reuse the authenticated HTTP harness without inheriting its test cases.
    request = harness.HTTPTests.request
    login = harness.HTTPTests.login
    completed = ReplyDeliveryRuntimeTests.completed

    def setUp(self):
        super().setUp()
        self.server = Server(('127.0.0.1', 0), self.chat)
        self.port = self.server.server_port
        self.origin = 'http://127.0.0.1:' + str(self.port)
        self.cookie = self.csrf = ''
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(2)
        super().tearDown()

    def test_http_auth_csrf_bounded_batches_and_concurrent_reload_receipts(self):
        _, message, row = self.completed()
        payload = dict(conversation_id=self.identifier, receipts=[row])
        route = '/api/reply-receipts'
        self.assertEqual(self.request('POST', route, payload, auth=False)[0], 401)
        self.login()
        self.assertEqual(self.request('POST', route, payload, headers={'X-CSRF-Token': 'wrong'})[0], 403)
        for rows in (None, [], [row] * 33, [dict(row, approval='send everything')]):
            self.assertEqual(self.request('POST', route, dict(payload, receipts=rows))[0], 400)
        self.assertFalse((self.chat.state / 'reply-receipts.sqlite').exists())
        # Ignore the first response as if it was lost, then simulate two tabs.
        self.assertEqual(self.request('POST', route, payload)[0], 200)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.request('POST', route, payload), range(2)))
        self.assertEqual([r[0] for r in results], [200, 200])
        with sqlite3.connect(self.chat.state / 'reply-receipts.sqlite') as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM replies').fetchone()[0], 1)
        self.assertEqual(len(self.fake.calls), 1)
        history = json.loads(self.request('GET', '/api/conversations/' + self.identifier)[2])
        self.assertEqual(history['messages'][-1], message)
