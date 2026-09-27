# Self-improvement round 3 (Cursor lane) — result

Measured 2026-09-27T05:26:00+00:00. Implementation on **`draft/self-improve-r3`** in worktree `worktrees/conductor-self-improve-r3`. **Commits: `e08ec48`, `2c9b7b9` (HEAD `2c9b7b9`).** Live conductor core unchanged (not merged, `last-good` not advanced).

## Fixes (R2 holes 4–5 + council)

| Item | Change | Regression tests |
| --- | --- | --- |
| **Hole 4 — lanes idle, READY backlog** | While `external_webjam_lease` is active, drop WebJam **coding** managed candidates before sort/launch so StoryBoard/AdoptIQ/shelf backlog items are not starved by retried WebJam coding rows. `candidate_rank()` tie-break uses normalized `id` strings. | `test_external_lease_drops_webjam_coding_candidates` |
| **Hole 4 — council / stale jobs blocked Codex/Cursor** | `live_managed_worker()` reserves a lane only when a managed job has a **live screen** (not merely `running` in `jobs.jsonl`). Screen inventory failures **fail closed** (lane treated busy). | `test_stale_running_job_does_not_block_lane_for_council`, `test_live_managed_worker_blocks_lane` |
| **Hole 5 — watchdog PermissionError** | `takeover()` wraps `/tmp/mini-conductor.lock` probe in `PermissionError` handling; returns `False` on deferral; watchdog only `alert("takeover")` on success. | `test_takeover_lock_permission_error_is_graceful` |
| **Council pr161 — synthesize BlockingIOError** | Same lane-reservation fix: stale `running` records no longer block council `ask()` when no worker screen exists (root cause of `svc-council-161.log` codex/cursor BlockingIOError). | Covered by stale/live worker tests above |

## Webchat

**`svc-webchat-failover` is running** (Codex on WEBCHAT-FAILOVER). Per instructions, **`conductor/webchat/` was not edited.** Transient “queued” / missing provider during failover is noted only; failover job owns that path.

## Council critique (Gemini + MiniMax + Claude short; full council)

Transcript: `worktrees/conductor-self-improve-r3/reviews/council-r3/20260927-002222-439020.md` — **synthesized**, all members answered.

**Applied from synthesis:** fail-closed screen discovery, session name matching, takeover deferral without false success alert, extra live-screen block test, simplified `candidate_rank`.

**Rejected:** missing `jobs` import (already via `state`), `NameError` on `stopped` when deferring (early return is correct).

## Verification

| Check | Result |
| --- | --- |
| `python3 -m unittest discover -S services -p 'test_*.py'` (worktree) | **PASS** — 54 tests |
| `python3 bootstrap.py check` (worktree) | **PASS** |
| Live merge / `launchctl` / spend beyond caps | **NOT RUN** |

**Overall: PASS** (draft implementation + tests). **Live activation: PENDING** (Jeff procedure).

## Jeff must do

1. **Activate draft** when ready: check out `draft/self-improve-r3` in `worktrees/conductor-self-improve-r3`, run your harden path (`MAINTENANCE`, tests, advance `last-good`, `start-all.sh`). Not done by this job.
2. **After activation**, confirm scheduling under WebJam test hold: `tail logs/tick.log` should show non-WebJam launches when Codex/Cursor free; WebJam coding stays skipped while `reviews/WEBJAM-TEST-BUILD-SCHEDULER.md` is ACTIVE or `svc-webjam-test` runs.
3. **Watchdog:** after deploy, `logs/watchdog.log` should not show bare `cycle error: PermissionError` on lock probe; deferral should log and continue.

## Not done (by design)

- No merge, undraft, force-push, texts, emails, or `conductor/webchat` edits.
- No change to live `conductor/services/*` on disk until you activate the draft branch.
