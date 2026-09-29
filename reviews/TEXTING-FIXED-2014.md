# Texting triage and fixes — 2014

Result: local validation PASS; committed and regularly pushed for fresh review.

- Branch: `draft/webbob-texting-0927` on `brain`.
- Parent: `78fa870a8ed7178662f97b0394ff80ba32ded63e`.
- New review SHA: `97513468016488ebe42ca1919e507db99fc0a15f`.
- Commit: `Clarify texting consent and preserve uncertain delivery receipts`.
- Validation date: September 27, 2026 America/Chicago (September 28 UTC).

The task supplied Gemini PASS on `78fa870` and MiniMax FAIL in
`LIVE-MINIMAX-draft_webbob-texting-0927-78fa870-rereview.md`. That report is not
present inside the permitted worktree. This triage checks the three claims
quoted in the task against the actual source; it does not claim to have read
an external report or obtained a fresh external verdict.

## MiniMax claim dispositions

| Claim | Actual code and evidence | Disposition |
| --- | --- | --- |
| Rejecting `request_id == draft["request_id"]` is wrong | `webchat/texting.py:281` now explains that draft creation cannot authorize its own delivery. `test_same_request_cannot_confirm_draft` in `webchat/test_texting.py:119` exercises both the chat replay rejection (409) and the consent guard directly, verifies no save, audit, or bridge call, then succeeds once with the same exact token in a later request. The mock delivery bridge is enabled. | Intentional invariant; equality check preserved. |
| Cancellation has an `IndentationError` | AST parsing passes for `texting.py` and `app.py` at both `78fa870` and the final source. The cancellation regression and full webchat suite pass. | False; no cancellation syntax change. |
| Bare yes/ok with `text_context` can send | `Texting.confirm()` still requires `re.fullmatch(r"yes (wbtxt-[0-9a-f]{32})", ...)`. A comment explains that tokenless phrases route to guidance. The strengthened test at `webchat/test_texting.py:101` checks all seven routed bare phrases with a working mock bridge, zero sends, zero handoffs, no consent consumption, and no model/job routing. The HTTP test at `webchat/test_texting_e2e.py:73` separately checks `yes`, `ok`, and `send it`, then confirms with the exact token. | False; unit and HTTP coverage strengthened. |

## Reproduced texting bug fixed

An Andrea delivery could succeed while its HTTP response was lost. Previously,
`Andrea.deliver()` converted any transport error into `False`, so the draft
became `confirmed_not_sent` and the owner was told “Not sent.”

The synthetic fixture now supports recording a delivery and closing the
connection without returning a receipt. The regression first failed against
the original runtime after asserting one mock delivery; its captured failure
is in [TEXTING-2014-lost-reply-before.txt](TEXTING-2014-lost-reply-before.txt).

`Andrea.deliver()` now distinguishes a confirmed delivery, a known rejection,
and an unknown outcome. Missing or invalid receipts, server errors, and lost
responses preserve `delivery_unconfirmed` and the consumed confirmation.
Only an affirmative receipt with a nonblank message GUID produces `sent`.
Authentication rejection and an absent endpoint (401/403/404/405) retain the
blocked receipt. Error handling retains only safe messages and HTTP status,
without exposing response bodies or credentials.

The lost-response test verifies the uncertain receipt, consumed token, audit
state, persisted state after restart, and exactly one bridge call despite
replays. Additional tests cover invalid acknowledgments and error redaction.
All deliveries in validation are synthetic fixture records.

## Validation on the committed source

| Check | Result | Evidence |
| --- | --- | --- |
| Seven focused consent, cancellation, receipt, and HTTP tests | 7 passed | [Targeted tests](TEXTING-2014-targeted-tests.txt) |
| `python3 -m unittest discover -s webchat -p 'test_*.py'` | 295 passed, 0 skipped, 44.760 s; includes the isolated browser proof | [Webchat suite](TEXTING-2014-webchat-tests.txt) |
| `python3 -m unittest discover -s services -p 'test_*.py'` | 121 passed, 0 skipped, 3.509 s in the identical source snapshot described below | [Services suite](TEXTING-2014-services-tests.txt) |
| AST parsing at the parent and final source; `node --check webchat/static/app.js` | PASS | [Syntax checks](TEXTING-2014-syntax-checks.txt) |
| `git diff --check` | PASS before commit | Four texting files committed |
| Regular push and exact remote SHA comparison | PASS; local and remote both `97513468016488ebe42ca1919e507db99fc0a15f` | [Tip and source verification](TEXTING-2014-tip-check.txt), [push log](TEXTING-2014-push.txt) |

### Services fixture location

To honor the worktree-only restriction, `TMPDIR` was set to
`reviews/.texting-proof-2014-tmp`. The initial services run completed 121 tests
with one error: `test_coding_boundary_allows_real_commit_and_normal_push`.
Its macOS sandbox denies writes under the module's source checkout, which
also covered the nested fixture repository. The full initial log is retained
in [TEXTING-2014-services-in-worktree.txt](TEXTING-2014-services-in-worktree.txt).

The entire services suite was rerun from a temporary source snapshot inside
this worktree, with fixture directories beside that snapshot. Its 169 tracked
files from `services/`, `state/`, `webchat/`, and `bootstrap.py` were copied
byte-for-byte from the working tree. The sandbox rules and all tests were
unchanged. The real sandboxed fixture commit/push and all 120 other tests
passed. Temporary source and fixture data were cleaned up afterward.

[The source hash manifest](TEXTING-2014-services-source-sha256.txt) was rechecked
after commit: all 169 files still match, including the four changed files.
The final tip verification also compares each changed file against its committed
bytes. Historical 0927 proof artifacts remain historical evidence; their source
hashes are not represented as evidence for this new SHA.

## Handoff and scope

No remaining reproduced texting defect is known from this triage.
[TEXTING-READY-2014.md](TEXTING-READY-2014.md) requests a fresh external review
of the new SHA; local green checks do not clear the external gate.

The two 2014 handoff markers and logs are local artifacts under this worktree's
`conductor/reviews/`, outside the code commit so they can identify its exact SHA.
The external conductor directory was not accessed. Existing untracked 2013
artifacts were left intact. No deployment, merge, undraft, force-push, real text,
Jeff notification, secret disclosure, or STOP-WEBBOB action was performed.
