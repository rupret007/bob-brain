Web Bob can now read the verified Instinct thread, show its latest replies, flag possible bills/deadlines, security items, and appointments, and prepare explicit or suggested reply drafts. For example, `digest Instinct` returns dated source excerpts; `send a message to Instinct: ...` creates an unsent card.

The feature reuses BlueBubbles-first reads and the existing draft → separate exact yes → Andrea fence. Recipient ambiguity fails closed. Incoming messages stay untrusted and out of provider context; no auto-reply, watcher, or task dispatch was added. Suggested drafts use local templates and show the exact tagged body for review.

Validation on `c51860cc36be4c44be722ba8175095b625666c4f`:

- Web Bob: 411 passed, 1 existing optional Playwright skip; services: 131 passed.
- Instinct: 31 regression tests and 22/22 eval cases; total Bob parity: 118/118.
- JavaScript checks, Python compilation, and branch whitespace checks passed. All messaging uses synthetic loopback fixtures, including the approved-delivery case.
- [Validation details and logs](https://github.com/rupret007/bob-brain/blob/c51860cc36be4c44be722ba8175095b625666c4f/reviews/INSTINCT-0810-VALIDATION.md).

Offline FIXED/READY markers are in the shared conductor/reviews directory. Fresh LIVE Gemini (gemini-2.5-pro) and MiniMax (MiniMax-M2.7) code reviews both returned PASS for this exact SHA. `GATE: BOTH_PASS`; the full responses and `INSTINCT-LIVE-0810.md` are retained in the shared conductor/reviews directory. The real Instinct mapping/connectivity and real delivery were not tested. Digests are bounded keyword summaries, and attachments are not analyzed.

**Draft only — do not merge or deploy.** Deployment is out of order: texting must go LIVE first, then gaps/media/voice/UI. No real iMessage/SMS or Jeff notification was sent. No production service or pin changed.
