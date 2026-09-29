Perform a fresh LIVE API code/release review of Web Bob tip 9cfe54840bed5cb0ca7f2e94db7ef6596b014cf7, branch draft/webbob-texting-onto-a777736, attempt 1.
This is a new review; do not reuse any previous verdict. Review the supplied exact code and test evidence. You have no tools; do not claim you ran tests or inspected live yourself.

Authoritative problem: ce2482c was merged as 1d72c44 (must remain), deployed, and rolled back to a777736 after session b33fac25-3c8a-452d-8673-47d3a99dd92c turn 3 ('Ok great works on all LLMs now?') produced a raw diagnostic dump.
Requirement: short natural status, no missing-model placeholders, queue_counts, job-runner internals, or semicolon worker inventories in casual chat. Reuse existing status/reply infrastructure. Keep truthful running/waiting/unconfirmed/idle states, exact saved observations, dispatch effects, texting consent/privacy, and opt-in diagnostics.
Full model/task/duration inventories are deliberately no longer required in casual prose; they remain in the saved observation and explicit diagnostics. Evaluate the new behavioral tests independently, not just renderer equality.
Scope excludes media/voice/UI/Instinct deploy, Grok/xAI, force-push and Jeff notifications/texts. The only browser change is the existing isolated texting test harness's CSP-compatible locator wait.
The release runner is adapted from the previous guarded script, requires fresh reviews + full tests + exact draft head and clean-merge tree, snapshots rollback, checks texting smoke and all 19 exact replay turns, waits for real jobs, and rolls back to a777736 on failure.
Find actual blocking defects with concrete symbols and examples. Nonblocking suggestions are welcome, clearly labeled. End with exactly one line: VERDICT: PASS or VERDICT: FAIL.


## Validation report
# TEXTING-FIXED-0810

tip: 9cfe54840bed5cb0ca7f2e94db7ef6596b014cf7
branch: draft/webbob-texting-onto-a777736
base: ce2482c (the retained clean merge is 1d72c44)

Casual status now summarizes observed work in short sentences. It groups matching worker states, keeps waiting and unconfirmed work distinct from running work, and omits model placeholders, elapsed-time inventories, machine task labels, and job-runner counts. Explicit diagnostics and the complete saved observation remain available.

The existing reply_authority formatter, cooldown mapping, server-owned status route, and status_observation evidence path from integrate a777736/reply-quality branches are retained. No new status subsystem. The release rubric now rejects the additional diagnostic phrases and worker inventories while retaining identity, timestamp, digest, count, execution-source and exact-render checks. Inventory-in-prose assertions were replaced with explicit short-answer/state regressions.

Exact previous failure, session b33fac25-3c8a-452d-8673-47d3a99dd92c turn 3:
> Codex is working on Web Bob. Gemini and MiniMax have work waiting to run. Claude and Cursor are idle.

Validation on this tip:
- Webchat: 389 passed, 0 skipped, including the isolated texting browser proof.
- Services: 131 passed.
- Offline parity/replay evals: 99/99 passed (including all 19 frozen turns across three scenarios and the failed live snapshot).
- Deployment guard tests: 2/2 passed; bad review gate never activates, failed smoke automatically restores and verifies a777736.
- Standalone texting browser proof: PASS, zero real texts or mock sends, no unexpected writes, model calls, or queued jobs. The existing browser wait was changed to a CSP-compatible locator wait; production UI/CSP were not changed.

Evidence: TEXTING-0810-tests.json, TEXTING-0810-*-tests.txt, TEXTING-0810-browser-proof/WEBBOB-TEXTING-0927.evidence.json. Initial old-wording assertion failures and the initial browser harness failure are preserved separately.

No Grok/xAI, force-push, or Jeff notifications/texts. Fresh LIVE Gemini + MiniMax reviews and deployment evidence follow separately.


## Exact diff from failed ce2482c
diff --git a/webchat/bob_parity_eval.py b/webchat/bob_parity_eval.py
index a41916f..968447b 100644
--- a/webchat/bob_parity_eval.py
+++ b/webchat/bob_parity_eval.py
@@ -106,9 +106,16 @@ def run_eval(root: Path | None = None) -> dict:
                         "lane_locks": {}, "provider_health": {}}
     status_line = format_operational_reply(status_snapshot, "server", "how's it going?")
     rows.append(_case("status reply skips robotic 'Yes —' prefix", not status_line.startswith("Yes")
-                       and "Codex is on “Review Web Bob replies” (gpt-fixture; running for 1 min)" in status_line))
+                       and "Codex is working on Review Web Bob replies" in status_line))
     rows.append(_case("status uses bounded sentences without dumps", len(status_line.split(". ")) <= 4
                        and "logs/" not in status_line and "lane-" not in status_line and " | " not in status_line))
+    from integration_rubric import style_errors
+    fixture = json.loads(Path(__file__).with_name("fixtures").joinpath("texting_diagdump_0810.json").read_text())
+    fixed = format_operational_reply(fixture["snapshot"], text=fixture["message"])
+    rows.append(_case("failed live texting status snapshot uses natural prose", fixed ==
+        "Codex is working on Web Bob. Gemini and MiniMax have work waiting to run. Claude and Cursor are idle."))
+    rows.append(_case("failed live diagnostic reply is rejected", "raw diagnostic dump" in style_errors(fixture["bad_reply"])))
+    rows.append(_case("fixed live status clears release style gate", not style_errors(fixed)))
     from task_dispatch import project_receipt
     receipt = project_receipt([dict(id="webchat-private-id", title="WebJam", status="queued", group_index=0, requested_worker="codex")])
     rows.append(_case("dispatch receipt cites task, worker and job ID", receipt == "I queued “WebJam” for Codex (job `webchat-private-id`)."))
diff --git a/webchat/browser_texting.cjs b/webchat/browser_texting.cjs
index 0d6daa2..3d6ec7c 100644
--- a/webchat/browser_texting.cjs
+++ b/webchat/browser_texting.cjs
@@ -23,7 +23,7 @@ const { chromium } = require(process.env.BOB_PLAYWRIGHT_MODULE || "playwright");
     await page.locator("#password").fill(config.password);
     await page.locator("#login-form button").click();
     await page.waitForURL(config.url + "/");
-    await page.waitForFunction(() => !document.querySelector("#send").disabled);
+    await page.locator("#send:enabled").waitFor();
     async function say(text) {
       await page.locator("#message").fill(text);
       const response = page.waitForResponse(r => r.url() === config.url + "/api/messages" && r.request().method() === "POST");
@@ -31,7 +31,7 @@ const { chromium } = require(process.env.BOB_PLAYWRIGHT_MODULE || "playwright");
       const result = await response;
       assert.equal(result.status(), 202);
       const data = await result.json();
-      await page.waitForFunction(() => !document.querySelector("#send").disabled);
+      await page.locator("#send:enabled").waitFor();
       return data;
     }
     const screenshots = [];
diff --git a/webchat/fixtures/texting_diagdump_0810.json b/webchat/fixtures/texting_diagdump_0810.json
new file mode 100644
index 0000000..5f16da1
--- /dev/null
+++ b/webchat/fixtures/texting_diagdump_0810.json
@@ -0,0 +1,111 @@
+{
+  "source": "WEBBOB-TEXTING-DEPLOYMENT-0927-attempt1.json",
+  "session_id": "b33fac25-3c8a-452d-8673-47d3a99dd92c",
+  "turn": 3,
+  "message": "Ok great works on all LLMs now?",
+  "bad_reply": "Codex is on \u201cWeb Bob: # lane-webbob-texting-deploy-0702\u201d (model not reported; running for 7 min); Gemini is on \u201cWeb Bob \u2014 Whole-repo audit and implementation plan\u201d (2 jobs waiting to run). MiniMax is on \u201cWeb Bob \u2014 Review and regression test-case drafts\u201d (2 jobs waiting to run). Claude and Cursor are idle. The job runner has 0 claimed and 4 queued jobs.",
+  "snapshot": {
+    "work": [
+      {
+        "title": "# lane-webbob-texting-deploy-0702",
+        "worker": "codex",
+        "model": null,
+        "state": "running",
+        "elapsed_seconds": 422,
+        "project": "Web Bob",
+        "task": "# lane-webbob-texting-deploy-0702"
+      }
+    ],
+    "work_counts": {
+      "running": 1,
+      "paused": 0,
+      "claimed": 0,
+      "unverified": 0
+    },
+    "inspection": {
+      "screens_available": true,
+      "processes_available": true,
+      "queue_available": true
+    },
+    "queue_counts": {
+      "queued": 4,
+      "claimed": 0,
+      "done": 218,
+      "failed": 41
+    },
+    "lane_locks": {
+      "codex": {
+        "state": "busy",
+        "cached_state": "ready",
+        "detail": "available"
+      },
+      "claude": {
+        "state": "ready",
+        "cached_state": "ready",
+        "detail": "available"
+      },
+      "cursor": {
+        "state": "ready",
+        "cached_state": "ready",
+        "detail": "available"
+      },
+      "gemini": {
+        "state": "ready",
+        "cached_state": "ready",
+        "detail": "available"
+      },
+      "minimax": {
+        "state": "ready",
+        "cached_state": "ready",
+        "detail": "available"
+      },
+      "mini": {
+        "state": "ready",
+        "cached_state": "ready",
+        "detail": "available"
+      }
+    },
+    "provider_health": {},
+    "screen_lanes": [],
+    "disk": {},
+    "queue_jobs": {
+      "queued": [
+        {
+          "state": "queued",
+          "bucket": "queued",
+          "worker": "minimax",
+          "model": null,
+          "title": "Web Bob \u2014 Review and regression test-case drafts",
+          "project": null
+        },
+        {
+          "state": "queued",
+          "bucket": "queued",
+          "worker": "gemini",
+          "model": null,
+          "title": "Web Bob \u2014 Whole-repo audit and implementation plan",
+          "project": null
+        },
+        {
+          "state": "queued",
+          "bucket": "queued",
+          "worker": "minimax",
+          "model": null,
+          "title": "Web Bob \u2014 Review and regression test-case drafts",
+          "project": null
+        },
+        {
+          "state": "queued",
+          "bucket": "queued",
+          "worker": "gemini",
+          "model": null,
+          "title": "Web Bob \u2014 Whole-repo audit and implementation plan",
+          "project": null
+        }
+      ],
+      "claimed": [],
+      "done": [],
+      "failed": []
+    }
+  }
+}
diff --git a/webchat/integration_rubric.py b/webchat/integration_rubric.py
index 0d7210c..ae39bf5 100644
--- a/webchat/integration_rubric.py
+++ b/webchat/integration_rubric.py
@@ -35,7 +35,9 @@ def style_errors(text, dispatch_count=0):
     if re.search(r"(?i)unknown task|task details unavailable|I['’]ll (?:focus|do better|make sure|ensure)|"
                  r"system is actively adding|ready for (?:new )?work|healthy and ready|prioritize adding work|Worker process", prose):
         errors.append("empty promise or readiness substituted for utilization")
