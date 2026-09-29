"""Execute the real shell launcher with private, inert Python applications."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1] / 'webchat/run.sh'
APP = '''import json, os
from pathlib import Path
root = Path(os.environ['BOB_ROOT'])
(root / 'launch.json').write_text(json.dumps({
    'application': str(Path(__file__).resolve()),
    'code': os.environ['BOB_CODE_ROOT'],
    'data': os.environ['BOB_WEBCHAT_DIR'],
    'dispatch': os.environ.get('BOB_WEBCHAT_DISPATCH'),
    'drills': os.environ['BOB_WEBCHAT_DRILLS'],
    'credentials_loaded': os.environ.get('GEMINI_API_KEY') == 'launcher-fixture-key',
}))
'''


class WebchatLauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='webbob-launcher-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / 'installation with spaces'
        self.core = self.root / 'conductor'
        self.state = self.core / 'state'
        self.state.mkdir(parents=True)
        self.codes = {name: self.root / name for name in ('dispatch code', 'webchat code')}
        self.codes['installed'] = self.core
        for code in self.codes.values():
            (code / 'webchat').mkdir(parents=True)
            (code / 'webchat/app.py').write_text(APP)
        self.runner = self.core / 'webchat/run.sh'
        shutil.copyfile(SOURCE, self.runner)
        (self.core / 'keys.env').write_text('GEMINI_API_KEY=launcher-fixture-key\n')
        self.history = self.core / 'webchat/existing-history.json'
        self.history.write_bytes(b'{"private_fixture":"preserve"}\n')
        self.env = dict(PATH=os.defpath, HOME=str(self.root), BOB_ROOT=str(self.root))

    def pin(self, name, target):
        (self.state / (name + '-code-root')).write_text(str(self.codes[target]) + '\n')

    def launch(self, target, *, dispatch=None, drills='0'):
        result = subprocess.run(['/bin/bash', str(self.runner)], env=self.env,
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads((self.root / 'launch.json').read_text())
        self.assertEqual(receipt['application'], str(self.codes[target] / 'webchat/app.py'))
        self.assertEqual(receipt['code'], str(self.codes[target]))
        self.assertEqual(receipt['data'], str(self.core / 'webchat'))
        self.assertEqual(receipt['dispatch'], dispatch)
        self.assertEqual(receipt['drills'], drills)
        self.assertTrue(receipt['credentials_loaded'])
        self.assertEqual(self.history.read_bytes(), b'{"private_fixture":"preserve"}\n')
        output = result.stdout + result.stderr + (self.root / 'logs/webchat-server.log').read_text()
        self.assertNotIn('launcher-fixture-key', output)

    def test_webchat_pin_wins_when_dispatch_pin_differs(self):
        self.pin('dispatch', 'dispatch code')
        self.pin('webchat', 'webchat code')
        self.launch('webchat code', dispatch='1')

    def test_webchat_pin_without_dispatch_pin(self):
        self.pin('webchat', 'webchat code')
        self.launch('webchat code', dispatch='1')

    def test_dispatch_only_installation_keeps_fallback(self):
        self.pin('dispatch', 'dispatch code')
        self.launch('dispatch code')

    def test_unpinned_installation_keeps_conductor_fallback(self):
        self.launch('installed')

    def test_explicit_drills_are_preserved(self):
        self.pin('webchat', 'webchat code')
        self.env['BOB_WEBCHAT_DRILLS'] = '1'
        self.launch('webchat code', dispatch='1', drills='1')

    def test_webchat_pin_disables_nonexplicit_drills(self):
        self.pin('webchat', 'webchat code')
        self.env['BOB_WEBCHAT_DRILLS'] = 'true'
        self.launch('webchat code', dispatch='1')


if __name__ == '__main__':
    unittest.main()
