"""Replay r26 provider_unavailable turn 2 without a model or network call."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

for directory in ('state', 'services', 'reviews', 'release'):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / directory))

import reply_contract
import resource_decision


SAMPLE = json.loads((Path(__file__).parent / 'fixtures' / 'provider_unavailable_r26.json').read_text())


class ResourceProposalFallbackTests(unittest.TestCase):
    def replay(self, raw):
        conversation = dict(id='offline-r26', messages=copy.deepcopy(SAMPLE['messages']))
        for index, message in enumerate(conversation['messages']):
            message.update(id=str(index), request_id=str(index), status='done')
        prompt = conversation['messages'][-1]['content']
        answer = dict(id='reply', role='assistant', provider='gemini', content=raw)
        conversation['messages'].append(answer)
        with tempfile.TemporaryDirectory() as folder, \
                patch('live_status_snapshot._screen_sessions', return_value={}), \
                patch('live_status_snapshot.process_table', return_value={}):
            root = Path(folder)
            answer['_reply_contract'] = reply_contract.derive(conversation, lambda text: text, root)
            self.assertEqual(answer['_reply_contract']['kind'], 'resource_advice')
            projection = answer['_reply_contract']['resource_projection']
            # The invalid proposal must remain rejected, even when its prose survives.
            with self.assertRaisesRegex(ValueError, 'Invalid general advice steps'):
                resource_decision.render(raw, projection)
            delivered, artifact = reply_contract.deliver(
                root, prompt, answer, conversation, observation=None, redact=lambda text: text)
        self.assertIsNone(artifact)
        decision = answer['resource_decision']
        self.assertFalse(decision['model_proposal_accepted'])
        self.assertFalse(decision['execution_started'])
        self.assertIsNone(decision['resource'])
        self.assertEqual(decision['steps'], [])
        return delivered, projection

    def test_exact_r26_answer_and_conversation_preserve_validated_text(self):
        delivered, projection = self.replay(SAMPLE['raw_answer'])
        expected = '\n\n'.join(projection['facts'][block['fact']] if 'fact' in block
                               else block['reasoning']
                               for block in json.loads(SAMPLE['raw_answer'])['answer'])
        self.assertEqual(delivered, expected)

    def test_invalid_steps_do_not_rescue_unsupported_resource_claims(self):
        for claim in ('Codex guarantees zero charges.', 'Codex guarantees equivalent answers.',
                      'Use Gemini for the next reply.',
                      'Continue with the previously prepared evidence snapshot.',
                      'I saved hold ID H-8841 and issued save receipt SR-12.',
                      'I routed this to Codex; Codex is now the active route.'):
            with self.subTest(claim=claim):
                packet = json.loads(SAMPLE['raw_answer'])
                packet['answer'].append(dict(reasoning=claim))
                delivered, projection = self.replay(json.dumps(packet))
                self.assertNotIn(claim, delivered)
                self.assertIn(projection['facts']['subscription_scope'], delivered)
                self.assertIn(packet['answer'][2]['reasoning'], delivered)
