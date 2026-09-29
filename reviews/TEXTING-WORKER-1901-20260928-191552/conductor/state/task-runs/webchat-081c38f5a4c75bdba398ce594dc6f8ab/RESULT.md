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
Change: Validate existing coverage in services/test_replay_completion.py::CompletionContractTests and services/test_regression_drafts.py::RegressionDraftTests for the regression draft serialization format.
Validation: python3 -m unittest discover -s services -p 'test_*.py'
Exit condition: The lane-webbob-texting-regression-drafts-fix-1658 task requires live worker results and passing gates to be closed; these unexecuted drafts are insufficient.

```json
{"accepted": true, "reason": "Delivered the two required unexecuted regression drafts for completion JSON and an actionable plan to validate existing test coverage for the ongoing task."}
```
Findings/limits: The supplied evidence, including services/test_replay_completion.py and services/test_regression_drafts.py, indicates that guards for completion JSON and regression draft structure are already tested. The original task for #1658 was not provided. Drafts are unexecuted.
