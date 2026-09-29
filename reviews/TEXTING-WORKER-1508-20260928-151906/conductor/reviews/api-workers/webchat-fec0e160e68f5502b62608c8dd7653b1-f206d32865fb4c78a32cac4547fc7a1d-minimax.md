Regression test: api_worker_file_task_rejected
Target: services/test_api_workers.py::APIWorkerTests::test_api_worker_artifact_rejected
Setup: Prompt "write hello to /tmp/wb-proof.txt", worker="minimax" (API_WORKERS), kind="artifact"
Action: task_queue.enqueue(root, cid, rid, prompt, worker="minimax", kind="artifact")
Expected: ValueError raised by validate_worker with message containing "API-only" and "cannot edit project files"

Regression test: api_worker_analysis_succeeds
Target: services/test_api_workers.py::APIWorkerTests::test_api_worker_analysis_accepted
Setup: Prompt "analyze the evidence and draft a report", worker="minimax" (API_WORKERS), kind="analysis"
Action: task_queue.enqueue(root, cid, rid, prompt, worker="minimax", kind="analysis")
Expected: Task queued successfully with status="queued" and requested_worker="minimax"

Action plan:
Change: No code change required; validate_worker in state/task_queue.py already enforces API-only restrictions via task_queue.API_WORKERS tuple.
Validation: Run python3 -m unittest discover -s services -p 'test_*.py'; require zero failures including new API worker isolation tests.
Exit condition: Lane lane-webbob-texting-screen-isolation-fix-1403 must receive actual worker results confirming API workers reject file/coding tasks and accept analysis tasks, validated by test run.

Findings/limits: The API_WORKERS tuple in state/task_queue.py defines which workers are API-only; validate_worker() already enforces these restrictions. Regression coverage for screen isolation between API workers and file-task workers is missing in test_api_workers.py and test_dispatch.py. The original lane prompt was not supplied in the evidence; these drafts are grounded in the validate_worker implementation and existing test patterns.

```json
{"accepted": true, "reason": "Delivered two grounded regression drafts for API worker isolation based on validate_worker enforcement in task_queue.py and existing test patterns in test_api_workers.py. Action plan confirms no code change needed; validation via unittest required. Original lane prompt missing from evidence."}
```
