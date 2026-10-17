"""Server-owned outage/unavailable answers keep receipt and lifecycle wording."""
import json
import tempfile
import unittest
import uuid
from pathlib import Path

import resource_decision
from reply_quality import check
from test_delivery_false_positives import OUTAGE_RAW
from test_webbob_replyq_1856 import SessionFixture


UNAVAILABLE_PROMPT = (
    'Suppose Grok is unavailable and Gemini says the prepaid balance is depleted. '
    'We still have ChatGPT Pro, Cursor and Claude subscriptions. What should Web Bob do? '
    'Treat this as a scenario.'
)
NEXT_STEP_PROMPT = (
    "Give me the best next step that preserves answer quality and doesn't buy anything."
)
OUTAGE_PROMPT = (
    'Planning example only: the hosted model credit is exhausted. '
    'Subscription allowance and optional overage settings are unchecked. '
    'What can we prepare without calling a model?'
)
OUTAGE_FOLLOWUP = 'Would short requests, one at a time, guarantee avoiding extra charges?'
REASONING = 'The lifecycle stage remains proposed. No execution-start receipt was recorded.'
PROPOSED_SNAPSHOT = (
    'Prepare a comparison:\n'
    '1. Supply a bounded owner-provided evidence snapshot.\n'
    '2. Define the initial task for the candidate model using a bounded prompt.'
)
FABRICATED = (
    'Continue with the previously prepared evidence snapshot and the save receipt SR-12 '
    'under hold ID H-8841. I routed this to Codex; Codex is now the active route.'
)


class OutageHonestySourceTextTests(SessionFixture):
    def ask(self, text, request=None):
        request = request or str(uuid.uuid4())
        self.chat.submit(self.identifier, text, request)
        info = self.chat.workers.get(self.identifier)
        if info:
            info['thread'].join(3)
            self.assertFalse(info['thread'].is_alive(), 'Reply worker did not finish within the fixture bound')
        answer = next(m for m in self.chat.history(self.identifier)['messages']
                      if m.get('request_id') == request and m.get('role') == 'assistant')
        self.assertNotIn(answer['status'], ('queued', 'running'))
        return request, answer

    def restored(self):
        restored = type(self.chat)(self.folder, self.root, self.fake)
        self.addCleanup(restored.close)
        return restored

    def test_quality_pass_would_rewrite_outage_honesty_vocabulary(self):
        mutated = check(UNAVAILABLE_PROMPT, REASONING)
        self.assertIn('status', mutated)
        self.assertIn('confirmation', mutated)
        self.assertNotIn('lifecycle stage', mutated)
        self.assertNotIn('receipt', mutated)
        outage = check(OUTAGE_FOLLOWUP, OUTAGE_RAW)
        self.assertIn('**proposed** status', outage)
        self.assertNotIn('lifecycle stage', outage)

    def test_provider_unavailable_facts_and_receipt_wording_survive_save_and_restart(self):
        self.fake.reply_text = json.dumps(dict(
            answer=[dict(fact='availability'), dict(reasoning=REASONING)],
            resource=None, steps=[]))
        request, answer = self.ask(UNAVAILABLE_PROMPT)
        self.assertTrue(answer.get('resource_decision'))
        self.assertTrue(answer.get('decision_context_review'))
        self.assertIn('Gemini, Grok are unavailable', answer['content'])
        self.assertIn('lifecycle stage', answer['content'])
        self.assertIn('execution-start receipt', answer['content'])
        self.assertNotIn('execution-start confirmation', answer['content'])
        self.assertNotIn('The status remains proposed', answer['content'])
        self.chat.save(self.chat.get(self.identifier))
        saved = self.chat.get(self.identifier)['messages'][-1]
        self.assertEqual(saved['content'], answer['content'])
        restored = self.restored()
        self.assertEqual(restored.history(self.identifier)['messages'][-1]['content'], answer['content'])
        replay = restored.submit(self.identifier, UNAVAILABLE_PROMPT, request)
        self.assertEqual(replay['messages'][-1]['content'], answer['content'])

    def test_outage_evidence_lifecycle_wording_survives_save_and_restart(self):
        self.fake.reply_text = 'Prepare evidence and inspect allowance before any generation.'
        self.ask(OUTAGE_PROMPT)
        self.fake.reply_text = OUTAGE_RAW
        request, answer = self.ask(OUTAGE_FOLLOWUP)
        self.assertTrue(answer.get('decision_context_review'))
        self.assertIn('**proposed** lifecycle stage', answer['content'])
        self.assertNotIn('**proposed** status', answer['content'])
        self.assertIn('remain unverified', answer['content'])
        self.chat.save(self.chat.get(self.identifier))
        self.assertEqual(self.chat.get(self.identifier)['messages'][-1]['content'], answer['content'])
        restored = self.restored()
        self.assertEqual(restored.history(self.identifier)['messages'][-1]['content'], answer['content'])
        replay = restored.submit(self.identifier, OUTAGE_FOLLOWUP, request)
        self.assertEqual(replay['messages'][-1]['content'], answer['content'])

    def test_proposed_snapshot_is_not_a_completed_receipt_on_unavailable_followup(self):
        self.fake.reply_text = json.dumps(dict(
            answer=[dict(fact='availability'), dict(reasoning=PROPOSED_SNAPSHOT)],
            resource=None, steps=['provide_inputs']))
        self.ask(UNAVAILABLE_PROMPT)
        self.fake.reply_text = json.dumps(dict(
            answer=[dict(fact='availability'), dict(reasoning=FABRICATED)],
            resource=None, steps=['preserve_standard']))
        request, answer = self.ask(NEXT_STEP_PROMPT)
        self.assertTrue(answer.get('resource_decision'))
        content = answer['content']
        self.assertTrue(
            'unavailable' in content or 'previously stated resource facts still apply' in content,
            content)
        self.assertNotIn('previously prepared evidence snapshot', content)
        self.assertNotIn('save receipt SR-12', content)
        self.assertNotIn('hold ID H-8841', content)
        self.assertNotIn('I routed this to Codex', content)
        self.assertNotIn('Codex is now the active route', content)
        self.assertTrue(answer['resource_decision'].get('partial'))
        self.assertFalse(answer['resource_decision']['execution_started'])
        self.chat.save(self.chat.get(self.identifier))
        self.assertEqual(self.chat.get(self.identifier)['messages'][-1]['content'], content)
        restored = self.restored()
        self.assertEqual(restored.history(self.identifier)['messages'][-1]['content'], content)
        replay = restored.submit(self.identifier, NEXT_STEP_PROMPT, request)
        self.assertEqual(replay['messages'][-1]['content'], content)
        self.assertNotIn('previously prepared evidence snapshot', replay['messages'][-1]['content'])


