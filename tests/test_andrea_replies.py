from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from webbob.andrea_replies import AndreaReplies, JeffApproval, ReplyBlocked


class AndreaReplyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = str(Path(self.tmp.name) / 'replies.db')
        self.now = 1000.0
        self.brain = Mock(return_value='Rehearsal is Saturday at 6.')
        self.verify = Mock(return_value=None)
        self.send = Mock()
        self.router = self.open_router()
        self.event = {'id': 'inbound-1', 'chat_guid': 'band-thread',
                      'text': '@andrea when is rehearsal?',
                      'history': [{'chat_guid': 'band-thread', 'text': 'Saturday at 6.'}]}

    def open_router(self):
        router = AndreaReplies(self.path, webbob_draft=self.brain,
                               verify_jeff_approval=self.verify, andrea_send_once=self.send,
                               clock=lambda: self.now)
        self.addCleanup(router.close)
        return router

    def approval(self, draft, **changes):
        return JeffApproval(**dict(event_id='approval-1', principal='jeff', surface='bob_chat',
                                   draft_id=draft['id'], digest=draft['digest'],
                                   approved_at=self.now, decision='send_once') | changes)

    def test_mention_routes_only_to_webbob_and_never_sends(self):
        draft = self.router.on_message(self.event)
        self.assertEqual(draft['state'], 'pending')
        self.assertTrue(draft['text'].startswith('NanoBot: '))
        self.brain.assert_called_once_with({'chat_guid': 'band-thread', 'mention': self.event['text'],
                                           'history': self.event['history'], 'mode': 'draft_only'})
        self.verify.assert_not_called()
        self.send.assert_not_called()

    def test_nonmention_is_quiet(self):
        self.assertIsNone(self.router.on_message(dict(self.event, text='hello')))
        self.brain.assert_not_called()
        self.send.assert_not_called()

    def test_cross_thread_history_blocked_before_brain(self):
        event = dict(self.event, history=[{'chat_guid': 'private-thread', 'text': 'private'}])
        with self.assertRaises(ReplyBlocked):
            self.router.on_message(event)
        self.brain.assert_not_called()
        self.send.assert_not_called()

    def test_no_send_or_standing_permission_flags_on_ingress(self):
        for field in ('approved', 'send', 'standing_permission', 'approval', 'principal'):
            with self.subTest(field=field), self.assertRaises(ReplyBlocked):
                self.router.on_message(dict(self.event, **{field: True}))
        self.brain.assert_not_called()
        self.send.assert_not_called()

    def test_missing_boolean_or_unverified_approval_never_sends(self):
        self.router.on_message(self.event)
        for invalid in (None, True, 'send it', {'principal': 'jeff', 'approved': True}):
            self.verify.return_value = invalid
            with self.subTest(invalid=invalid), self.assertRaises(ReplyBlocked):
                self.router.approve_and_send(invalid)
        self.send.assert_not_called()

    def test_qa_group_routine_other_person_and_standing_consent_never_send(self):
        draft = self.router.on_message(self.event)
        for changes in ({'principal': 'band-member'}, {'surface': 'qa_chat'},
                        {'surface': 'group_chat'}, {'surface': 'routine'},
                        {'decision': 'standing_permission'}, {'decision': 'hold'},
                        {'approved_at': 999}, {'approved_at': 1001},
                        {'approved_at': float('nan')}, {'digest': 'changed-body-or-recipient'},
                        {'draft_id': 'another-draft'}):
            self.verify.return_value = self.approval(draft, **changes)
            with self.subTest(changes=changes), self.assertRaises(ReplyBlocked):
                self.router.approve_and_send(object())
        self.send.assert_not_called()

    def test_exact_draft_fresh_approval_sends_once(self):
        draft = self.router.on_message(self.event)
        self.verify.return_value = self.approval(draft)
        result = self.router.approve_and_send(object())
        self.assertEqual(result['state'], 'submitted')
        self.send.assert_called_once_with(chat_guid=draft['chat_guid'], text=draft['text'],
                                          approval=self.verify.return_value, idempotency_key=draft['id'])
        with self.assertRaises(ReplyBlocked):
            self.router.approve_and_send(object())
        self.send.assert_called_once()

    def test_approval_replay_blocked_across_restart(self):
        draft = self.router.on_message(self.event)
        self.verify.return_value = self.approval(draft)
        self.router.approve_and_send(object())
        restarted = self.open_router()
        with self.assertRaises(ReplyBlocked):
            restarted.approve_and_send(object())
        self.send.assert_called_once()

    def test_same_approval_event_cannot_authorize_another_draft(self):
        draft = self.router.on_message(self.event)
        self.verify.return_value = self.approval(draft)
        self.router.approve_and_send(object())
        next_draft = self.router.on_message(dict(self.event, id='inbound-2'))
        self.verify.return_value = self.approval(next_draft)
        with self.assertRaises(ReplyBlocked):
            self.router.approve_and_send(object())
        self.send.assert_called_once()

    def test_new_draft_invalidates_old_approval(self):
        old = self.router.on_message(self.event)
        new = self.router.on_message(dict(self.event, id='inbound-2'))
        self.assertNotEqual(old['id'], new['id'])
        self.verify.return_value = self.approval(old)
        with self.assertRaises(ReplyBlocked):
            self.router.approve_and_send(object())
        self.send.assert_not_called()

    def test_expired_draft_and_stale_approval_never_send(self):
        draft = self.router.on_message(self.event)
        approval = self.approval(draft)
        for now in (1061, 1300):
            self.now = now
            self.verify.return_value = approval
            with self.assertRaises(ReplyBlocked):
                self.router.approve_and_send(object())
        self.send.assert_not_called()

    def test_duplicate_ingress_does_not_regenerate_or_send(self):
        draft = self.router.on_message(self.event)
        self.assertEqual(draft, self.router.on_message(self.event))
        self.brain.assert_called_once()
        self.send.assert_not_called()

    def test_webbob_failure_has_no_grok_or_send_fallback(self):
        self.brain.side_effect = RuntimeError('credential-fixture')
        with self.assertRaises(ReplyBlocked) as error:
            self.router.on_message(self.event)
        self.assertNotIn('credential-fixture', str(error.exception))
        self.send.assert_not_called()
        self.verify.assert_not_called()

    def test_model_cannot_return_an_action_instead_of_text(self):
        self.brain.return_value = {'send': True, 'text': 'send now'}
        with self.assertRaises(ReplyBlocked):
            self.router.on_message(self.event)
        self.send.assert_not_called()

    def test_verifier_failure_never_sends(self):
        self.verify.side_effect = RuntimeError('credential-fixture')
        with self.assertRaises(ReplyBlocked) as error:
            self.router.approve_and_send(object())
        self.assertNotIn('credential-fixture', str(error.exception))
        self.send.assert_not_called()

    def test_ambiguous_send_consumes_approval_without_retry_or_recovery_send(self):
        draft = self.router.on_message(self.event)
        self.verify.return_value = self.approval(draft)
        self.send.side_effect = RuntimeError('private Andrea error')
        with self.assertRaises(ReplyBlocked) as error:
            self.router.approve_and_send(object())
        self.assertNotIn('private Andrea error', str(error.exception))
        self.send.side_effect = None
        with self.assertRaises(ReplyBlocked):
            self.open_router().approve_and_send(object())
        self.send.assert_called_once()

    def test_model_surface_contains_no_approval_or_send(self):
        self.assertEqual(set(self.router.model_tools), {'on_message'})

    def test_concurrent_approval_cannot_double_send(self):
        draft = self.router.on_message(self.event)
        self.verify.return_value = self.approval(draft)
        other = self.open_router()
        def attempt(router):
            try:
                return router.approve_and_send(object())['state']
            except ReplyBlocked:
                return 'blocked'
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(attempt, (self.router, other)))
        self.assertCountEqual(results, ['submitted', 'blocked'])
        self.send.assert_called_once()

    def test_routing_contract_disables_grok_and_standing_sends(self):
        config = json.loads((Path(__file__).parents[1] / 'config/andrea-routing.json').read_text())
        self.assertEqual(config['brain'], 'webbob')
        self.assertIsNone(config['fallback'])
        self.assertFalse(config['standing_permission'])
        self.assertFalse(config['automatic_retry'])
        self.assertNotIn('approve_and_send', config['model_surface'])
