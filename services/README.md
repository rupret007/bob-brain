# Mini conductor

Opt-in same-project swarm services (`planner.py`, `leases.py`, `merge_train.py`)
are documented in [SWARM-V1.md](../docs/SWARM-V1.md). They use explicit state
roots and a separate project board; existing loops and deployment stay unchanged.

Start or recover with `bash conductor/services/start-all.sh`. `launchd/install.sh`
installs and loads bob-services (5 minute guard) and bob-watchdog (3 minute guard)
for this user's login. Reboot startup occurs after login; no login settings are
changed. `loop.sh` and old queue entrypoints only defer to these services.

| Service | Interval | Responsibility |
| --- | --- | --- |
| job-runner | 5s + cycle time | Claim/recover/refill chat workers; legacy project housekeeping every 60s |
| reviewer | 300s | Short Claude + Cursor/MiniMax/Gemini critiques with cached receipts |
| dashboard-updater | 300s | Local dashboard.json; optional draft branch publication |
| watchdog | 180s | Heartbeats, verified restarts, three attempts/hour cap |

`locks/<service>.pid` plus lifetime flock ownership prevent duplicate services.
Startup verifies both screen presence and the lock. Restart stops the recorded
loop process as well as its screen; macOS can orphan the shell on screen exit.
`MAINTENANCE` pauses automatic entrypoints while an operator changes the core.
Service logs retain a bounded tail backup once they exceed 5 MiB.

`jobs.jsonl` is an append-only/fsynced journal. States are queued, launched,
running, blocked, harvested. Only verified results become harvested. BLOCKERs
remain unfinished, retry with backoff and escalate after three attempts. Legacy
blocked closeouts are reopened as blocked; old shell scripts are never replayed.
A completed result arriving later can still be harvested idempotently.

The scheduler reads `services/backlog.json`, `services/projects.json`, and READY
rows in `../next-prompts/INDEX.md` (optional adjacent JSON specs). It prioritizes
WebJam > StoryBoard > AdoptIQ > shelf, with explicit #159/#160 CI fixes before UX.
Cursor is preferred for coding and is also a council/reviewer member. Codex and Cursor own coding and orchestration. Claude only provides short council critiques and small reviews: one call at a time, bounded context, 120s maximum, and a durable one-hour rate-limit cooldown. The five
shared lane leases permit one call per lane across every entrypoint. The scheduler
allows five jobs, one WebJam coder and separate Git worktrees under ../workspaces/.

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
and python -m py_compile before importing services. Validation and recovery are serialized and retried once. Invalid committed core files
are copied to reviews/quarantine/, then restored from the local last-good tag and
checked again. Uncommitted local changes are preserved; a failed launch waits for repair.
Scheduled council passes only assess and preserve proposed evidence. To maintain
this core: set MAINTENANCE, edit intentionally, run the tests/syntax check, commit,
advance the local last-good tag, remove MAINTENANCE, and restart the affected services. Never
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

## Web Bob dispatch

`state/queue.jsonl` records the originating chat/request, worker claim token,
execution timestamps, renewable lease, bounded retries and final result. Chat
intents are saved before enqueueing. The chat process saves a deterministic result
message before acknowledging delivery, so restarts and failed writes do not lose
or duplicate answers. `webchat/live_dispatch_proof.py` exercises the authenticated
chat API with real workers; `reviews/WEBBOB-DISPATCH-0927.md` records live evidence.

Gemini and MiniMax receive answer-only task instructions and supplied evidence;
they do not get a worktree, branch, or filesystem instructions. Explicit file
inspection uses Codex/Cursor with read tools, and file changes require a writing
CLI. Selecting an API worker for such a task returns a capability explanation
before queueing. Explicit max-mode packages use the same capability check.

A worker answer must pass result acceptance before `succeeded` is recorded.
Empty answers, blockers, refusals and missing required exact text fail directly.
Other model answers receive a separate task/answer review on the same lane,
under its existing lease and budget. A rejection or unavailable/malformed review
is terminal (`rejected` event, `failed` status); it does not consume the provider
outage retry loop. The redacted answer and rejection reason stay in the queue,
and chat delivers one failed result. Successful rows retain an acceptance
receipt bound to the result SHA-256. File tasks and Mini's local test runs use
server-verified execution instead of an additional semantic review. Semantic
acceptance checks whether an answer completes the task; it is not independent
proof of every factual claim.

The local, ignored `state/dispatch-code-root` file pins job-runner and svc-webchat
to the tested draft checkout. `BOB_ROOT` and `BOB_WEBCHAT_DIR` keep queue data,
credentials, logs, static assets and conversation history in their existing
locations. Worker subprocesses inherit the same code pin, source fresh credentials,
and protect both the live conductor and deployed code checkout from edits.
To update deployment, test and locally commit a draft checkout, update the local
recovery tag and code pin, then restart only job-runner and svc-webchat.
