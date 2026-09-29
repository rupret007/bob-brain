# Instinct FIXED 0810

Branch: draft/webbob-instinct-0810
Tip SHA: c51860cc36be4c44be722ba8175095b625666c4f
Base: 1d72c44 (includes texting ce2482c)
Worktree: /Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-instinct-0810
Recorded: 2026-09-28T13:28:01+00:00

Tests: 411 webchat passed, 1 optional Playwright skip; 131 services passed; 31 Instinct tests included.
Evals: Instinct 22/22; Bob parity 118/118 (includes Instinct).
Static checks: JavaScript checks and Python compilation passed; full branch diff whitespace check passed.
Evidence: /Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-instinct-0810/reviews/INSTINCT-0810-VALIDATION.md

No real iMessage/SMS, Jeff notification, merge, deploy, or live service/pin change. All messaging tests use synthetic loopback fixtures.
DEPLOY: HOLD — out of order; texting must go LIVE first, then gaps/media/voice/UI. This lane is draft-only.

Implemented read-only status/latest replies, bounded bills/security/appointments digest with dated excerpts, and explicit/suggested reply cards.
Reuses BlueBubbles-first reads and the texting draft → separate exact yes → Andrea fence. No auto-reply or routine dispatch.
Exact name or verified GUID mapping; fail closed on unavailable/ambiguous thread. Private thread content never enters model context.

LIVE review update: Gemini + MiniMax BOTH_PASS for c51860cc36be4c44be722ba8175095b625666c4f. See /Users/jeffstory/Documents/bob-overnight-inject/conductor/reviews/INSTINCT-LIVE-0810.md.
Draft PR: https://github.com/rupret007/bob-brain/pull/19
Deployment remains held.
