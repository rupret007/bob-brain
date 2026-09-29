Based on my audit of the repository, I have identified a potential issue related to the handling of task results and have formulated a plan for implementation.

### Concrete Findings

1.  **Result Acceptance Logic**: The `services/result_acceptance.py` module contains strict validation logic in `check_deliverables` and `check_coding_answer`. These functions raise a `ResultRejected` exception if a worker's answer is incomplete (e.g., missing test drafts, unblock plans, or coding verification). This is a deterministic, server-side check that occurs before any semantic review by another model.

2.  **Dispatch Worker Execution Flow**: In `services/dispatch_worker.py`, the `execute` function correctly wraps the call to `result_acceptance.check_answer` in a `try...except ResultRejected` block. When a `ResultRejected` exception is caught, the task is transitioned to a `rejected` state, which is then recorded as a terminal `failed` status in `state/task_queue.py`.

3.  **API Worker Test Case**: The test `test_1035_failed_report_is_never_published_by_either_api_worker` in `services/test_api_workers.py` confirms this behavior. It uses a fixture (`texting_jobcompletion_1035.json`) with an answer that is known to be incomplete. The test asserts that `dispatch_worker.execute` returns a failure code (1), and the task status becomes `failed`.

4.  **Potential Gap**: The current implementation correctly fails tasks with incomplete answers. However, there is no mechanism for the server to automatically retry the task with a different worker or with modified instructions to obtain a complete answer. A `failed` status is terminal. For tasks that are programmatically determined to be incomplete (rather than semantically wrong), an automatic retry could improve resilience and reduce the need for manual re-submission. The task name "jobcomplete-fix" suggests that a job is not reaching a satisfactory completion, and a `failed` state without a path to resolution is a form of incomplete completion.

### Unblock Plan

**Change:**
Introduce a new, non-terminal task state `incomplete` for programmatic rejections of a worker's answer. Modify the `dispatch_worker` to transition tasks to this state when `ResultRejected` is caught. The `web_dispatch` scheduler will then be updated to treat `incomplete` tasks as eligible for re-queueing, similar to `retry`, but with a clear distinction that the failure was due to an incomplete deliverable, not a provider outage. This allows the system to attempt the task again, potentially with a different worker, without exhausting the provider-outage retry attempts.

**Validation:**
A new unit test will be created in `services/test_dispatch.py`. This test will:
1.  Enqueue a task of kind `test-writing`.
2.  Mock `dispatch_worker.ask` to return an incomplete answer that triggers `ResultRejected`.
3.  Run `dispatch_worker.execute` and assert that the task transitions to the new `incomplete` status, not `failed`.
4.  Assert that the task is re-claimed by another worker on a subsequent `web_dispatch.tick()`.
5.  The existing test `test_1035_failed_report_is_never_published_by_either_api_worker` will be updated to expect a transition to `incomplete` instead of `failed`.

**Exit condition:**
The unblock is resolved when tasks rejected for incompleteness are automatically re-queued for another attempt instead of entering a terminal `failed` state. The system should still mark a task as `failed` after a reasonable number of `incomplete` attempts to prevent infinite loops.

### Proposed Patch

Here is a proposed patch to implement the plan. It introduces the `incomplete` state and updates the relevant logic in `dispatch_worker.py` and `state/task_queue.py`.

```diff
--- a/services/dispatch_worker.py
+++ b/services/dispatch_worker.py
@@ -291,9 +291,12 @@
         return 0
     except ResultRejected as exc:
         message = redact(str(exc))[:1500]
-        task_queue.transition(ROOT, identifier, token, "rejected", error=message, rejected_result=answer,
-                              acceptance=dict(accepted=False, reason=message))
-        return 1
+        # An incomplete answer can be retried; a semantic rejection is terminal.
+        if "did not complete the task" in message:
+            task_queue.transition(ROOT, identifier, token, "rejected", error=message, rejected_result=answer, acceptance=dict(accepted=False, reason=message))
+            return 1
+        task_queue.transition(ROOT, identifier, token, "incomplete", error=message, rejected_result=answer, acceptance=dict(accepted=False, reason=message))
+        return 0 # Not a worker process failure
     except Exception as exc:
         message = redact(str(exc)) if isinstance(exc, RuntimeError) else type(exc).__name__
         task_queue.transition(ROOT, identifier, token, "retry", error=message[:1500])
--- a/state/task_queue.py
+++ b/state/task_queue.py
@@ -165,7 +165,7 @@
             # An unusable answer is terminal, not a provider outage to retry
             # across every lane. Keep the rejection in the durable outbox.
             row.update(status="failed", finished_at=now, claim_token=None)
-        elif event in ("retry", "busy"):
+        elif event in ("retry", "busy", "incomplete"):
             if event == "busy":
                 row["attempts"] -= 1  # A lane race is not a failed execution.
             if event == "retry":

```
