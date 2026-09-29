INTEGRATE LIVE DEPLOY BLOCKER FIX — draft/webbob-integrate-2057 @ badc732

Context:
- Offline READY (INTEGRATE-FIXED-0058): 324 webchat / 130 services / 77 evals; tip badc732c740625dd4a15b1774db09815c7a5ed99.
- LIVE Gemini+MiniMax BOTH_PASS on badc732 (INTEGRATE-LIVE-0204.md) — code review only; does not cover live deploy rubric.
- deploy_integrate.py attempt2 at 0204 CT ACTIVATED badc732 then FAIL'd live rubric and rolled back to dff84e3 (verified=True).
- Failure: session b33fac25-3c8a-452d-8673-47d3a99dd92c turn 1 ("Ok remember you can use Gemini and Minimax for the ongoing jobs.")
  - Live reply: "I couldn't assign those workers: there is no identifiable ongoing job permitted by the current holds. Name a project and task to start."
  - errors: work request has no real dispatch; Gemini/MiniMax did not receive API worker jobs
  - task_ids=[], receipts=[], started_jobs=[]
  - expected kind: assign
- Evidence: conductor/reviews/WEBBOB-INTEGRATE-DEPLOYMENT-0927-attempt2.json and WEBBOB-INTEGRATE-FAIL-0927.md
- Offline lane-only evals pass this turn; live deploy path with current holds does not. Fix the LIVE path.

Goal:
1. Diagnose why live deploy cannot create real Gemini+MiniMax API worker jobs on turn 1 under current holds, while offline lane-only evals pass.
2. Fix so live deploy_integrate.py replay assigns real Gemini AND MiniMax API worker jobs on that turn (or equivalent permitted real dispatch with receipts/task_ids), without empty "work started" promises and without violating holds for projects that must stay parked.
3. Keep session-freeze honesty from 0058 (all 19 captured asks). Do NOT truncate/rewrite conductor/webchat/sessions/*.json.
4. Re-run full webchat + services unittests + bob parity/integration evals. Refresh webchat/evidence/integrate-tests.json so sha==HEAD, suite_exit=eval_exit=0, eval passed==total.
5. Regular push to brain/draft/webbob-integrate-2057 (NO force-push). Write conductor/reviews/INTEGRATE-FIXED-0204.md with RESULT READY|BLOCKED, new tip SHA, test counts, root cause, and note LIVE Gemini+MiniMax must be re-run on the new tip before deploy.
6. Do not deploy, merge, undraft, or notify Jeff. No Grok/xAI.

Worktree: /Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-integrate-2057
BOB_ROOT: /Users/jeffstory/Documents/bob-overnight-inject
Success: INTEGRATE-FIXED-0204.md READY + remote branch tip advanced past badc732 + offline gates green.
