# lane-webbob-instinct-0810

You are Codex on Jeff's Mac Mini. Build Web Bob Instinct parity. Do NOT use Grok/xAI. No force-push. No Jeff notify/text. Do NOT send any real iMessage/SMS.

## Why
Jeff (2026-09-28 ~8:05 AM CT) wants Web Bob parity to include Instinct: seeing, summarizing, and drafting replies in the Instinct thread, just like Bob. Instinct is Jeff's partnership contact reached through Andrea's iMessage/BlueBubbles path. Weekly Instinct partnership audit routine exists (folder weekly-instinct-partnership-audit).

## Product requirements
1. Read-only Instinct thread status + latest replies (via the same BlueBubbles-first / texts-via-Andrea path Bob uses; never invent messages).
2. Digest Instinct messages: flag bills, security, appointments.
3. Draft replies for Jeff in Web Bob chat.
4. NEVER send any text without Jeff's separate yes in Web Bob (same draft→yes→Andrea/BlueBubbles fence as texting).
5. Gate like every other feature: tests, evals, Gemini+MiniMax BOTH_PASS before any deploy consideration.
6. Deploy is OUT OF ORDER for now — texting must go LIVE first, then gaps/media/voice/UI. This lane only builds + offline READY + LIVE reviews. Do not merge/deploy to production.

## Reuse
- Skill / docs: bob-brain/skills/instinct-with-bob-and-andrea (and any Andrea/BlueBubbles helpers already used by texting tip ce2482c).
- Branch from draft/webbob-clean-0927 tip 1d72c44 (includes texting merge) or from texting tip ce2482c if clean tip is awkward. New branch: draft/webbob-instinct-0810.
- Worktree: /Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-instinct-0810

## Deliverables
1. Implement Instinct status/digest/draft (no send without yes).
2. Tests + evals covering: read/digest/draft; send fence (refuse without yes); no auto-reply to Instinct.
3. Write conductor/reviews/INSTINCT-FIXED-0810.md (tip SHA, test counts).
4. Offline READY marker INSTINCT-READY-0810.md when tests/evals green.
5. Launch/request LIVE Gemini + MiniMax reviews; write LIVE-* markers. BOTH_PASS → INSTINCT-LIVE-0810.md with GATE line. Do not deploy.
6. Draft PR only (rupret007/bob-brain), never merge to clean/prod this tick.

## Stop
Stop when INSTINCT-FIXED-0810.md exists and either INSTINCT-READY-0810.md is written or a clear BLOCKER file INSTINCT-BLOCKER-0810.md explains what's missing. Print tip SHA and marker paths.