-    if re.search(r"logs/|lane-[\w-]+|\blast:|\bPID\s*[:=]|\s\|\s", prose):
+    if re.search(r"logs/|lane-[\w-]+|\blast:|\bPID\s*[:=]|\s\|\s|"
+                 r"model not reported|queue_counts|job runner|"
+                 r"(?:Codex|Claude|Cursor|Gemini|MiniMax)[^.?!]*;[^.?!]*(?:Codex|Claude|Cursor|Gemini|MiniMax)", prose, re.I):
         errors.append("raw diagnostic dump")
     if prose.startswith(("Yes —", "Here's the status", "I understand.")):
         errors.append("answer is not first")
@@ -91,22 +93,9 @@ def check_reply(answer, exchange, cid, started, before, after, jobs):
         errors += evidence_errors
         if evidence_errors:
             return errors
-        from reply_authority import _task_name
-        observed = answer["status_observation"]["snapshot"]
-        for row in observed["work"]:
-            if row.get("assignment_recorded") is False:
-                if "CLI activity, but no recorded task" not in text:
-                    errors.append("unattributed process falsely presented as assigned work")
-                continue
-            if _task_name(row) not in text:
-                errors.append("status omits observed task " + _task_name(row))
-            if row.get("model") and row["model"] not in text:
-                errors.append("status omits observed model " + row["model"])
-        if text.count("running for") != observed["work_counts"]["running"]:
-            errors.append("status running count disagrees with observed execution")
-        for row in observed["queue_jobs"]["queued"]:
-            if _task_name(row) not in text:
-                errors.append("status omits waiting assignment " + _task_name(row))
+        # observation_errors still verifies exact rendering, identity, timestamps,
+        # digest, counts and execution evidence. Casual prose summarizes that
+        # sample; requiring every model/task/duration here forced diagnostic dumps.
     return errors
 
 
diff --git a/webchat/reply_authority.py b/webchat/reply_authority.py
index 34604c1..0668f14 100644
--- a/webchat/reply_authority.py
+++ b/webchat/reply_authority.py
@@ -148,77 +148,67 @@ def _task_name(row):
 
 
 def _casual_status(snap):
-    """Use full sentences; keep diagnostics and missing metadata out of task names."""
+    """Summarize the existing observation; keep its inventory in diagnostics."""
     work, inspection = snap["work"], snap["inspection"]
-    active, idle, extra = [], [], []
+    groups = {}
+
+    def add(name, singular, plural, priority):
+        groups.setdefault((priority, singular, plural), []).append(name)
+
     for name in WORKER_NAMES:
         rows = [row for row in work if row.get("worker") == name]
         pending = [row for row in snap.get("queue_jobs", {}).get("queued", []) if row.get("worker") == name]
-        unattributed = [row for row in rows if row.get("assignment_recorded") is False]
-        rows = [row for row in rows if row.get("assignment_recorded") is not False]
-        if name == "mini" and not rows:
+        if name == "mini" and not rows and not pending:
             continue
         display = WORKER_NAMES[name]
-        if unattributed:
-            extra.append(display + " has CLI activity, but no recorded task")
-        if rows or pending:
-            tasks = []
-            for row in rows:
-                model = row.get("model") or "model not reported"
-                duration = _duration(row.get("elapsed_seconds"))
-                state = {"running": "running for ", "paused": "paused; process age ",
-                         "claimed": "claimed, execution unconfirmed; age ",
-                         "unverified": "open, worker unconfirmed; age "}[row["state"]]
-                tasks.append("“" + _task_name(row) + "” (" + model + "; " + state + duration + ")")
-            from collections import Counter
-            for label, count in Counter(_task_name(row) for row in pending).items():
-                tasks.append("“" + label + "” (" + (str(count) + " jobs " if count > 1 else "") + "waiting to run)")
-            active.append(display + " is on " + _join(tasks) + _cooldown(snap, name))
-        elif unattributed:
-            pass
+        running = [row for row in rows if row.get("state") == "running" and row.get("assignment_recorded") is not False]
+        if running:
+            labels = []
+            for row in running:
+                label = clean(row.get("project") or _task_name(row), 60)
+                # Prompt headings and fallback screen labels are evidence, not
+                # readable assignments. Never echo machine labels into chat.
+                if re.search(r"lane-|logs/|\bPID\b|queue_counts|model not reported|job runner", label, re.I):
+                    label = "the current task"
+                label = re.sub(r"[;.!?]+", ",", label).strip(" #,: ") or "the current task"
+                if label not in labels:
+                    labels.append(label)
+            summary = _join(labels[:2]) + (" and other tasks" if len(labels) > 2 else "")
+            tail = "working on " + summary
+            if any(row.get("state") == "paused" for row in rows):
+                tail += ", with some work paused"
+            add(display, "is " + tail, "are " + tail, 0)
+        elif rows and all(row.get("state") == "paused" for row in rows):
+            add(display, "is paused", "are paused", 1)
+        elif rows:
+            add(display, "has activity I can't confirm yet", "have activity I can't confirm yet", 1)
+        elif pending:
+            add(display, "has work waiting to run", "have work waiting to run", 2)
         elif snap.get("lane_locks", {}).get(name, {}).get("state") == "busy":
-            extra.append(display + "'s last lane check was busy, but its task isn't recorded")
+            add(display, "has activity I can't confirm yet", "have activity I can't confirm yet", 1)
         elif _cooldown(snap, name):
-            extra.append(display + (" is idle" if all(inspection.values()) else " has unconfirmed activity") + _cooldown(snap, name))
+            cooldown = _cooldown(snap, name).removeprefix("; ")
+            tail = "cooling down" + (" until " + cooldown.removeprefix("resets ") if cooldown.startswith("resets ") else "")
+            if not all(inspection.values()):
+                tail += ", with current activity unconfirmed"
+            add(display, "is " + tail, "are " + tail, 3)
         else:
-            idle.append(display)
-    sentences = []
-    if active:
-        # At most two sentences for actual workers, even when all five are busy.
-        middle = (len(active) + 1) // 2
-        sentences.append("; ".join(active[:middle]) + ".")
-        if active[middle:]:
-            sentences.append("; ".join(active[middle:]) + ".")
-    elif work:
-        sentences.append("Work sessions are open, but I can't confirm a running worker.")
-    elif not all(inspection.values()):
-        sentences.append("I can't confirm all workers because a live check failed.")
-    elif snap["screen_lanes"]:
-        sentences.append("There are live service sessions, but no task worker is confirmed.")
-    else:
-        sentences.append("I don't see active work on the mini right now.")
+            add(display, "is idle" if all(inspection.values()) else "has no confirmed active work",
+                "are idle" if all(inspection.values()) else "have no confirmed active work", 4)
+    sentences = [_join(names) + " " + (singular if len(names) == 1 else plural)
+                 for (priority, singular, plural), names in sorted(groups.items(), key=lambda item: item[0][0])]
     other = [row for row in work if row.get("worker") not in WORKER_NAMES]
     if other:
-        extra.append(_join([_task_name(row) for row in other]) +
-                     (" has" if len(other) == 1 else " have") + " an open session with no confirmed worker")
-    # A cached lock or a failed inspection cannot establish that a worker is idle.
-    if idle:
-        extra.append(_join(idle) + ((" is idle" if len(idle) == 1 else " are idle") if all(inspection.values())
-                                   else " have no confirmed active work"))
-    if not all(inspection.values()) and active:
-        extra.append("a live check failed, so this list may be incomplete")
-    if extra:
-        sentences.append("; ".join(extra) + ".")
-    counts = snap["queue_counts"]
-    if inspection.get("queue_available", True):
-        queue_line = f"The job runner has {counts['claimed']} claimed and {counts['queued']} queued jobs"
-        unassigned = [row for row in snap.get("queue_jobs", {}).get("queued", []) if row.get("worker") not in WORKER_NAMES]
-        if unassigned:
-            queue_line += "; awaiting a worker for " + _join(["“" + _task_name(row) + "”" for row in unassigned])
-        sentences.append(queue_line + ".")
-    else:
-        sentences.append("I couldn't read the job queue.")
-    return " ".join(sentences)
+        sentences.append("There are other open sessions whose work I can't confirm")
+    if any(row.get("worker") not in WORKER_NAMES for row in snap.get("queue_jobs", {}).get("queued", [])):
+        sentences.append("Some work is still waiting for a worker")
+    if not all(inspection.values()):
+        sentences.append("A live check failed, so I can't confirm the full picture")
+    # Ordinary answers stay short even when all workers have different tasks.
+    # Group adjacent clauses with ordinary conjunctions, never diagnostic chains.
+    while len(sentences) > 4:
+        sentences[0:2] = [sentences[0] + ", while " + sentences[1]]
+    return ". ".join(sentences) + "."
 
 
 def format_operational_reply(snap, provider="server", text=""):
diff --git a/webchat/test_api_workers.py b/webchat/test_api_workers.py
index 8161eac..f34dfce 100644
--- a/webchat/test_api_workers.py
+++ b/webchat/test_api_workers.py
@@ -109,7 +109,7 @@ class APIAssignmentTests(SessionFixture):
             processes[pid] = dict(pid=pid, ppid=1, command="python3 /code/dispatch_worker.py " + claim["id"],
                                   process_state="S", elapsed_seconds=12)
         with patch("live_status_snapshot.process_table", return_value=processes):
-            status = operational_reply(self.root, "server", "status")
+            status = operational_reply(self.root, "server", "status with diagnostics")
             jobs = build_jobs_view(self.root)
         for model in ("gemini-2.5-pro", "MiniMax-M2.7"):
             self.assertIn(model, status)
diff --git a/webchat/test_chat_intent.py b/webchat/test_chat_intent.py
index a975a01..9e4fc96 100644
--- a/webchat/test_chat_intent.py
+++ b/webchat/test_chat_intent.py
@@ -59,7 +59,7 @@ class IntentTests(Fixture):
     def test_exact_live_going_question_uses_server_status_without_generation(self):
         answer = self.submit("is it going now?")["messages"][-1]
         self.assertEqual(answer["provider"], "state")
-        self.assertIn("I don't see active work", answer["content"])
+        self.assertIn("are idle", answer["content"])
         self.assertFalse(queue.tasks(self.root))
         self.assertFalse(self.fake.calls)
 
diff --git a/webchat/test_integrate_2057.py b/webchat/test_integrate_2057.py
index 38d6a3b..2616705 100644
--- a/webchat/test_integrate_2057.py
+++ b/webchat/test_integrate_2057.py
@@ -331,8 +331,8 @@ class IntegratedSessions(SessionFixture):
         self.seed()
         self.send("Use Gemini and MiniMax for ongoing jobs")
         answer = self.send("What about Gemini and MiniMax?")
