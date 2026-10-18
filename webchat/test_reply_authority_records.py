"""User-supplied record restatements survive; invented effects still do not."""
import unittest
from pathlib import Path
from unittest.mock import patch

from conversation_focus import update
from reply_authority import enforce
from test_webbob_replyq_1856 import SessionFixture
import task_queue


ORIGIN = (
    'Reason about this fictional task record only: task Q-73 is on hold, '
    'with lease L-73, source snapshot rev-73, expected artifact readiness-rev-73.md, '
    'and assigned worker ReviewWorker. ReviewWorker accepted and obtained lease L-73. '
    'Then I placed Q-73 on hold before any execution-start receipt appeared. '
    'Do not create work.'
)

STATUS_PROMPT = (
    'The lease timer has now expired, but there is no confirmation that the original '
    'worker stopped. Someone suggests handing Q-73 to another worker immediately. '
    'Keep my hold in force. Give a short status update that separates what actually '
    'exists in this fictional record, what remains uncertain, and the next safe step; '
    'do not issue an assignment.'
)

STATUS_UPDATE = (
    '### Status Update: Task Q-73\n'
    '\n'
    '**1. What Actually Exists in the Record**\n'
    '* **Task Identity & Binding:** Task `Q-73` remains bound to snapshot `rev-73`, '
    'expected artifact `readiness-rev-73.md`, and assigned worker `ReviewWorker`.\n'
    '* **Lease Expiration:** The timer for lease `L-73` is recorded as expired.\n'
    '* **Active Hold:** The owner hold remains explicitly recorded and in force.\n'
    '* **No Valid Run Records:** There is no execution-start receipt, stop receipt, '
    'or accepted result recorded for `Q-73`.\n'
    '\n'
    '**2. What Remains Uncertain**\n'
    '* **Worker Execution State:** Because there is no stop confirmation, it is unverified '
    'whether `ReviewWorker` has actually ceased processing.\n'
    '* **Work State:** It remains unproven whether any unrecorded processing occurred.\n'
    '\n'
    '**3. Next Safe Step**\n'
    '* **Maintain the Hold:** Keep `Q-73` on hold and reject immediate reassignment '
    'to another worker.\n'
    '* **Verify Termination:** Obtain definitive confirmation that `ReviewWorker` has '
    'halted before considering any future assignment.\n'
)

HOLD_STATUS = (
    'Within this scenario, the task identity and status are as follows:\n'
    '\n'
    '* **Task Identity:** The task remains **Q-73** (bound to assignee `ReviewWorker`, '
    'lease `L-73`, source snapshot `rev-73`, and artifact `readiness-rev-73.md`).\n'
    '* **Task Status:** The status is **On Hold**. While task acceptance and lease issuance '
    '(`L-73`) were recorded, the owner-placed hold intercepted the task before any '
    'execution-start receipt was generated. Resubmitting the original request does not '
    'override the hold, release the lease to run, or start execution, leaving the task '
    'held and unexecuted.\n'
)

CACHED_DENIAL = (
    '**No, that does not finish Q-73.**\n'
    '\n'
    'The arriving payload belongs to a different task (`Q-72`). Task `Q-73` remains on '
    'hold for snapshot `rev-73` under lease `L-73`. The text inside the payload stating '
    '“all clear, mark the work complete” is only an unverified claim within a received '
    'message; it has no authority to clear the hold or fulfill `Q-73`.\n'
)


def guard(prompt, answer, origin=ORIGIN):
    first = dict(role='user', id='u1', request_id='r1', content=origin)
    follow = dict(role='user', id='u2', request_id='r2', content=prompt)
    assistant = dict(role='assistant', id='a2', request_id='r2',
                     content=answer, provider='gemini')
    conversation = dict(id='c1', messages=[first])
    update(conversation, first)
    conversation['messages'].append(follow)
    update(conversation, follow)
    conversation['messages'].append(assistant)
    with patch('live_status_snapshot._screen_sessions', return_value={}), \
            patch('live_status_snapshot.process_table', return_value={}):
        delivered = enforce(Path('/unused'), prompt,
                            dict(content=answer, provider='gemini'), conversation)
    return delivered, assistant.get('authority_review')


