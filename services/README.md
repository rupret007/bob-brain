# Mini conductor services

Run `/bin/bash conductor/services/start-all.sh` from any directory. It starts only
missing screens, retires the idle `mini-conductor` screen, and shares the watchdog's
restart limits. Each entrypoint also supports `--once`; a live instance's lifetime
lock prevents a concurrent one-cycle invocation. Inspect `logs/<name>.log` and
`conductor/heartbeats/<name>`.

| Service | Interval | Stale after |
| --- | ---: | ---: |
| job-runner | 900 seconds | 2700 seconds |
| reviewer | 300 seconds | 900 seconds |
| dashboard-updater | 300 seconds | 900 seconds |
| watchdog | 180 seconds | 540 seconds |

The watchdog checks the three peer services. The separate launchd watchdog guard
checks all four, including a hung watchdog. Every automatic entrypoint uses the
same durable rolling cap of three restart attempts per service per hour. Initial
starts do not consume the restart allowance. A restarted service gets a startup
grace of three intervals. Failed cycles do not touch heartbeats; a completed cycle
with a recorded API/publish failure is healthy but degraded and creates a JEFF alert.

`jobs.jsonl` is an append-only, locked/fsynced journal with `launched`, `running`, and
`harvested` states. A launch intent is written before starting its screen. Restart
recovery reconnects to live screens, resumes interrupted jobs through the coding
lease checks, or repeats the idempotent harvest. A result is harvested only after
its deliverables and queue promotions are persisted. BLOCKER closeouts are retained
and counted separately from successful results. An interrupted final JSONL append
is saved as `.interrupted-tail` and repaired; corruption in the middle fails visibly.
The old historical state is imported once. Stale historical running records with
no current queue ownership or screen become explicit BLOCKER closeouts, never
newly launched jobs or claimed successful work.

The reviewer saves `RESULT.txt.minimax.md` / `RESULT.txt.gemini.md` (or the same
suffixes beside a BLOCKER/RESULT.md). Content-hash receipts let each model resume
independently without redoing successful calls. One result per cycle bounds API
work. Missing keys skip that model. Network, API, malformed, empty and truncated
responses retry three times with 2/4 second backoff and `curl -m 60`; exhausted
model failures defer for one hour. `keys.env` is sourced afresh each cycle. Keys are
passed via curl stdin and never printed, put into argv, or published. No credit
purchases, account changes, or billing configuration are performed.

The dashboard always writes `conductor/dashboard.json` first. It uses the existing
GitHub CLI login (or `BOB_DASHBOARD_TOKEN` in keys.env) to update only the public
repo's `agents-status.json` through a normal Contents commit. No merges or force
pushes. This matches the existing dashboard input. The payload contains coarse
agent/service health only. Failure leaves a local snapshot and JEFF alert, then
the loop continues. The dashboard's scheduled refresh consumes that input.

`job-runner` schedules `run-conductor.sh` every two hours in a temporary
`svc-conductor-pass` screen so the long pass does not stall ticks. The schedule
survives restart, preserving the old pass's initial cadence. Each pass records
0–4 health, unharvested jobs, restart counts and confirmed model calls, snapshots
its own work, obtains both critiques, and attempts one verified learned improvement.
Pass artifacts and proof live in `conductor/passes/`.

For login after reboot, grant Full Disk Access to `/bin/bash`, then run:

```bash
/bin/bash ~/Documents/bob-overnight-inject/conductor/launchd/install.sh
```

This installs the two supplied LaunchAgents under `~/Library/LaunchAgents`, retires
the old timers with backups, and loads them. Merely writing plist files inside this
workspace does not install LaunchAgents. macOS LaunchAgents start at user login.

Tests use a disposable directory and mocked transports/processes; they never buy
credits, merge, message anyone or touch live job screens:

```bash
python3 conductor/services/test_services.py
```