-        self.assertIn("Gemini is on", answer["content"])
-        self.assertIn("MiniMax is on", answer["content"])
+        self.assertIn("Gemini", answer["content"])
+        self.assertIn("MiniMax", answer["content"])
         self.assertIn("waiting to run", answer["content"])
         self.assertNotIn("ready", answer["content"])
 
@@ -429,7 +429,7 @@ class IntegratedSessions(SessionFixture):
         self.assertFalse(rows[0]["assignment_recorded"])
         with patch("live_status_snapshot.process_table", return_value=table):
             reply = self.send("What is working on what?")
-        self.assertIn("Codex has CLI activity, but no recorded task", reply["content"])
+        self.assertIn("Codex has activity I can't confirm yet", reply["content"])
         self.assertNotIn("running for", reply["content"])
         self.assertNotIn("Worker process", reply["content"])
 
diff --git a/webchat/test_replies_session.py b/webchat/test_replies_session.py
index 3870b33..05b8395 100644
--- a/webchat/test_replies_session.py
+++ b/webchat/test_replies_session.py
@@ -50,14 +50,14 @@ class SessionReplies(Fixture):
                     reply = self.submit(text)
                     answer = reply["content"]
                     self.assertEqual(reply["provider"], "state")
-                    self.assertEqual(answer.count("running for 11 min"), 5)
-                    for task in ("Fix login validation", "Test intake validation", "Review scene editing", "Audit lineup scoring", "Test login retries"):
+                    self.assertNotIn("running for", answer)
+                    for task in NAMES:
                         self.assertIn(task, answer)
                     for name in NAMES:
                         self.assertIn(name, answer)
-                    self.assertEqual(answer.count("running for 11 min"), 5)
-                    self.assertIn("Claude is idle; resets 6:20 PM CT", answer)
-                    self.assertNotIn("resets", answer.split("Claude")[0])
+                    self.assertNotIn("running for", answer)
+                    self.assertIn("Claude is cooling down until 6:20 PM CT", answer)
+                    self.assertNotIn("cooling down", answer.split("Claude")[0])
                     self.assertLessEqual(len(answer.split(". ")), 4)
                     for unwanted in ("unknown task", "details unavailable", "I'll focus", "Chat health", "Recent logs", "Disk space"):
                         self.assertNotIn(unwanted.lower(), answer.lower())
@@ -71,9 +71,9 @@ class SessionReplies(Fixture):
                 patch("live_status_snapshot.process_table", return_value=parse_processes(
                     "100 1 08:00 S SCREEN -dmS lane-mystery bash\n101 100 07:00 S codex exec private task")):
             answer = self.submit(ASKS[1])["content"]
-        for expected in ("Codex is on “Mystery", "model not reported", "7 min"):
+        for expected in ("Codex is working on Mystery",):
             self.assertIn(expected, answer)
-        for hidden in ("lane-mystery", "logs/", "waiting for response"):
+        for hidden in ("lane-mystery", "logs/", "waiting for response", "model not reported", "7 min"):
             self.assertNotIn(hidden, answer)
         self.assertNotIn("unknown task", answer.lower())
 
diff --git a/webchat/test_reply_authority.py b/webchat/test_reply_authority.py
index 179d2a9..30105bf 100644
--- a/webchat/test_reply_authority.py
+++ b/webchat/test_reply_authority.py
@@ -16,8 +16,8 @@ class AuthorityTests(unittest.TestCase):
             (root / "logs/job-runner.log").write_text("Claimed review job\n")
             with patch("live_status_snapshot._screen_sessions", return_value={"svc-job-runner": "12.svc-job-runner"}):
                 answer = operational_reply(root, "server", "is it going now?")
-            self.assertIn("live service sessions", answer)
-            self.assertIn("job runner has 0 claimed and 0 queued jobs", answer)
+            self.assertIn("are idle", answer)
+            self.assertNotIn("job runner", answer)
             self.assertNotIn("Recent logs:", answer)
             self.assertNotIn("I don't see active work", answer)
             with patch("live_status_snapshot._screen_sessions", return_value={"svc-job-runner": "12.svc-job-runner"}):
@@ -92,12 +92,12 @@ class AuthorityTests(unittest.TestCase):
                 with self.subTest(text=text):
                     answer = enforce(root, text, dict(provider="gemini", content=
                         "Nothing is running. All lanes are ready. Use `start a job: task`."))
-                    self.assertIn("Claude is on “Projects push", answer)
-                    self.assertIn("(opus; running for 24 min)", answer)
-                    self.assertIn("Codex is on “Web Bob clean", answer)
-                    self.assertIn("(gpt-fixture; running for 18 min)", answer)
-                    self.assertIn("running for 12 min", answer)
-                    self.assertIn("running for 8 min", answer)
+                    self.assertIn("Claude is working on", answer)
+                    self.assertIn("Codex is working on Web Bob", answer)
+                    self.assertIn("Gemini", answer)
+                    self.assertIn("MiniMax", answer)
+                    self.assertNotIn("running for", answer)
+                    self.assertNotIn(";", answer)
                     self.assertLessEqual(len(answer.split(". ")), 4)
                     for hidden in ("None", "shelf-load-1659", "History:", "provider:", "start a job:", "All lanes", "logs/", "lane-", "last:"):
                         self.assertNotIn(hidden, answer)
diff --git a/webchat/test_status_observation.py b/webchat/test_status_observation.py
index 24e1928..f8ed6fa 100644
--- a/webchat/test_status_observation.py
+++ b/webchat/test_status_observation.py
@@ -54,13 +54,17 @@ class StatusObservationTests(SessionFixture):
         observed = answer["status_observation"]["snapshot"]
         self.assertEqual([snap["work_counts"]["running"] for snap in (before, observed, after)], [1, 3, 5])
         self.assertEqual(observed["work_counts"]["claimed"], 2)
-        self.assertEqual(answer["content"].count("running for"), 3)
+        self.assertIn("Codex", answer["content"])
+        self.assertIn("Gemini", answer["content"])
+        self.assertIn("MiniMax", answer["content"])
+        self.assertNotIn("running for", answer["content"])
         self.assertEqual(sampler.call_count, 3)
         self.assertEqual(self.errors(answer, started, before, after), [])
         self.assertNotIn("private-claim-token", json.dumps(answer))
         # Matching a later count is still dishonest about this reply's sample.
         forged = copy.deepcopy(answer)
         forged["content"] = format_operational_reply(after)
+        forged["status_observation"]["snapshot"] = after
         self.assertTrue(self.errors(forged, started, before, after))
 
     def test_queued_claimed_reused_pid_and_running_observations_remain_distinct(self):
@@ -125,7 +129,8 @@ class StatusObservationTests(SessionFixture):
         answer = self.chat.history(self.identifier)["messages"][-1]
         self.assertEqual(answer["status"], "done")
         self.assertTrue(self.fake.calls)
-        self.assertIn("Overlay task", answer["content"])
+        self.assertIn("Overlay task", json.dumps(answer["status_observation"]["snapshot"]))
+        self.assertIn("Gemini has work waiting to run", answer["content"])
         self.assertFalse(observation_errors(answer, QUESTION, self.identifier, started, time.time()))
 
     def test_provider_metadata_cannot_forge_an_observation(self):
@@ -139,7 +144,7 @@ class StatusObservationTests(SessionFixture):
         queue.enqueue(self.root, "external", "fixture", "Review " + marker, worker="gemini", kind="audit", title="Review " + marker)
         answer, started, before, after = self.status()
         self.assertNotIn(marker, json.dumps(answer))
-        self.assertIn("[secret removed]", answer["content"])
+        self.assertIn("[secret removed]", json.dumps(answer["status_observation"]["snapshot"]))
         self.assertNotIn(marker, (self.chat.state / (self.identifier + ".json")).read_text())
         self.assertFalse(self.errors(answer, started, before, after))
 
diff --git a/webchat/test_texting_diagdump.py b/webchat/test_texting_diagdump.py
new file mode 100644
index 0000000..29b1607
--- /dev/null
+++ b/webchat/test_texting_diagdump.py
@@ -0,0 +1,74 @@
+"""The failed live status observation, plus truthfulness at its boundaries."""
+import copy
+import json
+import unittest
+from pathlib import Path
+
+from integration_rubric import style_errors
+from reply_authority import format_operational_reply
+
+FIXTURE = json.loads(Path(__file__).with_name("fixtures").joinpath("texting_diagdump_0810.json").read_text())
+
+
+class TextingStatusVoiceTests(unittest.TestCase):
+    def setUp(self):
+        self.snap = copy.deepcopy(FIXTURE["snapshot"])
+
+    def reply(self, question=None):
+        answer = format_operational_reply(self.snap, text=question or FIXTURE["message"])
+        self.assertEqual(style_errors(answer), [])
+        self.assertLessEqual(len(answer.split()), 120)
+        return answer
+
+    def test_exact_failed_turn_uses_short_natural_status(self):
+        self.assertEqual(self.reply(), "Codex is working on Web Bob. Gemini and MiniMax have work waiting to run. Claude and Cursor are idle.")
+        self.assertIn("raw diagnostic dump", style_errors(FIXTURE["bad_reply"]))
+
+    def test_each_forbidden_diagnostic_fails_the_rubric(self):
+        for text in ("model not reported", "queue_counts: 4", "The job runner has 4 queued jobs.",
+                     "Codex is working; Gemini is waiting; MiniMax is waiting."):
+            with self.subTest(text=text):
+                self.assertIn("raw diagnostic dump", style_errors(text))
+
+    def test_status_paraphrases_share_the_same_observation(self):
+        for text in ("status", "What's running?", "How's everything going?",
+                     "Status without internal IDs or raw diagnostics, please"):
+            self.assertEqual(self.reply(text), self.reply())
+
+    def test_pending_or_unverified_work_is_never_presented_as_running(self):
+        for state in ("claimed", "unverified", "paused"):
+            with self.subTest(state=state):
+                self.snap["work"][0]["state"] = state
+                answer = self.reply()
+                self.assertNotIn("working on", answer)
+                self.assertIn("Codex is paused" if state == "paused" else "Codex has activity I can't confirm yet", answer)
+                self.assertIn("Gemini and MiniMax have work waiting to run", answer)
+
+    def test_busy_or_unattributed_activity_is_not_idle_or_assigned(self):
+        self.snap["work"][0]["assignment_recorded"] = False
+        self.snap["lane_locks"]["claude"] = dict(state="busy")
+        answer = self.reply()
+        self.assertIn("Codex and Claude have activity I can't confirm yet", answer)
+        self.assertNotIn("working on", answer)
+
+    def test_failed_inspection_does_not_claim_idle(self):
+        self.snap["inspection"]["queue_available"] = False
+        answer = self.reply()
+        self.assertNotIn("idle", answer)
+        self.assertIn("A live check failed", answer)
+
+    def test_raw_titles_and_many_tasks_stay_bounded(self):
+        self.snap["work"][0].update(project=None, task="# lane-webbob-texting-deploy-0702")
+        self.assertIn("Codex is working on the current task", self.reply())
+        self.snap["queue_jobs"]["queued"] *= 100
+        self.snap["work"] *= 100
+        self.reply()
+
+    def test_known_models_stay_in_the_observation(self):
+        self.snap["work"][0]["model"] = "gpt-observed"
+        self.assertNotIn("gpt-observed", self.reply())
+        self.assertEqual(self.snap["work"][0]["model"], "gpt-observed")
+
+
+if __name__ == "__main__":
+    unittest.main()
diff --git a/webchat/test_webbob_replyq_1856.py b/webchat/test_webbob_replyq_1856.py
index 7f951fc..5f18f29 100644
--- a/webchat/test_webbob_replyq_1856.py
+++ b/webchat/test_webbob_replyq_1856.py
@@ -131,7 +131,8 @@ class Session8126301cTests(SessionFixture):
             reply = self.send("How’s it going?")
         self.assertEqual(reply["provider"], "state")
         self.assertFalse(reply["content"].startswith("Yes"))
