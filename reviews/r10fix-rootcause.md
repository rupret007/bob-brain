# R10 release regression investigation

## Attempt-three research at 9eec945 (before product/harness edits)

The driver committed attempt two as `9eec945ab7dbd992723f8a9d3494326c63a9d527`.
The latest outside-sandbox receipts are
`/Users/jeffstory/Documents/bob-overnight-inject/local-cursor-codex-leftovers-1005/goal1006d/r10fix-verify-2/`.
`webchat.log` reports **3070 tests, zero failures/errors, one skip**. The original
consent/provenance/dispatch/source-label regressions and the subsequent home-alias
regression no longer fail. `services.log` reports the same single temporary-path
identity failure documented below. Both browser logs still stop at argument
parsing; neither has exercised the repaired browser interactions.

The remaining causes were rechecked with `git log -p`, `git blame`, and direct
Node module probes before making further edits:

| Remaining result | Exact source and introducing commit | Repair direction |
| --- | --- | --- |
| Cold proof requires `--output-dir` | `webchat/cold_start_proof.py:17`, `99c7ab95e101742b10f345f3098c571ff23df44c` | Allow the requested bare invocation, retaining evidence in a unique private temporary directory and reporting its path. |
| Remaining proof requires `--output-dir` | `webchat/remaining_proof.py:17`, `0e144270e7b045cb6cc672bd5b5309863f7f984c` | Same default, with every existing assertion preserved. |
| Webchat browser test skipped | `webchat/test_texting_e2e.py:89–95`, skip introduced in `a13a4b659dac`; explicit module override in `e1f9ee1b9292` | Supply the already installed shared Playwright module through the existing environment contract. Do not edit the test or its skip/assertion logic. |
| Services repository identity comparison fails | `services/dispatch_worker.py:32`, canonicalization introduced in `1f6c042e066d6c9048553f03908ed3218f2f5fe3`; compared at `services/test_api_workers.py:204` | Use canonical temporary paths, as the release harness already does. Keep production repository canonicalization intact. |

All four causes predate `cf83a9a`; none was introduced in the 80-commit regression
range. `4f40935c20b35bf87e1096e8154bbdf17dedccc1` explicitly sets canonical
`TMPDIR` in the release harness. Current `release/solo.py:871–874` also supplies
`BOB_PLAYWRIGHT_MODULE`. The outside rerun omitted this existing setup: default
`require('playwright')` from this worktree fails, while the shared installed
module at `conductor/webchat/node_modules/playwright` loads successfully.

To make the next rerun reproducible, add a checked-in offline verification entry
point for these four unchanged discovery suites and two unchanged browser
assertion sets. It must supply release-equivalent environment isolation, require
the installed browser dependency, retain logs, and fail on any skip or nonzero
exit. The two standalone proof drivers will also discover the existing local or
shared browser runtime (explicit override takes precedence), without modifying
application startup or installing anything from the network.

Static review confirms the current browser confirmation expressions match the
product's exact draft token and scheduled reminder ID. Due-notification matching
and request-ID retry deduplication remain intact. A one-second draft legitimately
expires if confirmation arrives late; this investigation does not authorize
relaxing that consent rule or any timing/safety assertion.

### Additional reproduced source-integrity gap in the same wording pass

An independent in-process replay found that `Chat.save` still rewrites literal
saved-memory inspection. Save the note `Keep the original receipt for the
lifecycle stage handback.` with its separate memory-proposal confirmation, then
ask `show my saved memories`: the displayed note becomes `Keep the original
confirmation for the status saved update.` Although storage remains intact,
the direct inspection no longer faithfully quotes its source.

The first bad runtime commit is again `13ce547a4b69493b7a7b98a1f2ce147dfd1da8be`,
which adds the presentation pass at `webchat/app.py:220–225` in that revision;
the substitutions originate in `eb52e9cf` (`webchat/reply_quality.py:31–42` at
the current HEAD). The attempt-one exclusions at current `app.py:224–228`
preserve reviewed receipts but omit the existing `private_memory` marker.
Repair that same save boundary to preserve private-memory text, including its
existing redaction, and add a separate regression test without touching existing
tests. The original receipt/provenance gates and ordinary reply improvements
remain in force.

### Attempt-three implementation and verification

`Chat.save` now preserves `private_memory` source text. Two new tests exercise
separate memory-proposal consent, literal inspection, retry identity, unchanged
storage, redaction, and exclusion from model history. Historical replay with the
same script passes at `13ce547a^`, fails at `13ce547a`, and passes after this fix.
Receipts: `/private/tmp/r10fix-validation-3/literal-memory-history-before.log`,
`literal-memory-history-introduced.log`, and `private-memory-focused.log`.
The 30 focused memory/wording tests and 157 tests covering the original safety
clusters plus both new test modules pass with zero skips. A first focused-only
invocation lacked the repository/state import paths; its import-error log is
retained separately and the corrected invocation passes (`safety-clusters.log`).

