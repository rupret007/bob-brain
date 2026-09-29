# lane-webbob-texting-deploy-ancestry-fix-1307

You are Codex on Jeff's Mac Mini. Fix the Web Bob texting *deploy runner* ancestry/object bug that stopped TEXTING-DEPLOY-1207 before activation, then finish one gated redeploy of the already-reviewed tip. Do NOT use Grok/xAI. No force-push. No Jeff notify/text. No real SMS/iMessage.

## Authoritative failure — TEXTING-DEPLOY-1207 RESULT: FAIL_OR_ROLLBACK
- Tip `eb8029ed9fa17b26becb5487150b3d8981a5a0bb` on `draft/webbob-texting-jobcomplete-fix-1207` (draft PR #24) has TEXTING-FIXED-1207 + offline suites green + fresh LIVE Gemini+MiniMax BOTH_PASS (attempt6 / TEXTING-LIVE-1207.md).
- Clean merge already on `draft/webbob-clean-0927` as `e6c91a2efbf11d3c922469bcd912e675aea29c14` (tree == eb8029e; TEXTING-CLEAN-MERGE-1207.json).
- Deploy stopped *before* smoke / 1035-dd47c4cb replay / live activation:
  `git -C workspaces/webbob-texting-jobcomplete-1207 merge-base --is-ancestor eb8029e e6c91a2` → exit **128** (object `e6c91a2` missing in the feature worktree).
- Same check in `bob-brain` after fetch: exit **0** (ancestor holds). Production unchanged at `a777736`.
- Evidence: conductor/reviews/TEXTING-DEPLOY-1207.md, TEXTING-1207-deployment.log, TEXTING-FIXED-1207.md, TEXTING-LIVE-1207.md, TEXTING-CLEAN-MERGE-1207.json, deploy_texting_1207.py.

## Live baseline
- Local `/api/version` at http://127.0.0.1:8787/api/version → short_sha `a777736` full `a777736b3f0a37c82b0c4c62be8c91117c4c9881` built_at 2026-09-28T09:04:32+00:00
- Do **not** re-open the MiniMax deliverable fix unless a new tip is required. Prefer fixing the deploy runner so the existing BOTH_PASS tip can proceed.

## Goal
1. Fix deploy ancestry so it never asks a shallow feature worktree for a clean-merge SHA it does not have. Preferred minimal fix (reuse, don't invent):
   - In `conductor/reviews/deploy_texting_1207.py` (adapt → `deploy_texting_1307.py` if cleaner): before `merge-base --is-ancestor`, `git fetch` the clean branch into the candidate repo **or** run the ancestry check against `bob-brain` (which already has both objects) / the clean worktree.
   - Treat git exit 128 (missing object) as a fetch-and-retry / wrong-repo bug, not as "not an ancestor".
   - Keep all other gates: exact-tip offline receipts, fresh BOTH_PASS (reuse TEXTING-LIVE-1207.md attempt6 if tip SHA unchanged; if tip changes, run fresh LIVE Gemini+MiniMax and write TEXTING-LIVE-1307.md), texting smoke, 19 frozen live turns, exact 1035/dd47c4cb MiniMax job with accepted saved deliverable, auto-rollback to a777736 on any fail with local+public `/api/version` verify.
2. If tip must change for a tiny deploy-guard in-repo test: branch `draft/webbob-texting-deploy-ancestry-fix-1307` from `eb8029e`, keep product behavior identical, re-run offline suites + fresh BOTH_PASS, regular-merge into `draft/webbob-clean-0927`, new draft PR if needed. Never force-push.
3. If tip stays `eb8029e`: do **not** redo FIXED content; write TEXTING-FIXED-1307.md noting VERIFIED-ALREADY-FIXED tip + deploy-runner fix path; proceed to deploy with attempt slot next free (attempt7+ / WEBBOB-TEXTING-DEPLOYMENT-0927-attempt6.json or next free).
4. Redeploy ONE tip with fresh rollback under `rollbacks/webbob-texting-YYYYMMDD-HHMMSS` ONLY when gates pass.
5. Write `conductor/reviews/TEXTING-DEPLOY-1307.md` with RESULT: LIVE_PASS or FAIL_OR_ROLLBACK, tip, draft_pr, live before/after JSON, rollback path/verified.
6. Do NOT deploy gaps/media/voice/UI/Instinct. Those stay HOLD until texting LIVE_PASS.

## Preflight
- Confirm live still a777736 (or already new tip with LIVE_PASS — then document and stop).
- Confirm bob-brain has e6c91a2 on origin/draft/webbob-clean-0927 and ancestry eb8029e ⊆ e6c91a2.
- Fetch clean into candidate worktree OR point ancestry at bob-brain before any merge-base gate.
- If Gemini/MiniMax unhealthy and a fresh LIVE is required, write BLOCKER and stop before deploy.

## Out of scope
Gaps/media/voice/UI/Instinct deploy. Notify. Grok. Force-push. Real SMS/iMessage.

## Stop
Stop after TEXTING-DEPLOY-1307.md exists with a RESULT line (or BLOCKER). Print RESULT and live SHA.
