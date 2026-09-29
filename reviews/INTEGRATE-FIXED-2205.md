INTEGRATE-FIXED-2205

RESULT: READY

New tip: `2cdcce928ea6a975825829a6c10a88a99017f643`
Branch: `draft/webbob-integrate-2057`
Base: `ab5053331d128372607194a0756b893d3872c7a0`
Completed UTC: 2026-09-28T03:36:06.857671+00:00
Regular push to `brain` succeeded; the remote branch SHA matches the new tip. Working tree is clean.

The saved attempt3 deployment evidence shows the turn-1 request in frozen session
`b33fac25-3c8a-452d-8673-47d3a99dd92c` encountered zero queued/claimed jobs and zero
confirmed running workers. The open `lane-webbob-llm-reviews` screen identified
Web Bob, but its activity was unverified. The assignment planner required a running
source and discarded that project context. Previous offline replay seeded a coding
job, so it missed this state.

The production change is confined to `webchat/worker_assignment.py`. When no
permitted active source exists, an observed open screen with a known project and
repository can now supply context for new Gemini/MiniMax API reports. Gemini gets
an audit job; MiniMax gets a test-writing job. Their prompts explicitly describe
the unverified activity and use the supplied repository snapshot. Existing work
keeps priority; project holds and explicit scopes still apply. This fallback is
limited to API workers, and creates no invented source job or running status.

The new regression reproduced both exact deployment failures before the repair:
`work request has no real dispatch` and
`Gemini/MiniMax did not receive API worker jobs`.
It now verifies real durable job IDs, receipt ownership, retry/restart idempotency,
and honest activity state from the frozen turn with an empty queue. Additional
cases cover project holds, requested scope, existing-job priority, unsupported
coding-worker fallback, and unidentified screens/processes.

The service regression follows the frozen request through Chat, the durable queue,
scheduler claims, worker execution, metered API transport, repository evidence,
saved reports, result/acceptance hashes, immutable receipts, and one-time chat
delivery. It checks `gemini-2.5-pro` and `MiniMax-M2.7`. HTTP responses, lane health,
semantic acceptance and the process-launch boundary are controlled offline test
fixtures; the real worker executes in process. No paid provider calls were made.

| Validation | Result |
| --- | --- |
| Webchat unittest discovery | 323 passed (21.877 s) |
| Services unittest discovery | 130 passed (4.370 s) |
| Bob parity/integration evals | 73/73 passed |
| Whitespace check | Passed |

The evals retain all 56 existing cases and add a second replay of all 17 frozen
turns from the failed deployment's lane-only starting condition. The reply and
receipt grading requirements were not relaxed. The status-observation path is
unchanged. Services ran from a hash-verified copy of all 362 tracked files
inside this worktree, with temporary repositories beside that copy so the existing
macOS code-write sandbox remained effective. Temporary validation trees were
removed after preserving logs and the source manifest.

Evidence directory: `/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-integrate-2057/reviews/integrate-fixed-2205`

- `red-regression.log`: exact pre-fix failure reproduction.
- `webchat-tests.log`, `services-tests.log`, `evals.log`: full-suite results.
- `api-worker-tests.log`: focused API-worker execution regression.
- `bob-parity-eval.json`, `validation.json`: detailed evals and final-tip validation.
- `services-copy-manifest.json`: verified source hashes, matching the committed tip.

READY for review of the offline repair. The failed live attempt remains a failure;
a new live replay has not been run. No deploy, service restart, merge, undraft,
force-push, Grok/xAI call, or Jeff notification was performed.
