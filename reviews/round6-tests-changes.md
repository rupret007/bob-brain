# Round-6 test changes

Base: `fc2b80d`, branch `draft/webbob-h2h-fixes`.

Only expectations pinning the reported bugs changed. No tests were removed or
skipped. Exact approval commands, full 32-hex tokens, validation, pending state,
replay, binding, and no-effect assertions remain unchanged.

## Existing expectation changes

- `webchat/test_h2h_round2.py::test_oven_delay_clock_and_separate_durable_consent`:
  add “OK to set it?” to the exact preview expectation. T04 needs a natural prose
  approval question; the inactive-timer warning and exact-token footer remain.
- `webchat/test_h2h_round3.py::test_relative_oven_has_no_computed_clock_and_schedules_nothing`:
  same T04 preview change; clock, consent, and no-scheduling checks remain.
- `webchat/test_h2h_round5.py::test_T04_exact_answer_and_one_approval_line`:
  same T04 preview change; still requires exactly two lines and the full token.
- `webchat/test_h2h_round4.py::test_T08_move_policy_asks_preferences_and_reviewable_change`:
  replace the “availability is unverified” pin with “Do not imply availability has
  been checked.” The old wording caused repetitive trailing disclaimers; the new
  instruction preserves the honesty requirement directly.
- `webchat/test_h2h_round5.py::test_T08_preferences_and_ready_office_message_wait_for_ok`
  (renamed `test_T08_preferences_and_conditional_plan_wait_for_ok`): replace the
  mandatory draft, greeting, and available-slots pins with missing preferences,
  no unsolicited full draft, and a proposed change for approval. Replace the
  repeated availability disclaimer as above. Approval and no-create checks stay.
- `webchat/test_h2h_round5.py::test_T34_known_projects_without_fetched_status`
  (renamed `test_T34_no_roster_without_fetched_status`): require absence of all five
  unsupported names instead of their presence. The useful offer and unfetched
  status checks remain; the old roster itself was the T34 fabrication bug.
- `webchat/test_h2h_round5.py::test_partial_project_records_do_not_hide_other_projects`
  (renamed `test_partial_project_records_do_not_invent_other_projects`): require
  absence of the four unrecorded projects, preserving the recorded Web Bob entry
  and “not a live check” assertion. Partial records do not establish a roster.
- `webchat/test_recorded_brief.py::test_short_project_updates_use_saved_facts_and_one_line_per_project`:
  require exactly two project lines, matching the two fixture records, instead
  of five lines padded with unsupported project names. Both supplied facts and
  provenance checks remain.

## New coverage

`webchat/test_h2h_round6.py` covers empty, partial, queue, and saved-note project
records (including names outside the former roster); assembled guidance across
appointment, cleanup, naming, and project-summary variants; relative reminders
for different tasks and delays; and exact approval, conversation/request binding,
and replay behavior. Providers and transports are inert, and stores are private.
Prompt assertions verify guidance delivery, not sampled model quality or H2H gains.

## Validation

All 21 modules ran sequentially with `nice -n 10 python3 -m pytest -q`
from `webchat`. The sandbox rejected the priority adjustment (`setpriority:
Operation not permitted`); `nice` still executed each test command.

Final results: **1,933 passed; 67 failed due to sandbox socket restrictions**.
Round 6: **10 passed**. Round 5: **17 passed**. No assertions were loosened to
address environment failures. Logs are in `reviews/h2h-round6-tests/`.

| Module | Passed | Sandbox socket failures |
| --- | ---: | ---: |
| `test_h2h_round6` | 10 | 0 |
| `test_h2h_round5` | 17 | 0 |
| `test_h2h_round4` | 22 | 0 |
| `test_h2h_round3` | 10 | 0 |
| `test_h2h_round2` | 16 | 0 |
| `test_recorded_brief` | 5 | 0 |
| `test_reminders` | 44 | 0 |
| `test_approval_language` | 1500 | 0 |
| `test_calendar_actions` | 32 | 0 |
| `test_personal_drafts` | 9 | 0 |
| `test_texting` | 0 | 49 |
| `test_texting_draft_routing` | 6 | 0 |
| `test_reply_quality` | 6 | 0 |
| `test_reply_contract` | 10 | 0 |
| `test_reply_authority` | 20 | 0 |
| `test_prompt_guidance` | 37 | 0 |
| `test_chat_intent` | 34 | 0 |
| `test_local_tasks` | 52 | 0 |
| `test_actions_intent` | 9 | 0 |
| `test_hold_scope` | 8 | 0 |
| `test_webchat` | 86 | 18 |

Environment corrections and limits:

- The new module initially imported `ledger` before the shared fixture initialized
  repository import paths. Reordering those imports fixed collection; all 10 pass.
- Standalone `test_reply_authority` initially had 17 missing-`task_queue` import
  failures. With `PYTHONPATH=../state`, all 20 pass.
- `test_local_tasks` initially had 7 path failures because the default temporary
  directory used `/var/...`, while its resolved fixture home used `/private/var/...`.
  With `TMPDIR=/private/tmp PYTHONPATH=../state`, all 52 pass. No test edits needed.
- All 49 `test_texting` failures and 18 `test_webchat` failures are
  `PermissionError: [Errno 1] Operation not permitted` when fixtures try to bind
  temporary local sockets. No socket permissions or test assertions were changed.
- `git diff --check` passed. An AST comparison confirms reminder code outside
  `draft_receipt` is unchanged; its full-token footer is unchanged in the diff.
- Production model/provider configuration is unchanged (`gemini-3.8-flash`).
  No live model sampling, live-state changes, deployment, or commit was performed.
