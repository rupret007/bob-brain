# Strict LIVE tip review draft/webbob-integrate-2057 @199eb19 (199eb193396802bbbf899292e48cd04a55f9c57e)

SCOPE: apiworkers live-dispatch under holds + production checkout fallback + session-freeze honesty ONLY.
Focus: turn-1 Gemini audit + MiniMax test-writing real API jobs when queue empty / no identifiable project lane; production assignment planner accepts verified running Web Bob Git checkout as API report context (both server-owned deployment pins must match); prompts must not fabricate source job IDs or running-work claims; existing active work still takes precedence; holds/partial releases/maintenance/unavailable providers/API-only restriction; Barker/Wildflower parked; session-freeze capture honesty retained from prior tip.
Do NOT fail for missing voice/media/texting/iPhone. Ignore out-of-lane gaps.
Prior BOTH_PASS on tip badc732 does NOT cover this tip — re-review required after INTEGRATE-FIXED-0204 push 199eb19. Attempt-2 live deploy of badc732 FAIL'd rubric (API workers/holds turn 1) and rolled back to dff84e3.
Offline claim (INTEGRATE-FIXED-0204 READY): 333 webchat + 131 services + 96 evals; root cause attempt2 = no permitted source context (empty queue + unverified lane-integrate-deploy screen only; empty intent_state.holds).
Cite only real symbols in provided sources. List CRITICAL/HIGH real bugs only.
End with exactly one line: VERDICT: PASS or VERDICT: FAIL

## INTEGRATE-FIXED-0204 summary
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

## git log vs live dff84e3
199eb19 Dispatch bounded API reports from the verified live Web Bob checkout
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

## commits since prior BOTH_PASS tip badc732
199eb19 Dispatch bounded API reports from the verified live Web Bob checkout

## diffstat vs prior tip badc732 (primary review target)
 services/test_api_workers.py   |  52 +++++++++++----
 webchat/README.md              |   7 ++
 webchat/bob_parity_eval.py     |   4 +-
 webchat/integration_rubric.py  |  18 ++++--
 webchat/test_integrate_2057.py | 143 +++++++++++++++++++++++++++++++++++++++++
 webchat/test_webchat.py        |   2 +-
 webchat/worker_assignment.py   |  29 +++++++++
 7 files changed, 237 insertions(+), 18 deletions(-)

## patch since badc732 (apiworkers production-checkout fallback — primary review target)
commit 199eb193396802bbbf899292e48cd04a55f9c57e
Author:     Jeff Story <jeffstory@Jeffs-Mac-mini.local>
AuthorDate: Mon Sep 28 02:25:41 2026 -0500
Commit:     Jeff Story <jeffstory@Jeffs-Mac-mini.local>
CommitDate: Mon Sep 28 02:25:41 2026 -0500

    Dispatch bounded API reports from the verified live Web Bob checkout
---
 services/test_api_workers.py   |  52 +++++++++++----
 webchat/README.md              |   7 ++
 webchat/bob_parity_eval.py     |   4 +-
 webchat/integration_rubric.py  |  18 ++++--
 webchat/test_integrate_2057.py | 143 +++++++++++++++++++++++++++++++++++++++++
 webchat/test_webchat.py        |   2 +-
 webchat/worker_assignment.py   |  29 +++++++++
 7 files changed, 237 insertions(+), 18 deletions(-)

diff --git a/services/test_api_workers.py b/services/test_api_workers.py
index 33456e0..a821be7 100644
--- a/services/test_api_workers.py
+++ b/services/test_api_workers.py
@@ -42,30 +42,57 @@ class APIWorkerTests(unittest.TestCase):
         return repo
 
     def test_frozen_turn_one_reaches_both_api_transports_and_delivers_reports(self):
+        self.frozen_turn_reports(deployed_checkout=False)
+
+    def test_attempt2_without_a_project_lane_reaches_both_api_transports(self):
+        self.frozen_turn_reports(deployed_checkout=True)
+
+    def frozen_turn_reports(self, *, deployed_checkout):
         # Real chat -> queue -> scheduler -> worker -> metered API transport.
         # Only HTTP responses, lane health and semantic acceptance are fixtures.
         with patch.object(sys, "path", [str(Path(__file__).resolve().parents[1] / "webchat"), *sys.path]):
             from app import Chat
