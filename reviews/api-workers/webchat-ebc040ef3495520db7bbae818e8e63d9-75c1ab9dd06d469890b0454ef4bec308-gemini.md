Based on a comprehensive audit of the supplied repository snapshot, here is a report on the Web Bob system's architecture and a proposed implementation plan for improvements.

### Architectural Audit Findings

The system demonstrates a robust, decoupled architecture for managing and executing tasks. Key strengths include:

1.  **Durable, State-Driven Task Queue:** The core of the system is `state/task_queue.py`, which implements a durable, append-only task journal. This design ensures that user requests are not lost across restarts. The explicit state transitions (`queued`, `claimed`, `running`, `succeeded`, `failed`) and claim-fencing provide resilience against duplicate execution.

2.  **Clear Separation of Concerns:** There is a clean separation between intent parsing (`webchat/task_dispatch.py`), task queuing (`state/task_queue.py`), and task execution (`services/dispatch_worker.py`). This modularity allows different parts of the system to evolve independently.

3.  **Capability-Aware Worker Routing:** The system correctly distinguishes between tool-capable workers (e.g., `codex`, `cursor`) and API-only workers (`gemini`, `minimax`). `services/dispatch_worker.py` enforces this by preparing repository evidence for API workers via `services/api_worker.py` and rejecting tasks that require file system access for those workers.

4.  **Advanced Self-Reflection and Context Assignment:** The mechanism in `webchat/worker_assignment.py` that initiated this audit is a significant capability. It can create meta-tasks based on either actively running jobs or, as a fallback, the securely identified deployed codebase (`webchat/build_info.py`). This allows for powerful, in-context analysis and improvement cycles without a specific user-defined task.

### Implementation Plan

The current architecture is solid. The following plan focuses on refining the self-assignment logic and improving observability.

**1. Unify and Simplify Worker Assignment Context**

*   **Finding:** The `plan` function in `webchat/worker_assignment.py` has a multi-stage fallback logic to find a context for new jobs (active jobs, screen sessions, deployed code). This complexity can make behavior hard to predict.
*   **Proposal:** Refactor `webchat/worker_assignment.py` to centralize context discovery. Create a single function that returns a prioritized list of available contexts (e.g., active jobs first, then the deployed project). The `plan` function would then iterate this list. This simplifies the logic and makes it easier to add new context sources in the future.

**2. Draft Regression Tests for Dispatch Logic**

*   **Finding:** The dispatch and assignment logic is critical but lacks specific regression tests for its fallback behaviors.
*   **Proposal:** Create a new test file, `webchat/test_worker_assignment.py`, to provide coverage for the `plan` function. This will involve mocking `observe_work` and `deployed_project_context` to simulate different scenarios:
    *   One active coding job.
    *   No active jobs, but a valid deployed project context.
    *   No active jobs and no valid project context (should raise a `ValueError`).

```python
# Proposed test code for webchat/test_worker_assignment.py

import unittest
from unittest.mock import patch, MagicMock

from webchat import worker_assignment
from state import task_queue

class WorkerAssignmentPlanTest(unittest.TestCase):
    def setUp(self):
        self.root = "/fake/root"
        self.conversation = {"messages": [], "intent_state": {"holds": {}}}
        self.workers = ["gemini"]

    @patch("webchat.worker_assignment.observe_work")
    @patch("webchat.worker_assignment.deployed_project_context")
    def test_plan_assigns_from_active_job(self, mock_deployed_context, mock_observe):
        """Verify assignment uses an observed active job as the source."""
        mock_observe.return_value = {
            "records": {
                "job-123": {"job_id": "job-123", "status": "running", "project": "WebJam", "prompt": "Fix the build"}
            },
            "work": []
        }
        mock_deployed_context.return_value = None

        packages = worker_assignment.plan(self.root, self.conversation, "use gemini on ongoing work", self.workers)
        self.assertEqual(len(packages), 1)
        self.assertEqual(packages[0]["worker"], "gemini")
        self.assertIn("Project: WebJam", packages[0]["prompt"])
        self.assertIn("Fix the build", packages[0]["prompt"])
        self.assertEqual(packages[0]["source_job_id"], "job-123")
        mock_deployed_context.assert_not_called()

    @patch("webchat.worker_assignment.observe_work")
    @patch("webchat.worker_assignment.deployed_project_context")
    def test_plan_falls_back_to_deployed_context(self, mock_deployed_context, mock_observe):
        """Verify assignment falls back to deployed context when no jobs are active."""
        mock_observe.return_value = {"records": {}, "work": []}
        mock_deployed_context.return_value = {
            "id": None, "project": "Web Bob", "context": "project context",
            "prompt": "The Web Bob checkout is selected by matching deployment pins..."
        }

        packages = worker_assignment.plan(self.root, self.conversation, "use gemini on ongoing work", self.workers)
        self.assertEqual(len(packages), 1)
        self.assertEqual(packages[0]["worker"], "gemini")
        self.assertIn("Project: Web Bob", packages[0]["prompt"])
        self.assertIn("The Web Bob checkout is selected", packages[0]["prompt"])
        self.assertIsNone(packages[0]["source_job_id"])

    @patch("webchat.worker_assignment.observe_work")
    @patch("webchat.worker_assignment.deployed_project_context")
    def test_plan_fails_when_no_context_is_available(self, mock_deployed_context, mock_observe):
        """Verify assignment fails cleanly when no context can be found."""
        mock_observe.return_value = {"records": {}, "work": []}
        mock_deployed_context.return_value = None

        with self.assertRaises(ValueError):
            worker_assignment.plan(self.root, self.conversation, "use gemini on ongoing work", self.workers)
```
