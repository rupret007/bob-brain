# lane-webbob-texting-smoke-replay-fix-1901

You are Codex on Jeff's Mac Mini. Fix the Web Bob texting *deploy activation / smoke / live-replay evidence* failure that caused TEXTING-DEPLOY-1803 FAIL_OR_ROLLBACK, then finish one gated redeploy. Do NOT use Grok/xAI. No force-push. No Jeff notify/text. No real SMS/iMessage.

## Authoritative failure — TEXTING-DEPLOY-1803 RESULT: FAIL_OR_ROLLBACK (~18:25 CT)
- Tip `3b522c51331f66f6b58c0ff8a1ecf228d1ae961f` on `draft/webbob-texting-guard-consistency-fix-1803` (draft PR #28).
- Offline suites + fresh LIVE Gemini+MiniMax BOTH_PASS (`TEXTING-LIVE-1803.md`, `TEXTING-FIXED-1803.md`, attempt11).
- Clean merge `f4cb88ad1a009a05282bef19a2eb34a023bb00c5` on `draft/webbob-clean-0927` (tree == 3b522c5, ancestry retains d32d0f7).
- Deploy runner exited 1 **without activating a lasting tip** (rollback_path: not activated; live stayed `a777736`):
  - Texting smoke: not passed
  - Live replay: **0 captured turns** / 0 passed / 0 executed jobs
  - Named MiniMax live jobs (1035/dd47c4cb, f2c47c4c, 20bfc6f) and 1803 guard-consistency capture: not passed
  - Cited evidence `WEBBOB-TEXTING-DEPLOYMENT-0927-attempt11.json` is **missing on disk** after the run
  - Preflight listed the Codex lane screen still up (`lane-webbob-texting-guard-consistency-fix-1803`)
  - Marker: `conductor/reviews/TEXTING-DEPLOY-1803.md`, fail note `WEBBOB-TEXTING-FAIL-1803.md`

## Diagnosis (precise)
1. Attempt11 product tip cleared offline + LIVE review gates, but the **deploy wrapper never completed a successful activation path** that writes attempt11 evidence and reaches smoke/live-replay.
2. Highest-probability causes to verify in order:
   a) `check_lane_isolation` / durable-svc-peers-1403 rejecting because the coding `lane-webbob-*` screen was still attached during deploy — fix deploy runner to allow the owning lane screen OR stop that screen before activation and prove isolation.
   b) Deploy crashed / wrapper_failure before writing `WEBBOB-TEXTING-DEPLOYMENT-0927-attempt11.json` — ensure atomic evidence write from first preflight through smoke/replay, and surface the real exception in TEXTING-DEPLOY-*.md.
   c) Activation/restart left webchat on a777736 or unhealthy so smoke + 19-turn capture got 0 turns — fix pin/restart/version assert so smoke only runs when local+public SHA match the candidate tip.
3. Keep all prior product contracts from 1207–1803 (completion JSON, Action/Unblock, outer regression drafts, literal guard Expected, Findings/limits, report_repository worktree=None). Do not weaken LIVE honesty gates.
4. Prefer fixing deploy runner + activation/smoke sequencing over changing product behavior that already BOTH_PASS'd.

## Live baseline
- Local + public `/api/version` → short_sha `a777736` full `a777736b3f0a37c82b0c4c62be8c91117c4c9881` built_at 2026-09-28T09:04:32+00:00
- Durable screen-isolation policy from 1403 (durable `svc-*` peers only; ephemeral `svc-project-tick` / owning `lane-*` may be handled explicitly).

## Goal
1. Root-cause why attempt11 produced FAIL with 0 live-replay turns, missing attempt11 evidence JSON, and rollback not activated while live stayed a777736. Capture that root cause in TEXTING-FIXED-1901.md with file/line proof.
2. Fix deploy_texting / record wrapper (adapt 1803 → 1901) so: (a) owning lane screen does not abort deploy, (b) evidence JSON is always written for the attempt slot even on early fail, (c) smoke + 19-turn live replay only run after activation proves candidate SHA on local+public `/api/version`, (d) any fail auto-rollbacks to a777736 and verifies both version endpoints.
3. Branch `draft/webbob-texting-smoke-replay-fix-1901` from tip `3b522c5`. Keep texting product behavior otherwise identical unless a product bug is proven to block smoke. Regular-merge into `draft/webbob-clean-0927` when green. Update/open successor draft PR. Never force-push.
4. Re-run offline webchat + services suites + evals on the new tip. Fresh LIVE Gemini+MiniMax BOTH_PASS → `TEXTING-LIVE-1901.md`. Write `TEXTING-FIXED-1901.md`.
5. Next free attempt slot is **12+**. Redeploy ONE tip with fresh rollback under `rollbacks/webbob-texting-YYYYMMDD-HHMMSS` ONLY when gates pass. Full gates: offline receipts, BOTH_PASS, draft PR/clean, texting smoke PASS, 19 frozen live turns with executed jobs as required, exact 1035/dd47c4cb + f2c47c4c + 20bfc6f MiniMax jobs accepted+saved, 1803 guard-consistency capture, auto-rollback to a777736 on any fail.
6. Write `conductor/reviews/TEXTING-DEPLOY-1901.md` with RESULT: LIVE_PASS or FAIL_OR_ROLLBACK, tip, draft_pr, live before/after JSON, rollback path/verified, and a real evidence path that exists on disk.
7. Do NOT deploy gaps/media/voice/UI/Instinct. Those stay HOLD until texting LIVE_PASS.

## Preflight
- Confirm live still a777736 (or already new tip with LIVE_PASS — then document and stop).
- Before activation: ensure no *other* active `lane-webbob-*` screens (your own lane screen OK if runner allowlists it).
- Confirm bob-brain ancestry from f4cb88a / 3b522c5 / d32d0f7.
- If Gemini/MiniMax unhealthy and a fresh LIVE is required, write BLOCKER and stop before deploy.
- Borrow proven patterns from TEXTING-FIXED-1803/1658/1605/1403 — do not invent a parallel deploy stack.
- Worktree: `/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-texting-smoke-replay-1901` on branch from tip 3b522c5.

## Out of scope
Gaps/media/voice/UI/Instinct deploy. Notify. Grok. Force-push. Real SMS/iMessage. Other-repo merges.

## Stop
Stop after TEXTING-DEPLOY-1901.md exists with a RESULT line (or BLOCKER). Print RESULT and live SHA.
