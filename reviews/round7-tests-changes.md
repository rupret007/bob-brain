# Round 7 test changes

Research was completed before code edits in `reviews/round7-research.md`. The
sandbox denied the requested harness-path write; that report is ready to copy.

Existing expectations changed only where they pinned a documented presentation bug:

- `test_h2h_round4.py::test_T11_complete_reply_requires_thread_and_recipient_verification`:
  replace the synthetic subject expectation with subject absence, since an unseen
  reply thread does not supply a subject. Replace the passive repeated wait footer
  with the conditional approval question. Greeting, supplied fact, requested details,
  signoff, verification, pending-on-go-ahead, and no-send assertions remain.
- `test_h2h_round4.py::test_T38_bio_policy_honors_count_without_fabrication`:
  replace the mandated dad-energy/jokes guidance with restrained humor only if
  requested. The old rule encouraged invented stereotypes in factual bios. Genre,
  audience-response, exact count and unchanged-artifact checks remain.
- `test_personal_drafts.py::test_missing_channel_keeps_concrete_draft_and_no_job`:
  email replies require the conditional approval question, thread/recipient
  verification and no synthetic subject. New email, thank-you note and booking
  assertions are unchanged; pending state and no-effects checks remain.

No tests removed or skipped; no token, authorization, timing, binding, replay,
pending-state or no-effect assertions loosened. Round 7 adds varied requests,
draft-state and token-binding checks plus assembled guidance tests. Prompt tests
do not establish sampled model quality or an H2H gate pass.

## Validation

All requested suites ran sequentially with
`nice -n 10 /opt/homebrew/bin/python3.12 -m pytest -q webchat/<suite>.py`.
The sandbox denied the priority adjustment, but `nice` executed Python 3.12.

| Suite | Passed | Failed |
| --- | ---: | ---: |
| test_h2h_round7 | 10 | 0 |
| test_h2h_round6 | 10 | 0 |
| test_h2h_round5 | 17 | 0 |
| test_h2h_round4 | 22 | 0 |
| test_h2h_round3 | 10 | 0 |
| test_h2h_round2 | 16 | 0 |
| test_recorded_brief | 5 | 0 |
| test_texting | 0 | 49 |

Requested-suite total: **90 passed, 49 failed**. Every texting failure is
`PermissionError: [Errno 1] Operation not permitted` at its fixture's loopback
socket bind, before exercising the test. No assertions or fixtures were changed
to bypass that restriction. This is the same environment limitation documented
in round 6. Round 7's socket-free tests exercise held-text token binding and
uncertain handoff/replay behavior using inert transports.

Additional relevant suites, also sequential with the same interpreter and nice:
`test_personal_drafts` **9 passed**, `test_calendar_actions` **32 passed**,
`test_approval_language` **1,500 passed**. Overall: **1,631 passed, 49 failed**
(subtests excluded from these counts). Full logs: `reviews/h2h-round7-tests/`.

The first new-test run exposed two test-construction errors: `str.capitalize()`
lowercased “Thursday”, and a direct calendar handler call omitted its required
intent-state argument. Corrected to preserve supplied casing and pass a fresh
intent state; no behavior or existing assertions changed to accommodate failures.

`git diff --check` passed. AST comparison confirms all of `texting.py` outside
the final draft display return is identical to HEAD. `calendar_actions.py`,
`reminders.py`, and `approval_language.py` are byte-identical to HEAD. Full-token
generation and validation, binding, replay prevention, and the model/provider
configuration are unchanged. No H2H rerun or sampled model-quality claim is made.
No commit, deployment, port 8787, svc screen, or live-state change was performed.
