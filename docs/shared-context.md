# Shared accepted context and teammate inbox (P2)

One coord-owned SQLite store supplies current accepted facts to Bob, Web Bob,
Andrea and Karen. It uses SQLite's transactions and the official MIT MCP SDK;
it preserves the candidate project-context rules: facts are not permissions,
corrections replace prior bodies, forgetting hides prior revisions, and receipts
remain distinct from fact revisions. No additional memory engine is installed.

The trusted launcher binds `WEBBOB_BOT_ID` and `WEBBOB_CONTEXT_DB`, then starts
`python -m webbob.context_mcp`. Install `requirements-context.txt` in Python 3.11.
One stdio server per bot shares the same database. OS-level identity is trusted;
models cannot select the sender, recipient cursor, acceptance verifier, or DB.

The MCP surface reads accepted facts, prepares unpersisted proposals, posts
typed notifications referencing accepted facts, reads the bound bot's inbox,
and acknowledges its messages. No raw message body is accepted. Notifications
resolve references at read time, so corrections/forgetting also affect old inbox
messages. Each bot has independent durable acknowledgments. There is no wake-up
daemon in this PR; bots must poll their own inbox.
Each recipient has a cap of 1,000 pending notifications across all senders.
Insertion checks the cap in the same transaction; identical retries remain
idempotent even at capacity. Acknowledgment frees capacity. Completed/acknowledged
history remains durable and is not deleted by this pending-inbox cap.

Acceptance, correction and forgetting use `AcceptedWriter` in the trusted host.
Its required verifier binds the operation, complete fact, visibility, provenance
and expected revision to an existing memory-approval receipt. Wire the existing
memory/project-context approval handler here; never expose writer methods as
unrestricted model tools. The service does not replace the approval UI or accept
an `accepted=true` assertion from a model. The verifier must return
`VerifiedAcceptance(accepted_by, accepted_at)` derived from the authenticated
receipt/principal. A boolean success fails closed. Caller acceptance labels are
covered by the payload digest but overwritten with these verified values before
storage; a candidate cannot nominate its own approver or acceptance time.
Revision comparison rejects stale changes.

Ingress rejects SMS/text markers, phone numbers, credentials (including AWS and
Slack token families), audio data URIs, raw/encoded audio indicators, and send
approval assertions even if a caller labels them `accepted_fact`. Checks normalize
Unicode and also cover persisted provenance. Errors name only the denied category,
never the payload. These conservative guards supplement trusted source
classification: unmarked conversation content cannot be reliably classified by
patterns, so trusted adapters must still exclude conversations, texts and raw
voice at their source. Shared facts cannot carry send consent.

`begin_effect` and `complete_effect` are host-only receipt operations. Persist
uncertain before dispatch, preserve the transport receipt, then ACK. Completed
effects do not repeat after restart. Lost responses remain uncertain and require
reconciliation. This service does not authorize any effect; ownership and exact
send approval remain separate prerequisites. Existing ledger receipts should be
referenced by stable receipt ID, never copied with private payloads.

## Day-one Grok Bot import

`config/day-one-facts.json` explicitly selects two accepted profile facts: Jeff's
GitHub identity from `memory/profile.md` and Logic Pro preference from
`user-memory/.../profile.md`. It records exact line, hash and accepted text; the
import validates all three and records source provenance. It never scans logs,
copies whole documents, or imports historical permissions. Repeating import
does not overwrite later corrections or tombstones. The manifest is reviewed
host configuration and must not be supplied by an MCP caller. Selection and
hash matching alone do not authorize storage. Each item must carry a `receipt`
reference from independent review of the exact put payload; the checked-in
manifest contains no approvals. Lines must be integer indices within the document
(starting at one). Import never creates or verifies its own acceptance receipts.

Run `import_day_one(store, repository_root, manifest, verify_acceptance=verifier)`
from the trusted setup command after provisioning the coord database and obtaining
the independent receipts. Missing/invalid verification fails closed. Tests use a temporary database;
production coordination and Andrea's internal database remain untouched.

## Evidence and integration boundary

The test suite covers four-bot corrections, stale approval rejection, forgetting,
private-source exclusion, audience enforcement, independent ACKs, restart replay,
completed-effect deduplication, uncertain-response handling, both memory roots,
source drift, each denied content class, forged acceptance provenance, inbox
capacity, independent import approval, line bounds and the actual MCP tool schema.
Run sequentially under the mandated
load gate with `nice -n 10 python -m unittest discover -s tests -p
'test_shared_context.py' -v`.

Repository main lacks the runtime provider, memory store and ledger modules.
Connecting their existing acceptance/receipt callbacks and replacing prompt
snapshot assembly remain integration work against a selected runtime baseline.
No production import, four-runtime synchronization, automatic wake-up, or live
Andrea exchange is claimed by these component tests.
