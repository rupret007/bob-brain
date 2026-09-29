VERIFIED-ALREADY-FIXED — Web Bob dispatcher reliability + max-mode fan-out (rows 5-6), 2026-09-28.

Worktree: `workspaces/webbob-maxmode-1008`, branch `draft/webbob-maxmode-reliability-1008`.
Tip SHA: `2b6204aebe77318150bed9723bb7825d0f5b1819` (== `origin/draft/webbob-clean-0927` tip; branch has zero commits ahead — nothing to diff or push).

## What this lane found

`conductor/reviews/WEBBOB-PARITY-MATRIX.md` rows 5-6 cite `WEBBOB-MAX-GAPS-0927.md` (dated
2026-09-27) as evidence that reliability + max-mode fan-out are **MISSING**. That audit is now
stale: `draft/webbob-maxmode-0927` (`fce1d5a`, "Add durable Web Bob max-mode fan-out, capacity
routing and result merge" at `7d5615a`) already built every fix the audit called for, and
`draft/webbob-clean-0927` — this lane's actual base, confirmed via `git merge-base` to be a
strict descendant of `webbob-maxmode-0927` — already carries all of it forward. No divergent work
was needed; this lane's three goals were already closed on the assigned base branch before it
started.

Verified in the current tree (not just present — exercised end-to-end and passing):

### Goal 1 — auto-routed analysis tasks respect model fit (gap #5: "Claude always tried last")
- `state/task_queue.py:worker_order("analysis")` returns
  `("claude", "gemini", "minimax", "codex", "cursor")` — Claude first, not the old hardcoded
  `("cursor", "codex", "gemini", "minimax", "claude")` tuple the audit flagged.
- `services/web_dispatch.py:candidates()` consumes that kind-aware order (not a fixed lane loop)
  when `requested_worker == "auto"`.
- Proven live at the scheduler entry point (not just the helper) by
  `services/test_dispatch.py::test_auto_analysis_task_prefers_claude_when_multiple_lanes_ready` —
  marks every lane `ready`, calls the real `web_dispatch.tick()`, asserts the claimed worker is
  `claude`. Pass.

### Goal 2 — queueable "mini CPU" / local-test worker (gap #6)
- `state/task_queue.py:WORKERS = (*MODEL_WORKERS, "mini")` — mini is a first-class queue worker.
- `services/mini_worker.py` runs a named `services/test_*.py` / `webchat/test_*.py` suite via
  `python -m unittest` in an isolated tmp `BOB_ROOT` with no model CLI/API call.
- `services/dispatch_worker.py:execute()` branches on `row["worker"] == "mini"` to call
  `mini_worker.execute(row)` instead of `lanes.ask`.
- `services/lanes.py:refresh()` and `LANES = task_queue.WORKERS` already include `mini`, defaulting
  it to `state: ready` (no login/API dependency), so `web_dispatch.tick()` claims and refills it
  like every other lane.
- Proven by `services/test_dispatch.py::test_mini_worker_runs_local_test_suite_and_reports_result`
  — enqueues a `worker="mini"` row, runs the real `dispatch_worker.execute`, asserts the row
  succeeds with the actual `unittest` stdout captured and confirms no model `ask()` call fired.
  Pass.

### Goal 3 — chat-triggered "go to the max" fan-out (gap #1)
- `webchat/max_mode.py`: `MAX_MODE` regex recognizes "max mode", "go to the max", "go all out";
  `plan()` builds 2-24 independent per-worker packages (explicit `[worker]` blocks or the standing
  5-role + mini split); `enqueue()` writes one `task_queue` row per package sharing a `group_id`
  (via `group_id()`/`uuid5`) and the existing `group_size`/`group_index`/`group_goal` fields; no
  new orchestrator, reuses `task_queue.enqueue`.
- `webchat/task_dispatch.py:parse_work()` matches the max-mode phrase and routes
  `worker="max"`; `submit_task()`/`submit_max_task()` call `max_mode.plan()` and save one
  `dispatch_intent` with `subtasks`; `reconcile_tasks()`/`reconcile_groups()` merge results into a
  single assistant message only once every row in the group reaches a terminal state — the
  once-only confirmation/result receipt contract (`dispatch_receipts.verify_saved_receipt`,
  message-id dedup by `uuid5(group + ":result")`) is unchanged and still covered.
- Proven end-to-end through the real chat surface (`self.chat.submit`, not a unit stub) by
  `webchat/test_dispatch.py`: `test_max_mode_enqueues_one_row_per_idle_lane_with_shared_group_id`,
  `test_max_mode_explicit_packages_and_recovery_from_partial_enqueue`,
  `test_max_mode_delivery_ack_crash_posts_one_merged_answer`,
  `test_max_mode_chat_save_failure_keeps_every_result_pending`,
  `test_max_mode_rejects_grok_and_keeps_code_packages_independent`,
  `test_max_mode_api_file_package_queues_a_repository_report`. All pass. Regular (non-max) receipt
  tests (`test_natural_requests_have_short_server_confirmed_receipts`,
  `test_duplicate_request_creates_one_task`, etc.) also pass — max-mode phrase recognition did not
  regress ordinary once-only confirmation.

Bonus: the same base also already closes the two WEBBOB-MAX-GAPS-0927.md items this lane wasn't
scoped to fix — gap #3 (`services/test_dispatch.py::test_claim_allows_concurrent_gemini_tasks_but_serializes_codex`,
gemini/minimax now run up to `capacity()` concurrent claims instead of 1) and gap #4
(`test_budget_warning_runs_and_exhausted_lane_shifts_to_headroom`, 70/85/95% tiering with
Gemini capped same as MiniMax). Not verified further since out of this lane's scope (rows 5-6
Goals 1-3 only); noted for the record.

