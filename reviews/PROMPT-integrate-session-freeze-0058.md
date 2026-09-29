INTEGRATE DEPLOY BLOCKER FIX — draft/webbob-integrate-2057 @ 2cdcce9

Context:
- LIVE Gemini+MiniMax BOTH_PASS already on tip 2cdcce9 (worker_assignment API-worker fallback).
- Offline suites READY (323 webchat / 130 services / 73 evals) with gitignored webchat/evidence/integrate-tests.json pointing at 2cdcce9.
- deploy_integrate.py failed at 0058 CT with: "Original Jeff session changed since regression capture".
- Frozen session b33fac25-3c8a-452d-8673-47d3a99dd92c expected 7 user asks; live conductor/webchat/sessions/b33fac25-3c8a-452d-8673-47d3a99dd92c.json now has 9 (added "Hi" and "What are you working on?" after the original 7). Other two frozen sessions still match.

Goal:
1. Update integration_rubric frozen capture for b33fac25 to Jeff's CURRENT live user asks (all 9), with honest expected reply grading that still enforces: no empty "work started" promises; Gemini+MiniMax must get real API worker jobs on turn-1 lane-only conditions; receipts/status honesty unchanged.
2. Prefer extending exchanges for the two new turns rather than deleting Jeff's live messages. Do NOT truncate or rewrite conductor/webchat/sessions/*.json.
3. Re-run full webchat + services unittests + bob parity/integration evals. Refresh webchat/evidence/integrate-tests.json (gitignored OK) so sha==HEAD, suite_exit=eval_exit=0, eval passed==total.
4. Regular push to brain/draft/webbob-integrate-2057 (NO force-push). Write conductor/reviews/INTEGRATE-FIXED-0058.md with RESULT READY, new tip SHA, test counts, and note that LIVE reviews must be re-run before deploy.
5. Do not deploy, merge, undraft, or notify Jeff. No Grok/xAI.

Worktree: /Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-integrate-2057
BOB_ROOT: /Users/jeffstory/Documents/bob-overnight-inject
Success: INTEGRATE-FIXED-0058.md READY + remote branch tip advanced + offline gates green.
