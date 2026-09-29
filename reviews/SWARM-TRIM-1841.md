# Swarm draft trim — 2026-09-27

Completed in `~/Documents/bob-overnight-inject/workspaces/swarm-arch-1730`.
Branch: `draft/swarm-arch-1730`.
Starting tip: `c027334`.
**Pushed tip: `01b97b631c47c346fc824580e98b81ab099d2d79`**.
Remote `brain/refs/heads/draft/swarm-arch-1730` was read back and matches the
local commit. The workspace is clean.

## Research and inventory

Read [SWARM-RESEARCH-0927.md](SWARM-RESEARCH-0927.md), especially the executive
summary, §8 novelty, §9 P0 ranking, §10 v2 protocol and §11 reuse/build split.
The original branch adds one swarm implementation commit, `c027334`, above
`dcc2c8e`: 23 changed files, 1,878 inserted lines and 3 deleted lines.

| Original addition | Disposition |
| --- | --- |
| `planner.py`: assignment lifecycle, fixed model-role routing, resolver jobs and branch creation | Deleted; reuse the conductor job runner and selected harness planner |
| `merge_train.py`: polling/ticks, disposable worktrees, rebase, gate subprocesses, ref advancement and conflict recovery | Deleted; reuse Git worktrees and native GitHub/GitLab queue behavior |
| `project_board.py`, `webchat/swarm_status.py` and five Web Bob status/reply hooks | Deleted/reverted; reuse existing jobs, screens and observed live status |
| `swarm_store.py`: separate JSON persistence/locking helpers | Deleted; use SQLite only for the remaining transactional lease gap |
| `swarm_eval.py`: wrapper around existing parity checks | Deleted; run the existing parity evaluator directly with private fixtures |
| Planner/train/board/status tests and `swarm_test_support.py` | Deleted with the removed framework; retained behavioral policy coverage below |
| JSON leases with manual release and no expiry | Replaced with a small transactional, fenced lease module |
| Architecture/operator docs and historical implementation report | Rewritten around reuse; old report clearly labeled superseded |

The trim commit changes 26 files, with 752 insertions and 1,706 deletions:
**954 net lines removed**. Relative to the pre-swarm base, the entire remaining
draft is **10 files and 921 added lines**. New production policy code is only
**326 lines in three modules**. Webchat has no remaining diff from `dcc2c8e`.

## Kept project-specific gaps

1. **`services/leases.py` (159 lines).** SQLite transactions grant all requested
   paths/resources together. Durable generations and unique tokens fence stale
   owners. Heartbeats have bounded TTL and a 24-hour grant deadline. Expired
   owners cannot renew, release or submit; overlapping ownership stays reserved
   until the existing runner supplies an observed stop/quarantine receipt.
   Recovery is retryable, committed grants survive restart, and interrupted
   transactions roll back. Legacy JSON ownership fails closed pending explicit
   reconciliation. Path, subtree, Unicode/case, symlink and rename-source rules
   remain conservative.
2. **`services/task_contracts.py` (62 lines).** Validates versioned task packages
   with owners, goals, behavioral invariants, paths, runtime resources, immutable
   dependencies and pinned test/eval/independent-acceptance configurations.
   Content identities and transitive dependency checks invalidate superseded
   work without adding another task registry or scheduler.
3. **`services/integration_policy.py` (105 lines).** Validates host-observed
   evidence for the exact source head, train base, candidate commit/tree,
   contract, policy, lease fence and complete author set. Required checks and
   review bind the entire envelope. Missing/red/duplicate/stale evidence is
   rejected. Effective model, creator, provider and harness remain distinct;
   delegated writers and resolvers count toward review independence. Unknown
   provenance, unlisted fallbacks and Grok/xAI cannot satisfy the gate.

Reuse `workspaces.py`, `jobs.py`, `dispatch_worker.py`, `command.py`, `runtime.py`,
`job-runner.sh`, `reviewer.sh`, `lanes.py`, `api.py`, `pr_evidence.py`,
`result_acceptance.py` and current Web Bob jobs/status views. Cursor worktrees or
Projects remain optional existing harness surfaces. Native GitHub merge queues
or GitLab merge trains own candidate construction, ordering, conflicts and ref
updates where configured. There is no second model client, scheduler, terminal
manager, merge executor, resolver service, board or deployer.

Updated docs:

- [Architecture](../../workspaces/swarm-arch-1730/docs/MULTI-LLM-SWARM-ARCH-0927.md)
- [Module contract](../../workspaces/swarm-arch-1730/docs/SWARM-V1.md)
- [Services README](../../workspaces/swarm-arch-1730/services/README.md)

## Validation

| Check | Result |
| --- | --- |
| Full existing service discovery plus new policy tests | 135 tests passed |
| Full webchat discovery, including its JavaScript quiet-hours check | 249 tests passed |
| Existing Web Bob parity evaluator, all-pass threshold | 24/24 cases passed |
| Targeted lease/contract/policy tests, included in service count | 17 passed |
| `git diff --check` / staged whitespace check | Passed |
| Webchat compared with pre-swarm base `dcc2c8e` | Identical tracked source |
| Remote branch SHA compared with local tip after normal push | Identical |

New tests exercise independent-process lease contention, SQLite rollback after
process death, restart/recovery, stale tokens and expiry, bounded renewal,
contract/dependency/config changes, exact candidate and moved-ref rejection,
complete independent review provenance, resource conflicts and a disjoint-file
semantic incompatibility caught by independent acceptance while syntax passes.

All temporary files stayed inside the authorized workspace. The initial baseline
passed 256 webchat tests; its service run hit the existing sandbox fixture's
assumption that its writable repo is outside the protected source tree. For final
validation, copied the exact tracked/unignored source to
`state/task-runs/swarm-trim/source` and used sibling `tmp` and `runtime` folders.
Every copied source file was hash-compared with the working source. Both full
suites passed with the real macOS sandbox unchanged. Logs are in the ignored
`state/task-runs/swarm-trim` directory. Tests used private state and no live model
calls; the parity result required every case to pass.

## Remaining integration boundary

These modules are opt-in policy primitives, not enabled services. A trusted
runner/CI adapter must observe Git identities, authenticate receipts, protect the
lease database/current contracts, pin acceptance contents/environments and wire
the validator as a required check on each actual native queue candidate. Queue
checks must be invalidated on contract/policy changes as well as candidate/train
movement. A JSON issuer name is not authentication. This draft does not claim
that host plan support, queue configuration or receipt transport is already
available or activated. The policy fails closed when supplied evidence violates
its contract; existing job execution is unchanged.

Only a normal fast-forward push to the requested draft branch was performed.
No merge, undraft, force-push, deploy, live service restart or Jeff notification.
The requested report is the sole write outside the workspace; no secrets were
read or printed.
