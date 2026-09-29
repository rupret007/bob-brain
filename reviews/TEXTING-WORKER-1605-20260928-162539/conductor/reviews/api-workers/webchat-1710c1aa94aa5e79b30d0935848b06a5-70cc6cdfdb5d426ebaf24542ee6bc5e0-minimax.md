Regression test: missing_source_raises_runtime_error
Target: services/dispatch_worker.py::report_repository
Setup: row={'source_job_id': 'nonexistent-job-xyz', 'prompt': 'Review evidence'}; task_queue.tasks(ROOT) returns {} and state.jobs() returns {}.
Action: report_repository(row)
Expected: raises RuntimeError('The assigned source job is no longer available')

Regression test: valid_source_with_worktree_returns_worktree
Target: services/dispatch_worker.py::report_repository
Setup: d is a real temporary directory; source={'id': 'valid-001', 'project': 'Web Bob', 'prompt': 'Web Bob assigned this task', 'worktree': str(d), 'repo': '/unrelated'}; task_queue.tasks(ROOT) returns {'valid-001': source}.
Action: report_repository({'source_job_id': 'valid-001', 'prompt': 'Review evidence'})
Expected: returns ('Web Bob', Path(d)); the unrelated repo is not selected.

Action plan:
Change: Validate existing ReportRepositoryTests in services/test_replay_completion.py; the needed checks for source lookup and worktree selection already exist and cover the named lane's behavior.
Validation: Run python3 -m unittest discover -s services -p 'test_*.py' and require zero failures.
Exit condition: The lane-webbob-texting-replay-json-fix-1508 needs its actual worker result and live replay validation to pass; unexecuted drafts alone cannot close it.

```json
{"accepted": true, "reason": "Delivered two source-selection regression drafts grounded in dispatch_worker.py report_repository and existing ReportRepositoryTests; coverage validation and conditional plan supplied; no tests executed."}
```

Findings/limits: The two regression drafts target report_repository source_job_id lookup; ReportRepositoryTests already enforce missing-source raises, valid-worktree returns Path, and None/absent/non-dir worktrees return None. These drafts are unexecuted. The original prompt for lane-webbob-texting-replay-json-fix-1508 was not supplied in evidence; its full task context and live restart evidence are unavailable.
