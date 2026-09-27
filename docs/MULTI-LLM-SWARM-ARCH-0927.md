# Same-project integration policy — trimmed draft, 2026-09-27

Reuse existing execution and integration tools; we only own the project policy
that those tools must satisfy. This supersedes the original eight-point swarm
proposal and the implementation in `c027334`.

The basis is [SWARM-RESEARCH-0927.md](../../../conductor/reviews/SWARM-RESEARCH-0927.md):
the executive summary, §8 novelty assessment, §9 P0 ranking, §10 protocol, and
§11 reuse/build split. That report lives in the adjacent conductor checkout;
it is a dated research input, not a claim that every host feature is configured.

## Reuse X; we only own Y

| Responsibility | Reuse | Project-owned gap |
| --- | --- | --- |
| Isolated attempts | Git worktrees and `services/workspaces.py`; Cursor worktrees/Projects when selected | Require immutable attempt inputs and declared runtime resources |
| Jobs, retries, processes, screens | Existing `jobs.py`, `dispatch_worker.py`, `command.py`, `runtime.py`, `job-runner.sh` | Fenced integration authority over path/resource scopes in `leases.py` |
| Task planning and role selection | Existing conductor jobs and chosen harness planner | Versioned task packages, invariants, dependency invalidation and pinned acceptance configs in `task_contracts.py` |
| Candidate construction, ordering, conflicts and ref advancement | GitHub merge queues or GitLab merge trains, where enabled | Exact-candidate evidence and project policy validation in `integration_policy.py` |
| Model transport and review execution | Existing `lanes.py`, `api.py`, `reviewer.sh`, `pr_evidence.py`, `result_acceptance.py` | Effective identity allowlist; different-creator review across every contributing writer |
| Status and user interface | Existing jobs journal, screens, `live_status_snapshot.py`, `worker_activity.py`, Jobs/Status views | No additional board or Web Bob state source |

Git worktrees isolate files; the existing runner must also isolate or allocate
ports, databases and artifacts. Cursor Projects is an optional planner/harness,
not a new control plane to reproduce here. The research supports these reuse
choices; it does not establish Jeff's current host plan or enable a merge queue.

## Retained P0 modules

- **Leases:** one SQLite ledger per repository/project, atomic all-scope grants,
  durable generations and unique fencing tokens, bounded heartbeat/expiry,
  explicit recovery receipts, and rejection of stale authority. Expiry blocks
  submission; ownership stays reserved until the runner reconciles the attempt.
- **Contracts:** schema/version, owner, goal, invariants, paths, shared resources,
  content-addressed dependencies and separately controlled test/eval/acceptance
  configurations. Changing a contract invalidates its descendants' evidence.
- **Integration policy:** a required-check validator over the host's exact train
  base, submission head, candidate commit/tree, contract, policy, lease and author
  set. Every check and review binds that envelope; stale or incomplete evidence
  fails closed. Effective model, creator, provider and harness are distinct.

These are small importable modules. They add no daemon, scheduler, worktree
manager, resolver service, merge executor, model client, deployer or board.
The removed local train is not retained as a second queue implementation.

## Authority and remaining wiring

A trusted runner/CI adapter must supply observed Git identities and both sides of
renames, authenticated check/review receipts, complete writer provenance and
operator-controlled contracts/policy. Workers must not write the lease database,
replace acceptance suites, or manufacture receipts. Unknown nested routing fails
closed; Grok/xAI cannot satisfy the policy. Different-creator review is a policy
constraint, not proof of independent reasoning.

The hosting service owns candidate construction and atomic integration. Configure
this validator as a required check on the actual merge-group/train candidate,
rebuild on train movement, and invalidate/re-run on policy or contract changes.
Do not transplant a pass to a rewritten or squash commit. If the host cannot
supply/enforce that identity, keep integration blocked rather than inventing a
local merge queue.

This draft does not wire a host adapter or change branch protection, scheduled
jobs, webchat or deployment. It validates the owned policy locally; it does not
claim active enforcement in existing jobs. Native queue setup and trusted receipt
transport are prerequisites for enabling a future pilot, not implemented services.
See [SWARM-V1.md](SWARM-V1.md) for the module contract and tests.
