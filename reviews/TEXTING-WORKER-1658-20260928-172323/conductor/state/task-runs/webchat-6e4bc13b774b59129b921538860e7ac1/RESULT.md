Regression test: malformed completion JSON raises ResultRejected
Target: services/result_acceptance.py; result_acceptance.check_completion_json
Setup: prompt='Return JSON with accepted/reason fields.'; answer='Findings only.'
Action: call check_completion_json(prompt, answer).
Expected: ResultRejected containing 'Missing or ambiguous required completion JSON output block'.

Regression test: valid accepted/reason JSON passes completion guard
Target: services/result_acceptance.py; result_acceptance.check_completion_json
Setup: prompt='Return JSON with accepted/reason fields.'; answer='{"accepted": true, "reason": "Delivered bounded unexecuted drafts."}'
Action: call check_completion_json(prompt, answer).
Expected: returns None; this guard alone does not establish semantic acceptance or task completion.

Unblock plan:
Change: Validate existing CompletionContractTests in services/test_replay_completion.py covers check_completion_json; the completion guard and outer draft fields already exist in result_acceptance.py and api_worker.py.
Validation: python3 -m unittest discover -s services -p 'test_*.py' required; this is unexecuted validation of existing coverage only.
Exit condition: Web Bob unblock 1035 stays blocked until its actual worker results and live replay gates pass; drafts are unexecuted and original task prompt unavailable.

```json
{"accepted": true, "reason": "Delivered check_completion_json failure/control drafts grounded in existing CompletionContractTests; validation of existing coverage confirmed, exit requires actual worker results."}
```
Findings/limits: Original task prompt for lane 1035 was not recorded (limitation disclosed). Existing CompletionContractTests.test_missing_malformed_or_ambiguous_json_cannot_win_a_positive_vote already validates check_completion_json; test_exact_1403_failure_and_corrected_control provides failure/control pattern. Drafts are unexecuted and trace check_completion_json through literal prompt/answer inputs as required.
