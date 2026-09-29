# lane-webbob-instinct-deploy-queued-0916 (QUEUED — do not launch until UI is confirmed LIVE or explicitly cleared)

You are Codex on Jeff's Mac Mini. Deploy Web Bob Instinct (read/digest/draft, no auto-send) — last in the fixed deploy order. Do NOT use Grok/xAI. No force-push. No Jeff notify/text. No real iMessage/SMS send under any circumstance — this feature never sends.

## Gate — check this first, every time this lane is picked up
1. Confirm texting, gaps, media, voice, and UI are all LIVE (check each feature's `*-DEPLOY-RESULT-*.md` and current `/api/version`). Instinct is explicitly last.
2. If any earlier item is not LIVE: write `conductor/reviews/INSTINCT-DEPLOY-HOLD-<timestamp>.md` naming which item is still blocking, and stop.
3. If all five are LIVE: proceed below.

## What ships
Branch `draft/webbob-instinct-0810`, tip `c51860c` (or latest on that branch — re-verify on whatever you actually deploy):
- Read-only Instinct thread status + latest replies via the same BlueBubbles-first path texting uses.
- Digest: flags bills, security, appointments.
- Draft replies in Web Bob chat only.
- Hard send-fence: never sends without Jeff's separate yes in Web Bob, same draft→yes→Andrea/BlueBubbles pattern as texting.
- Already offline READY (411 webchat + 131 services tests, 31 Instinct tests, 22/22 evals) and LIVE Gemini+MiniMax BOTH_PASS (`INSTINCT-READY-0810.md`, `INSTINCT-LIVE-0810.md`), draft PR #19.

## Before deploying
1. Rebase onto the current live SHA (post-UI), not the stale `1d72c44` base.
2. Re-run tests/evals on the rebased tip; re-request LIVE Gemini + MiniMax if the base moved meaningfully.
3. Explicitly re-verify the send-fence test still passes post-rebase (refuse-without-yes, no auto-reply to Instinct) — this is the one irreversible-adjacent behavior in the whole matrix, treat it with the same care as texting's send gate.

## Stop
Stop after either the HOLD marker or `INSTINCT-DEPLOY-RESULT-<timestamp>.md` with outcome. Print tip SHA and result.
