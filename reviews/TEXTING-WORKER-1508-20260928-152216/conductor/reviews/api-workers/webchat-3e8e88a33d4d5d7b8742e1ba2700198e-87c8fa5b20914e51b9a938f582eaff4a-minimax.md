Regression test: test_concurrent_texting_lanes_isolation_violation
Target: services/test_api_workers.py::APIWorkerTests::test_concurrent_texting_lanes_isolation
Setup: root = self.root, lane1 = "lane-webbob-texting-screen-isolation-fix-1403", lane2 = "lane-webbob-texting-screen-isolation-fix-1403", screens = {lane1: "53678.lane-webbob-texting", lane2: "53679.lane-webbob-texting"}, with patch("live_status_snapshot._screen_sessions", return_value=screens), with patch("live_status_snapshot.process_table", return_value={}), task_id1 = enqueue(root, cid1, rid1, "send hello to screen", worker="gemini")
Action: enqueue(root, cid2, rid2, "send world to same screen", worker="gemini")
Expected: ResultRejected("Lane already occupied") or concurrent access raises BlockingIOError

Regression test: test_sequential_texting_lanes_complete_isolated
Target: services/test_api_workers.py::APIWorkerTests::test_sequential_texting_lanes_complete_isolated
Setup: root = self.root, lane1 = "lane-webbob-texting-screen-isolation-fix-1403", screens = {lane1: "53678.lane-webbob-texting"}, with patch("live_status_snapshot._screen_sessions", return_value=screens), with patch("live_status_snapshot.process_table", return_value={}), task_id = enqueue(root, cid, rid, "send hello to screen", worker="gemini"), claim_row = task_queue.claim(root, "gemini")
Action: task_queue.transition(root, claim_row["id"], claim_row["claim_token"], "succeeded", result="message sent")
Expected: task_queue.tasks(root)[task_id]["status"] == "succeeded" and observe_work(root)["records"][task_id]["result"] == "message sent"

Action plan:
Change: Add lane isolation assertion in dispatch_worker.py execute() after slot(row["worker"]) acquisition; raise ResultRejected if slot acquisition fails due to concurrent screen access.
Validation: python3 -m unittest discover -s services -p 'test_*.py' -v; grep texting screen isolation passes.
Exit condition: Actual lane-webbob-texting-screen-isolation-fix-1403 worker completes and python3 -m unittest discover -s services -p 'test_*.py' passes with zero failures.

Findings/limits: Regression drafts are unexecuted; the original prompt/state for lane-webbob-texting-screen-isolation-fix-1403 is not in the supplied evidence, only lane naming convention from test_api_workers.py and dispatch_worker.py slot isolation logic is available.

```json
{"accepted": true, "reason": "Delivered two grounded regression drafts (failure and control) tracing through enqueue/claim/transition/slot, with Action plan tied to lane-webbob-texting-screen-isolation-fix-1403 using existing test command. Original lane prompt is missing; drafts are conditional on available slot isolation evidence in dispatch_worker.py."}
```
