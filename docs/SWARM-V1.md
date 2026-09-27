# Swarm v1 operator contract

This implements [the September 27 architecture](MULTI-LLM-SWARM-ARCH-0927.md)
as opt-in Python services. No existing runner, launchd job, deployment pin, or
service startup is changed. The planner records assignments; an executor calls
`start`/`finish` around its worker. The train CLI processes finished assignments
once, so an operator can schedule it later without an always-on loop in v1.

## State and ownership

All entrypoints require an explicit conductor directory and a project ID.
Project IDs and worker IDs use letters, digits, underscores, and hyphens, up to
64 characters. Use a single project ID for each repository/integration train.

| File | Content |
| --- | --- |
| `leases/<project>.json` | Current owner, token, literal paths, claim time |
| `state/projects/<project>.json` | Repository, integration contract, worker records, resolver queue, revision |
| `locks/leases-<project>.lock` | Serializes claim, transfer, and release |
| `locks/plan-<project>.lock` | Serializes planner assignment and completion |
| `locks/train-<project>.lock` | Allows one integration attempt at a time |

Writes use temporary files, fsync, atomic replacement, and process locks.
Corrupt state fails closed. Runtime JSON is intentionally ignored by Git; the
planner creates the real board rather than committing fictional live workers.

Leases cover a file or its entire subtree. `webchat` conflicts with
`webchat/app.py`; `webchat/app.py` does not conflict with `webchat/app.py.bak`.
`.` reserves the whole repository. Globs, traversal, absolute paths, Git
metadata, and symlink aliases are refused. Case and Unicode aliases conflict
conservatively. Refactor assignments reserve `.` so shared hot-file extraction
finishes before parallel features start. Read-only roles do not take write leases.

Leases never silently expire. Stop the owner before releasing an abandoned
lease. A stale token cannot release a newer claim. A bounced worker retains its
paths; a successful integration releases them. Conflict resolution transfers
the fence directly to the resolver without a gap.

## API workflow

Run from this repository, or use `PYTHONPATH=services` with the short module
names. The source repo must already contain the integration branch and its
committed interface/test contract. Keep that integration branch unchecked out;
the train refuses to advance a ref attached to a worktree.

```python
from services.planner import Planner
from services.merge_train import MergeTrain

planner = Planner("/private/swarm/conductor", "webbob")
planner.initialize("/private/repos/webbob", "integration/webbob", contract_sha)

# Create an isolated worker worktree/branch from the integration contract first.
assignment = planner.assign(
    "cursor-leases", "Implement the agreed path lease interface",
    "feature", "draft/worker-leases", ["services/leases.py", "services/test_leases.py"],
    model_vendor="openai",  # Actual underlying Cursor model vendor.
)
planner.start(assignment["worker"], assignment["lease"]["token"])
# Executor works only inside this lease and commits in its private worktree.
planner.finish(assignment["worker"], assignment["lease"]["token"], full_worker_sha)

train = MergeTrain(
    "/private/swarm/conductor", "webbob",
    tests=[["python3", "-m", "unittest", "discover", "-s", "services"],
           ["python3", "-m", "unittest", "discover", "-s", "webchat"]],
    evals=[["python3", "services/swarm_eval.py"]],
    reviewer=cross_vendor_review,
)
results = train.tick()
```

`cross_vendor_review(context)` receives the exact rebased candidate SHA,
integration SHA, original worker SHA, task intent, authors, diff, and candidate
worktree. It must perform the review and return a receipt like:

```json
{"llm": "claude", "vendor": "anthropic", "sha": "FULL_REBASED_CANDIDATE_SHA", "approved": true}
```

The receipt must be for the candidate, not the original worker SHA. The reviewer
must differ from every contributing author by both model lane and vendor,
including the original author and any resolvers. Cursor requires an explicit
underlying vendor. Unknown vendors and Grok/xAI are rejected. Review adapters
and gate configuration are trusted operator inputs, not files supplied by a worker.
The receipt protocol validates identity and SHA; it does not authenticate a
remote reviewer or independently establish review quality.

## Integration and conflicts

Each attempt snapshots the current train tip, verifies the finished branch and
its lease, checks the worker diff (including both sides of renames) against that
lease, and rebases a detached disposable worktree onto the tip. The author's
branch is never rewritten. Tests and evals must both be configured and succeed;
the strict eval wrapper runs the existing Web Bob parity cases against private
temporary state and rejects even one failing case. Gate subprocesses receive
a private `BOB_ROOT`, bounded timeouts, and no shell expansion.

