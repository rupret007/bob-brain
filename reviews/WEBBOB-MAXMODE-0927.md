# Web Bob max mode — implementation and live proof (2026-09-27)

## Result

One authenticated chat request created six independent tasks. Codex, Cursor,
Claude, Gemini and MiniMax were simultaneously inside their execution calls for
**22.403 seconds**, from **2026-09-27T17:19:17.037+00:00**
to **2026-09-27T17:19:39.440+00:00**. Mini also ran the real local service test suite.
All six tasks succeeded, and the originating conversation received exactly one
combined answer. This is real provider execution, not a council simulation,
forced sleep, injected success, or a mocked API.

A second single-request run independently demonstrated **13.892 seconds**
of five-provider overlap. Both saved answers were re-read through the authenticated
API after subsequent service restarts and remained present exactly once.

Implementation commit: `7d5615a833a3f4396477f6f4062b47951f4a8b00`.
PR base: `draft/webbob-integrate-0927` at `1be30a1c3b068461f2fe2243d6a4e6d4c8e08bca`.

## Ranked gaps addressed

| Audit gap | Implemented behavior | Regression evidence |
|---|---|---|
| 1. One goal used one worker | Max phrases select a saved plan; standing role decomposition or explicit `[worker]` packages create grouped durable queue rows; a completeness barrier prevents partial groups from executing; one deterministic answer merges all terminal results. | Four-ready-lane fan-out, five-provider simultaneous execution, partial enqueue recovery, merged-answer acknowledgement crash/restart. |
| 2. Claude/explicit chat lacked failover | Selected chat provider is tried first, followed by the normal fallback chain. All five background model workers retry on compatible alternatives; failed workers are deprioritized. Ordinary automatic chat retains its existing non-Claude policy. | Forced explicit Claude failure recovers through Codex; every explicitly selected provider recovers; every background model failure routes to another worker. |
| 3. API workers serialized | Gemini and MiniMax have three queue claims and three cross-process execution slots each. CLI and mini capacity remains one. Legacy exclusive lane locks remain respected. | Real slot-lock saturation/release; queue capacity across all six workers; five-model execution barrier test and live proof below. |
| 4. Caps lacked tiers/Gemini ceiling | Both API providers default to a $48 ceiling, with optional lower runtime ceilings. Warn at 70%, reduce API concurrency at 85%, refuse worst-case reservations crossing 95%; shift work to headroom. Observed CLI quota percentages can stop plan lanes at 95%; provider rate-limit cooldowns remain enforced. | Concurrent reservations cannot cross 95% for either API; 71/86/96% health/capacity checks; exhausted lane routes to an available alternative; observed CLI quota/reset check. |
| 5. Fixed-order routing | Route by task kind and headroom: analysis prefers Claude/Gemini/MiniMax, coding stays on Codex/Cursor, local tests use mini. The runner refills each free slot from the queue. | Auto-analysis prefers Claude; coding failover stays on tool workers; a freed Codex lane takes the next queued task. |
| 6. No mini worker | Mini runs an existing named local unittest suite with an isolated data root, stripped credential environment variables, captured real output, and a 300-second timeout. | Real test subprocess succeeds and publishes stdout without calling a model; live mini task below. |

CLI subscription percentages are **unknown unless observed quota data is supplied**
in private `conductor/plan-usage.json`; token counts and estimated dollars are not
represented as plan utilization. This change does not invent missing provider
telemetry. Configured API caps and actual rate-limit responses remain enforced.
The reducer preserves each worker's findings, disagreements and failures in one
answer; it does not claim that a separate synthesis model resolved disagreements.
Coding packages create independent local commits and report them, without
integrating branches or publishing changes.

## Tests

On the exact implementation commit, both the system Python and the deployed
Python 3.14 interpreter passed:

- `python3 -m unittest discover -s services -p 'test_*.py'`: **93 passed**.
- `python3 -m unittest discover -s webchat -p 'test_*.py'`: **139 passed**.
- **232 total**, including the JavaScript quiet-hours check invoked by the suite.
- `git diff --check` and compilation of the added queue/planner/proof/mini modules passed.

Three additional proof-helper regressions pass: select an archived receipt without
submitting new work, reject absent simultaneous-execution observations, and reject
duplicate answers. The final PR suite is **93 service + 142 webchat = 235 tests**.
The preserved primary receipt was verified again by the updated helper at
`2026-09-27T17:33:48.108+00:00`, with the original answer hash and 22.403-second overlap.

