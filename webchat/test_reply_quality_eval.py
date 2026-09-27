#!/usr/bin/env python3
import json
import unittest
from pathlib import Path

from reply_builder import build_reply
from reply_quality_eval import load_cases, run_offline
from reply_rubric import evaluate_rubrics

HERE = Path(__file__).resolve().parent
CODE_ROOT = HERE.parent


class ReplyQualityEvalTests(unittest.TestCase):
    def test_case_file_has_thirty_plus_mined_prompts(self):
        payload = load_cases()
        self.assertGreaterEqual(len(payload["cases"]), 30)
        categories = {row["category"] for row in payload["cases"]}
        for name in ("status", "llm", "start", "criticism", "version", "hold"):
            self.assertIn(name, categories)

    def test_offline_runner_returns_every_case(self):
        payload = load_cases()
        rows = run_offline(CODE_ROOT, payload["cases"][:3])
        self.assertEqual(len(rows), 3)
        self.assertTrue(all("rubrics" in row for row in rows))

    def test_status_reply_avoids_unknown_task_wording_with_fixture(self):
        outcome = build_reply(
            "What's working on what?",
            code_root=CODE_ROOT,
            fixture="busy_workers",
        )
        rows = evaluate_rubrics(
            outcome.content,
            CODE_ROOT / ".reply-eval-runtime",
            ["no_unknown_task", "answer_first"],
            outcome.as_meta(),
        )
        self.assertTrue(all(row["ok"] for row in rows), rows)

    def test_version_question_returns_short_sha(self):
        outcome = build_reply("what version/build are you", code_root=CODE_ROOT)
        self.assertRegex(outcome.content.strip(), r"^[0-9a-f]{7}$", outcome.content)


if __name__ == "__main__":
    unittest.main()
