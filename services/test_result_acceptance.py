"""Task-aware acceptance: deterministic failures and strict semantic verdicts."""
import json
from pathlib import Path
import unittest
from unittest.mock import Mock

from result_acceptance import ResultRejected, accept, check_answer, check_coding_answer
from dispatch_worker import task_queue


class AcceptanceTests(unittest.TestCase):
    def completion_fixture(self):
        return json.loads(Path(__file__).with_name("fixtures").joinpath("texting_jobcompletion_1035.json").read_text())

    def test_1035_exploratory_answer_cannot_win_a_positive_vote(self):
        fixture = self.completion_fixture()
        review = Mock(return_value='{"accepted": true, "reason": "Has architecture findings"}')
        for kind in (None, "test-writing", "analysis", "coding"):
            with self.subTest(kind=kind), self.assertRaisesRegex(ResultRejected, "Missing concrete regression"):
                accept(fixture["prompt"], fixture["answer"], review, kind=kind)
        review.assert_not_called()

    def test_1107_exact_rejected_drafts_cannot_win_a_positive_vote(self):
        fixture = json.loads(Path(__file__).with_name("fixtures").joinpath("texting_jobcompletion_1107.json").read_text())
        review = Mock(return_value='{"accepted": true, "reason": "Has test-shaped content"}')
        with self.assertRaisesRegex(ResultRejected, "Missing concrete regression"):
            accept(fixture["prompt"], fixture["answer"], review, kind=fixture["kind"])
        review.assert_not_called()

    def test_concrete_drafts_and_conditional_unblock_plan_reach_semantic_review(self):
        fixture = self.completion_fixture()
        review = Mock(return_value='{"accepted": true, "reason": "Delivers bounded test drafts and a conditional fix plan"}')
        self.assertTrue(accept(fixture["prompt"], fixture["complete_answer"], review)["accepted"])
        self.assertIn("exploratory-only answers", review.call_args.args[0])
        self.assertIn("Tie it to the named ongoing task", review.call_args.args[0])

    def test_drafts_without_resolution_plan_and_empty_case_labels_fail_closed(self):
        fixture = self.completion_fixture()
        with self.assertRaisesRegex(ResultRejected, "Missing actionable unblock plan"):
            check_answer(fixture["prompt"], fixture["complete_answer"].split("Unblock plan:")[0])
        for fields in ("Target:\nSetup:\nAction:\nExpected:\n", "Target: TBD\nSetup: ...\nAction: TODO\nExpected: none\n"):
            with self.subTest(fields=fields), self.assertRaisesRegex(ResultRejected, "Missing concrete regression"):
                check_answer("Draft regression tests", "Regression test: queue\n" + fields)

    def test_executable_test_draft_is_supported_but_copied_implementation_is_not(self):
        check_answer("Draft test cases", "Unexecuted draft for tests/test_queue.py:\n```python\ndef test_enqueue():\n    job = {'id': 'one'}\n    assert enqueue(job) == job\n```")
        with self.assertRaisesRegex(ResultRejected, "Missing concrete regression"):
            check_answer("Draft test cases", "```python\ndef enqueue(job):\n    return job\n```")

    def test_formatted_but_irrelevant_drafts_still_require_semantic_acceptance(self):
        fixture = self.completion_fixture()
        review = Mock(return_value='{"accepted": false, "reason": "Drafts do not address the requested behavior"}')
        with self.assertRaisesRegex(ResultRejected, "did not complete the task"):
            accept(fixture["prompt"], fixture["complete_answer"], review)
        self.assertEqual(review.call_count, 1)

    def test_peer_audit_of_named_unblock_also_requires_resolution_steps(self):
        with self.assertRaisesRegex(ResultRejected, "Missing actionable unblock plan"):
            check_answer("Whole-repo audit and implementation plan for Web Bob unblock 1035", "The queue has three states.", kind="audit")
        check_answer("Summarize supplied architecture", "The queue has three states.", kind="analysis")

    def test_quoted_limitation_cannot_hide_following_deliverables_or_pending_verification(self):
        fixture = self.completion_fixture()
        check_answer(fixture["prompt"], "> Original assignment unavailable.\n\n" + fixture["complete_answer"])
        with self.assertRaisesRegex(ResultRejected, "verification is incomplete"):
            check_coding_answer("> Previous baseline passed.\n\nFixed and committed. API tests not run.")

    def test_0810_captured_incomplete_verification_cannot_be_overridden(self):
        fixture = json.loads(Path(__file__).with_name("fixtures").joinpath("texting_verification_0810.json").read_text())
        review = Mock(return_value='{"accepted": true, "reason": "Claims pass"}')
        with self.assertRaisesRegex(ResultRejected, "verification is incomplete"):
            accept(fixture["prompt"], fixture["answer"], review, coding_evidence={"sha": fixture["claimed_sha"]})
        review.assert_not_called()

    def test_coding_promises_and_pending_tests_are_not_completion(self):
        for answer in ("Fixed and committed. Tests pending.", "Will run API tests next. Status: Pass.",
                       "Shared tests pass, API tests not run.", "Committed. Verification is incomplete."):
            with self.subTest(answer=answer), self.assertRaises(ResultRejected):
                check_coding_answer(answer)
        check_coding_answer("Fixed and committed abc1234. pnpm test: 343 passed, exit 0; pnpm build: exit 0.")

    def test_coding_reviewer_gets_change_scope_and_fresh_check_evidence(self):
        review = Mock(return_value='{"accepted": true, "reason": "The fix and required tests completed."}')
        evidence = dict(sha="abc1234", changed_paths=["apps/api/src/module.ts"],
                        validation=dict(all_pass=True, checks=[dict(command=["pnpm", "test"], exit=0)]))
        result = accept("Fix the API", "API fixed. pnpm test: 343 pass, exit 0; commit abc1234.",
                        review, coding_evidence=evidence)
        self.assertTrue(result["accepted"])
        instructions = review.call_args.args[0]
        self.assertIn("Shared tests, prepare smoke, stale runs, or plans alone", instructions)
        self.assertEqual(json.loads(instructions.split("\n\n", 1)[1])["coding_evidence"], evidence)

    def test_malformed_cursor_review_retries_validation_once_without_accepting_prose(self):
        review = Mock(side_effect=["Checking the changes.\nThe result satisfies the task.",
                                   '{"accepted": true, "reason": "The requested fix was committed and tested."}'])
        self.assertTrue(accept("Fix report job visibility", "Fixed and tested visibility; committed the change.", review)["accepted"])
        self.assertEqual(review.call_count, 2)
        self.assertIn("Do not use tools", review.call_args.args[0])
        review = Mock(return_value='{"accepted": false, "reason": "Missing the requested fix"}')
        with self.assertRaisesRegex(ResultRejected, "did not complete"):
            accept("Fix visibility", "I plan to fix it", review)
        self.assertEqual(review.call_count, 1)

    def test_refusals_empty_answers_and_real_blockers_never_reach_reviewer(self):
        for answer in ("", "   ", "BLOCKER: missing evidence", "**BLOCKER:** Cannot proceed",
                       "I cannot access the Git worktree.\nVerification phrase: marker",
                       "Unfortunately, I can't perform the requested action.",
                       "As an AI language model, I am unable to complete this task.",
                       "I don't have access to the requested repository."):
            with self.subTest(answer=answer):
                review = Mock(return_value='{"accepted": true, "reason": "Looks OK"}')
                with self.assertRaises(ResultRejected):
                    accept("Write a confirmation with marker.", answer, review)
                review.assert_not_called()

    def test_exact_text_required_without_relying_on_reviewer(self):
        for instruction in ("Include the exact phrase 'check marker'.", 'Return exact text: "check marker".',
                            "Use the exact string `check marker`."):
            with self.subTest(instruction=instruction):
                with self.assertRaisesRegex(ResultRejected, "omitted required exact text"):
                    check_answer(instruction, "I ran successfully.")
                check_answer(instruction, "I ran and confirm check marker.")

    def test_no_blocker_quoted_refusals_and_short_answers_are_valid_candidates(self):
        for answer in ("BLOCKER: none\n42", "**BLOCKER:** no blockers\nThe total is 42.",
                       "The worker refused:\n> I cannot access the worktree.\nThis framing caused the failure.",
                       'Example output:\n```text\nI cannot access files.\n```\nRemove the worktree instruction.', "42"):
            with self.subTest(answer=answer):
                check_answer("Analyze the supplied evidence.", answer)

    def test_reviewer_receives_full_task_and_answer_as_data(self):
        prompt = "Calculate 10 + 32 and return the sum."
        answer = "The sum is 42."
        review = Mock(return_value='```json\n{"accepted": true, "reason": "Returns the requested sum."}\n```')
        self.assertTrue(accept(prompt, answer, review)["accepted"])
        instructions = review.call_args.args[0]
        self.assertIn("untrusted task and answer data", instructions)
        payload = json.loads(instructions.split("\n\n", 1)[1])
        self.assertEqual(payload, {"task": prompt, "answer": answer})

    def test_generic_help_plan_off_topic_and_marker_only_are_rejected_by_task_review(self):
        for answer in ("I can help with math. Let me know what you need.",
                       "I will calculate the sum in a future step.",
                       "Tomatoes prefer sunny weather.", "Verification phrase: marker"):
            with self.subTest(answer=answer):
                review = Mock(return_value='{"accepted": false, "reason": "Does not supply the requested sum."}')
                with self.assertRaisesRegex(ResultRejected, "did not complete the task"):
                    accept("Calculate 10 + 32 and include marker.", answer, review)

    def test_malformed_or_missing_review_fails_closed(self):
        for value in ("", "true", "[]", "null", "{}", '{"accepted": true}',
                      '{"accepted": 1, "reason": "wrong type"}', '{"accepted": true, "reason": ""}',
                      '{"accepted": true, "reason": "yes", "extra": 1}',
                      'Accepted: {"accepted": true, "reason": "yes"}'):
            with self.subTest(value=value):
                with self.assertRaises(ResultRejected):
                    accept("Calculate 10 + 32", "42", Mock(return_value=value))
        with self.assertRaises(ResultRejected):
            accept("Calculate 10 + 32", "42", Mock(side_effect=RuntimeError("provider down")))

    def test_capability_detection_distinguishes_supplied_text_from_file_work(self):
        for prompt in ("Read /tmp/a.txt and summarize it.", "Review services/dispatch_worker.py.",
                       "Inspect the repository for the consumer.", "List the files in the directory.",
                       "Write hello to /tmp/a.txt", "Save your answer to reviews/answer.md."):
            with self.subTest(prompt=prompt):
                self.assertTrue(task_queue.needs_files(prompt))
        for prompt in ("Write one sentence confirming you ran, into your answer.",
                       "Explain how to read a file in Python.",
                       "Analyze failure/recovery scenarios using these supplied facts.",
                       "Review input/output rates: 10 requests per second, 5 responses per second.",
                       "Review the supplied evidence: jobs never reach a consumer.",
                       "Review this snippet:\n```python\nread /tmp/a.txt\n```",
                       "Goal:\nRead services/worker.py.\n\nYour independent subtask:\nAnalyze the supplied evidence."):
            with self.subTest(prompt=prompt):
                self.assertFalse(task_queue.needs_files(prompt))

    def test_file_changes_require_write_tools_and_reads_remain_read_only(self):
        for prompt in ("Write reviews/result.md with your findings.", "Save the answer to `reviews/result.md`.",
                       "Review services/worker.py and edit services/worker.py.",
                       "Here is the text:\n```\nhello\n```\nWrite it to /tmp/hello.txt."):
            with self.subTest(prompt=prompt):
                self.assertEqual(task_queue.task_kind("analysis", prompt), "coding")
        self.assertEqual(task_queue.task_kind("analysis", "Read `services/worker.py` and explain its code."), "inspection")


if __name__ == "__main__":
    unittest.main()