The currently deployed descendant also passed **94 service + 144 webchat = 238 tests**
under `/opt/homebrew/bin/python3`, after the concurrent hotfix described below.
Offline tests use isolated roots, real file locks and bounded subprocesses; model
responses are mocked only in offline regression tests.

## Primary live API receipt

- Conversation: `ddb64b85-e439-441e-b287-5b8fde137ca9`.
- Request: `c82ef6db-98f0-4490-958d-5eaf06a0a2b2`.
- Group: `max-6d2993f554085db695b1339897687c79`.
- Accepted: `2026-09-27T17:18:46.516+00:00`.
- All-five-running authenticated `/api/jobs` observation: `2026-09-27T17:19:20.001+00:00`.
- Result message: `22d1d476-8225-5296-9a1b-3e6def553b34`.
- Chat answer saved: `2026-09-27T17:21:10.929+00:00`.
- Answer SHA-256: `f1ee0870882cbc5c4fc52dfe707873353a919b54fb611beedf36b256f2b0eaa5`.
- Reverified exactly once after restarts: `2026-09-27T17:30:39.950+00:00`.

The following times come from durable queue events exposed by `/api/jobs`.
`execution_started_at` is written immediately before the provider/local test call,
after workspace preparation; it is separate from claim and worker-start timestamps.

| Worker | Task ID | Claimed (UTC) | Execution started (UTC) | Finished (UTC) | Attempts |
|---|---|---|---|---|---|
| codex | `webchat-8aa10ddfcba8525b9f9def8e31e4a317` | 2026-09-27T17:18:56.209+00:00 | 2026-09-27T17:19:00.966+00:00 | 2026-09-27T17:21:10.255+00:00 | 1 |
| cursor | `webchat-86c0629bfebb56949ba976b47f03b3d0` | 2026-09-27T17:18:56.229+00:00 | 2026-09-27T17:18:59.090+00:00 | 2026-09-27T17:19:52.618+00:00 | 1 |
| claude | `webchat-b2d014dade2d5325bb0b68cd876e70fb` | 2026-09-27T17:18:56.258+00:00 | 2026-09-27T17:19:02.894+00:00 | 2026-09-27T17:20:24.970+00:00 | 1 |
| gemini | `webchat-ef0fba3418cd51ffa68f75d77a19cee3` | 2026-09-27T17:18:56.394+00:00 | 2026-09-27T17:19:17.037+00:00 | 2026-09-27T17:19:39.440+00:00 | 1 |
| minimax | `webchat-df8f46f15eaf5eb695f211c752c2f1ad` | 2026-09-27T17:18:56.511+00:00 | 2026-09-27T17:19:06.305+00:00 | 2026-09-27T17:19:48.575+00:00 | 1 |
| mini | `webchat-2e0a6a0952f5508e9cbde7ecad117a5f` | 2026-09-27T17:19:37.309+00:00 | 2026-09-27T17:19:42.782+00:00 | 2026-09-27T17:20:01.045+00:00 | 2 |

Mini's first suite execution reported failure and was retried; its second execution
passed. It was never marked successful from a failed exit code. The five model
subtasks all succeeded on their first attempt. The mini retry is excluded from the
five-provider overlap calculation.

At the captured simultaneous-execution snapshot:

| Worker | State | Worker PID | Execution-start timestamp (UTC) |
|---|---|---|---|
| codex | running | 71653 | 2026-09-27T17:19:00.966+00:00 |
| cursor | running | 71656 | 2026-09-27T17:18:59.090+00:00 |
| claude | running | 71663 | 2026-09-27T17:19:02.894+00:00 |
| gemini | running | 71677 | 2026-09-27T17:19:17.037+00:00 |
| minimax | running | 71685 | 2026-09-27T17:19:06.305+00:00 |
| mini | running | 71695 | 2026-09-27T17:18:57.374+00:00 |

Overlap is `min(model finished_at) - max(model execution_started_at)`, calculated
from all five distinct model workers; it is not inferred from screen names or
claim times. The positive interval is **22.403 seconds**.

Exact single submitted chat message:

