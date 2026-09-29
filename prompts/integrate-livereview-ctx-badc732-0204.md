# Strict LIVE tip review draft/webbob-integrate-2057 @badc732 (badc732c740625dd4a15b1774db09815c7a5ed99)

SCOPE: apiworkers / lane awareness / status_observation integrate ONLY + session-freeze capture repair from INTEGRATE-FIXED-0058.
Focus: status reply observations (digest, atomic write, history bind), worker/journal sample, frozen Jeff session capture honesty, status-pattern routing for 'What are you working on?', integration gate evidence.
Do NOT fail for missing voice/media/texting/iPhone. Ignore out-of-lane gaps.
Prior BOTH_PASS on tip 2cdcce9 does NOT cover this tip — re-review required after freeze-fix push badc732.
Offline claim (INTEGRATE-FIXED-0058 READY): 324 webchat + 130 services + 77 evals; read-only current-session capture check passed.
Cite only real symbols in provided sources. List CRITICAL/HIGH real bugs only.
End with exactly one line: VERDICT: PASS or VERDICT: FAIL

## INTEGRATE-FIXED-0058 summary
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

## git log vs live dff84e3
badc732 Update parity total for the two appended captured turns
504fdbc Refresh frozen Jeff turns and route current-work status honestly
2cdcce9 Dispatch API reports from identified project lanes without active jobs
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

## commits since prior BOTH_PASS tip 2cdcce9
badc732 Update parity total for the two appended captured turns
504fdbc Refresh frozen Jeff turns and route current-work status honestly

## diffstat vs live dff84e3 (webchat/)
 webchat/README.md                             |  34 ++-
 webchat/app.py                                |  71 ++++---
 webchat/bob_parity_eval.py                    | 109 +++++++++-
 webchat/deploy_integrate.py                   | 263 ++++++++++++++++++++++++
 webchat/deploy_parity.py                      |   6 +-
 webchat/deploy_replyq.py                      | 285 ++++++++++++++++++++++++++
 webchat/dispatch_receipts.py                  |  67 ++++++
 webchat/fixtures/integrate_sessions_0927.json |  99 +++++++++
 webchat/integration_rubric.py                 | 156 ++++++++++++++
 webchat/jobs_view.py                          |  61 +++++-
 webchat/lane_collector.py                     | 261 +++++++++++++++++++++++
 webchat/live_redeploy_check.py                |   9 +-
 webchat/live_replies_check.py                 |  18 +-
 webchat/live_status_snapshot.py               |  25 ++-
 webchat/max_mode.py                           |  14 +-
 webchat/providers.py                          |  42 +++-
 webchat/reply_authority.py                    | 195 +++++++++++++++++-
 webchat/static/app.js                         |  28 ++-
 webchat/status_observation.py                 |  86 ++++++++
 webchat/task_dispatch.py                      | 147 ++++++++++---
 webchat/test_api_workers.py                   | 153 ++++++++++++++
 webchat/test_chat_intent.py                   |   6 +-
 webchat/test_deploy_integrate.py              | 111 ++++++++++
 webchat/test_deploy_replyq.py                 |  76 +++++++
 webchat/test_dispatch.py                      |  34 +--
 webchat/test_integrate_2057.py                | 256 +++++++++++++++++++++++
 webchat/test_job_results_js.mjs               |  39 ++++
 webchat/test_lane_collector.py                |  69 +++++++
 webchat/test_live_status_snapshot.py          |  26 +++
 webchat/test_replies_session.py               |  21 +-
 webchat/test_reply_authority.py               |  25 ++-
 webchat/test_status_observation.py            | 200 ++++++++++++++++++
 webchat/test_webbob_replyq_1856.py            | 280 +++++++++++++++++++++++++
 webchat/test_webchat.py                       |  18 +-
 webchat/worker_activity.py                    |  14 +-
 webchat/worker_assignment.py                  | 140 +++++++++++++
 webchat/worker_evidence.py                    |  52 ++++-
 37 files changed, 3306 insertions(+), 190 deletions(-)

## patch since 2cdcce9 (freeze fix — primary review target)
commit badc732c740625dd4a15b1774db09815c7a5ed99
Author: Jeff Story <jeffstory@Jeffs-Mac-mini.local>
Date:   Mon Sep 28 01:09:53 2026 -0500

    Update parity total for the two appended captured turns
