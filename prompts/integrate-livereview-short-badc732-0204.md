Strict INTEGRATE-ONLY code review of tip badc732c740625dd4a15b1774db09815c7a5ed99 on draft/webbob-integrate-2057.
Delta from prior BOTH_PASS 2cdcce9: session-freeze capture refresh + status routing for 'What are you working on?' (INTEGRATE-FIXED-0058).
Offline READY: 324 webchat + 130 services + 77 evals. List real CRITICAL/HIGH only.
End with exactly one line: VERDICT: PASS or VERDICT: FAIL

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

## commits 2cdcce9..badc732
badc732 Update parity total for the two appended captured turns
504fdbc Refresh frozen Jeff turns and route current-work status honestly

## patch 2cdcce9..HEAD
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
