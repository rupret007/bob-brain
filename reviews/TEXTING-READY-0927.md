# Texting lane ready — 2026-09-27

**Worktree:** `workspaces/wt-webbob-texting-0927`  
**Branch:** `draft/webbob-texting-0927` (draft [PR #8](https://github.com/rupret007/bob-brain/pull/8), base `draft/webbob-clean-0927`)  
**Rebased onto:** `dcc2c8e` (Web Bob parity / jobs UI baseline on `brain`)  
**Goal:** Web Bob texting matches Bob the Bot for read → draft → separate yes; delivery is exercised only against **mocked** Andrea + BlueBubbles in tests. Production Andrea on this mini still has no Web Bob send bridge.

No merge, undraft, force-push, deploy, service restart, or real SMS/iMessage was performed for this document.

## What shipped

| Area | Behavior |
| --- | --- |
| Reads | `texts`, thread read/summarize via loopback BlueBubbles read allowlist |
| Drafts | Recipient + body card, five-minute `yes wbtxt-…` token, edits reset consent |
| Separate yes | Bare yes / send-it never sends; only exact `yes wbtxt-…` in a later chat turn |
| Mock delivery | Fixture `POST /web-bob/send` (Andrea handoff) when `enable_web_bob_send` is on — used in tests and `texting_proof.py` only |
| Production | Real Andrea control service: consent is recorded; `deliver()` probes `/web-bob/send`, gets 404, returns honest **Not sent.** receipt (unchanged safety) |
| UI | Draft card on chat messages, Texts quick chip, merged with `dcc2c8e` jobs/settings shell |

## End-to-end tests

| Test | What it proves |
| --- | --- |
| `webchat/test_texting_e2e.py::test_http_draft_shown_nothing_sent_until_separate_yes_then_mock_andrea` | Real `Server` + `/api/messages`: draft in JSON, no mock send until separate yes, then `owner_sent_via_andrea` and one mock send |
| `webchat/test_texting_e2e.py::test_browser_proof_when_playwright_available` | Optional Playwright run of `texting_proof.py` (skipped when `playwright` npm module missing) |
| `webchat/test_texting.py` | Unit/regression matrix including mock send and blocked production path |
| `webchat/texting_proof.py` + `browser_texting.cjs` | Isolated port, listener guard, screenshots under `reviews/` when Playwright is installed |

## Verification (this worktree)

Run from repository root (`workspaces/wt-webbob-texting-0927`):

```bash
node --check webchat/static/app.js
node --check webchat/browser_texting.cjs
node --test webchat/test_quiet_hours_js.mjs
python3 -m unittest discover -s webchat -p 'test_*.py'
python3 -m unittest discover -s services -p 'test_*.py'
python3 bootstrap.py check
```

| Check | Result (2026-09-27) |
| --- | --- |
| `webchat` unittest | **277 passed**, 1 skipped (browser proof without Playwright) |
| `services` unittest | **118 passed** |
| `bootstrap.py check` | `syntax: PASS` |

Optional isolated browser proof (does not touch port 8787 / 1234 / 4315):

```bash
# Install once where Node can see it: npm install playwright && npx playwright install chromium
python3 webchat/texting_proof.py
```

Artifacts: `reviews/WEBBOB-TEXTING-0927.evidence.json`, `reviews/WEBBOB-TEXTING-0927-*.png`.

## Deploy steps (human operator — not run by this lane)

Deploy only from an **approved** parity release process (e.g. after `draft/webbob-clean-0927` / parity PR merges per your conductor checklist). This texting branch stacks on that line.

1. **Pre-flight**
   - Confirm live Web Bob SHA you are replacing (rollback path documented in conductor parity reviews).
   - Ensure `~/STOP-WEBBOB` is **not** present if you intend to run the service.
   - Do not paste or log `conductor/webchat/.password` or Andrea/BlueBubbles tokens.

2. **Merge order (drafts only until explicitly approved)**
   - Land parity/clean base first if not already on the target host.
   - Merge or cherry-pick `draft/webbob-texting-0927` into the deploy branch your conductor uses (stay draft on GitHub until Jeff undrafts).

3. **Install on mini (example — match your existing `webchat` unit)**
   - `cd` to the bob-brain checkout at the chosen SHA.
   - `python3 bootstrap.py check`
   - Restart **only** via your existing supervised command (e.g. conductor redeploy script). This lane did not restart anything.

4. **Config (read-only checks OK; no credential output)**
   - BlueBubbles: `~/Library/Application Support/bluebubbles-server/config.db` (`password`, `socket_port`).
   - Andrea: `~/Andrea_NanoBot/.env` — control URL/token for **health** only until a real Web Bob send contract exists.
   - Optional env: `BOB_BLUEBUBBLES_CONFIG_DB`, `BOB_ANDREA_CONTROL_URL`, `BOB_ANDREA_CONTROL_TOKEN`.

5. **Post-deploy smoke (no sends)**
   - `curl -sS http://127.0.0.1:8787/api/version` — expect deployed short SHA.
   - Log in to Web Bob in a private window; open **Texts** chip → thread list loads.
   - `draft reply to <trusted contact>: TEST DRAFT ONLY` → card shows recipient/body; **do not** submit the yes token on production until delivery policy is explicitly enabled.

## Live check plan (manual, no automated texts)

Use a **non-production** conversation name or a contact you control. **Do not** complete the yes token on production until Andrea exposes an approved Web Bob send endpoint.

| Step | Action | Pass criteria |
| --- | --- | --- |
| 1 | Login | Session works; CSRF present |
| 2 | `texts` | Recent threads list; no errors leaking secrets |
| 3 | `read texts from <one thread>` | Ordered excerpts; no model call for content |
| 4 | `draft reply to <thread>: <body>` | Card pending; confirm message shown |
| 5 | Send `hello` unrelated | Draft still pending; nothing sent |
| 6 | Send bare `yes` | “Nothing sent” style message |
| 7 | Copy exact `yes wbtxt-…` from card in **separate** message | On current production Andrea: **Not sent.** receipt, audit only — expected |
| 8 | Settings → Voice / Jobs tabs | Still match `dcc2c8e` parity (jobs cards, build identity) |

When Andrea adds `/web-bob/send` (or successor) with owner binding, repeat step 7 on a staging fixture with `enable_web_bob_send` before enabling on live.

## Risks / follow-ups

- Production send remains **off** until Andrea contract matches Bob the Bot’s owner approval surface.
- BlueBubbles reads still use the server’s query-parameter password contract; errors are scrubbed in UI.
- Playwright browser proof is optional CI/local tooling, not required for unittest green.

## Changed files (this commit)

- `webchat/texting.py`, `webchat/texting_fixture.py` — mock Andrea deliver probe + fixture send route  
- `webchat/test_texting.py`, `webchat/test_texting_e2e.py` — regressions and HTTP E2E  
- `webchat/texting_proof.py`, `webchat/browser_texting.cjs`, `webchat/static/app.js` — proof and UI sent state  
- Rebase merge: `webchat/app.py`, `webchat/static/index.html`, `webchat/static/style.css` (on `dcc2c8e`)
