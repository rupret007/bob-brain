You are Codex on Jeff's Mac Mini. Work ONLY in:
  ~/Documents/bob-overnight-inject/workspaces/webbob-integrate-2057
Branch: draft/webbob-integrate-2057 @ ab50533 (may advance). Drafts only. No deploy/merge/undraft/force-push. Never Grok/xAI.

LIVE deploy attempt 2205 of tip ab50533 FAILED and rolled back to dff84e3.
Failure (WEBBOB-INTEGRATE-FAIL-0927.md / INTEGRATE-DEPLOY-2205.md):
  "b33fac25-3c8a-452d-8673-47d3a99dd92c turn 1: work request has no real dispatch; Gemini/MiniMax did not receive API worker jobs"

Context:
- Offline READY at ab50533 (319 webchat + 129 services + 56 evals); status_observation fix is in.
- LIVE Gemini+MiniMax BOTH_PASS on ab50533 after FP triage (INTEGRATE-LIVE-2205.md).
- Prior attempt3 on 61ad058 failed status observation mid-worker-startup; that is fixed offline.
- This new failure is turn-1: Jeff message that should create real Gemini+MiniMax API worker jobs did not dispatch.

Fix only the real dispatch/API-worker path so the frozen session turn 1 creates real Gemini and MiniMax API jobs with receipts. Add regressions. Run webchat+services+evals. Commit + regular-push. Write ~/Documents/bob-overnight-inject/conductor/reviews/INTEGRATE-FIXED-2205.md with new tip SHA, test counts, READY or STILL-FAIL. No Jeff notify. No live deploy.
