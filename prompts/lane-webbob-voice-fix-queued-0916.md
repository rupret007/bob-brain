# lane-webbob-voice-fix-queued-0916 (QUEUED — do not launch until media is LIVE; fix bugs before this even becomes deploy-eligible)

You are Codex on Jeff's Mac Mini. Fix Web Bob live two-way voice so it clears its own review bar, then hold for deploy order. Do NOT use Grok/xAI. No force-push. No Jeff notify/text. No real phone calls or live audio testing without Jeff present.

## Why this is queued, not deploy-ready
`conductor/reviews/WEBBOB-VOICE-MINIMAX-0927.md` VERDICT: **FAIL** on the current voice diff. This lane fixes that before voice can even be considered for its slot (4th) in the texting→gaps→media→voice→UI→Instinct order.

## Bugs to fix (ranked, from WEBBOB-VOICE-MINIMAX-0927.md)
1. **BUG-1** — `webchat/app.py:339`, IndexError risk: `new_messages[0]` accessed after slicing without checking the list is non-empty.
2. **BUG-2** — `webchat/app.py:253-257`, message-timeout regression: new `reply_id`-filtered lookup silently no-ops instead of falling back to `messages[-1]` when `reply_id` is absent/stale.
3. **BUG-3** — `webchat/app.py:341`, KeyError risk: `source["voice_order"]` accessed without `.get()` fallback.
4. **SEC-1** — voice endpoints must validate CSRF token same as `submit()`; add `test_voice_csrf_required`.
5. **SEC-2** — rate-limit ephemeral voice-token creation per user/session.
6. **SEC-3** — `RequestError(400, "The spoken request was not saved.")` leaks architecture; use a generic message.

## Missing tests to add
TEST-1 (concurrent voice+text race), TEST-2 (45s abandoned-tab lease recovery), TEST-3 (token expiry mid-call), TEST-4 (barge-in interrupt + retry transcript marking), TEST-5 (Safari AudioContext suspension), TEST-6 (voice call started while a chat reply is still queued) — see file for exact scenarios.

## Gate before deploy consideration
1. All 6 bugs/security findings fixed, all 6 missing tests added and green, plus the existing 254+111+18 passing suite still green.
2. Fresh LIVE Gemini + MiniMax reviews on the fixed tip — must be BOTH_PASS, not the prior FAIL.
3. Even on BOTH_PASS: still HOLD for deploy until media is confirmed LIVE (check `MEDIA-DEPLOY-RESULT-*.md`). Write `VOICE-DEPLOY-HOLD-<timestamp>.md` if media isn't live yet.

## Stop
Stop after `VOICE-FIXED-<timestamp>.md` (bug/test summary + tip SHA) and either a LIVE-review BOTH_PASS marker or a documented remaining blocker. Do not deploy this tick regardless of outcome unless media is independently confirmed LIVE. Print tip SHA and result.