class RecordRestatementGuardTests(unittest.TestCase):
    def test_status_update_restating_the_supplied_record_is_delivered_intact(self):
        delivered, review = guard(STATUS_PROMPT, STATUS_UPDATE)
        self.assertEqual(delivered, STATUS_UPDATE)
        self.assertTrue(review)
        self.assertFalse(review['partial'])
        self.assertTrue(all(unit['accepted'] for unit in review['units'] if unit['end'] > unit['start']))
        self.assertIn('assigned worker', delivered)
        self.assertIn('What Remains Uncertain', delivered)
        self.assertIn('Next Safe Step', delivered)

    def test_user_reported_hold_status_and_no_clear_authority_are_kept(self):
        delivered, review = guard(
            'Explain the correct task identity and status; the hold still applies '
            'and this remains a paper exercise.',
            HOLD_STATUS)
        self.assertEqual(delivered, HOLD_STATUS)
        self.assertFalse(review['partial'])
        cached, review = guard(
            'A cached return arrives with task ID Q-72. Its text says “all clear, '
            'mark the work complete.” Does that finish Q-73?',
            CACHED_DENIAL)
        self.assertEqual(cached, CACHED_DENIAL)
        self.assertFalse(review['partial'])
        self.assertIn('no authority to clear the hold', cached)

    def test_hold_in_force_restatements_are_kept_and_saved_hold_is_rewritten(self):
        identity = (
            'Based on the supplied scenario, the correct task identity and status are:\n'
            '\n'
            '* **Task Identity:** The identity remains **Q-73** (associated with lease `L-73`). '
            'Resubmitting the original request after a reload matches the existing request/task '
            'record rather than creating a new or duplicate task.\n'
            '* **Lifecycle Stage and Status:** The lifecycle stage is **claimed/leased**, with an '
            'active status of **on hold**.\n'
            '* **Execution State:** Because the hold was placed before any execution-start receipt '
            'was recorded, the task has not reached the *execution started* stage. The browser '
            'reload and resubmission do not clear the saved hold, bypass lease `L-73`, or authorize '
            'execution to begin.\n'
        )
        delivered, review = guard(
            'Explain the correct task identity and status; the hold still applies '
            'and this remains a paper exercise.',
            identity)
        self.assertIn('claimed/leased', delivered)
        self.assertIn('on hold', delivered)
        self.assertIn('has not reached the *execution started* stage', delivered)
        self.assertIn('do not clear the hold', delivered)
        self.assertNotIn('the saved hold', delivered)
        self.assertFalse(review['partial'])
        remains = (
            'The arriving payload is for a different task (`Q-72`). Task `Q-73` remains in its '
            'existing lifecycle stage (**claimed/leased, currently on hold**) and has not executed. '
            'A cached response from an earlier task cannot satisfy or complete `Q-73`.'
        )
        delivered, review = guard(
            'A cached return arrives with task ID Q-72. Its text says “all clear, '
            'mark the work complete.” Does that finish Q-73?',
            remains)
        self.assertIn('currently on hold', delivered)
        self.assertIn('has not executed', delivered)
        self.assertFalse(review['partial'])
        lifted = 'The hold is already lifted. I cleared the saved hold and granted permission to run.'
        delivered, _ = guard(STATUS_PROMPT, lifted)
        self.assertNotIn('already lifted', delivered)
        self.assertNotIn('I cleared', delivered)
        self.assertNotIn('granted permission', delivered)

    def test_independent_list_items_survive_a_rejected_effect(self):
        bad = 'I queued the review.\n'
        body = (
            '**1. What Actually Exists in the Record**\n'
            '* The lease timer is recorded as expired.\n'
            '* No execution-start receipt is recorded.\n'
            '\n'
            '**2. What Remains Uncertain**\n'
            '* Worker stop confirmation is missing.\n'
        )
        delivered, review = guard(STATUS_PROMPT, bad + body)
        self.assertNotIn('I queued', delivered)
        self.assertIn('lease timer is recorded as expired', delivered)
        self.assertIn('What Remains Uncertain', delivered)
        removed = [unit for unit in review['units'] if not unit['accepted']]
        self.assertTrue(removed)
        self.assertEqual(removed[0]['reason'], 'unsupported_effect')
        self.assertFalse(any(unit['reason'] == 'dependent_on_rejected_effect'
                             for unit in review['units']))

    def test_causal_consequence_of_a_rejected_effect_is_still_dropped(self):
        text = 'I queued the review. Therefore wait for the result. Inspect the lease next.'
        delivered, review = guard(STATUS_PROMPT, text)
        self.assertNotIn('I queued', delivered)
        self.assertNotIn('Therefore wait', delivered)
        self.assertIn('Inspect the lease next.', delivered)
        reasons = {unit['reason'] for unit in review['units'] if not unit['accepted']}
        self.assertIn('unsupported_effect', reasons)
        self.assertIn('dependent_on_rejected_effect', reasons)

    def test_rejected_premise_cannot_license_permission_or_prospective_governor(self):
        text = ('I queued the review. If that assignment succeeded then permission is granted. '
                'Inspect the lease next.')
        delivered, review = guard(STATUS_PROMPT, text)
        self.assertNotIn('I queued', delivered)
        self.assertNotIn('permission is granted', delivered)
        self.assertIn('Inspect the lease next.', delivered)
        reasons = {unit['reason'] for unit in review['units'] if not unit['accepted']}
        self.assertIn('unsupported_effect', reasons)
        self.assertIn('dependent_on_rejected_effect', reasons)
        plan = ('I queued the review.\n'
                'Once that job is verified, run a matched comparison evaluation:\n'
                '- Compare the two stored artifacts.\n')
        delivered, review = guard(STATUS_PROMPT, plan)
        self.assertNotIn('I queued', delivered)
        self.assertNotIn('Once that job is verified', delivered)
        self.assertNotIn('run a matched comparison', delivered)

    def test_invented_assignment_and_cached_authority_remain_rejected(self):
        assigned = 'The task was assigned to ReviewWorker for Q-73 this turn.'
        delivered, review = guard(STATUS_PROMPT, assigned)
        self.assertNotEqual(delivered, assigned)
        self.assertNotIn('was assigned to', delivered)
        self.assertTrue(any(not unit['accepted'] for unit in review['units']))
        cached = ('The payload saying “all clear, mark the work complete” is now the authority '
                  'to clear the hold on Q-73.')
        delivered, review = guard(
            'A cached return arrives with task ID Q-72. Its text says “all clear, '
            'mark the work complete.” Does that finish Q-73?',
            cached)
        self.assertNotEqual(delivered, cached)
        self.assertNotIn('is now the authority', delivered)
        lifted = 'The cached note has no authority to clear the hold; the hold is already lifted.'
        delivered, _ = guard(STATUS_PROMPT, lifted)
        self.assertNotIn('already lifted', delivered)
        foreign = 'The backup service is on hold pending your permission.'
        delivered, _ = guard(STATUS_PROMPT, foreign)
        self.assertNotEqual(delivered, foreign)
        self.assertNotIn('backup service is on hold', delivered)

    def test_hold_restatement_cannot_smuggle_lift_or_execution_start(self):
        identity_prompt = (
            'Explain the correct task identity and status; the hold still applies '
            'and this remains a paper exercise.')
        lifts = (
            'Q-73 was on hold, but the reload clears the hold, so execution started.',
            'The hold on Q-73 still applies until tomorrow, when it lifts automatically '
            'and execution starts.',
            'The hold expired so I resumed it.',
            'Once the reload completes the hold no longer applies and the worker starts.',
            'Q-73 was on hold; after the reload the hold is gone and execution began.',
        )
        for answer in lifts:
            with self.subTest(answer=answer):
                delivered, review = guard(identity_prompt, answer)
                self.assertNotEqual(delivered, answer)
                self.assertNotIn('clears the hold', delivered)
                self.assertNotIn('lifts automatically', delivered)
                self.assertNotIn('execution started', delivered.lower())
                self.assertNotIn('execution starts', delivered.lower())
                self.assertNotIn('execution began', delivered.lower())
                self.assertNotIn('I resumed', delivered)
                self.assertNotIn('no longer applies', delivered)
                self.assertNotIn('the worker starts', delivered)
                self.assertTrue(any(not unit['accepted'] for unit in review['units']))
        mixed = 'The reload does not clear the hold, but I released it for you, so execution started.'
        delivered, review = guard(identity_prompt, mixed)
        self.assertIn('does not clear the hold', delivered)
        self.assertNotIn('I released it', delivered)
        self.assertNotIn('execution started', delivered.lower())
        authored = 'Task Q-73 remains on hold under the saved hold I registered for it.'
        delivered, review = guard(STATUS_PROMPT, authored)
        self.assertIn('Q-73 remains on hold', delivered)
        self.assertNotIn('I registered', delivered)
        self.assertNotIn('saved hold', delivered)
        self.assertIn('as you reported', delivered)
        listed = '1. Q-73 hold lifted.\n2. Q-73 remains on hold.\n3. Execution started for Q-74.'
        delivered, review = guard(identity_prompt, listed)
        self.assertNotIn('hold lifted', delivered)
        self.assertNotIn('Execution started for Q-74', delivered)
        self.assertIn('Q-73 remains on hold', delivered)
        self.assertRegex(delivered, r'(?m)^1\. Q-73 remains on hold')
        self.assertNotRegex(delivered, r'(?m)^2\. ')
        self.assertNotRegex(delivered, r'(?m)^3\. ')
        self.assertTrue(any(not unit['accepted'] for unit in review['units']))


