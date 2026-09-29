Strict INTEGRATE-ONLY code review of tip 2cdcce928ea6a975825829a6c10a88a99017f643 on draft/webbob-integrate-2057.
Focus: webchat/worker_assignment.py turn-1 Gemini/MiniMax API dispatch when no permitted active source (use observed project lane context).
Gemini already PASSed this tip (LIVE-GEMINI ... 2cdcce9). Offline READY: 323 webchat + 130 services + 73/73 evals (INTEGRATE-FIXED-2205).
Prior LIVE MiniMax attempt timed out incomplete (HTTP curl_rc=28) — this is a fresh complete review.
List real CRITICAL/HIGH bugs only. End with exactly: VERDICT: PASS or VERDICT: FAIL

INTEGRATE-FIXED-2205

RESULT: READY

New tip: `2cdcce928ea6a975825829a6c10a88a99017f643`
Branch: `draft/webbob-integrate-2057`
Base: `ab5053331d128372607194a0756b893d3872c7a0`
Completed UTC: 2026-09-28T03:36:06.857671+00:00
Regular push to `brain` succeeded; the remote branch SHA matches the new tip. Working tree is clean.

The saved attempt3 deployment evidence shows the turn-1 request in frozen session
`b33fac25-3c8a-452d-8673-47d3a99dd92c` encountered zero queued/claimed jobs and zero
confirmed running workers. The open `lane-webbob-llm-reviews` screen identified
Web Bob, but its activity was unverified. The assignment planner required a running
source and discarded that project context. Previous offline replay seeded a coding
job, so it missed this state.

The production change is confined to `webchat/worker_assignment.py`. When no
permitted active source exists, an observed open screen with a known project and
repository can now supply context for new Gemini/MiniMax API reports. Gemini gets
an audit job; MiniMax gets a test-writing job. Their prompts explicitly describe
the unverified activity and use the supplied repository snapshot. Existing work
keeps priority; project holds and explicit scopes still apply. This fallback is
limited to API workers, and creates no invented source job or running status.

The new regression reproduced both exact deployment failures before the repair:
`work request has no real dispatch` and
`Gemini/MiniMax did not receive API worker jobs`.
It now verifies real durable job IDs, receipt ownership, retry/restart idempotency,
and honest activity state from the frozen turn with an empty queue. Additional
cases cover project holds, requested scope, existing-job priority, unsupported
coding-worker fallback, and unidentified screens/processes.

The service regression follows the frozen request through Chat, the durable queue,
scheduler claims, worker execution, metered API transport, repository evidence,
saved reports, result/acceptance hashes, immutable receipts, and one-time chat
delivery. It checks `gemini-2.5-pro` and `MiniMax-M2.7`. HTTP responses, lane health,
semantic acceptance and the process-launch boundary are controlled offline test
fixtures; the real worker executes in process. No paid provider calls were made.

| Validation | Result |
| --- | --- |
| Webchat unittest discovery | 323 passed (21.877 s) |
| Services unittest discovery | 130 passed (4.370 s) |
| Bob parity/integration evals | 73/73 passed |
| Whitespace check | Passed |

The evals retain all 56 existing cases and add a second replay of all 17 frozen
turns from the failed deployment's lane-only starting condition. The reply and
receipt grading requirements were not relaxed. The status-observation path is
unchanged. Services ran from a hash-verified copy of all 362 tracked files
inside this worktree, with temporary repositories beside that copy so the existing
macOS code-write sandbox remained effective. Temporary validation trees were
removed after preserving logs and the source manifest.

Evidence directory: `/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-integrate-2057/reviews/integrate-fixed-2205`

- `red-regression.log`: exact pre-fix failure reproduction.
- `webchat-tests.log`, `services-tests.log`, `evals.log`: full-suite results.
- `api-worker-tests.log`: focused API-worker execution regression.
- `bob-parity-eval.json`, `validation.json`: detailed evals and final-tip validation.
- `services-copy-manifest.json`: verified source hashes, matching the committed tip.

READY for review of the offline repair. The failed live attempt remains a failure;
a new live replay has not been run. No deploy, service restart, merge, undraft,
force-push, Grok/xAI call, or Jeff notification was performed.

## Diffstat vs live dff84e3
 webchat/README.md                             |  34 ++-
 webchat/app.py                                |  71 ++++---
 webchat/bob_parity_eval.py                    | 109 +++++++++-
 webchat/deploy_integrate.py                   | 263 ++++++++++++++++++++++++
 webchat/deploy_parity.py                      |   6 +-
 webchat/deploy_replyq.py                      | 285 ++++++++++++++++++++++++++
 webchat/dispatch_receipts.py                  |  67 ++++++
 webchat/fixtures/integrate_sessions_0927.json |  91 ++++++++
 webchat/integration_rubric.py                 | 156 ++++++++++++++
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
 webchat/test_integrate_2057.py                | 253 +++++++++++++++++++++++
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
 37 files changed, 3258 insertions(+), 189 deletions(-)

