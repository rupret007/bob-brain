Regression test: check_completion_json rejects text without JSON block
Target: services/result_acceptance.py; result_acceptance.check_completion_json
Setup: prompt='Return JSON with accepted/reason fields.'; answer='Findings only.'
Action: call check_completion_json(prompt, answer).
Expected: ResultRejected containing 'Missing or ambiguous required completion JSON output block'.

Regression test: check_completion_json accepts valid accepted/reason JSON
Target: services/result_acceptance.py; result_acceptance.check_completion_json
Setup: prompt='Return JSON with accepted/reason fields.'; answer='{"accepted": true, "reason": "Delivered bounded unexecuted drafts."}'
Action: call check_completion_json(prompt, answer).
Expected: returns None; no ResultRejected raised.

Action plan:
Change: Validate existing CompletionContractTests in services/test_replay_completion.py and test_result_acceptance.py for check_completion_json behavioral coverage; the guard already rejects missing, malformed, ambiguous and duplicate-key JSON; no new code required for this lane.
Validation: Run python3 -m unittest discover -s services -p 'test_*.py' and require zero failures; proposed validation only.
Exit condition: Lane lane-webbob-texting-replay-json-fix-1508 stays blocked until actual worker results, live replay gates and fresh semantic review pass; these unexecuted drafts cannot close it.

```json
{"accepted": true, "reason": "Delivered two regression test drafts targeting check_completion_json behavior and a grounded plan validating existing coverage; drafts are unexecuted and original task evidence was not fully supplied."}
```
Findings/limits: Existing CompletionContractTests already covers check_completion_json guards for missing blocks (test_missing_malformed_or_ambiguous_json_cannot_win_a_positive_vote), inline-escaped fixtures (test_inline_escaped_json_fixture_does_not_hide_real_completion_block) and semantic review requirement (test_valid_worker_json_still_requires_independent_semantic_review); drafts are unexecuted and the lane-webbob-texting-replay-json-fix-1508 original task prompt and worker results were not supplied.
