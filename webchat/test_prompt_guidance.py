"""Lane B prompt rules (items 6 and 8): structure and sample-raw guard stability."""
import json
import unittest
from pathlib import Path

from test_delivery_false_positives import HELD_PROMPT
from test_reply_authority_records import guard

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
        self.assertIn('in-chat proposal only, not a persisted task or queue entry', quality)
        self.assertIn('never call proposed a recorded lifecycle stage', quality)
        self.assertIn('Missing receipts leave external execution unverified', quality)
        self.assertIn('product receipt this turn or saved snapshot, as applicable', quality)
        self.assertIn('hold request ID only from supplied saved chat hold facts', quality)
        self.assertIn('configured route registry (not live-verified)', quality)

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
        self.assertIn('budget admission, acceptance/lease, execution start', quality)
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
