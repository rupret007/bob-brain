# Web Bob "run every resource at max" — gap audit (2026-09-27)

Scope: does Web Bob route chat + queued task work so codex, claude, cursor-agent,
gemini, minimax and the local mini CPU are all used for what they're best at, run
in parallel across idle workers, get refilled from the queue, respect usage caps,
and fail over completely? Read-only audit; no code changed (Codex owns
`wt-webbob-integrate`).

Baseline for "at max" is Web Bob's own spec in `WEBCHAT-READY.md:200-201` (03:42
"Max mode = divide and conquer") and `:163-167` (usage-cap tiering). Findings below
are graded against that spec, with file:line evidence from the current tree.

## What already works (so fixes below don't re-litigate it)
- Idle-lane refill is fast: `web_dispatch.tick()` runs every job-runner cycle
  (`services/job-runner.sh:12` → 5s loop) and claims one task per ready lane
  (`services/web_dispatch.py:88-100`) — well under the spec's 5-minute bar.
- Council (`services/council.py:98-103`) does fan out to all 5 members concurrently
  via `ThreadPoolExecutor` — this is the one place true parallel-across-providers
  exists.
- MiniMax has a real, enforced hard cap checked at reservation time
  (`services/budget.py:47-48`, `webchat/billing.py:2-7`).

## Ranked gaps

