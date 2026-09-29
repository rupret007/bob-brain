Regression test: report_repository_missing_source_raises
Target: services/test_replay_completion.py; services/dispatch_worker.py report_repository
Setup: import dispatch_worker as dispatch, from state import ROOT; patch dispatch.task_queue.tasks to return {} and state.jobs to return {}; row = {"source_job_id": "nonexistent-job-999", "prompt": "Review texting screen isolation", "kind": "test-writing"}
Action: report_repository(row)
Expected: raises RuntimeError("The assigned source job is no longer available")

Regression test: report_repository_valid_source_with_worktree_returns_worktree
Target: services/test_replay_completion.py; services/dispatch_worker.py report_repository
Setup: import dispatch_worker as dispatch, from state import ROOT, CONDUCTOR; worktree_dir = Path(tempfile.mkdtemp()); source_job = {"id": "valid-source-001", "prompt": "Your independent subtask:\nReview texting screen isolation\nOngoing task:\n# lane-webbob-texting-screen-isolation-fix-1403\nRelevant evidence: services/dispatch_worker.py", "project": "Web Bob", "worktree": str(worktree_dir), "repo": str(Path(tempfile.mkdtemp()))}; patch dispatch.task_queue.tasks to return {"valid-source-001": source_job}; row = {"source_job_id": "valid-source-001", "prompt": "Review evidence", "kind": "test-writing"}
Action: result = report_repository(row)
Expected: result == ("Web Bob", worktree_dir); the returned worktree is the source job's worktree, not the repo fallback

Action plan:
Change: Add regression test coverage for services/dispatch_worker.py report_repository source_job_id lookup paths in services/test_replay_completion.py; existing ReportRepositoryTests already cover most paths but lack the explicit source_job_id lookup validation.
Validation: python3 -m unittest discover -s services -p 'test_*.py'; require zero failures in ReportRepositoryTests and CompletionContractTests.
Exit condition: The lane-webbob-texting-screen-isolation-fix-1403 needs its actual worker result with accepted/reason JSON, check_answer or accept validation to pass, and the named lane's restart evidence to close.

Findings/limits: The regression drafts trace report_repository's source_job_id lookup and worktree selection logic; existing test coverage exists in ReportRepositoryTests but the explicit source_job_id lookup validation for #1403 behavior needs targeted drafts. No tests executed; lane's full task prompt and restart evidence were not supplied.

```json
{"accepted": true, "reason": "Delivered unexecuted regression drafts for report_repository source_job_id lookup paths and an actionable plan; no tests or live validation performed."}
```
