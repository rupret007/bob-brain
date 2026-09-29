"""Reasoning transports have bounded response time without bypassing metering."""
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import api


class ModelResponseTimeoutTests(unittest.TestCase):
    def test_reasoning_models_have_a_longer_response_window(self):
        for model, seconds in (("MiniMax-M2.7", 180), ("gemini-2.5-pro", 180),
                               ("gemini-2.5-flash", 60), (None, 60)):
            def transport(argv, **kwargs):
                self.assertEqual(argv[argv.index("-m") + 1], str(seconds))
                self.assertEqual(argv[argv.index("--connect-timeout") + 1], "10")
                self.assertEqual(kwargs["timeout"], seconds + 5)
                Path(argv[argv.index("-o") + 1]).write_text('{"ok": true}')
                return SimpleNamespace(returncode=0, stdout="200")
            with self.subTest(model=model), patch.object(api, "run", side_effect=transport):
                self.assertEqual(api.http_json("https://example.invalid", model_id=model), {"ok": True})

    def test_minimax_timeout_preserves_three_metered_attempts_and_never_accepts(self):
        reservations = [{"call_id": str(index)} for index in range(3)]
        validate = Mock()
        with patch.object(api.budget, "reserve", side_effect=reservations) as reserve, \
                patch.object(api.budget, "settle") as settle, \
                patch.object(api, "run", return_value=SimpleNamespace(returncode=28, stdout="000")) as transport, \
                patch.object(api.time, "sleep") as sleep, patch.object(api, "log"):
            with self.assertRaisesRegex(RuntimeError, "HTTP 0 curl_rc=28"):
                api.http_json("https://example.invalid", "POST", {"max_tokens": 8192},
                              lane="minimax", prompt="task", max_tokens=8192,
                              model_id="MiniMax-M2.7", validate=validate)
        self.assertEqual(reserve.call_count, 3)
        self.assertEqual(transport.call_count, 3)
        for call in reserve.call_args_list:
            self.assertEqual(call.args, ("minimax", "task", 8192, "api"))
            self.assertEqual(call.kwargs["model_id"], "MiniMax-M2.7")
        for call in transport.call_args_list:
            self.assertEqual(call.args[0][call.args[0].index("-m") + 1], "180")
            self.assertEqual(call.kwargs["timeout"], 185)
        self.assertEqual([call.args for call in sleep.call_args_list], [(2,), (4,)])
        settle.assert_not_called()
        validate.assert_not_called()

    def test_success_settles_actual_usage_and_still_validates_response(self):
        receipt = {"call_id": "metered"}
        response = {"usage": {"prompt_tokens": 25, "completion_tokens": 30}, "answer": "drafts"}
        def transport(argv, **kwargs):
            Path(argv[argv.index("-o") + 1]).write_text(json.dumps(response))
            return SimpleNamespace(returncode=0, stdout="200")
        validate = Mock(side_effect=RuntimeError("rejected incomplete response"))
        with patch.object(api.budget, "reserve", return_value=receipt), \
                patch.object(api.budget, "settle") as settle, \
                patch.object(api, "run", side_effect=transport), patch.object(api, "log"):
            with self.assertRaisesRegex(RuntimeError, "rejected incomplete response"):
                api.http_json("https://example.invalid", lane="minimax", prompt="task", max_tokens=8192,
                              model_id="MiniMax-M2.7", attempts=1, validate=validate)
        settle.assert_called_once_with("minimax", receipt, response)
        validate.assert_called_once_with(response)


if __name__ == "__main__":
    unittest.main()
