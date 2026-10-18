# Web Bob dispatch proof — 2026-09-27

Live endpoint: `http://127.0.0.1:8787`. Local branch: `draft/webbob-dispatch-0927`. Code commit: `1f6c042`. All timestamps below are UTC (Chicago is UTC−05:00 on this date).

## Verified outcome

Authenticated requests sent through `POST /api/messages` were claimed by **Codex, Gemini, and MiniMax**, executed by real workers, and returned as durable assistant messages in the originating conversations. No direct queue injection, mocked model, manual claim, or manual result insertion was used for the live proof. Each shown task has one visible result.

| Worker | Queued | Claimed | Execution started | Finished | Answer saved in chat | Attempts |
|---|---|---|---|---|---|---|
| codex | 2026-09-27T15:26:31.279+00:00 | 2026-09-27T15:26:32.215+00:00 | 2026-09-27T15:26:32.324+00:00 | 2026-09-27T15:26:49.414+00:00 | 2026-09-27T15:26:49.507+00:00 | 1 |
| gemini | 2026-09-27T15:27:19.937+00:00 | 2026-09-27T15:27:25.707+00:00 | 2026-09-27T15:27:25.773+00:00 | 2026-09-27T15:27:26.780+00:00 | 2026-09-27T15:27:27.713+00:00 | 1 |
| minimax | 2026-09-27T15:28:47.441+00:00 | 2026-09-27T15:28:50.808+00:00 | 2026-09-27T15:28:50.871+00:00 | 2026-09-27T15:29:08.178+00:00 | 2026-09-27T15:29:09.015+00:00 | 1 |

## Requests and returned answers

### codex

- Task: `webchat-c96d2c7fba4452dc8ad2cbb5fc65e875`
- Conversation: `494e5739-898f-4e8b-81b7-939ba8a9d3d0`
- Request: `04da57e8-29ac-4511-b417-c7e46e1f3054`
- Result message: `faa8e699-a802-52be-87b5-f32d3cce4401`
- Result SHA-256: `f90cc08c248a8801711b6fac5c291b17d63a3ddf658aba52d74b6670f3609761`
- Observed queue wait: `0.936 s`; result-to-chat delay: `0.093 s`.

Request:

> Review services/command.py in your assigned checkout. Read the file and explain how timeout and SIGTERM clean up child process groups. Cite two line numbers and identify one limit of this protection. Do not modify files; return a concrete review under 150 words.

Actual assistant response:

codex finished:

`run()` starts each child in a new session, giving it a separate process group. On timeout, `communicate()` raises; the exception handler kills the group, closes captured pipes, and re-raises ([line 45](/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webchat-c96d2c7fba4452dc8ad2cbb5fc65e875/services/command.py:45)).

On SIGTERM, the installed handler calls `kill_group()` and exits with status 143 ([line 38](/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webchat-c96d2c7fba4452dc8ad2cbb5fc65e875/services/command.py:38)). Cleanup sends SIGTERM to the entire group, waits up to 0.5 seconds for the direct child, then sends SIGKILL if the group still exists and waits for the child.

One limit: descendants that create a new session or leave the original process group escape this group-based cleanup.

No files were modified.

### gemini

- Task: `webchat-2acc32a044d75285b1261d348a2e00dc`
- Conversation: `7b80ddd2-bc63-498f-ac6c-41858ad28b78`
- Request: `5fadcf41-8ba6-45b8-a6ef-61b859007526`
- Result message: `5deb450b-aac9-5581-b44b-3c8d8a2cb8a2`
- Result SHA-256: `21f43024070c076c9eb658c0ff975e4b28a729b51b97680788ce79e978ed1f2d`
- Observed queue wait: `5.770 s`; result-to-chat delay: `0.933 s`.

Request:

> Calculate the pickup delay in seconds for a job queued at 15:02:03.250 UTC and claimed at 15:02:07.750 UTC. Show the subtraction and state whether it meets a five-second pickup objective. This is a fresh worker-refill task after a service restart.

