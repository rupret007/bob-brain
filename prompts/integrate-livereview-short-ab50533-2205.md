Strict INTEGRATE-ONLY code review of tip ab5053331d128372607194a0756b893d3872c7a0 (status_observation + lane awareness).
Offline claim: 319 webchat + 129 services + 56 evals READY. List real CRITICAL/HIGH only.
End with VERDICT: PASS or VERDICT: FAIL
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
 webchat/README.md                             |  34 ++-
 webchat/app.py                                |  71 ++++---
 webchat/bob_parity_eval.py                    | 108 +++++++++-
 webchat/deploy_integrate.py                   | 263 ++++++++++++++++++++++++
 webchat/deploy_parity.py                      |   6 +-
 webchat/deploy_replyq.py                      | 285 ++++++++++++++++++++++++++
 webchat/dispatch_receipts.py                  |  67 ++++++
 webchat/fixtures/integrate_sessions_0927.json |  91 ++++++++
 webchat/integration_rubric.py                 | 149 ++++++++++++++
 webchat/jobs_view.py                          |  61 +++++-
 webchat/lane_collector.py                     | 261 +++++++++++++++++++++++
 webchat/live_redeploy_check.py                |   9 +-
 webchat/live_replies_check.py                 |  18 +-
 webchat/live_status_snapshot.py               |  25 ++-
 webchat/max_mode.py                           |  14 +-
 webchat/providers.py                          |  42 +++-
 webchat/reply_authority.py                    | 193 ++++++++++++++++-
 webchat/static/app.js                         |  28 ++-
 webchat/status_observation.py                 |  86 ++++++++
 webchat/task_dispatch.py                      | 147 ++++++++++---
 webchat/test_api_workers.py                   | 153 ++++++++++++++
 webchat/test_chat_intent.py                   |   6 +-
 webchat/test_deploy_integrate.py              |  75 +++++++
 webchat/test_deploy_replyq.py                 |  76 +++++++
 webchat/test_dispatch.py                      |  34 +--
 webchat/test_integrate_2057.py                | 192 +++++++++++++++++
 webchat/test_job_results_js.mjs               |  39 ++++
 webchat/test_lane_collector.py                |  69 +++++++
 webchat/test_live_status_snapshot.py          |  26 +++
 webchat/test_replies_session.py               |  21 +-
 webchat/test_reply_authority.py               |  25 ++-
 webchat/test_status_observation.py            | 200 ++++++++++++++++++
 webchat/test_webbob_replyq_1856.py            | 280 +++++++++++++++++++++++++
 webchat/test_webchat.py                       |  18 +-
 webchat/worker_activity.py                    |  14 +-
 webchat/worker_assignment.py                  | 119 +++++++++++
 webchat/worker_evidence.py                    |  52 ++++-
 37 files changed, 3168 insertions(+), 189 deletions(-)
