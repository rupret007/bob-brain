"""Page reads never recover dispatch intents or acknowledge durable task results."""
import copy
import threading
import time
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from app import Chat, Server
from task_dispatch import task_queue
from test_webchat import Fixture
import test_webchat


class ReadIsolationTests(Fixture):
    def pending_intent(self):
        request = str(uuid.uuid4())
        # Simulate a crash after saving an accepted intent but before queue append.
        with patch.object(task_queue, 'enqueue', side_effect=OSError('private fixture interruption')):
            with self.assertRaises(OSError):
                self.chat.submit(self.identifier, 'Start a job: Explain an imaginary amber cloud.', request)
        self.assertTrue(self.chat.get(self.identifier)['messages'][-1].get('dispatch_intent'))
        return request

    def bytes(self):
        return {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def finished_task(self):
        row = task_queue.enqueue(self.root, self.identifier, str(uuid.uuid4()), 'Explain a private fixture cloud.', worker='gemini')
        claimed = task_queue.claim(self.root, 'gemini')
        task_queue.transition(self.root, row['id'], claimed['claim_token'], 'running')
        return task_queue.transition(self.root, row['id'], claimed['claim_token'], 'succeeded', result='Private fixture result.')

    def test_history_does_not_replay_saved_intent(self):
        self.pending_intent()
        before, value = self.bytes(), copy.deepcopy(self.chat.get(self.identifier))
        for _ in range(3):
            self.chat.history(self.identifier)
        self.assertEqual(self.bytes(), before)
        self.assertEqual(self.chat.get(self.identifier), value)
        self.assertFalse(task_queue.tasks(self.root))
        # Recovery still runs explicitly and stays idempotent.
        self.chat.reconcile_tasks()
        self.chat.reconcile_tasks()
        self.assertEqual(len(task_queue.tasks(self.root)), 1)
        self.assertTrue(self.chat.history(self.identifier)['messages'][-1]['task_id'])

    def test_history_does_not_acknowledge_finished_result(self):
        row = self.finished_task()
        before = self.bytes()
        self.chat.history(self.identifier)
        self.assertEqual(self.bytes(), before)
        self.assertIsNone(task_queue.tasks(self.root)[row['id']]['delivered_at'])
        self.chat.reconcile_tasks()
        self.chat.reconcile_tasks()
        results = [m for m in self.chat.history(self.identifier)['messages'] if m.get('task_status')]
        self.assertEqual(len(results), 1)
        self.assertIn('Private fixture result', results[0]['content'])
        self.assertIsNotNone(task_queue.tasks(self.root)[row['id']]['delivered_at'])

    def test_background_recovers_and_delivers_without_a_page_read(self):
        self.pending_intent()
        row = self.finished_task()
        completed = threading.Event()
        failures = []
        self.fake.start_probes = lambda: None
        self.fake.circuit = SimpleNamespace(log=lambda *a, **k: failures.append((a, k)))
        reconcile = self.chat.reconcile_tasks
        def tick():
            reconcile()
            completed.set()
        with patch.object(self.chat, 'reconcile_tasks', side_effect=tick):
            self.chat.start_background()
            try:
                self.assertTrue(completed.wait(4))
            finally:
                self.chat.close()
        self.assertEqual(failures, [])
        self.assertEqual(len(task_queue.tasks(self.root)), 2)
        self.assertIsNotNone(task_queue.tasks(self.root)[row['id']]['delivered_at'])
        self.assertEqual(len([m for m in self.chat.history(self.identifier)['messages'] if m.get('task_status')]), 1)

    def test_explicit_resume_recovers_only_after_permission_is_durable(self):
        self.pending_intent()
        self.chat.submit(self.identifier, 'Hold off.', str(uuid.uuid4()))
        self.chat.reconcile_tasks()
        self.assertFalse(task_queue.tasks(self.root))
        with patch.object(self.chat, 'save', side_effect=OSError('private fixture storage error')):
            with self.assertRaises(OSError):
                self.chat.submit(self.identifier, 'Resume.', str(uuid.uuid4()))
        self.assertFalse(task_queue.tasks(self.root))
        request = str(uuid.uuid4())
        value = self.chat.submit(self.identifier, 'Resume.', request)
        self.assertEqual(len(task_queue.tasks(self.root)), 1)
        self.assertTrue(any(m.get('task_id') for m in value['messages']))
        before = self.bytes()
        self.chat.submit(self.identifier, 'Resume.', request)
        self.assertEqual(self.bytes(), before)

    def test_shutdown_defers_intent_and_result_recovery(self):
        self.pending_intent()
        row = self.finished_task()
        self.chat.close()
        before = self.bytes()
        self.chat.reconcile_tasks()
        self.assertEqual(self.bytes(), before)
        self.assertEqual(list(task_queue.tasks(self.root)), [row['id']])
        replacement = Chat(self.folder, self.root, self.fake)
        try:
            self.assertEqual(len(task_queue.tasks(self.root)), 2)
            self.assertIsNotNone(task_queue.tasks(self.root)[row['id']]['delivered_at'])
            self.assertEqual(len([m for m in replacement.history(self.identifier)['messages'] if m.get('task_status')]), 1)
        finally:
            replacement.close()

    def test_shutdown_defers_legacy_migration_until_restart(self):
        filename = 'private-legacy-fixture.md'
        path = self.root / 'next-prompts' / filename
        path.parent.mkdir(parents=True)
        path.write_text('## Task\n\nExplain a private legacy fixture cloud.\n')
        value = self.chat.get(self.identifier)
        value['messages'].append(dict(id=str(uuid.uuid4()), request_id=str(uuid.uuid4()), role='assistant',
            status='done', content='Previously queued.', created_at=time.time(),
            action_card=dict(state='queued', queue_id=filename)))
        self.chat.save(value)
        self.chat.close()
        before = self.bytes()
        self.chat.migrate_legacy_tasks()
        self.assertEqual(self.bytes(), before)
        replacement = Chat(self.folder, self.root, self.fake)
        try:
            self.assertEqual(len(task_queue.tasks(self.root)), 1)
            self.assertTrue(replacement.history(self.identifier)['messages'][-1]['task_id'])
        finally:
            replacement.close()


class ReadHTTPTests(Fixture):
    def setUp(self):
        super().setUp()
        self.server = Server(('127.0.0.1', 0), self.chat)
        self.port = self.server.server_address[1]
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()
        self.origin = 'http://127.0.0.1:' + str(self.port)
        self.cookie, self.csrf = '', ''

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join(2)
        super().tearDown()

    request = test_webchat.HTTPTests.request
    login = test_webchat.HTTPTests.login
    pending_intent = ReadIsolationTests.pending_intent
    bytes = ReadIsolationTests.bytes

    def test_authenticated_get_and_head_do_not_dispatch_or_repair(self):
        self.login()
        self.pending_intent()
        row = task_queue.enqueue(self.root, self.identifier, str(uuid.uuid4()), 'Private queue fixture.')
        journal = self.root / 'conductor/state/queue.jsonl'
        with journal.open('ab') as handle:
            handle.write(b'{"id":')
        before = self.bytes()
        with patch('app.run', return_value=(1, '', '')):
            for method in ('GET', 'HEAD'):
                for path in ('/api/conversations/' + self.identifier, '/api/jobs'):
                    self.assertEqual(self.request(method, path)[0], 200)
        self.assertEqual(self.bytes(), before)
        self.assertEqual(list(task_queue.tasks(self.root)), [row['id']])
        self.assertFalse(self.fake.calls)