## Code changes made by this lane
None. No diff exists between this branch and its base (`git status` clean, `git log` shows zero
commits ahead of `origin/draft/webbob-clean-0927`). The three goals in the lane prompt were
already fully implemented and tested on the assigned base before this lane ran. No draft PR was
opened — there is nothing to review or merge.

## Test counts (full suite runs, this tip, this pass)
- `services/`: `python3 -m unittest discover -p "test_*.py"` — **131 tests, 1 failure** (pre-existing,
  see below).
- `webchat/`: `python3 -m unittest discover -p "test_*.py"` — **389 tests, 1 failure, 1 skip**
  (pre-existing, see below).
- All targeted rows-5/6 tests named above: pass, individually re-run.

### Pre-existing failures (not introduced by this lane; out of rows 5-6 scope)
Both are the same root cause, environment-only, not a production bug:
- `services/test_api_workers.py::test_frozen_turn_one_reaches_both_api_transports_and_delivers_reports`
- `webchat/test_integrate_2057.py::PinnedDeploymentAssignments::test_nested_tracked_code_uses_its_git_root_with_pins_to_the_running_code`

Root cause: both fixtures build `self.root = Path(tempfile.TemporaryDirectory().name)` **without**
calling `.resolve()`. On this macOS host, `/var` is a symlink to `/private/var`, so
`tempfile`'s raw path (`/var/folders/...`) diverges from the same path after production code calls
`Path.resolve(strict=True)` (`/private/var/folders/...`) — e.g. `webchat/worker_assignment.py:
deployed_project_context()` and the analogous check in `test_api_workers.py`. Confirmed by manual
repro: the assertion fails purely on `/private/var/...` vs `/var/...` path-object inequality, not
on any behavioral difference. This is a latent test-fixture gap (missing `.resolve()` on the tmp
root) that predates this lane, is unrelated to auto-routing/mini-worker/max-mode, and reproduces
identically on the unmodified branch tip. Left as-is per this lane's scope (rows 5-6 only); a
systemic fix would touch the shared tmp-root pattern used across many fixture files and belongs to
its own lane.

## Live reviews
Not applicable — no code changed, so no Gemini/MiniMax live review was run.
SKIPPED_LIVE_REVIEWS: no diff to review.

No deploy occurred. No Jeff notify/text was sent. Grok/xAI was not used. No force-push.
