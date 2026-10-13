# r10fix2: explicit personal reminder replay

## Research before product edits

Investigated at `fa08cd808843` on `draft/webbob-h2h-r10`. The release gate
`release/solo.py:605–616` submits
`remind me to Web Bob local reminder replay <hex> in 1 second`, requires the
`reminders` provider and `Reminder saved`, then waits up to ten seconds for
exactly one persisted reminder notice from the background loop. Lines 617–625
also require direct recurring creation and durable cancellation.

In-process reproduction used `Chat(temp / 'conductor/webchat', temp,
OfflineProviders())`, the same application/storage layout as solo staging,
with offline probe/circuit stubs and `Chat.start_background()`. Outbound HTTP
and macOS notification functions were patched to raise if called. The input
was `remind me to Web Bob local reminder replay 0123abcd in 1 second` with a
valid UUID request ID. The observed result was:

```text
parse body: Web Bob local reminder replay 0123abcd
parse delay: 1.0 seconds; interval: None
provider: reminders
content: Draft reminder: Web Bob local reminder replay 0123abcd in 1 second.
         OK to set it? It isn't running yet—use a phone or oven timer if you
         need it counting now.
         Reply `yes wbrem-<32 hex>` to set.
scheduled reminders: []
provider calls: 0
due notices after 2.2 seconds of the actual background loop: []
```

