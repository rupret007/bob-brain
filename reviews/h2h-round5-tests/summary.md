# Round-5 validation

1966/2036 test methods passed across 21 modules; 67 methods blocked by the sandbox and 3 methods encounter baseline fixture errors (48 subtest errors). The 18 entirely passing modules contain 1,837 tests. Round-5: 17/17. Approval language: 1,500/1,500.

Modules were run sequentially using `nice -n 10 python3 -m unittest MODULE` from `webchat`, with canonical `TMPDIR=/private/tmp` and repo/root, webchat, compat, services, and state on PYTHONPATH as needed. macOS sandbox rejects the nice priority adjustment (`setpriority: Operation not permitted`) but executes the tests.

No HTTP fixture bound a port: sandbox rejects their ephemeral localhost binds. No live state, port 8787, service screens, deployment, or production model/provider configuration was changed. Provider guidance tests use isolated fixtures and do not establish sampled live model quality.

A clean `git archive HEAD` snapshot in a temporary directory reproduced the same 48 `test_cap_ledger` subtest errors across 3 methods; fixture mocks lack the context-manager protocol. Tests and production safety were not weakened to conceal these errors.

An AST comparison confirms the text confirmation validators, reminder/calendar/local-file control handlers, and reminder/calendar draft creation functions are unchanged from HEAD. `git diff --check` passes.

| Module | Passed / run | Result |
| --- | ---: | --- |
| `test_actions_intent` | 9/9 | Pass |
| `test_approval_language` | 1500/1500 | Pass |
| `test_calendar_actions` | 32/32 | Pass |
| `test_cap_ledger` | 43/46 | Pre-existing mock context-manager errors; identical on b63c23d |
| `test_chat_intent` | 34/34 | Pass |
| `test_h2h_round2` | 16/16 | Pass |
| `test_h2h_round3` | 10/10 | Pass |
| `test_h2h_round4` | 22/22 | Pass |
| `test_h2h_round5` | 17/17 | Pass |
| `test_hold_scope` | 8/8 | Pass |
| `test_local_tasks` | 52/52 | Pass |
| `test_personal_drafts` | 9/9 | Pass |
| `test_prompt_guidance` | 37/37 | Pass |
| `test_recorded_brief` | 5/5 | Pass |
| `test_reminders` | 44/44 | Pass |
| `test_reply_authority` | 20/20 | Pass |
| `test_reply_contract` | 10/10 | Pass |
| `test_reply_quality` | 6/6 | Pass |
| `test_texting` | 0/49 | Sandbox denies localhost fixture bind |
| `test_texting_draft_routing` | 6/6 | Pass |
| `test_webchat` | 86/104 | Sandbox denies localhost fixture bind |

## Delivery constraints

- HEAD remains `b63c23d` on `draft/webbob-h2h-fixes`. Staging failed because the worktree Git directory is outside permitted writable roots: `index.lock: Operation not permitted`. No commit or push was made.
- Writing the requested external `h2h/round5-tests-changes.md` was denied by the filesystem sandbox. The complete per-method pin audit is saved at `reviews/round5-tests-changes.md` in the workspace.
- Existing untracked round-2/3/4 review logs were left intact. Round-5 logs are in this directory.
