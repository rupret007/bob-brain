Regression test: exploratory report is rejected
Target: services/test_result_acceptance.py, result_acceptance.accept
Setup: Use the fixture from services/fixtures/texting_jobcompletion_1035.json; supply a report with architecture findings and shell search commands but no 'Regression test:' headings with Target/Setup/Action/Expected fields; mock review to return accepted=true.
Action: Call accept(fixture["prompt"], exploratory_answer, review, kind="test-writing").
Expected: Raise ResultRejected before review is called; error message contains "Missing concrete regression".

Regression test: completed draft reaches semantic review
Target: services/test_result_acceptance.py, result_acceptance.accept
Setup: Use the fixture from services/fixtures/texting_jobcompletion_1035.json; supply a report containing two 'Regression test:' headings each with Target, Setup, Action, Expected fields, plus an Unblock plan section with Change, Validation, Exit condition lines; mock review to return accepted=true.
Action: Call accept(fixture["prompt"], complete_answer, review, kind="test-writing").
Expected: review is called and returns a verdict; no ResultRejected is raised.

Unblock plan:
Change: If the named unblock is the prior incomplete-report failure, no code change is needed because result_acceptance.check_deliverables already rejects missing drafts. Add the above drafts to services/test_result_acceptance.py to cover the missing coverage.
Validation: Run python3 -m unittest discover -s services -p 'test_*.py' and require zero failures.
Exit condition: Resolve Web Bob unblock 1035 only when a replay worker delivers the two drafts and Unblock plan and the test suite passes; retain the hold if any replay returns an exploratory answer without drafts.

These drafts are unexecuted. The original lane prompt for Web Bob unblock 1035 was not recorded; the regression drafts are grounded in the existing acceptance logic in result_acceptance.py and the fixture in services/fixtures/texting_jobcompletion_1035.json.
