Regression test: report_repository_source_missing_worktree_field
Target: services/test_replay_completion.py; services/dispatch_worker.py report_repository
Setup: row={'source_job_id': 'valid-no-worktree'}; task_queue.tasks(ROOT) returns {'valid-no-worktree': {'id': 'valid-no-worktree', 'project': 'Web Bob', 'prompt': 'Web Bob assigned this task', 'worktree': None, 'repo': '/repo/default'}}
Action: report_repository(row)
Expected: ('Web Bob', None); the source exists but lacks a worktree, so worktree is None and unrelated repo is not selected

Regression test: report_repository_source_with_valid_worktree
Target: services/test_replay_completion.py; services/dispatch_worker.py report_repository
Setup: create temporary directory d; row={'source_job_id': 'valid-with-worktree'}; task_queue.tasks(ROOT) returns {'valid-with-worktree': {'id': 'valid-with-worktree', 'project': 'Web Bob', 'prompt': 'Web Bob assigned this task', 'worktree': str(d), 'repo': '/unrelated'}}
Action: report_repository(row)
Expected: ('Web Bob', Path(d)); the valid worktree directory is returned and unrelated repo is not selected

Action plan:
Change: Add two test methods to ReportRepositoryTests in services/test_replay_completion.py covering source jobs with worktree=None and source jobs with valid worktree; existing dispatch_worker.py report_repository already enforces that behavior
Validation: Run python3 -m unittest discover -s services -p 'test_*.py' and require zero failures; distinguish proposed from executed checks since no test execution was performed
Exit condition: The named task # lane-webbob-texting-replay-json-fix-1508 needs its actual worker result and validation to pass; structural test coverage alone cannot close it

```json
{"accepted": true, "reason": "Delivered two source-selection regression test drafts grounded in current report_repository implementation and existing ReportRepositoryTests; drafts are unexecuted and the named lane's full task/evidence were not supplied."}
```

Findings/limits: The two drafts target the gap between existing tests: source exists with worktree=None returns (project, None), and source with valid worktree returns (project, worktree Path). Existing test_missing_or_none_worktree_returns_none_despite_repo covers None worktree in a different Setup shape. No original prompt for # lane-webbob-texting-replay-json-fix-1508 was supplied in evidence, so conditional actions are grounded only in available code. No test execution was performed.
