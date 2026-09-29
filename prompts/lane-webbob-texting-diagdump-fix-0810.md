# lane-webbob-texting-diagdump-fix-0810

You are Codex on Jeff's Mac Mini. Fix Web Bob texting deploy LIVE replay failure, then redeploy. Do NOT use Grok/xAI. No force-push. No Jeff notify/text.

## Failure (authoritative)
TEXTING-DEPLOY-0702 RESULT: FAIL_OR_ROLLBACK at 07:10 CT.
- Tip ce2482c merged to draft/webbob-clean-0927 as 1d72c44 (kept; do not revert merge).
- Live rolled back to a777736 (verified).
- Evidence: conductor/reviews/WEBBOB-TEXTING-DEPLOYMENT-0927-attempt1.json
- Failing check: session b33fac25-3c8a-452d-8673-47d3a99dd92c turn 3 "raw diagnostic dump"
- User message: "Ok great works on all LLMs now?" (expected: status)
- Bad after: "Codex is on “Web Bob: # lane-webbob-texting-deploy-0702” (model not reported; running for 7 min); Gemini is on … (2 jobs waiting to run). MiniMax is on … The job runner has 0 claimed and 4 queued jobs."
Jeff wants short natural status answers — never raw dumps with "model not reported", queue_counts, job runner internals, or semicolon-chained worker inventories that read like diagnostics.

## Goal
1. From worktree webbob-texting-onto-a777736-0420 (or a fresh worktree off ce2482c / clean 1d72c44), fix status/reply formatting so live-replay status turns pass (no "raw diagnostic dump").
2. Borrow proven reply-quality / status-voice patterns already on integrate tip a777736 and reply-fix branches; do not invent a new status subsystem.
3. Run offline tests + evals; write TEXTING-FIXED-0810.md with tip SHA and counts.
4. Fresh LIVE Gemini + MiniMax reviews on the new tip (attempt slot next free). BOTH_PASS required. Markers under conductor/reviews/.
5. Merge new tip into draft/webbob-clean-0927 (regular merge, never force-push). Update draft PR https://github.com/rupret007/bob-brain/pull/18 or open a new draft if needed.
6. Redeploy one tip with fresh rollback under rollbacks/webbob-texting-YYYYMMDD-HHMMSS. Adapt deploy_texting_0702.py → deploy_texting_0810.py; evidence WEBBOB-TEXTING-DEPLOYMENT-0927-attempt2.json (or next free attempt).
7. Live replay must clear the prior fail (turn 3 style status questions must pass). On failure auto-rollback to a777736 and verify /api/version.
8. Write conductor/reviews/TEXTING-DEPLOY-0810.md with RESULT: LIVE_PASS or FAIL_OR_ROLLBACK, tip, draft_pr, live before/after JSON, rollback path.

## Preflight
- Live short_sha is a777736 (or already new tip with LIVE_PASS — then document and stop).
- Do not re-litigate old BOTH_PASS on ce2482c; that tip failed deploy replay.
- Texting smoke still required.

## Out of scope
Media/gaps/voice/UI/Instinct deploy. No notify. No Grok.

## Stop
Stop after TEXTING-DEPLOY-0810.md exists with RESULT line. Print RESULT and live SHA.
