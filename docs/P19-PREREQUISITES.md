# P19 prerequisite check — blocked

P19 is not implemented. No deployment or live Gmail availability is established.
The task requires a verified P9 mapping and corrected read/privacy contract
before building the local reply-draft feature.

Local evidence checked on 2026-10-11:

- `cloud-prs.txt` still maps P9 to `PR97?`; no definitive PR-number evidence
  was found locally. Network verification is prohibited for this lane.
- The P9 task identifies `draft/webbob-parity-p9-cloud`. Its locally available
  remote-tracking tip is `767453b6fa51176b8375029bcb8fe2a3cbe4f985`, following
  implementation commit `44d72ae8c35d4882f90d54b5b9335f78396f86e6`.
- Neither commit is in this worktree's starting capability stack,
  `71c4a6d`. The local Gmail file history contains no subsequent privacy fix.
- `P9-cloud-review.json` reports **FAIL**: private mail reaches the voice model;
  unnamed attachments are displayed, and `format=raw` downloads MIME attachments.

Validation used a temporary application of the exact P9 dependency diff in
this worktree. All imported source changes were removed after the checks.

- `TMPDIR=/private/tmp python3 -m unittest discover -s webchat -p 'test_gmail_read.py'`:
  **24 tests passed**. This result does not resolve the review findings.
- An offline `EmailMessage.add_attachment(..., subtype='plain')` fixture with
  no filename reproduced attachment text in `GoogleGmail.message()['text']`.
  The mocked transport observed `format=raw`. Authentication was mocked too.
- Executing `BobVoice.prototype.tool` with mocked persistence, API, and socket
  operations reproduced private mail text in its outgoing `toolResponse`.

No real credentials were read; no network, provider, notification, send, push,
or full-suite operation ran. Product source and protected files remain unchanged.

Resume when the P9 source/PR mapping is confirmed and its reviewed privacy fixes
are available for integration (or the owner explicitly revises that prerequisite).
Then implement and test P19's conversation-bound local-save consent, deduplication,
hold checks, private storage, and exact recipient/body preview. Existing owner
authorization for `gmail.readonly` remains the intended setup; no scope expansion
or Gmail write/send endpoint belongs in P19.
