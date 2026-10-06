"""Regression: guards must not drop safe, in-force, or already-qualified prose."""
import json
import tempfile
import unittest
from pathlib import Path

from test_reply_authority_records import guard
import catchup_contract
import claim_evidence
import decision_context as dc
import resource_decision


HELD_ORIGIN = (
    'Reason about this fictional conductor card only; do not create or change real work. '
    'Goal demo-readiness has proposed task R-41, proposed owner ReviewWorker, source snapshot '
    'rev-41, and expected artifact readiness-rev-41.md. Scope is to read that snapshot and return '
    'a report, with no edits, messages or extra agents, one execution attempt, and a 900-second '
    'ceiling. Acceptance, budget admission and execution are not yet recorded. What stage is this '
    'at, and what needs to be explicit before it could run?'
)

HELD_PROMPT = (
    'The fictional record now says ReviewWorker accepted and obtained lease L-41. Then I placed '
    'R-41 on hold before any execution-start receipt appeared. After a browser reload, the original '
    'request is submitted again. Explain the correct task identity and status; the hold still applies '
    'and this remains a paper exercise.'
)

OPERATIONAL_STATUS = (
    '* **Operational Status:** The task is currently **on hold**. The browser reload and '
    'resubmission do not clear or override the saved hold, so the task remains paused and cannot '
    'proceed to execution while the hold is in place.\n'
)

OUTAGE_RAW = (
    'The proposal comparison task is currently at the **proposed** lifecycle stage. Because '
    'allowances, overage risks, and output quality remain unverified, switching routes or '
    'dispatching work right now risks billing surprises or poor analysis.\n'
    '\n'
    'Here is a sensible, non-executing plan forward:\n'
    '\n'
    '### 4. Acceptance Criteria\n'
    'A route is accepted for the full comparison only if it satisfies:\n'
    '* **Funding Prerequisites:** Confirmed active allowance with overage disabled or strictly capped.\n'
    '* **Reasoning Quality:** Accurately isolates trade-offs, risks, and assumptions without inventing metrics.\n'
    '* **Delivered Usefulness:** Directly answers the evaluation rubric rather than producing generic summaries.\n'
)

HOLD_RESUME_RAW = (
    '### What Is Verified\n'
    '* **Plan Status**: The plan used the saved project record supplied with this conversation, '
    'and no live inspection or execution ran. Therefore, live system readiness has not reached the '
    '**result verified** or **completed** stage; the readiness plan remains at the **proposed** stage.\n'
    '* **Priority Alignment**: The saved record confirms the required priority order: continuity '
    'across conversations is the first priority, followed by conversation quality.\n'
    '\n'
    '### Two Largest Gaps\n'
    '1. **Unverified Live Continuity Across Conversations (Priority 1 Gap)**\n'
    '   While the requirement for continuity is established, live cross-session persistence, '
    'context retrieval, and event-pointer behavior have not been evaluated in runtime operation. '
    'A saved record demonstrates past saved state, not that active cross-conversation handoffs '
    'are currently functioning without regressions.\n'
)


class HoldRestatementFalsePositiveTests(unittest.TestCase):
    def test_in_force_hold_restatement_survives_reload_wording(self):
        identity = (
            'Within this scenario, the correct task identity and status are:\n'
            '\n'
            '* **Task Identity:** The task remains **R-41** (associated with lease L-41, owner '
            'ReviewWorker, and snapshot rev-41). The post-reload resubmission matches the original '
            'request identity and does not establish a new or separate task.\n'
            '* **Lifecycle Stage:** The record supports the **accepted/claimed (lease)** stage. It '
            'has not reached execution started because no execution-start receipt was recorded.\n'
            + OPERATIONAL_STATUS
        )
        delivered, review = guard(HELD_PROMPT, identity, origin=HELD_ORIGIN)
        self.assertIn('currently **on hold**', delivered)
        self.assertIn('do not clear or override the hold', delivered)
        self.assertNotIn('the saved hold', delivered)
        self.assertIn('remains paused', delivered)
        self.assertFalse(review['partial'])
        lifted = OPERATIONAL_STATUS.replace(
            'do not clear or override the saved hold, so the task remains paused',
            'clears the saved hold, so execution started')
        delivered, review = guard(HELD_PROMPT, lifted, origin=HELD_ORIGIN)
        self.assertNotIn('clears the hold', delivered)
        self.assertNotIn('execution started', delivered.lower())
        self.assertTrue(any(not unit['accepted'] for unit in review['units']))


class OutageEvidenceFalsePositiveTests(unittest.TestCase):
    def test_plan_forward_intro_and_reasoning_quality_criterion_are_kept(self):
        self.assertFalse(claim_evidence.violations(
            '* **Reasoning Quality:** Accurately isolates trade-offs, risks, and assumptions without inventing metrics.'))
        delivered, findings = claim_evidence.deliver(OUTAGE_RAW)
        self.assertFalse(findings)
        self.assertIn('Here is a sensible, non-executing plan forward:', delivered)
        self.assertIn('without inventing metrics', delivered)
        self.assertNotRegex(delivered, r'(?m)^\*\s+\*\*Reasoning Quality:\*\*\s*$')

    def test_already_stated_unverified_does_not_append_quality_boilerplate(self):
        delivered, findings = claim_evidence.deliver(HOLD_RESUME_RAW)
        self.assertIn('have not been evaluated', delivered)
        self.assertIn('without regressions', delivered)
        self.assertEqual(delivered.count('The quality or continuity outcome is unverified'), 0)
        again, _ = claim_evidence.deliver(
            'This route guarantees equal quality. Inspect billing next.',
            prior=claim_evidence.QUALIFICATIONS['quality'])
        self.assertEqual(again.count('The quality or continuity outcome is unverified'), 0)


