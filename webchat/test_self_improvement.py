"""Owner incident regressions through the real saved conversation/submit path."""
import hashlib
import json
import uuid

from app import Chat
from self_improvement import resolve
from task_dispatch import task_queue
from test_webbob_replyq_1856 import SessionFixture


GOAL = 'Ok top priority is to make web bob better than grok bot. Make it happen any and all resources.'
ENABLE = 'Ok enable what we need to enable'
RESEARCH = 'Ok well make that your goal. Research what grok bot does and self improve to be better than it.'
RESOURCES = 'top priority use any and all resources'


class ImprovementTests(SessionFixture):
    def seed_incident(self):
        value = self.chat.get(self.identifier)
        for ask, answer in ((RESEARCH, "I'm definitely on board with it! I'll focus on improving."),
                            (ENABLE, "I can't enable additional project workers right now because that functionality is currently disabled.")):
            for role, content in (('user', ask), ('assistant', answer)):
                value['messages'].append(dict(id=str(uuid.uuid4()), role=role, content=content, status='done'))
        self.chat.save(value)
        self.chat.conversations[self.identifier] = value
        return value['messages'][:]

    def test_exact_owner_chain_completes_audits_and_saves_specific_cases_without_workers(self):
        prior = self.seed_incident()
        for prompt in (GOAL, RESOURCES, 'Ok make it happen use any and all resources.', RESEARCH,
                       'Yep and coordinate with Bob the Bot of this but use all of these to self improve.',
                       ENABLE, 'Constant self improvement is in your guiding principles'):
            with self.subTest(prompt=prompt):
                previous = self.chat.get(self.identifier)['messages'][:]
                answer = self.send(prompt)
                receipt = answer['improvement_receipt']
                self.assertEqual(answer['provider'], 'planner')
                self.assertNotIn('status_observation', answer)
                self.assertEqual(receipt['completed_step'], 'local_transcript_and_scheduling_audit')
                self.assertEqual(receipt['inspected_message_count'], len(previous))
                self.assertEqual(receipt['transcript_sha256'], hashlib.sha256(json.dumps(previous, sort_keys=True).encode()).hexdigest())
                self.assertEqual({r['kind'] for r in receipt['findings']},
                                 {'historical_worker_block_claim', 'assent_without_action_receipt'})
                self.assertIn(RESEARCH, [r['prompt'] for r in receipt['regression_cases']])
                self.assertIn(ENABLE, [r['prompt'] for r in receipt['regression_cases']])
                self.assertIn(prompt, [r['prompt'] for r in receipt['regression_cases']])
                self.assertIn('no global scheduling block', answer['content'])
                self.assertIn('First step completed', answer['content'])
                self.assertIn('Next implementation step', answer['content'])
                self.assertFalse(receipt['code_changed'])
                self.assertEqual(receipt['workers_started'], 0)
                self.assertEqual(receipt['queued_jobs'], 0)
                self.assertFalse(task_queue.tasks(self.root))
        self.assertFalse(self.fake.calls)
        self.assertEqual(self.chat.get(self.identifier)['messages'][:len(prior)], prior)

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
        self.seed_incident()
        for marker, wording in (('SOLO-WORKER', 'solo-work setting'), ('MAINTENANCE', 'paused for maintenance')):
            path = self.root / 'conductor' / marker
            path.write_text('Explicit operator setting')
            blocked = self.send(ENABLE)
            self.assertIn(wording, blocked['content'])
            self.assertTrue(blocked['improvement_receipt']['scheduling_blocks'][marker])
            self.assertEqual(path.read_text(), 'Explicit operator setting')
            path.unlink()
            enabled = self.send(ENABLE)
            self.assertIn('no global scheduling block', enabled['content'])
            self.assertFalse(any(enabled['improvement_receipt']['scheduling_blocks'].values()))
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
        self.assertIn('no matching failed reply', answer['content'])
        self.assertIn('no code has changed', answer['content'])
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

    def test_model_comparison_research_keeps_its_task_instead_of_a_self_audit(self):
        prompt = 'Research whether Claude is better than Grok at coding'
        answer = self.send(prompt)
        self.assertEqual(answer['provider'], 'dispatcher')
        self.assertNotIn('improvement_receipt', answer)
        self.assertEqual(task_queue.tasks(self.root)[answer['task_id']]['prompt'], prompt)

    def test_bare_resources_and_status_keep_existing_behavior(self):
        self.fake.reply_text = 'Which task should receive those resources?'
        self.assertEqual(self.send(RESOURCES)['provider'], 'gemini')
        self.send(GOAL)
        answer = self.send('how are the workers doing?')
        self.assertEqual(answer['provider'], 'state')
        self.assertIn('status_observation', answer)