+            from build_info import CODE_ROOT
+            from deploy_integrate import submit
             from dispatch_receipts import receipt_errors
             from integration_rubric import sessions
 
-            repo = self.repo()
-            (self.core / "services").mkdir()
-            (self.core / "services/projects.json").write_text(json.dumps({"Web Bob": {"repo": str(repo)}}))
+            if deployed_checkout:
+                # Match restart()'s real pin layout. No project mapping or
+                # report_repository mock: workers must inspect the pinned code.
+                repo = CODE_ROOT
+                (self.core / "state").mkdir()
+                for name in ("webchat", "dispatch"):
+                    (self.core / "state" / (name + "-code-root")).write_text(str(repo) + "\n")
+                screens = {"lane-integrate-deploy-0204": "53678.lane-integrate-deploy-0204"}
+                evidence_file = "webchat/worker_assignment.py"
+                context = "no current task or worker execution is confirmed"
+            else:
+                repo = self.repo()
+                (self.core / "services").mkdir()
+                (self.core / "services/projects.json").write_text(json.dumps({"Web Bob": {"repo": str(repo)}}))
+                screens = {"lane-webbob-llm-reviews": "29817.lane-webbob-llm-reviews"}
+                evidence_file = "queue.py"
+                context = "worker activity is unverified"
             (self.core / "keys.env").write_text("GEMINI_API_KEY=gemini-fixture-key\nMINIMAX_API_KEY=minimax-fixture-key\n")
             providers = Mock(spec=["reply"])
             providers.reply.side_effect = AssertionError("Assignments must bypass conversational models")
             chat = Chat(self.core / "webchat", self.root, providers)
             self.addCleanup(chat.close)
             cid = chat.conversation_list()["conversations"][0]["id"]
-            request = str(uuid.uuid4())
             started = time.time()
-            with patch("live_status_snapshot._screen_sessions", return_value={"lane-webbob-llm-reviews": "29817.lane-webbob-llm-reviews"}), \
+            # Use the deployment replay's submission function with an in-process
+            # HTTP adapter; all chat/intent/journal code stays real and isolated.
+            def call(route, payload=None):
+                if route == "/api/messages":
+                    return chat.submit(payload["conversation_id"], payload["message"], payload["request_id"])
+                return chat.get(cid)
+            with patch("live_status_snapshot._screen_sessions", return_value=screens), \
                     patch("live_status_snapshot.process_table", return_value={}):
-                receipt = chat.submit(cid, sessions()[0]["exchanges"][0]["message"], request)["messages"][-1]
+                receipt = submit(SimpleNamespace(call=call), cid, sessions()[0]["exchanges"][0]["message"])
             rows = queue.tasks(self.root)
             self.assertEqual(len(rows), 2)
-            self.assertEqual(receipt_errors(receipt, rows, cid, request, started), [])
+            self.assertEqual(receipt_errors(receipt, rows, cid, receipt["request_id"], started), [])
             self.assertEqual([rows[key]["requested_worker"] for key in receipt["task_ids"]], ["gemini", "minimax"])
             self.assertEqual([rows[key]["kind"] for key in receipt["task_ids"]], ["audit", "test-writing"])
             providers.reply.assert_not_called()
@@ -79,10 +106,11 @@ class APIWorkerTests(unittest.TestCase):
                 self.assertEqual(current["worker"], lane)
                 self.assertEqual(current["model"], MODELS[lane])
                 self.assertIsNone(current["source_job_id"])
