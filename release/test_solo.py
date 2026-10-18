"""Release failure behavior and evidence authority, without touching production."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import solo


class CurrentModeReplayTests(unittest.TestCase):
    def test_live_messaging_uses_only_health_and_the_protected_exact_thread(self):
        folder=self.root/'conductor/webchat';folder.mkdir(parents=True)
        bridge=folder/'andrea-bridge.json';bridge.write_text(json.dumps(dict(url='http://fixture',token='fixture')));bridge.chmod(0o600)
        mapping=folder/'instinct.json';mapping.write_text(json.dumps(dict(chat_guid='iMessage;-;+12025550101',addresses=['+12025550101'])))
        health=dict(ok=True,connected=True,paused=False,instinctReadOnly=True,sha=solo.andrea_pin()['sha'],deliveryProtocol=1)
        gateway=Mock(spec=['exact_chat','messages'])
        gateway.exact_chat.return_value=[dict(guid='iMessage;-;+12025550101',participants=[dict(address='+12025550101')])]
        gateway.messages.return_value=[]
        andrea=Mock(spec=['call']);andrea.call.return_value=health
        with patch('texting.BlueBubbles',return_value=gateway),patch('texting.Andrea',return_value=andrea):
            result=solo.live_messaging_reads(self.root,'improve')
            self.assertEqual(len(result),2)
            andrea.call.assert_called_once_with('health')
            gateway.exact_chat.assert_called_once_with('iMessage;-;+12025550101')
            gateway.messages.assert_called_once_with('iMessage;-;+12025550101')
            for changed in ({},dict(chat_guid='other',addresses=['+12025550102'])):
                mapping.write_text(json.dumps(changed))
                with self.assertRaises(Exception):solo.live_messaging_reads(self.root,'improve')
            mapping.write_text(json.dumps(dict(chat_guid='iMessage;-;+12025550101',addresses=['+12025550101'])))
            for key,bad in (('sha','old'),('connected',False),('instinctReadOnly',False),('paused',True)):
                andrea.call.return_value=dict(health,**{key:bad})
                with self.assertRaises(Exception):solo.live_messaging_reads(self.root,'improve')

    def test_isolated_remaining_replay_confirms_reminders_at_all_hours(self):
        from datetime import datetime
        from app import Chat
        from reminders import ZONE
        from texting_fixture import OfflineProviders
        import uuid
        for hour, minute, approval_delay in ((9, 0, 0), (19, 50, 0), (23, 30, 0), (19, 50, 2)):
            with self.subTest(hour=hour, approval_delay=approval_delay):
                folder = self.root / f"{hour}-{approval_delay}"
                chat = Chat(folder / 'webchat', folder, OfflineProviders())
                self.addCleanup(chat.close)
                now = [datetime(2026, 10, 16, hour, minute, tzinfo=ZONE).timestamp()]
                chat.reminders.clock = lambda: now[0]
                cid = chat.new_conversation()['id']
                seen = []
                def send(client, cid, text):
                    seen.append(text)
                    if text in ('Karen QA status', 'band desk status'):
                        return {}, dict(provider='teammates', content='Source: fixture')
                    if text == 'band desk digest for Fixture Band':
                        return {}, dict(provider='teammates', content='fixture',
                                        teammate_evidence=dict(all_read=True, band_reads=[dict(name='Fixture Band')]))
                    if text.startswith('yes wbrem-'):
                        now[0] += approval_delay
                    value = chat.submit(cid, text, str(uuid.uuid4()), actor='fixture-owner')
                    answer = value['messages'][-1]
                    if text.startswith('remind me'):
                        self.assertIn('Reply `yes wbrem-', answer['content'])
                        self.assertNotIn('Reminder saved', answer['content'])
                    return value, answer
                def call(path):
                    if path == '/api/reminders':
                        return dict(reminders=chat.reminders.listing())
                    self.assertEqual(path, '/api/conversations/' + cid)
                    now[0] += 2
                    chat.deliver_reminders()
                    return chat.conversations[cid]
                client = Mock(); client.call.side_effect = call
                with patch.object(solo, 'submit', side_effect=send), patch(
                        'teammates.band_mappings', return_value=[dict(name='Fixture Band')]):
                    checks = solo.remaining_replay(client, cid, folder)
                self.assertTrue(all(c['passed'] for c in checks))
                self.assertEqual(sum(text.startswith('yes wbrem-') for text in seen), 2)
                self.assertFalse(chat.providers.calls)

    def test_live_remaining_replay_never_creates_reminders_or_reads_multiple_bands(self):
        client=Mock();client.call.return_value={'reminders':[]}
        def submit(client,cid,text):
            if text in ('Karen QA status','band desk status'):
                return {},dict(provider='teammates',content='Source: configured fixture')
            self.assertEqual(text,'band desk digest for Fixture Band')
            return {},dict(provider='teammates',content='Fixture digest',teammate_evidence=dict(all_read=True,band_reads=[dict(name='Fixture Band')]))
        with patch.object(solo,'submit',side_effect=submit),patch('teammates.band_mappings',return_value=[dict(name='Fixture Band'),dict(name='Untouched')]):
            checks=solo.remaining_replay(client,'fixture',self.root,real=True)
        self.assertTrue(all(c['passed'] for c in checks))
        client.call.assert_called_once_with('/api/reminders')

    def test_live_memory_replay_reads_saved_bytes_without_proposals_or_capture(self):
        from bob_gaps import profile_path
        path=profile_path(self.root);path.parent.mkdir(parents=True,exist_ok=True);path.write_text('Keep owner memory.\n')
        def submit(client,cid,text):
            if text=='show my saved memories':
                return {},dict(provider='memory',private_memory=True,content='Keep owner memory; not all profile or chat context')
            self.assertEqual(text,'look up Python programming language')
            return {},dict(provider='state',content='Python https://www.python.org/')
        with patch.object(solo,'submit',side_effect=submit):
            self.assertTrue(all(c['passed'] for c in solo.gaps_replay(Mock(),'fixture',self.root,real=True)))
        self.assertEqual(path.read_text(),'Keep owner memory.\n')

    def test_retained_delivery_requires_manifest_and_every_child_binding(self):
        review=self.root/'conductor/reviews';review.mkdir(parents=True)
        files={}
        for name in ('phone_send','phone_return','owner_attestation'):
            path=review/(name+'.json');path.write_text(json.dumps(dict(fixture=name)))
            files[name]=dict(path=str(path),sha256=solo.digest(path))
        proof=dict(status='PASS_OWNER_PHONE_DELIVERY',sha='historical',andrea_sha=solo.andrea_pin()['sha'],real_submissions=1,
                   physical_receipt_without_retry=True,matching_return_read=True,synchronized_return_copy_not_used=True,
                   evidence_hashes={k:v['sha256'] for k,v in files.items()})
        phone=review/'phone.json';phone.write_text(json.dumps(proof));files['phone']=dict(path=str(phone),sha256=solo.digest(phone))
        manifest=review/'manifest.json';manifest.write_text(json.dumps(dict(sha='historical',files=files)))
        code=self.root/'code';(code/'release').mkdir(parents=True)
        (code/'release/retained-delivery.json').write_text(json.dumps(dict(manifest=str(manifest.relative_to(self.root)),sha256=solo.digest(manifest))))
        pin=solo.andrea_pin()
        with patch.object(solo,'CODE',code),patch.object(solo,'andrea_pin',return_value=pin):
            result=solo.retained_delivery_replay(self.root)[0]
            self.assertEqual(result['source_sha'],'historical');self.assertEqual(result['real_texts_sent'],0)
            for row in files.values():
                path=Path(row['path']);before=path.read_bytes();path.write_bytes(before+b' ')
                with self.assertRaises(Exception):solo.retained_delivery_replay(self.root)
                path.write_bytes(before)
            manifest.write_text(manifest.read_text()+' ')
            with self.assertRaises(Exception):solo.retained_delivery_replay(self.root)

    def test_synthetic_children_cannot_inherit_real_generation_admission(self):
        env=dict(BOB_GENERATION_BUDGET='real-goal',BOB_GENERATION_BUDGET_ROOT='/real',
                 BOB_GENERATION_PURPOSE='controller',BOB_REQUIRE_GENERATION_BUDGET='1',
                 BOB_ROOT='/fixture',PATH='/bin')
        result=solo.fixture_generation_environment(env)
        self.assertEqual(result,dict(BOB_ROOT='/fixture',PATH='/bin'))
        self.assertEqual(env['BOB_GENERATION_BUDGET'],'real-goal')

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_delivery_gate_requires_a_new_inspection_of_the_bound_message(self):
        before = dict(event='owner_sent_via_andrea', body='synthetic',
                      delivery_checks=[dict(state='delivery_failed', at=1)])
        after = copy.deepcopy(before)
        after['delivery_checks'].append(dict(state='delivery_failed', at=2))
        bridge = dict(actionId='original-action', digest='original-scope')
        evidence = dict(bridge, state='delivery_failed')
        answer = dict(content='Messages reports this text failed. Nothing was resent.')
        solo.verify_delivery_refresh(before, after, bridge, evidence, answer)
        cases = [
            (before, evidence, answer),
            (after, evidence, dict(content='Could not refresh delivery status. ' + answer['content'])),
            (after, dict(evidence, actionId='other-action'), answer),
            (after, dict(evidence, digest='other-scope'), answer),
            (dict(after, body='changed'), evidence, answer),
            (dict(after, delivery_checks=[dict(state='delivered', at=1),
                                         dict(state='delivery_failed', at=2)]), evidence, answer),
        ]
        for observed, receipt, reply in cases:
            with self.subTest(observed=observed, receipt=receipt, reply=reply), self.assertRaises(Exception):
                solo.verify_delivery_refresh(before, observed, bridge, receipt, reply)

    def test_unscoped_resources_requires_a_useful_question_without_action_claims(self):
        solo.verify_resource_clarification(dict(provider='planner', content='Which task should I work on, and what result do you want?'))
        for content in ('I did not start, assign, or queue any work in this turn.',
                        'I am ready to use all resources.', 'What task? I started it already.',
                        'Task and result are understood.'):
            with self.subTest(content=content), self.assertRaises(Exception):
                solo.verify_resource_clarification(dict(provider='planner', content=content))

    def test_improvement_gate_rejects_stale_or_fabricated_audit_evidence(self):
        from app import Chat
        from texting_fixture import OfflineProviders
        import uuid
        chat = Chat(self.root / 'conductor/webchat', self.root, OfflineProviders())
        self.addCleanup(chat.close)
        cid = chat.conversation_list()['conversations'][0]['id']
        answer = chat.submit(cid, solo.RESOURCE_PROMPTS[1], str(uuid.uuid4()))['messages'][-1]
        solo.verify_improvement_reply(self.root, [], answer)
        for key, bad in (('transcript_sha256', 'old'), ('inspected_message_count', 999),
                         ('queued_jobs', 1), ('code_changed', True), ('regression_cases', []),
                         ('scheduling_blocks', {'SOLO-WORKER': True, 'MAINTENANCE': False})):
            with self.subTest(key=key):
                altered = copy.deepcopy(answer)
                altered['improvement_receipt'][key] = bad
                with self.assertRaises(Exception):
                    solo.verify_improvement_reply(self.root, [], altered)

    def test_exact_action_replay_stays_held_without_global_solo_or_queue_writes(self):
        from app import Chat, Server
        from texting_fixture import MockMessaging, OfflineProviders
        from texting import Texting, BlueBubbles, Andrea
        from task_dispatch import task_queue
        import threading
        mock = MockMessaging(self.root)
        chat = Chat(self.root / 'conductor/webchat', self.root, OfflineProviders(),
                    texting=Texting(BlueBubbles(mock.config_db), Andrea(mock.base, mock.token, expected_protocol=1)))
        server = Server(('127.0.0.1', 0), chat)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            client = solo.Client('http://127.0.0.1:' + str(server.server_port), chat.folder / '.password')
            client.login()
            ids = []
            for prompt in (solo.START_PROMPT, solo.RESOURCE_ACTION_PROMPT):
                receipt = solo.held_action_replay(client, self.root, prompt)
                self.assertTrue(receipt['passed'])
                self.assertEqual(receipt['queued_workers'], 0)
                self.assertEqual(receipt['provider'], 'dispatcher')
                ids.append(receipt['conversation_id'])
            self.assertEqual(len(set(ids)), 2)
            self.assertFalse(task_queue.tasks(self.root))
            self.assertFalse((self.root / 'conductor/SOLO-WORKER').exists())
            for cid in ids:
                saved = json.loads((chat.folder / 'sessions' / (cid + '.json')).read_text())
                self.assertEqual(saved['intent_state']['holds']['all']['released_projects'], [])
                self.assertEqual(len(saved['messages']), 4)
        finally:
            server.shutdown()
            server.server_close()
            chat.close()
            mock.close()

    def test_service_guard_honors_current_mode_without_recreating_solo(self):
        sessions = {'svc-job-runner': '1.svc-job-runner', 'svc-reviewer': '2.svc-reviewer'}
        solo.verify_worker_service_mode(self.root, sessions)
        self.assertFalse((self.root / 'conductor/SOLO-WORKER').exists())
        (self.root / 'conductor').mkdir(exist_ok=True)
        (self.root / 'conductor/SOLO-WORKER').touch()
        with self.assertRaisesRegex(Exception, 'solo mode is active'):
            solo.verify_worker_service_mode(self.root, sessions)
        solo.verify_worker_service_mode(self.root, {})


class BridgeReplayTargetTests(unittest.TestCase):
    def test_excludes_short_codes_groups_and_mismatched_membership(self):
        for guid, addresses in (
            ('SMS;-;12345', ['12345']),
            ('iMessage;+;group', ['+12025550101']),
            ('iMessage;-;+12025550101', ['+12025550102']),
            ('iMessage;-;+12025550101', ['+12025550101', '+12025550102']),
            ('iMessage;-;bad@example', ['bad@example']),
        ):
            with self.subTest(guid=guid):
                self.assertFalse(solo.bridge_replay_target(dict(guid=guid, participants=[dict(address=a) for a in addresses])))

    def test_accepts_verified_direct_phone_or_email_membership(self):
        for service, address in (('SMS', '+12025550101'), ('iMessage', 'owner@example.com'), ('RCS', '+442079460123')):
            self.assertTrue(solo.bridge_replay_target(dict(guid=service+';-;'+address, participants=[dict(address=address)])))


class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / 'record.json'
        state = self.root / 'conductor/state'
        state.mkdir(parents=True)
        candidate = self.root / 'candidate'
        candidate.mkdir()
        (candidate / 'webbob-build.json').write_text(json.dumps(dict(sha='c' * 40)))
        snapshots = {}
        for name in ('webchat', 'dispatch'):
            prior = self.root / ('previous-' + name)
            prior.mkdir()
            (prior / 'webbob-build.json').write_text(json.dumps(dict(sha='b' * 40)))
            snapshots[name] = str(prior)
            (state / (name + '-code-root')).write_text(str(candidate.resolve()) + '\n')
        self.record = dict(previous='b' * 40, sha='c' * 40, snapshots=snapshots, rollback=str(self.root))
        self.record['snapshot_hashes'] = {name: solo.source_digest(path) for name, path in snapshots.items()}
        for name in ('require_disk_space', 'release_recovery', 'restart', 'versions'):
            p = patch.object(solo, name)
            setattr(self, name, p.start())
            self.addCleanup(p.stop)
        self.versions.return_value = {'local': {'sha': 'b' * 40}, 'public': {'sha': 'b' * 40}}
        self.restart.return_value = dict(before={}, after={}, restarted=['svc-webchat'])

    def attempt(self, activate=None, live=None, **kw):
        solo.transaction(self.root, self.record, self.path, activate or Mock(),
                         live or Mock(return_value={'all_pass': True}), **kw)

    def test_requires_two_live_greens(self):
        live = Mock(return_value={'all_pass': True})
        self.attempt(live=live)
        self.assertEqual(live.call_count, 2)
        self.assertEqual(len(json.loads(self.path.read_text())['rounds']), 2)
        self.restart.assert_not_called()

    def test_second_live_failure_rolls_back_to_immediate_predecessor(self):
        with self.assertRaisesRegex(Exception, 'Live replay failed'):
            self.attempt(live=Mock(side_effect=[{'all_pass': True}, {'all_pass': False}]))
        self.restart.assert_called_once_with(self.root, self.record['snapshots'])
        self.versions.assert_called_with(self.root, 'b' * 40)
        self.assertFalse(json.loads(self.path.read_text())['all_pass'])

    def test_scoped_live_proof_preserves_deferral_and_mixed_scope_rolls_back(self):
        from qualification_scope import outcome, passed
        scope=dict(path='/fixture/scope.json',sha256='fixture')
        self.record.update(outcome(False,scope))
        live=Mock(return_value=outcome(True,scope))
        with patch('qualification_scope.selected',return_value=scope):
            self.attempt(live=live)
        record=json.loads(self.path.read_text())
        self.assertEqual(live.call_count,2)
        self.assertEqual(record['status'],'SCOPED_LIVE_PASS')
        self.assertFalse(record['all_pass'])
        self.assertTrue(passed(record,scope))
        self.assertFalse(passed(record))

    def test_scoped_round_cannot_accept_unrestricted_or_different_scope_proof(self):
        from qualification_scope import outcome
        scope=dict(path='/fixture/scope.json',sha256='fixture')
        self.record.update(outcome(False,scope))
        with patch('qualification_scope.selected',return_value=scope):
            with self.assertRaisesRegex(Exception,'Live replay failed'):
                self.attempt(live=Mock(side_effect=[outcome(True,scope),{'all_pass':True}]))
        self.restart.assert_called_once_with(self.root,self.record['snapshots'])

    def test_partial_startup_failure_also_rolls_back(self):
        with self.assertRaisesRegex(RuntimeError, 'startup'):
            self.attempt(activate=Mock(side_effect=RuntimeError('startup')))
        self.restart.assert_called_once()

    def test_disk_failure_before_activation_never_restarts(self):
        self.require_disk_space.side_effect = OSError('disk floor')
        activate = Mock()
        with self.assertRaises(OSError):
            self.attempt(activate=activate)
        activate.assert_not_called()
        self.restart.assert_not_called()

    def test_disk_failure_in_live_round_restores_first(self):
        self.require_disk_space.side_effect = [{}, OSError('disk floor')]
        with self.assertRaises(OSError):
            self.attempt()
        self.restart.assert_called_once()

    def test_final_evidence_write_failure_cannot_leave_candidate_live(self):
        def publish(path, value):
            if value.get('all_pass'):
                raise OSError('publish failed')
            solo.atomic_json(path, value)
        with self.assertRaises(OSError):
            self.attempt(publish=publish)
        self.restart.assert_called_once()

    def test_success_alias_failure_rolls_back(self):
        alias = self.root / 'latest.json'
        def publish(path, value):
            if path == alias:
                raise OSError('alias failed')
            solo.atomic_json(path, value)
        with self.assertRaises(OSError):
            self.attempt(publish=publish, final_path=alias)
        self.restart.assert_called_once()
        self.assertFalse(json.loads(self.path.read_text())['all_pass'])

    def test_keyboard_interrupt_rolls_back(self):
        with self.assertRaises(KeyboardInterrupt):
            self.attempt(live=Mock(side_effect=KeyboardInterrupt))
        self.restart.assert_called_once()


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.log = self.folder / 'tests.log'
        self.log.write_text('Ran tests OK')
        names = {'webchat', 'services', 'reviews', 'release', 'eval', 'browser'}
        names.update(p.stem for p in (solo.CODE / 'webchat').glob('test_*.mjs'))
        self.check = dict(sha='a' * 40, feature='texting', all_pass=True, staging={'all_pass': True},
                          results={n: dict(exit=0, skipped=0, log=str(self.log), log_sha256=solo.digest(self.log)) for n in names})
        self.review = dict(sha='a' * 40, feature='texting', reviewer='Codex solo', verdict='PASS',
                           findings=['Inspected auth, durable consent, unknown outcome, rollback'])

    def verify(self):
        checks, review = self.folder / 'checks.json', self.folder / 'review.json'
        solo.atomic_json(checks, self.check)
        self.review['checks_sha256'] = solo.digest(checks)
        solo.atomic_json(review, self.review)
        return solo.verify_gates('a' * 40, 'texting', checks, review)

    def test_complete_evidence_passes_without_council(self):
        self.assertIn('self_review_sha256', self.verify())

    def attempts(self, states):
        for index, passed in enumerate(states, 1):
            folder = self.folder / f'attempt-{index:04d}'
            folder.mkdir()
            check = dict(self.check, all_pass=passed)
            solo.atomic_json(folder / 'checks.json', check)
        return folder / 'checks.json'

    def test_two_complete_latest_predeploy_greens_required(self):
        path = self.attempts([False, True, True])
        pair = solo.consecutive_checks('a' * 40, 'texting', path)
        self.assertEqual(len(pair), 2)
        self.assertEqual(pair[-1]['sha256'], solo.digest(path))

    def test_single_predeploy_green_is_not_enough(self):
        path = self.attempts([True])
        with self.assertRaisesRegex(Exception, 'Two consecutive'):
            solo.consecutive_checks('a' * 40, 'texting', path)

    def test_failure_between_predeploy_greens_is_not_skipped(self):
        path = self.attempts([True, False, True])
        with self.assertRaisesRegex(Exception, 'failed'):
            solo.consecutive_checks('a' * 40, 'texting', path)

    def test_earlier_green_pair_cannot_override_latest_failure(self):
        self.attempts([True, True, False])
        with self.assertRaisesRegex(Exception, 'latest'):
            solo.consecutive_checks('a' * 40, 'texting', self.folder / 'attempt-0002/checks.json')

    def test_both_predeploy_suite_hashes_are_rechecked(self):
        path = self.attempts([True, True])
        earlier = self.folder / 'attempt-0001/checks.json'
        check = json.loads(earlier.read_text())
        check['results']['webchat']['log_sha256'] = 'changed'
        solo.atomic_json(earlier, check)
        with self.assertRaisesRegex(Exception, 'changed'):
            solo.consecutive_checks('a' * 40, 'texting', path)

    def test_stale_candidate_review_rejected(self):
        self.review['sha'] = 'b' * 40
        with self.assertRaisesRegex(Exception, 'Stale'):
            self.verify()

    def test_cross_feature_evidence_rejected(self):
        self.check['feature'] = 'media'
        with self.assertRaisesRegex(Exception, 'wrong-feature'):
            self.verify()

    def test_missing_suite_rejected(self):
        del self.check['results']['services']
        with self.assertRaisesRegex(Exception, 'Missing'):
            self.verify()

    def test_voice_requires_audio_browser_and_js_suites(self):
        self.check['feature'] = self.review['feature'] = 'voice'
        self.check['results']['media-browser'] = self.check['results']['browser']
        checks, review = self.folder / 'checks.json', self.folder / 'review.json'
        solo.atomic_json(checks, self.check)
        self.review['checks_sha256'] = solo.digest(checks)
        solo.atomic_json(review, self.review)
        with self.assertRaisesRegex(Exception, 'Missing mandatory suite'):
            solo.verify_gates('a' * 40, 'voice', checks, review)

    def test_improve_requires_voice_availability_browser_without_replacing_real_audio(self):
        self.check['feature'] = 'improve'
        for name in ('media-browser', 'voice-js', 'voice-browser', 'instinct-browser',
                     'remaining-browser', 'cold-browser', 'startup-recovery-browser', 'bridge-contract', 'jobs-results-browser', 'reply-lifecycle-browser', 'memory-removal-browser', 'project-handoffs-browser'):
            self.check['results'][name] = self.check['results']['browser']
        sha = solo.andrea_pin()['sha']
        self.check['andrea'] = dict(sha=sha, results=[])
        solo.atomic_json(self.folder / 'bridge-contract.json', dict(all_pass=True, andrea_sha=sha, real_texts_sent=0))
        checks = self.folder / 'checks.json'
        solo.atomic_json(checks, self.check)
        with self.assertRaisesRegex(Exception, 'Missing mandatory suite'):
            solo.verify_checks('a' * 40, 'improve', checks)

        self.check['results']['voice-availability-browser'] = self.check['results']['browser']
        solo.atomic_json(checks, self.check)
        solo.verify_checks('a' * 40, 'improve', checks)
        memory = self.check['results'].pop('memory-removal-browser')
        solo.atomic_json(checks, self.check)
        with self.assertRaisesRegex(Exception, 'Missing mandatory suite'):
            solo.verify_checks('a' * 40, 'improve', checks)
        self.check['results']['memory-removal-browser'] = memory
        del self.check['results']['voice-browser']
        solo.atomic_json(checks, self.check)
        with self.assertRaisesRegex(Exception, 'Missing mandatory suite'):
            solo.verify_checks('a' * 40, 'improve', checks)


    def test_owner_voice_deferral_never_excuses_another_missing_gate(self):
        from qualification_scope import outcome
        scope=dict(path='/fixture/scope.json',sha256='fixture')
        self.check['feature']='improve'
        for name in ('media-browser','voice-js','instinct-browser','remaining-browser','cold-browser',
                     'startup-recovery-browser','bridge-contract','jobs-results-browser','reply-lifecycle-browser',
                     'memory-removal-browser','project-handoffs-browser','voice-availability-browser'):
            self.check['results'][name]=self.check['results']['browser']
        sha=solo.andrea_pin()['sha'];self.check['andrea']=dict(sha=sha,results=[])
        solo.atomic_json(self.folder/'bridge-contract.json',dict(all_pass=True,andrea_sha=sha,real_texts_sent=0))
        self.check.update(outcome(True,scope));checks=self.folder/'checks.json'
        solo.atomic_json(checks,self.check)
        with self.assertRaises(Exception):solo.verify_checks('a'*40,'improve',checks)
        with patch('qualification_scope.selected',return_value=scope):
            solo.verify_checks('a'*40,'improve',checks)
            del self.check['results']['voice-availability-browser'];solo.atomic_json(checks,self.check)
            with self.assertRaisesRegex(Exception,'Missing mandatory suite'):solo.verify_checks('a'*40,'improve',checks)

    def test_instinct_requires_read_only_browser_proof(self):
        self.check['feature'] = self.review['feature'] = 'instinct'
        for name in ('media-browser', 'voice-js', 'voice-browser'):
            self.check['results'][name] = self.check['results']['browser']
        checks, review = self.folder / 'checks.json', self.folder / 'review.json'
        solo.atomic_json(checks, self.check)
        self.review['checks_sha256'] = solo.digest(checks)
        solo.atomic_json(review, self.review)
        with self.assertRaisesRegex(Exception, 'Missing mandatory suite'):
            solo.verify_gates('a' * 40, 'instinct', checks, review)

    def test_remaining_requires_reminder_browser_proof(self):
        self.check['feature'] = self.review['feature'] = 'remaining'
        for name in ('media-browser', 'voice-js', 'voice-browser', 'instinct-browser'):
            self.check['results'][name] = self.check['results']['browser']
        checks, review = self.folder / 'checks.json', self.folder / 'review.json'
        solo.atomic_json(checks, self.check)
        self.review['checks_sha256'] = solo.digest(checks)
        solo.atomic_json(review, self.review)
        with self.assertRaisesRegex(Exception, 'Missing mandatory suite'):
            solo.verify_gates('a' * 40, 'remaining', checks, review)

    def test_bridge_cannot_release_without_pinned_andrea_evidence(self):
        self.check['feature'] = self.review['feature'] = 'bridge'
        for name in ('media-browser', 'voice-js', 'voice-browser', 'instinct-browser', 'remaining-browser', 'bridge-contract'):
            self.check['results'][name] = self.check['results']['browser']
        checks, review = self.folder / 'checks.json', self.folder / 'review.json'
        solo.atomic_json(checks, self.check)
        self.review['checks_sha256'] = solo.digest(checks)
        solo.atomic_json(review, self.review)
        with self.assertRaisesRegex(Exception, 'Andrea exact-tip evidence missing'):
            solo.verify_gates('a' * 40, 'bridge', checks, review)

    def test_skipped_required_checks_rejected(self):
        self.check['results']['webchat']['skipped'] = 1
        with self.assertRaisesRegex(Exception, 'skipped'):
            self.verify()

    def test_improve_requires_jobs_result_browser_and_still_requires_real_voice(self):
        self.check['feature'] = 'improve'
        for name in ('media-browser', 'voice-js', 'voice-browser', 'instinct-browser',
                     'remaining-browser', 'bridge-contract', 'cold-browser', 'jobs-results-browser',
                     'voice-availability-browser', 'reply-lifecycle-browser', 'memory-removal-browser', 'startup-recovery-browser', 'project-handoffs-browser'):
            self.check['results'][name] = dict(self.check['results']['browser'])
        self.check['andrea'] = {'sha': solo.andrea_pin()['sha'], 'results': []}
        solo.atomic_json(self.folder / 'bridge-contract.json', dict(
            all_pass=True, andrea_sha=solo.andrea_pin()['sha'], real_texts_sent=0))
        checks = self.folder / 'checks.json'
        solo.atomic_json(checks, self.check)
        solo.verify_checks('a' * 40, 'improve', checks)
        for missing in ('jobs-results-browser', 'reply-lifecycle-browser', 'voice-browser', 'startup-recovery-browser', 'project-handoffs-browser'):
            with self.subTest(missing=missing):
                value = copy.deepcopy(self.check)
                del value['results'][missing]
                solo.atomic_json(checks, value)
                with self.assertRaisesRegex(Exception, 'Missing mandatory suite'):
                    solo.verify_checks('a' * 40, 'improve', checks)

    def test_changed_log_rejected(self):
        self.log.write_text('Different bytes')
        with self.assertRaisesRegex(Exception, 'changed'):
            self.verify()

    def test_unresolved_review_blocker_rejected(self):
        self.review['unresolved_blockers'] = ['Broken consent']
        with self.assertRaisesRegex(Exception, 'unresolved'):
            self.verify()


class MediaEvidenceTests(unittest.TestCase):
    def test_guessed_text_on_nonvision_fallback_is_not_live_vision_evidence(self):
        answer = dict(provider='codex', content='red note-token pdf-token', attachments=[dict(media_id='picture')])
        with self.assertRaisesRegex(Exception, 'vision provider'):
            solo.verify_media_answer(answer, 'note-token', 'pdf-token', 'picture', real=True)

    def test_attachment_extraction_warning_is_not_a_full_media_pass(self):
        answer = dict(provider='gemini', content='red note-token pdf-token\nAttachment notes: failed to decode',
                      attachments=[dict(media_id='picture')])
        with self.assertRaisesRegex(Exception, 'incomplete attachment'):
            solo.verify_media_answer(answer, 'note-token', 'pdf-token', 'picture', real=True)


class InstinctEvidenceTests(unittest.TestCase):
    def test_missing_mapping_is_not_a_live_pass(self):
        with patch.object(solo, 'submit', return_value=({}, dict(provider='instinct', content='Verified thread not found'))):
            with self.assertRaisesRegex(Exception, 'mapping/read is unavailable'):
                solo.instinct_replay(Mock(), 'conversation')

    def test_confirmable_instinct_draft_is_not_a_live_pass(self):
        digest = dict(provider='instinct', content='read from BlueBubbles\nBills / deadlines: 0\nSecurity: 0\nAppointments: 0')
        card = dict(text_draft=dict(state='pending', confirm_message='yes wbtxt-' + 'a' * 32))
        with patch.object(solo, 'submit', side_effect=[({}, digest), ({}, card)]):
            with self.assertRaisesRegex(Exception, 'send authority'):
                solo.instinct_replay(Mock(), 'conversation')


if __name__ == '__main__':
    unittest.main()
