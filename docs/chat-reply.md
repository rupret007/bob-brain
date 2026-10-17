# Chat reply delivery (idempotent retry)

`ChatReplyJournal` records one outbound assistant reply per stable `reply_id` inside a
**Bob chat** conversation (`bob-chat:<thread>`). Callers supply the id so an interrupted
transport can resume without posting a second visible message. The transport adapter always
receives `(reply_id, body)` so the upstream channel can dedupe on the same idempotency key.

States:

- `queued` — registered, not yet sent
- `in_flight` — transport dispatched; concurrent callers wait until the lease expires
- `failed_retry` — last attempt raised `ReplyNotSentError`; `next_retry_at` gates the next try
- `delivered` — receipt stored (or `uncertain:<reply_id>` when the message may already be visible)
- `failed` — bounded `ReplyNotSentError` attempts exhausted

Retry policy: only `ReplyNotSentError` schedules another attempt. Timeouts, proxy errors, and
other ambiguous failures mark `delivered` with an `uncertain:` receipt so a visible message is
never duplicated. Stale `in_flight` rows (lease elapsed) are recovered on the next `deliver`.

Runtime wiring into Web Bob chat remains integration work on a later branch.
