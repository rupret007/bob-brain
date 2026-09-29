# lane-webbob-texting-screen-isolation-fix-1403

You are Codex on Jeff's Mac Mini. Fix the Web Bob texting *deploy restart screen-isolation guard* that caused TEXTING-DEPLOY-1307 FAIL_OR_ROLLBACK, then finish one gated redeploy of the already-reviewed tip. Do NOT use Grok/xAI. No force-push. No Jeff notify/text. No real SMS/iMessage.

## Authoritative failure — TEXTING-DEPLOY-1307 RESULT: FAIL_OR_ROLLBACK (~13:16 CT)
- Tip `eb8029ed9fa17b26becb5487150b3d8981a5a0bb` on `draft/webbob-texting-jobcomplete-fix-1207` (draft PR #24) still has TEXTING-FIXED-1207 / TEXTING-FIXED-1307 VERIFIED-ALREADY-FIXED + offline suites green + LIVE Gemini+MiniMax BOTH_PASS (TEXTING-LIVE-1207.md attempt6). Product tip unchanged.
- Clean merge already on `draft/webbob-clean-0927` as `e6c91a2efbf11d3c922469bcd912e675aea29c14` (tree == eb8029e).
- Ancestry/object bug from 1207 is fixed in `conductor/reviews/deploy_texting_1307.py` (checks against bob-brain after fetch). That part worked.
- Deploy *activated* then failed the restart screen guard and rolled back:
  - Failure string: **Unrelated screens changed during restart**
  - Evidence: `conductor/reviews/WEBBOB-TEXTING-DEPLOYMENT-0927-attempt6.json`
  - `evidence.restart.other_screens_unchanged == false`
  - `restarted_services: ["webchat", "job-runner"]` (expected)
  - before had `svc-project-tick` = `13512.svc-project-tick`; after lost that session entirely
  - Durable unrelated screens kept identity: svc-reviewer 45974, svc-dashboard-updater 17509, svc-disk-watch 94801, svc-watchdog 53542, svc-webbob-reviewers 77277, and the deploying lane screen
  - svc-webchat / svc-job-runner PIDs changed (expected — those are the restarted pair)
  - Rollback `rollbacks/webbob-texting-20260928-131601` verified; live stayed `a777736`
  - Smoke / 1035-dd47c4cb MiniMax completion replay / live Jeff session replay never ran (stopped at screen guard)
- Root cause in tip `webchat/deploy_parity.py` → `restart()` (imported because record wrapper runs with `cwd=workspaces/webbob-texting-jobcomplete-1207/webchat`):
  ```
  unrelated = {name: identity for name, identity in before.items()
               if name not in ("svc-webchat", "svc-job-runner") and name not in expected_exits}
  other_screens_unchanged = all(after.get(name) == identity for name, identity in unrelated.items())
  ```
  Any ephemeral/optional before-screen (e.g. `svc-project-tick`, `lane-*` coding screens) that exits during the supervisor-locked restart trips FAIL. `expected_exits` is currently passed cancelled *job IDs*, which never match screen names — do not treat that as a working screen allowlist.

## Live baseline
- Local `/api/version` at http://127.0.0.1:8787/api/version → short_sha `a777736` full `a777736b3f0a37c82b0c4c62be8c91117c4c9881` built_at 2026-09-28T09:04:32+00:00
- Do **not** re-open the MiniMax deliverable / texting product fix unless a new tip is required. Prefer fixing the deploy restart screen-isolation so the existing BOTH_PASS tip can proceed.

## Goal — preferred minimal fix (reuse, don't invent)
1. Harden screen-isolation so only *durable unrelated conductor services* must keep the same screen identity across restart. Proven shape:
   - Always allow (ignore identity change): `svc-webchat`, `svc-job-runner` (the restarted pair).
   - Require identity unchanged for durable peers that must not be disturbed: at least `svc-reviewer`, `svc-dashboard-updater`, `svc-disk-watch`, `svc-watchdog`, `svc-webbob-reviewers` (and any other long-lived `svc-*` that is not the restarted pair and is not known-optional).
   - Do **not** FAIL when optional/ephemeral sessions appear or disappear: `svc-project-tick`, any `lane-*` / coding-agent screens, or other non-durable names. Their exit must not set `other_screens_unchanged=False`.
   - Still FAIL if a durable unrelated svc-* screen changes PID/identity or vanishes unexpectedly.
   - Prefer implementing the hardened check in `conductor/reviews/` (e.g. `deploy_texting_1403.py` adapted from `deploy_texting_1307.py`, plus `record_texting_deploy_1403.py` from the 1307 wrapper) so product tip `eb8029e` stays unchanged. If you must touch tip `deploy_parity.restart`, keep behavior identical for product paths and isolate the allowlist change.
   - Keep ancestry fix from 1307 (bob-brain fetch + exit-128 retry). Keep all other gates.
2. Tip policy:
   - If tip stays `eb8029e`: write `TEXTING-FIXED-1403.md` as **VERIFIED-ALREADY-FIXED** (product unchanged; deploy-runner screen-isolation fix path). Reuse TEXTING-LIVE-1207.md BOTH_PASS. Do not redo offline suites.
   - If tip must change: branch `draft/webbob-texting-screen-isolation-fix-1403` from `eb8029e`, keep product texting behavior identical, re-run offline suites + fresh LIVE Gemini+MiniMax → TEXTING-LIVE-1403.md, regular-merge into `draft/webbob-clean-0927`, update draft PR if needed. Never force-push.
3. Redeploy ONE tip with fresh rollback under `rollbacks/webbob-texting-YYYYMMDD-HHMMSS` ONLY when gates pass. Next free attempt slot is **7+** (attempt6 used). Full gates: exact-tip offline receipts (if tip unchanged reuse), BOTH_PASS, draft PR #24 / clean e6c91a2, texting smoke, 19 frozen live turns, exact 1035/dd47c4cb MiniMax job with accepted saved deliverable, auto-rollback to a777736 on any fail with local+public `/api/version` verify.
4. Write `conductor/reviews/TEXTING-DEPLOY-1403.md` with RESULT: LIVE_PASS or FAIL_OR_ROLLBACK, tip, draft_pr, live before/after JSON, rollback path/verified.
5. Do NOT deploy gaps/media/voice/UI/Instinct. Those stay HOLD until texting LIVE_PASS.

## Preflight
- Confirm live still a777736 (or already new tip with LIVE_PASS — then document and stop).
- Confirm no other active `lane-webbob-*` screens before you start the deploy (svc-* only is OK; your own lane screen is OK).
- Confirm bob-brain has e6c91a2 and ancestry eb8029e ⊆ e6c91a2.
- If Gemini/MiniMax unhealthy and a fresh LIVE is required, write BLOCKER and stop before deploy.
- Add isolated unit/guard tests for the new screen filter (durable peer PID change → fail; svc-project-tick / lane-* exit → pass; restarted pair change → pass).

## Out of scope
Gaps/media/voice/UI/Instinct deploy. Notify. Grok. Force-push. Real SMS/iMessage.

## Stop
Stop after TEXTING-DEPLOY-1403.md exists with a RESULT line (or BLOCKER). Print RESULT and live SHA.
