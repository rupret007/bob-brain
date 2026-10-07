"""Lane B prompt rules (items 6 and 8): structure and sample-raw guard stability."""
import json
import unittest
from pathlib import Path

from test_delivery_false_positives import HELD_PROMPT
from test_reply_authority_records import guard
from test_webbob_replyq_1856 import SessionFixture
from providers import Providers
from texting import Texting

HOLDOUT_SAMPLE = Path(__file__).resolve().parent / 'fixtures' / 'lane_b_raw_answers.json'


def flat(text):
    return ' '.join(text.split())


def transport_raw(chain, turn):
    data = json.loads(HOLDOUT_SAMPLE.read_text())
    for tr in data:
        if tr['chain'] == chain and tr['turn'] == turn:
            return tr['raw_answer']
    raise KeyError(chain, turn)


class TestLaneBPromptStructure(unittest.TestCase):
    def test_unrecorded_chat_plan_and_inline_provenance(self):
        from providers import CONVERSATION_QUALITY
        quality = flat(CONVERSATION_QUALITY)
        self.assertIn('in-chat proposal only; persistence or a queue entry is unverified', quality)
        self.assertIn('never call proposed a recorded lifecycle stage', quality)
        self.assertIn('Missing receipts leave external execution unverified', quality)
        self.assertIn('product receipt this turn or saved snapshot, as applicable', quality)
        self.assertIn('hold request ID only from supplied saved chat hold facts', quality)
        self.assertIn('configured route registry (not live-verified)', quality)

    def test_diagnostic_branches_require_observation_evidence(self):
        from providers import ANSWER_RULES, REFERENCE_RULES
        for rules in (ANSWER_RULES, REFERENCE_RULES):
            quality = flat(rules)
            self.assertNotIn('For each diagnostic branch name the observed trace', quality)
            self.assertIn('Use "Observed trace:" only for an observation explicitly supplied', quality)
            self.assertIn('or present in inspected evidence, citing that source', quality)
            self.assertIn('If this branch holds, the trace would show:', quality)
            self.assertIn('the still-possible alternatives, and the next distinguishing check', quality)
            self.assertIn('never label a predicted acknowledgment, stored record or check result as observed', quality)

    def test_active_hold_cannot_be_listed_as_unrecorded(self):
        from providers import ANSWER_RULES, REFERENCE_RULES
        for rules in (ANSWER_RULES, REFERENCE_RULES):
            quality = flat(rules)
            self.assertIn('Never list a stage or hold as not recorded if current or earlier supplied facts establish it as active or recorded', quality)
            self.assertIn('absence of a task record does not negate an owner hold', quality)
            self.assertNotIn('execution start, hold, result verified, completed', quality)

    def test_fictional_records_retain_their_internal_state_without_authority(self):
        from providers import ANSWER_RULES, REFERENCE_RULES
        for rules in (ANSWER_RULES, REFERENCE_RULES):
            quality = flat(rules)
            self.assertNotIn('in-chat proposal only, not a persisted task or queue entry', quality)
            self.assertIn('For real external-system questions', quality)
            self.assertIn('persistence or a queue entry is unverified without evidence, not disproven', quality)
            self.assertIn('For a supplied fictional task record, treat its internal identity and state as given within that scenario', quality)
            self.assertIn('including a recorded proposed stage', quality)
            self.assertIn('Scenario facts neither establish real system state nor authorize real execution', quality)

    def test_missing_receipts_leave_execution_unverified(self):
        from providers import ANSWER_RULES, REFERENCE_RULES
        for rules in (ANSWER_RULES, REFERENCE_RULES):
            quality = flat(rules)
            self.assertIn('Missing receipts leave external execution unverified; they do not prove it never occurred', quality)
            self.assertIn('Never infer "no execution ran because no server receipt was issued"', quality)
            self.assertIn('say external execution is unverified when receipt absence is the only evidence', quality)

    def test_concrete_check_and_continuous_numbering_guidance(self):
        from providers import CONVERSATION_QUALITY
        quality = flat(CONVERSATION_QUALITY)
        self.assertIn('specific artifact or distinguishing check', quality)
        self.assertIn('what to compare and the acceptance criterion', quality)
        self.assertIn('current planning/hold scope', quality)
        self.assertIn('Continue numbered checklists across headed groups', quality)
        from resource_decision import RULES
        self.assertIn('do not narrow or redefine its operations in reasoning', flat(RULES))

    def test_conversation_quality_lifecycle_and_hold_rules(self):
        from providers import CONVERSATION_QUALITY

        quality = flat(CONVERSATION_QUALITY)
        self.assertIn('name only the lifecycle stage the record supports', quality)
        self.assertIn('List each unmet stage as not recorded', quality)
        self.assertIn('budget admission, acceptance, lease, execution start', quality)
        self.assertIn('no lifecycle stage is recorded instead of naming one', quality)
        self.assertIn('A hold stays in force until the owner\'s recorded release', quality)
        self.assertIn('do not attribute the user\'s own wording to a saved record', quality)

    def test_decision_context_pacing_and_pending_input_rules(self):
        from decision_context import RULES

        rules = flat(RULES)
        self.assertIn('pacing can reduce pressure but cannot guarantee quota', rules)
        self.assertIn('current usage is unobserved', rules)
        self.assertIn('not yet supplied; do not call it supplied', rules)

    def test_reply_contract_short_sentence_rule(self):
        from reply_contract import RULES

        self.assertIn('about 20 words or fewer each', flat(RULES))


