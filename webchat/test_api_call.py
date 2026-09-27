"""API child process must honor separate deployed code and live data roots."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class APIRootTests(unittest.TestCase):
    def test_pinned_checkout_imports_own_services_and_loads_live_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            code, data = base / "workspaces/tested-code", base / "live-data"
            (code / "webchat").mkdir(parents=True)
            (code / "services").mkdir()
            (data / "conductor").mkdir(parents=True)
            for name in ("api_call.py", "billing.py"):
                shutil.copyfile(Path(__file__).with_name(name), code / "webchat" / name)
            (code / "services/budget.py").write_text("CAP_USD = 59.0\n")
            (code / "services/api.py").write_text(
                "import os\n"
                "def model_call(lane, prompt, purpose):\n"
                "    assert os.environ[lane.upper() + '_API_KEY'] == 'offline-fixture-key'\n"
                "    assert prompt == 'fixture prompt' and purpose == 'webchat'\n"
                "    return '<bob-webchat-reply>Pinned API helper worked.</bob-webchat-reply>'\n")
            (data / "conductor/keys.env").write_text(
                "MINIMAX_API_KEY=offline-fixture-key\nGEMINI_API_KEY=offline-fixture-key\n")
            env = {key: value for key, value in os.environ.items() if not key.endswith(("_API_KEY", "_TOKEN"))}
            env["BOB_ROOT"] = str(data)
            for lane in ("minimax", "gemini"):
                with self.subTest(lane=lane):
                    result = subprocess.run([sys.executable, str(code / "webchat/api_call.py"), lane],
                                            cwd=base, env=env, input="fixture prompt", text=True,
                                            capture_output=True, timeout=10)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout.strip(), "Pinned API helper worked.")


if __name__ == "__main__":
    unittest.main()
