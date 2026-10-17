# FIX6: generalized approval intent

Branch: `draft/webbob-cap-3-tasks-routines` (PR #95 context).

Tests were committed first in `d765ca1`, against original implementation
`266a43a`. Implementation and category tests are in `b5431d5`.

## Changes

Replaced the accumulated catchphrase regex in `webchat/approval_language.py`
with independent semantic category detectors and shared grammatical signals.
`approval_categories()` returns overlapping reasons to ask;
`approval_requested()` retains the boolean interface used by both action paths.

Categories:

- `conditional_approval`: conditional clauses and temporal clauses with a person
  or possessor; the following verb need not appear in a vocabulary list.
- `preview_first`: previews and personal or prior inspection requests.
- `draft_only`: draft/provisional intent, restricted proposals, and negated effects.
- `wait_for_ok`: consent, waiting, holds, pending decisions, and delayed action.
- `dry_run`: simulation/rehearsal intent and explanations of hypothetical effects.
- `review_first`: personal, required, or prior review and assessment.
- `ambiguous_deferral`: uncertainty and incomplete before/until constraints.

Normalize case, Unicode typography, hyphens and whitespace. Inspect the entire
request, including requested content and quotes. A content interpretation or a
competing instruction does not cancel a hedge. Ambiguous matches require asking.
Ordinary review activities and a filename such as `proposal.txt` alone do not
imply a restriction. The module explicitly retains the honesty disclaimer:
this is a pattern/intent check, not a natural-language guarantee.

`reminders.parse()` uses the shared detector before parsing any schedule or
calling create/save; its duplicate phrase regex is removed. `local_tasks.py`
already checks `approval_requested()` before executing a create and retains
its durable draft and exact-token confirmation gate. No changes were needed
there. Holds, truth checks, allowlists, destructive confirmation, replay
protection and effect execution guards remain intact.

The existing recurring-reminder test now expects the earlier approval refusal
for ambiguous “until” clauses; its no-save assertions remain enforced.

## Corpus and verification

`webchat/test_approval_language.py` contains 84 distinct positive hedges:
12 per required category (72), plus 12 ambiguity cases. Every hedge runs through
`Chat.submit` for both a reminder and a file create (168 integration cases).
Another 28 cases cover timers, recurring reminders, morning reminders and
read-only morning routines. The 48 negative requests (24 reminders and 24 file
creates) verify actual successful effects and contents, including the normal
2am stretch reminder. This exceeds 100 paraphrases without counting generated
normalization or grammar combinations.

Tests use temporary homes/stores, mocked external adapters, effect spies and a
fixed clock of 2026-10-12 13:00 America/Chicago. Positive cases assert no reminder
create/save or file execute, no target file, no queued job/model/send/notification,
and a refusal or durable confirmation draft. Bare yes never executes a create.
Additional probes cover 48 shared-hedge/verb combinations, 336 typography/content
variants, all 72 required category labels, and five negated-consent cases.

- Failing first: 246 tests, 140 failures (116 action-boundary failures and 24
  shared-hedge subtest failures), zero errors. All 48 authorized controls passed.
- Final approval module: 249 tests pass as part of the focused run.
- Focused run: **393 tests pass** with
  `TMPDIR=/private/tmp PYTHONPATH=webchat python3 -m unittest test_approval_language test_reminders test_actions_intent test_local_tasks test_cap_ledger`.
- Ran the requested `python3 -m unittest discover -s webchat -p 'test_*.py'`.
  The initial run exposed macOS temporary-path alias failures as well as sandbox
  restrictions. Final rerun with `TMPDIR=/private/tmp`: **1,667 tests, zero
  assertion failures, 185 permission errors** (183 localhost socket binds and
  two `/bin/ps` calls). Full-suite success is not claimed in this sandbox.
- Baseline comparison loaded the original detector/reminder modules from
  `266a43a` and ran 1,418 existing tests: 86 temporary-path assertion failures
  and 186 errors. Of those errors, 182 were socket binds and two were `/bin/ps`;
  two diagnostic import/timing issues were rechecked separately with the repo
  import path restored (one pass, one socket-bind denial). This reproduces all
  185 permission-error cases in the final run. Using the canonical temporary
  directory resolves the 86 path-alias failures without changing file safety.

The explicitly protected files (`services/api.py`, `services/budget.py`,
`webchat/api_call.py`, `state/generation_budget.py`, `release/solo.py`) are
unchanged. No push, force-push or tags.

FIX6 DONE
