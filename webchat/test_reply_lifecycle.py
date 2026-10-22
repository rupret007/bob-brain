"""Deterministic reply admission and late-callback regressions; private providers only."""
import copy
import json
import threading
import time
import uuid
from unittest.mock import patch

from app import RequestError
from failover import AllDown
from test_webchat import Fixture
from voice import VoiceError


class ReplyLifecycleTests(Fixture):
    prompt = 'Describe an imaginary small purple cloud.'

    def test_completed_reply_admits_followup_before_old_thread_returns(self):
        self.completed_followup()

    def test_bookkeeping_error_does_not_leave_completed_reply_reserved(self):
        self.completed_followup(bookkeeping_error=True)

    def completed_followup(self, bookkeeping_error=False):
        published, release_old, second_entered, release_second = (threading.Event() for _ in range(4))
        first_request, second_request = str(uuid.uuid4()), str(uuid.uuid4())
        original_lock = self.chat.lock
        calls, first_thread, explicitly_released = [], [], []
        chat = self.chat
        identifier = self.identifier

        class PublicationBoundary:
            def __enter__(self):
                return original_lock.__enter__()

            def __exit__(self, *args):
                pause = (first_thread and threading.current_thread() is first_thread[0]
                         and not published.is_set()
                         and any(m.get('request_id') == first_request and m.get('role') == 'assistant'
                                 and m.get('status') == 'done'
                                 for m in chat.conversations[identifier]['messages']))
                result = original_lock.__exit__(*args)
                if pause:
                    published.set()
                    explicitly_released.append(release_old.wait(3))
                return result

        def reply(conversation, cancel, progress):
            request = conversation['messages'][-1]['request_id']
            calls.append(request)
            if request == first_request:
                first_thread.append(threading.current_thread())
            else:
                second_entered.set()
                release_second.wait(3)
            return dict(content='An imaginary purple cloud drifts above the lake.', provider='gemini', attempts=[])

        self.chat.lock = PublicationBoundary()
        self.fake.reply = reply
        overlay = self.root / 'private-overlay'
        overlay.mkdir()
        self.chat.overlay_roots[identifier] = overlay
        if bookkeeping_error:
            original_record = self.chat.record_turn
            def record(**kwargs):
                if kwargs.get('request_id') == first_request:
                    raise ValueError('fixture bookkeeping failure')
                return original_record(**kwargs)
            patcher = patch.object(self.chat, 'record_turn', side_effect=record)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(release_old.set)
        self.addCleanup(release_second.set)
        try:
            self.chat.submit(identifier, self.prompt, first_request, provider='gemini')
            self.assertTrue(published.wait(3))
            history = self.chat.history(identifier)
            self.assertEqual(history['messages'][-1]['status'], 'done')
            self.assertFalse(history['reply_stopping'])
            self.chat.submit(identifier, self.prompt, second_request, provider='gemini')
            self.assertTrue(second_entered.wait(3))
            new_worker = self.chat.workers[identifier]
            # Replaying the completed request must not dispatch another reply.
            self.chat.submit(identifier, self.prompt, first_request, provider='gemini')
            release_old.set()
            first_thread[0].join(3)
            self.assertFalse(first_thread[0].is_alive())
            self.assertEqual(explicitly_released, [True])
            self.assertIs(self.chat.workers[identifier], new_worker)
            self.assertEqual(self.chat.overlay_pins[identifier], overlay)
            self.assertEqual(calls, [first_request, second_request])
            release_second.set()
            new_worker['thread'].join(3)
            self.assertFalse(new_worker['thread'].is_alive())
            self.assertNotIn(identifier, self.chat.workers)
            self.assertEqual(len(self.chat.history(identifier)['messages']), 4)
        finally:
            release_old.set()
            release_second.set()
            for worker in first_thread + [v['thread'] for v in list(self.chat.workers.values())]:
                worker.join(3)
            self.chat.lock = original_lock

    def blocked_reply(self, outcome='success'):
        entered, callback, progressed, release = (threading.Event() for _ in range(4))
        def reply(conversation, cancel, progress):
            entered.set()
            callback.wait(3)
            progress('gemini', [{'provider': 'gemini', 'kind': 'network'}])
            progressed.set()
            release.wait(3)
            if outcome == 'queue':
                raise AllDown([], time.time() + 60, 'private retry prompt')
            if outcome == 'error':
                raise RuntimeError('private provider detail')
            return dict(content='Late answer.', provider='gemini', attempts=[])
        self.fake.reply = reply
        self.chat.submit(self.identifier, self.prompt, str(uuid.uuid4()), provider='gemini')
        self.assertTrue(entered.wait(3))
        self.addCleanup(release.set)
        self.addCleanup(callback.set)
        return callback, progressed, release

    def row(self):
        return copy.deepcopy(self.chat.get(self.identifier)['messages'][-1])

    def test_shutdown_refuses_new_turns_before_history_or_effects(self):
        self.chat.close()
        before = (self.chat.state / (self.identifier + '.json')).read_bytes()
        for prompt in (self.prompt, 'Remember: I like amber boats.', 'texting help',
                       'Start a job: write tests for a pretend blue widget.'):
            with self.subTest(prompt=prompt):
                with self.assertRaises(RequestError) as caught:
                    self.chat.submit(self.identifier, prompt, str(uuid.uuid4()))
                self.assertEqual(caught.exception.status, 503)
        self.assertEqual((self.chat.state / (self.identifier + '.json')).read_bytes(), before)
        self.assertEqual(self.fake.calls, [])
        self.assertEqual(self.chat.workers, {})

    def test_shutdown_allows_existing_idempotent_receipt(self):
        request = str(uuid.uuid4())
        self.chat.submit(self.identifier, self.prompt, request, provider='gemini')
        self.wait()
        before = self.chat.history(self.identifier)
        self.chat.close()
        self.assertEqual(self.chat.submit(self.identifier, self.prompt, request, provider='gemini'), before)
        self.assertEqual(len(self.fake.calls), 1)

    def test_shutdown_leaves_waiting_retry_bytes_untouched(self):
        def unavailable(*_):
            raise AllDown([], time.time() - 1, 'private retry prompt')
        self.fake.reply = unavailable
        self.chat.submit(self.identifier, self.prompt, str(uuid.uuid4()), provider='gemini')
        self.wait()
        self.assertEqual(self.row()['status'], 'waiting')
        before = (self.chat.state / (self.identifier + '.json')).read_bytes()
        self.chat.close()
        self.chat.retry_queued()
        self.assertEqual((self.chat.state / (self.identifier + '.json')).read_bytes(), before)
        self.assertEqual(self.row()['status'], 'waiting')

    def test_shutdown_defers_due_reminders_without_changing_history(self):
        self.chat.reminders.create(self.identifier, str(uuid.uuid4()), 'private reminder', time.time() - 1)
        before = (self.chat.state / (self.identifier + '.json')).read_bytes()
        reminders = self.chat.reminders.listing()
        self.chat.close()
        self.chat.deliver_reminders()
        self.assertEqual((self.chat.state / (self.identifier + '.json')).read_bytes(), before)
        self.assertEqual(self.chat.reminders.listing(), reminders)

    def test_initial_running_state_write_failure_releases_worker(self):
        save = self.chat.save
        failed = []
        def fail_once(value):
            if value['messages'] and value['messages'][-1]['status'] == 'running' and not failed:
                failed.append(True)
                raise OSError('private storage detail')
            return save(value)
        with patch.object(self.chat, 'save', side_effect=fail_once):
            self.chat.submit(self.identifier, self.prompt, str(uuid.uuid4()), provider='gemini')
            self.wait()
        self.assertEqual(failed, [True])
        self.assertEqual(self.chat.workers, {})
        self.assertEqual(self.row()['status'], 'error')
        self.assertNotIn('private storage detail', json.dumps(self.chat.history(self.identifier)))
        self.assertEqual(self.fake.calls, [])

    def test_close_cannot_split_an_admitted_submit_from_launch(self):
        entered, release, close_attempted = (threading.Event() for _ in range(3))
        launch = self.chat.launch
        errors = []
        def paused_launch(identifier):
            entered.set()
            release.wait(3)
            return launch(identifier)
        def submit():
            try:
                self.chat.submit(self.identifier, self.prompt, str(uuid.uuid4()), provider='gemini')
            except Exception as exc:
                errors.append(type(exc).__name__)
        def close():
            close_attempted.set()
            self.chat.close()
        with patch.object(self.chat, 'launch', side_effect=paused_launch):
            sender = threading.Thread(target=submit)
            sender.start()
            self.assertTrue(entered.wait(3))
            closer = threading.Thread(target=close)
            closer.start()
            try:
                self.assertTrue(close_attempted.wait(3))
                # Closing must take the same admission lock, rather than set its
                # event while a saved turn has yet to launch.
                self.assertFalse(self.chat.closing.wait(.1))
            finally:
                release.set()
                sender.join(3)
                closer.join(3)
        self.assertFalse(sender.is_alive() or closer.is_alive())
        self.assertEqual(errors, [])
        self.assertIn(self.row()['status'], ('done', 'cancelled'))
        self.assertEqual(self.chat.workers, {})

    def check_timeout(self, outcome):
        callback, progressed, release = self.blocked_reply(outcome)
        info = self.chat.workers[self.identifier]
        info['started_at'] = time.time() - self.chat.reply_deadline() - 1
        self.chat.sweep_stuck()
        timed_out = self.row()
        try:
            self.assertEqual(timed_out['status'], 'error')
            self.assertTrue(self.chat.history(self.identifier)['reply_stopping'])
            callback.set()
            self.assertTrue(progressed.wait(3))
            self.assertEqual(self.row(), timed_out)
            self.assertIs(self.chat.workers[self.identifier], info)
            with self.assertRaises(RequestError):
                self.chat.submit(self.identifier, 'A different question', str(uuid.uuid4()))
        finally:
            callback.set()
            release.set()
            self.wait()
        self.assertEqual(self.row(), timed_out)
        self.assertNotIn('retry_prompt', self.chat.get(self.identifier))
        self.assertEqual(self.chat.workers, {})
        self.assertFalse(self.chat.history(self.identifier)['reply_stopping'])

    def test_timeout_survives_late_progress_and_success(self):
        self.check_timeout('success')

    def test_timeout_survives_late_progress_and_queue(self):
        self.check_timeout('queue')

    def test_timeout_survives_late_progress_and_error(self):
        self.check_timeout('error')

    def test_stop_is_immediate_but_reservation_lasts_through_completion(self):
        callback, progressed, release = self.blocked_reply()
        info = self.chat.workers[self.identifier]
        try:
            self.chat.stop(self.identifier)
            stopped = self.row()
            self.assertEqual(stopped['status'], 'cancelled')
            self.assertTrue(self.chat.history(self.identifier)['reply_stopping'])
            callback.set()
            self.assertTrue(progressed.wait(3))
            self.assertEqual(self.row(), stopped)
            self.assertIs(self.chat.workers[self.identifier], info)
            with self.assertRaises(VoiceError):
                self.chat.voice.start(self.identifier, 'fixture-owner')
            with self.assertRaises(RequestError):
                self.chat.submit(self.identifier, 'Another question', str(uuid.uuid4()))
        finally:
            callback.set()
            release.set()
            self.wait()
        self.assertEqual(self.row(), stopped)
        self.assertEqual(self.chat.workers, {})
        self.assertFalse(self.chat.history(self.identifier)['reply_stopping'])
        self.fake.reply = lambda *_: dict(content='Next answer.', provider='gemini', attempts=[])
        self.chat.submit(self.identifier, self.prompt, str(uuid.uuid4()), provider='gemini')
        self.wait()
        self.assertEqual(self.row()['status'], 'done')

    def test_failed_thread_start_has_durable_error_and_no_phantom_worker(self):
        request = str(uuid.uuid4())
        with patch('app.threading.Thread.start', side_effect=RuntimeError('private launch detail')):
            value = self.chat.submit(self.identifier, self.prompt, request, provider='gemini')
        self.assertEqual(value['messages'][-1]['status'], 'error')
        self.assertNotIn('private launch detail', json.dumps(value))
        self.assertEqual(self.chat.workers, {})
        self.assertEqual(self.chat.overlay_pins, {})
        saved = json.loads((self.chat.state / (self.identifier + '.json')).read_text())
        self.assertEqual(saved['messages'][-1], self.row())
        self.chat.submit(self.identifier, self.prompt, request, provider='gemini')
        self.assertEqual(self.fake.calls, [])
        self.chat.submit(self.identifier, self.prompt, str(uuid.uuid4()), provider='gemini')
        self.wait()
        self.assertEqual(self.row()['status'], 'done')