class UnavailableReceiptHonestyTests(unittest.TestCase):
    def projection(self):
        with tempfile.TemporaryDirectory() as temp:
            return resource_decision.project(Path(temp), dict(messages=[dict(
                role='user', id='1', request_id='1', content=UNAVAILABLE_PROMPT)]))

    def test_safe_reasoning_rejects_fabricated_snapshot_receipts_and_keeps_proposals(self):
        self.assertFalse(resource_decision.safe_reasoning(FABRICATED))
        self.assertFalse(resource_decision.safe_reasoning(
            'Use the previously prepared evidence snapshot for the comparison.'))
        self.assertFalse(resource_decision.safe_reasoning(
            'The evidence snapshot has been prepared and saved.'))
        self.assertFalse(resource_decision.safe_reasoning(
            'I saved hold ID H-8841 and issued save receipt SR-12.'))
        self.assertFalse(resource_decision.safe_reasoning(
            'I routed this to Codex; Codex is now the active route.'))
        self.assertTrue(resource_decision.safe_reasoning(PROPOSED_SNAPSHOT))
        self.assertTrue(resource_decision.safe_reasoning(REASONING))
        self.assertTrue(resource_decision.safe_reasoning(
            resource_decision.SAME_STEPS))
        self.assertTrue(resource_decision.safe_reasoning(
            'Supply a bounded owner-provided evidence snapshot.'))
        self.assertTrue(resource_decision.safe_reasoning(
            'No save receipt was recorded and no hold ID was issued.'))

    def test_unavailable_render_keeps_server_facts_and_drops_fabricated_receipts(self):
        projection = self.projection()
        self.assertTrue(projection['unavailable'])
        packet = json.dumps(dict(
            answer=[dict(fact='availability'), dict(reasoning=FABRICATED)],
            resource=None, steps=['preserve_standard']))
        delivered, decision = resource_decision.render(packet, projection)
        self.assertIn(projection['facts']['availability'], delivered)
        self.assertIn('unavailable', delivered)
        self.assertNotIn('previously prepared evidence snapshot', delivered)
        self.assertNotIn('save receipt SR-12', delivered)
        self.assertNotIn('hold ID H-8841', delivered)
        self.assertNotIn('I routed this to Codex', delivered)
        self.assertTrue(decision['partial'])
        self.assertFalse(decision['execution_started'])
        proposal = json.dumps(dict(
            answer=[dict(fact='availability'), dict(reasoning=PROPOSED_SNAPSHOT)],
            resource=None, steps=['provide_inputs']))
        kept, receipt = resource_decision.render(proposal, projection)
        self.assertIn(PROPOSED_SNAPSHOT, kept)
        self.assertFalse(receipt.get('partial'))


if __name__ == '__main__':
    import unittest
    unittest.main()
