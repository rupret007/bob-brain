# Chat reply delivery (idempotent retry)

`ChatReplyJournal` records one outbound assistant reply per stable `reply_id` inside a
**Bob chat** conversation (`bob-chat:<thread>`). Callers supply the id so an interrupted
transport can resume without posting a second visible message. The transport adapter always
receives `(reply_id, body)` so the upstream channel can dedupe on the same idempotency key.

States:

- `queued` — registered, not yet sent
- `in_flight` — transport dispatched; concurrent callers wait until the lease expires
- `failed_retry` — last attempt raised `ReplyNotSentError` or the transport hung past the send timeout; `next_retry_at` gates the next try
- `uncertain` — the message may already be visible; receipt is `uncertain:<reply_id>` and no further send is attempted
- `delivered` — transport returned a non-empty receipt
- `failed` — bounded `ReplyNotSentError` attempts exhausted

Retry policy: only `ReplyNotSentError` and send timeouts (before the adapter runs) schedule another attempt. Adapter failures that may have posted, empty receipts, stale `in_flight` leases, and `CancelledError` surface `uncertain` so a visible message is never duplicated.

Runtime wiring into Web Bob chat remains integration work on a later branch.
