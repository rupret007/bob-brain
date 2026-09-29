# lane-webbob-whorunning-view-queued-0916 (QUEUED — draft-only, independent of the texting deploy chain)

You are Cursor on Jeff's Mac Mini. Add a read-only "who's running" status view to Web Bob's reports tab. Do NOT use Grok/xAI. No force-push. No Jeff notify/text. No deploy.

## Why
`conductor/reviews/WEBBOB-PARITY-0927.md` build item #5: expose `bin/who-is-running.sh` output (already text/human-readable) as a reports-tab view. This is squarely Web Bob's existing "reports with links" pattern (row 8 in that audit: `app.py:1060,1101,1278` already surfaces `STATUS.md`/`LATEST.md`/job-queue views the same way) and needs no new privilege.

## Product requirements
1. Read-only. Jeff can see current agent inventory (which Codex/Claude/Cursor/Gemini/MiniMax processes are running, DUPLICATE/STALE flags) from chat/reports tab.
2. Must not extend into the ability to start/stop/signal other agents from chat — `WEBBOB-PARITY-0927.md`'s safety rule for this item is explicit: strictly read-only, this specific capability (agent orchestration) is under a documented cloud from an earlier safety finding about SIGSTOPped sibling processes.
3. Reuse `bin/who-is-running.sh`/`.py` output verbatim (or a thin JSON wrapper around it) rather than reimplementing the dedup/DUPLICATE/STALE logic.

## Reuse
- `bin/who-is-running.sh` / `.py` (already used by desktop Bob, `BOB-HANDOFF.md:25,52`).
- Existing reports-tab wiring in `app.py:1060,1101,1278` for the display pattern.
- `mini_tools.py`'s existing read-only shell allowlist as the enforcement pattern for "no write/orchestration path exposed to the LLM."

## Deliverables
1. Chat command / reports-tab panel showing current agent inventory.
2. Test asserting the webchat code path never invokes `services/start-all.sh` or `mini-conductor` (mirror the existing assertion in `test_webchat.py:1261` for the analogous orchestration-fence check).
3. Write `conductor/reviews/WHORUNNING-VIEW-FIXED-<timestamp>.md` with tip SHA and test counts. Draft PR only.

## Stop
Stop when the fixed/ready marker exists. No deploy-order dependency, but still draft-only until Jeff prioritizes. Print tip SHA and marker path.
