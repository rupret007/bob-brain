"""r10fix6: saved/configured/provider/state facts need a receipt, registry, or record."""
import json
import tempfile
import unittest
from pathlib import Path

import claim_evidence
import grounded_state
import resource_decision
from test_delivery_false_positives import HELD_ORIGIN, HELD_PROMPT
from test_reply_authority_records import guard
from test_webbob_replyq_1856 import SessionFixture

HOLD_ID = 'fa9dc270-1111-2222-3333-444455556666'
SAVED_REVISION = (
    'As of revision 2 of the saved project record loaded with this chat, '
    'continuity across conversations is recorded as the first priority. '
    'Inspect the stored evidence next.')
HOLD_SAVED = (
    'Hold request ID ' + HOLD_ID + ' is saved. Inspect the stored evidence next.')
CONFIGURED_ROUTES = (
    'Web Bob’s configured route registry lists conversation-adapter and '
    'scoped-executor routes as configured. Inspect the stored evidence next.')
LAST_GEMINI = "Bob's last reply used Gemini. Inspect the stored evidence next."
DIAGNOSTICS_RELEASE = (
    'Task R-41 remains on hold at the accepted/claimed (lease) stage.\n'
    'Diagnostics require releasing the hold before analysis.\n'
    'Inspect the stored evidence next.')


class GroundedStateFactTests(unittest.TestCase):
    def test_saved_revision_without_receipt_is_unknown(self):
        self.assertTrue(list(grounded_state.unsourced_state_claims(SAVED_REVISION)))
        delivered, findings = claim_evidence.deliver(SAVED_REVISION)
        self.assertTrue(findings)
        self.assertNotIn('revision 2', delivered)
        self.assertNotIn('loaded with this chat', delivered)
        self.assertIn('Inspect the stored evidence next.', delivered)
        self.assertIn(claim_evidence.QUALIFICATIONS['unsourced_state'], delivered)
        backed = grounded_state.conversation_evidence(
            projection={'owner_context': {'revision': 2, 'attribution': 'saved project record'}},
            source='product receipt this turn at revision 2')
        self.assertFalse(list(grounded_state.unsourced_state_claims(
            'The saved project record revision 2 lists the current priority.', backed)))

    def test_hold_request_id_without_receipt_is_unknown(self):
        self.assertTrue(list(grounded_state.unsourced_state_claims(HOLD_SAVED)))
        delivered, findings = claim_evidence.deliver(HOLD_SAVED)
        self.assertTrue(findings)
        self.assertNotIn(HOLD_ID, delivered)
        self.assertIn('Inspect the stored evidence next.', delivered)
        evidence = dict(grounded_state.conversation_evidence(), hold_ids={HOLD_ID})
        self.assertFalse(list(grounded_state.unsourced_state_claims(HOLD_SAVED, evidence)))

    def test_configured_routes_without_registry_are_unknown(self):
        self.assertTrue(list(grounded_state.unsourced_state_claims(CONFIGURED_ROUTES)))
        delivered, findings = claim_evidence.deliver(CONFIGURED_ROUTES)
        self.assertTrue(findings)
        self.assertNotIn('configured route registry', delivered.lower())
        self.assertNotIn('conversation-adapter', delivered)
        self.assertIn('Inspect the stored evidence next.', delivered)
        with tempfile.TemporaryDirectory() as temp:
            projection = resource_decision.project(Path(temp), dict(messages=[dict(
                role='user', id='1', request_id='1',
                content='Can our Codex subscription replace the API route?')]))
            self.assertIn('configured route registry', projection['facts']['route_boundaries'])
            selected = json.dumps(dict(answer=[dict(fact='route_boundaries'),
                                               dict(reasoning='Inspect the stored evidence next.')],
                                       resource=None, steps=[]))
            kept, _ = resource_decision.render(selected, projection)
            self.assertIn('configured route registry', kept.lower())
            self.assertIn('Inspect the stored evidence next.', kept)

    def test_last_reply_provider_without_record_is_unknown(self):
        self.assertTrue(list(grounded_state.unsourced_state_claims(LAST_GEMINI)))
        delivered, findings = claim_evidence.deliver(LAST_GEMINI)
        self.assertTrue(findings)
        self.assertNotIn('used Gemini', delivered)
        self.assertIn('Inspect the stored evidence next.', delivered)
        evidence = grounded_state.conversation_evidence(dict(messages=[
            dict(role='assistant', status='done', provider='gemini', content='Earlier reply.'),
            dict(role='assistant', status='running', content=LAST_GEMINI)]))
        self.assertIn('gemini', evidence['providers'])
        self.assertFalse(list(grounded_state.unsourced_state_claims(LAST_GEMINI, evidence)))

    def test_held_assignment_keeps_hold_without_diagnostics_requiring_release(self):
        from providers import CONVERSATION_QUALITY
        quality = ' '.join(CONVERSATION_QUALITY.split())
        self.assertIn('Diagnostic reasoning, paper-exercise analysis, and this turn\'s answer '
                      'do not require releasing a hold', quality)
        self.assertIn('keep the hold', quality)
        self.assertTrue(grounded_state.diagnostics_require_release(DIAGNOSTICS_RELEASE))
        delivered, review = guard(HELD_PROMPT, DIAGNOSTICS_RELEASE, origin=HELD_ORIGIN)
        self.assertIn('on hold', delivered.lower())
        self.assertNotIn('diagnostics require releasing', delivered.lower())
        self.assertTrue(review)
        self.assertTrue(any(unit.get('reason') == 'diagnostics_require_hold_release'
                            for unit in review.get('units', [])))
        kept, findings = claim_evidence.deliver(DIAGNOSTICS_RELEASE)
        self.assertTrue(findings)
        self.assertIn('on hold', kept.lower())
        self.assertNotIn('diagnostics require releasing', kept.lower())
        self.assertIn(claim_evidence.QUALIFICATIONS['diagnostics_require_release'], kept)


class GroundedStateDeliveryTests(SessionFixture):
    def test_first_turn_cannot_claim_last_reply_provider_without_a_record(self):
        self.fake.reply_text = LAST_GEMINI
        answer = self.send('Explain the next planning check. Do not execute anything.')
        self.assertNotIn('used Gemini', answer['content'])
        self.assertIn('Inspect the stored evidence next.', answer['content'])


if __name__ == '__main__':
    unittest.main()
