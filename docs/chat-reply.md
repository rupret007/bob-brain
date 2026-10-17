# Chat reply delivery (idempotent retry)

`ChatReplyJournal` records one outbound assistant reply per stable `reply_id` inside a
conversation. Callers supply the id so a interrupted transport can resume without
posting a second visible message.

States:

- `queued` — registered, not yet sent
- `in_flight` — transport dispatched; outcome unknown (no automatic resend)
- `failed_retry` — last attempt failed; `next_retry_at` gates the next try
- `delivered` — receipt stored; retries return the same receipt
- `failed` — bounded attempts exhausted

Runtime wiring into Web Bob chat remains integration work on a later branch.
