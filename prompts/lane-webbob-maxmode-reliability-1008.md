# lane-webbob-maxmode-reliability-1008

You are Claude Code on Jeff's Mac Mini. Close Web Bob dispatcher reliability + "go to the max" fan-out gaps from `conductor/reviews/WEBBOB-PARITY-MATRIX.md` rows 5–6. Do NOT use Grok/xAI. No force-push. No Jeff notify/text. No Web Bob deploy.

## Goal
1. Make auto-routed analysis tasks respect model fit (do not always force Claude last).
2. Add a queueable "mini CPU" / local-test worker path if missing, borrowing existing mini_worker / isolated runner patterns — do not invent a new orchestrator.
3. Chat-triggered "go to the max" / fan-out: one plain-language goal may create a bounded group of jobs across idle lanes (reuse existing `group_id` / `group_size` fields already on job rows). Wire phrase recognition in parse_work / task_dispatch without breaking once-only confirmation receipts.
4. Tests for the new paths; keep webchat+services suites green.

## Worktree
`workspaces/webbob-maxmode-1008` on `draft/webbob-maxmode-reliability-1008` from `origin/draft/webbob-clean-0927` (or existing maxmode draft tip if closer). Draft PR only.

## Stop
Write `conductor/reviews/MAXMODE-FIXED-1008.md` with tip SHA, what changed, test counts. Print RESULT. No deploy. Skip LIVE Gemini/MiniMax if APIs return 402/empty — note SKIPPED_LIVE_REVIEWS.