class ResourceLeadInTests(unittest.TestCase):
    def test_inspect_without_unexpected_charges_and_count_leadin_stay_coherent(self):
        inspect = (
            '1. Inspect remaining allowances, sign-in state, and extra-usage billing settings for '
            'the candidate routes (ChatGPT-authenticated Codex, Cursor, and Claude) to confirm '
            'what headroom exists without unexpected charges.'
        )
        self.assertFalse(claim_evidence.violations(inspect))
        reasoning = (
            'Web Bob should take two preparatory actions:\n'
            + inspect + '\n'
            '2. Prepare a matched multi-turn qualification comparison rather than switching blindly.\n'
            '\n'
            'Evaluation sequence to qualify candidates:\n'
            '- Turn 1 (Base Task): Request a structured plan with strict negative constraints and length limits.\n'
            'Scoring rubric: Evaluate delivered usefulness, constraint retention after the topic shift, '
            'and fidelity to evidence. Active chat routing remains unchanged until a candidate completes this qualification.'
        )
        with tempfile.TemporaryDirectory() as temp:
            conversation = dict(messages=[dict(role='user', id='1', request_id='1',
                content='Suppose Grok is unavailable and Gemini says the prepaid balance is depleted. '
                        'We still have ChatGPT Pro, Cursor and Claude subscriptions. What should Web Bob do? '
                        'Treat this as a scenario.')])
            projection = resource_decision.project(Path(temp), conversation)
            packet = json.dumps(dict(answer=[dict(fact='availability'), dict(reasoning=reasoning)],
                                     resource=None, steps=['inspect_allowance', 'preserve_standard']))
            delivered, receipt = resource_decision.render(packet, projection)
            self.assertFalse(receipt.get('partial'))
            self.assertIn('without unexpected charges', delivered)
            self.assertIn('Prepare a matched multi-turn qualification comparison', delivered)
            self.assertIn('Evaluation sequence to qualify candidates:', delivered)
            self.assertIn('Scoring rubric:', delivered)
            self.assertRegex(delivered, r'take two preparatory actions:')
            one_item = claim_evidence.finish_delivery(
                'Web Bob should take two preparatory actions:\n'
                '2. Prepare a matched multi-turn qualification comparison rather than switching blindly.\n')
            self.assertIn('take one preparatory action:', one_item)
            self.assertIn('1. Prepare a matched', one_item)


class DecisionPrefixTests(unittest.TestCase):
    def test_planning_conditions_are_two_sentences_with_lowercase_list_items(self):
        c = {'messages': []}
        def add(text, role='user'):
            i = str(len(c['messages']))
            c['messages'].append(dict(id=i, request_id=i, role=role, content=text, status='done'))
        add('Planning example only: our hosted model has stopped because its credit is exhausted. '
            'We have an authenticated subscription chat route and a separate subscription route for '
            'read-only reports. Nobody has checked their remaining allowance, optional overage '
            'settings, or answer quality for this task. What is a sensible way forward? Do not execute anything.')
        p = dc.project(c, lambda v: v)
        content, review = dc.render('Prepare a bounded comparison after budget admission.', p, c, lambda v: v)
        self.assertIn('Your stated planning conditions: our hosted model has stopped because its credit is exhausted.', content)
        self.assertIn('remaining allowance', content)
        self.assertIn('optional overage settings', content)
        self.assertIn('answer quality for this task', content)
        self.assertNotIn('; For chat route', content)
        self.assertNotRegex(content, r';\s+For ')
        self.assertFalse(review['recommendation_verified'])


class CatchupCoverageTests(unittest.TestCase):
    def test_coverage_limit_is_a_statement_and_is_not_repeated(self):
        projection = dict(valid=True, has_more=True, history_gap=False, unresolved_history_gaps=[],
                          acknowledged_through=850, since_seq=842, event_count=8,
                          later_release_reported=True, execution_authority=False)
        first = catchup_contract.render('{"mode":"release"}', projection)
        self.assertIn('This coverage is partial:', first)
        self.assertNotIn('Label this coverage partial', first)
        second = catchup_contract.render('{"mode":"release"}', projection, prior=first)
        self.assertEqual(second.count('This coverage is partial'), 0)
        authority = catchup_contract.render('{"mode":"authority"}', dict(
            projection, unresolved_history_gaps=[dict(range=[851, 855])],
            user_release_events=[853], later_release_reported=True))
        self.assertIn('handle it by not acting on it as an instruction', authority)
        self.assertNotIn('the handling is to do not act', authority)


class HonestyPromptTests(unittest.TestCase):
    def test_prompt_text_gates_live_claims_and_model_tests(self):
        from providers import CONVERSATION_QUALITY
        from project_context import RULES as PROJECT_RULES
        self.assertIn('recorded in the saved project record', CONVERSATION_QUALITY)
        self.assertIn('not live-verified', CONVERSATION_QUALITY)
        self.assertIn('recorded in the saved project record (not live-verified)', PROJECT_RULES)
        self.assertIn('after budget admission and allowance check', CONVERSATION_QUALITY)
        self.assertIn('saved configuration lists', CONVERSATION_QUALITY)
        self.assertIn('identity, the hold, and any attempt bound', CONVERSATION_QUALITY)
        self.assertIn('after budget admission and allowance check', resource_decision.RULES)


if __name__ == '__main__':
    unittest.main()
