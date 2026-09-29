# lane-webbob-texting-deploy-0702

You are Codex on Jeff's Mac Mini. Deploy Web Bob texting tip now. Do NOT use Grok/xAI. No force-push. No Jeff notify/text.

## Authority
Jeff granted merge into draft/webbob-clean-0927 + deploy when gates pass (tests, evals, Gemini+MiniMax BOTH_PASS, live replay). Rollback on failure.

## Context
lane-webbob-texting-deploy-0556 started at 05:58 CT (session 01a0e7aa-e14a-7510-acc3-600e50def044) but died with no TEXTING-DEPLOY-0556.md and no live SHA change. Clean remote tip is now f7c2797 (integrate a777736 on clean after revert-of-revert). Live still a777736. Resume/finish deploy; do not re-litigate LIVE reviews.

## Proven gate (do not re-litigate)
- Tip FULL: ce2482cce311ce4317c1b3aca316f1ca446aeddb (short ce2482c)
- Branch: draft/webbob-texting-onto-a777736
- Worktree: /Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-texting-onto-a777736-0420
- LIVE BOTH_PASS: conductor/reviews/TEXTING-LIVE-ce2482c.md (GATE: BOTH_PASS tip=ce2482c)
- Gemini+MiniMax PASS artifacts: LIVE-GEMINI/MINIMAX-draft_webbob-texting-onto-a777736-ce2482c*.md
- Offline READY: TEXTING-READY-0420.md (381 webchat / 131 services)

## Preflight (refuse if any fail)
1. `git -C worktree rev-parse HEAD` must equal ce2482cce311ce4317c1b3aca316f1ca446aeddb
2. grep GATE BOTH_PASS tip=ce2482c in TEXTING-LIVE-ce2482c.md
3. Live `curl -sS http://127.0.0.1:8787/api/version` short_sha must be a777736 (integrate still live) OR already the texting tip if a prior partial deploy somehow succeeded — if already texting tip live with LIVE_PASS marker, just write TEXTING-DEPLOY-0702.md documenting that and stop.
4. Remote tip matches: git ls-remote for draft/webbob-texting-onto-a777736 equals tip.

## Deploy steps (one tip)
1. Ensure tip is on draft/webbob-texting-onto-a777736 and pushed.
2. Merge tip into draft/webbob-clean-0927 with a regular merge (or fast-forward/merge commit). Never force-push. Keep history usable (mirror integrate 0356 clean_note discipline if needed). Current clean is f7c2797 — merge onto that.
3. Open or update a draft PR rupret007/bob-brain for the texting tip onto clean; follow how deploy_integrate_0356.py accepted MERGED draft when head matches.
4. Copy/adapt conductor/reviews/deploy_integrate_0356.py → conductor/reviews/deploy_texting_0702.py (and run-texting-deploy-0702.sh). Changes: tip ce2482c, expected-live a777736, evidence WEBBOB-TEXTING-DEPLOYMENT-0927-attemptN.json, attempt slot next free, rollback dir under rollbacks/webbob-texting-YYYYMMDD-HHMMSS, live replay of Jeff's latest sessions (reuse integration_rubric / live_redeploy_check; include texting smoke). Prefer reusing deploy_parity/live_redeploy_check from candidate webchat.
5. Run deploy with timeout ~1800s. On failure auto-rollback to a777736 and verify /api/version.
6. Write conductor/reviews/TEXTING-DEPLOY-0702.md with exit, tip, draft_pr URL, live before/after JSON, rollback path, RESULT: LIVE_PASS or FAIL_OR_ROLLBACK. Also write/update TEXTING-DEPLOY-0556.md pointing to 0702 if that file is still missing.
7. If LIVE_PASS: also write TEXTING-LIVE-PASS-0702.md noting new live short SHA.

## Out of scope
- Do not deploy media/gaps/voice/UI.
- Do not notify Jeff / Andrea / Web Bob chat.
- Do not force-push.
- Do not claim work started without writing real markers.

## Stop
Stop after TEXTING-DEPLOY-0702.md exists with RESULT line. Print the RESULT and live SHA.