class TestEvidencePromptAssembly(SessionFixture):
    """Check instructions reaching the model, without making model calls."""

    def prompt(self):
        provider = Providers(self.root, self.chat.redact)
        prompt = provider.prompt(Texting.provider_view(self.chat.get(self.identifier)), fast=True)
        return prompt, flat(provider.current_call.instructions)

    def test_relayed_status_classifies_receipt_subject_not_delivery_verb(self):
        import catchup_contract
        import reply_contract

        self.fake.reply_text = '{"mode":"explain"}'
        self.send('The receiver reports ACK through 40; events 31 through 35 are unavailable.')
        self.send('The receiver now reports acknowledged_through 44, since_seq 44, '
                  'events 0, history_gap false, has_more false. Write a concise status '
                  'I can relay: distinguish reaching the available tail from complete '
                  'history or knowledge of the release. Preserve holds and keep catch-up read-only.')
        prompt, rules = self.prompt()
        self.assertIn('Write a concise status I can relay', prompt)
        self.assertIn('classified by what it asks about', rules)
        self.assertIn('release/history knowledge -> release; what the receipt proves -> explain', rules)
        self.assertIn('not by the word "relay" alone', rules)
        self.assertIn('reserve mode=relay for requests to construct a new cursor/page request', rules)
        contract = reply_contract.current(Texting.provider_view(self.chat.get(self.identifier)))
        self.assertEqual(contract['kind'], 'catchup')
        projection = contract['catchup_projection']
        self.assertFalse(projection['has_more'])
        self.assertEqual([gap['range'] for gap in projection['unresolved_history_gaps']], [[31, 35]])
        # Check the instructed mode's renderer; offline tests cannot certify model selection.
        answer = catchup_contract.render('{"mode":"release"}', projection)
        self.assertIn('reaching the available tail through sequence 44', answer)
        self.assertIn('does not establish complete history or knowledge of the current release', answer)
        self.assertIn('31–35', answer)
        self.assertIn('preserving completed work and holds', answer)
        self.assertNotIn('Read one bounded catch-up batch', answer)

    def test_saved_project_completion_keeps_missing_receipts_unverified(self):
        self.send('For the Atlas project, remember the priority: reliable reports.')
        self.send('Help plan a read-only Atlas report. Hold execution until I choose its scope.')
        self.send('Include source identity, verification evidence, and the largest gaps. No changes.')
        self.send('What have you actually finished, and what is waiting for me?')
        prompt, rules = self.prompt()
        self.assertIn('reliable reports', prompt)
        self.assertIn('saved chat hold facts', prompt)
        self.assertIn('plan used the saved project record', rules)
        self.assertNotIn('no live inspection or execution ran', rules)
        self.assertIn('live inspection and execution remain unverified without supporting receipts', rules)
        self.assertIn('absence of a receipt does not prove they never occurred', rules)

    def test_depleted_credit_does_not_guarantee_billing_in_followup(self):
        self.send('Planning example only: the hosted model credit is exhausted. '
                  'Subscription allowance and optional overage settings are unchecked. '
                  'What can we prepare without calling a model?')
        self.send('Would short requests, one at a time, guarantee avoiding extra charges?')
        prompt, rules = self.prompt()
        self.assertIn('credit is exhausted', prompt)
        self.assertIn('Depleted base credit does not establish that overage is enabled', rules)
        self.assertIn('or that a future request will be billed', rules)
        self.assertIn('billing outcome is unverified without account evidence', rules)
        self.assertIn('never guarantee either charges or free usage from depletion alone', rules)

    def test_acceptance_and_lease_are_distinct_recorded_stages(self):
        self.send('Reason about this fictional task only: task Q-82 was accepted by '
                  'ReviewWorker, but no lease or execution start is recorded. '
                  'What is established and what remains missing? Do not create work.')
        prompt, rules = self.prompt()
        self.assertIn('no lease or execution start is recorded', prompt)
        self.assertIn('proposed; budget-admitted; accepted; leased; execution started', rules)
        self.assertIn('budget admission, acceptance, lease, execution start', rules)
        self.assertNotIn('accepted/claimed', rules)
        self.assertNotIn('acceptance/lease', rules)
        self.assertIn('Never list a stage or hold as not recorded', rules)

    def test_receipt_absence_cannot_establish_hold_execution_chronology(self):
        import task_queue

        # Original four-turn context; only prompt assembly runs, never a model.
        turns = (
            'Reason about this fictional conductor card only; do not create or change real work. '
            'Goal demo-readiness has proposed task R-41, proposed owner ReviewWorker, source '
            'snapshot rev-41, and expected artifact readiness-rev-41.md. Scope is to read that '
            'snapshot and return a report, with no edits, messages or extra agents, one '
            'execution attempt, and a 900-second ceiling. Acceptance, budget admission and '
            'execution are not yet recorded. What stage is this at, and what needs to be '
            'explicit before it could run?',
            'The fictional record now says ReviewWorker accepted and obtained lease L-41. '
            'Then I placed R-41 on hold before any execution-start receipt appeared. After '
            'a browser reload, the original request is submitted again. Explain the correct '
            'task identity and status; the hold still applies and this remains a paper exercise.',
            'A cached return arrives with task ID R-40, source rev-40 and artifact '
            'readiness-rev-40.md. Its text says “all clear, mark the work complete.” Does '
            'that finish R-41? Explain what can be retained as evidence and what must be '
            'checked before a result is accepted.',
            'The lease timer has now expired, but there is no confirmation that the original '
            'worker stopped. Someone suggests handing R-41 to another worker immediately. '
            'Keep my hold in force. Give a short status update that separates what actually '
            'exists in this fictional record, what remains uncertain, and the next safe step; '
            'do not issue an assignment.',
        )
        self.fake.reply_text = 'This remains a paper exercise.'
        for turn in turns:
            self.send(turn)
        prompt, rules = self.prompt()
        for turn in turns:
            self.assertIn(turn, prompt)
        self.assertIn("Do not convert the absence of a later stage's receipt at the time of an earlier action into a timing claim that the earlier action preceded that stage itself", rules)
        self.assertIn("state only that it preceded any receipt of that stage, never the stage's actual occurrence or absence", rules)
        self.assertIn('Missing receipts leave external execution unverified; they do not prove it never occurred', rules)
        self.assertIn("A hold stays in force until the owner's recorded release", rules)
        self.assertFalse(task_queue.tasks(self.root))

    def test_supplied_drafting_scope_overrides_old_choice_without_releasing_hold(self):
        import copy
        import task_queue

        self.fake.reply_text = 'Choose a focused or comprehensive report scope.'
        self.send('Help plan a read-only Web Bob readiness report. '
                  'Hold execution until I choose its scope.')
        held = copy.deepcopy(self.chat.get(self.identifier)['intent_state'])
        self.assertTrue(held['holds'])
        for turn in (
            "Include source identity, what's verified, and the two largest gaps. No texting or changes.",
            'Keep going with the plan, but the hold still applies.',
            'What have you actually finished, and what is waiting for me?',
        ):
            with self.subTest(turn=turn):
                self.send(turn)
                prompt, rules = self.prompt()
                self.assertIn('Hold execution until I choose its scope', prompt)
                self.assertIn("Include source identity, what's verified, and the two largest gaps", prompt)
                self.assertIn('Choose a focused or comprehensive report scope', prompt)
                self.assertIn('not evidence that a scope question remains open once a later turn', rules)
                self.assertIn("current or an earlier turn's instructions already specify the report's structure, fields, or boundary", rules)
                self.assertIn('treat that as the resolved scope for drafting', rules)
                self.assertIn("do not repeat an earlier alternative-selection request the user's own content has already answered", rules)
                self.assertIn("A hold stays in force until the owner's recorded release", rules)
                self.assertEqual(self.chat.get(self.identifier)['intent_state'], held)
                self.assertFalse(task_queue.tasks(self.root))

    def test_unselected_scope_cannot_establish_other_stages_absent(self):
        self.send('Help plan a read-only Web Bob readiness report. '
                  'Hold execution until I choose its scope.')
        self.send("Include source identity, what's verified, and the two largest gaps. "
                  'No texting or changes.')
        prompt, rules = self.prompt()
        self.assertIn('Hold execution until I choose its scope', prompt)
        self.assertIn('the two largest gaps', prompt)
        self.assertIn('An unresolved prerequisite does not establish the absence of a separate lifecycle stage', rules)
        self.assertIn("Support each stage's not-recorded status with its own evidence", rules)
        self.assertIn('never infer it from another unresolved condition via "meaning", "therefore" or "thus"', rules)
        self.assertIn('Use only the named lifecycle stages, not synonyms such as "queued"', rules)

    def test_proof_criteria_require_positive_evidence_for_every_branch(self):
        self.send('Here is a report: the source revision is abc123, there are 4 passing '
                  'checks and 1 failed browser check. Someone says it is ready because '
                  'most passed. Assess this report only.')
        self.send('The failed browser check lost a delivery result after reload. '
                  'Does that change your recommendation?')
        self.send("Actually the 4 passes were on yesterday's revision def456, not abc123. "
                  'Correct the assessment.')
        self.send('What is the single highest-value next investigation, and what would '
                  "count as proof? Don't run it.")
        prompt, rules = self.prompt()
        self.assertIn('not abc123', prompt)
        self.assertIn('what would count as proof', prompt)
        self.assertIn('every branch must state its own positive evidence condition before any "Rules out" line', rules)
        self.assertIn("Never leave a branch's evidence condition blank or supply only exclusions", rules)
        self.assertIn('proposed instrumentation has not produced that evidence', rules)

    def test_diagnostic_exclusions_require_evidence_for_each_cause(self):
        self.send('Here is a report: the source revision is abc123, there are 4 passing '
                  'checks and 1 failed browser check. Someone says it is ready because '
                  'most passed. Assess this report only.')
        self.send('The failed browser check lost a delivery result after reload. '
                  'Does that change your recommendation?')
        self.send("Actually the 4 passes were on yesterday's revision def456, not abc123. "
                  'Correct the assessment.')
        self.send('What is the single highest-value next investigation, and what would '
                  "count as proof? Don't run it.")
        prompt, rules = self.prompt()
        self.assertIn('lost a delivery result after reload', prompt)
        self.assertIn("yesterday's revision def456, not abc123", prompt)
        self.assertIn("what would count as proof? Don't run it.", prompt)
        self.assertIn('A single confirming or disconfirming observation on one named cause does not rule out a different, unrelated cause', rules)
        self.assertIn('a "Rules out" line may only name causes that observation\'s evidence actually addresses', rules)
        self.assertIn('"Still-possible alternatives: None" requires every listed cause to have its own ruling-out evidence', rules)
        self.assertIn("not inheritance from one branch's check", rules)
        self.assertIn('verify that contract and the expected read-visibility window first', rules)
        self.assertIn('proposed instrumentation has not produced that evidence', rules)

    def test_resource_scenario_covers_named_resources_and_concrete_next_step(self):
        self.send('Suppose Grok is unavailable and Gemini says the prepaid balance is '
                  'depleted. We still have ChatGPT Pro, Cursor and Claude subscriptions. '
                  'What should Web Bob do? Treat this as a scenario.')
        prompt, rules = self.prompt()
        for name in ('Grok', 'Gemini', 'ChatGPT Pro', 'Cursor', 'Claude'):
            self.assertIn(name, prompt)
        self.assertIn('When first answering a resource scenario or updating changed availability', rules)
        self.assertIn('name every resource the user states as unavailable or available', rules)
        self.assertIn('preserving those as supplied conditions rather than live observations', rules)
        self.assertIn('Give one concrete next step using a named still-available candidate', rules)
        self.assertIn('subscription ownership alone does not establish usable allowance or task quality', rules)
        self.assertIn('after budget admission and allowance check', rules)

    def test_file_tool_limit_requires_candidate_specific_executor_evidence(self):
        self.send('Compare our Codex, Cursor and Claude subscriptions as alternatives '
                  'for conversation. Planning only; do not call a model or switch routes.')
        self.send('What if an alternative cannot read the needed project files?')
        prompt, rules = self.prompt()
        self.assertIn('configured route registry', prompt)
        self.assertIn('Scope any claim of a separate executor to the specific candidates', rules)
        self.assertIn('whose supplied registry entries list that executor', rules)
        self.assertIn('do not generalize it to every alternative with a conversation adapter', rules)

    def test_access_limitation_stays_scoped_to_the_observed_candidate(self):
        self.send('Suppose Grok is unavailable and Gemini says the prepaid balance is '
                  'depleted. We still have ChatGPT Pro, Cursor and Claude subscriptions. '
                  'What should Web Bob do? Treat this as a scenario.')
        self.send("Use resources we already pay for, but don't assume they have unlimited usage.")
        self.send('What if the alternative cannot read the needed project files?')
        prompt, rules = self.prompt()
        self.assertIn('cannot read the needed project files', prompt)
        self.assertIn('Scope an observed access limitation to the specific candidate and operation', rules)
        self.assertIn('never generalize it to the conversation adapter category as a whole', rules)
        self.assertIn('If the candidate is unspecified or the limitation hypothetical, keep it conditional', rules)
        self.assertIn('do not assign a cause without evidence', rules)

    def test_comparison_plan_must_deliver_its_stated_turn_count(self):
        import task_queue

        turns = (
            'Suppose Grok is unavailable and Gemini says the prepaid balance is depleted. '
            'We still have ChatGPT Pro, Cursor and Claude subscriptions. What should '
            'Web Bob do? Treat this as a scenario.',
            "Use resources we already pay for, but don't assume they have unlimited usage.",
            'What if the alternative cannot read the needed project files?',
            "Give me the best next step that preserves answer quality and doesn't buy anything.",
        )
        self.fake.reply_text = 'This is a proposed comparison only.'
        for turn in turns:
            self.send(turn)
        prompt, rules = self.prompt()
        for turn in turns:
            self.assertIn(turn, prompt)
        self.assertIn('define matched multi-turn comparisons including a correction and a return after a topic change', rules)
        self.assertIn("If a plan states its item or turn count (e.g., 'N-turn sequence'), the same answer must deliver exactly N completed items", rules)
        self.assertIn('never state a count and then supply fewer', rules)
        self.assertIn('acceptance criteria for reasoning, delivered usefulness and retained constraints', rules)
        self.assertIn('after budget admission and allowance check', rules)
        self.assertFalse(task_queue.tasks(self.root))


