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
Change: Validate existing CompletionContractTests in services/test_replay_completion.py; check_completion_json and check_deliverables guards are implemented in services/result_acceptance.py and already tested. The original unblock 1035 task prompt was not recorded (per job error: 'original task prompt was not recorded').
Validation: python3 -m unittest discover -s services -p 'test_*.py'; no tests were executed and no worker results are available.
Exit condition: Web Bob unblock 1035 remains blocked; these unexecuted drafts cannot close the lane without actual worker results, fresh reviews, and live replay gates passing. The original task prompt is unavailable per the historical job error.

```json
{"accepted": true, "reason": "Delivered regression test-case drafts for check_completion_json guard with literal inputs; existing CompletionContractTests already validate this guard. Original unblock 1035 task prompt not recorded per services/fixtures/texting_jobcompletion_1035.json job error."}
```
Findings/limits: check_completion_json rejects missing/invalid accepted/reason JSON per needs_completion_json and unique_object checks in services/result_acceptance.py. CompletionContractTests.test_missing_malformed_or_ambiguous_json_cannot_win_a_positive_vote already covers rejection cases including 'Findings only.' answer. Drafts are unexecuted per task constraints. Original task prompt for Web Bob unblock 1035 was not recorded per the historical job error in texting_jobcompletion_1035.json.
