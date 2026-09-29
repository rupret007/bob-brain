# lane-webbob-texting-deploy-0556

You are Codex on Jeff's Mac Mini. Deploy Web Bob texting tip now. Do NOT use Grok/xAI. No force-push. No Jeff notify/text.

## Authority
Jeff granted merge into draft/webbob-clean-0927 + deploy when gates pass (tests, evals, Gemini+MiniMax BOTH_PASS, live replay). Rollback on failure.

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
3. Live `curl -sS http://127.0.0.1:8787/api/version` short_sha must be a777736 (integrate still live)
4. Remote tip matches: git ls-remote brain draft/webbob-texting-onto-a777736

## Deploy steps (one tip)
1. Ensure tip is on draft/webbob-texting-onto-a777736 and pushed (already should be).
2. Merge tip into draft/webbob-clean-0927 with a regular merge (or fast-forward/merge commit). Never force-push. Keep history usable for future PRs (mirror integrate 0356 clean_note discipline if needed).
3. Open or update a draft PR rupret007/bob-brain: head=draft/webbob-texting-onto-a777736 (or clean after merge) base=draft/webbob-clean-0927 — draft only until deploy tooling needs it; follow how deploy_integrate_0356.py accepted MERGED draft when head matches.
4. Copy/adapt conductor/reviews/deploy_integrate_0356.py → conductor/reviews/deploy_texting_0556.py (and a run-texting-deploy-0556.sh). Changes: tip ce2482c, expected-live a777736, evidence WEBBOB-TEXTING-DEPLOYMENT-0927-attemptN.json, attempt slot next free (start 1), rollback dir under rollbacks/webbob-texting-YYYYMMDD-HHMMSS, live replay of Jeff's latest sessions (reuse integration_rubric / live_redeploy_check patterns; include texting-relevant sessions if frozen fixtures exist, else same integrate replay plus smoke that texting routes still present). Prefer reusing deploy_parity/live_redeploy_check from candidate webchat.
5. Run deploy with timeout ~1800s. On failure auto-rollback to a777736 and verify /api/version.
6. Write conductor/reviews/TEXTING-DEPLOY-0556.md with exit, tip, draft_pr URL, live before/after JSON, rollback path, RESULT: LIVE_PASS or FAIL_OR_ROLLBACK.
7. If LIVE_PASS: also write TEXTING-LIVE-PASS-0556.md noting new live short SHA.

## Out of scope
- Do not deploy media/gaps/voice/UI.
- Do not notify Jeff / Andrea / Web Bob chat.
- Do not force-push; do not undraft unless the proven deploy runner requires merge+head match like integrate.
- Do not claim work started without writing real markers.

## Stop
Stop after TEXTING-DEPLOY-0556.md exists with RESULT line. Print the RESULT and live SHA.
