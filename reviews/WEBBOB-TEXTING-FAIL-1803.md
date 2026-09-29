# WEBBOB-TEXTING-FAIL-1803

When: 2026-09-28 ~18:25 CT
Tip: 3b522c51331f66f6b58c0ff8a1ecf228d1ae961f
Branch: draft/webbob-texting-guard-consistency-fix-1803
Draft PR: https://github.com/rupret007/bob-brain/pull/28
Clean merge: f4cb88ad1a009a05282bef19a2eb34a023bb00c5 (tree == 3b522c5)
LIVE: BOTH_PASS attempt11 (Gemini+MiniMax) — TEXTING-LIVE-1803.md
FIXED: TEXTING-FIXED-1803.md

TEXTING-DEPLOY-1803 RESULT: FAIL_OR_ROLLBACK
- exit: 1
- rollback_path: not activated (live stayed a777736; rollback_verified True with snapshot not activated)
- Texting smoke: not passed
- Live replay: 0 captured turns / 0 passed / 0 executed jobs
- 1035/dd47c4cb, f2c47c4c, 20bfc6f MiniMax live jobs: not passed (reports unavailable)
- 1803 guard-consistency capture: not passed
- 1403 completion JSON + prior status-dump/incomplete-verification: not passed
- Evidence path cited: WEBBOB-TEXTING-DEPLOYMENT-0927-attempt11.json — **file missing on disk after deploy exit**
- Failure line: "Deployment exit, evidence, or live SHA did not pass"
- Preflight still listed active Codex screen `lane-webbob-texting-guard-consistency-fix-1803` (60559) among screens — likely deploy wrapper aborted before/during activation (lane isolation / evidence write / smoke) without producing attempt11 JSON.

Live before/after remained a777736b3f0a37c82b0c4c62be8c91117c4c9881.

## Authoritative root cause (from lane-webbob-texting-guard-consistency-fix-1803 EXIT)
Attempt11 stopped **before activation** because the launcher supplied a **relative Python path**, causing `ModuleNotFoundError: deploy_parity`. Live remained `a777736`. Product tip `3b522c5` had already passed offline tests, probes, and fresh BOTH_PASS reviews and merged via PR #28.
