# Web Bob integration, 2026-09-27

Branch: draft/webbob-integrate-2057. Base: draft/webbob-clean-0927.

Integrates replyq (PR #14), API workers and lane collection. The merge preserves
immutable chat receipts and the concise worker/task/model status; lane diagnostics
and recent result paths remain available in detailed status and the Jobs view.

Every dispatch reply cites the real journal job ID created for its conversation
and request. The receipt boundary rejects foreign, old, invented or uncited jobs.
Model output cannot mint receipt metadata; unsupported work acknowledgements and
empty utilization promises explicitly report that no dispatch occurred.
Contextual requests to use Gemini/MiniMax cause audit and test-writing jobs;
follow-up requests retain their worker context across restart. The conditional
fix request creates a coding task. No-job status says idle, and pending assignments
show their task and waiting-to-run state. Council uses the same durable dispatcher.

Regression source: the original sessions b33fac25, 8126301c and 65a5d782 named
in the failed replyq report. All 19 current user messages are frozen verbatim in
webchat/fixtures/integrate_sessions_0927.json (9 + 9 + 1). Automated replay conversations are
excluded. The optional MiniMax eval/grade and Gemini 2020 audit files were absent.

The integration gate verifies authenticated replies against the rubric, checks
receipt ownership and timestamps against the journal and Jobs API, waits for
actual worker execution and completed API reports, and preserves original receipt
text. It snapshots both code roots under rollbacks/, restarts only webchat and
job-runner, and verifies local/public /api/version. Failed replays revoke only
their own outstanding claims before rollback so old workers never receive new API
job kinds. Original sessions, completed results and draft worktrees are preserved.

Validation and live results are recorded under conductor/reviews/WEBBOB-INTEGRATE-*
and conductor/LOOP-INTEGRATE-LIVE-0927.txt after the gate and reply review succeed.
No merges, undrafts, force-pushes or STOP-WEBBOB files are part of this release.

## Status observation repair, 2143 (offline only)

Status replies now save a `status_observation` with the exact redacted snapshot
used to render their text. The versioned record includes observation start/end
times, the snapshot's microsecond UTC timestamp and SHA-256, rendering inputs,
and conversation/request/message IDs. It shares the reply's private, fsynced
atomic conversation write and authenticated history response. Retries, restart,
and later worker transitions preserve the original record; historical replies
without observations are not backfilled. Model metadata cannot supply it.

Worker rows and lane details share one process/journal sample, including failed
inspections. All pending and claimed assignments remain in the saved evidence;
prompt encoding still applies its existing size limit. The integration gate
checks the saved observation's identity, timestamps, digest, rendered text,
counts, tasks, models and process evidence. Before/after samples are timestamped
diagnostics. The gate preserves the reply observation in its artifact and checks
that authenticated history still contains the same record after jobs finish.
Receipt ownership and actual execution/completion checks remain strict.

Offline validation: **319 webchat tests, 129 services tests, 56/56 evals** passed.
JavaScript quiet-hours and result-dialog checks, JavaScript syntax, Python
compilation and whitespace checks passed. Regressions cover the 1→3→5 startup
race, queued/claimed/running transitions, reused PIDs, redaction, malformed or
foreign evidence, write failure, restart/retry, correction/fallback replies,
and the existing bounded lane greeting and concise linked completion behavior.
Services tests ran from a hash-verified source copy inside this worktree, with
temporary repositories beside that copy so the real macOS sandbox continued to
protect the code directory. An initial run with temporary repositories under
the protected code directory correctly blocked its commit/push fixture.

**READY for review of this code repair.** No new live attempt ran; the prior
three rollbacks remain failures. Full live replay, completion review and the
authenticated report-link browser check still require a separately authorized
release. This is not a LIVE PASS.

## Frozen capture repair, 0058 (offline only)

The b33fac25 capture now includes Jeff's two appended live turns, "Hi" and
"What are you working on?", with their original replies retained as historical
evidence. The greeting must not dispatch work or introduce an operations report.
The current-work question now routes through the authoritative status path and
must pass the existing saved-observation rubric. The first seven expectations,
the other two sessions, receipt checks, and lane-only API-worker dispatch checks
remain unchanged. Session comparison still rejects added, removed, rewritten,
or reordered asks and never rewrites the live session files.

LIVE Gemini and MiniMax reviews must be re-run on the new tip before deployment.
Offline validation and the pushed SHA are recorded in
conductor/reviews/INTEGRATE-FIXED-0058.md.
