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
Change: Validate existing CompletionContractTests in services/test_replay_completion.py for lane-webbob-texting-replay-json-fix-1508; check_completion_json and check_deliverables guards already implement the required acceptance logic.
Validation: Run python3 -m unittest discover -s services -p 'test_*.py' and require zero failures; existing tests already cover the completion JSON guard.
Exit condition: The named lane needs its actual worker result, durable service identity checks, live replay and rollback validation to pass; these unexecuted drafts cannot close it.

```json
{"accepted": true, "reason": "Delivered two regression test drafts validating the check_completion_json guard for lane-webbob-texting-replay-json-fix-1508 and a grounded conditional plan; no live tests executed."}
```
Findings/limits: Existing CompletionContractTests.test_missing_malformed_or_ambiguous_json_cannot_win_a_positive_vote already covers missing/invalid JSON rejection; the guard is implemented and tests exist in services/test_replay_completion.py. Drafts are unexecuted and the original task/evidence for lane 1508 was not supplied in full.
