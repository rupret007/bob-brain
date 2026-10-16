# Draft PR operations and Karen's exact-commit gate (P5)

Reuse the official MIT `github/github-mcp-server` v2.0.2. Its read-only instance
supplies PR metadata/diffs and file reads; only the trusted publisher instance
advertises `create_pull_request`. Configure both with the tool lists in
`config/github-mcp.json`; never expose that mutation instance directly to models.
No credential is installed or copied by this change.

`ReviewGate.request_review` creates a stable request bound to repository, PR,
full SHA, scope and evidence references. The supplied inbox callback must use the
P2 shared service's idempotent addressed message/receipt adapter, not a direct
email or chat. Pending delivery survives restart and can be replayed by ID.
The runtime adapter needs a reviewed artifact-reference ingress into P2; this
standalone branch does not pretend that wiring already exists.

Karen verdicts require an authenticated receipt verifier with no allow-all
default. The receipt covers every field, including request identity, evidence,
scope, SHA and expiry. The trusted Karen lane must independently review that
commit; Web Bob cannot manufacture a receipt by reading an old QA file. A later
commit makes the verdict stale. A later FAIL supersedes an earlier PASS.
Only configured trusted receipt ingress may call `record_verdict`.

`merge_readiness` requires Karen PASS for the CURRENT remotely observed SHA and
Jeff's standing approval scoped to the repository/action. The trusted caller
must obtain that SHA from GitHub immediately before assessment. The result is
an assessment for Jeff: Web Bob remains draft-only and has no merge/undraft
method, even after both checks pass. No approval is inferred from this PR.

Draft publication requires a current protected ownership context, fresh remote
branch SHA and exact publication approval, then creates only a draft against
main and verifies remote draft state/SHA. A failed/lost response returns
uncertain. A required private SQLite receipt store records uncertainty before
transport. Restart and repeated calls return that receipt without another
create; changed payloads on the same branch require reconciliation. The existing
draft publisher must reconcile through remote reads before any manual recovery.
No force push, rebase, issue mutation or merge operation is introduced.

Tests cover stale commits, forged/old QA receipts, scope/evidence binding, latest
FAIL, inbox replay, Jeff approval, expired lease, changed branch and draft-only
creation. They use fake upstream transport with real durable review storage.
Runtime `draft_publish`, `pr_evidence`, teammates and UI code are absent on main;
callbacks and UI binding remain integration work. Tests do not claim a real
Karen PASS or production release authorization.
