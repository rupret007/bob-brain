# Instinct 0810 — offline validation

Branch: `draft/webbob-instinct-0810`; base: `1d72c44` (texting merge included).

Instinct status/latest replies, bounded digest, and explicit or suggested reply
drafts run through Web Bob's existing authenticated texting entry point. Reads
use the BlueBubbles allowlist, and delivery keeps the existing separate exact
yes, session/conversation binding, durable one-shot consent, and Andrea bridge.
No auto-reply, watcher, routine, provider dispatch, or direct send was added.

## Final validation

| Check | Result | Evidence |
| --- | --- | --- |
| Web Bob: `cd webchat && TMPDIR=/private/tmp python3 -m pytest -q --tb=short` | 411 passed, 1 skipped | [log](INSTINCT-0810-webchat-tests.txt) |
| Services: `cd services && TMPDIR=/private/tmp python3 -m pytest -q --tb=short` | 131 passed | [log](INSTINCT-0810-services-tests.txt) |
| Instinct regression suite | 31 passed, included above | `webchat/test_instinct.py` |
| `python3 webchat/instinct_eval.py` | 22/22 passed | [rubric](INSTINCT-0810-instinct-eval.txt) |
| `python3 webchat/bob_parity_eval.py` | 118/118 passed, score 10/10; includes the 22 Instinct cases | [summary](INSTINCT-0810-bob-eval.txt) |
| `node webchat/test_quiet_hours_js.mjs` | OK | Exit 0 |
| `node webchat/test_job_results_js.mjs` | OK | Exit 0 |
| `node --check webchat/static/app.js` | PASS | Exit 0 |
| Python compile check for bootstrap and Instinct/texting modules | PASS | Exit 0 |
| `git diff --check` | PASS | Exit 0 |

The sole skip is the existing optional
`TextingE2ETest.test_browser_proof_when_playwright_available` (Playwright is not
available to Node). Instinct's authenticated HTTP read/digest/draft/yes flow runs
against a synthetic loopback server. No new browser or real-delivery proof is
claimed.

Initial full-suite failures are preserved in
[webchat](INSTINCT-0810-webchat-initial-failures.txt) and
[services](INSTINCT-0810-services-temp-alias-failure.txt). The existing nested
deployment and service tests compare canonical paths; macOS's default `/var`
temp alias fails those assertions. The documented `TMPDIR=/private/tmp` fixes
the environment without changing production code. The other initial failure
was the expected parity count, updated from 96 to 118 with an explicit check
that all 22 Instinct cases are included.

## Boundaries and handoff

All validation used synthetic thread data and mock Andrea/BlueBubbles, including
approved-delivery checks. Live thread identity/connectivity is unverified in
this lane. A verified `BOB_INSTINCT_CHAT_GUID` is available for unnamed or
ambiguous contacts; otherwise only an exact Instinct name with a single verified
recipient is accepted. No phone number or production configuration was added.

Digests use keyword flags and quoted excerpts from at most 30 messages. They do
not inspect attachments or certify that no other deadlines exist. Generated
drafts use conservative local templates; raw messages never go to a provider.

The reviewed full commit SHA will be written after commit to
`/Users/jeffstory/Documents/bob-overnight-inject/conductor/reviews/INSTINCT-FIXED-0810.md`
and `INSTINCT-READY-0810.md`. That shared conductor directory also receives the
fresh LIVE Gemini/MiniMax evidence and gate marker. This checkout is the
conductor code root, so repository evidence is under `reviews/`.

Offline READY and any eventual `GATE: BOTH_PASS` are review results only. This
lane remains a draft PR. No merge, deployment, live pin/service change, Jeff
notification, or real iMessage/SMS is authorized or performed.
