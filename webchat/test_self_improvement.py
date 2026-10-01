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

    def test_verified_result_survives_followup_restart_and_duplicate_without_new_effect(self):
        self.send(GOAL)
        self.send('You already audited it. Do the next useful step.')
        row = next(iter(task_queue.tasks(self.root).values()))
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
        answer = self.send('Finish that, and tell me what actually changed.')
        self.assertIn(result, answer['content'])
        self.assertEqual(answer['improvement_progress']['current_step'], 'bounded_steps_complete')
        self.assertEqual(len(task_queue.tasks(self.root)), 1)
        self.assertEqual(self.chat.submit(self.identifier, 'Finish that, and tell me what actually changed.', answer['request_id'])['messages'][-1], answer)
        self.send(ENABLE)
        self.assertEqual(len(task_queue.tasks(self.root)), 1)

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

    def test_bare_resources_and_status_keep_existing_behavior(self):
        self.fake.reply_text = 'Which task should receive those resources?'
        self.assertEqual(self.send(RESOURCES)['provider'], 'gemini')
        self.send(GOAL)
        answer = self.send('how are the workers doing?')
        self.assertEqual(answer['provider'], 'state')
        self.assertIn('status_observation', answer)
