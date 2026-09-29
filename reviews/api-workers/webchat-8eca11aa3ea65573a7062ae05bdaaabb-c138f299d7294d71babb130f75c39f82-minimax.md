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
Change: Validate existing CompletionContractTests coverage in services/test_replay_completion.py for Web Bob unblock 1035; check_completion_json and check_deliverables guards are already implemented; the original job_id webchat-f4b8e359666155c6a06900f02b313c8c failed because the worker provided architectural findings instead of actual regression test-case drafts.
Validation: Run python3 -m unittest discover -s services -p 'test_*.py' and require zero failures; existing CompletionContractTests.test_missing_malformed_or_ambiguous_json_cannot_win_a_positive_vote and test_valid_worker_json_still_requires_independent_semantic_review provide coverage for the completion guard.
Exit condition: Web Bob unblock 1035 remains blocked until its actual worker results and live replay gates pass; the completion guard tests validate the JSON acceptance contract but cannot close the lane without live worker output.

```json
{"accepted": true, "reason": "Delivered two regression test-case drafts for check_completion_json using literal guard inputs from completion_guard_examples(); validated existing CompletionContractTests coverage; original job prompt not recorded and worker results not supplied."}
```
Findings/limits: The check_completion_json guard rejects missing or malformed accepted/reason JSON per services/result_acceptance.py needs_completion_json and unique_object validation; CompletionContractTests covers the failure and control cases; drafts are unexecuted per requirements; original unblock 1035 task prompt unavailable from services/fixtures/texting_jobcompletion_1035.json; services/test_replay_completion.py, services/result_acceptance.py, services/dispatch_worker.py, and services/api_worker.py were inspected.
