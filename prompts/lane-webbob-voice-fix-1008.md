# lane-webbob-voice-fix-1008

You are Codex on Jeff's Mac Mini. Fix Web Bob live two-way voice so it clears its own offline review bar. Do NOT use Grok/xAI. No force-push. No Jeff notify/text. No real phone calls or live audio testing without Jeff present. Do NOT deploy.

## Context (2026-09-28 ~10:08 CT)
- Live Web Bob remains `a777736` (integrate tip).
- Texting tip `1ca5e12` (draft PR #21) is offline-green but DEPLOY BLOCKER: Gemini HTTP 402 + MiniMax empty/timeout → NOT_BOTH_PASS. Do not touch texting deploy.
- Voice is FAIL on `WEBBOB-VOICE-MINIMAX-0927.md`. Fix bugs/tests offline this tick. Skip LIVE Gemini+MiniMax for now if those APIs are still dead; document SKIPPED_LIVE_REVIEWS with reason rather than spinning.

## Bugs to fix (from WEBBOB-VOICE-MINIMAX-0927.md)
1. BUG-1 — webchat/app.py IndexError: `new_messages[0]` without empty check.
2. BUG-2 — webchat/app.py message-timeout regression: `reply_id`-filtered lookup must fall back to `messages[-1]` when reply_id absent/stale.
3. BUG-3 — webchat/app.py KeyError: `source["voice_order"]` → use `.get()`.
4. SEC-1 — voice endpoints validate CSRF like `submit()`; add `test_voice_csrf_required`.
5. SEC-2 — rate-limit ephemeral voice-token creation per user/session.
6. SEC-3 — do not leak architecture in voice RequestError messages; use a generic message.

## Tests to add
TEST-1 concurrent voice+text race; TEST-2 45s abandoned-tab lease recovery; TEST-3 token expiry mid-call; TEST-4 barge-in interrupt + retry transcript marking; TEST-5 Safari AudioContext suspension; TEST-6 voice call started while a chat reply is still queued. Keep existing suites green.

## Worktree
Use/create `workspaces/webbob-voice-1008` on branch `draft/webbob-voice-fix-1008` from `origin/draft/webbob-voice-0927` if that exists, else from `origin/draft/webbob-clean-0927`. Prefer the existing voice draft tip. Regular push only; never force-push. Update or open a draft PR on rupret007/bob-brain (voice).

## Stop
Write `conductor/reviews/VOICE-FIXED-1008.md` with tip SHA, bugs fixed, test counts, and LIVE review status (BOTH_PASS or SKIPPED_LIVE_REVIEWS + reason). Print tip SHA and RESULT. No deploy.
