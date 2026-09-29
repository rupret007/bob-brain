# INTEGRATE-FIXED-0204

RESULT: READY

New tip: `199eb193396802bbbf899292e48cd04a55f9c57e`
Branch: `draft/webbob-integrate-2057`
Base: `badc732c740625dd4a15b1774db09815c7a5ed99`
Completed UTC: 2026-09-28T07:28:48.365721+00:00

Regular push to `brain` succeeded: `badc732..199eb19`. The remote branch tip
matches HEAD, and the candidate working tree is clean.

Attempt 2 failed because no permitted source context remained: the queue had
zero queued/claimed jobs and the only observed work was the unverified
`lane-integrate-deploy-0204` screen, with no project, repository or task.
The failed replay's saved `intent_state.holds` was empty; “current holds” was
the generic no-candidate error, not evidence that a hold caused this failure.
The earlier offline lane-only fixture also supplied `lane-webbob-llm-reviews`,
which identified Web Bob and enabled its project-lane fallback. That extra lane
was absent from attempt 2. The new regression reproduced both exact rubric
errors before the fix: no real dispatch and no Gemini/MiniMax API jobs.

The production assignment planner now accepts the running Web Bob Git checkout
as API report context when no permitted ongoing job or identifiable project
lane exists. Both server-owned deployment pins must resolve to that running
checkout. Gemini receives a durable `audit` job and MiniMax a `test-writing`
job through the existing intent, queue, receipt and scheduler paths. Their
prompts explicitly state that no current task or worker execution is confirmed;
no source job ID or running-work claim is fabricated. Existing active work
still takes precedence. Missing/mismatched pins and rollback copies without
Git evidence cannot supply this context.

This fallback is limited to API reports on Web Bob. Tests verify project/global
holds, partial releases, maintenance, unavailable providers, requested project
scope and the API-only restriction. Barker and Wildflower remain parked:
their saved holds survive unchanged and no work is assigned to them.

| Validation on the new tip | Result |
| --- | --- |
| Full webchat unittest discovery | 333/333 passed |
| Full services unittest discovery | 131/131 passed |
| Bob parity/integration evals | 96/96 passed |
| Quiet-hours and job-results JavaScript tests | Passed |
| app.js syntax, 123 Python files compiled, whitespace | Passed |
| Read-only current-session capture check | All 19 asks passed |

The 96 evals comprise 39 parity checks plus all 19 captured asks in three
conditions: seeded work, the earlier project-lane-only fixture, and the actual
attempt-2 layout with matching deployment pins and no identified project lane.
The services regression uses `deploy_integrate.submit` through an isolated
in-process HTTP adapter, then the real chat, journal, scheduler, API-worker,
metered transport and report-saving code. It verifies both exact API models,
execution timestamps, task IDs, result hashes, reports and unchanged original
receipts. Provider HTTP responses, lane health and semantic acceptance are
mocked; this is offline path coverage, not proof of live provider execution.

Full suites ran after the commit using isolated BOB_ROOT and canonical temporary
paths outside the checkout, with provider credentials removed. All 362 tracked
file hashes match the tested commit. The original capture fixture is unchanged;
all 19 asks and all 792 conversation files retain their original bytes. Only the
separate `provider-health.json` runtime cache changed during this window. No
`conductor/webchat/sessions/*.json` file was written by this repair. Live code
pins also remain unchanged.

`webchat/evidence/integrate-tests.json` is refreshed with `sha==HEAD`,
`suite_exit=eval_exit=0`, and `eval.passed=eval.total=96`.
Evidence: `/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-integrate-2057/reviews/integrate-fixed-0204`. It contains the failing reproduction, diagnosis,
full test/eval logs, source and session hashes, read-only preflight, push output,
remote-tip verification and `validation.json`.

LIVE Gemini + MiniMax MUST be re-run on `199eb193396802bbbf899292e48cd04a55f9c57e` before deploy.
The previous BOTH_PASS on badc732 does not cover this new tip. A later authorized
live deployment must still pass the real replay/execution rubric; this READY
result covers the offline repair only.

No deployment, live review, service restart, merge, undraft, force-push,
Jeff notification, or Grok/xAI call was performed.