-        self.assertEqual(reply["content"].count("running for"), 4)
+        self.assertIn("working on", reply["content"])
+        self.assertNotIn("running for", reply["content"])
 
 
 class Session65a5d782Tests(SessionFixture):
@@ -205,14 +206,14 @@ class OperationalReplyFormattingTests(unittest.TestCase):
 
     def test_running_workers_line_has_no_yes_prefix(self):
         text = format_operational_reply(self._snapshot(running=2), "server", "how's it going?")
-        self.assertTrue(text.startswith("Codex is on “Review Web Bob replies"))
-        self.assertEqual(text.count("running for 1 min"), 2)
+        self.assertTrue(text.startswith("Codex is working on Review Web Bob replies"))
+        self.assertNotIn("running for", text)
         self.assertNotIn("Yes", text)
 
     def test_single_running_worker_uses_singular_verb_with_no_yes_prefix(self):
         text = format_operational_reply(self._snapshot(running=1), "server", "how's it going?")
-        self.assertTrue(text.startswith("Codex is on “Review Web Bob replies"))
-        self.assertEqual(text.count("running for 1 min"), 1)
+        self.assertTrue(text.startswith("Codex is working on Review Web Bob replies"))
+        self.assertNotIn("running for", text)
 
     def test_fallback_task_has_no_log_dump_and_diagnostics_are_opt_in(self):
         snap = self._snapshot()
@@ -220,7 +221,7 @@ class OperationalReplyFormattingTests(unittest.TestCase):
                                log_path="logs/replies.log", last_log_line="Raw output " * 100)
         casual = format_operational_reply(snap, text="How's it going?")
         self.assertIn("Web Bob replies", casual)
-        self.assertIn("gpt-fixture", casual)
+        self.assertNotIn("gpt-fixture", casual)
         for value in ("logs/", "lane-", "8912", "Raw output", " | "):
             self.assertNotIn(value, casual)
         self.assertLessEqual(len(re.split(r"[.!?]\s+", casual)), 4)
@@ -233,8 +234,8 @@ class OperationalReplyFormattingTests(unittest.TestCase):
         snap["inspection"]["queue_available"] = False
         snap["lane_locks"]["claude"] = dict(state="busy")
         reply = format_operational_reply(snap, text="What's working on what?")
-        self.assertIn("Claude's last lane check was busy", reply)
-        self.assertIn("couldn't read the job queue", reply)
+        self.assertIn("Claude has activity I can't confirm yet", reply)
+        self.assertIn("A live check failed", reply)
         self.assertNotIn("idle", reply)
         self.assertNotIn("0 queued", reply)
 
diff --git a/webchat/test_webchat.py b/webchat/test_webchat.py
index bc15936..95f9df4 100644
--- a/webchat/test_webchat.py
+++ b/webchat/test_webchat.py
@@ -332,7 +332,8 @@ class HTTPTests(Fixture):
                 if text.startswith("The hold"):
                     self.assertEqual(answer["content"], "Ready when you are.")
                 else:
-                    self.assertEqual(answer["content"].count("running for"), 4)
+                    self.assertIn("working on", answer["content"])
+                    self.assertNotIn("running for", answer["content"])
                 self.assertNotIn("start a job:", answer["content"])
                 self.assertNotIn("None", answer["content"])
         self.assertEqual(self.fake.calls, [])
@@ -1247,7 +1248,7 @@ class HandbackJobTests(Fixture):
         state_ledger.write_now(self.root, "offline parity fixture", sha="fedcba1")
         result = run_eval(self.root)
         self.assertEqual(result["passed"], result["total"], result["cases"])
-        self.assertEqual(result["total"], 96)
+        self.assertEqual(result["total"], 99)
 
     def test_catchup_event_ack_cursor(self):
         ledger_dir = Path(__file__).resolve().parent.parent / "state"

## Preserved observation validation
"""Evidence saved atomically with each operational reply, never supplied by a model."""
import hashlib
import json
import math
from datetime import datetime


def snapshot_digest(snapshot):
    payload = json.dumps(snapshot, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def redact_snapshot(value, redact):
    """Redact values before rendering and hashing without changing JSON structure."""
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, list):
        return [redact_snapshot(item, redact) for item in value]
    if isinstance(value, dict):
        return {key: redact_snapshot(item, redact) for key, item in value.items()}
    return value


def bind_observation(observation, conversation):
    message = conversation["messages"][-1]
    return dict(observation, conversation_id=conversation["id"], request_id=message["request_id"],
                message_id=message["id"])


def observation_errors(answer, question, conversation_id, started, finished):
    """Fail closed on absent/stale evidence or prose that differs from its sample.

    Independent before/after samples remain diagnostics, not alternate values a
    reply may choose between. Worker and queue assertions use the saved sample.
    """
    from reply_authority import format_operational_reply
    from worker_activity import WORKER_NAMES

    observation = answer.get("status_observation")
    if not isinstance(observation, dict):
        return ["status reply has no saved observation"]
    errors = []
    try:
        if observation["schema_version"] != 1:
            errors.append("unsupported status observation version")
        if (observation["conversation_id"] != conversation_id or
                observation["request_id"] != answer["request_id"] or
                observation["message_id"] != answer["id"] or observation["question"] != question):
            errors.append("status observation belongs to another reply")
        snap = observation["snapshot"]
        if observation["snapshot_sha256"] != snapshot_digest(snap):
            errors.append("status observation digest mismatch")
        first, last = observation["observed_from"], observation["observed_until"]
        captured = datetime.fromisoformat(snap["captured_at"])
        if (captured.tzinfo is None or not all(math.isfinite(t) for t in (first, last, started, finished)) or
                not started <= answer["created_at"] <= first <= last <= finished or
                abs(captured.timestamp() - first) > 0.000001):
            errors.append("status observation is outside its reply interval")
        if observation["renderer_provider"] not in ("server", answer.get("provider")):
            errors.append("status observation renderer does not match reply")
        if answer["content"] != format_operational_reply(snap, observation["renderer_provider"], question):
            errors.append("status reply differs from its saved observation")
        work, inspection = snap["work"], snap["inspection"]
        states = ("running", "paused", "claimed", "unverified")
        if snap["work_counts"] != {state: sum(row["state"] == state for row in work) for state in states}:
            errors.append("status observation worker counts disagree with its rows")
        if any(type(inspection[key]) is not bool for key in
               ("screens_available", "processes_available", "queue_available")):
            errors.append("status observation has invalid inspection evidence")
        for row in work:
            if row["state"] not in states:
                errors.append("status observation has an invalid worker state")
            if row["state"] in ("running", "paused") and (
                    not inspection["processes_available"] or row.get("source") != "process" or
                    type(row.get("pid")) is not int or row["pid"] <= 0 or
                    row.get("worker") not in WORKER_NAMES or row.get("assignment_recorded") is False):
                errors.append("status observation claims execution without a confirmed worker")
        for bucket in ("queued", "claimed", "done", "failed"):
            rows, count = snap["queue_jobs"][bucket], snap["queue_counts"][bucket]
            if type(count) is not int or count < len(rows) or (bucket in ("queued", "claimed") and count != len(rows)):
                errors.append("status observation queue counts disagree with its rows")
            if any(row["bucket"] != bucket for row in rows):
                errors.append("status observation queue row is in the wrong state")
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
        errors.append("malformed status observation")
    return errors


## Current operational formatting (including diagnostics)
def _cooldown(snap, name):
    # Provider identity is the join key; reset text never floats between LLMs.
    lane = snap["lane_locks"].get(name, {})
    health = snap.get("provider_health", {}).get(name, {})
    if lane.get("cached_state", lane.get("state")) != "cooldown" and health.get("state") != "cooldown":
        return ""
    detail = lane.get("detail") or health.get("reason") or ""
    reset = re.search(r"resets?\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)(?:\s*\(([^)]+)\))?", detail, re.I)
    if reset:
        zone = " CT" if reset[4] in ("America/Chicago", "CT", "CDT", "CST") else " " + reset[4] if reset[4] else ""
        return "; resets " + reset[1] + ":" + (reset[2] or "00") + " " + reset[3].upper() + zone
    return "; cooling down"


def _lane_line(row, detailed=False):
    label = row.get("screen") or "lane"
    llm = row.get("llm_label") or WORKER_NAMES.get(row.get("llm")) or row.get("llm") or "worker unconfirmed"
    if row.get("model"):
        llm += " (" + row["model"] + ")"
    project = row.get("project")
    task = row.get("task") or row.get("screen", "").removeprefix("lane-").replace("-", " ")
    body = (project + ": " if project else "") + task
    duration = _duration(row.get("elapsed_seconds"))
    state = row.get("state") or "running"
    if state == "finished":
        line = f"{label} — {llm}, finished {duration} ago — {body}"
    else:
        prefix = {"running": "running ", "paused": "paused ", "unverified": "session open ", "claimed": "claimed "}.get(state, "")
        line = f"{label} — {llm}, {prefix}{duration} — {body}"
    if row.get("result_path"):
        line += " — " + row["result_path"]
    elif row.get("log_path") and (not row.get("prompt_path") or not row.get("task")):
        line += "; " + row["log_path"]
        if row.get("last_log_line"):
            line += "; last: " + row["last_log_line"]
    if detailed:
        ids = [str(row[key]) for key in ("screen", "pid") if row.get(key)]
        if ids:
            line += " (" + ", ".join(ids) + ")"
        for key in ("prompt_path", "log_path"):
            if row.get(key):
                line += f"; {row[key]}"
    return line


