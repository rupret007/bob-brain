Regression test: missing_completion_json_rejected_for_test_writing_task
Target: services/test_result_acceptance.py; result_acceptance.check_deliverables
Setup: prompt = "Project: Web Bob\nYour independent subtask:\nReview and regression test-case drafts for the following ongoing task.\nDeliver concrete findings and an actionable plan.\nOngoing task:\n# lane-webbob-texting-replay-json-fix-1508\nRelevant evidence: services/dispatch_worker.py, services/result_acceptance.py\n"; answer = "Regression test: queue_depth_check\nTarget: state/task_queue.py; task_queue.tasks\nSetup: ROOT = Path('/tmp/test_root'); task_queue.tasks(ROOT) returns {'j1': {'id': 'j1', 'status': 'queued'}}\nAction: len(task_queue.tasks(ROOT))\nExpected: returns 1\n\nFindings/limits: Draft exists but missing JSON block."
Action: result_acceptance.check_deliverables(prompt, answer, kind="test-writing")
Expected: raises ResultRejected("Missing or ambiguous required completion JSON output block")

Regression test: valid_test_writing_with_json_and_plan_passes_structural_check
Target: services/test_result_acceptance.py; result_acceptance.check_deliverables
Setup: prompt = "Project: Web Bob\nYour independent subtask:\nReview and regression test-case drafts for the following ongoing task.\nDeliver concrete findings and an actionable plan.\nOngoing task:\n# lane-webbob-texting-replay-json-fix-1508\nRelevant evidence: services/dispatch_worker.py, services/result_acceptance.py\n"; answer = "Regression test: source_job_missing_raises\nTarget: services/dispatch_worker.py; report_repository\nSetup: row = {'source_job_id': 'nonexistent'} with mocked task_queue.tasks(ROOT) returning {}\nAction: report_repository(row)\nExpected: raises RuntimeError containing 'The assigned source job is no longer available'\n\nAction plan:\nChange: Existing ReportRepositoryTests already cover this case in services/test_replay_completion.py; validate with python3 -m unittest discover -s services -p 'test_*.py'\nValidation: python3 -m unittest discover -s services -p 'test_*.py' passes with zero failures\nExit condition: The lane-webbob-texting-replay-json-fix-1508 task requires actual worker result and validation to pass\n\nFindings/limits: Drafts are unexecuted; existing test coverage validates the source lookup path.\n```json\n{\"accepted\": true, \"reason\": \"Two regression drafts delivered for report_repository source lookup and acceptance JSON validation; existing coverage cited.\"}\n```"
Action: result_acceptance.check_deliverables(prompt, answer, kind="test-writing")
Expected: returns None (no exception raised)

Action plan:
Change: Add the two test cases above to services/test_result_acceptance.py covering check_deliverables JSON block enforcement for test-writing tasks
Validation: python3 -m unittest discover -s services -p 'test_*.py' passes with zero failures
Exit condition: The lane-webbob-texting-replay-json-fix-1508 stays blocked until its actual worker result, live replay and validation pass

Findings/limits: Existing ReportRepositoryTests in services/test_replay_completion.py already cover report_repository source lookup. The drafts above target check_deliverables structural enforcement not yet isolated in a dedicated test case. Original task prompt for lane-webbob-texting-replay-json-fix-1508 was not supplied in evidence; drafts are grounded in the current implementation and prior fixture patterns. No tests executed.

```json
{"accepted": true, "reason": "Delivered two unexecuted regression test drafts for check_deliverables JSON enforcement and report_repository source lookup; action plan and existing coverage cited."}
```