Actual assistant response:

gemini finished:

The job was queued at 15:02:03.250 UTC and claimed at 15:02:07.750 UTC.

Pickup delay = Claim time - Queue time
Pickup delay = 15:02:07.750 - 15:02:03.250
Pickup delay = 4.500 seconds

The pickup delay is 4.500 seconds. This meets the five-second pickup objective.

### minimax

- Task: `webchat-7cc70a31b3d6542b9899e5dd5a4876c2`
- Conversation: `20713793-417a-4c0b-a801-2609ea49df0d`
- Request: `9cf43b1a-81e4-4741-b14d-49cf23beeb55`
- Result message: `7b5b92fa-2b88-5832-bb32-09e7ce179e0a`
- Result SHA-256: `ba974b774dbb8abec55d98919fa9dfc07c3b12b70c9247e2ce6cdc7b7eacfbc0`
- Observed queue wait: `3.367 s`; result-to-chat delay: `0.836 s`.

Request:

> Calculate dispatch latency from these actual UTC events on the same date: queued 14:56:00.758, claimed 14:56:04.652, execution started 14:56:04.714, finished 14:56:30.337, chat answer saved 14:56:30.348. Report four durations in seconds to three decimals: queue wait (claimed minus queued), execution (finished minus started), delivery (chat minus finished), and end-to-end (chat minus queued). Show a compact table with the subtraction for each. This is an actual service measurement task; do not review code or propose changes.

Actual assistant response:

minimax finished:

**Dispatch Latency Summary**

| Metric | Calculation | Duration (s) |
|--------|-------------|--------------|
| Queue wait | 14:56:04.652 − 14:56:00.758 | **3.894** |
| Execution | 14:56:30.337 − 14:56:04.714 | **25.623** |
| Delivery | 14:56:30.348 − 14:56:30.337 | **0.011** |
| End‑to‑end | 14:56:30.348 − 14:56:00.758 | **29.590** |

All durations are expressed in seconds to three decimal places.

## Full path and repairs

1. **Chat → task:** direct work phrases, explicit job requests, and explicit worker routes now save the user turn plus dispatch intent before enqueueing. `state/queue.jsonl` is the fsynced, locked task journal. A deterministic task ID makes HTTP retries and interrupted saves idempotent. The API accepts `worker` (`codex`, `claude`, `cursor-agent`, `gemini`, `minimax`, or automatic routing); Grok is rejected. Code/execution tasks require tool workers. Accepted legacy chat receipts are migrated with their originating conversation.
2. **Task → runner:** the previous chat writer emitted `WebBob` rows that the project scheduler skipped. There was no durable chat-task consumer or result callback. `job-runner` now polls the chat dispatcher with a five-second sleep; older project housekeeping runs separately on its one-minute cadence. Cycle overhead is additional to the sleep. Legacy chat rows are excluded from the project scheduler to prevent duplicate execution.
3. **Claim → worker:** claims are atomic across processes, reserve one task per worker, carry a unique fencing token, and expire after 90 seconds. Workers hold the shared lane and task locks, renew leases every ten seconds, and persist actual execution start/PID. A duplicate launcher cannot invalidate the real owner. Lane contention releases the claim without spending an attempt. Expired or dead claims are recovered, with bounded retries and visible terminal failures. The expired-worker reaper verifies PID, task ID and claim token before stopping only its owned process tree.
4. **Worker → execution:** both the webchat launcher and detached worker launcher source `conductor/keys.env` without logging values; the runner already reloaded it each cycle. Code jobs use private local clones with independent Git metadata, draft branches, no origin remote, and a rejecting push hook. Uncommitted code changes cannot count as success. The existing live-core write boundary remains enforced.
5. **Execution → chat:** the final answer is saved in the fenced task record before the worker releases its lane. Web Bob writes a deterministic result-message ID into the originating conversation, then acknowledges delivery in the journal. A chat save or acknowledgement failure retries safely after restart. An in-flight ordinary chat reply cannot be overwritten by an asynchronous job result.
6. **Live-discovered Codex break:** the first Codex job reached execution but failed to read a file because its inner sandbox could not initialize inside `sandbox-exec`. The initial task exhausted three bounded attempts and reported its failure in chat. Codex now uses the existing outer OS boundary; analysis denies writes to both the worktree and Git metadata. Real macOS tests prove file reads succeed and writes fail. The replacement Codex request read `services/command.py` and returned line-specific findings.
7. **Deployment/recovery break:** maintenance initially prevented runner startup. Later, the bootstrap guard reported transient validation failures and restored the stale `last-good` (`d900498`), removing the dispatcher. Syntax checks of the affected files pass. The guard now serializes recovery, retries a failed validation, and refuses to roll back local changes. Preserved local edits were restored, and the tested local dispatch commit is installed as the new `last-good` recovery version before maintenance is cleared. This is a local recovery-tag update; no remote update or merge is involved.

