"""Route and constraint restatements stay qualified without boilerplate repeats."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'state'))

import resource_decision


ROUTE_REASONING = (
    'A limitation in reading local files belongs specifically to the conversation adapter, '
    'which relies on supplied context, rather than the separate scoped executors configured '
    'for local coding assignments.'
)


class ResourceRestatementTests(unittest.TestCase):
    def test_route_note_appears_once_and_same_as_above_is_omitted(self):
        with tempfile.TemporaryDirectory() as temp:
            conversation = dict(messages=[dict(
                role='user', id='1', request_id='1',
                content='Suppose Gemini is depleted and Grok is unavailable. What can our subscriptions do?')])
            projection = resource_decision.project(Path(temp), conversation)
            packet = json.dumps(dict(
                answer=[dict(reasoning=ROUTE_REASONING), dict(fact='availability')],
                resource=None, steps=[]))
            first, _ = resource_decision.render(packet, projection)
            self.assertEqual(first.count(resource_decision.ROUTE_NOTE), 1)
            self.assertNotIn('Same constraints as above', first)
            self.assertNotIn('Same missing-input limit as above', first)
            second, _ = resource_decision.render(packet, projection, prior=first)
            combined = first + '\n\n' + second
            self.assertEqual(combined.count(resource_decision.ROUTE_NOTE), 1)
            self.assertNotIn('Same constraints as above', second)
            self.assertNotIn('Same missing-input limit as above', second)
            third, _ = resource_decision.render(packet, projection, prior=combined)
            self.assertNotIn(resource_decision.ROUTE_NOTE, third)
            self.assertNotIn('Same constraints as above', third)
            self.assertNotIn('Same … as above', third)
            self.assertNotIn('Same constraints as above', first + second + third)

    def test_billing_fact_is_scoped_as_documented_not_account_checked(self):
        fact = resource_decision.facts({'resources': [], 'observed_at': 0})['openai_api_billing']
        self.assertIn('ChatGPT Pro does not pay for OpenAI API requests', fact)
        self.assertIn('as documented; not checked for this account', fact)

    def test_capability_claim_without_prior_note_is_still_qualified(self):
        text = resource_decision.qualify_route_restatement(ROUTE_REASONING)
        self.assertIn(resource_decision.ROUTE_NOTE, text)
        again = resource_decision.qualify_route_restatement(ROUTE_REASONING, prior=text)
        self.assertEqual(again, ROUTE_REASONING)


if __name__ == '__main__':
    unittest.main()
