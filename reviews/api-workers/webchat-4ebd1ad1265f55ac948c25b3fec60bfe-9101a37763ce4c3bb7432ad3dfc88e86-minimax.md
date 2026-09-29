Regression test: missing_drafts_rejected
Target: services/test_result_acceptance.py, result_acceptance.check_deliverables
Setup: Prompt contains "Review and regression test-case drafts"; answer provides only architecture notes and shell commands without Target/Setup/Action/Expected fields; kind is "test-writing".
Action: Call check_deliverables(prompt, answer, kind="test-writing").
Expected: Raise ResultRejected with message containing "Missing concrete regression".

Regression test: well_formed_drafts_accepted
Target: services/test_result_acceptance.py, result_acceptance.check_deliverables
Setup: Prompt requires test drafts; answer contains two distinct cases with Target, Setup, Action, Expected fields on separate label lines; kind is "test-writing".
Action: Call check_deliverables(prompt, answer, kind="test-writing").
Expected: Returns None without raising; drafts pass structural validation.

Unblock plan:
Change: Ensure services/result_acceptance.py check_deliverables correctly identifies malformed drafts by verifying regex patterns for Target/Setup/Action/Expected fields; the existing implementation in lines 70-78 already enforces these requirements but may miss edge cases where fields contain only whitespace or placeholder text.
Validation: Run python3 -m unittest discover -s services -p 'test_*.py', expect zero failures in AcceptanceTests including test_1035_exploratory_answer_cannot_win_a_positive_vote and test_concrete_drafts_and_conditional_unblock_plan_reach_semantic_review.
Exit condition: Web Bob unblock 1035 remains blocked until a worker response contains concrete regression drafts and an unblock plan that pass check_deliverables; the actual blocked job must be identified in jobs.jsonl and resolved with a passing acceptance vote from the review worker.

These drafts are unexecuted. The original prompt for Web Bob unblock 1035 was not recorded in the manifest; the bounded evidence does not contain the actual blocked job ID or its failure state.
