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
Change: Validate existing coverage in services/test_replay_completion.py and services/test_result_acceptance.py. These tests cover dispatch source selection and result acceptance guards relevant to the lane-webbob-texting-smoke-replay-fix-1901 task.
Validation: python3 -m unittest discover -s services -p 'test_*.py'; require zero failures.
Exit condition: The named lane requires its actual worker results and live replay gates to pass; retain hold until that evidence is available.

```json
{"accepted": true, "reason": "Delivered the two required regression drafts for completion JSON guards and an actionable plan tied to the ongoing task."}
```
Findings/limits: The supplied code in services/dispatch_worker.py and services/result_acceptance.py shows robust handling for source job lookups and result validation, with existing test coverage. The full context for lane-webbob-texting-smoke-replay-fix-1901 was not provided. Drafts are unexecuted.
