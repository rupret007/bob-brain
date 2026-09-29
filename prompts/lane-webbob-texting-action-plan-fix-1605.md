# lane-webbob-texting-action-plan-fix-1605

You are Codex on Jeff's Mac Mini. Fix the Web Bob texting *live-replay actionable Action plan* failure that caused TEXTING-DEPLOY-1508 FAIL_OR_ROLLBACK, then finish one gated redeploy. Do NOT use Grok/xAI. No force-push. No Jeff notify/text. No real SMS/iMessage.

## Authoritative failure — TEXTING-DEPLOY-1508 RESULT: FAIL_OR_ROLLBACK (~15:41 CT)
- Tip `2cd10065b55d4aba4179a1f49e11f1949bbbb5be` on `draft/webbob-texting-replay-json-fix-1508` (draft PR #25).
- Offline suites + fresh LIVE Gemini+MiniMax BOTH_PASS (`TEXTING-LIVE-1508.md`, `TEXTING-FIXED-1508.md`).
- Clean merge `e1c03ac936ada6a8427e9d86f2d1d3cf8d0bb53c` on `draft/webbob-clean-0927` (tree == 2cd1006).
- Deploy ran attempt8, activated smoke + 19-turn live replay (19 passed turns / 0 executed jobs before fail), then FAILED and rolled back:
  - Failure: Replay job `webchat-f2c47c4c66fd5163b806595b146cb5b0` — **Missing actionable action plan (change, validation and exit condition required)**
  - Gate detail: MiniMax "Review and regression test-case drafts" job (sibling of Gemini audit `webchat-7e146cc214bc563f9a905acf9b5f94e0`) for ongoing lane `# lane-webbob-texting-replay-json-fix-1508`. Prompt's assigned subtask / `deliverable_requirements()` require an `Action plan:` section with nonempty same-line `Change:`, `Validation:`, and `Exit condition:` fields (`services/result_acceptance.py` → `plan_heading` / `check_deliverables` ~L36–104, `deliverable_requirements` ~L255–281). Worker answer omitted or malformed that section; acceptance raised `ResultRejected` before publication.
  - Task-run artifacts: `conductor/state/task-runs/webchat-f2c47c4c66fd5163b806595b146cb5b0/{prompt.txt,REPO-EVIDENCE.json}` (repo was workspaces/webbob-texting-replay-json-1508 @ 2cd1006).
  - Also: `1035/dd47c4cb MiniMax completion replay: not passed` (`jobcompletion_regression.pass_check=false` in attempt8 JSON; fixture `services/fixtures/texting_jobcompletion_1035.json` + source job `webchat-dd47c4cb825451b5ab32daa219a11320`). 1403 completion JSON regression PASS.
  - Evidence: `conductor/reviews/WEBBOB-TEXTING-DEPLOYMENT-0927-attempt8.json`, `WEBBOB-TEXTING-FAIL-1508.md`, `TEXTING-DEPLOY-1508.md`.
  - Rollback `rollbacks/webbob-texting-20260928-154026` verified; live stayed `a777736`.

## Diagnosis (precise)
1. Enforcement is deterministic in `services/result_acceptance.py`: if `plan_heading(prompt)` returns `"Action plan"` (assigned subtask matches `\bactionable plan\b`) or `"Unblock plan"`, `check_deliverables` requires heading + Change/Validation/Exit condition on label lines.
2. Live replay still queues MiniMax test-writing jobs whose prompts include "actionable plan" and append `deliverable_requirements()`; workers (esp. MiniMax) often emit regression drafts + JSON but skip/malform the Action plan block → fail closed mid-replay.
3. Keep the 1508 completion JSON `accepted`/`reason` contract and Findings/limits — do not regress those. Fix so workers that need an actionable plan *always* emit Change+Validation+Exit condition (prompt shaping / evidence packing / answer post-check / fixtures / focused tests), and so the exact f2c47c4c case + 1035/dd47c4cb MiniMax completion replay pass under the deploy runner.

## Live baseline
- Local + public `/api/version` → short_sha `a777736` full `a777736b3f0a37c82b0c4c62be8c91117c4c9881` built_at 2026-09-28T09:04:32+00:00
- Keep durable screen-isolation policy from 1403 (durable `svc-*` peers only; ephemeral `svc-project-tick` / `lane-*` may churn).

## Goal
1. Fix product so live-replay jobs that need an actionable Action/Unblock plan always produce nonempty same-line `Change:`, `Validation:`, and `Exit condition:` under the required heading (API workers Gemini/MiniMax/Claude/Codex/Cursor and any prompt/schema path). Fail closed if missing — never claim the job finished without it. Prefer making workers reliably emit the plan (prompt + examples + evidence) over weakening acceptance.
2. Preserve 1508 contracts: fenced JSON `{"accepted": bool, "reason": "..."}`, Findings/limits, regression test drafts (Target/Setup/Action/Expected), `report_repository` worktree=None behavior, screen-isolation deploy policy.
3. Prove with focused unit/integration tests that (a) a MiniMax-style answer missing Action plan is rejected with the exact substring, (b) a complete answer with drafts + Action plan + JSON + Findings/limits passes `check_answer` / accept path, (c) fixture/replay covering the f2c47c4c prompt shape, (d) 1035/dd47c4cb MiniMax completion replay produces an accepted saved deliverable under the deploy gate.
4. Branch `draft/webbob-texting-action-plan-fix-1605` from `2cd1006`. Keep texting product behavior otherwise identical. Regular-merge into `draft/webbob-clean-0927` when green. Update draft PR #25 (or open a successor draft PR) with the new tip. Never force-push.
5. Re-run offline webchat + services suites + evals on the new tip. Fresh LIVE Gemini+MiniMax BOTH_PASS → `TEXTING-LIVE-1605.md`. Write `TEXTING-FIXED-1605.md`.
6. Adapt deploy runner from `deploy_texting_1508.py` → `deploy_texting_1605.py` (+ record wrapper) keeping ancestry fix + durable screen-isolation. Next free attempt slot is **9+**. Redeploy ONE tip with fresh rollback under `rollbacks/webbob-texting-YYYYMMDD-HHMMSS` ONLY when gates pass. Full gates: offline receipts, BOTH_PASS, draft PR/clean, texting smoke, 19 frozen live turns, exact 1035/dd47c4cb MiniMax job with accepted saved deliverable, f2c47-style Action plan acceptance, auto-rollback to a777736 on any fail with local+public `/api/version` verify.
7. Write `conductor/reviews/TEXTING-DEPLOY-1605.md` with RESULT: LIVE_PASS or FAIL_OR_ROLLBACK, tip, draft_pr, live before/after JSON, rollback path/verified.
8. Do NOT deploy gaps/media/voice/UI/Instinct. Those stay HOLD until texting LIVE_PASS.

## Preflight
- Confirm live still a777736 (or already new tip with LIVE_PASS — then document and stop).
- Confirm no other active `lane-webbob-*` screens before deploy (your own lane screen is OK).
- Confirm bob-brain has e1c03ac / 2cd1006 and can ancestry-check the new tip after clean merge.
- If Gemini/MiniMax unhealthy and a fresh LIVE is required, write BLOCKER and stop before deploy.
- Borrow proven patterns from TEXTING-FIXED-1508 (completion JSON), TEXTING-FIXED-1403 (screen isolation), TEXTING-FIXED-1207 (job-complete honesty) — do not invent a parallel deploy stack.
- Worktree: `/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-texting-action-plan-1605` already on branch from tip 2cd1006.

## Out of scope
Gaps/media/voice/UI/Instinct deploy. Notify. Grok. Force-push. Real SMS/iMessage. Other-repo merges.

## Stop
Stop after TEXTING-DEPLOY-1605.md exists with a RESULT line (or BLOCKER). Print RESULT and live SHA.
