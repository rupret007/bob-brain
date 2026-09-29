# lane-webbob-texting-regression-drafts-fix-1658

You are Codex on Jeff's Mac Mini. Fix the Web Bob texting *live-replay concrete regression test drafts* failure that caused TEXTING-DEPLOY-1605 FAIL_OR_ROLLBACK, then finish one gated redeploy. Do NOT use Grok/xAI. No force-push. No Jeff notify/text. No real SMS/iMessage.

## Authoritative failure — TEXTING-DEPLOY-1605 RESULT: FAIL_OR_ROLLBACK (~16:39 CT)
- Tip `c6b3e79218674703cd104d16c2a967ba0cb47221` on `draft/webbob-texting-action-plan-fix-1605` (draft PR #26).
- Offline suites + fresh LIVE Gemini+MiniMax BOTH_PASS (`TEXTING-LIVE-1605.md`, `TEXTING-FIXED-1605.md`, attempt9).
- Clean merge `667c05cef83d040c3f07d578f1eac2942acff33e` on `draft/webbob-clean-0927` (tree == c6b3e79).
- Deploy ran attempt9, activated smoke + 19-turn live replay (16 passed turns / 0 executed jobs before fail), then FAILED and rolled back:
  - Failure: Replay job `webchat-20bfc6f211c05e1f95221804051ff8a9` — **Missing concrete regression test drafts (setup, action and expected assertion required)**
  - Gate detail: MiniMax test-writing / "Review and regression test-case drafts" job. `services/result_acceptance.py` `check_deliverables` / `deliverable_requirements` require two `Regression test:` cases each with nonempty same-line `Target:`, `Setup:`, `Action:`, and `Expected:` (outer report labels; labels inside Setup strings do not count). Worker answer omitted/malformed those drafts; acceptance raised `ResultRejected` before publication.
  - Task-run artifacts: `conductor/state/task-runs/webchat-20bfc6f211c05e1f95221804051ff8a9/{prompt.txt,REPO-EVIDENCE.json,worker.log}` (repo tip was c6b3e79).
  - Also still failing under deploy gate: `1035/dd47c4cb MiniMax completion replay: not passed`; `f2c47c4c MiniMax Action plan replay: not passed` (Action plan report unavailable). 1403 completion JSON regression PASS; prior status-dump / incomplete-verification regressions PASS.
  - Evidence: `conductor/reviews/WEBBOB-TEXTING-DEPLOYMENT-0927-attempt9.json`, `WEBBOB-TEXTING-FAIL-1605.md`, `TEXTING-DEPLOY-1605.md`.
  - Rollback `rollbacks/webbob-texting-20260928-163838` verified; live stayed `a777736`.

## Diagnosis (precise)
1. Tip 1605 fixed structured report transport / Action plan rendering for API workers, and offline/LIVE reviews BOTH_PASS, but live MiniMax replay still fails the *outer* regression-draft contract (`Missing concrete regression test drafts`).
2. The 20bfc6f prompt is an Unblock-plan + regression-drafts job (ongoing "Web Bob unblock 1035"). It requires BOTH (a) two outer Regression test blocks with Target/Setup/Action/Expected and (b) Unblock plan Change/Validation/Exit condition, plus accepted/reason JSON and Findings/limits.
3. Nested fixtures / historical answers / Action-plan-only answers must not be mistaken for outer drafts. Prefer making workers reliably emit outer drafts (prompt shaping, examples, evidence packing, structured fields → render_report) over weakening acceptance.
4. Keep all prior contracts from 1207/1403/1508/1605: completion JSON, Action/Unblock plan, Findings/limits, screen-isolation deploy policy, report_repository worktree=None.

## Live baseline
- Local + public `/api/version` → short_sha `a777736` full `a777736b3f0a37c82b0c4c62be8c91117c4c9881` built_at 2026-09-28T09:04:32+00:00
- Durable screen-isolation policy from 1403 (durable `svc-*` peers only; ephemeral `svc-project-tick` / `lane-*` may churn).

## Goal
1. Fix product so live-replay MiniMax/Gemini/Claude/Codex/Cursor test-writing jobs always emit two outer `Regression test:` cases with nonempty same-line `Target:`, `Setup:`, `Action:`, `Expected:` (plus required Unblock/Action plan, accepted/reason JSON, Findings/limits). Fail closed if missing — never claim finished without drafts. Prefer structured worker fields → `api_worker.render_report` that always materializes outer draft labels.
2. Capture exact 20bfc6f prompt + rejected answer into a fixture (e.g. `services/fixtures/texting_regression_drafts_1658.json`) with hashes and the exact error substring.
3. Prove with focused tests: (a) MiniMax-style answer missing outer drafts rejected with exact substring, (b) complete answer with drafts+plan+JSON+Findings passes accept path, (c) nested/historical fixture labels do not count as outer drafts, (d) real MiniMax probes for 20bfc6f + f2c47c4c Action plan + 1035/dd47c4cb completion produce accepted saved deliverables with verified hashes.
4. Branch `draft/webbob-texting-regression-drafts-fix-1658` from `c6b3e79`. Keep texting product behavior otherwise identical. Regular-merge into `draft/webbob-clean-0927` when green. Update draft PR #26 (or open successor draft PR). Never force-push.
5. Re-run offline webchat + services suites + evals on the new tip. Fresh LIVE Gemini+MiniMax BOTH_PASS → `TEXTING-LIVE-1658.md`. Write `TEXTING-FIXED-1658.md`.
6. Adapt deploy runner from `deploy_texting_1605.py` → `deploy_texting_1658.py` (+ record wrapper) keeping ancestry fix + durable screen-isolation. Next free attempt slot is **10+**. Redeploy ONE tip with fresh rollback under `rollbacks/webbob-texting-YYYYMMDD-HHMMSS` ONLY when gates pass. Full gates: offline receipts, BOTH_PASS, draft PR/clean, texting smoke, 19 frozen live turns, exact 1035/dd47c4cb MiniMax job accepted+saved, f2c47c4c Action plan accepted+saved, 20bfc6f-style regression drafts accepted+saved, auto-rollback to a777736 on any fail with local+public `/api/version` verify.
7. Write `conductor/reviews/TEXTING-DEPLOY-1658.md` with RESULT: LIVE_PASS or FAIL_OR_ROLLBACK, tip, draft_pr, live before/after JSON, rollback path/verified.
8. Do NOT deploy gaps/media/voice/UI/Instinct. Those stay HOLD until texting LIVE_PASS.

## Preflight
- Confirm live still a777736 (or already new tip with LIVE_PASS — then document and stop).
- Confirm no other active `lane-webbob-*` screens before deploy (your own lane screen is OK).
- Confirm bob-brain can ancestry-check the new tip after clean merge from 667c05c / c6b3e79.
- If Gemini/MiniMax unhealthy and a fresh LIVE is required, write BLOCKER and stop before deploy.
- Borrow proven patterns from TEXTING-FIXED-1605 (structured report transport / Action plan), TEXTING-FIXED-1508 (completion JSON), TEXTING-FIXED-1403 (screen isolation) — do not invent a parallel deploy stack.
- Worktree: `/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-texting-regression-drafts-1658` on branch from tip c6b3e79.

## Out of scope
Gaps/media/voice/UI/Instinct deploy. Notify. Grok. Force-push. Real SMS/iMessage. Other-repo merges.

## Stop
Stop after TEXTING-DEPLOY-1658.md exists with a RESULT line (or BLOCKER). Print RESULT and live SHA.