The wrong behavior begins at commit
`2b8307b5aad757efabc626f31dfbac008073befe` ("require durable separate consent
for reminder and file creation"), within `cf83a9a..HEAD`, before r10fix
attempts 1–3. In `Reminders._handle`, that commit replaced `self.create(...)`
and its saved receipt with an unconditional `self.draft(...)`, justified by
the comment "Always ASK." This is still `webchat/reminders.py:664–670` at
the starting HEAD. `webchat/app.py:769–782` faithfully returns this draft
with provider `reminders`.

Read-only historical handler replay at a fixed clock and isolated temporary
storage confirmed the exact transition (historical reminder modules loaded
with current supporting imports):

| Revision | Parsed delay | Reply | Persisted reminders |
| --- | --- | --- | --- |
| `cf83a9a` | 1 second | `Reminder saved:` | 1 |
| `2b8307b^` | 1 second | `Reminder saved:` | 1 |
| `2b8307b` | 1 second | proposed reminder requiring `yes wbrem-…` | 0 |
| `fa08cd8` | 1 second | `Draft reminder:` requiring `yes wbrem-…` | 0 |

This is an overbroad consent requirement, not a provider routing, short-delay,
macOS notification, or parser failure. An explicit personal reminder request
already authorizes saving that reminder. Existing approval-language checks,
saved holds, unresolved schedules, extracted/model operands, executable
routines, and messages to other people still require their established gates.

## Existing test contract conflict

Some fixtures now assume *every* reminder needs a second message. For example,
`webchat/test_h2h_round2.py:260–262` submits
`remind me to check the oven in 10 minutes`, asserts an empty reminder store,
and then confirms a token. Several `ReminderChatTests` similarly submit
unqualified `remind me to … in …` through `confirm_reply`, which requires a
draft token. Restoring explicit reminder creation necessarily conflicts with
those inputs. Their assertions must not be removed or weakened. Confirmation
coverage can remain on the existing draft-producing request forms, with
separate regression coverage for explicit personal reminders.

## Implementation

`webchat/reminders.py` now recognizes the original, explicit personal forms
`remind me to <body> in <numeric duration>` and
`remind me every <numeric interval> to <body>` (including case variations,
optional `please`, and existing one-shot duration abbreviations). After the
unchanged parser, approval-language, and saved-hold checks succeed, it saves
through the existing durable `create()` and `created_receipt()` methods.
There is no special case for the gate's body, UUID, or one-second delay.
Previous reminder drafts lose their confirmation authority before the new
reminder is created. Lock order remains draft store then reminder items,
matching existing confirmation handling.

Matching the original request matters: normalization rewrites other reminder
forms into `remind me`, and resolving an incomplete weekday request synthesizes
a `remind me …` follow-up. Neither that synthesis nor model extraction grants
the new direct-save authority. Read-only routine actions and outbound messages
retain their existing authorization paths. Reminder help now describes the
direct-save forms accurately.

`webchat/test_explicit_reminders.py` adds five offline regressions. The exact
release message checks provider `reminders`, `Reminder saved`, request replay,
actual background-loop delivery within ten seconds, and one persisted notice
after restart. Additional cases check the release's recurring save/cancel
follow-up, unrelated bodies/delays, existing holds/approval clauses, and
replacement of older draft authority. Network connections, HTTP, macOS
notifications, and model replies are forbidden by the fixture.

The new tests reproduced the failure before the fix (four tests, five failing
subcases; the draft-replacement case was added with the implementation).
All five now pass. Evidence:
`/private/tmp/webbob-r10fix2-regression-before.log` and
`/private/tmp/webbob-r10fix2-regression-after.log`.

Six existing tests retain their confirmation coverage using existing
draft-producing setup commands: five in `test_reminders.py` and one in
`test_h2h_round2.py`. Their assertions, expected reply strings, bodies, delays,
and exact-token confirmation helper remain intact. Most now use
`create a reminder …`; the Instinct-body case uses the existing
`remind me in 1 minute to review Instinct` form to retain that route's explicit
Instinct exclusion. No production Instinct routing changes were needed.
Read-only AST review confirmed all 276 assertion calls in those two files
retain their structure and expected values after accounting only for nested
request-input arguments. `consent_fixture.py` is unchanged.

No files under `release/` or any of `services/api.py`, `services/budget.py`,
`webchat/api_call.py`, and `state/generation_budget.py` were changed. No commit
or push was attempted; the driver owns that step.

## Verification

All requested commands were attempted without weakening checks or adding
skips. This sandbox prohibits localhost socket binding, `/bin/ps`, and nested
`sandbox-exec`. The driver must rerun the full suites/browser proofs outside
the sandbox and then run the unchanged full release gate. No full-gate PASS
is claimed here.

| Command | Result |
| --- | --- |
| `python3 -m unittest discover -s webchat -p 'test_explicit_reminders.py'` | PASS, 5 tests |
| `python3 -m unittest discover -s webchat -p 'test_reminders.py'` | PASS, 44 tests |
| `python3 -m unittest discover -s webchat -p 'test_h2h_round2.py'` | PASS, 16 tests |
| `python3 -m unittest discover -s webchat -p 'test_*.py'` | 3,083 tests in 120.375s; 2,898 pass, 185 sandbox permission errors, zero assertion failures or skips |
| `python3 -m unittest discover -s services -p 'test_*.py'` | 313 tests; 1 failure and 3 errors from sandbox restrictions |
| `python3 -m unittest discover -s reviews -p 'test_*.py'` | 211 tests; 2 errors from denied localhost socket binding |
| `python3 -m unittest discover -s release -p 'test_*.py'` | 108 tests; 2 errors from denied localhost socket binding |
| `python3 webchat/cold_start_proof.py` | Blocked during fixture socket binding, before browser assertions |
| `python3 webchat/remaining_proof.py` | Blocked during fixture socket binding, before browser assertions |

The first full webchat run (before migrating confirmation setup commands)
ran 3,083 tests: 6 failures from the documented setup conflict and 185 errors
from sandbox restrictions (183 denied socket operations and 2 denied `/bin/ps`
calls). Those six setup conflicts were resolved without changing their
expected outcomes. The final run has zero assertion failures and the same
185 sandbox errors: 183 denied socket operations and 2 denied `/bin/ps`
calls. Services, reviews, release, and both browser proofs were also rerun
against the final product/test edits, with the same permission restrictions
and no new failures or skips. All unrestricted checks passed; the full suites
and browser proofs do **not** have a PASS receipt in this sandbox.

Logs are `/private/tmp/webbob-r10fix2-webchat.log`,
`/private/tmp/webbob-r10fix2-webchat-final.log`,
`/private/tmp/webbob-r10fix2-existing-reminders-after.log`,
`/private/tmp/webbob-r10fix2-round2-after.log`,
`/private/tmp/webbob-r10fix2-services.log`,
`/private/tmp/webbob-r10fix2-reviews.log`,
`/private/tmp/webbob-r10fix2-release.log`,
`/private/tmp/webbob-r10fix2-cold-start-proof.log`, and
`/private/tmp/webbob-r10fix2-remaining-proof.log`.

Services restrictions affect the process cleanup tests that invoke `ps` and
the real sandbox-boundary tests that invoke nested `sandbox-exec`. Reviews
errors are the private-HTTP queue replays in `isolated_replay_2055` and
`isolated_replay_2256`. Release errors are
`test_exact_action_replay_stays_held_without_global_solo_or_queue_writes` and
`test_failed_browser_keeps_original_error_and_metadata_after_fixture_cleanup`.
Both browser proofs fail in `MockMessaging` / `ThreadingHTTPServer` at
`socket.bind` (`webchat/texting_fixture.py:157`).

Final `git diff --check` passed. A read-only diff against HEAD confirmed no
changes in `release/` or the four protected files. The complete worktree edit
set is `webchat/reminders.py`, `webchat/test_explicit_reminders.py`, the two
existing test setup files above, and this report.
