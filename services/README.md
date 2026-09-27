# Mini conductor

Start or recover with `bash conductor/services/start-all.sh`. `launchd/install.sh`
installs and loads bob-services (5 minute guard) and bob-watchdog (3 minute guard)
for this user's login. Reboot startup occurs after login; no login settings are
changed. `loop.sh` and old queue entrypoints only defer to these services.

| Service | Interval | Responsibility |
| --- | --- | --- |
| job-runner | 60s | Consume state/queue.jsonl, assign lanes, recover, retry/fallback, promote |
| reviewer | 300s | Short Claude + Cursor/MiniMax/Gemini critiques with cached receipts |
| dashboard-updater | 300s | Local dashboard.json; optional draft branch publication |
| watchdog | 180s | Heartbeats, verified restarts, three attempts/hour cap |

`locks/<service>.pid` plus lifetime flock ownership prevent duplicate services.
Startup verifies both screen presence and the lock. Restart stops the recorded
loop process as well as its screen; macOS can orphan the shell on screen exit.
`MAINTENANCE` pauses automatic entrypoints while an operator changes the core.
Service logs retain a bounded tail backup once they exceed 5 MiB.

`state/queue.jsonl` is the durable request and promotion journal; `jobs.jsonl`
records executions. Both append complete rows under locks and fsync each write.
Only verified results become harvested. BLOCKERs remain unfinished. Each provider
gets an initial attempt and one retry with backoff before moving to the next
eligible provider. Exhausted fallback chains remain blocked. Legacy
blocked closeouts are reopened as blocked; old shell scripts are never replayed.
A completed result arriving later can still be harvested idempotently.

The scheduler consumes the durable queue even when INDEX.md is absent. It also
imports `services/backlog.json`, `services/projects.json`, and READY rows in
`../next-prompts/INDEX.md` (optional adjacent JSON specs), including WebBob requests.
Lower numeric priority runs first, with FIFO ordering at equal priority.
Web Bob writes this journal directly. Its synchronous dispatch entrypoint runs a
tick for one requested id and returns a receipt after observing the worker's
heartbeat and named screen; ordinary periodic ticks continue to drain the queue.
The chat process supplies an explicit state root without changing service-module
globals. `python3 services/lane_integration_smoke.py` proves three journal-only
assignments and the same-reply Web Bob queue/start path with temporary screen
workers and simulated provider responses. It does not restart any service.
Cursor is preferred for coding and is also a council/reviewer member. Codex and Cursor own coding and orchestration. Claude only provides short council critiques and small reviews: one call at a time, bounded context, 120s maximum, and a durable one-hour rate-limit cooldown. The five
shared model lane leases permit one call per lane across every entrypoint. A sixth
`mini` lane runs explicit local test commands without a model. Multiple coders in
the same repo, including WebJam, use separate worktrees and draft branches with
non-overlapping file scopes. Overlapping scopes serialize. Missing scope means
the whole repo; an external WebJam worker without scope still holds that repo.

Queue producers use `queue_store.enqueue(spec)` or
`BOB_ROOT=/path/to/root python3 conductor/services/queue_store.py enqueue request.json`.
`list` prints the current queue. The minimal request has `id` (stable producer id),
`goal`, `repo` (local Git checkout), `role`, and `priority`. Roles are `build`,
`review`, `research`, `critique`, `test`, and `council`. Example:

```json
{
  "id": "scheduler-fix",
  "goal": "Fix the scheduler regression and commit/push the assigned draft branch",
  "repo": "/path/to/repo",
  "role": "build",
  "priority": 1,
  "scope": ["services/"],
  "test_commands": [["python3", "-m", "unittest", "discover", "-s", "services"]]
}
```

`scope` accepts literal relative file/directory paths, not globs. Build and test
jobs require explicit `test_commands` argv lists before execution. Producers split
large goals by supplying `parts`, an array of child specifications with their own
goals and scopes. The scheduler expands these idempotently; children inherit repo,
role, priority, scope, base_ref and test commands unless overridden. It does not
guess file ownership or test commands from prose. `depends_on` optionally lists
request ids that must reach completed/Jeff-draft before dispatch.

