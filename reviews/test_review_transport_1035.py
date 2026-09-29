"""Safety checks for the release decision parser; no provider calls."""
import unittest
from review_transport_1035 import parse_verdict


def response(content, finish="stop", reasoning=""):
    return dict(base_resp=dict(status_code=0), choices=[dict(finish_reason=finish,
                message=dict(content=content, reasoning_content=reasoning))])


class VerdictContractTests(unittest.TestCase):
    def test_short_pass_and_fail_are_valid(self):
        for verdict in ("PASS", "FAIL"):
            self.assertEqual(parse_verdict("minimax", response("VERDICT: " + verdict)), "VERDICT: " + verdict)
            data = dict(candidates=[dict(finishReason="STOP", content=dict(parts=[dict(text="VERDICT: " + verdict)]))])
            self.assertEqual(parse_verdict("gemini", data), "VERDICT: " + verdict)

    def test_reasoning_cannot_supply_verdict(self):
        for content in ("", "<think>VERDICT: PASS</think>", "<think>VERDICT: PASS"):
            with self.assertRaises(RuntimeError):
                parse_verdict("minimax", response(content, reasoning="VERDICT: PASS"))

    def test_truncation_provider_error_and_conflicting_verdicts_rejected(self):
        for data in (response("VERDICT: PASS", finish="length"),
                     response("VERDICT: PASS\nVERDICT: FAIL"),
                     response("I think VERDICT: PASS"),
                     dict(base_resp=dict(status_code=1008), choices=response("VERDICT: PASS")["choices"])):
            with self.assertRaises(RuntimeError):
                parse_verdict("minimax", data)

    def test_gemini_thought_only_and_incomplete_rejected(self):
        for finish, thought in (("STOP", True), ("MAX_TOKENS", False)):
            data = dict(candidates=[dict(finishReason=finish, content=dict(parts=[dict(text="VERDICT: PASS", thought=thought)]))])
            with self.assertRaises(RuntimeError):
                parse_verdict("gemini", data)


if __name__ == "__main__":
    unittest.main()
