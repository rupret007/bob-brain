# R10 release regression investigation

Research recorded before changing product code or proof interactions. Candidate:
`draft/webbob-h2h-r10`, `268056aeae7c824b7968faaa995ce24bb17d4630`;
known passing baseline: `cf83a9a`. Investigated the 80 intervening commits with
`git log -p`, `git show`, and `git blame`, plus isolated historical checkouts.
Original receipts are in
`/Users/jeffstory/Documents/bob-overnight-inject/conductor/reviews/SOLO-0018-improve-268056aeae7c/attempt-0001/`.
Line references below refer to the unmodified candidate unless stated otherwise.

## Findings before edits

### Exact-yes file consent: 48 capability-ledger errors

First bad runtime commit: `13ce547a4b69493b7a7b98a1f2ce147dfd1da8be`.
Its new early call to `personal_drafts.handle` (`webchat/app.py:724–727`)
intercepts vague approvals before the native local-file consent handler.
The helper was introduced in `f360e68e7623cb51bd06aa5e120f421bbbbe75e0`:
`webchat/personal_drafts.py:16–22` assumes every calendar adapter implements a
context-managed draft store. The ledger's supported handle-only adapter does
not; `with lock()` raises `AttributeError: __enter__`. The error handler at
line 119 does not catch this protocol failure. Commit `76128a5138bb1339a3b2d99ab3adee9e5417b194`
added the earlier inspection at lines 115–116, but did not introduce the failure.
The unified pending inspection also omits local-file drafts.

Historical reproduction with unchanged tests: `13ce547^` runs 46 capability
ledger tests successfully; `13ce547` runs the same 46 with 48 errors. HEAD
reproduces the same errors. Logs: `/private/tmp/r10-consent-13ce547-parent.log`,
`/private/tmp/r10-consent-13ce547.log`, `/private/tmp/r10-consent-before.log`.
Repair direction: fail closed on an unavailable draft-store protocol, keep the
native exact-token confirmation path, and count local drafts when checking
ambiguity. Never treat failed inspection as permission.

### Provenance, project-context labels, priorities, and reported records: 18 failures

First bad runtime commit: `13ce547a4b69493b7a7b98a1f2ce147dfd1da8be`,
which runs the new wording pass inside `Chat.save` (`webchat/app.py:220–229`).
The broad substitution was introduced in `eb52e9cfa47c60e48364e8b8a3a7961969638508`,
`webchat/reply_quality.py:35`: `receipt` becomes `confirmation`.
The pass runs after provenance and authority checks and on deterministic
product receipts. It changes their source labels and checked evidence text.

This accounts for eight `received_payload_is_not_evidence_of_completed_work`
subtests, one provenance attribution test, both priorities-delivery tests
(including recovery_four), both project-context tests, and five
reported-record subtests. The supplied payload claims are still rejected;
the subsequent presentation pass corrupts the evidence checklist's
`execution receipt` wording. This is not justification to relax provenance.
Historical replay of the project source-label, recovery_four, and received
payload methods passes at `13ce547^` (3 methods) and fails at `13ce547`
(10 failures including eight subtests).

Repair direction: preserve deterministic project receipts and content that
has undergone authority/provenance review at the save boundary. Retain the
generic wording improvements for ordinary replies. Do not change assertions
or the review/acceptance rules.

### Ambiguous dispatch and saved proposal recovery: 3 failures, 1 error

First bad routing commit: `13ce547a4b69493b7a7b98a1f2ce147dfd1da8be`,
`webchat/app.py:724–727`, enabling the early personal-draft interception from
`f360e68e7623cb51bd06aa5e120f421bbbbe75e0` (`personal_drafts.py:111–128`).
Bare `go ahead`/`do it` no longer reach `task_dispatch.followup_work`, so a
current saved offer is not recovered and a missing work target gets the
wrong clarification. `06c59b7e` changes the intercepted zero-draft response
to the currently observed missing-approval-context text (line 125); it does
not fix the precedence error. The `fix it` response is independently rewritten
by `reply_quality.py:20–22` (introduced in `eb52e9cf`, enabled in `13ce547`).
HEAD reproduces 40 dispatch tests with 3 failures and 1 error in
`/private/tmp/r10-dispatch-before.log`.
Adjacent historical verification also passes all 40 at `13ce547^` and
reproduces all 3 failures plus 1 error at `13ce547`; logs are
`/private/tmp/r10-dispatch-13ce547-parent.log` and
`/private/tmp/r10-dispatch-13ce547.log`.

Repair direction: defer work follow-ups to the existing dispatcher when no
personal draft competes, preserve its current-offer and ambiguity checks,
and retain an existing request for work details across vague follow-ups.
Initial personal-approval clarification and useful initial troubleshooting
questions can remain; neither authorizes an effect.

### Browser cold-start and remaining reminders

`2b8307b5aad757efabc626f31dfbac008073befe` deliberately replaced direct
reminder creation with a durable draft requiring a separate exact `yes wbrem-…`
message (`webchat/reminders.py:664–669`, originally `_handle` lines 486–493).
The browser interactions were not migrated to this safer protocol.
`browser_remaining.cjs:74–75` reads a scheduled reminder ID from an unconfirmed
draft and dereferences a null regex match. The one-second notification waits
in both proofs can accidentally match `Draft reminder:` because Playwright's
text matching is case-insensitive; they do not establish delivery.

Cold-start has an additional earlier incompatibility:
`bf6a167f73ea7f4fe2e709e178792acac48dd1f8` adds bare
`once` to approval prerequisites and `accept*` to consent words in
`approval_language.py:43,61`. The synthetic reminder body `accepted once despite
lost acknowledgment` is therefore classified as conditional approval.
Historical classifier replay first changes at `bf6a167` (parent `b5431d5`).
`browser_cold_start.cjs:75–100` expects one scheduled row after retrying this
request; there are zero, not duplicate creations. Even without the phrase
collision, the later mandatory-consent change means the unconfirmed request
must not schedule a reminder.

