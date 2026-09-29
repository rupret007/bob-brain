# lane-webbob-texting-jobcomplete-fix-1207

You are Codex on Jeff's Mac Mini. Fix Web Bob texting deploy LIVE replay failure (job-completion / MiniMax incomplete deliverable) that survived the 1107 tip, then redeploy only if gates pass. Do NOT use Grok/xAI. No force-push. No Jeff notify/text.

## Failure (authoritative) — TEXTING-DEPLOY-1107 RESULT: FAIL_OR_ROLLBACK
- Tip `6670444bd932409b39044c65d651ae4715f2218f` on `draft/webbob-texting-jobcomplete-fix-1107` (draft PR #23) had TEXTING-FIXED-1107 + offline suites green + fresh LIVE Gemini+MiniMax BOTH_PASS (attempt5), clean merge to `draft/webbob-clean-0927` as `1fe9fe6`, then deploy attempt4 rolled back to live `a777736` (verified local+public).
- Evidence: conductor/reviews/TEXTING-DEPLOY-1107.md, WEBBOB-TEXTING-FAIL-1107.md, WEBBOB-TEXTING-DEPLOYMENT-0927-attempt4.json, TEXTING-LIVE-1107.md, TEXTING-FIXED-1107.md
- Failing check: live replay job `webchat-dd47c4cb825451b5ab32daa219a11320` (MiniMax worker, kind `test-writing`, title “Web Bob — Review and regression test-case drafts (1035 replay)”)
- Fail reason: **Missing concrete regression test drafts (setup, action and expected assertion required)**. Same class as 1035 fail on tip `1ca5e12` (job `webchat-f4b8e359666155c6a06900f02b313c8c`). Offline acceptance tightening in 1107 was not enough — the live MiniMax worker still did not emit the required deliverable under the real replay prompt/budget.
- Keep prior greens: casual status voice, 0810 incomplete-verification, 1035/1107 offline fixtures, texting smoke, BOTH_PASS review transport.

## Live baseline
- Prod `/api/version` short_sha `a777736` full `a777736b3f0a37c82b0c4c62be8c91117c4c9881` built_at 2026-09-28T09:04:32+00:00
- Start from tip `6670444` / branch `draft/webbob-texting-jobcomplete-fix-1107` in worktree `workspaces/webbob-texting-jobcomplete-1207` on new branch `draft/webbob-texting-jobcomplete-fix-1207`. Do not invent a parallel orchestrator. Borrow proven patterns; reuse existing result_acceptance / worker_assignment / api workers.

## Goal
1. Make the LIVE MiniMax test-writing path produce concrete regression drafts (setup/input, action/trigger, expected assertions) plus a short Change/Validation/Exit unblock plan when the ongoing task names an unblock — not only reject exploratory answers offline. Prefer: stronger assignment prompts, bounded code snapshots MiniMax can actually use within budget, fixture of the exact rejected `webchat-dd47c4cb…` answer if capturable, and acceptance that still fails closed. Reuse, do not invent a new subsystem.
2. Keep casual status voice and prior 0810/0916/1035/1107 regressions green.
3. Re-run the real offline API/webchat/services tests + evals the gate expects on the new tip. Write TEXTING-FIXED-1207.md with tip SHA and counts.
4. Fresh LIVE Gemini + MiniMax reviews on the NEW tip (attempt slot next free after 1107 attempt5 → attempt6+). BOTH_PASS required. Markers TEXTING-LIVE-1207.md / LIVE-GEMINI-* / LIVE-MINIMAX-*. Reuse review transport patterns from UNBLOCK-1035 / run_texting_reviews_1107.py.
5. Merge new tip into `draft/webbob-clean-0927` (regular merge, never force-push). Open a new draft PR if needed (PR #23 may already be merged/superseded). Clean is at `1fe9fe6` (== tree of 6670444); production still on a777736 after rollback.
6. Redeploy ONE tip with fresh rollback under `rollbacks/webbob-texting-YYYYMMDD-HHMMSS` ONLY if BOTH_PASS + offline tests pass. Adapt deploy_texting_1107.py → deploy_texting_1207.py; evidence WEBBOB-TEXTING-DEPLOYMENT-0927-attempt5.json (next free).
7. Live replay must clear the dd47c4cb / 1035 MiniMax incomplete-deliverable fail AND keep prior status-dump + incomplete-verification regressions green. On failure auto-rollback to a777736 and verify `/api/version` local+public.
8. Write conductor/reviews/TEXTING-DEPLOY-1207.md with RESULT: LIVE_PASS or FAIL_OR_ROLLBACK, tip, draft_pr, live before/after JSON, rollback path.
9. Do NOT deploy gaps/media/Instinct/voice/UI in this lane. Those stay HOLD until texting LIVE_PASS.

## Preflight
- Live short_sha is a777736 (or already new tip with LIVE_PASS — then document and stop).
- Do not re-litigate BOTH_PASS on 6670444; that tip failed deploy replay on job completion.
- Texting smoke still required.
- If Gemini/MiniMax unhealthy, write BLOCKER and stop before deploy.

## Out of scope
Media/gaps/voice/UI/Instinct deploy. No notify. No Grok. No force-push. No real SMS/iMessage delivery.

## Stop
Stop after TEXTING-DEPLOY-1207.md exists with RESULT line (or after BLOCKER documenting why deploy was not attempted). Print RESULT and live SHA.
