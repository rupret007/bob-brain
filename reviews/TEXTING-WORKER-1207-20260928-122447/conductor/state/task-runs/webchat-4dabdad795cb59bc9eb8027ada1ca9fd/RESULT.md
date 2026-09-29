Regression test: exploratory answer rejected for missing drafts
Target: services/test_result_acceptance.py, result_acceptance.accept
Setup: Load fixture services/fixtures/texting_jobcompletion_1035.json; its prompt asks for test drafts for Web Bob unblock 1035 but its answer contains only architecture findings and grep commands; mock review returning {"accepted": true, "reason": "Good effort"}.
Action: Call accept(fixture["prompt"], fixture["answer"], review, kind="test-writing").
Expected: Raise ResultRejected with message containing "Missing concrete regression test drafts"; review.assert_not_called.

Regression test: concrete drafts and conditional plan reach semantic review
Target: services/test_result_acceptance.py, result_acceptance.accept
Setup: Load fixture services/fixtures/texting_jobcompletion_1035.json; use its complete_answer field containing two regression test cases with Target/Setup/Action/Expected lines and an Unblock plan with Change/Validation/Exit condition; mock review returning {"accepted": true, "reason": "Bounded drafts delivered"}.
Action: Call accept(fixture["prompt"], fixture["complete_answer"], review, kind="test-writing").
Expected: review.assert_called_once returns accepted true; no ResultRejected is raised during deliverable checks.

Unblock plan:
Change: The result_acceptance module already enforces the test-draft and unblock-plan requirements via check_deliverables. No new check is needed. Propose adding coverage in services/test_result_acceptance.py for the 1035 scenario by extending test_concrete_drafts_and_conditional_unblock_plan_reach_semantic_review to explicitly load the 1035 fixture and assert the correct pass/fail split.
Validation: Run python3 -m unittest discover -s services -p 'test_*.py' and verify zero failures in AcceptanceTests.
Exit condition: Resolve Web Bob unblock 1035 only when a bounded replay worker delivers the two drafts plus an Unblock plan in its answer and the acceptance reviewer returns {"accepted": true}; retain the deployment hold if the replay still produces exploratory-only output.

These drafts are unexecuted. The original task prompt for lane Web Bob unblock 1035 was not recorded, limiting the assignment to conditional coverage grounded in the supplied dispatch/acceptance implementation.
