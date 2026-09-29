Regression test: missing test drafts triggers rejection
Target: services/test_result_acceptance.py; result_acceptance.check_deliverables
Setup: prompt="Your independent subtask:\nReview and regression test-case drafts\n\nOngoing task:\nObserved active lane: Web Bob unblock 1035"; answer="Here are my findings about the lane. I will write tests later."; kind="test-writing"
Action: call check_deliverables(prompt, answer, kind="test-writing")
Expected: Raise ResultRejected containing 'Missing concrete regression test drafts'

Regression test: valid test drafts with plan passes deliverables gate
Target: services/test_result_acceptance.py; result_acceptance.check_deliverables
Setup: Use the exact prompt and answer from services/fixtures/texting_jobcompletion_1035.json fields; ensure answer contains 'Regression test:', 'Target:', 'Setup:', 'Action:', 'Expected:', 'Unblock plan:', 'Change:', 'Validation:', 'Exit condition:', the completion JSON and 'Findings/limits:'
Action: call check_deliverables(prompt_from_fixture, answer_from_fixture, kind="test-writing")
Expected: Return None without raising; check_completion_json is called internally

Unblock plan:
Change: Validate existing test coverage in services/test_result_acceptance.py for check_deliverables behavioral gates; existing code already raises ResultRejected for missing drafts/plan/JSON per services/result_acceptance.py lines 58-73.
Validation: Run python3 -m unittest discover -s services -p 'test_*.py' and require zero failures; manually inspect test_result_acceptance.py for coverage of the check_answer and check_deliverables behavioral paths.
Exit condition: Resolve Web Bob unblock 1035 only when actual saved reports contain the drafts, plan and completion JSON and every replay job passes acceptance; the structural check alone cannot close the unblock.

```json
{"accepted": true, "reason": "Delivered two behavioral drafts for check_deliverables regression coverage and a conditional validation plan; tests were not executed."}
```
Findings/limits: The original task prompt for lane 1035 was not recorded; drafts are grounded in the supplied result_acceptance.py implementation which already enforces the required structure. Execution requires tools not available in this environment.