Both proof drivers now accept the literal commands requested in this task,
allocate unique private evidence directories when omitted, print their paths,
and discover the installed Playwright runtime. Explicit runtime overrides remain
authoritative. Six new tests cover discovery and configuration boundaries.
The installed shared runtime is also linked at the already ignored
`webchat/node_modules/playwright` in this worktree; a direct default Node
`require('playwright')` now succeeds without any environment override. This
local dependency setup performs no download and is not part of the commit.
`reviews/r10fix_verify.py` runs all four unchanged discovery suites and both
proofs with isolated synthetic roots, stripped credential/generation variables,
canonical `/private/tmp` on macOS, installed Playwright, and Python assertions
enabled. It rejects skipped/empty suites and nonzero exits, invalidates stale
green receipts before setup, and terminates timed-out process groups. Independent
synthetic runner tests verified all these behaviors, including cleanup of a
TERM-resistant browser-like grandchild (`runner-review/review-receipt.json`).
The parser uses the final anchored unittest summary, so earlier printed
`skipped=0` output cannot mask a real skipped test.

Full requested verification against the repaired product code is retained in
`/private/tmp/r10fix-validation-3/full/`:

| Check | Tests | Result in this sandbox |
| --- | ---: | --- |
| Webchat discovery | 3078 | 0 assertion failures; 185 errors; 0 skipped |
| Services discovery | 313 | 2 failures; 3 errors; 0 skipped |
| Reviews discovery | 211 | 2 errors; 0 skipped |
| Release discovery | 108 | 2 errors; 0 skipped |
| Cold-start browser proof | attempted | loopback bind denied before Node |
| Remaining browser proof | attempted | loopback bind denied before Node |

**Sandbox blocks sockets:** every one of the 183 Webchat socket errors, both
Reviews errors, both Release errors, and both proof errors reports
`PermissionError: [Errno 1] Operation not permitted` at `socket.bind`. The other
two Webchat errors deny `ps`. Services has two denied `ps` calls, two nested
`sandbox-exec` denials, and one unavailable screen-inventory check. All blocks
were classified; there are no unexplained failures. The full run initially used
the canonical host temporary directory; Services was then rerun with the final
runner's release-equivalent `/private/tmp` and has the same restrictions
(`canonical-services/services.log`). Its outside-run path-comparison assertion
does not recur. These are **not passing release/browser receipts**.

The literal bare proof commands were also attempted (`cold-bare.log`,
`remaining-bare.log`). They now pass argument parsing and runtime discovery and
reach the same socket denial. An additional in-process replay confirms capability
answers, draft-before-consent, one saved reminder after request-ID retry, actual
due-message formatting, recurring reminder IDs, and cancellation with zero
provider/network calls (`offline-browser-replay.log`); this is not a substitute
for a real browser run. Reminder expiration safety remains unchanged.

All 165 existing tracked test files are byte-identical to `9eec945`. All 17
existing Python proof assertions are unchanged; neither browser JavaScript file
was edited in this attempt. The four prohibited files are unchanged. Both Node
syntax checks and `git diff --check` pass. No paid API calls, external sends,
remote push, or deployment were performed.

The driver can rerun the complete requested checks outside this sandbox with:

```sh
python3 reviews/r10fix_verify.py --output-dir /private/tmp/r10fix-outside-3
```

### Attempt-three commit restriction

Both staging the eight prepared files and the requested normal commit were
attempted and failed with exit 128 because this linked worktree's Git metadata
lies outside the writable sandbox roots:

```
fatal: Unable to create '/Users/jeffstory/Documents/bob-overnight-inject/bob-brain/.git/worktrees/webbob-h2h-cand-268056a/index.lock': Operation not permitted
```

HEAD remains `9eec945` on `draft/webbob-h2h-r10`, with eight prepared files
uncommitted. Permission escalation is unavailable. The requested normal commit must be
performed by the outside driver after verification; no metadata was relocated
or changes discarded to manufacture a clean worktree. The intended command is:

```sh
git add -- reviews/r10fix-rootcause.md reviews/r10fix_verify.py webchat/app.py webchat/cold_start_proof.py webchat/remaining_proof.py webchat/proof_runtime.py webchat/test_private_memory_source_text.py webchat/test_proof_runtime.py
git commit -m 'fix(r10): restore consent/provenance/ask-first gates broken since cf83a9a'
```

## Follow-up investigation at cf5a5dd (recorded before further product edits)