---
 webchat/test_webchat.py | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)

diff --git a/webchat/test_webchat.py b/webchat/test_webchat.py
index 2a43dd0..96798f6 100644
--- a/webchat/test_webchat.py
+++ b/webchat/test_webchat.py
@@ -1231,7 +1231,7 @@ class HandbackJobTests(Fixture):
         state_ledger.write_now(self.root, "offline parity fixture", sha="fedcba1")
         result = run_eval(self.root)
         self.assertEqual(result["passed"], result["total"], result["cases"])
-        self.assertEqual(result["total"], 73)
+        self.assertEqual(result["total"], 77)
 
     def test_catchup_event_ack_cursor(self):
         ledger_dir = Path(__file__).resolve().parent.parent / "state"

commit 504fdbc2e89b401ce063916e59a3c1ac05dab148
Author: Jeff Story <jeffstory@Jeffs-Mac-mini.local>
Date:   Mon Sep 28 01:07:52 2026 -0500

    Refresh frozen Jeff turns and route current-work status honestly
---
 webchat/fixtures/integrate_sessions_0927.json | 10 ++++++-
 webchat/integration_rubric.py                 |  2 +-
 webchat/reply_authority.py                    |  2 +-
 webchat/test_deploy_integrate.py              | 38 ++++++++++++++++++++++++++-
 webchat/test_integrate_2057.py                |  7 +++--
 5 files changed, 53 insertions(+), 6 deletions(-)

