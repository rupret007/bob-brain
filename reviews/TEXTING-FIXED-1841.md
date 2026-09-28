# Texting fixes — 1841 gate follow-up

**Branch:** `draft/webbob-texting-0927` on `brain` (draft only).

**Implementation / tested code SHA:** `e1f9ee1b9292bf9b7d3ec7f53220ceeae95fd14d`.

**Live baseline included:** `dff84e37169b30014ff0f48502b8cc66542cf737`.

**Review target:** the final draft-branch tip containing this marker and the regenerated evidence; the commit after the implementation changes only review files.

**Deploy verdict:** STILL FAIL until the remaining conductor gates below are cleared.

## Changes

1. **Honest, matching browser evidence.** `browser_texting.cjs` and
   `texting_proof.py` now exercise the blocked bridge, asserting “Not sent,”
   `confirmed_not_sent`, consumed consent after reload, and zero deliveries.
   All five screenshots, the JSON manifest and browser result were regenerated
   against implementation `e1f9ee1`. Source and screenshot SHA-256 hashes match.
   Mock “Sent via Andrea” success remains a separate HTTP/Python test path.
   The README and older reports distinguish current evidence from historical
   checkpoints and describe the single rejected Andrea bridge probe accurately.

2. **Public data filtering.** `Chat.public()` removes `codex_thread_id`,
   `retry_prompt`, `pending_job`, `pending_job_id`, and `held_job` before calling
   `texting.public()`. It deep-copies retained values and guards extension output
   with the same exclusions. The regression verifies that the texting layer never
   sees core-private values, cannot expose them through its output, and cannot
   mutate the original conversation. Private texting state and session identity
   remain absent from public JSON.

3. **Consent and error coverage.** Existing `hmac.compare_digest` comparisons for
   actor, yes-token and fingerprint are preserved. The new timing-safe comparison
   test spies on the actual primitive for valid and invalid tokens rather than
   drawing conclusions from noisy HTTP timings. Added the specifically requested
   `test_separate_yes_success_message_content`, plus Andrea 401/403/500 scrubbing
   checks for credentials, URLs and internal paths in responses and saved history.
   Worker-prefixed texting under a coding hold is also covered.

4. **Persistence.** Removed the extra save after `texting.handle()`. Every handled
   turn persists once through its callback, including pending-work cleanup.
   Confirmations have two intentional writes: consumed consent before any Andrea
   handoff, then the final receipt. Previously the pre-handoff durability comment
   was inaccurate: delivery occurred before saving. A failed first write now sends
   nothing; a failed receipt write leaves a durable “delivery unconfirmed” state
   with no reusable token, even after restart. Tests cover both failures and save
   ordering/counts.

5. **Browser controls.** Executing the previously skipped browser test exposed a
   missing `submitChatText` function used by the Texts, Edit, Cancel and Review
   buttons. Restored the helper through the existing composer submission flow.
   Filling a yes-token still does not submit it. Card copy now distinguishes sent,
   blocked and unconfirmed outcomes.

6. **Live integration.** Locally merged `dff84e3` while preserving the published
   `8f82fc0` ancestry for a regular push. The one `app.py` conflict preserves both
   texting's early routing and the live status-correction handler. The branch stays
   `draft/webbob-texting-0927`; no pull request was merged or undrafted.

## Verification

All required commands ran from the worktree root.

| Check | Result |
| --- | --- |
| `python3 -m unittest discover -s webchat -p 'test_*.py'` | **292 passed, 0 skipped**, including browser proof; 41.811 s |
| `python3 -m unittest discover -s services -p 'test_*.py'` | **121 passed**, 3.516 s |
| Focused `test_texting.py` suite | **33 passed** |
| `node --check webchat/static/app.js` | PASS |
| `node --check webchat/browser_texting.cjs` | PASS |
| `node --test webchat/test_quiet_hours_js.mjs` | **1 passed** |
| `python3 bootstrap.py check` | `syntax: PASS` |
| `git diff --check` | PASS |
| Committed-code isolated browser run | **5 screenshots**, 0 browser errors, 0 mock/real deliveries, unchanged live listener identities |
| Offline parity eval | **24/24**, plus **3/3** strict status checks; limited synthetic scope |

Logs: `TEXTING-1841-webchat-tests.txt`, `TEXTING-1841-services-tests.txt`, and
`TEXTING-1841-targeted-tests.txt`. `WEBBOB-TEXTING-0927.evidence.json` and
`WEBBOB-TEXTING-0927.browser.txt` describe the final screenshot run. Historical
0927 test logs remain explicitly labeled as historical. Test output about failed
providers or restarted reviewers is mocked behavior, not live operations.

Playwright and Chromium were installed only under the ignored
`webchat/node_modules/` directory. Browser-enabled checks used:

```sh
export PLAYWRIGHT_BROWSERS_PATH="$PWD/webchat/node_modules/.cache/ms-playwright"
python3 -m unittest discover -s webchat -p 'test_*.py'
python3 webchat/texting_proof.py
```

`WEBBOB-EVALS-0927.md` and `.json` provide newly executed offline evidence and a
reproduction command. They explain the seeded status fixture, the initial empty
fixture mismatch, and stricter checks added around three permissive eval rows.
They do not claim unrun live evals or production delivery parity.

## Remaining conductor gates

- Fresh LIVE Gemini and LIVE MiniMax **PASS on the same final pushed tip** are
  still required. The supplied reviews concern `8f82fc0` and cannot clear this tip.
- The conductor must assess the supplied limited offline eval evidence against
  its deployment eval requirement; no broader/live eval pass is claimed.
- Production outbound delivery still depends on a separately approved Andrea
  bridge. This change proves safe blocked behavior and synthetic success only.

`TEXTING-STILL-FAIL-1841.md` records these blockers; no READY marker is written.
No deploy, service restart, PR merge, undraft, force-push, real text, Jeff
notification, password disclosure, or `~/STOP-WEBBOB` creation was performed.