Workers pulse heartbeat every 15 seconds. The 90-second stale threshold and
30-second launch grace preserve reservations through screen startup/restart.
Stale workers are stopped only after process identity verification; an unverified
live worker keeps its lane. Tokens reject stale attempt updates. Scheduling pauses
under MAINTENANCE or STOP-WEBBOB. Backoff and provider attempts survive restarts.

Verified work promotes to a Claude review (with coding-lane fallback), then two
independent council jobs (Gemini/MiniMax preferred, coding-lane fallback), then
`jeff-draft`. Each review/council receipt must contain a single `VERDICT: PASS`;
missing/negative verdicts do not advance. This gate schedules independent council
assessments through the shared queue; the separate interactive `council.py` workflow
remains available. Split parents reach Jeff-draft only after every part does.
Build promotion requires tests at the exact result SHA plus Git conflict checks
across sibling build drafts. Conflict checks compute object trees and never merge
branches. Result files are hashed after verification. Promotion does not merge,
undraft, or publish a final build. All queue stages/results appear on the runtime
lane board in STATUS.md and in `snapshot()["lane_board"]`.

Every job has an explicit repo, worktree, draft/ branch, kind, prompt and lane.
Existing PR targets are checked as OPEN + draft before execution. Push hooks allow
only the approved branch and fast-forward updates. Git-capable Codex jobs use the
bypass flag inside a separate macOS boundary denying writes to the live conductor,
bin helpers, queue and handoff. CLI subprocesses have DEVNULL stdin and hard
wall-clock timeouts; timeout/signals kill the entire child process group.
The boundary protects the core from same-user chmod attempts too. It is not a
separate-user security boundary or a restriction on every possible remote action;
GitHub account permissions and the standing draft-only rules still apply.

`PROMPT.md`, bootstrap and service scripts are chmod a-w. Bootstrap runs bash -n
and python -m py_compile before importing services. Invalid core files are copied
to reviews/quarantine/, then restored from Git's last-good tag and checked again.
Scheduled council passes only assess and preserve proposed evidence. To maintain
this core: set MAINTENANCE, edit intentionally, run the tests/syntax check, commit,
advance the local last-good tag, remove MAINTENANCE, and run start-all.sh. Never
advance last-good over failed checks. The Git repository excludes credentials,
worktrees, runtime journals and transient logs.

runtime.py alone writes STATUS.md. Alerts go to alerts.json; worker observations
start as STATUS-NOTE.md in the job worktree and are copied to status/notes-<lane>.md.
Cursor `needs_login` is visible there and automatically clears after successful
login status on the next tick. No service attempts to log in or buy credits.

All API calls reserve worst-case cost under a ledger lock before the request.
MiniMax stops before a request could exceed $48, including prior UX usage and
uncertain calls. Raw usage settles reservations even for rejected/truncated model
answers; missing/failed responses retain their reservation. CLI token usage and
reported costs are recorded; unknown subscription charges remain unknown. The
compat/ directory contains installed legacy wrapper copies; asks/tip reviews use
the same metered transport. MiniMax-M2.7 and Gemini 2.5 Flash are the priced models.

Rates were checked against [MiniMax pricing](https://platform.minimax.io/subscribe/token-plan?tab=api-enterprise)
and [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing). Codex launch
flags were checked locally and against the [official CLI reference](https://learn.chatgpt.com/docs/developer-commands?surface=cli).

Validation: `python3 -m unittest discover -s services -p 'test_*.py'`,
`python3 bootstrap.py check`, and the live smoke harness `python3 services/smoke.py`
with keys.env exported. Smoke evidence is in reviews/SMOKE.md.

Scheduler-only screen drill: `python3 services/scheduler_smoke.py`. It queues three
split goals, occupies all six lanes, and exercises branch tests and promotion to
Jeff-draft using temporary Git repos and real screen workers. Provider replies are
explicit fixture adapters; no paid/network provider calls occur. Evidence can be
written with `--evidence state/queue-proof.md`.
