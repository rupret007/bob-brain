Regression test: missing completion JSON fails closed
Target: services/result_acceptance.py::check_completion_json
Setup: prompt='Project: Web Bob\nYour independent subtask:\nReview and regression test-case drafts for # lane-webbob-texting-replay-json-fix-1508.\nDeliver concrete findings and an actionable plan.\nOngoing task:\n# lane-webbob-texting-replay-json-fix-1508'; answer='Findings only. The replay JSON fix requires validation.'
Action: check_completion_json(prompt, answer)
Expected: raises ResultRejected('Missing or ambiguous required completion JSON output block')

Regression test: complete accepted/reason JSON passes the completion guard
Target: services/result_acceptance.py::check_completion_json
Setup: prompt='Project: Web Bob\nYour independent subtask:\nReview and regression test-case drafts for # lane-webbob-texting-replay-json-fix-1508.\nDeliver concrete findings and an actionable plan.\nOngoing task:\n# lane-webbob-texting-replay-json-fix-1508'; answer='{"accepted": true, "reason": "Delivered bounded unexecuted drafts for replay JSON fix validation."}'
Action: check_completion_json(prompt, answer)
Expected: returns None

Action plan:
Change: Validate existing CompletionContractTests in services/test_replay_completion.py for lane-webbob-texting-replay-json-fix-1508; the check_completion_json guard in services/result_acceptance.py already enforces accepted/reason output and rejects malformed or missing JSON.
Validation: Run python3 -m unittest discover -s services -p 'test_*.py' and require zero failures; the existing test_replay_completion.py::CompletionContractTests covers the completion guard contracts.
Exit condition: Lane # lane-webbob-texting-replay-json-fix-1508 stays blocked until actual worker results, fresh semantic reviews and live replay gates pass; these unexecuted regression drafts validate the guard behavior but cannot close the lane.

```json
{"accepted": true, "reason": "Delivered two regression test drafts (failure and control) for check_completion_json guard; validated existing test coverage in services/test_replay_completion.py; lane 1508 exit requires live worker results not provided in evidence."}
```
Findings/limits: The check_completion_json guard in services/result_acceptance.py (lines 60-85) rejects missing, ambiguous or invalid accepted/reason JSON; CompletionContractTests.test_missing_malformed_or_ambiguous_json_cannot_win_a_positive_vote and test_valid_worker_json_still_requires_independent_semantic_review provide existing coverage; drafts are unexecuted and the original lane 1508 task prompt/evidence were not supplied in full.
