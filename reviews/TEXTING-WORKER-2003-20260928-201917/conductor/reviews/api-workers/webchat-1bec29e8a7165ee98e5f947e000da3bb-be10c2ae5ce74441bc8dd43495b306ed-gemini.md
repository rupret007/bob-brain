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
Change: Validate existing coverage in services/test_replay_completion.py::CompletionContractTests, which already tests the behavior targeted by these drafts for the completion JSON guard.
Validation: python3 -m unittest discover -s services -p 'test_*.py'; require zero failures.
Exit condition: The lane-webbob-texting-regression-drafts-fix-1658 task requires its actual worker results and live gates to pass; these unexecuted drafts and validation of existing coverage do not close it.

```json
{"accepted": true, "reason": "Delivered the two required unexecuted regression drafts for the completion guard and an actionable plan to validate existing test coverage for the ongoing task."}
```
Findings/limits: The supplied regression drafts target the completion JSON guard in services/result_acceptance.py. Existing test coverage for this guard is present in services/test_replay_completion.py. Drafts are unexecuted and the original task prompt for #1658 was not supplied.
