# lane-webbob-media-deploy-queued-0916 (QUEUED — do not launch until gaps is LIVE)

You are Codex on Jeff's Mac Mini. Deploy Web Bob file/image attachments ("media") — but ONLY after gaps is confirmed LIVE (which itself requires texting LIVE first). Do NOT use Grok/xAI. No force-push. No Jeff notify/text.

## Gate — check this first, every time this lane is picked up
1. Confirm the current live tip includes the gaps deploy (check `conductor/reviews/GAPS-DEPLOY-RESULT-*.md` for a LIVE outcome, and cross-check `/api/version`).
2. If gaps is not yet LIVE: write `conductor/reviews/MEDIA-DEPLOY-HOLD-<timestamp>.md` and stop.
3. If gaps is LIVE: proceed below.

## What ships
Branch `draft/webbob-media-0927`, tip `b8aa84a` (or latest tip on that branch — re-verify reviews on whatever you actually deploy):
- Bounded/chunked upload reads with declared `Content-Length` cap (`Handler.read_content`).
- Binary-aware embedded-secret scan (`_reject_embedded_secrets`, latin-1 + UTF-8 replace).
- `PROCESS_SLOTS` leak fix (explicit `acquired` flag, `finally` release).
- Orphan-blob cleanup on metadata write failure (`store_media`).
See `conductor/reviews/MEDIA-FIXED-2205.md` for full detail (292+39 tests passed at that tip).

## Before deploying
1. Rebase onto the current live SHA (post-gaps), not the stale base it was reviewed against.
2. Re-run webchat + `test_chat_media.py` / `test_media_http.py` / `test_media_transport.py` on the rebased tip.
3. Fresh LIVE Gemini + MiniMax reviews on the rebased tip — do not reuse `b8aa84a`'s prior review if the base moved.
4. Note the known remaining risk from `MEDIA-FIXED-2205.md`: slow clients can still block until the 10s connection timeout while filling a declared body — do not treat this as a blocker unless it regresses, but call it out in the deploy result.

## Stop
Stop after either the HOLD marker or `MEDIA-DEPLOY-RESULT-<timestamp>.md` with outcome. Print tip SHA and result.
