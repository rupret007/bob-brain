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
Change: Validate existing CompletionContractTests.test_missing_malformed_or_ambiguous_json_cannot_win_a_positive_vote in services/test_replay_completion.py covers the check_completion_json guard behavior; no new implementation needed for Web Bob unblock 1035 since the guard and test contracts are already present.
Validation: python3 -m unittest discover -s services -p 'test_*.py' has not been executed; validation is conditional on actual worker execution results which are unavailable for this draft.
Exit condition: Web Bob unblock 1035 remains blocked until actual worker results, live test execution, and independent semantic review pass; drafts are unexecuted and cannot close the lane.

```json
{"accepted": true, "reason": "Delivered regression test-case drafts for check_completion_json guard using literal inputs and expected outcomes; validated existing CompletionContractTests coverage; disclosed missing original task prompt and unexecuted drafts."}
```
Findings/limits: The original task prompt for Web Bob unblock 1035 (job_id: webchat-f4b8e359666155c6a06900f02b313c8c) was not recorded per services/fixtures/texting_jobcompletion_1035.json error. Existing check_completion_json guard is already implemented in services/result_acceptance.py and covered by CompletionContractTests. Regression drafts are unexecuted. No shell/file-writing tools available to run validation. Cannot claim test execution or resolve lane closure.
