# Strict LIVE tip review draft/webbob-integrate-2057 @ab50533 (ab5053331d128372607194a0756b893d3872c7a0)

SCOPE: apiworkers / lane awareness / status_observation integrate ONLY.
Focus: status reply observations (digest, atomic write, history bind), worker/journal sample, integration gate evidence.
Do NOT fail for missing voice/media/texting/iPhone. Ignore out-of-lane gaps.
Prior live attempts on older tips failed 3× (WEBBOB-INTEGRATE-FAIL-0927.md); this tip ab50533 claims offline READY (319 webchat + 129 services + 56 evals).
Cite only real symbols in provided sources. List CRITICAL/HIGH real bugs only.
End with exactly: VERDICT: PASS or VERDICT: FAIL

## FIXED-2143 summary
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

## git log vs live dff84e3
ab50533 Persist status reply observations and validate their exact evidence
61ad058 Open authenticated job results from chat and grade every completion
969aecb Summarize completed jobs in chat and link full authenticated results
2c12838 Give follow-up fixes a complete concise receipt title
ad28873 Bound lane snapshots and distinguish unassigned CLI activity; harden rollback
4fc9f35 Use observed project lanes as explicit bounded API review context
08ff353 Require turn-owned dispatch receipts and execute contextual LLM assignments
9b35338 Merge lane collection with concise replies and opt-in lane diagnostics
079fe7a Merge API workers while preserving immutable dispatch receipts
af68f5b Assign Gemini and MiniMax to real report-producing jobs
0acad5a Clarify Codex performed the independent live rubric review
ef60d84 Record failed live reply rubric and verified rollback to dff84e3
1cd1d77 Gate Web Bob replies with concise facts, immutable receipts and live rollback checks
446409d Add read-only lane collector so Web Bob reports Bob screen lanes truthfully.
15d0ff4 Fix Web Bob reply quality: no unknown-task wording, no empty promises, no raw log dumps
## diffstat vs live dff84e3
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
## key files (status observation / workers)
--- webchat/app.py (grep status_observation / observation) ---
229:        from status_observation import bind_observation
234:        conversation["messages"][-1]["status_observation"] = bind_observation(observation, conversation)
627:                from status_observation import bind_observation
632:                    answer["status_observation"] = bind_observation(observation, value)
--- webchat/task_dispatch.py (grep status_observation / observation) ---
--- webchat/providers.py (grep status_observation / observation) ---
## recent status_observation-related hunks (bounded)
+++ b/webchat/README.md
@@ -59,10 +59,26 @@ tools; success requires the server to verify the changed file and its contents.
@@ -81,7 +97,7 @@ are excluded. Open screens without a confirmed worker and unavailable checks are
@@ -106,7 +122,8 @@ Max mode: review this design and supplied evidence ...
@@ -154,9 +171,10 @@ CLI slot falls through to the next provider. Handback: `conductor/handback/`
+++ b/webchat/app.py
@@ -224,6 +224,18 @@ class Chat(TaskDispatch):
+        from status_observation import bind_observation
+        conversation["messages"][-1]["status_observation"] = bind_observation(observation, conversation)
+        # fsynced atomic conversation write. Retries/restarts keep both intact.
@@ -336,9 +348,9 @@ class Chat(TaskDispatch):
@@ -349,6 +361,14 @@ class Chat(TaskDispatch):
@@ -419,26 +439,8 @@ class Chat(TaskDispatch):
@@ -467,8 +469,8 @@ class Chat(TaskDispatch):
@@ -540,16 +542,12 @@ class Chat(TaskDispatch):
@@ -621,10 +619,19 @@ class Chat(TaskDispatch):
+                from status_observation import bind_observation
+                    answer["status_observation"] = bind_observation(observation, value)
+++ b/webchat/bob_parity_eval.py
@@ -23,7 +23,14 @@ def _case(name: str, ok: bool, detail: str = "") -> dict:
@@ -66,29 +73,114 @@ def run_eval(root: Path | None = None) -> dict:
+++ b/webchat/deploy_integrate.py
@@ -0,0 +1,263 @@
+                                observations={"reply": answer.get("status_observation"),
+                        receipt.get("status_observation") == exchange["observations"]["reply"],
+++ b/webchat/deploy_parity.py
@@ -23,7 +23,7 @@ def write(path, value):
@@ -74,8 +74,10 @@ def restart(root, pins):
+++ b/webchat/deploy_replyq.py
@@ -0,0 +1,285 @@
+++ b/webchat/dispatch_receipts.py
@@ -0,0 +1,67 @@
+++ b/webchat/fixtures/integrate_sessions_0927.json
@@ -0,0 +1,91 @@
+++ b/webchat/integration_rubric.py
@@ -0,0 +1,149 @@
+        from status_observation import observation_errors
+        evidence_errors = observation_errors(answer, exchange["message"], cid, started,
+        observed = answer["status_observation"]["snapshot"]
+++ b/webchat/jobs_view.py
@@ -8,8 +8,9 @@ import time
@@ -144,9 +145,36 @@ def costs(root):
@@ -160,6 +188,7 @@ def build_jobs_view(root: Path, *, now=None):
@@ -172,8 +201,23 @@ def build_jobs_view(root: Path, *, now=None):
@@ -187,6 +231,17 @@ def build_jobs_view(root: Path, *, now=None):
+++ b/webchat/lane_collector.py
@@ -0,0 +1,261 @@
+++ b/webchat/live_redeploy_check.py
@@ -121,7 +121,8 @@ def verify_four(client, root, output):
@@ -148,12 +149,12 @@ def verify_four(client, root, output):
+++ b/webchat/live_replies_check.py
@@ -33,26 +33,24 @@ def verify_replies(client, root, output, timeout=1800):
+++ b/webchat/live_status_snapshot.py
@@ -18,7 +18,7 @@ _HOME = re.compile(r"/Users/[^\s\"']+")
@@ -189,6 +189,7 @@ def _queue_jobs(jobs_map: dict[str, dict], sessions: set[str], *, limit: int = 2
@@ -440,6 +441,14 @@ def build_live_status_snapshot(root: Path, *, now: float | None = None) -> dict:
@@ -450,11 +459,12 @@ def build_live_status_snapshot(root: Path, *, now: float | None = None) -> dict:
@@ -474,7 +484,9 @@ def build_live_status_snapshot(root: Path, *, now: float | None = None) -> dict:
@@ -483,7 +495,8 @@ def build_live_status_snapshot(root: Path, *, now: float | None = None) -> dict:
@@ -503,8 +516,12 @@ def encode_snapshot(snapshot: dict, max_chars: int) -> tuple[str, bool]:
+++ b/webchat/max_mode.py
@@ -4,6 +4,7 @@ import re
@@ -54,6 +55,7 @@ def plan(root, prompt, kind):
@@ -69,11 +71,11 @@ def enqueue(root, conversation_id, intent):
@@ -81,11 +83,13 @@ def merge_text(rows):
+++ b/webchat/providers.py
@@ -24,13 +24,21 @@ RULES = """Read BOB-HANDOFF.md + bob-brain/ + conductor/handback/ (BOB-STATE.md,
@@ -44,6 +52,11 @@ The model proposes; authorized server handlers execute and return action cards.
@@ -65,12 +78,19 @@ in Reference snapshots. Say plainly what is moving, which worker/model is doing
+++ b/webchat/reply_authority.py
@@ -1,9 +1,11 @@
@@ -18,7 +20,8 @@ NO_JOB_NOTICE = re.compile(
@@ -72,12 +75,43 @@ def _cooldown(snap, name):
@@ -98,13 +132,135 @@ def _work_line(row, detailed=False):
@@ -155,12 +311,25 @@ def correcting_status(text, conversation):
+    from status_observation import redact_snapshot, snapshot_digest
+                           snapshot=snap, snapshot_sha256=snapshot_digest(snap))
@@ -171,15 +340,19 @@ def enforce(root, text, answer, conversation=None):
+++ b/webchat/static/app.js
@@ -41,6 +41,8 @@ if ($("login-form")) {
@@ -66,6 +68,18 @@ if ($("login-form")) {
@@ -317,6 +331,11 @@ if ($("login-form")) {
@@ -955,14 +974,7 @@ if ($("login-form")) {
diff --git a/webchat/status_observation.py b/webchat/status_observation.py
+++ b/webchat/status_observation.py
@@ -0,0 +1,86 @@
+"""Evidence saved atomically with each operational reply, never supplied by a model."""
+def snapshot_digest(snapshot):
+    return hashlib.sha256(payload.encode()).hexdigest()
+def observation_errors(answer, question, conversation_id, started, finished):
+    observation = answer.get("status_observation")
+        if observation["snapshot_sha256"] != snapshot_digest(snap):
+            errors.append("status observation digest mismatch")
+++ b/webchat/task_dispatch.py
@@ -12,12 +12,13 @@ from pathlib import Path
@@ -96,7 +97,7 @@ def parse_work(text):
@@ -105,18 +106,13 @@ def parse_work(text):
@@ -145,7 +141,7 @@ def project_plan(root, description, names, worker):
@@ -173,7 +169,9 @@ def project_plan(root, description, names, worker):
@@ -183,17 +181,79 @@ def project_plan(root, description, names, worker):
@@ -225,6 +285,7 @@ class TaskDispatch:
@@ -275,7 +336,7 @@ class TaskDispatch:
@@ -286,18 +347,23 @@ class TaskDispatch:
@@ -310,9 +376,21 @@ class TaskDispatch:
@@ -330,7 +408,6 @@ class TaskDispatch:
@@ -345,12 +422,11 @@ class TaskDispatch:
@@ -376,9 +452,12 @@ class TaskDispatch:
+++ b/webchat/test_api_workers.py
@@ -0,0 +1,153 @@
+++ b/webchat/test_chat_intent.py
@@ -141,8 +141,10 @@ class IntentTests(Fixture):
+++ b/webchat/test_deploy_integrate.py
@@ -0,0 +1,75 @@
+++ b/webchat/test_deploy_replyq.py
@@ -0,0 +1,76 @@
+++ b/webchat/test_dispatch.py
@@ -42,12 +42,15 @@ class ChatDispatchTests(Fixture):
@@ -56,9 +59,9 @@ class ChatDispatchTests(Fixture):
@@ -90,8 +93,9 @@ class ChatDispatchTests(Fixture):
@@ -108,7 +112,7 @@ class ChatDispatchTests(Fixture):
## test names mentioning observation/status
318:    def test_progress_status_is_local_plain_and_does_not_start_duplicate_work(self):
471:    def test_busy_cli_lane_falls_through_to_next_provider(self):
513:    def test_live_status_snapshot_builder_reads_jobs_and_lanes(self):
537:    def test_gemini_prompt_includes_live_status_snapshot(self):
558:    def test_minimax_call_receives_live_status_snapshot_prompt(self):
607:    def test_busy_cli_lane_does_not_start_competing_process(self):
854:    def test_status_chip_answers_from_state_without_model(self):
883:    def test_self_improve_status_from_handback(self):
913:    def test_status_hides_drill_open_asks(self):
bob-parity-eval.json
handback-drill.json
integrate-fixed-service-source.json
integrate-fixed-services.log
integrate-fixed-tests.json
integrate-fixed-webchat.log
integrate-tests.json
iphone-r10
iphone-r15
iphone-r8
ready-drill.json
