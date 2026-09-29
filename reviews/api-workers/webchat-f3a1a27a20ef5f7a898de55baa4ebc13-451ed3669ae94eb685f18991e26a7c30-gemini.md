Based on the provided repository snapshot, this report outlines an audit and implementation plan for the task "lane-webbob-texting-diagdump-fix-0810".

### 1. Audit and Findings

The task name and the presence of `webchat/fixtures/texting_diagdump_0810.json` indicate a need to fix an issue related to a diagnostic dump from a texting-related deployment. The fixture captures a "bad_reply" from the system.

**Evidence:** `webchat/fixtures/texting_diagdump_0810.json`

The "bad_reply" in the fixture is:
> "Codex is on “Web Bob: # lane-webbob-texting-deploy-0702” (model not reported; running for 7 min); Gemini is on “Web Bob — Whole-repo audit and implementation plan” (2 jobs waiting to run). MiniMax is on “Web Bob — Review and regression test-case drafts” (2 jobs waiting to run). Claude and Cursor are idle. The job runner has 0 claimed and 4 queued jobs."

This reply is overly verbose, contains internal implementation details (like lane names and job runner stats), and fails to provide a clear, user-friendly status. This style of reply was identified as a problem in `webchat/bob_parity_eval.py`, which contains checks to prevent "raw diagnostic dump" and ensure a "natural prose" style.

The fix likely involves improving the status formatting logic to produce a more colloquial and less technical summary of system activity, as demonstrated by the test cases in `webchat/bob_parity_eval.py`. The test `test_failed_live_texting_status_snapshot_uses_natural_prose` specifically targets a similar verbose reply and expects a concise, natural language summary.

### 2. Implementation Plan

The goal is to refine the status reporting mechanism to align with the quality standards evidenced in `webchat/bob_parity_eval.py`. The fix should be implemented in `webchat/reply_authority.py`, which appears to be responsible for formatting operational replies.

The proposed change will modify the `format_operational_reply` function to:
1.  Summarize running and queued work by provider, without exposing internal job IDs or lane names.
2.  Consolidate information into a brief, natural language paragraph.
3.  Avoid jargon like "job runner", "claimed", and "queued" in the final output.

The following patch for `webchat/reply_authority.py` is proposed.

```diff
--- a/webchat/reply_authority.py
+++ b/webchat/reply_authority.py
@@ -1,5 +1,6 @@
 """Final authority on what Web Bob says (no unreviewed model prose)."""
 import re
+from collections import defaultdict
 
 from providers import Redactor
 from worker_evidence import clean
@@ -10,13 +11,26 @@
 
 
 def format_operational_reply(snapshot, provider=None, text=None):
-    """Plain-English summary of live work (no model call)."""
+    """Natural language summary of live work (no model call)."""
     parts = []
-    if snapshot["work_counts"]["running"]:
-        parts.append(f"Yes — {snapshot['work_counts']['running']} worker{'s are' if snapshot['work_counts']['running'] != 1 else ' is'} running.")
+    running_by_worker = defaultdict(list)
+    for job in snapshot.get("work", []):
+        if job.get("worker"):
+            running_by_worker[job["worker"].title()].append(job)
+
+    queued_by_worker = defaultdict(list)
+    for job in (snapshot.get("queue_jobs") or {}).get("queued", []):
+        if job.get("worker"):
+            queued_by_worker[job["worker"].title()].append(job)
+
     for row in snapshot.get("work", []):
         label = clean(row.get("task") or row["title"], 95).strip(" .;:")
-        parts.append(f"- {row.get('project', 'Web Bob')}: {label} — {row['worker']} ({row.get('model') or 'model not reported'}) — running for {row['elapsed_seconds'] // 60} min")
+        if row.get("worker"):
+            parts.append(f"{row['worker'].title()} is working on {label}.")
+
+    for worker, jobs in queued_by_worker.items():
+        if not running_by_worker.get(worker):
+            parts.append(f"{worker} has {len(jobs)} job{'s' if len(jobs) > 1 else ''} waiting to run.")
 
     idle_workers = []
     for name, health in snapshot.get("provider_health", {}).items():
@@ -24,12 +38,10 @@
             idle_workers.append(name.title())
 
     if idle_workers:
-        parts.append(f"{', '.join(idle_workers)}: idle.")
+        parts.append(f"{', '.join(idle_workers)} {'are' if len(idle_workers) > 1 else 'is'} idle.")
 
-    if snapshot["queue_counts"]["claimed"] or snapshot["queue_counts"]["queued"]:
-        parts.append(f"Job runner: {snapshot['queue_counts']['claimed']} claimed, {snapshot['queue_counts']['queued']} queued.")
-
-    return "\n".join(parts)
+    if not parts:
+        return "All workers are idle and no jobs are waiting."
+    return " ".join(parts)
 
 
 def enforce(root, ask, answer, conversation, *, observation=None, redact: Redactor):

```

### 3. Validation Plan

1.  **Unit Tests**: The existing test suite, particularly `webchat/test_reply_authority.py`, should be run to ensure no regressions are introduced.
2.  **Parity Evaluation**: Run `webchat/bob_parity_eval.py`. The test case `test_failed_live_texting_status_snapshot_uses_natural_prose` should now pass with the updated formatting logic, confirming the fix for the issue captured in `webchat/fixtures/texting_diagdump_0810.json`.
3.  **Manual Verification**: After applying the patch, manually trigger a status request in the Web Bob chat UI to confirm the output is concise and user-friendly, matching the improved style.
