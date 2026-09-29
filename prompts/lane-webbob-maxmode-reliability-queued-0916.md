# lane-webbob-maxmode-reliability-queued-0916 (QUEUED — draft-only, dispatcher-level, independent of the webchat-feature deploy chain)

You are Codex on Jeff's Mac Mini. Close the dispatcher-reliability gaps identified in the "run every resource at max" audit. Do NOT use Grok/xAI. No force-push. No Jeff notify/text. No deploy — this touches `services/` scheduling code, treat any change here with the same care as a live-service change even though it isn't a webchat-feature deploy.

## Why
`conductor/reviews/WEBBOB-MAX-GAPS-0927.md` is a read-only audit (no code changed at the time) against Web Bob's own spec in `WEBCHAT-READY.md:200-201,163-167`. Six ranked gaps, none of which are gated behind the texting→gaps→media→voice→UI→Instinct feature-deploy order — this is dispatcher plumbing, not a chat-facing feature, so it can proceed independently once Jeff wants it.

## Gaps to fix (ranked, from WEBBOB-MAX-GAPS-0927.md — full detail, fix sketch, and test plan already written there for each)
1. **No "max mode" fan-out**: `task_dispatch.submit_task` is 1 request → 1 queue row → 1 worker. Add a `submit_max_task` path recognizing "go to the max"/"max mode" phrasing, enqueueing one row per idle lane with a shared `group_id`, merged by `reconcile_tasks` once all rows are terminal.
2. **Claude has zero failover in chat**: `route_order` returns the literal 1-tuple `("claude",)` for an explicit Claude preference — one Claude hiccup fails the whole request. Return `("claude", *ORDER)` instead.
3. **Gemini/MiniMax serialized to 1 concurrent job** despite being stateless HTTP APIs (`Circuit.acquire`'s own comment says HTTP APIs allow concurrent chats). Replace the uniform `claim()` gate with a per-worker concurrency limit: 1 for codex/cursor/claude, up to ~3 for gemini/minimax, gated by budget headroom.
4. **No 70/85/95% usage-cap tiering; Gemini fully uncapped** despite being priced identically to MiniMax. Add `GEMINI_CAP_USD`, add `budget_warning`/`budget_exhausted` lane states, and have `tick()` prefer an alternate lane of the same kind before giving up a claim.
5. **Fixed lane-check order starves Claude** for auto-routed analysis tasks (`web_dispatch.py:88` always tries `cursor, codex, gemini, minimax, claude` in that order). Route by task `kind`: prefer Claude first for `kind == "analysis"`.
6. **No "mini CPU" worker** in the queue at all, despite being one of six resources the spec names. Add `"mini"` to `task_queue.WORKERS`, teach `dispatch_worker.execute` to run local test suites/drills for it, mark it always `ready`.

## Deliverables
1. Fix each gap with the exact test named in `WEBBOB-MAX-GAPS-0927.md` for it (six named tests across `services/test_dispatch.py` and a new `services/test_budget.py`).
2. Run the full `services/` test suite, not just the new tests — this code is load-bearing for every existing lane.
3. Write `conductor/reviews/MAXMODE-RELIABILITY-FIXED-<timestamp>.md` with tip SHA, which gaps were fixed, and full test counts. Draft PR only, never merge/deploy.

## Stop
Stop when the fixed marker exists. This lane can proceed independently of the webchat feature-deploy order, but do not deploy without a separate explicit go — this is scheduler code that affects every in-flight lane. Print tip SHA and marker path.
