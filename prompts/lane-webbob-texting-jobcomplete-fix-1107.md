# lane-webbob-texting-jobcomplete-fix-1107

You are Codex on Jeff's Mac Mini. Fix Web Bob texting deploy LIVE replay failure (job-completion / MiniMax incomplete deliverable), then redeploy only if gates pass. Do NOT use Grok/xAI. No force-push. No Jeff notify/text.

## Failure (authoritative) — TEXTING-DEPLOY-1035 / TEXTING-DEPLOY-0916 RESULT: FAIL_OR_ROLLBACK
- Tip `1ca5e12` on `draft/webbob-texting-diagdump-fix-0916` (draft PR #21) had fresh LIVE Gemini+MiniMax BOTH_PASS (attempt 3), offline 389 webchat + 139 services + 100/100 evals, clean merge to `draft/webbob-clean-0927` as `1fb1431`, then deploy attempt3 rolled back to live `a777736` (verified local+public).
- Evidence: conductor/reviews/UNBLOCK-1035.md, TEXTING-DEPLOY-1035.md, WEBBOB-TEXTING-FAIL-0916.md, WEBBOB-TEXTING-DEPLOYMENT-0927-attempt3.json, UNBLOCK-1035-after.json
- Failing check: live replay job `webchat-f4b8e359666155c6a06900f02b313c8c` (MiniMax worker, task “Web Bob — Review and regression test-case drafts” for ongoing “Web Bob unblock 1035”)
- Fail reason: Answer did not complete the task — produced architectural findings and investigation commands but **no actual regression test-case drafts** and **no concrete resolution plan**. Substantive task-completion failure (not empty provider / not verdict-parser). Runner observed 8/13 executions; only 5 succeeded before fail; remaining claims revoked; rollback verified.
- Keep prior greens: casual status voice (no raw diagnostic dumps), incomplete-verification regression from 0916, texting smoke, BOTH_PASS review transport fixes from UNBLOCK-1035.

## Live baseline
- Prod `/api/version` short_sha `a777736` full `a777736b3f0a37c82b0c4c62be8c91117c4c9881` built_at 2026-09-28T09:04:32+00:00
- Start from tip `1ca5e12` / branch `draft/webbob-texting-diagdump-fix-0916` in worktree `workspaces/webbob-texting-jobcomplete-1107` on new branch `draft/webbob-texting-jobcomplete-fix-1107`. Do not invent a parallel orchestrator. Borrow proven patterns already on integrate/`a777736` and texting tips.

## Goal
1. Fix MiniMax (and peer) “Review and regression test-case drafts” / analysis coding jobs so live-replay acceptance cannot pass an exploratory-only answer. Require concrete regression test drafts (or equivalent deliverable the gate expects) plus a short actionable unblock plan when the ongoing task names a specific unblock. Prefer tightening worker system/prompt contracts and/or result acceptance that already exists in webchat/services — reuse, do not invent a new subsystem.
2. Keep casual status voice and prior 0810/0916 regressions green.
3. Re-run the real offline API/webchat/services tests + evals the gate expects on the new tip. Write TEXTING-FIXED-1107.md with tip SHA and counts.
4. Fresh LIVE Gemini + MiniMax reviews on the NEW tip (attempt slot next free after 0916 attempt3 → attempt4+). BOTH_PASS required. Markers under conductor/reviews/ (TEXTING-LIVE-1107.md / LIVE-GEMINI-* / LIVE-MINIMAX-*). Reuse fixed review transport from UNBLOCK-1035 (`review_transport_1035.py` / run_texting_reviews_0916.py patterns).
5. Merge new tip into `draft/webbob-clean-0927` (regular merge, never force-push). Update draft PR #21 or open a new draft if needed. Note clean already has `1fb1431` (== tree of 1ca5e12); production is still on a777736 after rollback — Git history was not forced back.
6. Redeploy ONE tip with fresh rollback under `rollbacks/webbob-texting-YYYYMMDD-HHMMSS` ONLY if BOTH_PASS + offline tests pass. Adapt deploy_texting_0916.py → deploy_texting_1107.py; evidence WEBBOB-TEXTING-DEPLOYMENT-0927-attempt4.json (next free).
7. Live replay must clear the 1035 MiniMax incomplete-deliverable fail AND keep prior status-dump + incomplete-verification regressions green. On failure auto-rollback to a777736 and verify `/api/version` local+public.
8. Write conductor/reviews/TEXTING-DEPLOY-1107.md with RESULT: LIVE_PASS or FAIL_OR_ROLLBACK, tip, draft_pr, live before/after JSON, rollback path.
9. Do NOT deploy gaps/media/Instinct/voice/UI in this lane. Those stay HOLD until texting LIVE_PASS.

## Preflight
- Live short_sha is a777736 (or already new tip with LIVE_PASS — then document and stop).
- Do not re-litigate BOTH_PASS on 1ca5e12; that tip failed deploy replay on job completion.
- Texting smoke still required.
- Gemini+MiniMax were healthy at 1035 (HTTP 200 + VERDICT PASS); if either dies again, write BLOCKER and stop before deploy.

## Out of scope
Media/gaps/voice/UI/Instinct deploy. No notify. No Grok. No force-push. No real SMS/iMessage delivery.

## Stop
Stop after TEXTING-DEPLOY-1107.md exists with RESULT line (or after BLOCKER documenting why deploy was not attempted). Print RESULT and live SHA.
