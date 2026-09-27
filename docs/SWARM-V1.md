# Swarm draft: thin policy module contract

The original v1 planner/train/board is removed. Reuse Git worktrees, the existing
conductor runner/screens/reviewers/status views, and native GitHub/GitLab queues;
we only own `leases.py`, `task_contracts.py` and `integration_policy.py`.
The [trimmed architecture](MULTI-LLM-SWARM-ARCH-0927.md) maps each responsibility
and points to [SWARM-RESEARCH-0927.md](../../../conductor/reviews/SWARM-RESEARCH-0927.md),
especially §8–§10. Existing job/review acceptance continues to use
`result_acceptance.py`; it is not replaced by the integration gate.

## Fenced leases

```python
from services.leases import LeaseStore

leases = LeaseStore(conductor_path, "webbob", repository_path)
lease = leases.claim("attempt-one", ["webchat/reply_authority.py"],
                     shared_resources=["webbob-test-db"], ttl=300)
leases.renew("attempt-one", lease["token"], ttl=300)
with leases.guard("attempt-one", lease["token"]):
    pass  # Short, trusted acceptance operation; never run an agent/CI job here.
leases.release("attempt-one", lease["token"])
```

Use one project ID per repository and one coordinator host/time authority.
`leases/<project>.sqlite3` holds only integration ownership, not jobs or status.
SQLite transactions serialize all-scope grants; committed generations increase
and tokens change on reacquisition. Case/Unicode aliases, subtrees and named
exclusive resources conflict conservatively. Traversal, globs, Git metadata and
symlink aliases are rejected. The caller supplies a real repository path when
checking filesystem aliases. All runtime databases are ignored by Git.

TTL is at most one hour; renewal cannot extend a grant beyond 24 hours from its
creation. A lease guards integration authority, not OS writes. Worktrees and
runtime isolation remain the existing runner's responsibility. Best-of-N attempts
can compute in isolated worktrees under one logical task; only the selected
attempt receives the integration grant. These leases are separate from existing
model-lane capacity locks.

An expired grant cannot renew, release or submit. It still blocks conflicting
grants until the runner stops/quarantines the old attempt and supplies an observed
recovery receipt: `leases.recover(owner, token, receipt="runner/observed-stop")`.
Recovery is idempotent for that receipt; a fresh claim gets a new fence. Committed
grants and recovery survive restart; interrupted transactions roll back. Inspect
`list()` after a lost response and resume only the verified owner. There is no
implicit lease stealing, workspace deletion or separate recovery daemon.

Legacy `leases/<project>.json` causes a refusal. Reconcile its writers and archive
it explicitly before opting into SQLite; there is no automatic migration that
could grant duplicate ownership. Keep the database private to the coordinator.
Never restore an old ledger while workers retain authority.

## Versioned task packages

`task_contracts.contract_id(contract)` validates a JSON-compatible package and
returns its SHA-256 identity. Required fields are:

| Field | Meaning |
| --- | --- |
| `schema`, `version`, `task`, `owner` | Schema 1, positive revision, task ID and responsible owner |
| `goal`, `invariants` | Nonempty goal and behavioral invariants |
| `paths`, `resources` | Canonical exclusive paths and named runtime resources |
| `dependencies` | Task ID → immutable contract digest, including semantic read dependencies |
| `checks` | Check ID → trusted suite/config digest; includes `tests`, `evals`, `acceptance` |

`require_current(contract, current_contracts)` checks the current task and all
transitive dependency pins. Missing or superseded packages block acceptance.
Store immutable packages in the existing job artifacts or reviewed configuration;
this library creates no new task registry. A change proposal must bump the version,
receive separate review and replace the authoritative current package. Suspend
and rebase/restart affected work, then regenerate its evidence. The digest also
invalidates evidence if someone edits content without bumping the version.

Independent acceptance definitions come from trusted configuration outside worker
control. Pin their contents and execution environment, not just a command name.
Changes to the evaluator cannot approve the same patch that weakened it.

## Exact-candidate gate

`integration_policy.authorize(candidate, contract=..., current_contracts=...,
policy=..., checks=..., review=..., leases=..., current_train_sha=...,
current_source_sha=...)` raises `ValueError` on rejection. On success it returns
`accepted`, the exact candidate `sha`/`tree`, and `binding=digest(candidate)`.
The executable fixture in `services/test_integration_policy.py` shows complete
input records and a disjoint-file semantic regression.

The candidate envelope contains `project`, `task`, `attempt`, `source_sha`,
`train_sha`, `sha`, `tree`, `contract`, `policy`, `lease_owner`, `lease_token`,
`authors`, `provenance_complete`, and host-observed `changed_paths`. Every receipt
binds the entire envelope, including authorship and the lease fence. Observe
both rename endpoints and the final candidate delta; never trust worker paths.

The policy specifies schema/version, exact `identities`, `check_issuers`,
`review_issuers` and a pinned `review_config`. An identity records actual `model`,
`creator`, `provider`, `harness`, and `harness_version`. Include delegated writers
and resolvers; unknown provenance, forbidden Grok/xAI and unlisted fallbacks fail.
Reviewer model/creator must differ from every writer, regardless of harness.

Each required check has exactly one receipt with `check`, `config`, `binding`,
`passed: true`, trusted `issuer`, `environment` and an `artifact` reference.
A review supplies `binding`, `config`, trusted `issuer`, effective `identity`,
`provenance_complete: true` and `approved: true`. Strings or integer truth values
are not approvals. Missing, duplicated, red, stale or untrusted receipts fail.

These records are not cryptographic attestations. The adapter authenticates the
issuer and observes Git/state; the validator enforces the acceptance rules. Run
checks with the existing runner/CI and reviews with the existing reviewers.
The host queue performs the ref update and invalidates obsolete candidates.
Publishing the validator as a required check and invalidating contract/policy
changes remain explicit prerequisites; no active host adapter is included here.
No module merges, pushes, rewrites branches, changes PR draft state or deploys.

## Validation

Run the existing service and webchat unittest discovery suites. New tests cover
cross-process lease races, rollback after a killed transaction, restart recovery,
fence/expiry rejection, contract/dependency changes, exact evidence, independent
review and semantic acceptance. Reuse `webchat/bob_parity_eval.py:run_eval` for an
offline fixture and require all cases to pass; the removed wrapper added no suite.
All tests and parity fixtures must use private state with no live model calls.
On macOS, keep temporary repositories outside the tested source tree so the real
sandbox write boundary can distinguish allowed workspaces from protected code.
