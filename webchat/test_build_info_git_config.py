"""User-wide Git settings must not override the running code's identity."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import build_info


class GitConfigurationIsolation(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.repo = self.root / 'repo'
        module = self.repo / 'webchat/build_info.py'
        module.parent.mkdir(parents=True)
        module.write_text('# Tracked fixture identity module.\n')
        self.git('init', '-b', 'main')
        self.git('add', '.')
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                 'commit', '-m', 'Fixture')
        self.sha = self.git('rev-parse', 'HEAD')
        self.xdg = self.root / 'xdg'
        self.config = self.xdg / 'git/config'
        self.config.parent.mkdir(parents=True)

    def git(self, *args):
        # Fixture setup neither reads nor changes user Git settings or hooks.
        env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
        env.update(GIT_CONFIG_GLOBAL='/dev/null', GIT_CONFIG_NOSYSTEM='1',
                   GIT_CONFIG_COUNT='1', GIT_CONFIG_KEY_0='core.hooksPath',
                   GIT_CONFIG_VALUE_0='/dev/null')
        return subprocess.check_output(['git', '-C', str(self.repo), *args], env=env,
                                       text=True, stderr=subprocess.PIPE).strip()

    def test_global_worktree_cannot_choose_another_code_root(self):
        other = self.root / 'other checkout'
        other.mkdir()
        self.config.write_text('[core]\n\tworktree = ' + json.dumps(str(other)) + '\n')
        with patch.dict(os.environ, {'XDG_CONFIG_HOME': str(self.xdg)}):
            self.assertEqual(build_info.git_checkout_root(self.repo), self.repo)
            self.assertEqual(build_info.load_build(self.repo)['sha'], self.sha)

    def test_malformed_global_config_cannot_hide_a_valid_release(self):
        self.config.write_text('[malformed configuration\n')
        with patch.dict(os.environ, {'XDG_CONFIG_HOME': str(self.xdg)}):
            self.assertEqual(build_info.git_checkout_root(self.repo), self.repo)
            self.assertEqual(build_info.load_build(self.repo)['sha'], self.sha)


if __name__ == '__main__':
    unittest.main()
