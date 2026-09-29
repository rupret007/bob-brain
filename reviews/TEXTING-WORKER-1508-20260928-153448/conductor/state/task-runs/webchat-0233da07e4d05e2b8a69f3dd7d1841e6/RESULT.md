Regression test: Missing_unblock_plan_rejects
Target: services/test_result_acceptance.py::AcceptanceTests::test_1035_exploratory_answer_cannot_win_a_positive_vote
Setup: prompt="Project: Web Bob\nYour independent subtask:\nReview and regression test-case drafts for the following ongoing task. Ongoing task:\nObserved active lane: Web Bob unblock 1035. Its original task prompt was not recorded; inspect the project's current code and state that limitation. Do not invent the lane's exact assignment." with kind="test-writing"; answer="Regression test: queue\nTarget: services/test_result_acceptance.py::AcceptanceTests::test_concrete_drafts\nSetup: job={'id': 'one'}\nAction: check_answer(prompt, answer)\nExpected: ResultRejected('Missing actionable unblock plan')"
Regression test: Complete_answer_with_plan_passes
Target: services/test_result_acceptance.py::AcceptanceTests::test_concrete_drafts_and_conditional_unblock_plan_reach_semantic_review
Setup: prompt from fixtures/texting_jobcompletion_1035.json["prompt"]; answer fixture contains two regression test headings (Target/Setup/Action/Expected each), "Unblock plan:" with "Change:", "Validation:", "Exit condition:" lines, "Findings/limits:" sentence, and fenced JSON {"accepted": true, "reason": "Bounded drafts and plan delivered for unblock 1035"}
Action: check_answer(prompt, answer, kind="test-writing")
Expected: No ResultRejected raised

Unblock plan:
Change: Add test coverage for result_acceptance.check_deliverables rejecting independent-subtask answers missing the Unblock plan, targeting the existing AcceptanceTests class in services/test_result_acceptance.py with two new test methods: test_independent_task_requires_unblock_plan (failure case) and test_independent_task_with_complete_plan_passes (control case).
Validation: python3 -m unittest discover -s services -p 'test_*.py' -k 'test_independent_task'
Exit condition: Named unblock 1035 remains blocked until the actual lane worker produces its result; this test coverage addition addresses the deterministic gate gap that caused the previous exploratory-only rejection.

Findings/limits: The regression test drafts above are unexecuted; the original task prompt for lane "Web Bob unblock 1035" was not recorded, constraining the drafts to the deterministic acceptance gates in result_acceptance.py rather than lane-specific behavior.

```json
{"accepted": true, "reason": "Delivered two unexecuted regression test drafts grounded in result_acceptance.py check_deliverables logic, plus an Unblock plan for adding test coverage to close the gate gap that caused the exploratory-only 1035 failure; original lane prompt remains unavailable."}
```