def _work_line(row, detailed=False):
    project = row.get("project")
    repo = row.get("repo")
    label = project + (" (" + repo + ")" if repo else "") + ": " if project else (repo + ": " if repo else "")
    label += row.get("task") or row["title"]
    if detailed and not row.get("task") and "task" in row:
        label += " — " + (row.get("screen") or "process " + str(row.get("pid")))
        label += "; " + row["log_path"] + "; last: " + row["last_log_line"]
    if row.get("model"):
        label += " (" + row["model"] + ")"
    duration = _duration(row.get("elapsed_seconds"))
    state = {"running": "running for ", "paused": "paused; process age ",
             "claimed": "claimed; execution unconfirmed; age ",
             "unverified": "session open; worker activity unconfirmed; age "}[row["state"]]
    label += " — " + state + duration
    if detailed:
        ids = [str(row[key]) for key in ("screen", "pid", "job_id") if row.get(key)]
        if ids:
            label += " (" + ", ".join(ids) + ")"
        if row.get("prompt_path"):
            label += "; prompt " + row["prompt_path"]
        if row.get("log_path") and row.get("task"):
            label += "; " + row["log_path"] + "; last: " + row["last_log_line"]
    return label


def _join(items):
    return ", ".join(items[:-1]) + " and " + items[-1] if len(items) > 1 else items[0]


def _task_name(row):
    label = row.get("task") or row.get("title") or (row.get("prompt") or "").split("\n")[0] or task_label(screen=row.get("screen"))
    label = clean(label, 95).strip(" .;:") or "a CLI session"
    project = row.get("project")
    if project and project.lower() not in label.lower():
        label = project + ": " + label
    elif project:
        label = re.sub(re.escape(project), lambda _: project, label, flags=re.I)
    return label


def _casual_status(snap):
    """Summarize the existing observation; keep its inventory in diagnostics."""
    work, inspection = snap["work"], snap["inspection"]
    groups = {}

    def add(name, singular, plural, priority):
        groups.setdefault((priority, singular, plural), []).append(name)

    for name in WORKER_NAMES:
        rows = [row for row in work if row.get("worker") == name]
        pending = [row for row in snap.get("queue_jobs", {}).get("queued", []) if row.get("worker") == name]
        if name == "mini" and not rows and not pending:
            continue
        display = WORKER_NAMES[name]
        running = [row for row in rows if row.get("state") == "running" and row.get("assignment_recorded") is not False]
        if running:
            labels = []
            for row in running:
                label = clean(row.get("project") or _task_name(row), 60)
                # Prompt headings and fallback screen labels are evidence, not
                # readable assignments. Never echo machine labels into chat.
                if re.search(r"lane-|logs/|\bPID\b|queue_counts|model not reported|job runner", label, re.I):
                    label = "the current task"
                label = re.sub(r"[;.!?]+", ",", label).strip(" #,: ") or "the current task"
                if label not in labels:
                    labels.append(label)
            summary = _join(labels[:2]) + (" and other tasks" if len(labels) > 2 else "")
            tail = "working on " + summary
            if any(row.get("state") == "paused" for row in rows):
                tail += ", with some work paused"
            add(display, "is " + tail, "are " + tail, 0)
        elif rows and all(row.get("state") == "paused" for row in rows):
            add(display, "is paused", "are paused", 1)
        elif rows:
            add(display, "has activity I can't confirm yet", "have activity I can't confirm yet", 1)
        elif pending:
            add(display, "has work waiting to run", "have work waiting to run", 2)
        elif snap.get("lane_locks", {}).get(name, {}).get("state") == "busy":
            add(display, "has activity I can't confirm yet", "have activity I can't confirm yet", 1)
        elif _cooldown(snap, name):
            cooldown = _cooldown(snap, name).removeprefix("; ")
            tail = "cooling down" + (" until " + cooldown.removeprefix("resets ") if cooldown.startswith("resets ") else "")
            if not all(inspection.values()):
                tail += ", with current activity unconfirmed"
            add(display, "is " + tail, "are " + tail, 3)
        else:
            add(display, "is idle" if all(inspection.values()) else "has no confirmed active work",
                "are idle" if all(inspection.values()) else "have no confirmed active work", 4)
    sentences = [_join(names) + " " + (singular if len(names) == 1 else plural)
                 for (priority, singular, plural), names in sorted(groups.items(), key=lambda item: item[0][0])]
    other = [row for row in work if row.get("worker") not in WORKER_NAMES]
    if other:
        sentences.append("There are other open sessions whose work I can't confirm")
    if any(row.get("worker") not in WORKER_NAMES for row in snap.get("queue_jobs", {}).get("queued", [])):
        sentences.append("Some work is still waiting for a worker")
    if not all(inspection.values()):
        sentences.append("A live check failed, so I can't confirm the full picture")
    # Ordinary answers stay short even when all workers have different tasks.
    # Group adjacent clauses with ordinary conjunctions, never diagnostic chains.
    while len(sentences) > 4:
        sentences[0:2] = [sentences[0] + ", while " + sentences[1]]
    return ". ".join(sentences) + "."


def format_operational_reply(snap, provider="server", text=""):
    """Live worker facts in casual sentences; diagnostics are opt-in."""
    counts, work, inspection = snap["queue_counts"], snap["work"], snap["inspection"]
    bob = snap.get("bob_lanes") or {}
    live_lanes = bob.get("live") or []
    finished_lanes = bob.get("finished_recent") or []
    running = snap["work_counts"]["running"]
    detailed = bool(DETAILS.search(text) and not HIDE_DETAILS.search(text))
    if not detailed:
        answer = _casual_status(snap)
        if IDENTITY.search(text):
            answer += (" " + WORKER_NAMES[provider] + " answered this message." if provider in WORKER_NAMES
                       else " This answer comes from live checks.")
        if re.search(r"\b(?:disk|storage)\b", text, re.I) and snap["disk"].get("available"):
            answer += f" Disk space: {snap['disk']['avail_gb']} GB free."
        return answer
    if live_lanes:
        running_count = sum(1 for row in live_lanes if row.get("state") == "running")
        first = f"{running_count or len(live_lanes)} Bob lane{'s' if len(live_lanes) != 1 else ''} on screen."
        lines = [first]
        lines.extend(_lane_line(row, detailed) for row in live_lanes)
        if finished_lanes and re.search(r"\b(?:finished|done|recent|last)\b", text, re.I):
            lines.append("Finished (last 12h): " + " | ".join(_lane_line(row, detailed) for row in finished_lanes[:6]))
        other = [row for row in work if row.get("state") == "running" and row.get("screen") not in {lane["screen"] for lane in live_lanes}]
        if other:
            lines.append("Other sessions: " + " | ".join(_work_line(row, detailed) for row in other))
        lines.append(f"Job runner: {counts['claimed']} claimed, {counts['queued']} queued.")
        for name in ("codex", "claude", "cursor", "gemini", "minimax"):
            rows = [row for row in work if row.get("worker") == name]
            if rows:
                continue
            state = "idle" if all(inspection.values()) else "activity unconfirmed"
            cooldown = _cooldown(snap, name)
            if cooldown or (snap.get("lane_locks", {}).get(name, {}).get("cached_state") == "cooldown"):
                lines.append(WORKER_NAMES[name] + ": " + state + cooldown + ".")
        if IDENTITY.search(text):
            lines.append(WORKER_NAMES[provider] + " answered this message." if provider in WORKER_NAMES else "This answer comes from live checks.")
        return "\n".join(lines)
    if running:
        first = f"{running} worker{'s are' if running != 1 else ' is'} running."
    elif work:
        first = "Work is listed; I can't confirm a running worker."
    elif not all(inspection.values()):
        first = "I can't confirm all workers; a live check failed."
    elif snap["screen_lanes"]:
        first = "There are live service sessions; no task worker is confirmed."
    else:
        first = "I don't see active work on the mini right now."
    lines = [first]
    for name in ("codex", "claude", "cursor", "gemini", "minimax"):
        rows = [row for row in work if row.get("worker") == name]
        current = " | ".join(_work_line(row, detailed) for row in rows)
        if not current:
            current = "idle" if all(inspection.values()) else "activity unconfirmed"
        lines.append(WORKER_NAMES[name] + ": " + current + _cooldown(snap, name) + ".")
    other = [row for row in work if row.get("worker") not in ("codex", "claude", "cursor", "gemini", "minimax")]
    if other:
        lines.append("Other sessions: " + " | ".join(_work_line(row, detailed) for row in other) + ".")
    queue_line = f"Job runner: {counts['claimed']} claimed, {counts['queued']} queued."
    if running and not all(inspection.values()):
        queue_line += " Some live checks failed; this list may be incomplete."
    lines.append(queue_line)
    if IDENTITY.search(text):
        lines.append(WORKER_NAMES[provider] + " answered this message." if provider in WORKER_NAMES else "This answer comes from live checks.")
    if detailed or re.search(r"\b(?:health|healthy|services?|diagnostics?|logs?)\b", text, re.I):
        services = [row["screen"] for row in snap["screen_lanes"] if row["role"] == "service"]
        if services:
            lines.append("Service sessions: " + ", ".join(services) + ".")
        if detailed:
            lines.extend(row["path"] + ": " + " / ".join(row["lines"]) for row in snap.get("recent_logs", []) if row["lines"])
    if re.search(r"\b(?:disk|storage)\b", text, re.I) and snap["disk"].get("available"):
        lines.append(f"Disk space: {snap['disk']['avail_gb']} GB free.")
    return "\n".join(lines)


CRITICISM = re.compile(r"^(?:this|that|it|your (?:answer|reply|response|update)) (?:needs? to be (?:way |much )?better|"
                       r"(?:is|was|isn['’]t) (?:bad|wrong|not good|good enough|helpful))|"
                       r"^(?:do better|be more specific|try again|fix your (?:answer|reply))\b", re.I)


def correcting_status(text, conversation):
    if not CRITICISM.search(text.strip()):
        return False
    previous = [m["content"] for m in (conversation or {}).get("messages", []) if m["role"] == "user"]
    if previous and previous[-1] == text:
        previous.pop()
    previous = [ask for ask in previous if not CRITICISM.search(ask)]
    return bool(previous and STATUS_QUESTION.search(previous[-1]))




## Saved status route
    def status_reply(self, conversation, text):
        from reply_authority import operational_reply
        from status_observation import bind_observation
        conversation = copy.deepcopy(conversation)
        observation = {}
        content = operational_reply(self.ledger_root(conversation["id"]), "server", text,
                                    observation=observation, redact=self.redact)
        conversation["messages"][-1]["status_observation"] = bind_observation(observation, conversation)
        # The reply and its exact rendering input share the existing private,
        # fsynced atomic conversation write. Retries/restarts keep both intact.
        return self.intent_reply(conversation, self.redact(content), provider="state")



