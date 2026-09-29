## Regression Tests for Web Bob Unblock 1035

**Limitation:** The original task prompt for lane 1035 was not recorded. The drafts below are grounded in the observable code behavior and the test fixture patterns in `services/test_result_acceptance.py` and `services/test_api_workers.py`.

---

**Regression test: exploratory-answer-fails-acceptance**

Target: services/result_acceptance.py::check_answer

Setup: prompt contains "Review and regression test-case drafts" with "unblock 1035"; answer contains architectural observations but no concrete test drafts.

Action: call check_answer(prompt, answer, kind="test-writing")

Expected: raises ResultRejected with message containing "Missing concrete regression"

---

**Regression test: complete-answer-with-drafts-passes-check**

Target: services/result_acceptance.py::check_answer

Setup: prompt requests test drafts; answer contains "Regression test: queue" with Target:, Setup:, Action:, Expected: fields populated with concrete values.

Action: call check_answer(prompt, answer, kind="test-writing")

Expected: returns without raising (no exception)

---

**Regression test: unblock-plan-required-when-unblock-keyword-present**

Target: services/result_acceptance.py::check_deliverables

Setup: prompt contains "unblock 1035" but answer lacks "Unblock plan:" section.

Action: call check_deliverables(prompt, answer)

Expected: raises ResultRejected with "Missing actionable unblock plan"

---

**Regression test: unblock-plan-with-change-validation-exit-passes**

Target: services/result_acceptance.py::check_deliverables

Setup: answer contains "Unblock plan:" section with "Change: services/result_acceptance.py::check_deliverables", "Validation: python -m pytest services/test_result_acceptance.py::AcceptanceTests::test_concrete_drafts", "Exit condition: ResultRejected not raised"

Action: call check_deliverables(prompt, answer)

Expected: returns without raising

---

**Regression test: test-writing-job-executes-and-reports**

Target: services/dispatch_worker.py::execute

Setup: task_queue entry with kind="test-writing", worker="minimax", prompt containing "unblock 1035"; mock api_worker.evidence returning bounded snapshot.

Action: call execute(identifier, token)

Expected: transitions to "succeeded"; result contains "Regression test:" and "Unblock plan:"

---

## Unblock plan:

Change: services/result_acceptance.py::check_deliverables — the function checks for "Unblock plan:" but may not enforce concrete values when the original prompt names a specific lane without recording its assignment.

Validation: python -m pytest services/test_result_acceptance.py::AcceptanceTests::test_concrete_drafts_and_conditional_unblock_plan_reach_semantic_review -c exit 0

Exit condition: test_result_acceptance.py confirms that answers with concrete drafts plus a Change/Validation/Exit condition pass check_deliverables, and the lane 1035 task can be closed without manual override.

---

**Findings:** The acceptance module validates both test drafts and unblock plans using regex-based field extraction; the fixtures confirm this behavior. The bounded snapshot evidence confirms symbols like `check_deliverables`, `check_answer`, and `ResultRejected` are present. Without the original lane 1035 prompt, conditional actions are limited to verifying the acceptance logic itself.
