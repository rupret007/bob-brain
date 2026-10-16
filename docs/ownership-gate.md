# Shared ownership gate (P1)

This is a staged successor to `bin/claim-gate.py`, copied from the existing local
gate and retaining its advisory GitHub duplicate checks, lock and append-only
claim directory. It uses the official MIT MCP Python SDK v1 compatibility API.
No live gate, bot, queue, publisher, service, or Andrea deployment was modified.

Install `requirements-ownership.txt` into an isolated Python 3.11 environment.
The trusted launcher sets `CLAIM_GATE_CLAIMS` to the ONE coord claims directory
and `WEBBOB_BOT_ID` to `bob`, `webbob`, `andrea`, or `karen`, then launches
`python -m webbob.ownership_mcp`. This is a local stdio boundary; no HTTP listener
or model-selectable identity is exposed. The OS launcher is trusted. A process
with unrestricted same-user filesystem access can bypass this service.

`claim`, `renew`, `release`, and `get_owner` share the same implementation with
the CLI. Lease TTLs in the API are seconds (1–14400); CLI `--ttl-min` is minutes.
Keep the returned token in private job state. Tokens are hashed in claim files
and omitted from observation. Same branch does not imply same owner. Renewal and
release require owner, token and current fence; expired renewal is rejected.
Resource keys are conservative lowercase `repo:owner/name/path`, `pr:owner/name/1`,
`browser:session`, `outbound:channel/identity`, or `work:owner/name/id`.
Parent resources exclude descendants. A directory resource must be used when a
job may create multiple files there; path aliases must be normalized by trusted
adapters, not accepted from model-generated filesystem paths.

Malformed, unreadable, ambiguous, or unsupported legacy records block the gate.
Records use a persisted sequence, never mtime. Legacy records use their written
created/expiry timestamps; unsupported records require explicit owner-led
migration. Do not delete malformed records to make the gate green. A successful
empty response means a successful read of the full claim history.

## Runtime adoption contract

`Executor.reserve()` supplies the queue job's durable `Ticket`; persist it with
the existing queue claim before dispatch. `Executor.renew()` runs before expiry.
Both dispatcher and worker carry the ticket. At every publication/send/browser
effect the trusted executor calls `Executor.protected(ticket, resource, effect)`.
This validates the current generation immediately before execution and holds the
existing lock through the bounded effect; a prior MCP ownership read does not
authorize later publication. Every callback must have a timeout. Effects started
with a valid lease may finish after its expiry; no successor can acquire until
the lock is released. Network uncertainty still requires the existing receipts.

The Andrea adapter accepts only historical pinned release `83623dd8`; this checks
the declared version, not live compatibility. It does not import or edit Andrea.
All four runtimes must adopt this contract before claiming global exclusion.
An old writer can still bypass token enforcement; conflicting legacy claims deny
execution. Activation must replace legacy writers together, under the release
gate. Repository main currently contains no `state/task_queue.py`,
`services/web_dispatch.py`, `services/dispatch_worker.py`, or draft publisher;
wiring and end-to-end runtime tests remain pending an integration baseline.

## Evidence

`python -m unittest discover -s tests -p 'test_ownership.py' -v` exercises four
simultaneous in-process claim clients, unrelated work, correct and expired
publication callbacks, wrong-owner/token/fence release, renewal, failed reads,
legacy blockers, resource ancestry, metadata-order tampering, and a real MCP
stdio client/server round trip. Tests use private temporary claims, never coord.
The suite runs sequentially; the contention test uses threads solely to exercise
the required simultaneous-claim behavior.
