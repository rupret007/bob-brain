Regression test: missing completion JSON fails closed
Target: services/test_replay_completion.py; result_acceptance.check_completion_json
Setup: prompt='Your independent subtask:\nReview and regression test-case drafts.\nOngoing task:\nWeb Bob unblock 1035.\nReturn ONLY the following JSON object, without a Markdown fence or prose.\n{"regression_tests": [{"name": "[failure case]"}], "completion": {"accepted": true, "reason": "[reason]"}}.\n'; answer='Findings only. No JSON block provided. The task was explored but actual test drafts are pending another worker.'
Action: call result_acceptance.check_completion_json(prompt, answer).
Expected: raises ResultRejected with message containing 'Missing or ambiguous required completion JSON output block'.

Regression test: valid accepted/reason JSON passes completion guard
Target: services/test_replay_completion.py; result_acceptance.check_completion_json
Setup: prompt='Your independent subtask:\nReview and regression test-case drafts.\nOngoing task:\nWeb Bob unblock 1035.\nReturn ONLY the following JSON object, without a Markdown fence or prose.\n{"regression_tests": [{"name": "[failure case]"}], "completion": {"accepted": true, "reason": "[reason]"}}.\n'; answer='{"regression_tests": [{"name": "test", "target": "file", "setup": "{}", "action": "call", "expected": "result"}], "completion": {"accepted": true, "reason": "Delivered bounded unexecuted drafts and conditional plan for unblock 1035."}}'
Action: call result_acceptance.check_completion_json(prompt, answer).
Expected: returns None without raising; this guard alone does not establish semantic acceptance.

Unblock plan:
Change: Validate existing CompletionContractTests.test_missing_malformed_or_ambiguous_json_cannot_win_a_positive_vote in services/test_replay_completion.py for Web Bob unblock 1035; the check_completion_json and check_deliverables guards already exist and the original task prompt is unavailable.
Validation: Run python3 -m unittest services.test_replay_completion.CompletionContractTests -v and require zero failures; proposed validation only.
Exit condition: Web Bob unblock 1035 remains blocked until its actual worker results, fresh semantic reviews and live replay gates pass; these unexecuted drafts cannot close the lane.

```json
{"accepted": true, "reason": "Delivered check_completion_json failure/control drafts and a conditional validation plan grounded in existing CompletionContractTests; no tests or live gates executed; original unblock 1035 prompt unavailable."}
```
Findings/limits: Existing check_completion_json in result_acceptance.py rejects missing/ambiguous output blocks and validates accepted (bool) and reason (non-empty string) fields; CompletionContractTests.test_missing_malformed_or_ambiguous_json_cannot_win_a_positive_vote covers this guard with concrete answer examples; drafts are unexecuted, the original unblock 1035 prompt and live worker results were not supplied, and api_worker.render_report was truncated in the snapshot.
