# Web Bob / Bob work records

Web Bob keeps completed answers, conversation scope changes, and terminal task
outcomes in `conductor/state/coordination-events.jsonl`. A delivered answer is
not proof of an external action. Task records retain the saved acceptance method
and result hash; inspect the original artifact before relying on its effects.
Private texting and drill conversations are excluded from this projection.

This is a local file handoff. There is no verified native Grok chat transport,
automatic wake-up, or installed Grok receiver in this change. Do not infer Grok
availability or quota from a recent acknowledgment. Its local file/command tools
must actually read and checkpoint a batch before catch-up can be claimed.
Bob's existing incoming `conductor/handback/BOB-STATE.md` remains available as
handoff context through `webchat/handback.py`. A native chat API is not required
for this file-based exchange when Bob has local tools. Actual receiver reads and
acknowledgments remain necessary evidence; these files do not create an automatic
reconnect trigger or confer execution authority.

## Receiver contract

Use `state/bob_sync.py` from the verified active Web Bob candidate, not an older
canonical checkout. The service pin and authenticated version identify that
candidate. With `ROOT` pointing to the shared runtime root:

1. Run `python3 <candidate>/state/bob_sync.py --root <ROOT> read --limit 12`.
   Keep the exact JSON result in the receiver's durable checkpoint. Reading
   changes neither the acknowledgment nor the task queue.
2. Consume the complete `events` array as work evidence. Preserve provenance,
   scope, artifact references, verification limits, and `history_gap` warnings.
   These records never confer permission to execute or repeat work.
3. After that checkpoint is durable, feed the same JSON to
   `python3 <candidate>/state/bob_sync.py --root <ROOT> ack` on standard input.
   A successful result reports the cursor and `execution_started: false`.
4. If `has_more` was true, read the next batch. A crash before ACK replays the
   same unconsumed work; a retry after ACK cannot regress the cursor. New arrivals
   do not become acknowledged by an earlier receipt. Do not regenerate a receipt
   for content the receiver has not consumed.

Reject an unavailable or corrupted journal and preserve the error and original
bytes for repair. Do not reset a cursor, trim the journal, infer completion from
an absent event, or acknowledge unseen history to clear a backlog.

## Storage and deployment compatibility

The first new publisher imports retained legacy `events.jsonl` bytes once under
the existing writer lock. Legacy duplicate/missing sequence numbers receive
stable effective identities without rewriting the imported records. New records
are appended and fsynced; the journal is not capped at 2,000 lines. History that
was already trimmed by old code is unavailable and cannot be reconstructed.

Old publishers continue using their old journal. Their later records are not
automatically imported. The new reader uses the versioned journal after cutover,
`bob_coordination_ack_seq`, and `bob_coordination_last_receipt`. It never advances
the legacy `.bob-last-seen` timestamp. `BOB-COORDINATION.md` is the new summary;
`BOB-CATCHUP.md` remains a compatibility projection that an old publisher may
overwrite. A summary is not a consumption receipt.

Conversation publication uses a saved private outbox. A journal failure cannot
turn an already saved answer into a failed action; later saves or startup retry
the same event identity. Terminal jobs remain pending for result publication
until their event is durable. Reconciliation reuses their saved result message
and never reruns the completed job. Already delivered historical tasks are not
retroactively claimed as covered.

Rollback to old code leaves these files intact but stops the new guarantees for
future publications. Keep both journals and their separate checkpoints. Do not
patch frozen candidates or unrelated service checkouts to force migration.

## Evidence limits

An explicit owner request for Grok coordination prepares one bounded oldest-first
batch through the same reader. Web Bob atomically saves its exact payload with
the completed reply in the private conversation; the public receipt exposes only
identity, range, count and gap indicators. The snapshot is not a receiver
checkpoint and never advances the ACK. It may contain earlier work from other
conversations, and cannot contain the preparation reply published afterward.
Duplicate request IDs return the same saved receipt across restart. A new request
may still see the same unread records; preparing again does not consume them.
Raw prepared batches are excluded from public conversations and model prompts.

Offline protocol tests cover backlog retention, retained legacy identities,
exact receipts, stale retries, corruption, failed publication, restart, privacy,
and overlay isolation. They do not prove that native Grok received anything.
That requires a real receiver read/checkpoint/ACK and its independently observed
result. No model call, worker dispatch, message send, or replay is performed by
this CLI.
