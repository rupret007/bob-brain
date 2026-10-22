"""Browser proof dependency discovery must preserve explicit configuration."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from proof_runtime import playwright_environment


class ProofRuntimeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.code = self.root / 'workspaces/review/webchat'
        self.code.mkdir(parents=True)
        self.shared = self.root / 'conductor/webchat/node_modules/playwright'
        self.shared.mkdir(parents=True)
        self.local = self.code / 'node_modules/playwright'

    def test_shared_runtime_discovered_from_nested_worktree(self):
        result = playwright_environment(self.code, {'PATH': '/fixture/bin'})
        self.assertEqual(result, {'PATH': '/fixture/bin',
                                  'BOB_PLAYWRIGHT_MODULE': str(self.shared)})

    def test_local_runtime_takes_precedence_over_shared_runtime(self):
        self.local.mkdir(parents=True)
        result = playwright_environment(self.code, {})
        self.assertEqual(result['BOB_PLAYWRIGHT_MODULE'], str(self.local))

    def test_explicit_override_wins_and_input_environment_is_preserved(self):
        self.local.mkdir(parents=True)
        alias = self.root / 'playwright-alias'
        alias.symlink_to(self.shared, target_is_directory=True)
        original = {'BOB_PLAYWRIGHT_MODULE': str(alias), 'PATH': '/fixture/bin'}
        result = playwright_environment(self.code, original)
        self.assertEqual(result['BOB_PLAYWRIGHT_MODULE'], str(self.shared))
        self.assertEqual(result['PATH'], original['PATH'])
        self.assertEqual(original['BOB_PLAYWRIGHT_MODULE'], str(alias))
        self.assertIsNot(result, original)

    def test_invalid_override_does_not_fall_back_to_installed_runtime(self):
        ordinary_file = self.root / 'ordinary-file'
        ordinary_file.write_text('not a package')
        for override in ('', str(self.root / 'missing'), str(ordinary_file)):
            with self.subTest(override=override):
                with self.assertRaisesRegex(RuntimeError, 'BOB_PLAYWRIGHT_MODULE'):
                    playwright_environment(self.code, {'BOB_PLAYWRIGHT_MODULE': override})

    def test_missing_runtime_fails_without_using_ambient_override(self):
        with patch.dict(os.environ, {'BOB_PLAYWRIGHT_MODULE': str(self.shared)}, clear=True):
            with patch.object(Path, 'is_dir', return_value=False):
                with self.assertRaisesRegex(RuntimeError, 'Set BOB_PLAYWRIGHT_MODULE'):
                    playwright_environment(self.code, {})

    def test_default_environment_is_copied_without_process_mutation(self):
        with patch.dict(os.environ, {'PATH': '/fixture/bin'}, clear=True):
            result = playwright_environment(self.code)
            self.assertEqual(result['BOB_PLAYWRIGHT_MODULE'], str(self.shared))
            self.assertEqual(dict(os.environ), {'PATH': '/fixture/bin'})


if __name__ == '__main__':
    unittest.main()
