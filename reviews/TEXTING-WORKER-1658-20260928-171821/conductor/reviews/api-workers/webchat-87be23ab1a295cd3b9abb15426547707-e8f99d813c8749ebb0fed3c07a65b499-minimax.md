Regression test: missing completion JSON fails closed
Target: services/result_acceptance.py::check_completion_json
Setup: prompt='Your independent subtask:\nReview and return JSON with accepted/reason fields.'; answer='Findings only.'
Action: result_acceptance.check_completion_json(prompt, answer)
Expected: ResultRejected containing 'Missing or ambiguous required completion JSON output block'

Regression test: valid completion JSON passes the guard
Target: services/result_acceptance.py::check_completion_json
Setup: prompt='Your independent subtask:\nReturn JSON with accepted/reason fields.'; answer='```json\n{"accepted": true, "reason": "Delivered bounded unexecuted drafts."}\n```'
Action: result_acceptance.check_completion_json(prompt, answer)
Expected: returns None without raising ResultRejected

Action plan:
Change: Validate existing CompletionContractTests in services/test_replay_completion.py; the check_completion_json guard rejects missing/ambiguous JSON blocks and checks accepted/reason field types/values per result_acceptance.py lines 35-60
Validation: python3 -m unittest discover -s services -p 'test_*.py'; require zero failures; proposed validation only
Exit condition: lane-webbob-texting-replay-json-fix-1508 stays blocked until actual worker results with valid completion JSON blocks and live replay gates pass; these unexecuted drafts cannot close the lane

```json
{"accepted": true, "reason": "Delivered two regression drafts targeting check_completion_json in result_acceptance.py, validated existing CompletionContractTests coverage, and provided conditional plan tied to lane-webbob-texting-replay-json-fix-1508; no tests executed"}
```
Findings/limits: Drafts trace check_completion_json behavior from result_acceptance.py; existing CompletionContractTests::test_missing_malformed_or_ambiguous_json_cannot_win_a_positive_vote covers this guard; original task prompt and live worker results for lane 1508 were not supplied; these are unexecuted behavioral drafts, not proof of lane closure
