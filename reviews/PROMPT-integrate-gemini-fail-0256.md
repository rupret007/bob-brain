INTEGRATE GEMINI LIVE FAIL FIX — draft/webbob-integrate-2057 @ 199eb19

Context:
- Offline READY: INTEGRATE-FIXED-0204 (333 webchat / 131 services / 96 evals); tip 199eb193396802bbbf899292e48cd04a55f9c57e.
- LIVE MiniMax PASS on 199eb19; LIVE Gemini FAIL → INTEGRATE-LIVE-0256 GATE NOT_BOTH_PASS. Deploy attempt3 skipped; prod still dff84e3.
- Gemini review: conductor/reviews/LIVE-GEMINI-draft_webbob-integrate-2057-199eb19-0256.md

Gemini CRITICAL/HIGH to address (fix real issues; do not rubber-stamp):
1. CRITICAL: deployed_project_context depends on build_info.CODE_ROOT / .git; ensure build_info is a real tracked module in the checkout (or stop importing an unverifiable generated path). Make fallback activation robust and documented with tests.
2. CRITICAL: integration_rubric deployed_checkout=True injects screen lane-integrate-deploy-0204 while fallback is for "no identifiable project lane". Align rubric fixture with live intent: that screen may exist but must NOT count as project/repo/task context; fallback must still activate; add regression that mirrors attempt2 (deploy screen present, no project context) and proves Gemini+MiniMax API jobs are created.
3. HIGH: tests relying on CODE_ROOT — ensure CODE_ROOT is the running Web Bob git checkout root (or resolve git root correctly if nested); absolute-path pin checks should match production pin files; avoid false-pass offline / fail-live.

Also keep:
- Session-freeze honesty (all 19 captured asks); do NOT truncate/rewrite conductor/webchat/sessions/*.json.
- Holds: Barker + Wildflower stay parked; no empty "work started" promises.
- Prior attempt2 failure (no real Gemini/MiniMax API worker jobs on turn 1 under holds) must remain fixed.

Goal:
1. Diagnose which Gemini findings are real defects vs review-prompt evidence gaps.
2. Harden code/tests as needed on tip 199eb19 worktree.
3. Re-run full webchat + services unittests + bob parity/integration evals. Refresh webchat/evidence/integrate-tests.json (sha==HEAD, suite_exit=eval_exit=0, passed==total).
4. Regular push to brain/draft/webbob-integrate-2057 (NO force-push).
5. Write conductor/reviews/INTEGRATE-FIXED-0256.md with RESULT READY|BLOCKED, new tip SHA (or same if evidence-only), test counts, which Gemini findings were real vs false, and note LIVE Gemini+MiniMax must be re-run on the new tip before deploy.
6. Do not deploy, merge, undraft, or notify Jeff. No Grok/xAI.

Worktree: /Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-integrate-2057
BOB_ROOT: /Users/jeffstory/Documents/bob-overnight-inject
Success: INTEGRATE-FIXED-0256.md READY + remote tip advanced (or explicit evidence-only READY with tip unchanged) + offline gates green.
