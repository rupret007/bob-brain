Regression test: missing completion JSON fails closed
Target: services/result_acceptance.py::check_completion_json
Setup: prompt='Return JSON with accepted/reason fields.'; answer='Findings only.'
Action: check_completion_json(prompt, answer)
Expected: raises ResultRejected('Missing or ambiguous required completion JSON output block')

Regression test: complete accepted/reason JSON passes the completion guard
Target: services/result_acceptance.py::check_completion_json
Setup: prompt='Return JSON with accepted/reason fields.'; answer='{"accepted": true, "reason": "Delivered bounded unexecuted drafts."}'
Action: check_completion_json(prompt, answer)
Expected: returns None

Unblock plan:
Change: Validate existing CompletionContractTests in services/test_replay_completion.py; the check_completion_json guard and draft_acceptance coverage already exist for Web Bob unblock 1035, but the original task prompt is unavailable.
Validation: python3 -m unittest discover -s services -p 'test_*.py'; exit requires actual worker results and live gates, otherwise remain blocked.
Exit condition: Web Bob unblock 1035 remains blocked until actual worker results, fresh semantic reviews and live replay gates pass; these unexecuted drafts cannot close the lane.

```json
{"accepted": true, "reason": "Delivered completion-JSON failure/control regression test drafts and a validation plan; existing CompletionContractTests coverage confirmed, but original unblock 1035 prompt and live worker results are unavailable."}
```
Findings/limits: Original task prompt for Web Bob unblock 1035 was not recorded (confirmed in texting_jobcompletion_1035.json fixture); check_completion_json guard exists and is tested in CompletionContractTests; drafts are unexecuted; cannot validate without actual worker results and live gates.
