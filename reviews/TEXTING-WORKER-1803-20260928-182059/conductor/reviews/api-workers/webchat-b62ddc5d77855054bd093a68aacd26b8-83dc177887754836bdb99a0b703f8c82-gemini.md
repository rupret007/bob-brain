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
Change: Validate existing test coverage in services/test_regression_drafts.py and services/test_guard_consistency.py, which verify the structured JSON report format for regression drafts and the underlying acceptance guards.
Validation: python3 -m unittest discover -s services -p 'test_*.py'; require zero failures.
Exit condition: The lane-webbob-texting-regression-drafts-fix-1658 hold must be retained until its actual worker results and live gates pass; these unexecuted drafts are insufficient to close the lane.

```json
{"accepted": true, "reason": "Delivered the two required unexecuted regression drafts for the completion JSON guard and an actionable plan to validate existing test coverage for the ongoing task."}
```
Findings/limits: The structured JSON report format for regression drafts is tested in services/test_regression_drafts.py. The supplied drafts are unexecuted examples of the completion guard, not a fix for the named lane. The original task prompt for #1658 was not supplied.
