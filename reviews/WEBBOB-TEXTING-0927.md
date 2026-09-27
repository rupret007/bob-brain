# Web Bob texting — 2026-09-27

**Read, extractive summaries, reply draft cards, and exact chat consent: PASS with mock messaging. Outbound delivery: BLOCKED. Texting parity is not complete.**

Branch: `draft/webbob-texting-0927`, remote `brain`, DRAFT PR base
`draft/webbob-clean-0927` at `0804021ac249db4ab0054e849a7dab199ef3a5e4`.
All code changes and proof artifacts belong to this worktree. No live service
was called, restarted, reconfigured, or deployed. No real text was sent.

## Andrea bridge finding

Read the requested `conductor/reviews/WEBBOB-PARITY-0927.md` first from the parent
checkout; this worktree contains the conductor repository at its root.
The brief proposed an approval-gated Andrea control handoff, but the actual
installed source **and compiled code** explicitly prohibit it:

- `~/Andrea_NanoBot/src/bluebubbles-control-server.ts:1142` returns HTTP 410
  (`direct_bluebubbles_send_retired`) for `/v1/bluebubbles/send`.
- The same source at lines 701–714 and 1155–1177 rejects message-action
  `send` and `send_again`. It requires a fresh owner-authored approval from
  registered Telegram or the configured Messages self-thread.
- `~/Andrea_NanoBot/dist/bluebubbles-control-server.js:523,861,875,881`
  has the same restrictions. There is no ordinary recipient/body draft-creation
  endpoint in this control API. Its other operations can post real Messages
  confirmations, so they were not used as a draft relay.
- The owner cockpit source was also inspected; it does not provide a Web Bob
  text-send bridge. No Andrea files were changed or executed.

A valid separate Web Bob yes therefore records local consent, consumes the
token, and returns **“Not sent.”** It makes no outbound call, queues no delivery,
and is never retried. There is no fake success adapter or assumed send endpoint.
Web Bob cannot manufacture Andrea's independent owner-chat approval by
translating a yes into a synthetic `send it` message.

Completing delivery requires a separately approved Andrea contract that accepts
this authenticated chat as an owner surface, presents/binds the exact recipient
and body, independently checks fresh approval, and returns an idempotent delivery
receipt. That change is outside this worktree and the user's authorized scope.
The parity brief's deployment/human-verification gates remain untouched. This
PR does not claim a real delivery E2E pass.

## Configuration found on this mini

| Component | Configuration | Findings |
| --- | --- | --- |
| BlueBubbles | `~/Library/Application Support/bluebubbles-server/config.db` | Exists; `socket_port=1234`; password present. Read-only SQLite inspection of those keys only. |
| Andrea | `~/Andrea_NanoBot/.env` | Control API enabled; host `127.0.0.1`; port `4315`; base URL `http://127.0.0.1:4315`; bearer token present. Credential values were not printed or copied. |
| Web Bob read adapter | `BOB_BLUEBUBBLES_CONFIG_DB` or BlueBubbles' default config path | Loads only password/port with SQLite `mode=ro`. No `chat.db`, Messages scripting, or Andrea filesystem access at runtime. |
| Optional Andrea status | `BOB_ANDREA_CONTROL_URL` and `BOB_ANDREA_CONTROL_TOKEN` | Only authenticated `GET /health`; no new credentials provisioned and no live status call made. Missing credentials yield an honest configuration message. |

Runtime secrets stay server-side. HTTP errors omit URLs, credential values and
response bodies. Loopback requests disable proxies and redirects, time out after
five seconds, cap the response at 2 MiB, and use an explicit operation allowlist.
BlueBubbles' `POST /api/v1/chat/query` is a **read query**, not a message send;
thread history uses `GET /api/v1/chat/<encoded-guid>/message`.

## Behavior implemented

- **Texts chip / chat reading:** `texts`, `read texts from Alex Morgan`,
  `summarize texts from Alex Morgan`. Lists up to 20 of the 200 recent threads;
  reads at most 30 messages. Summaries are local counts, time windows and recent
  quoted excerpts, not model-generated interpretations.
- **Recipient selection:** exact GUID, address, full name or unique name match.
  Ambiguous names and duplicate SMS/iMessage threads require an exact choice.
  Missing recipient addresses block drafting. Cards show name, all addresses,
  and thread GUID.
- **Draft composition:** `draft reply to Alex Morgan: I’ll bring the charts at 6.`
  preserves the supplied body. `send a text to …` also creates only a draft.
  Requests without a body ask for the text; this lane does not generate a reply
  through a model. Worker/job-prefixed texting requests cannot bypass the gate.
- **Separate yes:** the owner submits the exact `yes wbtxt-…` from the card in a
  later chat request. The button only fills the composer. Bare yes/ok/send-it,
  embedded approvals, wrong tokens, other conversations/logins, or tampered
  recipient/body/revision cannot confirm.