The driver committed the first repair as `cf5a5dd1c997b7b28ef85434d643fb5f6a0685df`.
The latest outside-sandbox receipts are in
`/Users/jeffstory/Documents/bob-overnight-inject/local-cursor-codex-leftovers-1005/goal1006d/r10fix-verify-1/`.
They report 3065 Webchat tests with **86 failures and one skip**, one Services
failure, and two browser command-line errors. The original consent, provenance,
dispatch, priorities and source-label failure clusters no longer appear.
The earlier investigation and attempt-one results are retained below as history.

### Remaining local-file failures: trusted home alias lost

First bad commit: `1678809277f377c45efc70493d38a31b500dd33c`, which introduced
`LocalFiles`. Its original `webchat/local_tasks.py:126` resolves the trusted home,
while line 139 compares the unresolved input with that resolved home. At
`cf5a5dd` these are lines 203 and 217. `git show 1678809:webchat/local_tasks.py`
and `git log -p cf83a9a..HEAD -- webchat/local_tasks.py` establish the source.
macOS `/var` is a symlink to `/private/var`: an absolute path under a temporary
home spelled `/var/folders/.../home` fails `relative_to` against the canonical
`/private/var/folders/.../home`. The allowlist rejects it before evaluating the
intended runtime-storage or secret-content boundary.

All 86 failures have this cause, including literal punctuation paths, protected
runtime/accounting/calendar paths, legacy-draft creation and armored PGP reads.
Unmodified current tests reproduce it with the host's default temporary directory:
52 tests, 86 failures, zero errors/skips; receipt:
`/private/tmp/r10fix-validation-2/local-tasks-before.log`.

Repair direction: retain the trusted home spelling as well as its canonical
path, derive the suffix lexically from either, and perform exclusions and file
operations beneath the canonical home. Preserve the unmodified suffix for
traversal/private-path checks and descriptor-based `O_NOFOLLOW` operations.
Do **not** resolve the entire user path, which would hide symlink components.
Pass the same trusted alias through `LocalTasks.file_worker` and
`webchat/local_task_worker.py:run`, which currently transfer only canonical home.
No existing assertion or expected string needs changing.

### Services repo spelling and missing browser dependency setup

The single Services failure compares a canonical saved repository path with an
unresolved fixture path (`services/test_api_workers.py:204`). Its canonicalization
is `services/dispatch_worker.py:32`, introduced in `1f6c042e`, before `cf83a9a`;
it is unchanged in this regression range. The release harness already sets
`TMPDIR=/private/tmp` at `release/solo.py:871–873`, introduced in `4f40935c`, to
give repository-identity fixtures canonical paths. Preserve production repo
identity and run the requested full suites with the existing release setup.
Separately verify the local-file repair under the default `/var` path so the
release environment cannot conceal that product regression.

Four focused historical runs confirm that the unchanged Services test fails
with default `/var` temporary paths at both `cf83a9a` and `cf5a5dd`, and passes
at both revisions with `TMPDIR=/private/tmp`. Receipts:
`/private/tmp/r10fix-services-research/{baseline,current}-{default,canonical}.log`.

The single skip is attributable to the unchanged browser dependency check at
`webchat/test_texting_e2e.py:89–95`: it needs the shared installed Playwright via
`BOB_PLAYWRIGHT_MODULE`, as supplied by `release/solo.py:874`. The media tools
are present. Direct Node probes confirm that default `require('playwright')`
fails while requiring the shared module succeeds. Full verification explicitly
supplies this existing dependency and reports skips rather than altering tests.

### Latest browser receipts did not execute either proof

Both `cold.log` and `remaining.log` contain only argparse's required
`--output-dir` error. This is an invocation error, not evidence of a remaining
browser regression. The argument predates `cf83a9a` and the existing release
harness supplies it at `release/solo.py:847–849`. Run each Python driver with a
distinct output directory and the installed Playwright module. Both scripts
use isolated synthetic fixtures; real external delivery and model calls are
forbidden by their existing assertions. The prior repair preserved all original
browser assertions/expected strings, added separate exact-token confirmation,
and asserts zero scheduled reminders before that confirmation. Both JavaScript
files pass `node --check` at `cf5a5dd`.

### Follow-up implementation and focused verification

`LocalFiles` now retains both spellings of the trusted home. It translates only
that prefix before protected-storage comparisons; user suffixes still undergo
the original private-path/traversal checks and `O_NOFOLLOW` descriptor opens.
The child worker receives the alias separately and installs the parent's
canonical root verbatim. It does not resolve that root again: replacing the
canonical home with a symlink must remain a refusal. This boundary was checked
in an independent code review as well as a real subprocess regression test.