-                self.assertIn("FILE queue.py", json.dumps(payload))
-                self.assertIn("worker activity is unverified", json.dumps(payload))
-                self.assertNotIn("fixture-must-not-be-sent", json.dumps(payload))
-                answer = lane + ": queue.py needs a duplicate-enqueue regression. Tests were not run."
+                self.assertIn("FILE " + evidence_file, json.dumps(payload))
+                self.assertIn(context, json.dumps(payload))
+                if not deployed_checkout:
+                    self.assertNotIn("fixture-must-not-be-sent", json.dumps(payload))
+                answer = lane + ": " + evidence_file + " needs a duplicate-enqueue regression. Tests were not run."
                 if lane == "gemini":
                     self.assertIn("gemini-2.5-pro:generateContent", config)
                     result = dict(candidates=[dict(finishReason="STOP", content=dict(parts=[dict(text=answer)]))],
@@ -111,6 +139,8 @@ class APIWorkerTests(unittest.TestCase):
             publish.assert_not_called()
             for row in queue.tasks(self.root).values():
                 self.assertEqual(row["status"], "succeeded")
+                self.assertEqual(row["worker"], row["requested_worker"])
+                self.assertGreaterEqual(row["execution_started_at"], started)
                 self.assertEqual(Path(row["repo"]), repo)
                 self.assertIn(row["result"], Path(row["result_path"]).read_text())
                 self.assertEqual(row["result_sha256"], hashlib.sha256(row["result"].encode()).hexdigest())
diff --git a/webchat/README.md b/webchat/README.md
index f420857..be9a06f 100644
--- a/webchat/README.md
+++ b/webchat/README.md
@@ -72,6 +72,13 @@ holds, maintenance or unavailable lanes get an honest explanation, never a
 readiness-only acknowledgement. A queued receipt means waiting for runner
 capacity; a started receipt requires a recorded worker claim.
 
+When no permitted ongoing job or identified project lane remains, matching
+webchat and dispatcher deployment pins can identify the running Web Bob Git
+checkout for these API reports. The assignments explicitly say no current task
+or execution is confirmed. This fallback only supplies Web Bob repository
+context to API workers; project/global holds, maintenance and provider
+availability still apply. Missing or mismatched pins cannot supply context.
+
 Named API requests also support audits, planning, research, repository reviews,
 test-case writing and eval grading. Gemini job calls use `gemini-2.5-pro`;
 research enables `google_search`. MiniMax uses `MiniMax-M2.7`. The runner supplies
diff --git a/webchat/bob_parity_eval.py b/webchat/bob_parity_eval.py
index fa9fc87..a41916f 100644
--- a/webchat/bob_parity_eval.py
+++ b/webchat/bob_parity_eval.py
@@ -157,8 +157,8 @@ def run_eval(root: Path | None = None) -> dict:
                 chat.close()
 
     from integration_rubric import run_eval as integration_eval
-    for project_lane_only in (False, True):
-        for result in integration_eval(project_lane_only=project_lane_only):
+    for scenario in ({}, {"project_lane_only": True}, {"deployed_checkout": True}):
+        for result in integration_eval(**scenario):
             rows.append(_case(result["name"], result["pass_check"], "; ".join(result["errors"])))
 
     passed = sum(1 for r in rows if r["pass"])
diff --git a/webchat/integration_rubric.py b/webchat/integration_rubric.py
index 9a988ac..982281b 100644
--- a/webchat/integration_rubric.py
+++ b/webchat/integration_rubric.py
@@ -109,7 +109,7 @@ def check_reply(answer, exchange, cid, started, before, after, jobs):
     return errors
 
 
-def run_eval(*, project_lane_only=False):
+def run_eval(*, project_lane_only=False, deployed_checkout=False):
     """Run the same exact-message rubric offline against real isolated journals."""
     import tempfile
     import time
@@ -125,7 +125,8 @@ def run_eval(*, project_lane_only=False):
 
     # Attempt 2205 had these open screens but zero queued/claimed jobs and no
     # confirmed worker. Exercise collection and dispatch without a seed job.
-    screens = ({"lane-integrate-deploy-2205": "68531.lane-integrate-deploy-2205",
+    screens = ({"lane-integrate-deploy-0204": "53678.lane-integrate-deploy-0204"} if deployed_checkout else
+               {"lane-integrate-deploy-2205": "68531.lane-integrate-deploy-2205",
                 "lane-webbob-llm-reviews": "29817.lane-webbob-llm-reviews"}
                if project_lane_only else {})
     results = []
@@ -133,9 +134,17 @@ def run_eval(*, project_lane_only=False):
             patch("live_status_snapshot._screen_sessions", return_value=screens), \
             patch("live_status_snapshot.process_table", return_value={}):
         root = Path(folder)
+        if deployed_checkout:
+            # Attempt 0204: no active source job or project screen. Use the
+            # same release pins written by deploy_parity.restart in production.
+            from build_info import CODE_ROOT
+            pins = root / "conductor/state"
+            pins.mkdir(parents=True)
+            for name in ("webchat", "dispatch"):
+                (pins / (name + "-code-root")).write_text(str(CODE_ROOT) + "\n")
         chat = Chat(root / "conductor/webchat", root, Greeting())
         try:
-            if not project_lane_only:
+            if not project_lane_only and not deployed_checkout:
                 task_queue.enqueue(root, "external", "source", "Improve WebJam recording reliability", worker="codex", kind="coding", title="WebJam")
             for source in sessions():
                 cid = chat.new_conversation()["id"]
@@ -149,7 +158,8 @@ def run_eval(*, project_lane_only=False):
                     answer = chat.get(cid)["messages"][-1]
                     errors = check_reply(answer, exchange, cid, started, before, build_live_status_snapshot(root), task_queue.tasks(root))
                     results.append(dict(name=source["source_id"][:8] + " turn " + str(index + 1) +
-                                             (" (unverified project lane)" if project_lane_only else ""),
+                                             (" (deployed checkout, no project lane)" if deployed_checkout else
+                                              " (unverified project lane)" if project_lane_only else ""),
                                         pass_check=not errors, errors=errors, reply=answer["content"]))
         finally:
             chat.close()
diff --git a/webchat/test_integrate_2057.py b/webchat/test_integrate_2057.py
index 0d3b0dc..591b8b5 100644
--- a/webchat/test_integrate_2057.py
+++ b/webchat/test_integrate_2057.py
@@ -15,6 +15,149 @@ from test_webbob_replyq_1856 import SessionFixture
 SESSIONS = json.loads(Path(__file__).with_name("fixtures").joinpath("integrate_sessions_0927.json").read_text())["sessions"]
 
 
+class PinnedDeploymentAssignments(SessionFixture):
+    def setUp(self):
+        super().setUp()
+        from build_info import CODE_ROOT
+        self.code_root = CODE_ROOT
+        self.pins = self.root / "conductor/state"
+        self.pins.mkdir(parents=True, exist_ok=True)
+        for name in ("webchat", "dispatch"):
+            (self.pins / (name + "-code-root")).write_text(str(CODE_ROOT) + "\n")
+        # Attempt 0204 had this screen only: no identifiable project lane.
+        sampler = patch("live_status_snapshot._screen_sessions", return_value={
+            "lane-integrate-deploy-0204": "53678.lane-integrate-deploy-0204"})
+        sampler.start()
+        self.addCleanup(sampler.stop)
+
+    def test_attempt2_turn_one_dispatches_from_the_matching_release_pins(self):
+        from integration_rubric import check_reply, sessions
+        from live_status_snapshot import build_live_status_snapshot
+        exchange = sessions()[0]["exchanges"][0]
+        before = build_live_status_snapshot(self.root)
+        self.assertEqual(before["queue_counts"]["queued"], 0)
+        self.assertEqual(before["queue_counts"]["claimed"], 0)
+        self.assertEqual(before["work_counts"]["running"], 0)
+        self.assertEqual(len(before["work"]), 1)
+        self.assertIsNone(before["work"][0]["project"])
+        started = time.time()
+        answer = self.send(exchange["message"])
+        records = queue.tasks(self.root)
+        after = build_live_status_snapshot(self.root)
+        self.assertEqual(check_reply(answer, exchange, self.identifier, started, before, after, records), [])
+        self.assertEqual(len(records), 2)
+        self.assertEqual(after["work_counts"]["running"], 0)
+        for row in records.values():
+            self.assertEqual(row["status"], "queued")
+            self.assertIsNone(row["source_job_id"])
+            self.assertIn("Project: Web Bob", row["prompt"])
+            self.assertIn("matching deployment pins", row["prompt"])
+            self.assertIn("no current task or worker execution is confirmed", row["prompt"])
+            self.assertNotIn("Ongoing task:", row["prompt"])
+        self.assertFalse(self.fake.calls)
+        self.chat.close()
+        self.chat = Chat(self.folder, self.root, self.fake)
+        replay = self.chat.submit(self.identifier, exchange["message"], answer["request_id"])["messages"][-1]
+        self.assertEqual(replay["task_ids"], answer["task_ids"])
+        self.assertEqual(replay["content"], answer["content"])
+        self.assertEqual(set(queue.tasks(self.root)), set(records))
+
+    def test_pins_are_context_without_an_open_screen_or_a_claim_of_running_work(self):
+        with patch("live_status_snapshot._screen_sessions", return_value={}):
+            answer = self.send(SESSIONS[0]["exchanges"][0]["message"])
+            self.assertEqual(len(answer.get("task_ids", [])), 2)
+            status = self.send("What are you working on?")
+        self.assertIn("waiting to run", status["content"])
+        self.assertNotIn("running for", status["content"])
+
+    def test_missing_empty_relative_mismatched_and_unreadable_pins_fail_closed(self):
+        for name in ("webchat", "dispatch"):
+            pin = self.pins / (name + "-code-root")
+            for value in (None, "", ".", str(self.root), str(self.root / "missing")):
+                with self.subTest(pin=name, value=value):
+                    pin.unlink(missing_ok=True)
+                    if value is not None:
+                        pin.write_text(value)
+                    answer = self.send(SESSIONS[0]["exchanges"][0]["message"])
+                    self.assertFalse(answer.get("task_ids"))
+                    self.assertFalse(queue.tasks(self.root))
+                    pin.write_text(str(self.code_root))
+            pin.unlink()
+            pin.mkdir()
+            self.assertIn("couldn't assign", self.send(SESSIONS[0]["exchanges"][0]["message"])["content"])
+            pin.rmdir()
+            pin.write_text(str(self.code_root))
+
+    def test_pinned_context_respects_project_global_and_partial_release_holds(self):
+        for hold, release, permitted in (
+            ("Hold off on Web Bob", None, False),
+            ("Hold off", None, False),
+            ("Hold off", "Resume WebJam", False),
+            ("Hold off", "Resume Web Bob", True),
+            ("Hold off on WebJam", None, True),
+        ):
+            with self.subTest(hold=hold, release=release):
+                self.identifier = self.chat.new_conversation()["id"]
+                self.send(hold)
+                if release:
+                    self.send(release)
+                before = set(queue.tasks(self.root))
+                answer = self.send(SESSIONS[0]["exchanges"][0]["message"])
+                added = set(queue.tasks(self.root)) - before
+                self.assertEqual(len(added), 2 if permitted else 0)
+                if permitted:
+                    for key in added:
+                        self.assertTrue(queue.tasks(self.root)[key]["prompt"].startswith("Project: Web Bob\n"))
+                else:
+                    self.assertIn("current holds", answer["content"])
+
+    def test_pins_do_not_authorize_other_projects_or_tool_workers(self):
+        for text in ("Use Gemini and MiniMax for ongoing WebJam jobs",
+                     "Use Codex for ongoing jobs", "Use all LLMs for ongoing jobs"):
+            with self.subTest(text=text):
+                self.assertIn("couldn't assign", self.send(text)["content"])
+                self.assertFalse(queue.tasks(self.root))
+
+    def test_parked_project_holds_survive_the_permitted_webbob_dispatch(self):
+        conversation = self.chat.conversations[self.identifier]
+        holds = {name: dict(request_id="parked", reason="Keep parked", released_projects=[])
+                 for name in ("Barker", "Wildflower")}
+        conversation["intent_state"]["holds"] = copy.deepcopy(holds)
+        self.chat.save(conversation)
+        answer = self.send(SESSIONS[0]["exchanges"][0]["message"])
+        self.assertEqual(len(answer.get("task_ids", [])), 2)
+        self.assertEqual(self.chat.get(self.identifier)["intent_state"]["holds"], holds)
+        for row in queue.tasks(self.root).values():
+            self.assertTrue(row["prompt"].startswith("Project: Web Bob\n"))
+            self.assertIsNone(row["publish_project"])
+
+    def test_rollback_copy_without_git_evidence_cannot_supply_report_context(self):
+        rollback = self.root / "rollback-copy"
+        rollback.mkdir()
+        for name in ("webchat", "dispatch"):
+            (self.pins / (name + "-code-root")).write_text(str(rollback))
+        with patch("worker_assignment.CODE_ROOT", rollback):
+            self.assertIn("couldn't assign", self.send(SESSIONS[0]["exchanges"][0]["message"])["content"])
+        self.assertFalse(queue.tasks(self.root))
+
+    def test_pinned_context_does_not_displace_a_permitted_ongoing_job(self):
+        source = queue.enqueue(self.root, "external", "source", "Improve WebJam recording", kind="coding")
+        answer = self.send(SESSIONS[0]["exchanges"][0]["message"])
+        rows = queue.tasks(self.root)
+        self.assertEqual([rows[key]["source_job_id"] for key in answer["task_ids"]], [source["id"], source["id"]])
+
+    def test_pinned_context_still_respects_maintenance_and_provider_unavailability(self):
+        maintenance = self.root / "conductor/MAINTENANCE"
+        maintenance.touch()
+        self.assertIn("maintenance", self.send(SESSIONS[0]["exchanges"][0]["message"])["content"])
+        maintenance.unlink()
+        for state in ("needs_key", "cooldown", "budget_exhausted"):
+            with self.subTest(state=state):
+                (self.root / "conductor/lanes.json").write_text(json.dumps({"minimax": {"state": state}}))
+                self.assertIn(state.replace("_", " "), self.send(SESSIONS[0]["exchanges"][0]["message"])["content"])
+                self.assertFalse(queue.tasks(self.root))
+
+
 class IntegratedSessions(SessionFixture):
     def seed(self):
         return queue.enqueue(self.root, "external-project-work", str(uuid.uuid4()),
diff --git a/webchat/test_webchat.py b/webchat/test_webchat.py
index 96798f6..f8fd851 100644
--- a/webchat/test_webchat.py
+++ b/webchat/test_webchat.py
@@ -1231,7 +1231,7 @@ class HandbackJobTests(Fixture):
         state_ledger.write_now(self.root, "offline parity fixture", sha="fedcba1")
         result = run_eval(self.root)
         self.assertEqual(result["passed"], result["total"], result["cases"])
-        self.assertEqual(result["total"], 77)
+        self.assertEqual(result["total"], 96)
 
     def test_catchup_event_ack_cursor(self):
         ledger_dir = Path(__file__).resolve().parent.parent / "state"
diff --git a/webchat/worker_assignment.py b/webchat/worker_assignment.py
index e1d4b37..38d875c 100644
--- a/webchat/worker_assignment.py
+++ b/webchat/worker_assignment.py
@@ -1,9 +1,11 @@
 """Turn requests to use LLMs on ongoing work into durable, scoped assignments."""
 import json
 import re
+from pathlib import Path
 
 import task_queue
 from api_tasks import ROLES
+from build_info import CODE_ROOT
 from chat_intent import blocked_scopes, command, project_targets, state_for
 from live_status_snapshot import observe_work
 
@@ -60,6 +62,29 @@ def issue_followup(root, conversation, text):
             "Report evidence if no fix is needed. Work in your assigned draft worktree; never deploy or merge.")
 
 
+def deployed_project_context(root):
+    """A pinned checkout can supply API evidence, never proof of ongoing work."""
+    # Deployments can have no active jobs and no identifiable project screen.
+    # Both services must select this running checkout; an arbitrary/stale pin
+    # or a rollback copy without Git evidence is not enough to assign a report.
+    if not (CODE_ROOT / ".git").exists():
+        return None
+    try:
+        for name in ("webchat", "dispatch"):
+            value = (root / "conductor/state" / (name + "-code-root")).read_text().strip()
+            path = Path(value)
+            if not path.is_absolute() or path.resolve(strict=True) != CODE_ROOT:
+                return None
+    except (OSError, ValueError, RuntimeError):
+        return None
+    return dict(id=None, project="Web Bob", context="project context", prompt=(
+        "The Web Bob checkout is selected by matching deployment pins for this server and its dispatcher; "
+        "no current task or worker execution is confirmed. Inspect the supplied repository snapshot for "
+        "concrete dispatch findings and regression test drafts, including webchat/worker_assignment.py, "
+        "webchat/task_dispatch.py, state/task_queue.py and services/dispatch_worker.py. "
+        "Do not infer active work, progress or results from deployment metadata."))
+
+
 def plan(root, conversation, text, workers):
     for worker in workers:
         task_queue.worker_name(worker)  # Reject Grok/xAI before any queue write.
@@ -117,6 +142,10 @@ def plan(root, conversation, text, workers):
                        "progress or results from the lane name or historical logs.")
             candidates.append(dict(id=None, prompt=context, project=project, context="project context"))
             seen_projects.add(project)
+        if not candidates and (not targets or "Web Bob" in targets) and not blocked_scopes(state, ["Web Bob"]):
+            context = deployed_project_context(root)
+            if context:
+                candidates.append(context)
     if not candidates:
         raise ValueError("I couldn't assign those workers: there is no identifiable ongoing job permitted by the current holds. Name a project and task to start.")
     health = root / "conductor/lanes.json"
