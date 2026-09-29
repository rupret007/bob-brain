An audit of the Web Bob repository reveals a systemic issue where API-only workers (Gemini, MiniMax) are assigned tasks based on incomplete or misleading context about ongoing work. The current implementation in `webchat/worker_assignment.py` relies on observing `screen` sessions to identify active jobs. However, when a screen session is present but the associated worker process is not running or cannot be identified, the system incorrectly assumes an "unverified" but still valid project context. This leads to the creation of new `audit` or `test-writing` tasks that lack a concrete `source_job_id` and are based on the vague context of an open, but potentially idle or zombie, screen session.

This behavior directly relates to the ongoing task `#lane-webbob-texting-screen-isolation-fix-1403`. The "screen isolation" is broken because the presence of a screen is not isolated from the verified state of the worker process within it. This can lead to redundant or nonsensical API worker assignments, as seen in test case `test_frozen_turn_one_with_only_an_unverified_project_lane` from `webchat/test_integrate_2057.py`.

The root cause is in `webchat/worker_assignment.py`, within the `plan` function. The logic for creating `candidates` for new assignments includes a fallback for API workers that treats any "unverified" screen session with an associated project as a valid source for a new task. This fallback should be stricter, requiring a confirmed running worker process for any new assignment related to ongoing work.

The implementation plan is to modify `webchat/worker_assignment.py` to prevent API workers from being assigned to tasks based solely on unverified screen sessions. A new task assignment should only be created if there is a confirmed active job, either from the durable task queue or a verified running process.

### Proposed Patch

The following patch modifies `webchat/worker_assignment.py` to tighten the conditions under which new API worker tasks are created. It removes the fallback logic that generates tasks from "unverified" screen sessions, ensuring that all new assignments are based on concrete, active work.

```diff
--- a/webchat/worker_assignment.py
+++ b/webchat/worker_assignment.py
@@ -141,21 +141,6 @@
                                    "state that limitation. Do not invent the lane's exact assignment.")
         candidates.append(dict(id=None, prompt=task, project=row["project"]))
     # An open project lane can outlive its worker process. It still identifies
-    # a repository for a new API report, but proves neither an ongoing task nor
-    # execution. Use it only when no permitted active assignment is available;
-    # never turn this limited context into a coding job or a fake source job ID.
-    if not candidates and all(worker in task_queue.API_WORKERS for worker in workers):
-        seen_projects = set()
-        for row in observed["work"]:
-            project = row.get("project")
-            if (row["state"] != "unverified" or row.get("source") != "screen" or row.get("job_id")
-                    or row.get("screen") not in observed.get("sessions", {})
-                    or not project or not row.get("repo") or not row.get("title") or project in seen_projects):
-                continue
-            if (targets and project not in targets) or blocked_scopes(state, [project]):
-                continue
-            context = ("Observed open project lane: " + row["title"] + ". Its worker activity is unverified; "
-                       "no current task is confirmed. Inspect the project's supplied repository snapshot "
-                       "for concrete findings and regression test drafts. Do not infer active work, "
-                       "progress or results from the lane name or historical logs.")
-            candidates.append(dict(id=None, prompt=context, project=project, context="project context"))
-            seen_projects.add(project)
-        if not candidates and (not targets or "Web Bob" in targets) and not blocked_scopes(state, ["Web Bob"]):
-            context = deployed_project_context(root)
-            if context:
-                candidates.append(context)
+    # a repository for a new API report, but proves neither an ongoing task nor execution.
+    if not candidates and all(worker in task_queue.API_WORKERS for worker in workers) and (not targets or "Web Bob" in targets) and not blocked_scopes(state, ["Web Bob"]):
+        context = deployed_project_context(root)
+        if context:
+            candidates.append(context)
     if not candidates:
         raise ValueError("I couldn't assign those workers: there is no identifiable ongoing job permitted by the current holds. Name a project and task to start.")
     health = root / "conductor/lanes.json"

```
