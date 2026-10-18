"""StoryPool controls never execute without a fresh, bound owner approval."""
import concurrent.futures
import json
from pathlib import Path
import re
import tempfile
import sys
import types
import unittest
from unittest.mock import Mock, patch
import uuid

from storypool_actions import StoryPoolActions, guarded_executor, UNAVAILABLE


class ActionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.now = 1000
        self.effect = Mock(return_value='confirmed fixture action')
        self.actions = StoryPoolActions(self.folder, execute=self.effect, clock=lambda: self.now)

    def say(self, text, **kwargs):
        return self.actions.handle(text, kwargs.pop('conversation_id', 'chat'),
            kwargs.pop('request_id', str(uuid.uuid4())), actor=kwargs.pop('actor', 'session-jeff'), **kwargs)

    def proposal(self, text='storypool kick dashboard', **kwargs):
        result = self.say(text, **kwargs)
        self.assertIn('No action has run', result)
        self.effect.assert_not_called()
        return re.search(r'wbsp-[a-f0-9]{32}', result)[0]

    def test_status_question_remains_read_only_routing(self):
        self.assertIsNone(self.say('storypool status'))
        self.assertIsNone(self.say('StoryPool: is it working?'))
        self.effect.assert_not_called()

    def test_requires_fresh_exact_separate_ok(self):
        token = self.proposal(request_id='first')
        self.assertIsNone(self.say('yes'))
        self.assertIsNone(self.say('quoted: yes ' + token))
        self.effect.assert_not_called()
        self.assertEqual(self.say('yes ' + token), 'confirmed fixture action')
        self.effect.assert_called_once_with({'kind': 'kick', 'service': 'dashboard'}, token)

    def test_same_request_cannot_approve(self):
        token = self.proposal(request_id='same')
        self.assertIn('not a separate message', self.say('yes ' + token, request_id='same'))
        self.effect.assert_not_called()

    def test_wrong_conversation_and_actor(self):
        token = self.proposal()
        for kwargs in ({'actor': 'other'}, {'conversation_id': 'other'}):
            self.assertIn('No matching', self.say('yes ' + token, **kwargs))
        self.effect.assert_not_called()
        self.assertEqual(self.say('yes ' + token), 'confirmed fixture action')

    def test_expired_and_backward_clock(self):
        for now in (1301, 999):
            self.now = 1000
            token = self.proposal()
            self.now = now
            self.assertIn('expired', self.say('yes ' + token))
        self.effect.assert_not_called()

    def test_restart_cannot_replay_durable_receipt(self):
        token = self.proposal()
        self.say('yes ' + token)
        self.actions = StoryPoolActions(self.folder, execute=self.effect, clock=lambda: self.now)
        self.assertIn('already consumed', self.say('yes ' + token))
        self.effect.assert_called_once()

    def test_ambiguous_failure_cannot_replay(self):
        self.effect.side_effect = RuntimeError('fixture secret must not appear')
        token = self.proposal()
        self.assertEqual(self.say('yes ' + token), UNAVAILABLE)
        self.assertIn('already consumed', self.say('yes ' + token))
        self.effect.assert_called_once()

    def test_durable_consume_before_effect(self):
        def inspect(action, token):
            rows = json.loads((self.actions.folder / 'receipts.json').read_text())
            self.assertEqual(rows[token]['state'], 'claimed')
            return 'confirmed fixture action'
        self.effect.side_effect = inspect
        token = self.proposal()
        self.say('yes ' + token)
        self.effect.assert_called_once()

    def test_cancel_and_supersede(self):
        old = self.proposal()
        fresh = self.proposal('storypool kick watchdog')
        self.assertIn('already consumed', self.say('yes ' + old))
        self.assertIn('cancelled', self.say('cancel ' + fresh))
        self.assertIn('already consumed', self.say('yes ' + fresh))
        self.effect.assert_not_called()

    def test_concurrent_confirm_runs_once(self):
        token = self.proposal()
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            replies = list(pool.map(lambda _: self.say('yes ' + token), range(2)))
        self.assertEqual(replies.count('confirmed fixture action'), 1)
        self.effect.assert_called_once()

    def test_no_actor_worker_voice_or_attachment_effect(self):
        self.assertIn('authenticated typed owner', self.say('storypool kick dashboard', actor=None))
        token = self.proposal()
        self.assertIn('authenticated typed owner', self.say('yes ' + token, allow_effects=False))
        self.effect.assert_not_called()

    def test_saved_hold_blocks_effects_and_allows_cancel(self):
        token = self.proposal()
        self.assertIn('saved chat hold', self.say('yes ' + token, blocked=True))
        self.effect.assert_not_called()
        self.assertIn('cancelled', self.say('cancel ' + token, blocked=True))

    def test_queue_is_only_proposal(self):
        token = self.proposal('storypool queue codex task: add Web Bob tests')
        self.say('yes ' + token)
        self.effect.assert_called_once_with({'kind': 'queue', 'description': 'add Web Bob tests'}, token)

    def test_unknown_service_and_outbound_tasks_fail_closed(self):
        for command in ('storypool kick conductor', 'storypool kick dashboard; rm x',
                        'storypool queue codex task: use Grok', 'storypool queue codex task: merge PR 4',
                        'storypool queue codex task: fix rad-dad-show-night'):
            self.assertNotIn('No action has run', self.say(command))
        self.effect.assert_not_called()

    def test_absent_guarded_adapter_never_claims_success(self):
        self.actions.execute = None
        token = self.proposal()
        self.assertEqual(self.say('yes ' + token), UNAVAILABLE)
        self.effect.assert_not_called()

    def test_guarded_executor_rejects_unknown_action_before_os_calls(self):
        with patch('subprocess.run', side_effect=AssertionError('no OS effect')):
            run = guarded_executor(self.folder, install=self.folder)
            for action in ({'kind': 'shell'}, {'kind': 'kick', 'service': 'conductor'},
                           {'kind': 'queue', 'description': 'merge it'}):
                with self.assertRaises(ValueError):
                    run(action, 'token')


class GuardedAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.client = Mock()
        self.lease = Mock()
        self.lease.__enter__ = Mock(return_value=self.lease)
        self.lease.__exit__ = Mock(return_value=False)
        self.lease_type = Mock(return_value=self.lease)
        self.modules = {
            'cluster.control_plane.coordination': types.SimpleNamespace(
                ClaimClient=types.SimpleNamespace(from_env=Mock(return_value=self.client)), Lease=self.lease_type),
            'cluster.control_plane.node_control': types.SimpleNamespace(is_draining=Mock(return_value=False))}
        self.module_patch = patch.dict(sys.modules, self.modules)
        self.module_patch.start()
        self.addCleanup(self.module_patch.stop)
        self.proc = patch('subprocess.run', return_value=types.SimpleNamespace(stdout='a' * 40))
        self.process = self.proc.start()
        self.addCleanup(self.proc.stop)
        self.addCleanup(lambda: sys.path.remove(str(self.root)) if str(self.root) in sys.path else None)
        self.run = guarded_executor(self.root, install=self.root, data=self.root / 'data')

    def test_service_uses_claim_and_privacy_safe_managed_audit(self):
        with patch('platform.system', return_value='Linux'):
            result = self.run({'kind': 'kick', 'service': 'dashboard'}, 'private-approval-token')
        self.assertIn('confirmed dashboard', result)
        self.client.acquire_task.assert_called_once_with('rupret007/bob-ops-dashboard',
            'webbob-service-dashboard', 'a' * 40, 'nucbox')
        self.assertEqual(self.lease.renew.call_count, 2)
        self.assertIn(['systemctl', '--user', 'restart', 'storypool-dashboard.service'],
                      [call.args[0] for call in self.process.call_args_list])
        journal = (self.root / 'data/chat/HANDOFF.md').read_text()
        self.assertIn('<!-- committed event storypool-control-', journal)
        self.assertNotIn('private-approval-token', journal)

    def test_lost_claim_before_restart_fails_closed(self):
        self.lease.renew.side_effect = [None, RuntimeError('lost claim')]
        with self.assertRaises(RuntimeError):
            self.run({'kind': 'kick', 'service': 'dashboard'}, 'approval')
        self.assertTrue(all(call.args[0][0] == 'git' for call in self.process.call_args_list))

    def test_coordination_unavailable_stops_all_os_effects(self):
        self.modules['cluster.control_plane.coordination'].ClaimClient.from_env.side_effect = RuntimeError('unavailable')
        with self.assertRaises(RuntimeError):
            self.run({'kind': 'kick', 'service': 'watchdog'}, 'approval')
        self.process.assert_not_called()

    def test_draining_and_maintenance_stop_restart(self):
        self.modules['cluster.control_plane.node_control'].is_draining.return_value = True
        with self.assertRaises(RuntimeError):
            self.run({'kind': 'kick', 'service': 'watchdog'}, 'approval')
        self.process.assert_not_called()
        (self.root / 'conductor').mkdir()
        (self.root / 'conductor/MAINTENANCE').touch()
        with self.assertRaises(RuntimeError):
            self.run({'kind': 'kick', 'service': 'watchdog'}, 'approval')
        self.process.assert_not_called()

    def test_unverified_queue_fails_closed_without_legacy_queue(self):
        with patch('actions.queue_once', side_effect=AssertionError('legacy queue forbidden')):
            result = self.run({'kind': 'queue', 'description': 'add Web Bob tests'}, 'approval')
        self.assertIn('was not queued', result)
        self.process.assert_not_called()
        self.client.acquire_task.assert_not_called()


class RuntimeTests(unittest.TestCase):
    def test_chat_routes_controls_without_provider_or_queue(self):
        from app import Chat
        from texting_fixture import OfflineProviders
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            effect = Mock(return_value='confirmed fixture action')
            controls = StoryPoolActions(root / 'private', execute=effect)
            chat = Chat(root / 'webchat', root=root, providers=OfflineProviders(), storypool_actions=controls)
            cid = chat.new_conversation()['id']
            result = chat.submit(cid, 'storypool kick dashboard', str(uuid.uuid4()), actor='jeff')
            self.assertEqual(result['messages'][-1]['provider'], 'storypool-controls')
            token = re.search(r'wbsp-[a-f0-9]{32}', result['messages'][-1]['content'])[0]
            effect.assert_not_called()
            result = chat.submit(cid, 'yes ' + token, str(uuid.uuid4()), actor='jeff')
            self.assertEqual(result['messages'][-1]['content'], 'confirmed fixture action')
            effect.assert_called_once()


if __name__ == '__main__':
    unittest.main()