Execution is retried after an interrupted attempt; it is not a claim of exactly-once external side effects. Claim fencing and deterministic chat message IDs prevent a superseded worker or delivery retry from publishing duplicate terminal answers. Tasks stay local and draft-only.

## Tests

| File set | Command | Result |
|---|---|---|
| Shared tree before concurrent rewrites | `python3 -m unittest discover -s services -p 'test_*.py'` | 98 passed (2.017 s) |
| Shared tree before concurrent rewrites | `python3 -m unittest discover -s webchat -p 'test_*.py'` | 166 passed (13.405 s) |
| Isolated commit contents | `python3 -m unittest discover -s services -p 'test_*.py'` | 82 passed (2.159 s) |
| Isolated commit contents | `python3 -m unittest discover -s webchat -p 'test_*.py'` | 124 passed (10.285 s) |

`python3 bootstrap.py check`, Python compilation of the new queue/chat modules, and `bash -n` on the launchers pass. Regression coverage includes concurrent claims, torn writes, stale-token completion, real process death, hung-worker ownership checks, lane contention, lease renewal, idle refill, crash recovery before/after enqueue, original-chat delivery, save/ack failure deduplication, credential loading, no Grok, and the real macOS sandbox boundary.

The isolated commit check excludes unrelated ongoing frontend and review changes. Small preexisting queue-parser/provider/card helpers required by the committed app and its existing tests are included so the dispatch commit is self-contained.

## Live attempts and restart checks

| Worker | Task | Outcome | Attempts | Chat timestamp |
|---|---|---|---|---|
| codex | `webchat-260071f0845f59359813ff1df7f5e351` | failed | 3 | 2026-09-27T14:57:29.138+00:00 |
| gemini | `webchat-507705c0221650c1995512863cfb2807` | succeeded | 1 | 2026-09-27T14:56:06.322+00:00 |
| minimax | `webchat-c0e540c8d9885245b307a6c9b758bd32` | succeeded | 1 | 2026-09-27T14:56:30.348+00:00 |
| codex | `webchat-c970316bc444501d8ec69fe7bbaaea34` | succeeded | 1 | 2026-09-27T14:59:45.209+00:00 |
| gemini | `webchat-24159ec0a957569cb19a656a81be2dae` | succeeded | 1 | 2026-09-27T15:00:50.079+00:00 |
| minimax | `webchat-988ce808940f5f529a7da4242878f1e8` | succeeded | 1 | 2026-09-27T15:03:39.180+00:00 |
| gemini | `webchat-04d526dcaaa857fd8958eb2d2749887b` | succeeded | 1 | 2026-09-27T15:25:37.746+00:00 |
| codex | `webchat-c96d2c7fba4452dc8ad2cbb5fc65e875` | succeeded | 1 | 2026-09-27T15:26:49.507+00:00 |
| gemini | `webchat-2acc32a044d75285b1261d348a2e00dc` | succeeded | 1 | 2026-09-27T15:27:27.713+00:00 |
| minimax | `webchat-7cc70a31b3d6542b9899e5dd5a4876c2` | succeeded | 1 | 2026-09-27T15:29:09.015+00:00 |