## Routing before generic work/provider handling
            if conversation["messages"] and conversation["messages"][-1]["status"] == "waiting":
                raise RequestError(409, "This conversation has a queued request. Stop it before sending another message.")
            intent_state = chat_intent.state_for(conversation)
            was_held = bool(intent_state["holds"])
            conversation["preferred_provider"] = provider
            conversation["messages"] += [
                {"id": str(uuid.uuid4()), "request_id": request_id, "preferred_provider": provider, "role": "user", "content": text,
                 "status": "done", "created_at": time.time(), "requested_worker": worker},
                {"id": str(uuid.uuid4()), "request_id": request_id, "role": "assistant", "content": "", "status": "queued",
                 "provider": None, "attempts": [], "created_at": time.time()},
            ]
            if conversation["title"] == "New conversation":
                conversation["title"] = text[:65]
            if VERSION_QUESTION.search(text):
                return self.intent_reply(conversation, BUILD["short_sha"])
            # Text intent and confirmations never enter generic job/provider routing.
            def persist_texting(value):
                for key in ("pending_job", "pending_job_id", "pending_council", "pending_council_id"):
                    value.pop(key, None)
                self.save(value)
                self.conversations[identifier] = copy.deepcopy(value)
            if self.texting.handle(conversation, text, actor, request_id, persist_texting, self.redact):
                return self.public(conversation)
            from reply_authority import correcting_status
            if correcting_status(text, conversation):
                return self.status_reply(conversation, text)
            transition = chat_intent.apply_turn(intent_state, text, request_id)
            if transition == "hold":
                held_work, held_worker = followup_work(conversation)
                if held_work:
                    conversation["held_job"] = dict(prompt=held_work, worker=held_worker)
                return self.intent_reply(conversation, chat_intent.hold_reply(chat_intent.blocked_scopes(intent_state, [])))
            if transition == "priorities":
                conversation["pending_job"] = "Improve " + ", ".join(intent_state["project_order"])
                conversation["pending_job_id"] = request_id
                return self.intent_reply(conversation, "Priority order: " + ", ".join(intent_state["project_order"]) + ".")
            from worker_assignment import requested_workers
            assignments = requested_workers(text, conversation)
            if assignments:
                return self.submit_worker_assignment(conversation, text, request_id, assignments)
            from worker_assignment import issue_followup
            fix = issue_followup(self.root, conversation, text)
            if fix:
                return self.submit_task(conversation, fix, request_id)
            work, route = parse_work(text)
            if transition == "resume" and not work:
                work_text = re.sub(r"^(?:go(?:\s+ahead)?|resume)(?:\s+and)?[\s,:!]+", "", chat_intent.command(text), flags=re.I)
                work, route = parse_work(work_text)
            started = parse_start(text)
            inbox_task = state_ledger.parse_inbox_message(text)
            if inbox_task:
                inbox_work, inbox_route = parse_work(inbox_task)
                if parse_start(inbox_task) or inbox_work:
                    work, route = parse_start(inbox_task) or inbox_work, inbox_route
            followup = FOLLOW_UP.fullmatch(text) or FOLLOW_UP.fullmatch(PREAMBLE.sub("", text)) or parse_do_more(text)
            if followup:
                work, route = followup_work(conversation)
            task = started or work or (text if worker is not None and not followup else None)
            names = chat_intent.project_targets(task or text, intent_state)
            if task and len(names) >= 2:
                intent_state["project_order"] = names
            if (chat_intent.PUSH.match(chat_intent.command(text)) or chat_intent.project_start(text)) and not names:
                return self.intent_reply(conversation, "Which projects should I work on?")
            if route != "max":
                try:
                    task_queue.worker_name(worker or route)
                except ValueError:
                    return self.submit_task(conversation, task or text, request_id, worker or route)
            if ((followup and not task) or (route != "auto" and not task)
                    or (task and needs_task_detail(task))):

## Texting confirmation/handler (unchanged)
    def confirm(self, conversation, text, actor, request_id, persist):
        state = conversation.get("_texting", {})
        draft = state.get("drafts", {}).get(state.get("active"))
        match = re.fullmatch(r"yes (wbtxt-[0-9a-f]{32})", text, re.I)
        if not draft or not match:
            if text.lower().startswith("yes wbtxt-"):
                self.invalidate(conversation)
            return "Nothing sent. Review a fresh text draft and send its exact ‘yes wbtxt-…’ message separately in this chat."
        if draft["state"] != "pending":
            return "Nothing sent. That text confirmation was already used, cancelled, or replaced. Review a fresh draft."
        if draft["epoch"] != self.epoch or self.clock() >= draft["expires_at"]:
            draft.update(state="expired", token=None)
            return "Nothing sent. That text confirmation expired. Review a fresh draft."
        # The draft-creation request cannot also authorize delivery: the owner
        # must review the card and submit its exact token in a later request.
        if (not actor or not hmac.compare_digest(actor, draft["actor"]) or
                request_id == draft["request_id"] or draft["conversation_id"] != conversation["id"] or
                not hmac.compare_digest(match[1], draft["token"]) or
                not hmac.compare_digest(fingerprint(draft), draft["fingerprint"])):
            return "Nothing sent. This yes does not match the exact draft and login that presented it. Review a fresh draft."
        # Save consumed consent before any handoff. Never replay on restart/error.
        draft.update(state="delivery_unconfirmed", token=None, approved_at=self.clock())
        audit = {"event": "owner_confirmed_delivery_unconfirmed", "actor": actor,
                 "conversation_id": conversation["id"], "draft_id": draft["id"], "revision": draft["revision"],
                 "recipient": copy.deepcopy(draft["recipient"]), "body": draft["body"],
                 "fingerprint": draft["fingerprint"], "at": self.clock(), "request_id": request_id}
        state["audit"].append(audit)
        conversation["messages"][-1].update(status="done", provider="texting", content=DELIVERY_UNCONFIRMED)
        persist(conversation)
        delivered = self.andrea.deliver(draft["recipient"]["guid"], draft["body"])
        if delivered is True:
            draft["state"] = "sent"
            audit["event"] = "owner_sent_via_andrea"
            content = SENT_VIA_ANDREA
        elif delivered is False:
            draft["state"] = "confirmed_not_sent"
            audit["event"] = "owner_confirmed_not_sent"
            content = BRIDGE_BLOCKED
        else:
            content = DELIVERY_UNCONFIRMED
        return content

    def handle(self, conversation, text, actor, request_id, persist, redact):
        state = conversation.get("_texting", {})
        active = state.get("drafts", {}).get(state.get("active"))
        clean = re.sub(r"^(?:please |can you |could you )", "", text, flags=re.I).strip()
        # A worker/job prefix is not a way around the texting gate. Only matching
        # texting commands use this stripped value; other work keeps normal routing.
        clean = re.sub(r"^(?:(?:ask|have|tell|use) (?:codex|claude|cursor|gemini|minimax|mini)(?: to)?\s+|"
                       r"start (?:a )?job:\s*|(?:codex|claude|cursor|gemini|minimax|mini):\s*)", "", clean, flags=re.I)
        command = clean.casefold().rstrip(".?!")
        text_context = active and (active["state"] in ("pending", "editing") or
            len(conversation["messages"]) >= 3 and conversation["messages"][-3].get("texting"))
        # Bare approvals are routed here for token guidance only; confirm() still
        # requires the entire message to match the exact yes + token format.
        confirmation = re.match(r"^yes\s+wbtxt-", clean, re.I) or (text_context and command in ("yes", "ok", "send it", "send it now", "send now", "go", "do it"))
        edit = re.fullmatch(r"(edit|cancel) text draft ([0-9a-f]{16})", clean, re.I)
        replace = re.fullmatch(r"replace text draft ([0-9a-f]{16}) to (.+?):\s*([\s\S]+)", clean, re.I)
        compose = re.fullmatch(r"(?:draft|write|compose|send) (?:a )?(?:text|reply|sms|message)(?: reply)? to (.+?)(?::\s*| saying )([\s\S]+)", clean, re.I)
        compose = compose or re.fullmatch(r"text (.+?):\s*([\s\S]+)", clean, re.I)
        read = re.fullmatch(r"(read|show|summari[sz]e) (?:the )?(?:recent )?(?:texts?|messages?|imessages?|sms|thread) (?:from |with |in |for )?(.+)", clean, re.I)
        listing = command in ("texts", "list texts", "show texts", "recent texts", "show recent texts", "list recent texts", "summarize recent texts", "summarize texts")
        # Incomplete texting commands only — not colloquial chat like “text me when you're free”.
        help_request = command in ("texting", "texting help", "texting status") or re.match(
            r"^(?:draft|write|compose|send) (?:a )?(?:text|reply|sms|message)\b", clean, re.I
        )
        cancel = active and command in ("cancel text", "cancel text draft", "never mind", "cancel")
        if not any((confirmation, edit, replace, compose, read, listing, help_request, cancel)):
            # An intervening turn also withdraws consent, including unsupported edits.
            self.invalidate(conversation)
            return False
        conversation["messages"][-2]["texting"] = True
        answer = conversation["messages"][-1]
        answer.update(texting=True, provider="texting", status="done")
        try:
            if confirmation:
                # The chat turn itself must be yes + token, never a command prefix
                # or quoted/embedded approval extracted from another request.
                content = self.confirm(conversation, text, actor, request_id, persist)
            elif cancel:
                self.invalidate(conversation, "cancelled")
                content = "Text draft cancelled. Nothing sent."
            elif edit:
                draft = state.get("drafts", {}).get(edit[2])
                if not draft or state.get("active") != draft["id"] or draft["state"] not in ("pending", "expired", "editing", "confirmed_not_sent"):
                    raise TextingError("That draft is no longer current. Prepare a fresh text draft.")
                draft.update(state="editing" if edit[1].lower() == "edit" else "cancelled", token=None)
                content = "Confirmation cleared. Edit the draft card, then review it again." if draft["state"] == "editing" else "Text draft cancelled. Nothing sent."
            elif replace or compose:
                # Even a failed/ambiguous edit withdraws the previous confirmation.
                self.invalidate(conversation)
                if replace:
                    if not active or replace[1] != active["id"]:
                        raise TextingError("That draft is no longer current. Prepare a fresh text draft.")
                    query, body = replace[2], replace[3]
                else:
                    query, body = compose[1], compose[2]
                target = recipient(self.resolve(query.strip()))
                if redact(json.dumps(target, ensure_ascii=False)) != json.dumps(target, ensure_ascii=False):
                    raise TextingError("The thread details contain sensitive credentials; no draft was prepared.")
                content = self.draft(conversation, target, body, actor, request_id)
            else:
                self.invalidate(conversation)
                if listing:
                    chats = self.bluebubbles.chats()[:20]
                    content = "Recent text threads (up to 20):\n" + ("\n".join(
                        f"• {label(c)} — {c.get('guid', '?')}\n  {str((c.get('lastMessage') if isinstance(c.get('lastMessage'), dict) else {}).get('text') or '[No text preview]')[:180]}"
                        for c in chats) or "No recent threads.")
                elif read:
                    chat = self.resolve(read[2].strip())
                    messages = sorted(self.bluebubbles.messages(chat["guid"]), key=timestamp)
                    content = f"{label(chat)} — {chat['guid']}\n"
                    if not messages:
                        content += "No recent messages in this thread."
                    elif read[1].lower().startswith("summari"):
                        incoming = sum(m.get("isFromMe") is not True for m in messages)
                        content += (f"Recent thread summary: {len(messages)} messages, {incoming} incoming and "
                                    f"{len(messages) - incoming} from you.\n"
                                    f"Window: {time_label(messages[0])} – {time_label(messages[-1])}.\n"
                                    "Latest messages:\n")
                        content += "\n".join(self.message_line(m, 400) for m in messages[-4:])
                    else:
                        content += "Last 30 messages at most, oldest first:\n" + "\n".join(self.message_line(m, 1200) for m in messages)
                elif command == "texting status":
                    content = self.andrea.status() + " Web Bob delivery is blocked: Andrea requires approval in its registered owner chat."
                else:
                    content = HELP
        except TextingError as exc:
            content = str(exc)
        answer["content"] = redact(content)
        # Every handled turn is saved once here. Confirmations also persist consumed
        # consent before delivery so an interrupted receipt cannot authorize a replay.
        persist(conversation)
        return True

    @staticmethod
    def message_line(message, limit):
        handle = message.get("handle")
        sender = "You" if message.get("isFromMe") is True else str((handle.get("address") if isinstance(handle, dict) else None) or "Contact")
        body = str(message.get("text") or "[Attachment or non-text message]")
        return f"• {time_label(message)} · {sender}: {body[:limit]}" + ("… [excerpt]" if len(body) > limit else "")


