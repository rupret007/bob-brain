Regression test: regression_test_case_failure
Target: services/test_replay_completion.py; result_acceptance.check_completion_json
Setup: prompt='Return JSON with accepted/reason fields.'; answer='Findings only.'
Action: call check_completion_json(prompt, answer).
Expected: ResultRejected containing 'Missing or ambiguous required completion JSON output block'.

Regression test: regression_test_case_control
Target: services/test_replay_completion.py; result_acceptance.check_completion_json
Setup: prompt='Return JSON with accepted/reason fields.'; answer='{"accepted": true, "reason": "Delivered bounded unexecuted drafts."}'
Action: call check_completion_json(prompt, answer).
Expected: returns None; this guard alone does not establish semantic acceptance or task completion.

Unblock plan:
Change: Validate existing CompletionContractTests in services/test_replay_completion.py for Web Bob unblock 1035; the completion and outer draft guards already exist, and the original assignment is unavailable.
Validation: Run python3 -m unittest discover -s services -p 'test_*.py' and require zero failures; proposed validation only.
Exit condition: Web Bob unblock 1035 stays blocked until its actual worker results, fresh reviews and live replay gates pass; these unexecuted drafts cannot close the lane.

```json
{"accepted": true, "reason": "Delivered completion-JSON failure/control drafts and a conditional plan; no tests or live gates executed."}
```
Findings/limits: Existing check_completion_json rejects missing output and checks accepted/reason fields; drafts are unexecuted, and the original unblock 1035 prompt and live result were not supplied.
