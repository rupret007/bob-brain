"""Keep the actual final council failure binding after removing vendor gates."""
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import Mock
from result_acceptance import ResultRejected, accept
from api_worker import render_report


class SoloRegressionTests(unittest.TestCase):
    def test_ebfa417_probe_still_rejected_before_any_model_review(self):
        fixture = json.loads(Path(__file__).with_name('fixtures').joinpath('texting_probe_failure_2256.json').read_text())
        for key in ('answer', 'prompt'):
            self.assertEqual(hashlib.sha256(fixture[key].encode()).hexdigest(), fixture[key + '_sha256'])
        reviewer = Mock(return_value='{"accepted":true,"reason":"looks fine"}')
        with self.assertRaisesRegex(ResultRejected, 'Regression draft contradicts literal guard outcome'):
            rendered = render_report(fixture['prompt'], fixture['answer'], kind=fixture['kind'])
            accept(fixture['prompt'], rendered, reviewer, kind=fixture['kind'])
        reviewer.assert_not_called()


if __name__ == '__main__':
    unittest.main()