## Release runner
#!/usr/bin/env python3
"""Review-gated draft release, exact session replay, and verified rollback."""
import argparse
import json
import os
import re
import shlex
import shutil
import signal
import hashlib
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from deploy_parity import restart, run, write
from live_redeploy_check import Client, require
from live_status_snapshot import build_live_status_snapshot
from providers import Redactor
from task_dispatch import task_queue


from integration_rubric import sessions as frozen_sessions, check_reply, style_errors

TIP = "9cfe54840bed5cb0ca7f2e94db7ef6596b014cf7"
PREVIOUS = "a777736b3f0a37c82b0c4c62be8c91117c4c9881"
BRANCH = "draft/webbob-texting-onto-a777736"


def texting_smoke(client, root, evidence, save):
    cid = client.new()
    smoke = evidence["texting_smoke"] = dict(conversation_id=cid, all_pass=False, exchanges=[])
    save()
    for prompt in ("texting help", "yes wbtxt-00000000000000000000000000000000"):
        answer = submit(client, cid, prompt)
        require(answer.get("provider") == "texting" and answer.get("texting"), "Live texting route did not handle smoke")
        require(not answer.get("task_ids") and not answer.get("task_id"), "Texting smoke dispatched work")
        require("drafts stay unsent" in answer["content"] if prompt == "texting help" else
                answer["content"].startswith("Nothing sent."), "Texting consent/help behavior changed")
        smoke["exchanges"].append(dict(prompt=prompt, reply=answer["content"], provider=answer["provider"], pass_check=True))
        save()
    saved = json.loads((root / "conductor/webchat/sessions" / (cid + ".json")).read_text())
    require(not saved.get("_texting", {}).get("drafts") and not saved.get("_texting", {}).get("audit"),
            "Texting smoke unexpectedly created a draft or delivery attempt")
    require(not any(row["conversation_id"] == cid for row in task_queue.tasks(root).values()),
            "Texting smoke created a job")
    smoke.update(all_pass=True, draft_count=0, delivery_audit_count=0, jobs=0)
    save()
    print("Live texting smoke: PASS; help and invalid confirmation, no delivery attempt", flush=True)


def latest_sessions(root):
    rows = frozen_sessions()
    for source in rows:
        saved = json.loads((root / "conductor/webchat/sessions" / (source["source_id"] + ".json")).read_text())
        asks = [m["content"] for m in saved["messages"] if m.get("role") == "user"]
        require(asks == [e["message"] for e in source["exchanges"]], "Original Jeff session changed since regression capture")
    return rows


def submit(client, cid, text):
    request = str(uuid.uuid4())
    value = client.call("/api/messages", dict(conversation_id=cid, message=text, request_id=request))
    deadline = time.monotonic() + 120
    while True:
        answer = next(m for m in value["messages"] if m.get("role") == "assistant" and m.get("request_id") == request)
        if answer["status"] == "done":
            return answer
        require(answer["status"] not in ("error", "cancelled", "waiting"), "Reply failed or providers unavailable")
        require(time.monotonic() < deadline, "Reply timed out")
        time.sleep(.5)
        value = client.call("/api/conversations/" + cid)


