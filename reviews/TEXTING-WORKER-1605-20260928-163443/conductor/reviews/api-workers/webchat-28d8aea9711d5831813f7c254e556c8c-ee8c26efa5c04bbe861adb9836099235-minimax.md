Regression test: report_repository_missing_source_job
Target: services/test_replay_completion.py; services/dispatch_worker.py report_repository
Setup: row={'source_job_id': 'missing-job-999'}; patch dispatch_worker.task_queue.tasks to return {} and patch state.jobs to return {}.
Action: report_repository(row)
Expected: raises RuntimeError("The assigned source job is no longer available")

Regression test: report_repository_valid_worktree_selected
Target: services/test_replay_completion.py; services/dispatch_worker.py report_repository
Setup: create tempdir d; source={'id': 'valid-source-001', 'project': 'Web Bob', 'prompt': 'Web Bob assigned this task', 'worktree': str(d), 'repo': '/unrelated'}; patch task_queue.tasks to return {'valid-source-001': source}; patch state.jobs to return {}.
Action: report_repository({'source_job_id': 'valid-source-001'})
Expected: returns ('Web Bob', Path(d)); the unrelated repo is not selected.

Action plan:
Change: Validate existing ReportRepositoryTests coverage in services/test_replay_completion.py for report_repository source_job_id lookup and unavailable-worktree None behavior; no new checks needed in services/dispatch_worker.py.
Validation: Run python3 -m unittest discover -s services -p 'test_*.py' and require zero failures, then obtain fresh Gemini/MiniMax review and accepted saved replay reports for lane-webbob-texting-replay-json-fix-1508.
Exit condition: The named lane stays blocked until its actual worker results, offline suites, live replay and rollback gates pass; these unexecuted drafts alone cannot close it.

```json
{"accepted": true, "reason": "Delivered two source-selection regression drafts grounded in current report_repository implementation; validated existing ReportRepositoryTests coverage and provided conditional validation plan for lane-webbob-texting-replay-json-fix-1508; tests not executed."}
```

Findings/limits: Existing ReportRepositoryTests in services/test_replay_completion.py already cover missing-source and valid-source worktree cases; drafts confirm coverage and behavior; tests and live gates were not executed; original prompt/state for lane-webbob-texting-replay-json-fix-1508 was not supplied in evidence.
