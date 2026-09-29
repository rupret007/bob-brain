# lane-webbob-texting-replay-json-fix-1508

You are Codex on Jeff's Mac Mini. Fix the Web Bob texting *live-replay honesty / completion JSON* failure that caused TEXTING-DEPLOY-1403 FAIL_OR_ROLLBACK, then finish one gated redeploy. Do NOT use Grok/xAI. No force-push. No Jeff notify/text. No real SMS/iMessage.

## Authoritative failure — TEXTING-DEPLOY-1403 RESULT: FAIL_OR_ROLLBACK (~14:14 CT)
- Tip `eb8029ed9fa17b26becb5487150b3d8981a5a0bb` on `draft/webbob-texting-jobcomplete-fix-1207` (draft PR #24).
- Screen-isolation deploy-runner fix from 1403 is already in place (`deploy_texting_1403.py` / `TEXTING-FIXED-1403.md` VERIFIED-ALREADY-FIXED). Product tip stayed `eb8029e`. Offline suites + LIVE Gemini+MiniMax BOTH_PASS from TEXTING-LIVE-1207.md attempt6 still valid for that tip.
- Clean merge `e6c91a2efbf11d3c922469bcd912e675aea29c14` on `draft/webbob-clean-0927` (tree == eb8029e).
- Deploy ran attempt7, activated smoke + 19-turn live replay, then FAILED and rolled back:
  - Failure: Replay job `webchat-34bc2543b29254c2b70aaca7a0fb545c` — **Answer did not complete the task: Missing required JSON output block.**
  - Gate detail: two regression drafts target `report_repository` in `services/dispatch_worker.py` and trace `source_job_id` for missing-source and valid-source cases, but the answer omitted (1) concrete findings / actionable plan tied to the ongoing lane task, (2) the required JSON block with `accepted`/`reason` fields, (3) a brief findings/limits closing sentence.
  - Additional product bug called out: successful control Setup specifies `worktree=None`, which makes the implementation fall through to the repo fallback path instead of returning the expected worktree Path (see `report_repository` around lines 42–52).
  - Evidence: `conductor/reviews/WEBBOB-TEXTING-DEPLOYMENT-0927-attempt7.json`, `WEBBOB-TEXTING-FAIL-1403.md`, `TEXTING-DEPLOY-1403.md`.
  - Rollback `rollbacks/webbob-texting-20260928-141315` verified; live stayed `a777736`.
  - Texting smoke PASS; prior status-dump / incomplete-verification regressions PASS; 1035/dd47c4cb MiniMax completion replay did not pass; completion report unavailable.

## Live baseline
- Local + public `/api/version` → short_sha `a777736` full `a777736b3f0a37c82b0c4c62be8c91117c4c9881` built_at 2026-09-28T09:04:32+00:00
- Keep durable screen-isolation policy from 1403 (durable `svc-*` peers only; ephemeral `svc-project-tick` / `lane-*` may churn).

## Goal
1. Fix product so live-replay jobs that require a JSON `accepted`/`reason` block actually complete that contract (Gemini/MiniMax/Claude/Codex/Cursor API workers and any prompt/schema path that produced the incomplete answer). Fail closed if the worker answer lacks the required JSON — never claim the job finished without it.
2. Fix `services/dispatch_worker.py` → `report_repository` so `worktree=None` / missing worktree does not incorrectly fall through to the repo Path when the Expected control requires the worktree Path (or correctly returns None when that is the contract). Add focused unit tests covering: missing source, valid source with worktree dir, worktree=None, worktree path that is not a dir.
3. Branch `draft/webbob-texting-replay-json-fix-1508` from `eb8029e` (or from current clean tip if you must rebase). Keep texting product behavior otherwise identical. Regular-merge into `draft/webbob-clean-0927` when green. Update draft PR #24 (or open a successor draft PR) with the new tip. Never force-push.
4. Re-run offline webchat + services suites + evals on the new tip. Fresh LIVE Gemini+MiniMax BOTH_PASS → `TEXTING-LIVE-1508.md`. Write `TEXTING-FIXED-1508.md`.
5. Adapt deploy runner from `deploy_texting_1403.py` → `deploy_texting_1508.py` (+ record wrapper) keeping ancestry fix + durable screen-isolation. Next free attempt slot is **8+**. Redeploy ONE tip with fresh rollback under `rollbacks/webbob-texting-YYYYMMDD-HHMMSS` ONLY when gates pass. Full gates: offline receipts, BOTH_PASS, draft PR/clean, texting smoke, 19 frozen live turns, exact 1035/dd47c4cb MiniMax job with accepted saved deliverable, auto-rollback to a777736 on any fail with local+public `/api/version` verify.
6. Write `conductor/reviews/TEXTING-DEPLOY-1508.md` with RESULT: LIVE_PASS or FAIL_OR_ROLLBACK, tip, draft_pr, live before/after JSON, rollback path/verified.
7. Do NOT deploy gaps/media/voice/UI/Instinct. Those stay HOLD until texting LIVE_PASS.

## Preflight
- Confirm live still a777736 (or already new tip with LIVE_PASS — then document and stop).
- Confirm no other active `lane-webbob-*` screens before deploy (your own lane screen is OK).
- Confirm bob-brain has e6c91a2 and can ancestry-check the new tip after clean merge.
- If Gemini/MiniMax unhealthy and a fresh LIVE is required, write BLOCKER and stop before deploy.
- Borrow proven patterns from TEXTING-FIXED-1207 (job-complete honesty), TEXTING-FIXED-1403 (screen isolation), and existing report_repository tests — do not invent a parallel deploy stack.

## Out of scope
Gaps/media/voice/UI/Instinct deploy. Notify. Grok. Force-push. Real SMS/iMessage. Other-repo merges.

## Stop
Stop after TEXTING-DEPLOY-1508.md exists with a RESULT line (or BLOCKER). Print RESULT and live SHA.
