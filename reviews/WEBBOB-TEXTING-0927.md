# Web Bob texting evidence — refreshed for the 1841 gate

The browser script, JSON evidence and all five screenshots now prove the same
**blocked “Not sent” path**. Python unit tests and HTTP E2E exercise mock Andrea
success separately. No real text was sent, no live endpoint was called, and no
service was deployed or restarted.

Tested implementation and screenshot build: `e1f9ee1b9292bf9b7d3ec7f53220ceeae95fd14d`.
The following commit adds only evidence and review documents.

This refresh supersedes the earlier 0927 report and screenshots. The draft branch
integrates live baseline `dff84e3`; current changes and test counts are recorded in
`TEXTING-FIXED-1841.md`. The next conductor loop still needs fresh LIVE Gemini and
LIVE MiniMax PASS reviews on the final pushed tip before clearing the deploy gate.

## Delivery and consent

- BlueBubbles access is restricted to thread-list and thread-history reads.
- A send request creates a recipient/body draft. Only the exact `yes wbtxt-…` in
  a later authenticated chat turn can consume consent. Tokens expire after five
  minutes and bind the login, conversation, recipient, body and revision.
- With credentials configured, confirmed consent makes one authenticated
  `/web-bob/send` request to Andrea. The browser fixture returns 404, reproducing
  the unavailable production bridge described in the earlier review. It records
  `owner_confirmed_not_sent`, displays “Not sent,” and performs zero deliveries.
- The success fixture used by HTTP/Python tests explicitly enables the bridge;
  those tests verify “Sent via Andrea,” the sent card and one synthetic delivery.
  This does not establish a working production delivery contract.
- Consumed consent is saved before the bridge handoff, then the result is saved.
  If the result cannot be persisted, the durable card says delivery is unconfirmed
  and cannot be replayed, including after restart. Ordinary texting turns save once.
- Text history and private consent state stay out of model context. Core private
  fields are excluded before the texting projection; returned data is copied.

## Browser evidence

The runner uses synthetic Alex Morgan/Alex Taylor contacts, a new private data
root, a real isolated HTTP server, and two spare loopback ports. It rejects known
live ports and blocks browser requests outside its fixture origin. Its listener
snapshots match before and after, and it closes only its own fixtures.

The flow logs in, uses the Texts button, reads a summary, reviews a draft, edits
6 to 7, rejects the old token, fills the composer without submitting, submits the
new token separately, observes “Not sent,” and reloads to verify consumed consent.
It also checks phone overflow and browser errors. Running it exposed and fixed a
missing `submitChatText` helper used by the Texts and draft-edit buttons.

- [Phone: thread summary](WEBBOB-TEXTING-0927-phone-summary.png)
- [Phone: recipient/body draft](WEBBOB-TEXTING-0927-phone-draft.png)
- [Phone: revised draft](WEBBOB-TEXTING-0927-phone-revised.png)
- [Phone: not-sent receipt](WEBBOB-TEXTING-0927-phone-not-sent.png)
- [Desktop: confirmed here, not sent](WEBBOB-TEXTING-0927-desktop-confirmed-not-sent.png)

[JSON evidence](WEBBOB-TEXTING-0927.evidence.json) contains the actual run times,
fixture ports, source hashes, screenshot hashes, request list and redacted audit.
It records **zero model calls, zero queued jobs, zero mock deliveries and zero real
texts**. The requests are four read queries, one history GET, and one rejected
Andrea bridge probe. [Browser result](WEBBOB-TEXTING-0927.browser.txt) summarizes
that same run. All five screenshots were regenerated; the phone blocked receipt
and desktop confirmed card were visually inspected.

From this worktree root, with the local Playwright installation used for this run:

```sh
PLAYWRIGHT_BROWSERS_PATH="$PWD/webchat/node_modules/.cache/ms-playwright" \
python3 webchat/texting_proof.py
```

An existing runtime can instead be selected with `BOB_PLAYWRIGHT_MODULE` and
`BOB_CHROMIUM_PATH`. `--output-dir <directory>` writes scratch evidence elsewhere;
the optional browser unittest uses its own temporary directory. Synthetic
confirmation tokens pictured here are inert after fixture cleanup.

## Validation records

- [Full webchat suite](TEXTING-1841-webchat-tests.txt)
- [Full services suite](TEXTING-1841-services-tests.txt)
- [Focused texting regressions](TEXTING-1841-targeted-tests.txt)
- [Offline eval evidence and limitations](WEBBOB-EVALS-0927.md)

The `WEBBOB-TEXTING-0927.webchat-tests.txt` and `.services-tests.txt` files are
historical logs; the 1841 logs above are the current verification. Service-test
messages about restarting a reviewer are mocked test output, not live restarts.
