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

Acceptance, correction and forgetting use `AcceptedWriter` in the trusted host.
Its required verifier binds the operation, complete fact, visibility, provenance
and expected revision to an existing memory-approval receipt. Wire the existing
memory/project-context approval handler here; never expose writer methods as
unrestricted model tools. The service does not replace the approval UI or accept
an `accepted=true` assertion from a model. Revision comparison rejects stale
changes. Content classification and source origin must be supplied by trusted
adapters; regex checks are defense in depth, not a content classifier. Texting,
conversations, credentials and raw voice are forbidden ingress categories.

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
host configuration and must not be supplied by an MCP caller.

Run `import_day_one(store, repository_root, manifest)` from the trusted setup
command after provisioning the coord database. Tests use a temporary database;
production coordination and Andrea's internal database remain untouched.

## Evidence and integration boundary

The test suite covers four-bot corrections, stale approval rejection, forgetting,
private-source exclusion, audience enforcement, independent ACKs, restart replay,
completed-effect deduplication, uncertain-response handling, both memory roots,
source drift and the actual MCP tool schema. Run sequentially under the mandated
load gate with `nice -n 10 python -m unittest discover -s tests -p
'test_shared_context.py' -v`.

Repository main lacks the runtime provider, memory store and ledger modules.
Connecting their existing acceptance/receipt callbacks and replacing prompt
snapshot assembly remain integration work against a selected runtime baseline.
No production import, four-runtime synchronization, automatic wake-up, or live
Andrea exchange is claimed by these component tests.
