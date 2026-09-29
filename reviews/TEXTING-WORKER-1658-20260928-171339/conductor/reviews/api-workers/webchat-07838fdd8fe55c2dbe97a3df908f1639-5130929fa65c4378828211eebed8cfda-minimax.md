Regression test: test_drafts_required_for_test_writing_kind
Target: services/result_acceptance.py; result_acceptance.check_deliverables
Setup: prompt='Your independent subtask: Review and regression test-case drafts. Ongoing task: Web Bob unblock 1035.'; answer='Findings: inspect the code. Commands: grep job. Missing actual drafts.'; kind='test-writing'
Action: call result_acceptance.check_deliverables(prompt, answer, kind='test-writing')
Expected: raises ResultRejected with 'Missing concrete regression test drafts'

Regression test: valid_drafts_with_all_sections_passes_guard
Target: services/result_acceptance.py; result_acceptance.check_deliverables
Setup: prompt='Your independent subtask: Review and regression test-case drafts. Ongoing task: Web Bob unblock 1035.'; answer='Regression test: test_drafts_required\nTarget: services/result_acceptance.py\nSetup: prompt contains test-writing kind; answer has no regression_tests section\nAction: call check_deliverables(prompt, answer, kind=kind)\nExpected: raises ResultRejected\n\nFindings/limits: concrete finding.'; kind='test-writing'
Action: call result_acceptance.check_deliverables(prompt, answer, kind='test-writing')
Expected: returns None; passes the draft requirement when all sections (Target, Setup, Action, Expected) are present

Unblock plan:
Change: Validate existing CompletionContractTests in services/test_replay_completion.py for test-writing kind acceptance; the check_deliverables DRAFT_ERROR guard is already implemented and requires two structured regression cases plus unblock plan for task prompts containing 'unblock' or 'actionable plan'.
Validation: Run python3 -m unittest discover -s services -p 'test_*.py' to verify existing CompletionContractTests pass; the actual command output is not supplied and requires a worker execution.
Exit condition: Web Bob unblock 1035 remains blocked until actual worker results, fresh semantic reviews and live replay gates pass; the original task prompt was not recorded (limitation stated per task requirements), and these unexecuted drafts cannot close the lane without worker execution evidence.

```json
{"accepted": true, "reason": "Delivered failure/control regression test drafts targeting check_deliverables DRAFT_ERROR guard; traced through supplied code in result_acceptance.py and test_replay_completion.py; no execution performed."}
```
Findings/limits: The original task prompt for Web Bob unblock 1035 was not recorded (stated limitation per task requirements). Existing CompletionContractTests already validates completion JSON guards; check_deliverables DRAFT_ERROR requires exactly two regression cases with Target/Setup/Action/Expected sections for test-writing kind tasks. Drafts are unexecuted per task constraints.
