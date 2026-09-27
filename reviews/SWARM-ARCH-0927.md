# Swarm architecture v1 review — 2026-09-27

Implemented in `../workspaces/swarm-arch-1730`, branch `draft/swarm-arch-1730`,
starting at `dcc2c8e`. PR target: `rupret007/bob-brain: draft/webbob-clean-0927`.
The starting commit already contains three commits beyond that target; this
implementation is the change after `dcc2c8e`.

## Delivered behavior

- `services/leases.py`: atomic, process-locked path claims, idempotent retries,
  exact/subtree/root overlap refusal, case/Unicode alias handling, path and
  symlink validation, fenced release, and recoverable resolver transfer.
  Leases remain held until explicit release; failure does not silently free paths.
- `services/planner.py`: contract-ancestry validation, role routing by the
  architecture's strengths, Cursor's explicit underlying vendor, no Grok/xAI,
  no cheap conflict/deploy fallback, no same-model/vendor review, whole-project
  ownership for early hot-file refactors, and fenced worker start/finish.
- `services/merge_train.py`: serialized finished-worker processing in detached
  temporary worktrees; rebase onto the latest integration tip; mandatory tests,
  evals, and exact-candidate cross-vendor review; atomic local fast-forward on
  green; failure evidence returned to the original worker on red. The worker
  branch is preserved even when inherited Git configuration enables updateRefs.
  Checked-out integration branches, out-of-lease changes, stale worker SHAs,
  modified candidates, ownership changes, and moved train tips cannot advance.
- Rebase conflicts create durable Codex resolver jobs containing both diffs,
  conflicting paths, SHAs, and task intent. Claiming makes a separate draft
  branch and transfers the lease. Resolver results pass the full train again;
  review must be independent of the original author and every resolver.
- `services/project_board.py`: one versioned JSON board per project under
  `conductor/state/projects/`, containing worker/model/lease/task/branch/SHA/status
  records, integration contract, resolver jobs, timestamps, and revision.
- Web Bob reads the board in conversational status, `/api/status`, live provider
  snapshots, overview data, and conductor status. Saved assignments remain
  distinct from observed process activity. Stale or damaged state is visible;
  ownership tokens, diffs, and gate logs are excluded from the public projection.
- `services/swarm_eval.py`: the existing parity suite with temporary state and
  an all-cases-must-pass exit status. [SWARM-V1.md](../docs/SWARM-V1.md) documents
  API/CLI use, review receipts, lifecycle, recovery, and state ownership.

## Validation

All checks ran from the isolated worktree with no live model requests.

| Check | Result |
| --- | --- |
| Baseline service tests at `dcc2c8e` | 118 passed |
| Baseline Web Bob tests at `dcc2c8e` | 249 passed |
| Final `python3 -m unittest discover -s services -p 'test_*.py'` | 164 passed |
| Final `python3 -m unittest discover -s webchat -p 'test_*.py'` | 256 passed |
| `python3 services/swarm_eval.py` | 24/24 parity cases passed |
| CLI help and package imports | Passed for leases, planner, and merge train |
| `git diff --check` | Passed |

The 53 added tests cover independent-process overlapping claims, disjoint worker
assignment, role restrictions, exact-SHA ownership, real Git rebases and ordered
train integration, failed tests/evals/reviews, compare-and-swap races, resolver
handoff through a successful second integration, and status read-only behavior.

Recovery regressions interrupt the process after ref advancement, after green
board persistence but before lease release, and after resolver lease transfer
but before board persistence. Retrying reconciles state without falsely marking
an integrated commit as bounced or rewriting the author's branch.

## Operating limits and review findings

The services are opt-in one-shot APIs/CLIs; this change does not activate a timer,
launch model workers, connect the resolver queue to an existing live runner, or
install a review provider. The executor supplies actual model availability and
Cursor vendor identity, owns private worker checkouts, consumes resolver jobs,
and reports start/finish. The trusted review adapter receives the candidate
context and returns an exact-SHA receipt. Tests stub model review, so they prove
gate enforcement rather than review quality or remote identity authentication.

Leases coordinate cooperative workers and guard integration; they are not an OS
write sandbox. Their deliberate lack of automatic expiry requires stopping an
abandoned writer before releasing ownership. An interrupted ordinary assignment
may leave an orphan lease held for inspection. The train changes only its local
integration ref; it does not publish or deploy it.

No deployment, service restart, PR merge, undraft, or force-push was performed.
The live `webchat/.password` was not read or printed. The original dirty checkout
was left untouched; the architecture source document was copied into this draft
so its implementation contract travels with the PR.
