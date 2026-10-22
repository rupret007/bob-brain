"""Scheduler admission must be verified; no raw queue or worker fallback."""
import concurrent.futures
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from storypool_actions import StoryPoolActions, UNAVAILABLE
from storypool_task_queue import (CHECKS, OwnerTaskQueue, QueueUnavailable,
    SchedulerNotInstalled, enqueue_installed_owner_task, installed_scheduler)


class OwnerTaskQueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.token = 'wbsp-' + 'a' * 32
        self.scheduler = Mock(side_effect=self.receipt)
        self.queue = OwnerTaskQueue(self.root, self.scheduler, clock=lambda: 1000)

    def receipt(self, request):
        return dict({k: v for k, v in request.items() if k != 'description'},
                    receipt_id='owner-task-1', state='queued', admitted_at=1000,
                    codex_weekly_pct=22.6, checks={k: True for k in CHECKS})

    def enqueue(self, **kw):
        return self.queue.enqueue(kw.get('description', 'Add Web Bob chat tests'),
                                  kw.get('token', self.token), kw.get('head', 'b' * 40))

    def test_fixed_repo_provider_branch_and_full_head_in_receipt(self):
        self.assertIn('accepted', self.enqueue())
        request = self.scheduler.call_args.args[0]
        self.assertEqual(request['repo'], 'rupret007/bob-brain')
        self.assertEqual(request['head_sha'], 'b' * 40)
        self.assertEqual(request['provider'], 'codex')
        self.assertTrue(request['branch'].startswith('draft/webbob-task-'))
        self.assertNotIn(self.token, json.dumps(request))

    def test_restart_or_racing_calls_do_not_duplicate_admission(self):
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            answers = list(pool.map(lambda _: self.enqueue(), range(2)))
        self.assertEqual(answers[0], answers[1])
        self.queue = OwnerTaskQueue(self.root, self.scheduler, clock=lambda: 1000)
        self.assertEqual(answers[0], self.enqueue())
        self.scheduler.assert_called_once()

    def test_approval_cannot_be_reused_with_different_task_or_head(self):
        self.enqueue()
        for kw in ({'description': 'Different task'}, {'head': 'c' * 40}):
            with self.assertRaises(QueueUnavailable):
                self.enqueue(**kw)
        self.scheduler.assert_called_once()

    def test_timeout_after_admission_is_consumed_not_retried(self):
        self.scheduler.side_effect = TimeoutError('ambiguous admission')
        with self.assertRaises(TimeoutError):
            self.enqueue()
        self.scheduler.side_effect = self.receipt
        with self.assertRaises(QueueUnavailable):
            self.enqueue()
        self.scheduler.assert_called_once()

    def test_every_required_guard_and_policy_fails_closed(self):
        variants = [lambda r, key=key: r['checks'].update({key: False}) for key in CHECKS]
        variants += [lambda r: r.update(head_sha='c' * 40),
                     lambda r: r.update(repo='other/repo'),
                     lambda r: r.update(branch='main'),
                     lambda r: r.update(state='started'),
                     lambda r: r.update(codex_weekly_pct=75),
                     lambda r: r.update(codex_weekly_pct=float('nan')),
                     lambda r: r.update(codex_weekly_pct=True),
                     lambda r: r.update(admitted_at=969),
                     lambda r: r.update(admitted_at=1001),
                     lambda r: r.update(receipt_id='unsafe\nvalue')]
        for index, mutate in enumerate(variants):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as tmp:
                def response(request):
                    result = self.receipt(request)
                    mutate(result)
                    return result
                queue = OwnerTaskQueue(tmp, response, clock=lambda: 1000)
                with self.assertRaises(QueueUnavailable):
                    queue.enqueue('Add tests', self.token, 'b' * 40)

    def test_durable_pending_inbox_is_recorded_without_claiming_lane_admission(self):
        def staged(request):
            return dict({k: v for k, v in request.items() if k != 'description'},
                        receipt_id=request['request_id'], state='awaiting_admission', recorded_at=999)
        self.scheduler.side_effect = staged
        answer = self.enqueue()
        self.assertIn('recorded in the shared StoryPool inbox', answer)
        self.assertIn('no Codex lane has started', answer)
        self.assertNotIn('accepted by', answer)
        self.assertEqual(self.enqueue(), answer)
        self.scheduler.assert_called_once()
        for mutate in (lambda r: r.update(receipt_id='other'),
                       lambda r: r.update(recorded_at=float('nan')),
                       lambda r: r.update(recorded_at=True),
                       lambda r: r.update(head_sha='c' * 40),
                       lambda r: r.update(checks={k: True for k in CHECKS})):
            with tempfile.TemporaryDirectory() as tmp:
                def invalid(request):
                    result = staged(request)
                    mutate(result)
                    return result
                with self.assertRaises(QueueUnavailable):
                    OwnerTaskQueue(tmp, invalid, clock=lambda: 1000).enqueue('Add tests', self.token, 'b' * 40)

    def test_invalid_task_never_reaches_scheduler(self):
        for kw in ({'description': ''}, {'description': 'x' * 2001},
                   {'description': 'merge the change'}, {'description': 'use Grok'},
                   {'description': 'change rad-dad-show-night'},
                   {'head': 'b' * 12}, {'token': 'unapproved'}):
            with self.assertRaises(QueueUnavailable):
                self.enqueue(**kw)
        self.scheduler.assert_not_called()

    def test_missing_installed_backend_does_not_invoke_git_or_worker(self):
        with patch('subprocess.run', side_effect=AssertionError('No process')):
            with self.assertRaises(SchedulerNotInstalled):
                enqueue_installed_owner_task(self.root, self.root, self.root, 'Add tests', self.token)
        self.assertFalse((self.root / 'owner-task-receipts/receipts.json').exists())

    def test_symlink_backend_rejected_before_loading(self):
        package = self.root / 'cluster/control_plane'
        package.mkdir(parents=True)
        source = self.root / 'untrusted.py'
        source.write_text('raise AssertionError("Must not load")')
        (package / 'owner_task_scheduler.py').symlink_to(source)
        with self.assertRaises(SchedulerNotInstalled):
            installed_scheduler(self.root)

    def test_pause_or_invalid_node_control_stops_before_backend_import(self):
        with patch('storypool_task_queue.installed_scheduler') as load:
            for contents in ('{broken', '{"maintenance": true}', '{"maintenance": "false"}'):
                (self.root / 'node-control.json').write_text(contents)
                with self.assertRaises(QueueUnavailable):
                    enqueue_installed_owner_task(self.root, self.root, self.root, 'Add tests', self.token)
            (self.root / 'node-control.json').unlink()
            (self.root / 'conductor').mkdir()
            (self.root / 'conductor/MAINTENANCE').touch()
            with self.assertRaises(QueueUnavailable):
                enqueue_installed_owner_task(self.root, self.root, self.root, 'Add tests', self.token)
            load.assert_not_called()

    def test_actual_approval_route_cannot_bypass_or_replay_queue(self):
        actions = StoryPoolActions(self.root, clock=lambda: 1000,
            execute=lambda action, token: self.queue.enqueue(action['description'], token, 'b' * 40))
        proposal = actions.handle('storypool queue codex task: Add tests', 'chat', 'request', actor='jeff')
        import re
        token = re.search(r'wbsp-[a-f0-9]{32}', proposal)[0]
        self.assertIn('No matching', actions.handle('yes ' + token, 'other', 'approve', actor='jeff'))
        self.scheduler.assert_not_called()
        self.assertIn('accepted', actions.handle('yes ' + token, 'chat', 'approve', actor='jeff'))
        self.assertIn('already consumed', actions.handle('yes ' + token, 'chat', 'again', actor='jeff'))
        self.scheduler.assert_called_once()


if __name__ == '__main__':
    unittest.main()