### 1. There is no "max mode" fan-out — one Jeff goal never becomes parallel work across idle lanes
**Where:** `webchat/task_dispatch.py:47-83` (`submit_task`), `state/task_queue.py:81-99` (`enqueue`)
**Gap:** The whole task pipeline is 1 request → 1 queue row → 1 worker
(`worker_name(worker)` picks exactly one lane, or `"auto"` for the dispatcher to
pick exactly one lane). There is no code path that takes a single goal, splits it
into independent parts, and enqueues one row per idle lane the way
`WEBCHAT-READY.md:201` describes ("split the goal into independent parts and run
EVERY available non-Grok resource at once... Council vote merges results"). The
only fan-out primitive that exists is `council.py`, and it only runs when Jeff (or
Web Bob) explicitly types `run council: ...` (`webchat/job_queue.py:21-22,73-81`) —
never automatically for a "go to the max" request, and never for coding goals
(council members never execute code, only propose/critique text).
**Effect:** Even when codex, cursor, gemini and minimax are all idle, a single
"go to the max on X" chat message can only ever occupy one worker at a time
through the normal task queue; Jeff has to know to say `run council:` to get
parallelism, and even then it's advisory text, not decomposed build work.
**Fix:** Add a `submit_max_task` path: recognize a "go to the max" / "max mode"
phrase in `task_dispatch.parse_work`, require the caller to supply (or an LLM to
draft) N independent sub-prompts, and call `task_queue.enqueue` once per idle lane
with `requested_worker` pinned to each lane instead of `"auto"`. Record a
`group_id` on each row so `reconcile_tasks` can merge results once all rows in the
group reach a terminal state.
**Test:** `services/test_dispatch.py` — add
`test_max_mode_enqueues_one_row_per_idle_lane_with_shared_group_id`: seed
`lanes.refresh()`-equivalent health as ready for codex/cursor/gemini/minimax,
submit one "go to the max: ..." request, assert 4 queue rows exist with distinct
`requested_worker` and identical `group_id`, then assert `reconcile_tasks` posts a
single merged reply only after all 4 rows are terminal.

### 2. Claude has zero failover coverage in chat — in either direction
**Where:** `webchat/failover.py:14` (`ORDER = ("codex", "cursor", "gemini", "minimax")`),
`webchat/providers.py:443-450` (`route_order`)
**Gap:** `ORDER` (the automatic chat failover chain) never contains `"claude"`, so
a casual chat message can never reach Claude no matter how many other providers
are down — confirmed by design intent at `webchat/task_dispatch.py:21` ("No
automatic Claude"), but the flip side isn't intentional: `route_order` returns the
literal 1-tuple `("claude",)` when `conversation["preferred_provider"] == "claude"`
(`providers.py:444-445`). Look at `reply()`'s loop (`providers.py:461-525`): with a
1-element `order`, the moment Claude raises any `ProviderError`, the `while`
loop exits and `AllDown` is raised — there is no tail of other providers to fall
back to, unlike every other route which tries up to 4 providers.
**Effect:** The one path where Jeff explicitly asks for Claude is also the only
path with *no* resilience at all — a single Claude hiccup (rate limit, CLI crash)
fails the whole request instead of degrading to Codex/Cursor/Gemini/MiniMax the
way every other message does.
**Fix:** In `route_order`, when `preferred_provider == "claude"`, return
`("claude", *ORDER)` instead of `("claude",)` so an explicit Claude pick still
degrades gracefully; keep automatic (`"auto"`) messages excluded from Claude per
existing intent.
**Test:** `webchat/test_failover.py` — add
`test_explicit_claude_preference_falls_back_to_order_on_failure`: set
`conversation["preferred_provider"] = "claude"`, force Claude to raise via
`BOB_WEBCHAT_FORCE_FAIL=claude` (pattern already used in
`test_failover.py`/`providers.drill`), call `reply()`, and assert it succeeds via
the next healthy provider in `ORDER` rather than raising `AllDown`.

### 3. Background task queue serializes gemini/minimax to one job each, even though they're HTTP APIs that can run concurrently
**Where:** `state/task_queue.py:102-121` (`claim`), contrast with
`webchat/failover.py:172-181` (`Circuit.acquire`, which explicitly says "HTTP APIs
allow concurrent chats" and only serializes CLI/interactive lanes)
**Gap:** `claim()` refuses to hand out a second row to a worker if
`any(r["status"] in ACTIVE and r["worker"] == worker for r in rows.values())` —
this applies uniformly to codex/cursor (correctly, they hold an exclusive local
git worktree + screen session) **and** to gemini/minimax (incorrectly — they are
stateless API calls with no shared local resource, and the codebase already knows
this per the `Circuit.acquire` comment above).
**Effect:** If three independent analysis tasks are queued for `gemini`, only one
runs at a time even though Gemini/MiniMax have no local contention and plenty of
rate-limit headroom most of the time — directly against "run every idle worker in
parallel to the max" for the two lanes best suited to concurrency.
**Fix:** In `claim()`, replace the single boolean `any(...)` gate with a
per-worker concurrency limit: keep it at 1 for `codex`/`cursor`/`claude` (CLI/plan
lanes) but allow up to e.g. 3 concurrent `ACTIVE` rows for `gemini`/`minimax`,
gated additionally by `budget.totals(lane)` headroom so concurrency can't blow
through the cap faster than the reservation check catches it.
**Test:** `services/test_dispatch.py` — add
`test_claim_allows_concurrent_gemini_tasks_but_serializes_codex`: enqueue 3
`gemini` rows and 3 `codex` rows, call `task_queue.claim` repeatedly, assert more
than one `gemini` row reaches `ACTIVE` simultaneously while at most one `codex`
row does.

### 4. No usage-cap tiering (70/85/95%) and no "shift work to headroom" — spec'd but absent; Gemini has no cap at all
**Where:** `services/budget.py:11-14` (`LANES`, `RATES` — only `minimax`/`gemini`
priced), `:47-48` (cap check only for `lane == "minimax"`); `services/lanes.py:65-67`
(`refresh()` only marks a lane `budget_exhausted` for `minimax`)
**Gap:** `WEBCHAT-READY.md:167` calls for "Warn at 70%, slow down at 85%, hard
stop at 95% of any cap; router shifts work to resources with headroom." None of
that exists: there's a single hard stop for MiniMax only
(`budget.reserve:47`), no warning tier, and Gemini — priced identically to
MiniMax in `RATES` and metered per-call in the same ledger — has **no cap
enforced anywhere**, so it can run unbounded while MiniMax silently stops at
$48/$59. Codex/Cursor/Claude have no usage accounting against their plan limits
at all (`providers.spend()` returns `"billing": "plan; webchat dollar usage
unavailable"` for them, `providers.py:548`), so nothing can warn before a plan
limit is hit.
**Effect:** Gemini is the one lane that can genuinely run away in cost with zero
guardrail; MiniMax has a guardrail but no early warning, so it goes from "fine"
to "hard down" with no graceful degradation; and there's no mechanism to route
work away from a lane approaching its limit toward one with headroom, so "usage
caps respected" is only true for one of five lanes, and only the abruptest way.
**Fix:** Add a `GEMINI_CAP_USD` to `services/budget.py` mirroring the MiniMax
check in `reserve()`; add a `lanes.refresh()` state `budget_warning` at 70%/85% of
`CAP_USD` (both lanes) that `web_dispatch.tick()` treats as still-ready but logs,
and a `budget_exhausted` state at 95%/100% that `tick()` skips — then in `tick()`,
when a lane is skipped for budget, prefer an alternate lane of the same kind
(e.g. minimax↔gemini for analysis) before giving up the tick's claim for that
task.
**Test:** `services/test_council.py` or a new `services/test_budget.py` —
`test_lane_state_warns_at_70_and_stops_at_95_percent_of_cap`: seed the ledger with
reservations at 71% and 96% of a fake cap, call `lanes.refresh()`, assert state is
`budget_warning` then `budget_exhausted` respectively, and that `tick()` still
claims from the warning-state lane but not the exhausted one.

### 5. Background auto-routing checks lanes in a fixed order, not by task fit — Claude is always tried last
**Where:** `services/web_dispatch.py:88` — `for lane in ("cursor", "codex", "gemini", "minimax", "claude"):`
**Gap:** For an `"auto"`-worker analysis task, whichever lane appears earliest in
this hardcoded tuple and is `ready` claims the row (`task_queue.claim`, first
match wins by `created_at` order within a lane, but *lanes* are tried in this
fixed sequence every tick). Claude is always last, so on a tick where cursor and
codex are both idle and ready, an analysis-only task that would suit Claude's
"review/plan" strength (per Web Bob's own design division of labor,
`WEBCHAT-READY.md:201`) instead goes to whichever generalist CLI happened to be
first in the tuple — not matched to capability, just position.
**Effect:** "Does each provider get used for what it's best at" is only true by
accident for auto-routed background tasks; Claude in particular is structurally
starved of auto-assigned work since it's checked last and is also the most
restricted lane (`lanes.py:154-156` only allows `review`/`council-critique`/
`smoke`/`small-review` purposes for Claude).
**Fix:** Replace the fixed tuple with capability-aware ordering: keep
coding-kind tasks restricted to `codex`/`cursor` as today, but for
`kind == "analysis"` auto tasks, prefer `claude` first (it's the cheapest/fastest
critique lane and explicitly designed for this), then `gemini`/`minimax`, and
only fall through to cursor/codex if those are unavailable — i.e. route by task
`kind` instead of by a single lane-priority tuple.
**Test:** `services/test_dispatch.py` —
`test_auto_analysis_task_prefers_claude_when_multiple_lanes_ready`: mark
cursor/codex/gemini/minimax/claude all `ready` in `lanes.refresh()`'s output,
enqueue one `kind="analysis"`, `requested_worker="auto"` row, call `tick()`,
assert the claimed `worker` is `claude`.

### 6. The local "mini CPU" resource from the design spec doesn't exist as a worker
**Where:** `state/task_queue.py:12` (`WORKERS = ("codex", "claude", "cursor", "gemini", "minimax")`),
`webchat/mini_tools.py:32-63` (`parse_tool`/`command`)
**Gap:** `WEBCHAT-READY.md:164,201` explicitly lists "mini CPU" as one of the six
resources to run at max ("local mini CPU (tests/drills)"), alongside the five
model lanes. It has no representation in `task_queue.WORKERS`, so it can never be
`requested_worker`, never appears in `lanes.refresh()`, and never gets claimed or
refilled by `web_dispatch.tick()`. The only "mini CPU" surface that exists is
`mini_tools.py`, which handles a short allowlist of synchronous, ad-hoc shell
commands typed directly by Jeff (git status, `df -h`, etc.) — it's a chat command
handler, not a queueable worker that can run tests/drills as background jobs
competing for/filling idle capacity like the other five.
**Effect:** One of the six resources the spec says to run at max is entirely
absent from the scheduler; local test/drill work Jeff wants dispatched the same
way as a Codex or Gemini job has no path to get queued, claimed, or shown in the
lane board next to the other five.
**Fix:** Add `"mini"` to `task_queue.WORKERS`, teach `dispatch_worker.execute` a
branch for `row["worker"] == "mini"` that runs the project's test suite (e.g.
`services/test_services.py` / `webchat/test_webchat.py`) or a named drill script
locally instead of calling `lanes.ask`, and add `"mini"` to the lane list in
`services/web_dispatch.py:88` and `services/lanes.py:LANES` (with `state` always
`ready` since it has no login/API dependency).
**Test:** `services/test_dispatch.py` —
`test_mini_worker_runs_local_test_suite_and_reports_result`: enqueue a
`worker="mini", kind="analysis"` row with a prompt naming a test module, run
`dispatch_worker.execute`, assert the row transitions to `succeeded` with the
test runner's real stdout captured as `result` (no model CLI invoked).

## Summary table

| # | Gap | Blocks |
|---|-----|--------|
| 1 | No fan-out for "go to the max" goals | Parallel use of *all* idle workers on one goal |
| 2 | Explicit Claude chat has no failover | Failover coverage for every provider |
| 3 | Gemini/MiniMax capped to 1 concurrent task | Parallel use of idle API workers |
| 4 | No 70/85/95% tiers; Gemini uncapped | Usage caps respected |
| 5 | Fixed lane-check order, Claude always last | Each provider used for its strength |
| 6 | No "mini CPU" worker in the queue | A named resource is entirely unused |