The initial Gemini/MiniMax tasks were real code/protocol critiques. Their model opinions are retained in chat as execution evidence, not treated as validation of correctness; deterministic tests validate those invariants. The later latency tasks returned checked arithmetic. The initial API preflight, before the affected processes were fully deployed, returned no task ID and is not counted as a successful dispatch. Task `webchat-04d526dcaaa857fd8958eb2d2749887b` was queued before the recovery/deployment maintenance window; its long wait is explicit in the journal. It was retained through maintenance and completed automatically when dispatch resumed. The three primary rows above are fresh tasks submitted after deployment activation.

Only `svc-webchat` and `svc-job-runner` were restarted for this work. Each controlled restart recorded the other service screen identities and verified they were unchanged. Subsequent unrelated service activity is outside these restart operations.

- 2026-09-27T14:55:50.496627+00:00: `svc-webchat`, `svc-job-runner`; other checked service identities unchanged: `True`.
- 2026-09-27T14:59:18.414389+00:00: `svc-webchat`, `svc-job-runner`; other checked service identities unchanged: `True`.
- 2026-09-27T15:00:21.094231+00:00: `svc-webchat`, `svc-job-runner`; other checked service identities unchanged: `True`.
- 2026-09-27T15:09:09.080461+00:00: `svc-job-runner`; other checked service identities unchanged: `True`.
- 2026-09-27T15:25:38.006313+00:00: `svc-webchat`, `svc-job-runner`; other checked service identities unchanged: `True`.
- 2026-09-27T15:30:51.703449+00:00: `svc-webchat`, `svc-job-runner`; other checked service identities unchanged: `True`.
- 2026-09-27T15:00:42.294+00:00: authenticated history recheck of 4 saved task results: all original answers present exactly once.
- 2026-09-27T15:02:00.189+00:00: authenticated history recheck of 5 saved task results: all original answers present exactly once.
- 2026-09-27T15:04:49.150+00:00: authenticated history recheck of 6 saved task results: all original answers present exactly once.
- 2026-09-27T15:26:12.987+00:00: authenticated history recheck of 7 saved task results: all original answers present exactly once.
- 2026-09-27T15:29:49.538+00:00: authenticated history recheck of 10 saved task results: all original answers present exactly once.
- 2026-09-27T15:31:19.302+00:00: authenticated history recheck of 10 saved task results: all original answers present exactly once.

## Reproduce and inspect locally

`python3 webchat/live_dispatch_proof.py submit` sends three new real worker tasks through the authenticated chat API. `verify` checks saved message IDs and exact answer content; `refill` submits a fresh task after restart. The harness reads the password locally into memory and never prints credentials, cookies, CSRF values, or API keys.

Deployment code and data roots plus source hashes are recorded in `state/dispatch-deployment-0927.json`. Private raw receipts: `state/dispatch-proof-0927.json`, `state/dispatch-restarts-0927.json`, `state/queue.jsonl`, and `state/task-runs/<task-id>/RESULT.md`. Model transport receipts are in `model-runs.jsonl` and the existing metering journals. Runtime receipts, task logs, sessions and credentials remain outside Git.

The code is committed locally on the new draft branch in `../workspaces/webbob-dispatch-0927-service`. The two affected launchers read `state/dispatch-code-root` and execute that tested checkout using the existing queue, logs, credentials and chat sessions. This isolates service code from concurrent edits and branch switches in the shared checkout. The deployed checkout itself is protected by the worker sandbox. No merge, push, force-push, undraft, or remote PR operation was performed.
