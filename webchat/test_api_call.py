"""API child process must honor separate deployed code and live data roots."""
import os
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class APIRootTests(unittest.TestCase):
    def test_child_preserves_structured_context_and_refuses_old_helper(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'webchat').mkdir()
            (root / 'services').mkdir()
            for name in ('api_call.py', 'billing.py'):
                shutil.copyfile(Path(__file__).with_name(name), root / 'webchat' / name)
            (root / 'services/budget.py').write_text('CAP_USD = 48.0\ndef check(lane): pass\n')
            (root / 'services/lanes.py').write_text('from contextlib import nullcontext\ndef slot(lane): return nullcontext()\n')
            helper = root / 'services/api.py'
            helper.write_text(
                'def model_call(lane, prompt, purpose, vision=None, system=None, messages=None, thinking_budget=None):\n'
                '    assert system == "trusted policy"\n'
                '    assert messages == [{"role":"user", "content":"user asks"}]\n'
                '    assert prompt == "reference data"\n'
                '    assert thinking_budget == 1024\n'
                '    return "The structured helper preserved context."\n')
            payload = json.dumps(dict(prompt='reference data', system='trusted policy', thinking_budget=1024,
                                      messages=[dict(role='user', content='user asks')]))
            command = [sys.executable, str(root / 'webchat/api_call.py'), 'gemini']
            env = dict(os.environ, BOB_ROOT=str(root))
            result = subprocess.run(command, env=env, input=payload, text=True, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('preserved context', result.stdout)
            helper.write_text('def model_call(lane, prompt, purpose):\n    raise AssertionError("must not be called")\n')
            result = subprocess.run(command, env=env, input=payload, text=True, capture_output=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('does not support structured chat input', result.stderr)
            self.assertNotIn('must not be called', result.stderr)

    def test_pinned_checkout_imports_own_services_and_loads_live_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            code, data = base / "workspaces/tested-code", base / "live-data"
            (code / "webchat").mkdir(parents=True)
            (code / "services").mkdir()
            (data / "conductor").mkdir(parents=True)
            for name in ("api_call.py", "billing.py"):
                shutil.copyfile(Path(__file__).with_name(name), code / "webchat" / name)
            (code / "services/budget.py").write_text("CAP_USD = 59.0\ndef check(lane): pass\n")
            (code / "services/lanes.py").write_text("from contextlib import nullcontext\ndef slot(lane): return nullcontext()\n")
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
                                            cwd=base, env=env, input=json.dumps({"prompt": "fixture prompt", "vision": []}), text=True,
                                            capture_output=True, timeout=10)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout.strip(), "Pinned API helper worked.")

    def test_vision_child_transport_round_trip_and_invalid_envelope(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'webchat').mkdir()
            (root / 'services').mkdir()
            for name in ('api_call.py', 'billing.py'):
                shutil.copyfile(Path(__file__).with_name(name), root / 'webchat' / name)
            (root / 'services/budget.py').write_text('CAP_USD = 59.0\ndef check(lane): pass\n')
            (root / 'services/lanes.py').write_text('from contextlib import nullcontext\ndef slot(lane): return nullcontext()\n')
            (root / 'services/api.py').write_text(
                'def model_call(lane, prompt, purpose, vision=None):\n'
                '    assert "---BOB_VISION_JSON---" in prompt\n'
                '    assert vision == [{"mime": "image/jpeg", "data_base64": "YQ=="}]\n'
                '    return "A complete offline vision transport reply."\n')
            command = [sys.executable, str(root / 'webchat/api_call.py'), 'gemini']
            env = dict(os.environ, BOB_ROOT=str(root))
            good = json.dumps({'prompt': 'Before\n---BOB_VISION_JSON---\nAfter',
                               'vision': [{'mime': 'image/jpeg', 'data_base64': 'YQ=='}]})
            result = subprocess.run(command, env=env, input=good, text=True, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('complete offline vision', result.stdout)
            for bad in ('[]', '{"prompt":null}', 'raw text'):
                result = subprocess.run(command, env=env, input=bad, text=True, capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stderr.strip(), 'invalid transport payload')


if __name__ == "__main__":
    unittest.main()
