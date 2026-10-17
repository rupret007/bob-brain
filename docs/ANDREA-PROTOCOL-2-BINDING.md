# Andrea protocol 2: required request binding

Web Bob defaults to the exact integer protocol in `release/andrea-bridge.json`
(currently 2). The private `BOB_ANDREA_WEBBOB_CONFIG` JSON file can explicitly
set `"protocol": 1` for a legacy installation. Embedders/tests can pass
`expected_protocol=1` to `Andrea`. A health response cannot change that policy.
Missing/invalid release policy, malformed configuration, or a mismatching health,
draft or receipt protocol fails closed. Saved legacy drafts cannot send under a
protocol-2 policy.

The pinned Andrea revision `6f1030f9d1b8a8c973ccd3ef4c5cf148669179d1` implements
this binding in `src/web-bob-request-scope.ts` and `src/web-bob-bridge.ts`.
Its `docs/WEB_BOB_BRIDGE.md` specifies `protocol: 2` for owner approval and
`deliveryProtocol: 1` for receipt inspection. These are separate versions;
requiring delivery protocol 2 would reject this reviewed pin. Protocol-1
approval responses remain refused under the release policy.

Andrea includes `requestDigest` (64 lowercase SHA-256 hex characters) in successful
protocol-2 draft responses and in every confirm/cancel/status receipt. This is
separate from the existing `digest` of Andrea's normalized action.

Compute `requestDigest` from the immutable original Web Bob scope, before Andrea
substitutes its own actor or request ID. Serialize these fields in this exact
order, using compact JSON (no separator whitespace), UTF-8, literal Unicode
(`ensure_ascii=False`), JSON escaping for quotes/control characters, and no
Unicode normalization:

1. `issuer`, `audience`, `actor`, `conversationId`, `epoch`
2. `draftId`, `revision`, `draftRequestId`
3. `chatGuid`, `addresses`, `text`

The values must be exactly those in the draft request (including array order and
body whitespace). Addresses in that request are already canonicalized by Web
Bob. `Andrea.scope` and `Andrea.scope_digest` in `webchat/texting.py` define the
reference serialization. Never hash an action with replaced actor/request IDs,
never copy an unverified digest supplied by a caller, and never derive receipt
evidence from the current status/confirm request.

Persist the original scope and its digest with the remote `draftId`, `actionId`,
normalized action digest, and independently delivered approval. The remote ID
must be unique and must never be rebound to another request. Andrea must bind
its owner approval to that same immutable record, enforce single use and expiry,
and reverify its recipient before dispatch. Confirmation sends `bridgeDraftId`, the expected `requestDigest`, and the owner's
`approvalToken`. Cancel/status also send `bridgeDraftId` and `requestDigest`.
Andrea must compare the expected digest against the stored original request
**before consuming approval or dispatching**, and reject a mismatch. A response
with an injected digest must not cause a different remote draft to be sent.
All receipts must attest that record's original `requestDigest`, never a different
request that happens to share an action or recipient. No challenge/approval token
may appear on the service response channel.

Web Bob compares Andrea's `requestDigest` with the exact current request before
accepting a draft, before handoff/recovery, and in receipts. It also retains the
local fingerprint as a separate edit guard. The private
`andrea-draft-ids.sqlite3` file in the Chat state directory reserves remote IDs
atomically across conversations and restarts; failed reservations block approval.
Do not remove this registry to retry an old remote draft. Old protocol-2 records
with only `localDigest` cannot authorize sends or validate receipts.

Responses are decoded with duplicate-key rejection at every object depth, before
schema validation. Only the original, untrimmed `yes wbtxt-<64 lowercase hex>`
chat submission can authorize protocol 2; padding, Unicode lookalikes, extra
prose, and worker prefixes cannot be normalized into consent.

Offline negative checks (no Andrea process or network access):

```sh
PATH=/opt/homebrew/opt/node@22/bin:$PATH python3 release/bridge_probe.py --negative-contract
PYTHONPATH=webchat python3 -m unittest test_proto2_security test_texting.AndreaProtocolTests
```
