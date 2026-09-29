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

Action plan:
Change: Validate existing CompletionContractTests in services/test_replay_completion.py for lane-webbob-texting-replay-json-fix-1508; check_completion_json and check_deliverables already implement the required guards, and CompletionContractTests covers the malformed/ambiguous cases.
Validation: Run python3 -m unittest discover -s services -p 'test_*.py'; existing tests verify the completion guard behavior for test-writing kind tasks.
Exit condition: lane-webbob-texting-replay-json-fix-1508 remains blocked until its actual worker results, fresh semantic review and live replay gates pass; these unexecuted drafts cannot close the lane.

```json
{"accepted": true, "reason": "Delivered completion-JSON failure/control regression drafts tied to lane-webbob-texting-replay-json-fix-1508; existing CompletionContractTests already covers malformed/ambiguous cases."}
```
Findings/limits: check_completion_json rejects missing/ambiguous output with 'Missing or ambiguous required completion JSON output block' and checks accepted/reason fields per services/result_acceptance.py lines 66-82; test_missing_malformed_or_ambiguous_json_cannot_win_a_positive_vote in services/test_replay_completion.py already covers these cases; drafts are unexecuted, and the actual worker results for lane-webbob-texting-replay-json-fix-1508 were not supplied.