After cross-vendor review, the train checks that the candidate stayed unchanged,
the worker stayed at the submitted SHA, and the lease still belongs to it. It
proves the candidate descends from the old train tip, then advances the local ref
with an atomic `update-ref <new> <expected-old>`. A moved tip bounces the worker;
the next submission reruns the gates against the new tip. The service never
pushes, merges a PR, changes draft state, or deploys.

Red tests/evals/review set the original worker to `bounced` with stage, command,
exit code, and bounded output recorded on the board. The executor calls `start`,
fixes its branch, and calls `finish` again. Output and ownership tokens stay out
of the Web Bob projection.

A content conflict sets the worker to `conflict` and atomically queues a
`resolver_jobs` record on the project board. It contains both diffs from the
merge base, conflicting paths, original intent, the two SHAs, a new draft branch
name, and a pinned `codex` conflict-resolution role. Consume it with:

```python
resolver = planner.claim_resolver(job_id, "codex-resolver-1")
# Create a private worktree for resolver["branch"]. That branch starts at the
# original worker SHA. The Codex executor rebases onto the saved integration SHA,
# resolves conflicts, runs checks, and commits/continues the rebase.
planner.start(resolver["worker"], resolver["lease"]["token"])
planner.finish(resolver["worker"], resolver["lease"]["token"], full_resolved_sha)
train.tick()  # Repeat tests, evals, and a review independent of both authors.
```

Resolver claiming is retryable across interruption of branch creation, lease
transfer, and board writes. The train also reconciles an interrupted green ref
advance or lease release on its next tick. An orphaned ordinary assignment lease
after a storage failure remains held for inspection; it is never stolen.

## Roles and status

`planner.route` chooses Codex for architecture, hard fixes, conflicts, and deploy
roles; Claude for long-context design, reply/UX quality, careful refactors, and
final review; Cursor for features and tests; Gemini for audits, gap analysis,
planning, and second review; MiniMax for volume reviews, test cases, eval grading,
and push critique. Review fallback is cross-vendor. Cheap models cannot become
deployers or conflict resolvers; routine features do not fall back to expensive
lanes. Deploy is a routing designation only: these services contain no deploy action.

Each worker record includes `worker`, `llm`, `vendor`, `lease`, `task`, `role`,
`branch`, `sha`, `status`, and `updated_at`. Status moves through
`assigned → running → finished → integrating → merged`, or to `bounced` or
`conflict`. `integrated_sha` records the rebased commit separately from the
original worker SHA. Resolver jobs have `queued/claiming/claimed/resolved` states.

Web Bob reads boards directly in live status snapshots, the tab overview,
`/api/status`, the conductor API, and conversational status including “Who is
working on what?”.
It projects only assignment fields and lease paths, never lease tokens, diffs,
gate output, or private repository paths. Saved assignment states do not inflate
live worker counts. Missing boards are empty; damaged boards are reported as
unavailable. Assignments older than five minutes are labeled stale.

## One-shot CLI and validation

`python3 services/leases.py --conductor PATH --project ID claim OWNER PATH...`
claims paths; `release OWNER TOKEN` releases them; `list` inspects them.

`python3 services/planner.py --conductor PATH --project ID ACTION --spec FILE`
accepts `init`, `assign`, `start`, `finish`, `claim-resolver`, or `board`.
`FILE` is a JSON object with the API method's keyword arguments; `board` needs no
spec. The CLI is an operator interface and may include private ownership tokens.

`python3 services/merge_train.py --conductor PATH --project ID --config FILE`
processes one tick; `--worker ID` limits it to one worker. The trusted config has
`tests` and `evals` arrays of argv arrays, `timeout` seconds, and `review_command`
as an argv array. The adapter appends a context JSON file path, runs in the
candidate worktree, and expects the receipt JSON on stdout. A failed/conflicted
tick exits nonzero. Nothing installs or schedules the CLI automatically.

```sh
python3 -m unittest discover -s services -p 'test_*.py'
python3 -m unittest discover -s webchat -p 'test_*.py'
python3 services/swarm_eval.py
git diff --check
```

The tests use temporary repositories and mocked model boundaries. They exercise
real Git rebases and fast-forwards, conflict-to-resolver-to-green flow, red gates,
ownership and ref races, process-interruption recovery, and read-only Web Bob status.