```text
Max mode: Review Web Bob's new parallel task dispatcher. Produce one combined answer covering independent implementation, testing, design, capacity, and failure analyses, with actual local test evidence. Work read-only; do not edit files, push, or open PRs.

Shared evidence: A request saves a durable dispatch intent, expands into independent queue rows with a shared group_id and expected group_size, and starts nothing until every group row exists. Each claim has a unique token and a 90-second renewable lease. CLI capacity is 1 each; Gemini and MiniMax capacity is 3 each. A provider error records the failed worker and retries an untried compatible worker; coding stays on Codex/Cursor. Budgets include outstanding worst-case reservations; tiers warn at 70%, reduce API concurrency at 85%, and refuse new reservations crossing 95%. Queue results are saved before the single deterministic group answer is saved; delivery acknowledgements follow that chat write. Mini runs a named local test suite without a model call. Analysis outputs and local commits from code packages remain attributable to their worker.

[codex] Read state/task_queue.py and services/web_dispatch.py in the assigned checkout. Audit atomic claims, partial group enqueue recovery, retries, capacity and routing. Cite specific code locations, trace two concrete races, and list the three highest-priority correctness risks. Use 500-700 words and distinguish proven facts from recommendations.
[cursor] Read webchat/task_dispatch.py, webchat/max_mode.py and webchat/test_dispatch.py in the assigned checkout. Audit the group result outbox, duplicate request handling and restart delivery. Cite code locations and propose a concrete regression matrix with at least eight crash/failure cases. Use 500-700 words; do not modify anything.
[claude] Using only the shared evidence, independently critique the design assumptions, separation of responsibilities and acceptance criteria. Evaluate five invariants and specify an observable falsification test for each. Rank the three most consequential risks. Use a focused 400-500 word critique and clearly label unknown implementation details.
[gemini] Using only the shared evidence, calculate maximum concurrency and a capacity model. Assume mean CLI durations Codex 50s, Cursor 40s, Claude 20s; API durations Gemini 12s, MiniMax 30s; Mini tests 5s. Compute per-lane and aggregate hourly throughput at normal capacity and at the 85% API throttle, explain why this is only an upper bound, and analyze five scheduling/starvation scenarios. Give formulas, tables and a detailed 600-800 word analysis.
[minimax] Using only the shared evidence, build a failure/recovery matrix of at least twelve cases spanning lost claims, crashed workers, timed-out provider calls, cap exhaustion, partial enqueue, stale tokens, chat save failure and lost delivery acknowledgements. For each give expected durable state, next action and evidence needed. Finish with the three most useful operational alerts. Use 600-800 words; do not invent observations.
[mini] Run services/test_services.py on the local CPU and return its real test output.
```

The single combined answer begins:

```text
Max mode completed: 6/6 subtasks succeeded.

### Implementation and correctness (codex)

The queue’s claim and fencing logic is sound within its locking protocol, but retry exhaustion and group validation have reproducible correctness gaps. This review covers only the assigned queue/dispatcher subtask. No files were changed, workers launched, commits made, or remote actions taken; Git status remained clean.

**Observed implementation.** In [state/task_queue.py:119](/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webchat-8aa10ddfcba8525b9f9def8e31e4a317/state/task_queue.py:119), `claim()` holds an exclusive queue lock across reading state, checking capacity, selecting a queued row, and appending its claim. Claims receive unique tokens and 90-second leases. `_append()` flushes and fsyncs the journal and parent directory. `transition()` rejects expired leases and mismatched tokens before accepting results or heartbeats.

The group barrier counts rows sharing `group_id` and compares that count with the candidate row’s `group_size` (queue lines 137–138). This prevents a correctly described partial group from starting. However, these two files contain no intent-replay implementation: recovery of missing rows remains dependent on the supplied upstream design.

**Two concrete races.**

1. Two claimants readied for one Codex task contend for the queue lock. A acquires it, sees available capacity, and persists `claimed`. B subsequently reads A’s claim and returns without claiming because Codex’s capacity is occupied. Separately, if A expires and recovery requeues its task,
[excerpt ends; full answer is preserved in the authenticated conversation and private receipt]
```

The response has `provider="max-mode"`, `task_status="succeeded"`, six attributed
subtask receipts and one deterministic message ID. Each member's delivery record
points at that same saved answer. Re-reading the conversation does not duplicate it.

## Additional live evidence

Second independent big request:

