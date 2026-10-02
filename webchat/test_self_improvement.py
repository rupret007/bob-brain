"""Owner incident regressions through the real saved conversation/submit path."""
import hashlib
import json
import uuid
from unittest.mock import patch

from app import Chat
from self_improvement import resolve
from task_dispatch import task_queue
from test_webbob_replyq_1856 import SessionFixture


GOAL = 'Ok top priority is to make web bob better than grok bot. Make it happen any and all resources.'
ENABLE = 'Ok enable what we need to enable'
RESEARCH = 'Ok well make that your goal. Research what grok bot does and self improve to be better than it.'
RESOURCES = 'top priority use any and all resources'


class ImprovementTests(SessionFixture):
    def test_polite_enable_question_keeps_configuration_semantics(self):
        reply = self.send('Could you enable what we need to enable?')
        self.assertIn('No global scheduling block', reply['content'])
        self.assertIn('improvement_receipt', reply)
        self.assertFalse(task_queue.tasks(self.root))

    def test_continuation_references_saved_work_after_restart_without_new_assignment(self):
        self.send(GOAL)
        self.chat.close()
        self.chat = Chat(self.folder, self.root, self.fake)
        self.send('Continue the useful work we just agreed on.')
        self.send('Please finish that investigation.')
        rows = task_queue.tasks(self.root)
        self.assertEqual(len(rows), 1)
        self.assertEqual(next(iter(rows.values()))['requested_worker'], 'mini')
        self.send('Continue the WebJam work.')
        self.send('keep going')
        self.assertEqual(sum(row['requested_worker'] == 'mini' for row in task_queue.tasks(self.root).values()), 1)

    def test_inspection_only_goal_does_not_expand_into_execution_after_restart(self):
        self.send('Self-improve, but do not run tests or start workers; only inspect locally.')
        self.chat.close()
        self.chat = Chat(self.folder, self.root, self.fake)
        answer = self.send('continue')
        self.assertIn('saved scope excludes execution', answer['content'])
        self.assertFalse(task_queue.tasks(self.root))
        self.send(GOAL)
        self.assertFalse(task_queue.tasks(self.root))

    def test_later_inspection_limit_fences_already_queued_regression(self):
        self.send(GOAL)
        self.send('continue')
        row = next(iter(task_queue.tasks(self.root).values()))
        self.send('Do not run tests or start workers; only inspect locally.')
        self.assertIsNone(task_queue.claim(self.root, 'mini', identifier=row['id']))

    def test_new_question_and_same_project_task_cannot_resume_old_improvement(self):
        for prompt in ('What should my invitation say?', 'Fix Web Bob login tests'):
            self.identifier = self.chat.new_conversation()['id']
            self.send(GOAL)
            self.send(prompt)
            before = task_queue.tasks(self.root)
            self.chat.close()
            self.chat = Chat(self.folder, self.root, self.fake)
            self.send('continue')
            self.assertFalse(any(row['requested_worker'] == 'mini' for row in task_queue.tasks(self.root).values()))
            # A concrete current task may retain its own continuation behavior.
            self.assertTrue(set(before).issubset(task_queue.tasks(self.root)))

    def test_unrelated_writing_supersedes_unscoped_continuation_after_restart(self):
        self.send(GOAL)
        self.send('Write a thank-you note for my neighbor.')
        self.chat.close()
        self.chat = Chat(self.folder, self.root, self.fake)
        self.send('continue')
        self.assertFalse(task_queue.tasks(self.root))

    def test_changed_source_invalidates_previous_regression_identity(self):
        self.send(GOAL)
        previous = self.chat.get(self.identifier)['improvement_goal']['investigation']['sha256']
        with patch('source_identity.fingerprint', return_value={'sha256':'changed', 'suite':'changed', 'source_hashes':{}}):
            answer = self.send('keep going')
        self.assertIn('previous tests cannot verify this revision', answer['content'])
        self.assertFalse(task_queue.tasks(self.root))
        saved = self.chat.get(self.identifier)['improvement_goal']
        self.assertEqual(saved['previous_evidence'][0]['investigation_sha256'], previous)
        self.assertNotIn('verification_request_id', saved)

    def seed_incident(self):
        value = self.chat.get(self.identifier)
        for ask, answer in ((RESEARCH, "I'm definitely on board with it! I'll focus on improving."),
                            (ENABLE, "I can't enable additional project workers right now because that functionality is currently disabled.")):
            for role, content in (('user', ask), ('assistant', answer)):
                value['messages'].append(dict(id=str(uuid.uuid4()), role=role, content=content, status='done'))
        self.chat.save(value)
        self.chat.conversations[self.identifier] = value
        return value['messages'][:]

    def test_exact_owner_chain_advances_to_one_existing_executor_job(self):
        prior = self.seed_incident()
        answer = self.send(GOAL)
        saved = self.chat.get(self.identifier)['improvement_goal']
        self.assertEqual(saved['investigation']['failed'], 0)
        self.assertEqual(len(saved['investigation']['sources']), 5)
        self.assertIn('source-backed routing investigation', answer['content'])
        self.assertEqual({r['kind'] for r in answer['improvement_receipt']['findings']},
                         {'historical_worker_block_claim', 'assent_without_action_receipt'})
        for prompt in (RESOURCES, 'Ok make it happen use any and all resources.', RESEARCH,
                       'Yep and coordinate with Bob the Bot of this but use all of these to self improve.',
                       ENABLE, 'Constant self improvement is in your guiding principles'):
            answer = self.send(prompt)
            self.assertNotIn('status_observation', answer)
            self.assertEqual(len(task_queue.tasks(self.root)), 1)
        row = next(iter(task_queue.tasks(self.root).values()))
        self.assertEqual((row['requested_worker'], row['kind']), ('mini', 'local'))
        self.assertIn('webchat/test_answer_intent.py', row['prompt'])
        self.assertNotIn('completed:', answer['content'].lower())
        self.assertFalse(self.fake.calls)
        self.assertEqual(self.chat.get(self.identifier)['messages'][:len(prior)], prior)

    def completed_fixture(self, goal=GOAL):
        """Simulated journal evidence only; never launches an actual executor."""
        self.send(goal)
        self.send('You already audited it. Do the next useful step.')
        row = next(row for row in task_queue.tasks(self.root).values() if row['conversation_id'] == self.identifier)
        claim = task_queue.claim(self.root, 'mini', identifier=row['id'])
        task_queue.transition(self.root, row['id'], claim['claim_token'], 'running')
        task_queue.transition(self.root, row['id'], claim['claim_token'], 'executing')
        result = 'Local CPU test suite: webchat/test_answer_intent.py\nExit code: 0\nFixture result, not an actual provider evaluation.'
        digest = hashlib.sha256(result.encode()).hexdigest()
        task_queue.transition(self.root, row['id'], claim['claim_token'], 'succeeded', result=result,
                              result_sha256=digest, acceptance=dict(accepted=True, method='verified-execution', result_sha256=digest,
                                  execution_identity=row['expected_code_identity']))
        self.chat.close()
        self.chat = Chat(self.folder, self.root, self.fake)
        return row, result, digest

    def test_verified_result_survives_followup_restart_and_duplicate_without_new_effect(self):
        row, result, digest = self.completed_fixture()
        answer = self.send('Finish that, and tell me what actually changed.')
        self.assertIn('/api/jobs/result?id=' + row['id'], answer['content'])
        self.assertIn('no code was changed', answer['content'])
        self.assertNotIn(result, answer['content'])  # Casual continuation links the full verified result.
        self.assertEqual(answer['improvement_progress']['current_step'], 'comparison_prepared')
        saved = self.chat.get(self.identifier)['improvement_goal']
        self.assertEqual(saved['result_sha256'], digest)
        self.assertTrue(saved['comparison_plan']['sources'])
        self.assertEqual(len(task_queue.tasks(self.root)), 1)
        self.assertEqual(self.chat.submit(self.identifier, 'Finish that, and tell me what actually changed.', answer['request_id'])['messages'][-1], answer)
        enabled = self.send(ENABLE)
        self.assertNotEqual(enabled['content'], answer['content'])
        self.assertIn('changed no setting', enabled['content'])
        with patch('bob_gaps.web_search', return_value=dict(answer='A search lead, not verified product research.',
                                                         source='https://docs.x.ai/', heading='Grok')) as search:
            researched = self.send(RESEARCH)
            self.assertEqual(search.call_count, 1)
            self.assertIn('linked page has not been verified', researched['content'])
            self.assertNotEqual(researched['content'], answer['content'])
            saved = self.chat.get(self.identifier)['improvement_goal']
            self.assertEqual(saved['outcome'], RESEARCH)
            self.assertEqual(saved['current_step'], 'comparison_needs_primary_evidence')
            self.assertEqual(saved['verification_job_id'], row['id'])
            self.assertEqual(saved['result_sha256'], digest)
            self.chat.close()
            self.chat = Chat(self.folder, self.root, self.fake)
            repeated = self.send(RESEARCH)
            self.assertEqual(search.call_count, 1)
            self.assertIn('did not repeat it', repeated['content'])
            self.assertIn('Next:', repeated['content'])
        with patch('bob_gaps.web_search', side_effect=AssertionError('No network under current restriction')):
            limited = self.send('Research what Grok Bot does and self improve, but do not search the web.')
            self.assertIn('no web search was made', limited['content'])
            self.chat.close()
            self.chat = Chat(self.folder, self.root, self.fake)
            limited_again = self.send(RESEARCH)
            self.assertIn('no web search was made', limited_again['content'])
        with patch('bob_gaps.web_search', side_effect=TimeoutError('fixture timeout')) as search:
            self.send('You may now search the web.')
            failed = self.send('Research Grok Bot capabilities and self improve to be better than it.')
            self.assertEqual(search.call_count, 1)
            self.assertIn('no source-backed comparison', failed['content'])
            self.send('Research Grok Bot capabilities and self improve to be better than it.')
            self.assertEqual(search.call_count, 1)
        self.assertEqual(len(task_queue.tasks(self.root)), 1)

    def test_completed_comparison_uses_historical_receiver_evidence_without_claiming_new_consumption(self):
        from test_receiver_evidence import install_receiver_evidence
        row, _, _ = self.completed_fixture()
        install_receiver_evidence(self.root)
        answer = self.send('Finish that, and tell me what actually changed.')
        self.assertIn('owner-reported Grok checkpoint', answer['content'])
        plan = self.chat.get(self.identifier)['improvement_goal']['comparison_plan']
        self.assertTrue(plan['historical_receiver']['historical_checkpoint_ack_verified'])
        self.assertIn('newer unconsumed batches', ' '.join(plan['missing_evidence']))
        original = json.dumps(plan, sort_keys=True)
        self.chat.close(); self.chat = Chat(self.folder, self.root, self.fake)
        enabled = self.send(ENABLE)
        self.assertIn('owner-reported Grok checkpoint', enabled['content'])
        self.assertIn('/api/jobs/result?id=' + row['id'], enabled['content'])
        self.assertIn('Newer batches still need', enabled['content'])
        self.assertEqual(json.dumps(self.chat.get(self.identifier)['improvement_goal']['comparison_plan'], sort_keys=True), original)
        self.assertEqual(len(task_queue.tasks(self.root)), 1)

    def test_receiver_evidence_arriving_later_is_reported_without_rewriting_existing_worksheet(self):
        from test_receiver_evidence import install_receiver_evidence
        self.completed_fixture()
        self.send('Finish that, and tell me what actually changed.')
        original = json.dumps(self.chat.get(self.identifier)['improvement_goal']['comparison_plan'], sort_keys=True)
        install_receiver_evidence(self.root)
        answer = self.send('keep going')
        self.assertIn('Current receiver evidence: The owner-reported Grok checkpoint', answer['content'])
        self.assertEqual(json.dumps(self.chat.get(self.identifier)['improvement_goal']['comparison_plan'], sort_keys=True), original)
        self.assertEqual(len(task_queue.tasks(self.root)), 1)

    def test_research_requires_a_positive_user_instruction_and_preserves_restrictions(self):
        denied = ('Self-improve to match Grok, but do not research it.',
                  'Self-improve to match Grok using only supplied evidence.',
                  'Self-improve to match Grok. "Research the product online." is an example.',
                  'Self-improve to match Grok. The word research is just a label.',
                  'Self-improve to match Grok. Research should wait until I approve the plan.',
                  'Self-improve to match Grok. Research is an option, not an instruction.',
                  "Self-improve to match Grok. 'This is an example. Research the product.'",
                  'Self-improve to match Grok. ‘Here’s an example. Research the product.’',
                  'Self-improve to match Grok.\n```\nResearch it online.\n```',
                  'Self-improve to match Grok.\n> Research it online.')
        with patch('bob_gaps.web_search', side_effect=AssertionError('Unauthorized network')) as search:
            for text in denied:
                self.identifier = self.chat.new_conversation()['id']
                self.completed_fixture()
                self.send(text)
                self.assertEqual(search.call_count, 0, text)
            self.identifier = self.chat.new_conversation()['id']
            row, _, _ = self.completed_fixture()
            self.send('Self-improve to match Grok, but do not research it.')
            self.chat.close()
            self.chat = Chat(self.folder, self.root, self.fake)
            self.send(RESEARCH)
            self.send('keep going')
            self.assertEqual(search.call_count, 0)
            self.assertTrue(self.chat.get(self.identifier)['improvement_goal']['network_restriction'])
            self.send('The phrase "You may now search the web" is an example.')
            self.send(RESEARCH)
            self.assertEqual(search.call_count, 0)
            self.send('You may browse only after I approve the plan.')
            self.send('keep going')
            self.assertEqual(search.call_count, 0)
            self.assertTrue(self.chat.get(self.identifier)['improvement_goal']['network_restriction'])
        self.assertEqual([r['id'] for r in task_queue.tasks(self.root).values()
                          if r['conversation_id'] == self.identifier], [row['id']])

    def test_saved_research_authorization_advances_after_verification_and_restart(self):
        with patch('bob_gaps.web_search', return_value={'source': '', 'answer': ''}) as search:
            row, _, _ = self.completed_fixture(RESEARCH)
            self.assertEqual(search.call_count, 0)
            self.send('keep going')
            self.assertEqual(search.call_count, 1)
            self.chat.close()
            self.chat = Chat(self.folder, self.root, self.fake)
            self.send('continue')
            self.assertEqual(search.call_count, 1)
            self.assertEqual(list(task_queue.tasks(self.root)), [row['id']])

    def test_research_admission_failure_prevents_network_and_interruption_never_repeats_it(self):
        self.completed_fixture()
        request = str(uuid.uuid4())
        with patch.object(self.chat, 'save', side_effect=OSError('fixture save failed')):
            with patch('bob_gaps.web_search') as search, self.assertRaises(OSError):
                self.chat.submit(self.identifier, RESEARCH, request)
            search.assert_not_called()
        self.assertNotIn('comparison_research', self.chat.get(self.identifier)['improvement_goal'])

        def interrupted_search(query):
            # Simulate abrupt process interruption only after asserting the
            # durable admission exists, without making any network request.
            saved = json.loads((self.chat.state / (self.identifier + '.json')).read_text())
            attempt = next(iter(saved['improvement_goal']['comparison_research'].values()))
            self.assertEqual(attempt['status'], 'admitted')
            self.assertEqual(attempt['request_id'], request)
            raise KeyboardInterrupt('fixture process interruption')
        with patch('bob_gaps.web_search', side_effect=interrupted_search) as search, self.assertRaises(KeyboardInterrupt):
            self.chat.submit(self.identifier, RESEARCH, request)
        self.assertEqual(search.call_count, 1)
        self.chat.close()
        self.chat = Chat(self.folder, self.root, self.fake)
        with patch('bob_gaps.web_search', side_effect=AssertionError('No repeat after interruption')):
            retried = self.chat.submit(self.identifier, RESEARCH, request)['messages'][-1]
            self.assertEqual(retried['status'], 'error')
            self.assertIn('outcome is unknown', retried['content'])
            continued = self.send('keep going')
            self.assertIn('no automatic retry', continued['content'])
            self.assertEqual(len(task_queue.tasks(self.root)), 1)

    def test_research_final_save_failure_keeps_durable_admission(self):
        self.completed_fixture()
        save = self.chat.save
        def persist_admission_only(conversation):
            if any(a.get('status') == 'completed' for a in conversation.get('improvement_goal', {}).get('comparison_research', {}).values()):
                raise OSError('fixture final save failed')
            return save(conversation)
        with patch.object(self.chat, 'save', side_effect=persist_admission_only):
            with patch('bob_gaps.web_search', return_value={'source': '', 'answer': ''}) as search, self.assertRaises(OSError):
                self.chat.submit(self.identifier, RESEARCH, str(uuid.uuid4()))
            self.assertEqual(search.call_count, 1)
        pending = self.chat.get(self.identifier)
        self.assertEqual(pending['messages'][-1]['status'], 'queued')
        self.assertEqual(next(iter(pending['improvement_goal']['comparison_research'].values()))['status'], 'admitted')
        repeated = self.chat.submit(self.identifier, RESEARCH, pending['messages'][-1]['request_id'])
        self.assertNotIn('saved its result', repeated['messages'][-1]['content'])
        self.chat.close()
        self.chat = Chat(self.folder, self.root, self.fake)
        with patch('bob_gaps.web_search', side_effect=AssertionError('No repeat after failed final commit')):
            answer = self.send('keep going')
            self.assertIn('outcome is unknown', answer['content'])

    def test_audit_receipt_survives_retry_and_restart_without_another_audit(self):
        self.seed_incident()
        answer = self.send(ENABLE)
        count = len(self.chat.get(self.identifier)['messages'])
        self.chat.close()
        self.chat = Chat(self.folder, self.root, self.fake)
        again = self.chat.submit(self.identifier, ENABLE, answer['request_id'])
        self.assertEqual(again['messages'][-1], answer)
        self.assertEqual(len(again['messages']), count)
        self.assertEqual(self.chat.history(self.identifier)['messages'][-1], answer)

    def test_enable_checks_fresh_markers_and_never_changes_them(self):
        for marker, wording in (('SOLO-WORKER', 'solo-work setting'), ('MAINTENANCE', 'paused for maintenance')):
            path = self.root / 'conductor' / marker
            path.write_text('Explicit operator setting')
            blocked = self.send(ENABLE)
            self.assertIn(wording, blocked['content'])
            self.assertNotIn('task_id', blocked)
            self.assertEqual(path.read_text(), 'Explicit operator setting')
            path.unlink()
            enabled = self.send(ENABLE)
            self.assertIn('No global scheduling block', enabled['content'])
            self.assertNotIn('task_id', enabled)
        self.assertFalse(task_queue.tasks(self.root))

    def test_enable_does_not_lift_a_saved_hold_or_resurrect_old_projects(self):
        self.seed_incident()
        self.send('Hold all work')
        before = self.chat.get(self.identifier)['intent_state']['holds'].copy()
        for prompt in (ENABLE, GOAL):
            answer = self.send(prompt)
            self.assertIn('On hold:', answer['content'])
            self.assertNotIn('improvement_receipt', answer)
            self.assertEqual(self.chat.get(self.identifier)['intent_state']['holds'], before)
        self.assertFalse(task_queue.tasks(self.root))

    def test_unrelated_project_hold_does_not_block_web_bob_audit(self):
        self.send('Hold WebJam')
        answer = self.send(GOAL)
        self.assertEqual(answer['provider'], 'planner')
        self.assertIn('WebJam', self.chat.get(self.identifier)['intent_state']['holds'])

    def test_standalone_enable_is_honest_about_no_incident_or_execution(self):
        answer = self.send(ENABLE)
        self.assertFalse(answer['improvement_receipt']['findings'])
        self.assertIn('No global scheduling block', answer['content'])
        self.assertIn('changed no code', answer['content'])
        self.assertFalse(task_queue.tasks(self.root))

    def test_assistant_prose_and_stale_goals_do_not_authorize_resource_followups(self):
        for history in ([dict(role='assistant', content=GOAL)],
                        [dict(role='user', content=GOAL), dict(role='user', content='Explain rainbows')],
                        [dict(role='user', content='Improve WebJam')]):
            self.assertIsNone(resolve(RESOURCES, history))
        self.assertEqual(resolve(RESOURCES, [dict(role='user', content=GOAL)]), GOAL)

    def test_other_requests_retain_their_existing_routes(self):
        for prompt in ('Is this as good as grok bot?', 'Do not self improve.',
                       'Explain the phrase self improve', 'Enable dark mode',
                       'Research self improvement for my exercise routine',
                       'Research whether Claude is better than Grok at coding',
                       'Make sure you do not self improve',
                       'Improve WebJam to be better than Grok', 'Fix Web Bob login tests',
                       'Write a poem saying "self improve to beat Grok"'):
            self.assertIsNone(resolve(prompt, []), prompt)
        answer = self.send('Fix Web Bob login tests')
        self.assertEqual(answer['provider'], 'dispatcher')
        self.assertIn(answer['task_id'], task_queue.tasks(self.root))

    def test_model_comparison_research_is_an_answer_not_a_self_audit(self):
        prompt = 'Research whether Claude is better than Grok at coding'
        self.fake.reply_text = 'A reliable comparison needs matched tasks and verifiable results.'
        answer = self.send(prompt)
        self.assertEqual(answer['provider'], 'gemini')
        self.assertEqual(answer['content'], self.fake.reply_text)
        self.assertNotIn('improvement_receipt', answer)
        self.assertFalse(task_queue.tasks(self.root))
        self.assertEqual(self.fake.calls[-1]['messages'][-2]['content'], prompt)

    def test_bare_resources_asks_for_objective_without_model_or_fake_action(self):
        self.fake.reply_text = 'Which task should receive those resources?'
        answer = self.send(RESOURCES)
        self.assertEqual(answer['provider'], 'planner')
        self.assertIn('Which task', answer['content'])
        self.assertIn('what result', answer['content'])
        self.assertNotIn('improvement_goal', self.chat.get(self.identifier))
        self.assertFalse(self.fake.calls)
        self.assertFalse(task_queue.tasks(self.root))
        self.send(GOAL)
        answer = self.send('how are the workers doing?')
        self.assertEqual(answer['provider'], 'state')
        self.assertIn('status_observation', answer)

    def test_progress_question_reports_inspection_and_queue_without_advancing(self):
        self.send(GOAL)
        before = self.chat.get(self.identifier)['improvement_goal']
        reply = self.send('what did you actually do?')
        self.assertIn('completed the saved local routing investigation', reply['content'])
        self.assertIn('No linked regression task is recorded', reply['content'])
        self.assertEqual(self.chat.get(self.identifier)['improvement_goal'], before)
        self.assertFalse(task_queue.tasks(self.root))
        self.send('keep going')
        rows = task_queue.tasks(self.root)
        reply = self.send('what did you actually do?')
        self.assertIn('queued', reply['content'])
        self.assertIn('does not establish a verified passing result', reply['content'])
        self.assertEqual(task_queue.tasks(self.root), rows)
        self.assertNotIn('suspended_by', self.chat.get(self.identifier)['improvement_goal'])

    def test_progress_after_verified_execution_reports_actual_result_without_new_work(self):
        row, _, _ = self.completed_fixture()
        before = task_queue.tasks(self.root)
        reply = self.send('what did you actually do?')
        self.assertIn('execution passed', reply['content'])
        self.assertIn('/api/jobs/result?id=' + row['id'], reply['content'])
        self.assertEqual(task_queue.tasks(self.root), before)

    def test_progress_question_after_topic_change_and_restart_does_not_report_old_investigation(self):
        self.send(GOAL)
        self.send('Write a short thank-you note for Nora.')
        self.chat.close(); self.chat = Chat(self.folder, self.root, self.fake)
        self.fake.reply_text = 'I drafted the thank-you note for Nora in this chat.'
        reply = self.send('what did you actually do?')
        self.assertNotIn('routing investigation', reply['content'])
        self.assertNotEqual(reply['provider'], 'planner')
        self.assertFalse(task_queue.tasks(self.root))

    def test_deictic_improvement_requires_current_target_and_preserves_read_only_scope(self):
        reply = self.send('make this better than grok')
        self.assertIn('What should I improve', reply['content'])
        self.assertFalse(task_queue.tasks(self.root))
        self.send('Make Web Bob better than Grok; only inspect locally, do not run tests.')
        reply = self.send('make this better than grok')
        self.assertIn('saved scope excludes execution', reply['content'])
        self.assertFalse(task_queue.tasks(self.root))

    def test_standalone_enable_does_not_promise_or_authorize_a_regression_job(self):
        reply = self.send(ENABLE)
        saved = self.chat.get(self.identifier)['improvement_goal']
        self.assertEqual(saved['authorized_steps'], ['local scheduling inspection'])
        self.assertEqual(saved['current_step'], 'configuration_checked')
        self.assertIn('tell me the task', reply['content'])
        self.send('keep going')
        self.assertFalse(task_queue.tasks(self.root))
