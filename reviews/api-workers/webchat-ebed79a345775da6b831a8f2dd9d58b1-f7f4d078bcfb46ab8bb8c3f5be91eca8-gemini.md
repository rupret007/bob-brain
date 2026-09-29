Based on a whole-repo audit for the ongoing task `lane-webbob-texting-replay-json-fix-1508`, this report provides concrete findings and an actionable implementation plan. The original prompt for the ongoing task was not supplied; this analysis is grounded in the available code.

### Findings

The task name `lane-webbob-texting-replay-json-fix-1508` suggests an issue with JSON handling in worker reports, possibly during a "texting replay" scenario. The codebase has a strict requirement for certain tasks to include a specific JSON block in their final answer. This is enforced by `check_completion_json` in `services/result_acceptance.py`.

1.  **Strict JSON Requirement:** The function `needs_completion_json` in `services/result_acceptance.py` mandates a completion JSON block for any task whose prompt contains "Your independent subtask:". This is a common pattern for audit and test-writing tasks assigned by `webchat/worker_assignment.py`.

2.  **Enforcement:** `services/dispatch_worker.py` calls `result_acceptance.check_answer` before any semantic review. This function deterministically rejects answers that fail `check_completion_json`, preventing them from ever reaching a "succeeded" state. The task is marked "rejected" and its status becomes "failed" in the queue, as shown in `services/test_api_workers.py` in `test_1035_failed_report_is_never_published_by_either_api_worker`.

3.  **Coverage Gap:** While `services/test_result_acceptance.py` and `services/test_api_workers.py` have extensive coverage for rejecting answers with *missing* or *malformed* JSON, there is no explicit test case that verifies an answer with a valid JSON block is correctly parsed and accepted by the deterministic checks, allowing it to proceed to the semantic review stage. The existing test `test_concrete_drafts_and_conditional_unblock_plan_reach_semantic_review` covers this implicitly but is focused on test-draft deliverables. A dedicated, minimal test case would harden this contract.

4.  **Implementation Plan:** The current implementation correctly enforces the required JSON structure. No code change is necessary. The actionable plan is to add a new test case to `services/test_result_acceptance.py` to explicitly cover the successful validation of a minimal, compliant answer containing the required JSON block. This ensures the gate doesn't have false positives and solidifies the contract for all workers.

### Action plan:
Change:In `services/test_result_acceptance.py`, add a new test method to `AcceptanceTests` to verify that `check_completion_json` correctly passes a minimal, valid answer.
Validation:python3 -m unittest discover -s services -p 'test_*.py'; the command must exit 0 with all tests passing, including the newly added test.
Exit condition:The `lane-webbob-texting-replay-json-fix-1508` unblock is resolved when the proposed test patch is accepted, its validation command passes, and the change is part of the deployed release.

```diff
--- a/services/test_result_acceptance.py
+++ b/services/test_result_acceptance.py
@@ -212,6 +212,12 @@
                        "Review this snippet:\n```python\nread /tmp/a.txt\n```",
                        "Goal:\nRead services/worker.py.\n\nYour independent subtask:\nAnalyze the supplied evidence."):
             with self.subTest(prompt=prompt):
                 self.assertFalse(task_queue.needs_files(prompt))
+
+    def test_minimal_valid_completion_json_passes_check(self):
+        prompt = "Your independent subtask:\nReview the evidence."
+        answer = 'Findings.\n```json\n{"accepted": true, "reason": "A valid reason."}\n```'
+        check_completion_json(prompt, answer)
 
     def test_file_changes_require_write_tools_and_reads_remain_read_only(self):
         for prompt in ("Write reviews/result.md with your findings.", "Save the answer to `reviews/result.md`.",

```

```json
{"accepted": true, "reason": "task-specific findings and limits of the work delivered"}
```
Findings/limits:The current implementation correctly enforces the required JSON output; the actionable plan is to add test coverage to prevent regressions, as no bug was found in the existing code.