- Conversation `7dcba51e-9b8b-4380-9d6f-25256b90d82c`, request `ffb7f15b-03b6-4a91-9e0c-af8f8e5b35d9`.
- Group `max-ba39b2d091535c188bf3b3458d4c8352`; one message `77b090cc-a7bc-570c-8bfd-be181790232f`.
- All five executing at `2026-09-27T17:23:22.909+00:00`.
- Overlap `2026-09-27T17:23:22.228+00:00` through `2026-09-27T17:23:36.120+00:00`,
  **13.892 seconds**.
- Answer SHA-256 `b86ed69c9a39502c3b8a0dca202612b7cef56be33c260c561ff6271aea622441`.
- Re-read after restarts at `2026-09-27T17:30:40.163+00:00`; exactly one successful answer.

A third request, `55f09211-418f-4dcf-84c6-e75b9b1200ff`, completed all six packages and produced
one saved answer `ddc8d703-6b0b-5e56-a548-fa5c8721bc6d`. Cursor was initially occupied by other
work and remained queued until its slot freed; Gemini finished before Cursor
started. That run demonstrates busy-lane queueing/refill, **not** five-way overlap,
and is not used as the simultaneous-execution proof. Its result was verified at
`2026-09-27T17:30:40.393+00:00`.

## Deployment and concurrent-session boundary

After the 232-test pass, this task restarted only `svc-webchat` and
`svc-job-runner`, initially on the implementation checkout. A separate
`lane-webbob-hotfix` session then edited the same checkout and restarted those
services during live capture. Its edits were preserved, not staged into this PR.
A clean copy of `7d5615a` was separately tested with both Python interpreters and
its service process paths were verified at `2026-09-27T17:25:14.634+00:00`.
Closing a screen did not always terminate its service process; process identity
checks caught the surviving old processes instead of claiming the replacement
was live merely from a screen-launch exit status.

The concurrent session subsequently deployed committed hotfix `ed3d689740c28dc1eddd85b19b08ec3da1b78687` at
`/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-integrate-0927-service`. Git ancestry verifies that it contains the complete max-mode
implementation `7d5615a`; it also passes the 238 tests noted above. Both current
code pins point there. That descendant deployment is preserved. The completed
max-mode answers were authenticated and verified again against that deployment.

This task did not restart reviewer, dashboard-updater, watchdog, disk-watch or
webbob-reviewers. Their independent screen identities remained unchanged across
this task's recorded deployments. The other session changed its own readiness
service independently; no claim is made that all concurrent host activity stopped.

No credentials, cookies, CSRF tokens, private runtime receipts or provider keys
were staged. No Grok calls, cap resets, purchases, merges, force pushes or
non-draft PR publication were performed.

## Reproduction and private evidence

The password is read directly into memory from `conductor/webchat/.password`.
`live_maxmode_proof.py` logs only task IDs, states, timestamps and result hashes.
`run` submits one group; `resume` reauthenticates and continues a saved receipt;
`verify` checks the same saved answer without submitting another model request.

```bash
python3 webchat/live_maxmode_proof.py run --root /Users/jeffstory/Documents/bob-overnight-inject
python3 webchat/live_maxmode_proof.py resume --root /Users/jeffstory/Documents/bob-overnight-inject
python3 webchat/live_maxmode_proof.py verify --root /Users/jeffstory/Documents/bob-overnight-inject \
  --receipt /Users/jeffstory/Documents/bob-overnight-inject/conductor/state/webbob-maxmode-proof-0927-initial.json
```

The helper refuses to overwrite an existing run receipt. The three preserved
receipts correspond to separate invocations, never six separate chat submissions
masquerading as a single request. Private files, all outside Git:

- `conductor/state/webbob-maxmode-proof-0927-initial.json` — primary successful overlap proof.
- `conductor/state/webbob-maxmode-proof-0927-before-clean-deployment.json` — second successful overlap proof.
- `conductor/state/webbob-maxmode-proof-0927.json` — busy-Cursor refill run; no five-way overlap claimed.
- `conductor/state/webbob-maxmode-deployment-0927-initial.json` and `webbob-maxmode-deployment-0927.json` — process identities, pins and source hashes.
- `conductor/state/queue.jsonl`, `state/task-runs/<task-id>/RESULT.md`, model ledgers,
  and saved webchat conversation files — durable events and complete results.
