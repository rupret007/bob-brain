# lane-webbob-gaps-deploy-queued-0916 (QUEUED — do not launch until texting is LIVE)

You are Codex on Jeff's Mac Mini. Deploy Web Bob "gaps" (memory write, web research, screenshot hardening) — but ONLY after texting is confirmed LIVE. Do NOT use Grok/xAI. No force-push. No Jeff notify/text.

## Gate — check this first, every time this lane is picked up
1. Read `conductor/reviews/LOOP-RUN-*-SUMMARY.md` (latest by filename) and confirm `/api/version` tip matches a texting-LIVE state (texting shows `LIVE`, not `FAIL_OR_ROLLBACK` or `HOLD`, in the feature table).
2. If texting is not LIVE: do nothing. Write `conductor/reviews/GAPS-DEPLOY-HOLD-<timestamp>.md` stating texting is not yet LIVE and stop. Do not deploy.
3. If texting is LIVE: proceed below.

## What ships
Branch `draft/webbob-gaps-1725`, tip `70d59e3` (or latest tip on that branch if it has moved — re-verify LIVE Gemini+MiniMax BOTH_PASS on whatever tip you actually deploy, do not reuse a stale review).
- `append_profile_memory` — durable "remember that…" write-back to `bob-brain/memory/profile.md`, fcntl-locked + atomic write (`GAPS-FIXED-2143.md`).
- `web_search()` / `format_web_search_reply()` — read-only web research tool.
- `capture_screenshot()` — AppleScript-injection-hardened, macOS-gated (`GAPS-PROGRESS-1841.md`).

## Before deploying
1. Rebase/merge this branch onto whatever SHA is currently live (texting's new tip), not onto the stale `a777736` base.
2. Re-run full webchat + services test suites on the rebased tip.
3. Request fresh LIVE Gemini + MiniMax reviews on the rebased tip (do not reuse the `e62b6e3`/`70d59e3` reviews — they were against a different base).
4. Only deploy on BOTH_PASS. Same deploy-guard/rollback pattern as `deploy_texting_0810.py` — verify rollback path before and after.

## Stop
Stop after either: (a) HOLD marker written because texting isn't LIVE yet, or (b) `GAPS-DEPLOY-RESULT-<timestamp>.md` with LIVE/FAIL_OR_ROLLBACK outcome. Print tip SHA and result.
