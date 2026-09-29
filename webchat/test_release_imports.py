"""A release selects executable ledger code independently of persistent data."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class ReleaseImportsTests(unittest.TestCase):
    def test_app_uses_release_ledger_with_data_root_and_pythonpath_pollution(self):
        code = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            data_ledger = root / "conductor/state/ledger.py"
            data_ledger.parent.mkdir(parents=True)
            data_ledger.write_text("raise RuntimeError('DATA_ROOT_LEDGER_EXECUTED')\n")
            shadow = root / "shadow"
            shadow.mkdir()
            (shadow / "ledger.py").write_text("raise RuntimeError('PYTHONPATH_LEDGER_EXECUTED')\n")
            env = dict(os.environ, BOB_ROOT=str(root),
                       BOB_WEBCHAT_DIR=str(root / "conductor/webchat"),
                       PYTHONDONTWRITEBYTECODE="1",
                       PYTHONPATH=os.pathsep.join(str(path) for path in
                                                 (shadow, code / "state", code / "webchat", code / "services")))
            script = """
import json
from pathlib import Path
import sys
import task_dispatch
# The release path is already present, but an inherited path can precede it.
sys.path.insert(0, sys.argv[1])
import app
import handback
import drill_fixture
assert handback._ledger_module(app.ROOT) is app.state_ledger
app.state_ledger.write_now(app.ROOT, 'Isolated import regression', sha='abc1234')
drill_fixture.assert_prod_unchanged(drill_fixture.prod_fingerprint(app.ROOT), app.ROOT)
import ledger
assert ledger is app.state_ledger
print(json.dumps(dict(ledger=str(Path(ledger.__file__).resolve()), root=str(app.ROOT))))
"""
            result = subprocess.run([sys.executable, "-c", script, str(shadow)],
                                    cwd=root, env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout),
                             dict(ledger=str(code / "state/ledger.py"), root=str(root)))
            self.assertIn("Isolated import regression", (root / "conductor/state/NOW.md").read_text())
            self.assertEqual(data_ledger.read_text(), "raise RuntimeError('DATA_ROOT_LEDGER_EXECUTED')\n")


if __name__ == "__main__":
    unittest.main()