The **unchanged 52 local-task tests now pass, zero skipped**, under the host's
default `/var` temporary directory. Before/after receipts:
`/private/tmp/r10fix-validation-2/local-tasks-before.log` and
`/private/tmp/r10fix-validation-2/local-tasks-after.log`.
Five new tests in `webchat/test_local_home_alias.py` also pass, zero skipped.
They cover alias/canonical reads, user suffix symlinks and traversal, protected
trees through either spelling (including case variants), alias retargeting
across the actual child-worker boundary, and canonical-home symlink replacement.
No existing test, assertion, expected string, or browser script was edited in
this follow-up. The four prohibited files are byte-identical to `cf5a5dd`.

### Follow-up full verification

All requested checks were run against the final product code with independent
temporary `BOB_ROOT` directories, the existing release credential/generation
environment sanitization, `TMPDIR=/private/tmp`, and
`BOB_PLAYWRIGHT_MODULE=/Users/jeffstory/Documents/bob-overnight-inject/conductor/webchat/node_modules/playwright`.
The receipts and the exact synthetic runner are in
`/private/tmp/r10fix-validation-2/` (`run_check.py`, per-check JSON receipts and
the following logs). No existing tests were patched or skipped to bypass errors.

| Command/check | Tests | Final result in this sandbox | Log |
| --- | ---: | --- | --- |
| `python3 -m unittest discover -s webchat -p 'test_*.py'` | 3070 | 0 assertion failures, 185 errors, 0 skipped | `webchat.log` |
| `python3 -m unittest discover -s services -p 'test_*.py'` | 313 | 2 failures, 3 errors, 0 skipped | `services.log` |
| `python3 -m unittest discover -s reviews -p 'test_*.py'` | 211 | 2 errors, 0 skipped | `reviews.log` |
| `python3 -m unittest discover -s release -p 'test_*.py'` | 108 | 2 errors, 0 skipped | `release.log` |
| Cold-start browser proof with required output directory | attempted | loopback bind denied before Node | `cold-browser.log` |
| Remaining browser proof with required output directory | attempted | loopback bind denied before Node | `remaining-browser.log` |

**Sandbox blocks sockets:** all 183 Webchat socket errors, both Reviews errors,
both Release errors, and both browser attempts fail on loopback `socket.bind`
with `PermissionError: [Errno 1] Operation not permitted`. The remaining two
Webchat errors are denied `ps` executions. Every failure/error block was
classified; none is unexplained. Services has two denied `ps` calls, two nested
`sandbox-exec` denials (exit 71), and one screen-inventory failure:
`screen -ls` under the release TMPDIR reports
`Cannot access /private/tmp.screen: No such file or directory`.
These Services paths are unchanged since the passing release baseline.
The latest outside-run Services repo-spelling assertion does not recur with
the existing release environment. These results are **not** a passing release
check; the driver must rerun outside this sandbox.

The exact browser commands used (with the environment above) are:

```sh
python3 webchat/cold_start_proof.py --output-dir /private/tmp/r10fix-validation-2/cold-browser
python3 webchat/remaining_proof.py --output-dir /private/tmp/r10fix-validation-2/remaining-browser
```

Do not omit `--output-dir` on the outside rerun; the latest supplied receipts
never reached either browser proof for that reason. Both JavaScript syntax
checks and `git diff --check` pass. No paid API calls, external messages,
deployment, or push were performed. The added five tests account for the
increase from 3065 to 3070; all original tests are intact.

### Follow-up commit blocked by the filesystem sandbox

Both the requested `git add` and normal
`git commit -m 'fix(r10): restore consent/provenance/ask-first gates broken since cf83a9a'`
were attempted after verification. Both failed with exit 128:

```
fatal: Unable to create '/Users/jeffstory/Documents/bob-overnight-inject/bob-brain/.git/worktrees/webbob-h2h-cand-268056a/index.lock': Operation not permitted
```

The linked worktree's Git metadata is outside the writable roots; this session
does not permit escalation. No commit was created, metadata relocated, changes
discarded, or push attempted. HEAD remains `cf5a5dd` on `draft/webbob-h2h-r10`.
The worktree cannot be made clean by the requested normal commit here: these
four prepared files remain uncommitted:

- `reviews/r10fix-rootcause.md`
- `webchat/local_tasks.py`
- `webchat/local_task_worker.py`
- `webchat/test_local_home_alias.py` (new)

After outside-sandbox verification, the driver can create the requested commit:

```sh
git add -- reviews/r10fix-rootcause.md webchat/local_tasks.py webchat/local_task_worker.py webchat/test_local_home_alias.py
git commit -m 'fix(r10): restore consent/provenance/ask-first gates broken since cf83a9a'
```

## Original investigation and attempt-one history

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
