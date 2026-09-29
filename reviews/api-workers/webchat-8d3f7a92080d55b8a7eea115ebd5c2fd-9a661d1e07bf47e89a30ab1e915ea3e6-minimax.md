Regression test: replay escaped JSON in answer without outer completion block fails closed
Target: services/result_acceptance.py::check_completion_json
Setup: prompt='Return JSON with accepted/reason fields.'; answer='Setup: answer = "```json\n{\"accepted\": true, \"reason\": \"fixture\"}\n```"\n'
Action: check_completion_json(prompt, answer)
Expected: raises ResultRejected('Missing or ambiguous required completion JSON output block')

Regression test: valid accepted/reason JSON passes the completion guard
Target: services/result_acceptance.py::check_completion_json
Setup: prompt='Return JSON with accepted/reason fields.'; answer='{"accepted": true, "reason": "Delivered bounded unexecuted drafts."}'
Action: check_completion_json(prompt, answer)
Expected: returns None

Action plan:
Change: Validate existing CompletionContractTests.test_inline_escaped_json_fixture_does_not_hide_real_completion_block in services/test_replay_completion.py covers the escaped-JSON-in-replay scenario; no new code changes required for the check_completion_json guard itself.
Validation: Run python3 -m unittest discover -s services -p 'test_*.py' and require zero failures; actual worker results not available from this bounded snapshot.
Exit condition: Lane #1508 stays blocked until actual replay worker results and live replay gates pass; these unexecuted drafts validate existing guard coverage only.

```json
{"accepted": true, "reason": "Delivered two regression test drafts targeting check_completion_json with literal inputs and explicit guard outcomes; existing CompletionContractTests already covers escaped-JSON-in-replay scenario."}
```
Findings/limits: CompletionContractTests in services/test_replay_completion.py already validates escaped-JSON rejection and complete-JSON acceptance; report_repository and task_queue coverage exists via ReportRepositoryTests; original unblock assignment for #1508 not supplied; drafts are unexecuted.
