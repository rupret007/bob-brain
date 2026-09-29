Regression test: missing source_job_id raises runtime error
Target: services/test_replay_completion.py; services/dispatch_worker.py report_repository
Setup: row={'source_job_id': 'nonexistent-1508'}; task_queue.tasks(ROOT) returns {}; jobs() returns {}.
Action: report_repository(row)
Expected: RuntimeError containing 'The assigned source job is no longer available'

Regression test: valid source with worktree returns worktree path
Target: services/test_replay_completion.py; services/dispatch_worker.py report_repository
Setup: tmpdir as Path; source={'id': 'source-1508', 'project': 'Web Bob', 'prompt': 'Web Bob assigned this task', 'worktree': str(tmpdir)}; task_queue.tasks(ROOT) returns {'source-1508': source}.
Action: report_repository({'source_job_id': 'source-1508'})
Expected: ('Web Bob', tmpdir) where tmpdir is the existing directory

Action plan:
Change: Validate existing ReportRepositoryTests and completion-contract coverage in services/test_replay_completion.py for lane-webbob-texting-replay-json-fix-1508; retain the unavailable-worktree None behavior in services/dispatch_worker.py report_repository.
Validation: Run python3 -m unittest discover -s services -p 'test_*.py' and require zero failures, then obtain fresh review and accepted saved replay reports.
Exit condition: The named lane stays blocked until its actual worker results, offline suites, live replay and rollback gates pass; these unexecuted drafts alone cannot close it.

```json
{"accepted": true, "reason": "Delivered two source-selection regression drafts grounded in report_repository implementation; tests are unexecuted and the full task/lane evidence was not supplied."}
```
Findings/limits: Existing ReportRepositoryTests in services/test_replay_completion.py already covers both missing-source and valid-worktree cases; drafts validate the current implementation against the named lane. Original prompt for #1508 was not supplied in evidence; drafts are conditional on available code.
