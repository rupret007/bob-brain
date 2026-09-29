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
Change: Validate existing CompletionContractTests in services/test_replay_completion.py; the check_completion_json guard and outer draft fields are already implemented; original unblock 1035 task prompt is unavailable per services/fixtures/texting_jobcompletion_1035.json error.
Validation: Cannot execute: python3 -m unittest discover -s services -p 'test_*.py' - unexecuted drafts require a tool worker with live gates to run validation.
Exit condition: Web Bob unblock 1035 remains blocked until actual worker results, fresh reviews and live replay gates pass; these unexecuted regression test drafts cannot close the lane without tool-worker execution.

```json
{"accepted": true, "reason": "Delivered two completion-guard regression test drafts using literal prompt/answer inputs; adapted plan to validate existing test coverage for check_completion_json; original unblock 1035 task prompt not recorded per fixture."}
```
Findings/limits: check_completion_json is defined in services/result_acceptance.py lines 44-70; CompletionContractTests in services/test_replay_completion.py lines 51-76 cover malformed JSON rejection; services/fixtures/texting_jobcompletion_1035.json shows prior failure for lack of regression test drafts; services/fixtures/texting_regression_drafts_1658.json provides example transport structure; validation command requires live execution not available to this draft worker.
