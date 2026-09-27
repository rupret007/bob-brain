# Self-improvement round 2 (Cursor lane) — result

Measured 2026-09-27T05:16:00+00:00. Implementation on **`draft/self-improve-r2`** in worktree `../worktrees/conductor-self-improve-r2`. **Commit: `a6959f1`.** Live read-only core unchanged (not merged, `last-good` not advanced).

## Top 5 holes (ranked by impact)

| Rank | Hole | Evidence | Severity |
| --- | --- | --- | --- |
| 1 | **launchd auto-start exit 126** (`Operation not permitted`) | `logs/webchat-launchd.log` and `logs/com.jeff.bob-services.log`: repeated `getcwd: cannot access parent directories` and `/bin/bash: …/conductor/…: Operation not permitted`. WEBCHAT-RESULT.md documents webchat; services log shows **bob-services** hits the same gate. Plists used `WorkingDirectory` under `~/Documents` and `ProgramArguments` pointing at scripts under Documents. | **High** — login/reboot does not start services or webchat without Terminal |
| 2 | **Blocked legacy jobs re-marked READY in queue** | `jobs.recover()` called `update_index(..., "READY")` for every legacy job with a `file`, even when `state == "blocked"`. `next-prompts/INDEX.md` row 17 shows **READY** with recovery `legacy job needs a private worktree specification` while STATUS lists blocked legacy jobs. Scheduler can pick work that is intentionally blocked. | **High** — false queue signal, wasted lane attempts |
| 3 | **MiniMax committed spend inflated by stuck reservations** | STATUS/HARDEN-EVIDENCE: **$1.08 spent + $1.15 reserved** (142 calls). `api.http_json` reserved per attempt but left failed transports unsettled, so `reserved_usd` stayed on the ledger indefinitely. | **Medium** — cap math and STATUS misleading |
| 4 | **13 blocked jobs, 0 running while lanes ready** | STATUS.md: `0 launched, 0 running`, `13 blocked jobs retained`, `RECOVERY: 13 unharvested`. `logs/job-runner.log`: many `maintenance: launch paused` lines during harden. Lanes idle with backlog READY rows (e.g. 17–23). | **Medium** — throughput; partly maintenance/external WebJam hold, partly hole #2 |
| 5 | **Watchdog single-cycle PermissionError** | `logs/watchdog.log` `2026-09-27T04:06:57 cycle error: PermissionError` (one cycle; later cycles good). `runtime.takeover()` returns early on `PermissionError` when probing `/tmp/mini-conductor.lock`. | **Low** — transient; self-healed |

## Top 3 fixes implemented

### 1. launchd: `~/bin` launchers + home WorkingDirectory (fix #1)

- Added `launchd/bin-stub/bob-launch-{services,watchdog,webchat}.sh` installed to `~/bin` by `launchd/install.py` with `@@BOB_ROOT@@` substituted.
- Plists now run **`/Users/jeffstory/bin/bob-launch-*.sh`** only; `WorkingDirectory` is **`/Users/jeffstory`** (not Documents).
- `install.py` installs launchers before bootstrap/load and uses them for post-install smoke starts.

**Regression:** `test_launchd_plists_use_home_bin_launchers`

**Diagnosis (FDA):** launchd still executes `/bin/bash` on scripts under `~/Documents/bob-overnight-inject/…` inside the wrapper. macOS TCC often still requires **Full Disk Access for `/bin/bash`** (or moving the repo out of Documents) for that second hop. The wrapper fixes the **plist entrypoint + getcwd** failures; it does not guarantee Documents read without FDA.

### 2. Legacy recover: do not READY blocked jobs (fix #2)

- `jobs.recover()` only calls `update_index(record, "READY")` when `record["state"] != "blocked"`.

**Regression:** `test_blocked_legacy_job_does_not_mark_index_ready`

### 3. Metered HTTP: abandon failed reservations (fix #3)

- `budget.abandon()` charges the worst-case reservation on transport failure.
- `api.http_json` calls `abandon` when an attempt fails (per-attempt reserve/abandon).

**Regression:** `test_http_failure_abandons_reservation`

## Verification

| Check | Result |
| --- | --- |
| `python3 -m unittest discover -s services -p 'test_*.py'` | **PASS** — 50 tests |
| `python3 bootstrap.py check` | **PASS** |
| `bash -n` on maintained shells in worktree | **PASS** |
| `plutil -lint` on three bob LaunchAgent plists | **PASS** |
| Live `launchctl` reload / reboot | **NOT RUN** — draft branch only; live core read-only |

**Overall: PASS** (implementation + tests). **Live launchd auto-start: PENDING** until install + permission check below.

## Jeff must do (exact)

1. **Full Disk Access (if auto-start still 126 after step 2):** System Settings → Privacy & Security → **Full Disk Access** → add **`/bin/bash`** (Cmd+Shift+G in the file picker), enable it. This is the documented macOS gate for launchd reading scripts under Documents.
2. **Activate draft on the mini** (when ready): check out `draft/self-improve-r2` per your harden procedure (`MAINTENANCE`, tests, advance `last-good`, `start-all.sh`). Not done by this job.
3. **Reinstall agents from Terminal (after activation):**
   ```bash
   bash ~/Documents/bob-overnight-inject/conductor/launchd/install.sh
   ```
   Or webchat only:
   ```bash
   bash ~/Documents/bob-overnight-inject/conductor/launchd/install.sh --webchat-only
   ```
4. **Verify:** `launchctl print gui/$(id -u)/com.jeff.bob-webchat | grep lastexit` (expect not 126), tail `logs/webchat-launchd.log` and `logs/com.jeff.bob-services.log`, `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8787/login`.

## Not done (by design)

- No merge, undraft, force-push, texts, emails, or spend beyond caps.
- **`conductor/webchat/`** not edited (another job owns it).
- Live core not modified; no `last-good` advance.
