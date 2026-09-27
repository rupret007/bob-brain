# Lane scheduler result — 2026-09-27

Branch: `draft/lane-scheduler-0927`. Base: `cfa72d6`.

Implemented the scheduler scope from `../conductor/WEBCHAT-READY.md` sections
04:06 and 04:09. Section 04:09 supersedes the earlier one-coder rule. Changes are
limited to scheduler/service code and tests, `state/queue-proof.md`, and this report.
The Web Bob UI/tool layer and the live conductor checkout were not changed.

## Delivered

- `services/queue_store.py`: locked, fsynced `conductor/state/queue.jsonl` requests
  with id, goal, repo, role, priority, status, owner, heartbeat, execution and
  promotion receipts. Stable producer ids prevent replay; interrupted final lines
  are quarantined/repaired, while middle corruption fails visibly. Structured
  `parts` expand idempotently into scoped jobs. See `services/README.md` for the
  producer API, CLI and request example.
- `services/scheduler.py` and the job-runner cycle: assign eligible ready jobs by
  priority, maintain durable reservations and named screens, and use six shared
  lanes: Cursor/Codex build, Claude review, Gemini research, MiniMax critique,
  and mini local tests. The existing INDEX/backlog importer remains available;
  an INDEX file is not required. Pending legacy executions are retained.
- Workers have separate Git worktrees/draft branches, attempt tokens and 15-second
  heartbeats. Launch grace is 30 seconds; stale threshold is 90 seconds. A stale
  process must be identified and stopped before reassignment; an unverified live
  worker keeps its reservation. Backoff, one retry per provider and subsequent
  fallback survive scheduler restarts. Exhausted chains remain blocked.
- Concurrent coding in the same repo is allowed for disjoint literal file/area
  scopes, including WebJam. Overlapping or unspecified scopes serialize. Repo
  identity resolves Git worktree aliases. Builds require explicit passing test
  commands at the exact result SHA, a clean committed worktree, scoped changes,
  and the approved normal draft push. Bootstrap and push guards remain in place.
- Verified work advances to review, then two independent council assessments,
  then `jeff-draft`. Reviewers receive actual result/test/diff/conflict evidence.
  Each approving assessment must explicitly return `VERDICT: PASS`. An explicit
  `FAIL` is preserved as a rejection and is not retried to seek approval elsewhere.
  Sibling build drafts pass conflict checks before review and again before final
  promotion. Git merge-tree only computes conflict evidence; no branch is merged.
- `runtime.py` still owns STATUS.md. Its lane board reports lane, job, state,
  start time, heartbeat and result/stage; the same rows are in the runtime
  `lane_board` snapshot. MAINTENANCE/STOP-WEBBOB stop new scheduling.

## Validation

| Check | Evidence |
| --- | --- |
| Full service regression suite | `python3 -m unittest discover -s services -p 'test_*.py'` — **91 tests passed**, 9.969s; includes the original 56 and 35 scheduler tests |
| Syntax gate | `python3 bootstrap.py check` — **syntax: PASS** |
| Whitespace/error check | `git diff --check` — **PASS** |
| Actual screen drill | `python3 services/scheduler_smoke.py --evidence state/queue-proof.md` — **PASS** |
| Six lanes occupied | Six named screen workers and fresh worker heartbeats observed together; captured STATUS lane board in [queue-proof.md](../state/queue-proof.md) |
| Three goals promoted | `goal-build`, `goal-audit`, `goal-checks` each reached **jeff-draft** through 27 queue records and 24 executions |
| Branch tests | Two independent fixture build branches committed and pushed to a temporary local bare remote; passing tests recorded at exact SHAs `d7f69826d4e27137995f19070b7f6a32cb68052b` and `2313449a5915cdb8d984b0b3fa0a181c85f8bc1f` |
| No source merge | Smoke source HEAD stayed `a9a01a763cfff972baae560578fecbdffad33ee7`; sibling conflict success/failure also tested against real Git repositories |

The screen drill uses **simulated provider replies**, explicitly labeled fixture
adapters. Queue dispatch, process launch, worktrees, heartbeat threads, Git
commits/pushes to the local fixture remote, tests, conflict checks and all
promotion transitions are real. No paid/live model calls or production jobs were
started. This proves the scheduler plumbing, not live-provider review quality or
production deployment. Temporary drill worktrees/processes were cleaned up.

Regression coverage includes concurrent enqueue/replay, partial journal recovery,
scope overlap and repo aliases, split replay, delayed screen visibility, stale
worker leases, old attempt tokens, Cursor → Cursor retry → Codex → Codex retry,
unavailable-provider fallback, lease contention without consuming attempts,
periodic heartbeats, real mini tests, failed/missing tests, untracked implementation,
out-of-scope changes, tampered result files, explicit review rejection, distinct
council providers, branch changes after tests, and real conflicting sibling drafts.

## Boundaries and push status

Large goals use producer-supplied `parts`, scopes and test commands. The scheduler
does not infer file ownership or invent a test command from prose. Unknown scope
means the whole repo. The council gate is two independent queued assessments;
the existing interactive `council.py` workflow is unchanged. `jeff-draft` is a
review-ready queue state, not a merge or final-build approval.

The repository has **no configured Git remote** (`git remote -v` is empty).
A normal `git push` failed with exit 128: `fatal: No configured push destination.`
The destination was requested during the session. Work is committed on the draft
branch containing this report; remote push requires that missing destination.
No merge, undraft, force-push, or live deployment was performed.
