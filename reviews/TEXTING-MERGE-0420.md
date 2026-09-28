# Texting onto live integrate — offline merge validation

Branch: `draft/webbob-texting-onto-a777736`

Merge parents:
- Integrate: `a777736b3f0a37c82b0c4c62be8c91117c4c9881`
- Texting: `97513468016488ebe42ca1919e507db99fc0a15f`
- Common ancestor: `dff84e37169b30014ff0f48502b8cc66542cf737`

## Conflict resolution

`webchat/app.py` retains integrate's `status_reply`, `reply_authority`,
`status_observation`, worker `requested_workers` / `issue_followup`, task/council
dispatch, and provider metadata filtering. Texting adds its import, injectable
`Texting()` instance, public filtering, provider-context filtering, and the
authenticated session actor on `submit`. Its early `texting.handle` runs before
generic routing; `persist_texting` removes pending job/council keys and saves the
private conversation. The diff from integrate contains only texting wiring.

`reviews/WEBBOB-EVALS-0927.md` preserves both the integrate rubric and historical
texting evidence. Earlier 24/24 plus 3/3, 31-case, and 33-case notes are explicitly
historical. The current 96-case parity assertion remains in the webchat suite.
No previous score or LIVE approval is claimed for the new combined commit.

All 51 integrate-only paths were checked byte-for-byte against integrate. All
27 texting-only paths were checked against texting, with only trailing whitespace
removed from `TEXTING-FIXED-0927.md` and `TEXTING-READY-0927.md` for the diff check.
The six shared paths are the eval notes, app, README, provider rules, static JS,
and `test_webchat.py`. Texting source, tests, fixtures, proof script, browser
script, static card assets, screenshots, and earlier evidence are retained.

## Validation on the combined source tree

| Command | Result | Evidence |
| --- | --- | --- |
| `python3 -m unittest discover -s webchat -p 'test_*.py'` | OK: 381 run, 380 passed, 1 skipped; 43.438s | [webchat log](TEXTING-0420-webchat-tests.txt) |
| `python3 -m unittest discover -s services -p 'test_*.py'` | OK: 131 passed; 3.712s | [services log](TEXTING-0420-services-tests.txt) |
| `node --check webchat/static/app.js` | PASS | Exit 0 |
| `git diff --check` and `git diff --cached --check` | PASS | Exit 0 |

The only skip is `TextingE2ETest.test_browser_proof_when_playwright_available`:
Playwright is unavailable to Node in this checkout. The retained screenshots are
historical artifacts from the texting tip; a new browser proof is not claimed.
Texting unit and HTTP E2E checks used synthetic loopback messaging fixtures.
No live model review, production messaging, or real text delivery was attempted.

`BOB_ROOT` and `BOB_WEBCHAT_DIR` were set to the isolated ignored
`reviews/.texting-proof-0420-runtime` data tree. Webchat's `TMPDIR` was inside that
tree. Services required `TMPDIR=/private/tmp`: its coding sandbox deliberately
blocks writes below the source checkout, and the default macOS `/var` alias
failed an existing path-equality assertion against `/private/var`. The two
environment-only failed attempts are preserved in
[the checkout-temp log](TEXTING-0420-services-initial-fixture-failure.txt) and
[the default-temp alias log](TEXTING-0420-services-temp-alias-failure.txt).
No services source, sandbox policy, or test assertion was changed.

## Handoff

Offline READY means ready for fresh LIVE Gemini and MiniMax review on the new
combined SHA. It does not authorize deployment. The full committed/pushed SHA
will be recorded in the requested `TEXTING-FIXED-0420.md` and
`TEXTING-READY-0420.md` conductor review markers after the regular draft push.
The worktree has no `conductor/reviews/` directory; the required shared conductor
review directory receives those markers. No PR, live pin, or production change
is part of this handoff.