## worker_assignment.py diff
diff --git a/webchat/worker_assignment.py b/webchat/worker_assignment.py
new file mode 100644
index 0000000..e1d4b37
--- /dev/null
+++ b/webchat/worker_assignment.py
@@ -0,0 +1,140 @@
+"""Turn requests to use LLMs on ongoing work into durable, scoped assignments."""
+import json
+import re
+
+import task_queue
+from api_tasks import ROLES
+from chat_intent import blocked_scopes, command, project_targets, state_for
+from live_status_snapshot import observe_work
+
+NAMES = r"(?:gemini|minimax|codex|claude|cursor(?:-agent)?|grok|xai|xAI)"
+DIRECTIVE = re.compile(
+    r"^(?:remember\s*[:,]?\s*(?:that\s+)?(?:(?:you|we)\s+can\s+|to\s+)?|(?:you|we)\s+can\s+)?"
+    r"(?:also\s+)?(?:use|assign|put|have|get|delegate\s+to)\s+(?P<names>" + NAMES +
+    r"(?:\s*(?:,|&|and)\s*(?:and\s+)?" + NAMES + r")*)\b(?P<rest>.*)$", re.I | re.S)
+ONGOING = re.compile(r"\b(?:ongoing|current|existing|active|running|queued)\b.{0,35}\b(?:jobs?|tasks?|work|projects?)\b|"
+                     r"\b(?:jobs?|tasks?|work|projects?)\b.{0,30}\b(?:ongoing|underway|running)\b|"
+                     r"\b(?:for|on|with)\s+(?:these|those|our|the)\s+(?:jobs?|tasks?|work)\b", re.I)
+
+
+def requested_workers(text, conversation=None):
+    cleaned = command(text)
+    if re.match(r"^(?:don't|do not|never|stop|hold)\b", cleaned, re.I):
+        return None
+    # A follow-up references the last explicit worker request, not arbitrary
+    # names from a model answer or provider-health metadata.
+    followup = re.search(r"\b(?:add|assign|queue|give)\s+(?:some |more |new )?(?:work|jobs?|tasks?)\s+(?:for|to)\s+(?:them|those (?:LLMs|workers))\b|"
+                         r"\b(?:want|need)\s+them\s+(?:workout|working|to work|busy)\b|"
+                         r"\b(?:put|get|keep)\s+them\s+(?:to work|working|busy)\b", cleaned, re.I)
+    if followup:
+        names = (conversation or {}).get("assignment_workers")
+        if not names:
+            for message in reversed((conversation or {}).get("messages", [])):
+                if message.get("role") == "user" and message.get("content") != text:
+                    names = requested_workers(message.get("content", ""))
+                    if names:
+                        break
+        if names:
+            return list(names)
+    all_workers = re.match(r"^(?:use|assign|put|get|keep)\s+all\s+(?:the\s+)?(?:LLMs|models|workers)\b", cleaned, re.I)
+    if all_workers and (ONGOING.search(cleaned) or re.search(r"\b(?:to work|busy|working)\b", cleaned, re.I)):
+        return list(task_queue.MODEL_WORKERS)
+    match = DIRECTIVE.match(cleaned)
+    reminder = re.match(r"^(?:remember|you can|we can)\b", cleaned, re.I)
+    if not match or not (ONGOING.search(match["rest"]) or (reminder and re.fullmatch(r"\s*(?:too|also)?[.!]*", match["rest"], re.I))):
+        return None
+    return list(dict.fromkeys(name.lower().replace("cursor-agent", "cursor")
+                              for name in re.findall(NAMES, match["names"], re.I)))
+
+
+def issue_followup(root, conversation, text):
+    if not re.fullmatch(r"if you find (?:any )?(?:issues|bugs)[, ]+(?:please )?fix them[.!]*", command(text), re.I):
+        return None
+    previous = next((m["dispatch_intent"] for m in reversed(conversation["messages"][:-2])
+                     if m.get("dispatch_intent", {}).get("worker_assignment")), None)
+    if not previous or not previous.get("assignment_projects"):
+        return None
+    project = previous["assignment_projects"][0]
+    return ("Fix verified issues in " + project + "\nInspect the ongoing work and available review reports, "
+            "reproduce a concrete issue, implement one bounded fix if warranted, and run relevant tests. "
+            "Report evidence if no fix is needed. Work in your assigned draft worktree; never deploy or merge.")
+
+
+def plan(root, conversation, text, workers):
+    for worker in workers:
+        task_queue.worker_name(worker)  # Reject Grok/xAI before any queue write.
+    observed = observe_work(root)
+    state = state_for(conversation)
+    targets = project_targets(text, state)
+    candidates = []
+    for row in observed["records"].values():
+        if (row.get("status") or row.get("state")) not in ("queued", "claimed", "launched", "running"):
+            continue
+        if row.get("source_job_id") or (row.get("kind") in ("audit", "test-writing", "planning", "review", "research", "eval-grading")):
+            continue  # Never recursively create report jobs about report jobs.
+        prompt = row.get("prompt") or row.get("title") or row.get("project")
+        if not prompt:
+            continue
+        names = project_targets(row.get("project") or prompt, state)
+        if targets and not any(name in targets for name in names):
+            continue
+        if blocked_scopes(state, names):
+            continue
+        candidates.append(dict(id=row["job_id"], prompt=prompt,
+                               project=", ".join(names) or "Web Bob"))
+    # Some ongoing jobs are external CLI workers, observed outside the journal.
+    known = {row["id"] for row in candidates}
+    for row in observed["work"]:
+        if row["state"] != "running" or row.get("job_id") in known or not (row.get("task") or row.get("title")) or not row.get("project"):
+            continue
+        if row.get("job_id") and observed["records"].get(row["job_id"], {}).get("kind") in ("audit", "test-writing", "planning", "review", "research", "eval-grading"):
+            continue
+        if targets and row["project"] not in targets:
+            continue
+        if blocked_scopes(state, [row["project"]]):
+            continue
+        task = row.get("task") or ("Observed active lane: " + row["title"] +
+                                   ". Its original task prompt was not recorded; inspect the project's current code and "
+                                   "state that limitation. Do not invent the lane's exact assignment.")
+        candidates.append(dict(id=None, prompt=task, project=row["project"]))
+    # An open project lane can outlive its worker process. It still identifies
+    # a repository for a new API report, but proves neither an ongoing task nor
+    # execution. Use it only when no permitted active assignment is available;
+    # never turn this limited context into a coding job or a fake source job ID.
+    if not candidates and all(worker in task_queue.API_WORKERS for worker in workers):
+        seen_projects = set()
+        for row in observed["work"]:
+            project = row.get("project")
+            if (row["state"] != "unverified" or row.get("source") != "screen" or row.get("job_id")
+                    or row.get("screen") not in observed.get("sessions", {})
+                    or not project or not row.get("repo") or not row.get("title") or project in seen_projects):
+                continue
+            if (targets and project not in targets) or blocked_scopes(state, [project]):
+                continue
+            context = ("Observed open project lane: " + row["title"] + ". Its worker activity is unverified; "
+                       "no current task is confirmed. Inspect the project's supplied repository snapshot "
+                       "for concrete findings and regression test drafts. Do not infer active work, "
+                       "progress or results from the lane name or historical logs.")
+            candidates.append(dict(id=None, prompt=context, project=project, context="project context"))
+            seen_projects.add(project)
+    if not candidates:
+        raise ValueError("I couldn't assign those workers: there is no identifiable ongoing job permitted by the current holds. Name a project and task to start.")
+    health = root / "conductor/lanes.json"
+    board = json.loads(health.read_text()) if health.exists() else {}
+    packages = []
+    for index, worker in enumerate(workers):
+        row = board.get(worker, {})
+        if row.get("state") in ("needs_key", "unavailable", "budget_exhausted", "cooldown", "needs_login"):
+            raise ValueError("I couldn't assign " + worker + ": " + row["state"].replace("_", " ") + ". No new assignments were queued.")
+        source = candidates[index % len(candidates)]
+        kind, role = ROLES.get(worker, ("analysis", "Review the ongoing task and propose next steps"))
+        context = source.get("context", "ongoing task")
+        # One concrete bounded package per requested worker. Keep existing
+        # coders running; do not revoke a live claim or share their edit rights.
+        prompt = ("Project: " + source["project"] + "\nYour independent subtask:\n" + role +
+                  " for the following " + context + ". Deliver concrete findings and "
+                  "an actionable plan or test drafts. Never deploy or resolve conflicts.\n" +
+                  context.capitalize() + ":\n" + source["prompt"][:8000])
+        packages.append(dict(worker=worker, kind=kind, title=source["project"] + " — " + role,
+                             prompt=prompt, source_job_id=source["id"]))
+    return packages
