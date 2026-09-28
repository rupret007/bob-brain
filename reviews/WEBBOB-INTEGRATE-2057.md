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
in the failed replyq report. All 17 user messages are frozen verbatim in
webchat/fixtures/integrate_sessions_0927.json. Automated replay conversations are
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