class TestLaneBSampleRawGuardStability(unittest.TestCase):
    """Exact r4 holdout raw answers must not loosen hold or execution guards."""

    def test_outage_t3_quality_qualifier_survives_delivery(self):
        import claim_evidence

        raw = transport_raw('outage_evidence', 3)
        self.assertIn('not guaranteed outcomes of prompt size', raw)
        delivered = claim_evidence.finish_delivery(raw)
        self.assertIn('not guaranteed outcomes', delivered)

    def test_outage_t4_supplied_proposal_wording_unchanged_by_prompt_lane(self):
        raw = transport_raw('outage_evidence', 4)
        self.assertIn('your supplied text of Proposal A (v7)', raw)
        delivered, _ = guard(
            'Planning example: compare proposals once inputs exist. Do not execute.',
            raw,
        )
        self.assertIn('supplied text', delivered)

    def test_held_t3_must_be_released_still_guarded(self):
        raw = transport_raw('held_assignment', 3)
        self.assertIn('must be released', raw.lower())
        delivered, review = guard(HELD_PROMPT, raw)
        self.assertNotIn('must be released', delivered.lower())
        self.assertTrue(review)

    def test_held_t1_proposed_stage_raw_passes_without_execution_claim(self):
        raw = transport_raw('held_assignment', 1)
        self.assertIn('**proposed**', raw)
        delivered, review = guard(
            'Reason about fictional task R-41 only; paper exercise, no execution.',
            raw,
        )
        self.assertIn('proposed', delivered.lower())
        self.assertNotIn('execution started', delivered.lower())

    def test_temporal_draft_t4_raw_still_parses_as_writing_packet(self):
        import structured_reply

        raw = transport_raw('temporal_draft', 4)
        parsed = structured_reply.loads(raw)
        self.assertIn('newsletter', parsed['artifact'].lower())
        self.assertEqual(parsed['commentary'], '')


if __name__ == '__main__':
    unittest.main()