Repair direction: preserve separate consent and every existing browser
assertion/expected product string. Add explicit browser confirmation
interactions; lost-response replay must exercise the actual confirmation
mutation. The timestamped synthetic input label is changed to `recovery
reminder`, preserving the body identity used by the unchanged assertions.
This avoids the fixture's accidental approval clause without creating a
product exception: quoted/content approval restrictions remain safety gates.
No fixture auto-authorizes product actions.

## Validation and final changes

Product fixes:

- `personal_drafts.pending` now counts native local-file drafts. Inspection
  protocol/storage failures return the existing clarification, with no effect.
  With no pending drafts/proposals, work follow-ups reach the existing dispatch
  resolver; stored proposals retain their explicit consent requirement.
- `Chat.save` preserves project-context receipts and authority/provenance-reviewed
  text. Ordinary h2h wording improvements remain enabled. Existing work-detail
  clarifications remain stable across vague follow-ups, while initial
  troubleshooting requests retain the more useful h2h question.
- The browser scripts explicitly request a draft, verify zero scheduled rows,
  and submit its full `yes wbrem-…` in a separate request. Cold-start loses and
  retries the actual confirmation response with the same request identity.
  Both proofs additionally verify an anchored actual due notification, so a
  draft cannot satisfy the old notification wait. All 15 original cold-start
  and 27 original remaining-proof assertion lines are preserved verbatim and
  in order. Only the synthetic cold-start input label changes as described
  above; expected product messages, exact consent, and the one-row invariant
  are preserved.

No existing Python test was edited. All four prohibited files are byte-identical
to HEAD. No paid API calls, real outbound messages, deployment, or push were
performed. Full synthetic suites used independent temporary `BOB_ROOT` directories,
credential/generation environment sanitization from `release/solo.py`, and
`TMPDIR=/private/tmp`. No tests were skipped or patched to evade sandbox failures.

Focused verification passes: 181 tests across all original failure clusters
and related h2h suites. The first full discovery additionally caught an overly
broad work-proposal fallback in this repair; it was narrowed to conversations
with no pending rows. The final dispatch/consent/h2h5 check passes all 118 tests
with zero skips (`/private/tmp/r10fix-validation/dispatch-consent-final.log`).
Both edited browser scripts pass `node --check`; `git diff --check` passes.

Full verification receipts are in `/private/tmp/r10fix-validation/`:

| Requested suite | Executed | Result in this sandbox |
| --- | ---: | --- |
| `python3 -m unittest discover -s webchat -p 'test_*.py'` | 3065 | 0 assertion failures, 185 sandbox errors: 183 socket binds, 2 `/bin/ps` calls |
| `python3 -m unittest discover -s services -p 'test_*.py'` | 313 | 2 failures, 3 errors; environment restrictions below |
| `python3 -m unittest discover -s reviews -p 'test_*.py'` | 211 | 2 errors: loopback socket binding denied |
| `python3 -m unittest discover -s release -p 'test_*.py'` | 108 | 2 errors: loopback socket binding denied |
| `python3 webchat/cold_start_proof.py --output-dir /private/tmp/r10fix-validation/cold-browser` | attempted | Fixture loopback socket binding denied before Node execution |
| `python3 webchat/remaining_proof.py --output-dir /private/tmp/r10fix-validation/remaining-browser` | attempted | Fixture loopback socket binding denied before Node execution |

**Sandbox blocks sockets:** both browser proofs fail at
`webchat/texting_fixture.py:157`, `ThreadingHTTPServer(('127.0.0.1', 0))`, with
`PermissionError: [Errno 1] Operation not permitted` from `socket.bind`.
The driver must rerun the full suites and browser proofs outside this sandbox;
these are not browser passes. Services also cannot execute `ps` or apply a
nested `sandbox-exec` profile, and its screen inventory check fails because
`screen -ls` reports missing `/private/tmp.screen` under the release TMPDIR.
The affected service code and test files are unchanged since `cf83a9a`.
See `webchat.log`, `services.log`, `reviews.log`, `release.log`,
`cold-browser.log`, and `remaining-browser.log` in the receipt directory.
All four discovery suites were run against the final product code, with zero
skips. Every webchat failure/error block was inspected: all 185 errors are the
two denied-operation categories above; all original regression clusters pass.
Both browser attempts set `BOB_PLAYWRIGHT_MODULE` to
`/Users/jeffstory/Documents/bob-overnight-inject/conductor/webchat/node_modules/playwright`,
matching the release driver's shared runtime.

## Commit restriction

The requested normal commit is prepared but cannot be written in this session.
`git add -- reviews/r10fix-rootcause.md webchat/app.py webchat/personal_drafts.py
webchat/reply_quality.py webchat/browser_cold_start.cjs webchat/browser_remaining.cjs`
fails with:

```
fatal: Unable to create '/Users/jeffstory/Documents/bob-overnight-inject/bob-brain/.git/worktrees/webbob-h2h-cand-268056a/index.lock': Operation not permitted
```

The normal `git commit -m 'fix(r10): restore consent/provenance/ask-first gates broken since cf83a9a'`
was also attempted after final verification and failed with the same denial.

The shared Git metadata directory is outside the writable sandbox roots, and
the session forbids permission escalation. No metadata was relocated and no
changes were discarded to manufacture a clean worktree. The six prepared
files remain uncommitted on `draft/webbob-h2h-r10` at `268056a`. After outside
verification, the driver must stage these files and create the requested
normal commit with message:
`fix(r10): restore consent/provenance/ask-first gates broken since cf83a9a`.