- **Expiry and edits:** five-minute token, bound to the draft, conversation,
  authenticated login and process epoch. Edit clears the server token before
  opening fields. Reviewing changes creates a new card/token. Failed/ambiguous
  edits also withdraw consent. Cancellation, replacement, unrelated turns,
  logout and restart invalidate approval. Old cards display their current state.
- **Durability:** successful consent consumption and its exact recipient/body,
  revision, fingerprint, owner-session identity, timestamp and request ID are
  persisted before a result. Conversation files remain mode 600 in a mode 700
  directory. Duplicate/replayed/concurrent confirmations create one audit event.
- **Privacy:** message contents render as plain text. Text exchanges, draft
  state, recipients and confirmation tokens are omitted from model context and
  the shared handback ledger. Existing coding holds/resume behavior remains
  intact after texting.

## Verification

Final checks ran on the rebased implementation:

| Check | Result |
| --- | --- |
| `python3 -m unittest discover -s webchat -p 'test_*.py'` | **213 passed**, 24.635 s; includes **23 new texting tests** |
| `python3 -m unittest discover -s services -p 'test_*.py'` | **111 passed**, 3.628 s |
| `node --test webchat/test_quiet_hours_js.mjs` | **1 passed** |
| `node --check webchat/static/app.js` and `node --check webchat/browser_texting.cjs` | Passed |
| `python3 bootstrap.py check` | `syntax: PASS` |
| `git diff --check` | Passed |
| Isolated browser / HTTP proof | Passed, 5 screenshots, zero browser errors |

No skipped tests. Test output mentioning `restarted svc-reviewer` comes from
mocked service tests; it is not a live restart. The existing tests also emit
expected Git diagnostics from temporary non-repository fixtures.

The texting tests use a mock BlueBubbles HTTP server and synthetic SQLite config;
they never load the real config or call a real messaging listener. They exercise
actual HTTP reads, errors, redirect rejection, proxy isolation, authentication,
CSRF, login binding, duplicate requests, expiry, restart, edits, recipient
ambiguity, concurrent consent and persistence failures. Mock Andrea checks cover
authenticated health and honest reporting of the unsupported send bridge.

Logs: [webchat suite](WEBBOB-TEXTING-0927.webchat-tests.txt),
[service suite](WEBBOB-TEXTING-0927.services-tests.txt),
[browser result](WEBBOB-TEXTING-0927.browser.txt).

## Isolated server and screenshot evidence

Final browser proof: **2026-09-27 19:29:36–19:29:40 UTC**.
Web Bob bound `127.0.0.1:65108`; mock messaging bound `127.0.0.1:65107`.
It used a new private data root inside this worktree's `reviews/`, the real
login form, CSRF-protected chat API, actual frontend, and synthetic contacts.
The proof closed both of its listeners and removed its temporary state afterward.

The browser read a thread summary, reviewed an exact draft, edited 6 to 7,
verified the first token no longer worked, explicitly submitted the new yes in
chat, observed “Not sent,” and reloaded to verify consumed consent remained
consumed. Phone rendering passed the horizontal-overflow check at 390 × 844;
desktop rendering used 1100 × 1000. Screenshots were visually inspected.

- [Phone: thread summary](WEBBOB-TEXTING-0927-phone-summary.png)
- [Phone: recipient/body draft](WEBBOB-TEXTING-0927-phone-draft.png)
- [Phone: revised draft](WEBBOB-TEXTING-0927-phone-revised.png)
- [Phone: not-sent receipt](WEBBOB-TEXTING-0927-phone-not-sent.png)
- [Desktop: confirmed here, not sent](WEBBOB-TEXTING-0927-desktop-confirmed-not-sent.png)

[Machine-readable evidence](WEBBOB-TEXTING-0927.evidence.json) records source
SHA-256 hashes, mock requests, browser checks, and the synthetic consent audit.
It reports **zero model calls, zero queued jobs, zero send attempts**. The only
messaging requests were four chat-read queries and one thread-history GET.

Read-only listener snapshots were identical before and after: live Web Bob
PID **99149** on 8787, BlueBubbles PID **926** on 1234, Andrea PID **66987** on
4315. No signal, service control command, deployment, merge, undraft or
force-push was used.

Reproduce with an existing Playwright/Chromium installation:

```sh
BOB_PLAYWRIGHT_MODULE=/path/to/node_modules/playwright \
BOB_CHROMIUM_PATH=/path/to/Chromium \
python3 webchat/texting_proof.py
```

The runner rejects the known live ports for the browser target and intercepts
browser requests outside the isolated origin. Evidence contains synthetic data
only; confirmation tokens pictured in screenshots are inert after fixture cleanup.