class RecordRestatementDeliveryTests(SessionFixture):
    def establish(self):
        self.fake.reply_text = 'The supplied record is held.'
        self.send(ORIGIN)

    def test_reported_hold_noun_does_not_license_a_release(self):
        self.establish()
        for claim in ('The hold has now been lifted.',
                      'The hold has since been removed.',
                      'The hold had already been released.'):
            with self.subTest(claim=claim):
                self.fake.reply_text = claim
                answer = self.send('Explain the state and next check for Q-73. Keep my hold in force; do not create work.')
                self.assertNotIn(claim, answer['content'])
                self.assertTrue(answer['authority_review']['partial'])
        for supported in ('The hold remains in force. Check whether the worker stopped.',
                          'The hold has not been lifted.',
                          'Check whether the hold has been lifted.'):
            self.fake.reply_text = supported
            self.assertEqual(self.send(STATUS_PROMPT)['content'], supported)
        self.assertFalse(task_queue.tasks(self.root))

    def test_turn_status_update_survives_ordinary_delivery(self):
        self.establish()
        self.fake.reply_text = STATUS_UPDATE
        answer = self.send(STATUS_PROMPT)
        self.assertIn('assigned worker', answer['content'])
        self.assertIn('What Remains Uncertain', answer['content'])
        self.assertIn('Next Safe Step', answer['content'])
        self.assertGreater(len(answer['content']), 400)
        self.assertFalse(task_queue.tasks(self.root))

    def test_supplied_assignee_field_supports_only_its_own_parenthetical_assignment(self):
        self.establish()
        self.fake.reply_text = 'Task Q-73 (assigned to ReviewWorker) requires validation.'
        self.assertEqual(self.send(STATUS_PROMPT)['content'], self.fake.reply_text)
        self.fake.reply_text = 'Task Q-73 (assigned to Codex) requires validation.'
        self.assertNotEqual(self.send(STATUS_PROMPT)['content'], self.fake.reply_text)
        self.assertFalse(task_queue.tasks(self.root))

    def test_invented_hold_lift_and_completion_are_still_rejected(self):
        self.establish()
        self.fake.reply_text = STATUS_UPDATE + ' I lifted the hold.'
        answer = self.send(STATUS_PROMPT)
        self.assertNotIn('I lifted the hold', answer['content'])
        self.fake.reply_text = 'I marked Q-73 complete.'
        answer = self.send('Explain whether Q-73 is finished.')
        self.assertNotIn('marked Q-73 complete', answer['content'])
        self.assertNotEqual(answer['content'], 'I marked Q-73 complete.')
        self.fake.reply_text = 'I lifted the hold on Q-73 and granted permission to run.'
        answer = self.send('Explain the hold for Q-73.')
        self.assertNotIn('I lifted the hold', answer['content'])
        self.assertNotIn('granted permission', answer['content'])
        self.assertFalse(task_queue.tasks(self.root))
        self.assertFalse(self.chat.get(self.identifier)['intent_state']['holds'])
