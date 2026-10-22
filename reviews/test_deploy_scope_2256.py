"""Bound activation retries and keep cross-project publication off production."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import deploy_texting_2256 as deploy


class ReleaseScopeTests(unittest.TestCase):
    def test_fifth_activation_allowed_sixth_blocked_even_after_rollback(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as temporary:
            root = Path(temporary)
            folder = root / 'conductor/reviews'
            folder.mkdir(parents=True)
            # A review reservation or failed preflight is not an activation.
            (folder / 'WEBBOB-TEXTING-DEPLOYMENT-0927-attempt14.json').write_text(json.dumps(
                dict(release_series='2256', activated=False, attempt=14)))
            for number in range(15, 19):
                (folder / f'WEBBOB-TEXTING-DEPLOYMENT-0927-attempt{number}.json').write_text(json.dumps(
                    dict(release_series='2055' if number == 15 else '2256', activated=True,
                         rolled_back=True, attempt=number, sha='a'*40)))
            self.assertEqual(deploy.activation_budget(root)['next_activation'], 5)
            (folder / 'WEBBOB-TEXTING-DEPLOYMENT-0927-attempt19.json').write_text(json.dumps(
                dict(release_series='2256', activated=True, attempt=19, sha='b'*40)))
            with self.assertRaisesRegex(RuntimeError, 'five 2055/2256 deployment activations'):
                deploy.activation_budget(root)

    def test_missing_private_proof_cannot_silently_skip_cross_project_checks(self):
        with patch.object(deploy, 'latest_sessions', return_value=deploy.frozen_sessions()), \
                patch('isolated_replay_2256.verify_proof', side_effect=FileNotFoundError('required private proof')):
            with self.assertRaises(FileNotFoundError):
                deploy.scoped_sessions(Path('/test-root'), Path('/candidate'))

    def test_original_turns_partition_nine_live_ten_private_without_rewriting(self):
        sources = deploy.frozen_sessions()
        proof = dict(all_pass=True, captured_turns=10, passed_turns=10)
        with patch.object(deploy, 'latest_sessions', return_value=sources), \
                patch('isolated_replay_2256.verify_proof', return_value=proof) as verify:
            live, receipt = deploy.scoped_sessions(Path('/test-root'), Path('/candidate'))
        self.assertEqual(receipt, proof)
        self.assertEqual(len(live), 1)
        self.assertEqual(live[0]['scope'], 'production-webbob')
        self.assertEqual(len(live[0]['exchanges']), 9)
        self.assertFalse(any(turn['expected'].startswith('projects') for turn in live[0]['exchanges']))
        private = verify.call_args.args[2]
        self.assertEqual([row['source_id'] for row in private], [row['source_id'] for row in sources[1:]])
        self.assertEqual(sum(len(row['exchanges']) for row in private), 10)

    def test_incomplete_private_turns_fail_scope_gate(self):
        for proof in (dict(all_pass=False, captured_turns=10, passed_turns=10),
                      dict(all_pass=True, captured_turns=10, passed_turns=9)):
            with self.subTest(proof=proof), \
                    patch.object(deploy, 'latest_sessions', return_value=deploy.frozen_sessions()), \
                    patch('isolated_replay_2256.verify_proof', return_value=proof):
                with self.assertRaisesRegex(RuntimeError, 'all ten turns'):
                    deploy.scoped_sessions(Path('/test-root'), Path('/candidate'))


if __name__ == '__main__':
    unittest.main()
