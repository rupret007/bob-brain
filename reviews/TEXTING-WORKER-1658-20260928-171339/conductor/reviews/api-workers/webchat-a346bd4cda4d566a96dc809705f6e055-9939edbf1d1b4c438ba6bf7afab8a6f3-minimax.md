Regression test: replay_json_missing_fences_fails_closed
Target: services/test_replay_completion.py; result_acceptance.check_completion_json
Setup: prompt='Project: Web Bob\nYour independent subtask:\nReview and regression test-case drafts for the following ongoing task. Deliver concrete findings and an actionable plan. Lead with two unexecuted regression drafts: one failure and one successful control. Each needs Regression test:, Target:, Setup:, Action: and Expected: lines with concrete values on the same line as each label. Keep findings brief. Never deploy or resolve conflicts.\nOngoing task:\n# lane-webbob-texting-replay-json-fix-1508\nRelevant evidence: services/dispatch_worker.py, services/result_acceptance.py, services/test_result_acceptance.py, services/test_api_workers.py, state/task_queue.py, webchat/worker_assignment.py, webchat/test_dispatch.py.'; answer='Findings: The replay contract tests are present. No JSON block supplied.'
Action: call check_completion_json(prompt, answer).
Expected: ResultRejected containing 'Missing or ambiguous required completion JSON output block'.

Regression test: replay_json_valid_accepted_reason_passes_completion_guard
Target: services/test_replay_completion.py; result_acceptance.check_completion_json
Setup: prompt='Project: Web Bob\nYour independent subtask:\nReview and regression test-case drafts for the following ongoing task. Deliver concrete findings and an actionable plan. Lead with two unexecuted regression drafts: one failure and one successful control. Each needs Regression test:, Target:, Setup:, Action: and Expected: lines with concrete values on the same line as each label. Keep findings brief. Never deploy or resolve conflicts.\nOngoing task:\n# lane-webbob-texting-replay-json-fix-1508\nRelevant evidence: services/dispatch_worker.py, services/result_acceptance.py, services/test_result_acceptance.py, services/test_api_workers.py, state/task_queue.py, webchat/worker_assignment.py, webchat/test_dispatch.py.'; answer='Findings: Valid regression drafts delivered.\n```json\n{"accepted": true, "reason": "Delivered regression test drafts for lane-webbob-texting-replay-json-fix-1508."}\n```'
Action: call check_completion_json(prompt, answer).
Expected: returns None; completion guard passes but semantic review still required for task acceptance.

Action plan:
Change: Validate existing CompletionContractTests in services/test_replay_completion.py cover the replay JSON fix; the check_completion_json guard rejects missing/ambiguous JSON and validates accepted/reason fields per result_acceptance.py unique_object hook.
Validation: Run python3 -m unittest discover -s services -p 'test_*.py' and require zero failures; validate existing test coverage before proposing new test additions.
Exit condition: Lane # lane-webbob-texting-replay-json-fix-1508 stays blocked until actual worker results and live replay gates pass; the validation command exit status confirms existing coverage but cannot substitute for live task completion.

```json
{"accepted": true, "reason": "Delivered two regression test drafts for lane-webbob-texting-replay-json-fix-1508 tracing check_completion_json failure/control paths; validated existing CompletionContractTests coverage in services/test_replay_completion.py; no live execution performed."}
```
Findings/limits: Existing CompletionContractTests.test_missing_malformed_or_ambiguous_json_cannot_win_a_positive_vote covers missing/malformed JSON rejection; check_completion_json unique_object hook detects duplicate fields; drafts are unexecuted, original lane-webbob-texting-replay-json-fix-1508 task prompt and worker results not supplied.