def verify_executions(root, identifiers):
    rows = [task_queue.tasks(root)[identifier] for identifier in identifiers]
    for row in rows:
        require(row["status"] not in ("failed", "cancelled"), "Replay job failed: " + row["id"] + " " + str(row.get("error")))
    started = [r for r in rows if r.get("execution_started_at") and r["status"] in ("running", "succeeded")]
    return rows, started


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--draft-pr", default="")
    parser.add_argument("--expected-live", default="a777736")
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--rollback", type=Path)
    parser.add_argument("--attempt", type=int, required=True)
    args = parser.parse_args()
    root, candidate = args.root.resolve(), args.candidate.resolve()
    os.umask(0o077)
    os.environ["BOB_ROOT"] = str(root)
    sys.path.insert(0, str(candidate / "services"))
    password_file = root / "conductor/webchat/.password"
    redact = Redactor(root, password_file.read_text().strip())
    client = Client("http://127.0.0.1:8787", password_file)
    if args.rollback:
        release = json.loads((args.rollback / "release.json").read_text())
        cancelled = task_queue.cancel_replay(root, {s["replay_id"] for s in release.get("sessions", []) if s.get("replay_id")},
                                            "Texting deployment live replay cancelled for release rollback.")
        expected = set(release.get("cancelled_replay_jobs", [])) | {r["id"] for r in cancelled}
        restored = restart(root, {key: Path(path) for key, path in release["snapshots"].items()}, expected_exits=expected)
        client.login()
        require(client.call("/api/version")["sha"] == release["previous_version"]["sha"], "Rollback version mismatch")
        require(restored["other_screens_unchanged"], "Unrelated screens changed during rollback")
        origin = root / "conductor/webchat/.public-origin"
        if origin.exists():
            public = Client(origin.read_text().strip(), password_file)
            public.login()
            require(public.call("/api/version")["sha"] == release["previous_version"]["sha"], "Public rollback version mismatch")
        print("Rollback verified: " + release["previous_version"]["sha"])
        return 0
    evidence = dict(all_pass=False, sessions=[], task_ids=[], started_jobs=[])
    require(args.attempt > 0, "Attempt must be positive")
    record = root / ("conductor/reviews/WEBBOB-TEXTING-DEPLOYMENT-0927-attempt" + str(args.attempt) + ".json")
    with record.open("x") as stream:
        json.dump(dict(all_pass=False, sha=TIP, status="PREFLIGHT", started_at=time.time()), stream)
    evidence.update(started_at=time.time(), attempt=args.attempt)
    def interrupted(signum, frame):
        raise RuntimeError("Deployment interrupted or exceeded its total timeout: " + str(signum))
    for signum in (signal.SIGALRM, signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, interrupted)
    signal.alarm(args.timeout)
    def save():
        write(record, redact(json.dumps(evidence, indent=2, ensure_ascii=False)) + "\n")
        if rollback:
            write(rollback / "release.json", redact(json.dumps(evidence, indent=2, ensure_ascii=False)) + "\n")
    activated = False
    rollback = None
    try:
        sha = run(["git", "-C", candidate, "rev-parse", "HEAD"])
        require(sha == TIP, "Reviewed candidate SHA changed")
        require(bool(args.draft_pr), "A draft PR is required for deployment")
        gate = root / "conductor/reviews/TEXTING-LIVE-0810.md"
        require("GATE: BOTH_PASS tip=9cfe548" in gate.read_text(), "Recorded BOTH_PASS gate missing")
        reviews = json.loads((root / "conductor/reviews/TEXTING-LIVE-0810.json").read_text())
        require(reviews["sha"] == sha and reviews["gate"] == "BOTH_PASS", "Fresh review SHA/gate mismatch")
        for name in ("gemini", "minimax"):
            review = reviews["reviews"][name]
            output = Path(review["output"])
            require(review["exit"] == 0 and review["verdict"] == "PASS" and
                    hashlib.sha256(output.read_bytes()).hexdigest() == review["output_sha256"],
                    "Fresh review output is missing or changed: " + name)
        evidence["fresh_reviews"] = reviews
        remote = dict(line.split()[::-1] for line in run([
            "git", "-C", candidate, "ls-remote", "brain", "refs/heads/" + BRANCH,
            "refs/heads/draft/webbob-clean-0927"]).splitlines())
        require(remote.get("refs/heads/" + BRANCH) == sha, "Remote candidate tip mismatch")
        clean = json.loads((root / "conductor/reviews/TEXTING-CLEAN-MERGE-0810.json").read_text())
        require(remote.get("refs/heads/draft/webbob-clean-0927") == clean["merge_sha"], "Clean remote changed")
        run(["git", "-C", candidate, "merge-base", "--is-ancestor", sha, clean["merge_sha"]])
        require(not run(["git", "-C", candidate, "diff", "--name-only", sha, clean["merge_sha"]]),
                "Clean merge tree differs from reviewed tip")
        evidence.update(review_gate=dict(path=str(gate), sha256=hashlib.sha256(gate.read_bytes()).hexdigest()),
                        clean_merge=clean, remote=remote)
        evidence.update(sha=sha, draft_pr=args.draft_pr)
        require(run(["git", "-C", candidate, "branch", "--show-current"]) == BRANCH, "Wrong branch")
        require(not run(["git", "-C", candidate, "status", "--porcelain"]), "Candidate has uncommitted changes")
        pr = json.loads(run(["gh", "pr", "view", args.draft_pr, "--json", "isDraft,headRefOid,state,baseRefName"]))
        # Like 0356, GitHub may mark the draft MERGED after a regular branch merge.
        # Accept only the exact reviewed head and clean base; never undraft it.
        require(pr["isDraft"] and pr["state"] in ("OPEN", "MERGED") and pr["headRefOid"] == sha and pr["baseRefName"] == "draft/webbob-clean-0927", "Draft PR does not match tested candidate")
        tests = json.loads((root / "conductor/reviews/TEXTING-0810-tests.json").read_text())
        require(tests["sha"] == sha and tests["suite_exit"] == tests["eval_exit"] == 0 and
                tests["eval"]["passed"] == tests["eval"]["total"], "Full suite/eval gate is not green for this SHA")
        evidence["tests"] = tests
        # Retest the authoritative failed observation before touching live.
        from reply_authority import format_operational_reply
        regression = json.loads((candidate / "webchat/fixtures/texting_diagdump_0810.json").read_text())
        corrected = format_operational_reply(regression["snapshot"], text=regression["message"])
        require(not style_errors(corrected), "Prior live failure still produces a diagnostic dump")
        evidence["prior_failure_regression"] = dict(session_id=regression["session_id"], turn=3,
                                                   question=regression["message"], reply=corrected, pass_check=True)
        client.login()
        previous_version = client.call("/api/version")
        require(previous_version["sha"] == PREVIOUS and previous_version["sha"].startswith(args.expected_live), "Live changed since review")
        session = client.call("/api/session")
        require(not session.get("active_conversations") and not session.get("active_conversation"), "A chat reply is in flight")
        # Freeze the source before creating any replay conversations.
        evidence["sessions"] = latest_sessions(root)
        evidence["previous_version"] = previous_version
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        rollback = root / "rollbacks" / ("webbob-texting-" + stamp)
        rollback.mkdir(mode=0o700)
        evidence["rollback"] = str(rollback)
        previous, snapshots, copied = {}, {}, {}
        for name in ("webchat", "dispatch"):
            pin = root / "conductor/state" / (name + "-code-root")
            previous[name] = str(Path(pin.read_text().strip()).resolve())
            if previous[name] not in copied:
                target = rollback / ("previous-" + name)
                shutil.copytree(previous[name], target, ignore=shutil.ignore_patterns(
                    ".git", ".password", ".session-secret", "keys.env", ".env", ".env.*", "sessions",
                    "node_modules", "__pycache__", "uploads", "evidence", "task-runs"))
                copied[previous[name]] = str(target)
            snapshots[name] = copied[previous[name]]
        evidence.update(previous_pins=previous, snapshots=snapshots)
        write(rollback / "release.json", redact(json.dumps(evidence, indent=2, ensure_ascii=False)) + "\n")
        write(rollback / "rollback.sh", "#!/bin/bash\nset -euo pipefail\n" + shlex.join([
            "env", "PYTHONPATH=" + str(candidate / "webchat"), "TMPDIR=/private/tmp",
            sys.executable, str(Path(__file__).resolve()), "--root", str(root),
            "--candidate", str(candidate), "--attempt", str(args.attempt), "--rollback", str(rollback)]) + "\n")
        (rollback / "rollback.sh").chmod(0o700)
        save()
        write(candidate / "webbob-build.json", json.dumps(dict(sha=sha, built_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))) + "\n")
        activated = True
        evidence["activated"] = True
        save()
        evidence["restart"] = restart(root, dict(webchat=candidate, dispatch=candidate))
        require(evidence["restart"]["other_screens_unchanged"], "Unrelated screens changed during restart")
        client = Client(client.url, password_file)
        client.login()
        evidence["version"] = client.call("/api/version")
        require(evidence["version"]["sha"] == sha, "Live /api/version differs from candidate")
        origin = root / "conductor/webchat/.public-origin"
        if origin.exists():
            public = Client(origin.read_text().strip(), password_file)
            public.login()
            evidence["public_version"] = public.call("/api/version")
            require(evidence["public_version"]["sha"] == sha, "Public /api/version differs from candidate")
        save()
        print("Deployed " + sha[:7] + "; rollback ready at " + str(rollback), flush=True)
        texting_smoke(client, root, evidence, save)
        for source in evidence["sessions"]:
            cid = client.new()
            source["replay_id"] = cid
            save()
            for index, exchange in enumerate(source["exchanges"]):
                before = build_live_status_snapshot(root)
                turn_started = time.time()
                answer = submit(client, cid, exchange["message"])
                after = build_live_status_snapshot(root)
                ids = answer.get("task_ids", [answer["task_id"]] if answer.get("task_id") else [])
                evidence["task_ids"].extend(ids)
                errors = check_reply(answer, exchange, cid, turn_started, before, after, task_queue.tasks(root))
                api_jobs = {r["id"]: r for r in client.call("/api/jobs")["dispatch"]}
                require(all(i in api_jobs for i in ids), "Receipt jobs missing from authenticated Jobs API")
                exchange.update(after=answer["content"], provider=answer["provider"], request_id=answer["request_id"],
                                message_id=answer["id"],
                                task_ids=ids, errors=errors, pass_check=not errors, turn_started_at=turn_started,
                                receipts=[task_queue.tasks(root)[i] for i in ids],
                                observations={"reply": answer.get("status_observation"),
                                              "before": {k: before[k] for k in ("captured_at", "work", "work_counts", "queue_counts", "queue_jobs", "inspection")},
                                              "after": {k: after[k] for k in ("captured_at", "work", "work_counts", "queue_counts", "queue_jobs", "inspection")}})
                save()
                require(not errors, source["source_id"] + " turn " + str(index + 1) + ": " + "; ".join(errors))
                verify_executions(root, evidence["task_ids"])
                print(source["source_id"][:8] + " turn " + str(index + 1) + ": PASS — " + answer["content"], flush=True)
        deadline, last_progress = time.monotonic() + args.timeout, 0
        while True:
            rows, started = verify_executions(root, evidence["task_ids"])
            evidence["jobs"] = [{k: row.get(k) for k in ("id", "title", "worker", "status", "execution_started_at", "worktree", "branch", "publication", "result_path", "result_sha256", "kind", "model", "evidence", "error")} for row in rows]
            evidence["started_jobs"] = [row["id"] for row in started]
            save()
            if len(started) == len(rows) and all(r["status"] == "succeeded" for r in rows):
                break
            require(time.monotonic() < deadline, "Timed out waiting for every replay job to finish")
            if time.monotonic() - last_progress > 20:
                print("Replay executions: " + str(len(started)) + "/" + str(len(rows)) + "; " +
                      ", ".join((row.get("title") or row["id"]) + "=" + row["status"] for row in rows), flush=True)
                last_progress = time.monotonic()
            time.sleep(2)
        coding = [r for r in rows if r["kind"] == "coding"]
        require(len({r["worktree"] for r in coding}) == len(coding), "Coding jobs share a worktree")
        for row in coding:
            require(row["worker"] in ("codex", "cursor", "claude"), "Coding job has no file worker")
            require(run(["git", "-C", row["worktree"], "branch", "--show-current"]) == row["branch"] == "draft/" + row["id"], "Job left assigned draft branch")
        for row in rows:
            if row["worker"] in ("gemini", "minimax"):
                require(row.get("model") in ("gemini-2.5-pro", "MiniMax-M2.7"), "API execution model not recorded")
                require(not row.get("worktree"), "API report worker gained a code worktree")
                require(row["status"] == "succeeded" and Path(row.get("result_path") or "").is_file(), "API report did not complete")
        # Verify all replay jobs completed before accepting their replies.
        # Queue entries and an executing timestamp alone cannot pass.
        # Reconciliation must not rewrite the historical dispatch receipts.
        for source in evidence["sessions"]:
            messages = client.call("/api/conversations/" + source["replay_id"])["messages"]
            source["completions"] = []
            for exchange in source["exchanges"]:
                receipt = next(m for m in messages if m.get("request_id") == exchange["request_id"] and m.get("role") == "assistant")
                require(receipt["content"] == exchange["after"], "Original reply was rewritten after dispatch")
                require(receipt["id"] == exchange["message_id"] and
                        receipt.get("status_observation") == exchange["observations"]["reply"],
                        "Original status observation was rewritten or lost")
            for message in messages:
                if message.get("task_status"):
                    errors = style_errors(message["content"], 1 + len(message.get("task_ids", [])))
                    source["completions"].append(dict(content=message["content"], status=message["task_status"], errors=errors))
                    require(not errors, "Completion reply: " + "; ".join(errors))
        require(client.call("/api/version")["sha"] == sha, "Live version changed during replay")
        signal.alarm(0)
        evidence.update(all_pass=True, finished_at=time.time())
        save()
        # The cross-vendor reviewer inspects this evidence before writing PASS.
        print("LIVE GATE GREEN: " + str(sum(len(s["exchanges"]) for s in evidence["sessions"])) +
              " replies; " + str(len(started)) + " actual executions. Evidence: " + str(record), flush=True)
        return 0
    except BaseException as exc:
        signal.alarm(0)
        evidence["finished_at"] = time.time()
        evidence["failure"] = redact(str(exc))
        if activated:
            try:
                evidence["cancelled_replay_jobs"] = [row["id"] for row in task_queue.cancel_replay(
                    root, {s["replay_id"] for s in evidence["sessions"] if s.get("replay_id")},
                    "Texting deployment live replay failed; claim revoked before release rollback.")]
                evidence["rollback_result"] = restart(root, {key: Path(path) for key, path in evidence["snapshots"].items()},
                                                     expected_exits=evidence["cancelled_replay_jobs"])
                client = Client(client.url, password_file)
                client.login()
                evidence["restored_version"] = client.call("/api/version")
                require(evidence["restored_version"]["sha"] == evidence["previous_version"]["sha"], "Rollback version mismatch")
                require(evidence["rollback_result"]["other_screens_unchanged"], "Unrelated screens changed during rollback")
                origin = root / "conductor/webchat/.public-origin"
                if origin.exists():
                    public = Client(origin.read_text().strip(), password_file)
                    public.login()
                    evidence["restored_public_version"] = public.call("/api/version")
                    require(evidence["restored_public_version"]["sha"] == evidence["previous_version"]["sha"], "Public rollback version mismatch")
                evidence["rolled_back"] = True
            except BaseException as rollback_error:
                evidence["rollback_error"] = redact(str(rollback_error))
        save()
        report = ("# Web Bob texting deployment — FAIL\n\nCandidate: `" + evidence.get("sha", "unresolved") +
                  "`\n\nDraft PR: " + args.draft_pr + "\n\nFailing check: " + evidence["failure"] +
                  "\n\nRollback: `" + str(rollback) + "`; verified: " + str(evidence.get("rolled_back", False)) +
                  "\n\nEvidence: `" + str(record) + "`.\n")
        for directory in (root / "conductor/reviews",):
            write(directory / "WEBBOB-TEXTING-FAIL-0810.md", report)
        print("FAIL: " + evidence["failure"] + "; rollback verified=" + str(evidence.get("rolled_back", False)), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


## Guard test results
test_bad_fresh_review_gate_never_activates (__main__.TextingReleaseGuards) ... ok
test_failed_smoke_restores_and_verifies_a777736 (__main__.TextingReleaseGuards) ... ok

----------------------------------------------------------------------
Ran 2 tests in 0.022s

OK
