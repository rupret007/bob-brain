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
Change: Validate existing CompletionContractTests in services/test_replay_completion.py for Web Bob unblock 1035; the completion guard in result_acceptance.py::check_completion_json already implements the required accepted/reason validation, and the original task prompt is unavailable as noted in the evidence.
Validation: python3 -m unittest discover -s services -p 'test_*.py' cannot be executed by this worker; proposed validation only.
Exit condition: Web Bob unblock 1035 remains blocked until its actual worker results, fresh task prompt, and live replay gates pass; these unexecuted drafts do not close the lane.

```json
{"accepted": true, "reason": "Delivered two completion-JSON guard drafts (missing/reject and complete/pass) with literal inputs from api_worker.py::completion_guard_examples(); validated existing CompletionContractTests coverage; cannot execute unittest due to no execution capability."}
```
Findings/limits: Original task prompt for Web Bob unblock 1035 is not recorded per services/fixtures/texting_jobcompletion_1035.json error message. Existing CompletionContractTests.test_missing_malformed_or_ambiguous_json_cannot_win_a_positive_vote and test_valid_worker_json_still_requires_independent_semantic_review in services/test_replay_completion.py provide guard coverage. Drafts are unexecuted per api_worker.py guidance. Cannot run validation command; plan requires actual worker results and live gates to exit blocked state.
