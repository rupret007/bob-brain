# INTEGRATE-FIXED-2143 — READY (offline code repair)

Recorded: 2026-09-28T02:57:30+00:00.

- Tip SHA: `ab5053331d128372607194a0756b893d3872c7a0`.
- Branch: `draft/webbob-integrate-2057`.
- Regular push to `brain`: verified remote tip matches the SHA above.
- Draft PR: https://github.com/rupret007/bob-brain/pull/17 — OPEN, still draft, matching head SHA; description updated.
- Worktree: `/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-integrate-2057` — clean, with upstream set to `brain/draft/webbob-integrate-2057`.
- Result: **READY** for review of the code repair. **Not LIVE PASS.**

## Repair

Each status/worker reply now persists a versioned `status_observation` containing
the exact redacted snapshot used for rendering, observation start/end times,
a microsecond UTC capture timestamp, a SHA-256 digest, rendering inputs and
conversation/request/message IDs. Reply and observation use the existing
private, fsynced atomic conversation write and authenticated history response.
Retries and restart preserve both; legacy messages are not given invented
observations. Status corrections and provider fallback replies also capture
and bind their own evidence, and model metadata cannot forge it.

Worker rows and lane details share one worker/journal sample, including failed
inspections. Active queue assignments are fully preserved. The integration gate
validates identity, time bounds, digest, exact rendered text, counts, task/model
coverage and confirmed process evidence against that saved observation. It
retains timestamped before/after diagnostics and the reply observation, then
checks that history still contains the same message and observation after work
finishes. Receipt ownership and actual worker execution/completion checks remain
strict.

Attempt 1's bounded lane prompt handling and honest unattributed CLI reporting,
and attempt 2's concise completion summaries with authenticated full-report
links, are already implemented and remain covered by passing regressions.

## Validation

| Check | Result |
| --- | --- |
| Full webchat suite | 319 passed, 0 failed |
| Full services suite | 129 passed, 0 failed |
| Offline eval suite | 56/56 passed |
| JavaScript quiet-hours checks | Passed |
| JavaScript result renderer/dialog checks | Passed |
| JavaScript syntax | Passed |
| Python compilation | Passed |
| Git whitespace check | Passed |

New regressions exercise running counts **1 before / 3 in the saved reply
observation / 5 after**, queued→claimed→running transitions, reused PIDs,
redaction, stale/foreign/malformed/tampered observations, write failure,
retry/restart, legacy history and correction/fallback replies. Evidence that
only matches an endpoint count is rejected. Existing receipt-forgery and all
17 original-message regressions pass.

To keep all test writes in the authorized worktree, services tests ran from a
hash-verified identical source copy with temporary Git repositories beside it.
The real macOS sandbox stayed enabled. An initial services run placed temporary
repositories under its protected code root and failed the commit/push fixture
(128 passed, 1 failed); fixing only that test layout produced 129/129. No tests
were skipped or weakened, and the temporary source/data copy was removed.

Local evidence in this worktree:

- `webchat/evidence/integrate-fixed-tests.json`
- `webchat/evidence/integrate-fixed-webchat.log`
- `webchat/evidence/integrate-fixed-services.log`
- `webchat/evidence/integrate-fixed-service-source.json`
- `webchat/evidence/bob-parity-eval.json`

## Live state and remaining release validation

No deployment, merge, undraft, force push or live service restart was performed.
No STOP-WEBBOB file was created. No live credentials were accessed, no Grok/xAI
provider was used, and no notification was sent to Jeff. Changes were confined
to the authorized worktree plus this explicitly requested report.

The three earlier live attempts remain failed and rolled back, as documented in
`WEBBOB-INTEGRATE-FAIL-0927.md`; the supplied live baseline is `dff84e3`.
No new live check was run. A separately authorized release still needs full live
replay, completion review and the authenticated report-link browser check.
