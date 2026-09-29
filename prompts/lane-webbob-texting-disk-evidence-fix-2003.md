# lane-webbob-texting-disk-evidence-fix-2003

You are Codex on Jeff's Mac Mini. Fix the Web Bob texting *deploy LIVE_REPLAY evidence checkpoint disk-exhaustion* failure that caused TEXTING-DEPLOY-1901 FAIL_OR_ROLLBACK, then finish one gated redeploy. Do NOT use Grok/xAI. No force-push. No Jeff notify/text. No real SMS/iMessage.

## Authoritative failure — TEXTING-DEPLOY-1901 RESULT: FAIL_OR_ROLLBACK (~19:20–19:25 CT)
- Tip `8260f800ae29dbcf306f3902227645d6da3cee97` on `draft/webbob-texting-smoke-replay-fix-1901` (draft PR #29).
- Offline suites + fresh LIVE Gemini+MiniMax BOTH_PASS (`TEXTING-LIVE-1901.md`, `TEXTING-FIXED-1901.md`, attempt12).
- Clean merge `28d35f94dd4dc545bddaabb2803b13cdc0b13780` on `draft/webbob-clean-0927`.
- Activation, texting smoke, **19/19 live turns**, named MiniMax jobs, and 1803 guard-consistency capture **passed**.
- Failure: `OSError: [Errno 28] No space left on device` during LIVE_REPLAY evidence checkpoint; runner + recording wrapper also failed writing failure evidence before automatic rollback.
- Agent invoked prepared `rollback.sh`; verified local/public back to `a777736b3f0a37c82b0c4c62be8c91117c4c9881`.
- Markers: `conductor/reviews/TEXTING-DEPLOY-1901.md`, `WEBBOB-TEXTING-FAIL-1901.md`, rollback `rollbacks/webbob-texting-20260928-192035`.

## Diagnosis (precise)
1. Product tip + deploy path almost LIVE_PASS'd; **disk full mid-checkpoint** after successful smoke/19-turn/named jobs turned a green path into FAIL_OR_ROLLBACK.
2. Evidence/checkpoint writers must be disk-safe: atomic small writes, fail closed with RESULT before filling the volume, never leave live tip without rollback when evidence IO fails.
3. Preflight must refuse activation unless free space ≥ **5 GiB** on `/System/Volumes/Data` (or the volume hosting `conductor/reviews` + workspaces). Re-check before LIVE_REPLAY checkpoint.
4. Keep all 1207–1901 product contracts. Prefer hardening deploy evidence + preflight over product behavior changes.

## Conductor cleanup already done this tick (do not redo blindly)
- Freed ~14 GiB stale workspaces/archives; kept `workspaces/webbob-texting-smoke-replay-1901` @ 8260f80 and live rollback `rollbacks/webbob-texting-20260928-192035`.
- At launch, Data volume had ~7 GiB free. Re-verify before any activation.

## Live baseline
- Local + public `/api/version` → short_sha `a777736` full `a777736b3f0a37c82b0c4c62be8c91117c4c9881`.
- No other `lane-webbob-*` screen should be up; durable `svc-*` peers OK.

## Goal
1. Root-cause attempt12 disk FAIL with file/line proof in `TEXTING-FIXED-2003.md` (which checkpoint path filled the disk; why failure evidence also failed).
2. Fix deploy/record wrappers (adapt 1901 → 2003): (a) disk free-space preflight ≥5 GiB before activation, (b) compact/streamed LIVE_REPLAY evidence (no giant context dumps to Data if avoidable; prefer /private/tmp then atomic publish), (c) on ENOSPC or any evidence IO error → cancel claims, rollback to a777736, write RESULT even if only a tiny marker fits, (d) owning lane screen allowlisted.
3. Branch `draft/webbob-texting-disk-evidence-fix-2003` from tip `8260f80`. Keep texting product behavior identical unless a product bug blocks deploy. Regular-merge into `draft/webbob-clean-0927` when green. Update/open successor draft PR. Never force-push.
4. Re-run offline webchat + services suites + evals on the new tip. Fresh LIVE Gemini+MiniMax BOTH_PASS → `TEXTING-LIVE-2003.md`. Write `TEXTING-FIXED-2003.md`.
5. Next free attempt slot is **13+**. Redeploy ONE tip with fresh rollback under `rollbacks/webbob-texting-YYYYMMDD-HHMMSS` ONLY when gates pass AND free space still ≥5 GiB. Full gates unchanged from 1901 (smoke, 19 turns, named MiniMax, 1803 guard capture, auto-rollback on fail).
6. Write `conductor/reviews/TEXTING-DEPLOY-2003.md` with RESULT: LIVE_PASS or FAIL_OR_ROLLBACK, tip, draft_pr, live before/after JSON, rollback path/verified, evidence path that exists on disk, and free-space before/after.
7. Do NOT deploy gaps/media/voice/UI/Instinct. Those stay HOLD until texting LIVE_PASS.

## Preflight
- Confirm live still a777736 (or already new tip with LIVE_PASS — then document and stop).
- `df -g /System/Volumes/Data` free ≥ 5 before activation; if not, free only clearly stale `workspaces/webchat-*` / old lane worktrees (never delete live rollback or your own WT), re-check, or BLOCKER.
- No other active `lane-webbob-*` screens.
- Borrow 1901 runners (`reviews/deploy_texting_1901.py`, `record_texting_deploy_1901.py`, `texting_deploy_record.py`) — do not invent a parallel stack.
- Worktree: `/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-texting-disk-evidence-2003` from tip 8260f80.

## Out of scope
Gaps/media/voice/UI/Instinct deploy. Notify. Grok. Force-push. Real SMS/iMessage. Other-repo merges.

## Stop
Stop after TEXTING-DEPLOY-2003.md exists with a RESULT line (or BLOCKER). Print RESULT and live SHA.
