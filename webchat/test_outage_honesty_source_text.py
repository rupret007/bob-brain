"""Server-owned outage/unavailable answers keep receipt and lifecycle wording."""
import json
import uuid

from reply_quality import check
from test_delivery_false_positives import OUTAGE_RAW
from test_webbob_replyq_1856 import SessionFixture


UNAVAILABLE_PROMPT = (
    'Suppose Grok is unavailable and Gemini says the prepaid balance is depleted. '
    'We still have ChatGPT Pro, Cursor and Claude subscriptions. What should Web Bob do? '
    'Treat this as a scenario.'
)
OUTAGE_PROMPT = (
    'Planning example only: the hosted model credit is exhausted. '
    'Subscription allowance and optional overage settings are unchecked. '
    'What can we prepare without calling a model?'
)
OUTAGE_FOLLOWUP = 'Would short requests, one at a time, guarantee avoiding extra charges?'
REASONING = 'The lifecycle stage remains proposed. No execution-start receipt was recorded.'


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


if __name__ == '__main__':
    import unittest
    unittest.main()
