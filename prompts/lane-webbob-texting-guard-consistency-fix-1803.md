# lane-webbob-texting-guard-consistency-fix-1803

You are Codex on Jeff's Mac Mini. Fix the Web Bob texting *regression-draft vs literal acceptance-guard consistency* failure that caused TEXTING-DEPLOY-1658 FAIL_OR_ROLLBACK, then finish one gated redeploy. Do NOT use Grok/xAI. No force-push. No Jeff notify/text. No real SMS/iMessage.

## Authoritative failure — TEXTING-DEPLOY-1658 RESULT: FAIL_OR_ROLLBACK (~17:33 CT)
- Tip `d32d0f7244d191b85b429c3c8d0228ec0c9b4670` on `draft/webbob-texting-regression-drafts-fix-1658` (draft PR #27, state MERGED into clean then rolled back live).
- Offline suites + fresh LIVE Gemini+MiniMax BOTH_PASS (`TEXTING-LIVE-1658.md`, `TEXTING-FIXED-1658.md`, attempt10).
- Clean merge `d40180791a093921fd7999720cbae762c74107f9` on `draft/webbob-clean-0927` (tree == d32d0f7).
- Deploy ran attempt10, activated smoke + 19-turn live replay (8 passed turns / 0 executed jobs before fail), then FAILED and rolled back:
  - Failure: Replay job `webchat-8e7eee346e1d51099fdf99d23fe7c353` — **Regression draft contradicts literal guard outcome: check_completion_json raised Missing or ambiguous required completion JSON output block**
  - Meaning: a Regression test control's Expected/outcome claimed one acceptance result, but the literal `check_completion_json` / acceptance guard raised a different ResultRejected substring. Deploy wrapper rejects that contradiction before publication (commit `6eb5871` style).
  - Also under deploy gate: `1035/dd47c4cb MiniMax completion replay: not passed`; `f2c47c4c MiniMax Action plan replay: not passed`; `20bfc6f MiniMax regression drafts replay: not passed` (reports unavailable after early reject). 1403 completion JSON regression PASS; prior status-dump / incomplete-verification regressions PASS.
  - Evidence: `conductor/reviews/WEBBOB-TEXTING-DEPLOYMENT-0927-attempt10.json`, `WEBBOB-TEXTING-FAIL-1658.md`, `TEXTING-DEPLOY-1658.md`.
  - Rollback `rollbacks/webbob-texting-20260928-173302` verified; live stayed `a777736`.

## Diagnosis (precise)
1. Tip 1658 made workers emit outer Regression test Target/Setup/Action/Expected and added literal-control audits, but live replay still produced a *control that contradicts* what `check_completion_json` actually raises (`Missing or ambiguous required completion JSON output block`).
2. Regression drafts that assert completion-JSON failures must use the **exact** ResultRejected substring the guard raises today — never a paraphrased Expected, never an Expected that implies pass when the fixture answer is missing/ambiguous JSON, and never a control that claims a different error class.
3. Prefer fixing fixture generation / example packs / `render_report` / probe templates so Expected lines are derived from the live guard string (single source of truth), over weakening the contradiction check.
4. Keep all prior contracts from 1207/1403/1508/1605/1658: completion JSON, Action/Unblock plan, outer regression drafts, Findings/limits, screen-isolation deploy policy, report_repository worktree=None, reject nested/historical quoted drafts as outer drafts.

## Live baseline
- Local + public `/api/version` → short_sha `a777736` full `a777736b3f0a37c82b0c4c62be8c91117c4c9881` built_at 2026-09-28T09:04:32+00:00
- Durable screen-isolation policy from 1403 (durable `svc-*` peers only; ephemeral `svc-project-tick` / `lane-*` may churn).

## Goal
1. Fix product so every Regression test control that exercises completion JSON (and related acceptance guards) has Expected/outcome that **exactly matches** the literal guard ResultRejected substring (or exact pass path). Fail closed if a control contradicts the guard — never publish/deploy that tip.
2. Capture the exact 8e7eee34 prompt + rejected answer / control into a fixture (e.g. `services/fixtures/texting_guard_consistency_1803.json`) with hashes and the exact contradiction error substring.
3. Prove with focused tests: (a) Expected that paraphrases or mismatches `Missing or ambiguous required completion JSON output block` is rejected with the contradiction substring, (b) Expected that copies the live guard string for a missing/ambiguous JSON answer passes the contradiction check and is then accepted/rejected correctly by the guard itself, (c) prior 1658 outer-draft contract still holds, (d) real MiniMax probes for 20bfc6f + f2c47c4c Action plan + 1035/dd47c4cb completion produce accepted saved deliverables with verified hashes and zero guard-contradiction rejects.
4. Branch `draft/webbob-texting-guard-consistency-fix-1803` from `d32d0f7`. Keep texting product behavior otherwise identical. Regular-merge into `draft/webbob-clean-0927` when green. Update/open successor draft PR. Never force-push.
5. Re-run offline webchat + services suites + evals on the new tip. Fresh LIVE Gemini+MiniMax BOTH_PASS → `TEXTING-LIVE-1803.md`. Write `TEXTING-FIXED-1803.md`.
6. Adapt deploy runner from `deploy_texting_1658.py` → `deploy_texting_1803.py` (+ record wrapper) keeping ancestry fix + durable screen-isolation. Next free attempt slot is **11+**. Redeploy ONE tip with fresh rollback under `rollbacks/webbob-texting-YYYYMMDD-HHMMSS` ONLY when gates pass. Full gates: offline receipts, BOTH_PASS, draft PR/clean, texting smoke, 19 frozen live turns, exact 1035/dd47c4cb MiniMax job accepted+saved, f2c47c4c Action plan accepted+saved, 20bfc6f-style regression drafts accepted+saved, auto-rollback to a777736 on any fail with local+public `/api/version` verify.
7. Write `conductor/reviews/TEXTING-DEPLOY-1803.md` with RESULT: LIVE_PASS or FAIL_OR_ROLLBACK, tip, draft_pr, live before/after JSON, rollback path/verified.
8. Do NOT deploy gaps/media/voice/UI/Instinct. Those stay HOLD until texting LIVE_PASS.

## Preflight
- Confirm live still a777736 (or already new tip with LIVE_PASS — then document and stop).
- Confirm no other active `lane-webbob-*` screens before deploy (your own lane screen is OK).
- Confirm bob-brain can ancestry-check the new tip after clean merge from d401807 / d32d0f7.
- If Gemini/MiniMax unhealthy and a fresh LIVE is required, write BLOCKER and stop before deploy.
- Borrow proven patterns from TEXTING-FIXED-1658 (outer drafts + literal controls), TEXTING-FIXED-1605 (Action plan), TEXTING-FIXED-1508 (completion JSON), TEXTING-FIXED-1403 (screen isolation) — do not invent a parallel deploy stack.
- Worktree: `/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-texting-guard-consistency-1803` on branch from tip d32d0f7.

## Out of scope
Gaps/media/voice/UI/Instinct deploy. Notify. Grok. Force-push. Real SMS/iMessage. Other-repo merges.

## Stop
Stop after TEXTING-DEPLOY-1803.md exists with a RESULT line (or BLOCKER). Print RESULT and live SHA.
