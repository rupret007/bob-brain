Regression test: missing completion JSON fails closed
Target: services/result_acceptance.py::check_completion_json
Setup: prompt='Return JSON with accepted/reason fields.'; answer='Findings only.'
Action: check_completion_json(prompt, answer)
Expected: raises ResultRejected('Missing or ambiguous required completion JSON output block')

Regression test: complete accepted/reason JSON passes the completion guard
Target: services/result_acceptance.py::check_completion_json
Setup: prompt='Return JSON with accepted/reason fields.'; answer='{"accepted": true, "reason": "Delivered bounded unexecuted drafts."}'
Action: check_completion_json(prompt, answer)
Expected: returns None

Unblock plan:
Change: Validate existing CompletionContractTests in services/test_replay_completion.py for Web Bob unblock 1035; the check_completion_json guard already covers the required failure/control cases and needs no modification.
Validation: python3 -m unittest discover -s services -p 'test_*.py' - validation requires actual worker results and live gates not available to this draft
Exit condition: Web Bob unblock 1035 remains blocked until its actual task prompt and worker results are available; these unexecuted drafts cannot unblock the lane without live replay gates.

```json
{"accepted": true, "reason": "Delivered regression test drafts for check_completion_json guard using literal inputs from completion_guard_examples(); original unblock 1035 prompt unavailable and not invented."}
```
Findings/limits: Original task prompt for Web Bob unblock 1035 not recorded in manifest; task was test-writing kind per texting_jobcompletion_1035.json error. Existing CompletionContractTests.test_missing_malformed_or_ambiguous_json_cannot_win_a_positive_vote covers this guard. No shell/execution tools available; drafts are unexecuted per protocol. check_literal_guard_drafts in result_acceptance.py validates these literal guard drafts.
