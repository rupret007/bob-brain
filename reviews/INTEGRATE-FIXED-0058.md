INTEGRATE-FIXED-0058

RESULT: READY

New tip: `badc732c740625dd4a15b1774db09815c7a5ed99`
Branch: `draft/webbob-integrate-2057`
Base: `2cdcce928ea6a975825829a6c10a88a99017f643`
Completed UTC: 2026-09-28T06:13:34.255853+00:00
Regular push to `brain` succeeded: `2cdcce9..badc732`. The remote branch tip
matches HEAD, and the candidate working tree is clean.

The 0058 blocker was a stale frozen capture: session
`b33fac25-3c8a-452d-8673-47d3a99dd92c` contains nine live user asks, while the
fixture contained seven. The capture now appends the exact "Hi" and
"What are you working on?" exchanges, including their historical replies and
the live updated_at value. The original seven exchanges and both other frozen
sessions are unchanged. All three source-session SHA-256 hashes are unchanged;
no live session file was truncated or rewritten. The read-only
`deploy_integrate.latest_sessions` check now passes for 19 asks (9 + 9 + 1).

"Hi" is graded as a greeting with no dispatch or unsolicited operations report.
"What are you working on?" is graded as status, using the existing strict
saved-observation checks. Extending the capture exposed that this wording had
bypassed authoritative status routing. A narrow status-pattern addition routes
it through the existing server-owned observation path. Before that change, both
seeded and lane-only replay failed turn 9 for missing authoritative status and
saved observation; both now pass. Historical model prose is retained as evidence,
not accepted as a current observation.

Empty work promises, receipt ownership and timestamps, real Gemini audit and
MiniMax test-writing jobs on turn 1 under lane-only conditions, and status honesty
retain their existing requirements. The new capture regression also verifies
that appended, removed, rewritten, or reordered asks still block preflight and
that comparison never writes session files.

| Validation | Result |
| --- | --- |
| Full webchat unittest discovery | 324/324 passed |
| Full services unittest discovery | 130/130 passed |
| Bob parity/integration evals | 77/77 passed |
| Quiet-hours and job-results JavaScript tests | Passed |
| app.js syntax, 123 Python files compiled, whitespace | Passed |
| Read-only current-session capture check | Passed |

The evals cover 39 parity checks plus all 19 captured turns in both seeded-work
and lane-only conditions. Full suites ran from the committed checkout with
isolated BOB_ROOT and canonical temporary paths outside the checkout; provider
API keys were removed from their environments. Existing macOS sandbox checks
remained active. All 362 tracked source hashes still match the tested tip.
The initial full-run logs are retained: the stale 73-eval assertion was updated
to 77, and the services fixture's /var versus /private/var path mismatch was
resolved by using canonical temporary paths. All final gates were then re-run
on `badc732c740625dd4a15b1774db09815c7a5ed99` and passed.

`webchat/evidence/integrate-tests.json` is refreshed for HEAD with
`suite_exit=0`, `eval_exit=0`, and `eval.passed=eval.total=77`.
Evidence directory: `/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-integrate-2057/reviews/integrate-fixed-0058`.
It contains full test logs, detailed evals, source hashes, before/after session
hashes, preflight and routing failure reproductions, push output, remote-tip
verification, and `validation.json`.

LIVE Gemini and MiniMax reviews MUST be re-run on `badc732c740625dd4a15b1774db09815c7a5ed99` before deploy.
The prior BOTH_PASS on `2cdcce9` does not cover this tip. This READY result covers
the offline repair only. No live review or deployment was run; no service restart,
merge, undraft, force-push, Jeff notification, or Grok/xAI call was performed.