diff --git a/webchat/fixtures/integrate_sessions_0927.json b/webchat/fixtures/integrate_sessions_0927.json
index d221faf..23bb587 100644
--- a/webchat/fixtures/integrate_sessions_0927.json
+++ b/webchat/fixtures/integrate_sessions_0927.json
@@ -3,7 +3,7 @@
   "sessions": [
     {
       "source_id": "b33fac25-3c8a-452d-8673-47d3a99dd92c",
-      "updated_at": 1790558292.175429,
+      "updated_at": 1790571497.5886872,
       "exchanges": [
         {
           "message": "Ok remember you can use Gemini and Minimax for the ongoing jobs.",
@@ -32,6 +32,14 @@
         {
           "message": "Ok if you find any issues fix them.",
           "before": "Got it—fix issues found along the way, test the fixes, and keep changes in draft for your review."
+        },
+        {
+          "message": "Hi",
+          "before": "Hi Jeff!"
+        },
+        {
+          "message": "What are you working on?",
+          "before": "Right now, I'm running the `lane-webbob-llm-reviews` screen, which has been active for about 3 hours and 47 minutes. It's reviewing LLM outputs for Web Bob."
         }
       ]
     },
diff --git a/webchat/integration_rubric.py b/webchat/integration_rubric.py
index 6f11726..9a988ac 100644
--- a/webchat/integration_rubric.py
+++ b/webchat/integration_rubric.py
@@ -10,7 +10,7 @@ from dispatch_receipts import NO_DISPATCH, claims_dispatch, receipt_errors
 def sessions():
     rows = json.loads(Path(__file__).with_name("fixtures").joinpath("integrate_sessions_0927.json").read_text())["sessions"]
     for session in rows:
-        kinds = (["assign", "assign", "status", "status", "status", "assign", "fix"]
+        kinds = (["assign", "assign", "status", "status", "status", "assign", "fix", "greeting", "status"]
                  if session["source_id"].startswith("b33fac") else
                  ["missing", "status", "status", "status", "status", "projects4", "greeting", "status", "status"]
                  if session["source_id"].startswith("8126301c") else ["projects2"])
diff --git a/webchat/reply_authority.py b/webchat/reply_authority.py
index a2f6557..34604c1 100644
--- a/webchat/reply_authority.py
+++ b/webchat/reply_authority.py
@@ -22,7 +22,7 @@ NO_JOB_NOTICE = re.compile(
 STATUS_QUESTION = re.compile(
     r"\b(?:status|resources?|workers? doing|each (?:worker|model)|all (?:workers|models|LLMs)|"
     r"work being performed|what about (?:Gemini|MiniMax|Codex|Claude|Cursor)|"
-    r"(?:what(?:['’]s| is) (?:working on what|going on)|each llm)|"
+    r"(?:what(?:['’]s| is) (?:working on what|going on)|what are you working on|each llm)|"
     r"everything (?:going|running)|how(?:['’]s| is| we)? (?:everything|it going|we doing)|"
     r"(?:is|are) (?:it|anything|everything|things|the (?:work|jobs?|workers?)) "
     r"(?:going(?: now)?|moving(?: along)?|running|making progress)|(?:any|making) progress|"
diff --git a/webchat/test_deploy_integrate.py b/webchat/test_deploy_integrate.py
index e138ba0..5f7d078 100644
--- a/webchat/test_deploy_integrate.py
+++ b/webchat/test_deploy_integrate.py
@@ -8,12 +8,48 @@ import unittest
 from pathlib import Path
 from unittest.mock import MagicMock, patch
 
-from deploy_integrate import main
+from deploy_integrate import latest_sessions, main
 from integration_rubric import check_reply, style_errors, sessions
 from task_dispatch import task_queue
 
 
 class IntegrationGate(unittest.TestCase):
+    def test_current_capture_matches_without_rewriting_sessions_and_rejects_drift(self):
+        with tempfile.TemporaryDirectory() as folder:
+            root = Path(folder)
+            saved_sessions = root / "conductor/webchat/sessions"
+            saved_sessions.mkdir(parents=True)
+            captured = sessions()
+            original = {}
+            for source in captured:
+                path = saved_sessions / (source["source_id"] + ".json")
+                messages = []
+                for exchange in source["exchanges"]:
+                    messages.extend([dict(role="user", content=exchange["message"]),
+                                     dict(role="assistant", content=exchange["before"])])
+                path.write_text(json.dumps(dict(messages=messages)))
+                original[path] = path.read_bytes()
+            self.assertEqual(latest_sessions(root), captured)
+            self.assertEqual({p: p.read_bytes() for p in original}, original)
+            for path, payload in original.items():
+                saved = json.loads(payload)
+                messages = saved["messages"]
+                for change, changed in (
+                    ("appended ask", messages + [dict(role="user", content="Any updates?")]),
+                    ("removed ask", messages[2:]),
+                    ("rewritten ask", [dict(role="user", content="A different ask"), *messages[1:]]),
+                    ("reordered asks", messages[2:] + messages[:2]),
+                ):
+                    if changed == messages:
+                        continue  # A single-ask session has no alternate user order.
+                    with self.subTest(session=path.stem, change=change):
+                        path.write_text(json.dumps(dict(messages=changed)))
+                        before = {p: p.read_bytes() for p in original}
+                        with self.assertRaisesRegex(RuntimeError, "Original Jeff session changed"):
+                            latest_sessions(root)
+                        self.assertEqual({p: p.read_bytes() for p in original}, before)
+                        path.write_bytes(payload)
+
     def test_rubric_rejects_all_failed_deployment_promises(self):
         for text in ("I'll make sure they're utilized.", "The system is actively adding work for them.",
                      "I'll focus on getting everything running.", "All LLMs are healthy and ready."):
diff --git a/webchat/test_integrate_2057.py b/webchat/test_integrate_2057.py
index 33717ab..0d3b0dc 100644
--- a/webchat/test_integrate_2057.py
+++ b/webchat/test_integrate_2057.py
@@ -20,7 +20,7 @@ class IntegratedSessions(SessionFixture):
         return queue.enqueue(self.root, "external-project-work", str(uuid.uuid4()),
                              "Improve WebJam recording reliability", kind="coding", worker="codex", title="WebJam")
 
-    def test_all_17_original_messages_in_conversation_order(self):
+    def test_all_19_captured_messages_in_conversation_order(self):
         self.seed()
         checked = 0
         for source in SESSIONS:
@@ -44,6 +44,9 @@ class IntegratedSessions(SessionFixture):
                         elif index == 6:
                             self.assertEqual(len(identifiers), 1)
                             self.assertEqual(records[identifiers[0]]["kind"], "coding")
+                        elif index == 7:
+                            self.assertEqual(answer["content"], "Hi Jeff!")
+                            self.assertFalse(identifiers)
                         else:
                             self.assertEqual(answer["provider"], "state")
                             self.assertFalse(identifiers)
@@ -72,7 +75,7 @@ class IntegratedSessions(SessionFixture):
             self.assertEqual(replacement.get(self.identifier)["messages"][-1]["content"], answer["content"])
         finally:
             replacement.close()
-        self.assertEqual(checked, 17)
+        self.assertEqual(checked, 19)
 
     def test_unsupported_promises_cannot_escape_the_model_boundary(self):
         claims = [

## key symbols (status_observation / freeze / routing)
--- webchat/app.py ---
229:        from status_observation import bind_observation
234:        conversation["messages"][-1]["status_observation"] = bind_observation(observation, conversation)
627:                from status_observation import bind_observation
632:                    answer["status_observation"] = bind_observation(observation, value)
--- webchat/task_dispatch.py ---
--- webchat/status_observation.py ---
39:    observation = answer.get("status_observation")
--- webchat/integration_rubric.py ---
87:        from status_observation import observation_errors
94:        observed = answer["status_observation"]["snapshot"]
--- webchat/deploy_integrate.py ---
26:def latest_sessions(root):
116:        evidence["sessions"] = latest_sessions(root)
173:                                observations={"reply": answer.get("status_observation"),
214:                        receipt.get("status_observation") == exchange["observations"]["reply"],
--- webchat/fixtures/integrate_sessions_0927.json ---
keys ['provenance', 'sessions']
session_count 3

## test names mentioning observation/status/integrate/freeze
/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-integrate-2057/webchat/test_webchat.py:233:    def test_bad_password_throttles_without_creating_sessions(self):
/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-integrate-2057/webchat/test_webchat.py:318:    def test_progress_status_is_local_plain_and_does_not_start_duplicate_work(self):
/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-integrate-2057/webchat/test_webchat.py:471:    def test_busy_cli_lane_falls_through_to_next_provider(self):
/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-integrate-2057/webchat/test_webchat.py:513:    def test_live_status_snapshot_builder_reads_jobs_and_lanes(self):
/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-integrate-2057/webchat/test_webchat.py:537:    def test_gemini_prompt_includes_live_status_snapshot(self):
/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-integrate-2057/webchat/test_webchat.py:558:    def test_minimax_call_receives_live_status_snapshot_prompt(self):
/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-integrate-2057/webchat/test_webchat.py:607:    def test_busy_cli_lane_does_not_start_competing_process(self):
/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-integrate-2057/webchat/test_webchat.py:854:    def test_status_chip_answers_from_state_without_model(self):
/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-integrate-2057/webchat/test_webchat.py:883:    def test_self_improve_status_from_handback(self):
/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-integrate-2057/webchat/test_webchat.py:913:    def test_status_hides_drill_open_asks(self):
/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-integrate-2057/webchat/test_integrate_2057.py:23:    def test_all_19_captured_messages_in_conversation_order(self):
/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-integrate-2057/webchat/test_integrate_2057.py:130:    def test_empty_status_says_idle_and_queued_assignments_are_not_idle(self):
/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-integrate-2057/webchat/test_integrate_2057.py:141:    def test_all_llms_directive_makes_a_real_job_per_named_worker(self):
/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-integrate-2057/webchat/test_integrate_2057.py:148:    def test_observed_active_project_lane_can_supply_missing_prompt_context(self):
/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-integrate-2057/webchat/test_integrate_2057.py:160:    def test_frozen_turn_one_with_only_an_unverified_project_lane(self):
/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-integrate-2057/webchat/test_integrate_2057.py:207:    def test_unverified_lane_fallback_does_not_displace_an_ongoing_job(self):
/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-integrate-2057/webchat/test_status_observation.py:66:    def test_queued_claimed_reused_pid_and_running_observations_remain_distinct(self):
/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-integrate-2057/webchat/test_status_observation.py:97:    def test_write_failure_cannot_expose_a_successful_unpersisted_status(self):
/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-integrate-2057/webchat/test_status_observation.py:109:    def test_correction_has_its_own_bound_observation(self):
/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-integrate-2057/webchat/test_status_observation.py:115:    def test_provider_fallback_status_is_observed_and_bound_to_the_overlay(self):
/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-integrate-2057/webchat/test_status_observation.py:131:    def test_provider_metadata_cannot_forge_an_observation(self):
/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-integrate-2057/webchat/test_status_observation.py:170:    def test_digest_and_matching_prose_cannot_replace_observed_worker_evidence(self):
/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-integrate-2057/webchat/test_deploy_integrate.py:17:    def test_current_capture_matches_without_rewriting_sessions_and_rejects_drift(self):
