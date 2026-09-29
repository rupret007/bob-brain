# lane-webbob-texting-diagdump-fix-0916

You are Codex on Jeff's Mac Mini. Fix Web Bob texting deploy LIVE replay failure, then redeploy only if gates pass. Do NOT use Grok/xAI. No force-push. No Jeff notify/text.

## Failure (authoritative) — TEXTING-DEPLOY-0810 RESULT: FAIL_OR_ROLLBACK
- Tip `9cfe548` on `draft/webbob-texting-onto-a777736` had LIVE Gemini+MiniMax BOTH_PASS, then deploy attempt2 rolled back to `a777736` (verified).
- Draft PR: https://github.com/rupret007/bob-brain/pull/20
- Evidence: conductor/reviews/WEBBOB-TEXTING-FAIL-0810.md, TEXTING-DEPLOY-0810.md, WEBBOB-TEXTING-DEPLOYMENT-0927-attempt2.json
- Failing check: live replay job `webchat-53ff7beab93c5adaad5c4177ec9b9e7f` (StoryBoard / Cursor worker)
- Fail reason: Answer did not complete the task — claimed bounded fix/local commit but incomplete verification: only shared tests + prepare smoke; did not re-run API or broader project tests to substantiate pass.
- Prior status-dump failure (session b33fac25 turn 3) already FIXED on 9cfe548 (`prior_failure_regression.pass_check: true`). Keep that casual status voice — never regress to raw diagnostic dumps ("model not reported", queue_counts, job-runner internals, semicolon-chained worker inventories).

## Live baseline
- Prod `/api/version` short_sha `a777736` full `a777736b3f0a37c82b0c4c62be8c91117c4c9881` built_at 2026-09-28T09:04:32+00:00
- Work from existing worktree `workspaces/webbob-texting-onto-a777736-0420` on tip `9cfe548` / branch `draft/webbob-texting-onto-a777736` (or successor branch `draft/webbob-texting-diagdump-fix-0916` cut from 9cfe548). Do not invent a parallel orchestrator.

## Goal
1. Fix incomplete-verification / empty-promise worker answers so live-replay coding jobs (esp. StoryBoard-style "bounded fix + tests") cannot claim done without re-running the real API / webchat / services (or project-specific) tests the gate expects. Borrow proven patterns already on integrate a777736 / reply-quality / texting tips — do not invent a new subsystem.
2. Keep casual status voice from 9cfe548 (short natural status; no raw dumps).
3. Re-run the real offline API/webchat/services tests + evals the gate expects on the new tip. Write TEXTING-FIXED-0916.md with tip SHA and counts.
4. Fresh LIVE Gemini + MiniMax reviews on the new tip (attempt slot next free after 0810). BOTH_PASS required. Markers under conductor/reviews/ (e.g. TEXTING-LIVE-0916.md / LIVE-GEMINI-* / LIVE-MINIMAX-*).
5. Merge new tip into `draft/webbob-clean-0927` (regular merge, never force-push). Update draft PR #20 or open a new draft if needed.
6. Redeploy ONE tip with fresh rollback under `rollbacks/webbob-texting-YYYYMMDD-HHMMSS` ONLY if BOTH_PASS + offline tests pass. Adapt deploy_texting_0810.py → deploy_texting_0916.py; evidence WEBBOB-TEXTING-DEPLOYMENT-0927-attempt3.json (next free).
7. Live replay must clear the 0810 incomplete-verification fail AND keep prior status-dump regression green. On failure auto-rollback to a777736 and verify `/api/version`.
8. Write conductor/reviews/TEXTING-DEPLOY-0916.md with RESULT: LIVE_PASS or FAIL_OR_ROLLBACK, tip, draft_pr, live before/after JSON, rollback path.

## Preflight
- Live short_sha is a777736 (or already new tip with LIVE_PASS — then document and stop).
- Do not re-litigate old BOTH_PASS on 9cfe548; that tip failed deploy replay.
- Texting smoke still required.
- Do NOT deploy Instinct/gaps/media/voice/UI.

## Out of scope
Media/gaps/voice/UI/Instinct deploy. No notify. No Grok. No force-push.

## Stop
Stop after TEXTING-DEPLOY-0916.md exists with RESULT line (or after BLOCKER documenting why deploy was not attempted). Print RESULT and live SHA.
