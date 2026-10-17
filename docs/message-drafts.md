# Message drafts (text and email)

Outbound texts and emails are local private drafts with exact payload, account,
conversation, revision, expiry and digest. Web Bob presents the draft through
`present_draft`; transport is forbidden until Jeff's consent card verifies the
current digest. Edits bump revision and invalidate prior approvals.

`execute()` accepts only `trigger="explicit_approval"`. Routines, timers,
background jobs and automations must not call it. Writes stay disabled until
Jeff separately enables scopes; no Andrea or Gmail live paths are modified here.

Tests use injected dispatch callbacks, SQLite restart semantics, stale-edit
rejection, missing consent, and forbidden automatic triggers.
